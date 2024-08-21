from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import google.generativeai as genai
import os

app = FastAPI()

# Initialize the Gemini API client with your API key
os.environ["API_KEY"] = 'AIzaSyDLZ25ToQVFKpFjC1RZy0nV0YB3ANKzZwk'
genai.configure(api_key=os.environ["API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest', generation_config={"response_mime_type": "application/json"})

@app.get("/get-subtopics")
async def get_subtopics(topic: str = Query(..., description=f"Generate subtopics for a given topic ")):
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
