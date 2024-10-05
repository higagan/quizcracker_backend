from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel, validator, Field
import google.generativeai as genai
import json
import logging
import time
import re
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI instance
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; replace with specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Replace with your actual API key
API_KEY = "AIzaSyAe0mFYAaMD5XRTWf78jy9Tf2Vzp_UkOHs"

# Configure the model with the API key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "temperature": 0.1,
    },
)

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
    numQuestions: int  # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

# Pydantic model for request payload with email validation
class FeedbackRequest(BaseModel):
    feedback: str
    email: Optional[str] = None  # Make the email field optional  
    
    # Ensures email is a valid email format
    @validator('email', always=True, pre=True)
    def validate_email(cls, v):
        if v is None or v == "":
            return v
        else:
            # Basic regex for email validation
            email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
            if not re.match(email_regex, v):
                raise ValueError("Invalid email address")
            return v

def sanitize_response(response_text):
    # Remove backticks and extraneous backslashes
    response_text = response_text.replace('`', '').replace('\\', '')
    
    # Remove code snippets enclosed in triple quotes
    response_text = re.sub(r'""".*?"""', '', response_text, flags=re.DOTALL)
    response_text = re.sub(r"'''.*?'''", '', response_text, flags=re.DOTALL)
    
    # Remove code snippet markers in questions
    response_text = re.sub(r'("question"\s*:\s*")(.+?)(\\n\\n.*?)(?=",)', r'\1\2', response_text, flags=re.DOTALL)
    
    # Remove newlines inside JSON strings
    response_text = re.sub(r'\n', ' ', response_text)
    
    # Remove any remaining control characters
    response_text = ''.join(c for c in response_text if c.isprintable())
    
    # Remove any stray strings not associated with keys
    response_text = re.sub(
        r',\s*"[^"]+"\s*(?=,|\})',
        '',
        response_text
    )
    
    # Fix missing brackets in 'options' field if necessary
    def fix_options(match):
        options_content = match.group(1)
        # Ensure options_content starts and ends with square brackets
        if not options_content.strip().startswith('['):
            options_content = '[' + options_content
        if not options_content.strip().endswith(']'):
            options_content = options_content + ']'
        return f'"options": {options_content}'
    
    response_text = re.sub(
        r'"options"\s*:\s*([^]]+?\])',
        fix_options,
        response_text
    )
    
    # Ensure the response is a valid JSON array
    response_text = response_text.strip()
    if not response_text.startswith('['):
        response_text = '[' + response_text
    if not response_text.endswith(']'):
        response_text = response_text + ']'
    
    return response_text

def is_similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.9

@app.get("/get-subtopics")
async def get_subtopics(
    request: Request,
    topic: str = Query(..., description="Generate subtopics for a given topic"),
):
    try:
        response = model.generate_content(
            f"Provide a combined list of all the core concepts and advanced features in {topic} without explanation in brief in a list without segregation."
            "Format the output as valid JSON and ensure there are no unterminated strings, special characters and unescaped characters."
        )
        subtopics = response.text.strip()
        return {"subtopics": subtopics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

async def get_questions(request: Request, quiz_request: QuizGenerationRequest):
    start_time = time.time()

    subtopics_str = (
        ", ".join(quiz_request.subtopics)
        if quiz_request.subtopics
        else "general concepts"
    )
    difficulty_str = ", ".join(quiz_request.difficulty)
    question_types_str = ", ".join(quiz_request.questionTypes)
    ai_used = "gemini-1.5-flash"
    topic = quiz_request.topic

    prompt = (
        f"Generate {quiz_request.numQuestions} {question_types_str} questions on '{topic}' "
        f"focused on '{subtopics_str}'. Return the questions as a JSON array of objects, where each object has exactly the following fields "
        f"and in this order: 'question' (string), 'options' (array of strings), 'answer' (string), and 'difficulty' (string). "
        f"Ensure the difficulty is '{difficulty_str}'. "
        "The 'options' array must include the correct answer provided in the 'answer' field. "
        "The 'answer' field must exactly match one of the options. "
        "Do NOT include any code snippets, code examples, programming code, or any kind of code in any field. "
        "All content should be in plain text and in full sentences. "
        "Avoid using unescaped double quotes inside string values. "
        "Ensure that the 'options' field is always an array (e.g., \"options\": [\"Option1\", \"Option2\"]). and should have 4 values"
        "Before completing, validate that the JSON is correct and properly formatted."
    )

    logging.info(f"Prompt generation took {time.time() - start_time:.2f} seconds")
    logging.info(f"Generated prompt: {prompt}")

    MAX_RETRIES = 3
    retry_count = 0
    raw_questions = None  # Initialize raw_questions

    while retry_count < MAX_RETRIES:
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            logging.info(f"API response text: {response_text}")

            # Log the API response instead of writing to a file
            logger.info("API response received.")

            # Sanitize the response
            sanitized_response = sanitize_response(response_text)

            # Try to parse the JSON
            try:
                raw_questions = json.loads(sanitized_response)
                break  # Parsing succeeded
            except json.JSONDecodeError as e:
                logging.error(f"JSON decoding failed: {str(e)}")
                retry_count += 1
                time.sleep(1)  # Optional delay between retries
        except Exception as e:
            logging.error(f"Error during content generation: {str(e)}")
            retry_count += 1
            time.sleep(1)

    if raw_questions is None:
        raise HTTPException(status_code=500, detail="Failed to parse JSON after sanitization.")

    # Ensure raw_questions is a list
    if isinstance(raw_questions, dict):
        raw_questions = [raw_questions]

    logging.info(f"Parsed raw_questions type: {type(raw_questions)}")
    logging.info(f"Parsed raw_questions content: {raw_questions}")

    # Initialize structured_questions
    structured_questions = []
    quiz_id = id(request)
    for idx, question in enumerate(raw_questions):
        logging.info(f"Processing question {idx}: {question}")

        # Skip questions containing code snippets
        if any(keyword in question.get('question', '').lower() for keyword in ['code snippet', 'code example', 'following code']):
            logging.warning(f"Question {idx} contains code snippet. Skipping.")
            continue  # Skip this question

        # Ensure required fields exist in question
        if 'options' not in question or 'answer' not in question or 'question' not in question:
            logging.warning(f"Question {idx} is missing required fields. Skipping.")
            continue  # Skip this question

        options = [
            {"id": chr(97 + i), "text": str(option).strip()}
            for i, option in enumerate(question["options"])
        ]

        # Determine the correct answer ID
        answer_text = str(question["answer"]).strip()
        answer_id = None

        # Attempt to match the answer with the options
        for option in options:
            if is_similar(option["text"], answer_text):
                answer_id = option["id"]
                break

        if answer_id is None:
            # Optionally, add the answer to the options
            answer_id = chr(97 + len(options))
            options.append({"id": answer_id, "text": answer_text})
            logging.warning(f"Answer not found in options for question {idx}. Added answer to options.")

        structured_question = {
            "id": f"question_{quiz_id}_{len(structured_questions)+1}",
            "text": question["question"],
            "options": options,
            "answer": answer_id,
            "difficulty": question.get("difficulty", (
                quiz_request.difficulty[0]
                if len(quiz_request.difficulty) == 1
                else "medium"
            )),
        }
        structured_questions.append(structured_question)

        # Removed BigQuery insertion
        # insert_structured_question_to_bigquery(
        #     quiz_id,
        #     topic,
        #     subtopics_str,
        #     question_types_str,
        #     ai_used,
        #     structured_question,
        # )

    if not structured_questions:
        raise HTTPException(status_code=500, detail="No valid questions generated.")

    logging.info(f"Total processing took {time.time() - start_time:.2f} seconds")

    return {"id": quiz_id, "quiz": {"questions": structured_questions}}

async def get_questions_in_batches(request: Request, quiz_request: QuizGenerationRequest):
    total_questions = quiz_request.numQuestions
    batch_size = 10  # Adjust based on the AI model's capabilities
    all_questions = []
    batches = (total_questions + batch_size - 1) // batch_size  # Ceiling division

    for batch_num in range(batches):
        logging.info(f"Requesting batch {batch_num+1}/{batches}")
        batch_request = QuizGenerationRequest(
            topic=quiz_request.topic,
            subtopics=quiz_request.subtopics,
            difficulty=quiz_request.difficulty,
            numQuestions=min(batch_size, total_questions - len(all_questions)),
            questionTypes=quiz_request.questionTypes
        )
        try:
            response = await get_questions(request, batch_request)
            all_questions.extend(response['quiz']['questions'])
        except HTTPException as e:
            logging.error(f"Batch {batch_num+1} failed: {str(e)}")
            continue  # Optionally, you could retry or handle the error differently

    if not all_questions:
        raise HTTPException(status_code=500, detail="Failed to generate any questions.")

    return {"id": id(request), "quiz": {"questions": all_questions}}

@app.post("/get-quiz")
async def get_quiz_endpoint(request: Request, quiz_request: QuizGenerationRequest):
    if quiz_request.numQuestions > 10:
        # Use batch processing for large number of questions
        return await get_questions_in_batches(request, quiz_request)
    else:
        # Single request is sufficient
        return await get_questions(request, quiz_request)

# Feedback API endpoint
@app.post("/feedback")
async def submit_feedback(request: Request, feedback_request: FeedbackRequest):
    try:
        # Log the feedback instead of inserting into BigQuery
        logger.info(f"Received feedback: {feedback_request.feedback}")
        if feedback_request.email:
            logger.info(f"Feedback provided by email: {feedback_request.email}")

        # Generate a unique feedback ID
        feedback_id = id(request)

        return {"message": "Feedback submitted successfully!", "feedback_id": feedback_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Main entry point for the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="0.0.0.0", port=8000
    )
