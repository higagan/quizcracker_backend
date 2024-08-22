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
os.environ["API_KEY"] = 'AIzaSyCASarQu7LmV6db0vwIoPAOXLdYVOMyVlU'
genai.configure(api_key=os.environ["API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

class QuizGenerationRequest(BaseModel):
    topic: str
    subtopics: Optional[List[str]] = None  # Subtopics are optional
    difficulty: List[str]  # Accepting multiple difficulty levels
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
        difficulty_str = ', '.join(request.difficulty)
        question_types_str = ', '.join(request.questionTypes)
        
        prompt = (f"Generate {request.numQuestions} {question_types_str} questions on the topic '{request.topic}' "
                  f"with a focus on '{subtopics_str}' at the difficulty levels: {difficulty_str} along with correct answer for interview preparation."
                   " Do not give questions that have no options and answer. For True or False questions give options as true and false and answer as correct answer for it. ")
        
        response = model.generate_content(prompt)
        raw_questions = json.loads(response.text.strip())  # Parse the JSON response

        # Structure the output as per the requested format
        structured_questions = []
        
        with counter_lock:
            quiz_counter += 1
            quiz_id = quiz_counter

        for idx, question in enumerate(raw_questions):
            options = [{"id": chr(97 + i), "text": option.strip()} for i, option in enumerate(question["options"])]
            
            # Find the correct option ID
            answer_text = question["answer"].strip().lower()
            answer_id = next(
                (option["id"] for option in options if option["text"].lower() == answer_text), 
                None
            )
            
            structured_question = {
                "id": f"question {quiz_id}",
                "text": question["question"],
                "options": options,
                "answer": answer_id,  # Use the ID of the correct option
                "difficulty": request.difficulty[0] if len(request.difficulty) == 1 else "medium"  # Assuming a default value of 'medium'
            }
            structured_questions.append(structured_question)
        
        return {"id": quiz_id, "quiz": {"questions": structured_questions}}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}"
        )
