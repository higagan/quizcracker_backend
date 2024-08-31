from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import os
import threading  # For thread-safe counter increment
import json  # For parsing the JSON response
import logging,time

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, replace with specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Single API key
API_KEY = 'AIzaSyAe0mFYAaMD5XRTWf78jy9Tf2Vzp_UkOHs'

# Configure the model with the single API key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
    numQuestions: int        # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

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
