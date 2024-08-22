from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import os
import threading  # For thread-safe counter increment
import json  # For parsing the JSON response

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, replace with specific domains if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Initialize the Gemini API client with your API key
os.environ["API_KEY"] = 'AIzaSyDLZ25ToQVFKpFjC1RZy0nV0YB3ANKzZwk'
genai.configure(api_key=os.environ["API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulties: List[str]  # Accepting multiple difficulty levels
    numQuestions: int        # Number of questions
    questionTypes: List[str]  # Accepting multiple question types

# In-memory counter for generating numeric IDs
quiz_counter = 0
counter_lock = threading.Lock()  # Ensure thread-safe increments

@app.get("/get-subtopics")
async def get_subtopics(topic: str = Query(..., description="Generate subtopics for a given topic")):
    try:
        # Accessing the Gemini API to get subtopics
        response = model.generate_content(
            f"Provide a combined list of all the core concepts and advanced features in {topic} without explanation in brief in a list without segregation."
        )
        subtopics = response.text.strip()

        return {"subtopics": subtopics}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )

@app.post("/get-quiz")
async def get_questions(request: QuizGenerationRequest):
    global quiz_counter

    try:
        # Generating a prompt for the Gemini API to create MCQs
        subtopics_str = ', '.join(request.subtopics) if request.subtopics else "general concepts"
        difficulties_str = ', '.join(request.difficulties)
        question_types_str = ', '.join(request.questionTypes)
        
        prompt = (f"Generate {request.numQuestions} {question_types_str} questions on the topic '{request.topic}' "
                  f"with a focus on '{subtopics_str}' at the difficulty levels: {difficulties_str} along with correct answer for interview preparation."
                   " Do not give questions that have no options and answer. For True or False questions give options as treu and false and answer as correct answer for it. ")
        
        response = model.generate_content(prompt)
        questions_data = json.loads(response.text.strip())  # Parse the JSON response

        # Generate a unique numeric ID for the quiz
        with counter_lock:
            quiz_counter += 1
            quiz_id = quiz_counter

        # Create a structured dictionary with numbered questions
        structured_questions = []
        for i, question_data in enumerate(questions_data):
            question_id = f"question {i+1}"
            options = question_data.get("options", [])
            structured_options = [{"id": chr(97 + idx), "text": option.strip()} for idx, option in enumerate(options)]

            # Normalize answer and option texts for comparison
            answer_text = question_data["answer"].strip().lower()
            answer_id = next((opt["id"] for opt in structured_options if opt["text"].strip().lower() == answer_text), None)

            structured_question = {
                "id": question_id,
                "text": question_data["question"].strip(),
                "options": structured_options,
                "answer": answer_id,
                "difficulty": question_data["difficulty"]
            }
            structured_questions.append(structured_question)

        return {"id": quiz_id, "quiz": {"questions": structured_questions}}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )
