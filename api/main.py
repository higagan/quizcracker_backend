from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import openai
import os
import json
import logging
import time
from fastapi.openapi.utils import get_openapi
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI instance
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, replace with specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Single API key for Gemini
GEMINI_API_KEY = 'AIzaSyAe0mFYAaMD5XRTWf78jy9Tf2Vzp_UkOHs'

# Configure Gemini model with the single API key
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

# OpenAI API key
OPENAI_API_KEY = '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'

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
    numQuestions: int        # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

@app.get("/get-subtopics")
async def get_subtopics(request: Request, topic: str = Query(..., description="Generate subtopics for a given topic")):
    try:
        # Generate using Gemini API
        response = gemini_model.generate_content(
            f"Provide a combined list of all the core concepts and advanced features in {topic} without explanation in brief in a list without segregation."
            "Format the output as valid JSON and ensure there are no unterminated strings, special characters and unescaped characters."
        )
        subtopics = response.text.strip()
        return {"subtopics": subtopics}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred with Gemini API: {str(e)}"
        )

@app.post("/get-quiz")
async def get_questions(request: Request, quiz_request: QuizGenerationRequest):
    try:
        start_time = time.time()

        subtopics_str = ', '.join(quiz_request.subtopics) if quiz_request.subtopics else "general concepts"
        difficulty_str = ', '.join(quiz_request.difficulty)
        question_types_str = ', '.join(quiz_request.questionTypes)
        
        prompt = (f"Generate {quiz_request.numQuestions} {question_types_str} questions on the topic '{quiz_request.topic}' "
                  f"with a strong focus on '{subtopics_str}'. Each question should be a {question_types_str} with clear options and a correct answer. Ensure the difficulty level is {difficulty_str}. "
                  f"The response should be formatted as valid JSON, with each question containing a unique ID, the question text, options, correct answer, and difficulty level. "
                  f"Do not include questions without answers. The total length of the JSON response should be at least 150 characters. If the generated response is shorter, regenerate until the length requirement is met.")
        
        logging.info(f"Prompt generation took {time.time() - start_time:.2f} seconds")

        try:
            # Try Gemini API first
            response = gemini_model.generate_content(prompt)
            raw_response = response.text.strip()
            logging.info(f"Gemini API response: {raw_response}")
            raw_questions = json.loads(raw_response.replace('\n', '').replace('\\n', ''))
            logging.info(f"Gemini API response parsed successfully.")
            
            # Process the Gemini response and return it
            structured_questions = []
            quiz_id = id(request)
            for idx, question in enumerate(raw_questions):
                options = [{"id": chr(97 + i), "text": option.strip()} for i, option in enumerate(question["options"])]
                answer_text = question["answer"].strip().lower()
                answer_id = next(
                    (option["id"] for option in options if option["text"].lower() == answer_text), 
                    None
                )
                structured_question = {
                    "id": f"question_{quiz_id}_{idx+1}",
                    "text": question["question"],
                    "options": options,
                    "answer": answer_id,  # Ensure the correct answer is mapped to 'answer'
                    "difficulty": quiz_request.difficulty[0] if len(quiz_request.difficulty) == 1 else "medium"
                }
                structured_questions.append(structured_question)

            logging.info(f"Total processing took {time.time() - start_time:.2f} seconds")
            return {"id": quiz_id, "quiz": {"questions": structured_questions}}

        except Exception as gemini_error:
            logging.error(f"Gemini API failed: {gemini_error}. Falling back to OpenAI.")
            
            # Fallback to OpenAI if Gemini API fails
            try:
                openai_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "You are a quiz generator."},
                              {"role": "user", "content": prompt}],
                    max_tokens=2048,
                    temperature=0.7,
                )
                
                # Capture raw response from OpenAI
                openai_content = openai_response["choices"][0]["message"]["content"]
                logging.info(f"OpenAI API response before cleaning: {openai_content}")
                
                # Clean the response (remove Markdown code blocks, triple backticks)
                clean_openai_content = re.sub(r"```(json|python)?\n*", "", openai_content)
                clean_openai_content = re.sub(r"```", "", clean_openai_content)  # Remove any remaining backticks
                logging.info(f"OpenAI API response after cleaning: {clean_openai_content}")
                
                try:
                    raw_questions = json.loads(clean_openai_content.strip())
                    logging.info(f"OpenAI API response parsed successfully.")
                except json.JSONDecodeError as json_error:
                    logging.error(f"Failed to parse cleaned OpenAI response: {json_error}")
                    raise HTTPException(status_code=500, detail=f"Failed to parse OpenAI response: {json_error}")

                # Process the OpenAI response and return it
                structured_questions = []
                quiz_id = id(request)
                for idx, question in enumerate(raw_questions['questions']):
                    if isinstance(question["options"], dict):
                        options = [{"id": key, "text": value} for key, value in question["options"].items()]
                    else:
                        options = [{"id": chr(97 + i), "text": option.strip()} for i, option in enumerate(question["options"])]
                    
                    answer_text = question["correct_answer"].strip().lower()  # Ensure the correct answer is mapped to 'answer'
                    answer_id = next(
                        (option["id"] for option in options if option["text"].lower() == answer_text), 
                        None
                    )
                    structured_question = {
                        "id": f"question_{quiz_id}_{idx+1}",
                        "text": question["question"],
                        "options": options,
                        "answer": answer_id,  # Correctly map 'correct_answer' to 'answer'
                        "difficulty": quiz_request.difficulty[0] if len(quiz_request.difficulty) == 1 else "medium"
                    }
                    structured_questions.append(structured_question)
                
                logging.info(f"Total processing took {time.time() - start_time:.2f} seconds")
                return {"id": quiz_id, "quiz": {"questions": structured_questions}}

            except Exception as openai_error:
                logging.error(f"OpenAI API failed: {openai_error}")
                raise HTTPException(status_code=500, detail=f"OpenAI API failed: {openai_error}")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )

# Custom OpenAPI schema handler
@app.get("/openapi.json", include_in_schema=False)
async def custom_openapi():
    try:
        return get_openapi(
            title="Quiz API",
            version="1.0.0",
            description="API for generating quizzes using Gemini and OpenAI",
            routes=app.routes,
        )
    except Exception as e:
        logger.error(f"Failed to load OpenAPI schema: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load OpenAPI schema")

# Main entry point for the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)  # Adjust the number of workers as needed
