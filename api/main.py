from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import google.generativeai as genai
import os
import threading  # For thread-safe counter increment

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
async def get_mcq_questions(request: QuizGenerationRequest):
    global quiz_counter

    try:
        # Generating a prompt for the Gemini API to create MCQs
        subtopics_str = ', '.join(request.subtopics) if request.subtopics else "general concepts"
        difficulties_str = ', '.join(request.difficulties)
        question_types_str = ', '.join(request.questionTypes)
        
        prompt = (f"Generate {request.numQuestions} {question_types_str} questions on the topic '{request.topic}' "
                  f"with a focus on '{subtopics_str}' at the difficulty levels: {difficulties_str} along with correct answer for interview preparation .")
        
        response = model.generate_content(prompt)
        questions = response.text.strip()

        # Generate a unique numeric ID for the quiz
        with counter_lock:
            quiz_counter += 1
            quiz_id = quiz_counter

        return {"id": quiz_id, "quiz": questions}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )
