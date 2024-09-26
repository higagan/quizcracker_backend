# server.py

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import os
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI instance
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single API key for Google Generative AI
API_KEY = 'AIzaSyAe0mFYAaMD5XRTWf78jy9Tf2Vzp_UkOHs'  # Replace with your actual API key

# Configure the model with the single API key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
    numQuestions: int        # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

class MCQAnswerRequest(BaseModel):
    question_text: str  # The extracted MCQ question with options

@app.get("/get-subtopics")
async def get_subtopics(request: Request, topic: str = Query(..., description="Generate subtopics for a given topic")):
    try:
        response = model.generate_content(
            f"Provide a combined list of all the core concepts and advanced features in {topic} without explanation in brief in a list without segregation."
            "Format the output as valid JSON and ensure there are no unterminated strings, special characters and unescaped characters."
        )
        subtopics = response.text.strip()
        return {"subtopics": subtopics}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
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

        response = model.generate_content(prompt)

        logging.info(f"API response took {time.time() - start_time:.2f} seconds")

        raw_questions = json.loads(response.text.strip().replace('\n', '').replace('\\n', ''))

        logging.info(f"JSON processing took {time.time() - start_time:.2f} seconds")

        structured_questions = []
        quiz_id = id(request)
        for idx, question in enumerate(raw_questions):
            options = [{"id": chr(97 + i).upper(), "text": option.strip()} for i, option in enumerate(question["options"])]
            answer_text = question["answer"].strip().lower()
            answer_id = next(
                (option["id"] for option in options if option["text"].lower() == answer_text), 
                None
            )
            structured_question = {
                "id": f"question_{quiz_id}_{idx+1}",
                "text": question["question"],
                "options": options,
                "answer": answer_id,
                "difficulty": quiz_request.difficulty[0] if len(quiz_request.difficulty) == 1 else "medium"
            }
            structured_questions.append(structured_question)
        
        logging.info(f"Total processing took {time.time() - start_time:.2f} seconds")

        return {"id": quiz_id, "quiz": {"questions": structured_questions}}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )

@app.post("/api/get-answer")
async def get_answer(request: Request, answer_request: MCQAnswerRequest):
    """
    Endpoint to process an MCQ question and return the correct answer.
    """
    try:
        start_time = time.time()

        question_text = answer_request.question_text.strip()
        if not question_text:
            raise HTTPException(status_code=400, detail="Question text is required.")

        # Define the prompt for the AI model
        prompt = (
            f"You are an intelligent assistant that helps answer multiple-choice questions. "
            f"Below is the question and the options. Provide the correct answer (e.g., 'A', 'B', 'C', or 'D') along with a brief explanation.\n\n"
            f"{question_text}\n\nAnswer:"
        )

        logging.info(f"Prompt for answer generation: {prompt}")

        # Generate the answer using the Generative AI model
        response = model.generate_content(prompt)

        logging.info(f"AI response took {time.time() - start_time:.2f} seconds")

        ai_text = response.text.strip()

        if not ai_text:
            raise HTTPException(status_code=500, detail="AI failed to generate an answer.")

        # Optionally, you can parse the AI response to extract the answer and explanation
        # For simplicity, we'll return the raw AI response
        return {"answer": ai_text}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in /api/get-answer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Main entry point for the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)  # Adjust the number of workers as needed
