from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import os
import threading  # For thread-safe counter increment
import json  # For parsing the JSON response
import random

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, replace with specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

API_KEYS = [
    'AIzaSyD96CwakYFCjkqX5H1x1zE7roCj8I_yx54',
    'AIzaSyDTPMjLjmbbNZLimXuFZgWkvuyBRXVt32s',
    'AIzaSyAj6HeKVo47_Y2wTuLqAI4fOsHKLH8wj5I',
    'AIzaSyCgfYI-1yhg2zU-WmUNvRoY1QLs2Xb5_kE',
    'AIzaSyAhYb1VdfqSjKZSRaM1RiAbPvDgWRjK-ko',
    'AIzaSyDCYcMaRfAxFBrbrGxka8Wb0k2shAaanh4'
    
    # add other keys here
]

# Thread-safe storage of the API key for each request
request_api_key = threading.local()

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
    numQuestions: int        # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

def validate_api_key(api_key):
    try:
        genai.configure(api_key=api_key)
        # A simple test to check if the key is valid
        model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})
        test_response = model.generate_content("Test the API key validity.")
        return True  # Key is valid
    except Exception as e:
        if "API_KEY_INVALID" in str(e):
            return False  # Key is invalid
        else:
            raise e  # Some other error occurred

def get_valid_api_key():
    for api_key in API_KEYS:
        if validate_api_key(api_key):
            return api_key
    raise HTTPException(status_code=500, detail="All API keys are expired or invalid.")

def configure_model(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

@app.middleware("http")
async def assign_api_key(request: Request, call_next):
    valid_api_key = get_valid_api_key()
    request.state.model = configure_model(valid_api_key)
    response = await call_next(request)
    return response

@app.get("/get-subtopics")
async def get_subtopics(request: Request, topic: str = Query(..., description="Generate subtopics for a given topic")):
    try:
        response = request.state.model.generate_content(
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
        subtopics_str = ', '.join(quiz_request.subtopics) if quiz_request.subtopics else "general concepts"
        difficulty_str = ', '.join(quiz_request.difficulty)
        question_types_str = ', '.join(quiz_request.questionTypes)
        
        prompt = (f"Generate {quiz_request.numQuestions} {question_types_str} questions on the topic '{quiz_request.topic}' "
                  f"with a strong focus on '{subtopics_str}'. Each question should be a {question_types_str} with clear options and a correct answer. Ensure the difficulty level is {difficulty_str}. "
                  f"The response should be formatted as valid JSON, with each question containing a unique ID, the question text, options, correct answer, and difficulty level. "
                  f"Do not include questions without answers. The total length of the JSON response should be at least 150 characters. If the generated response is shorter, regenerate until the length requirement is met.")
        
        response = request.state.model.generate_content(prompt)
        print(response.text.strip())
        if len(response.text.strip()) < 150:
            print("re-generating....")
            response = request.state.model.generate_content(prompt)

        try:
            raw_questions = json.loads(response.text.strip().replace('\n', '').replace('\\n', ''))  # Parse the JSON response
        except:
            raw_questions = []

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
                "idx": f"question_{quiz_id}_{idx+1}",  # Generate a unique ID for each question
               
                "text": question["question"],
                "options": options,
                "answer": answer_id,
                "difficulty": quiz_request.difficulty[0] if len(quiz_request.difficulty) == 1 else "medium"
            }
            structured_questions.append(structured_question)
        
        return {"id": quiz_id, "quiz": {"questions": structured_questions}}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )
