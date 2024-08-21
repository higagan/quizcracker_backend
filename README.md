****Overview****

This API provides a RESTful interface for generating quizzes based on a given topic or subject. It utilizes a pre-trained AI model to generate questions and answers.


****Dependencies****

1. **FastAPI:** A modern, high-performance web framework for building APIs with Python.

2. **AI Model:** A pre-trained AI model capable of generating text, such as a language model or a question-answering system.

3. **Libraries:** Depending on the requirements, we might need additional libraries.


****Environment Setup****
1. Install FastAPI : pip install fastapi
2. Install Uvicorn (FastAPI doesn’t come with any built-in server application thus, to run FastAPI app, we need an ASGI server called uvicorn.) : pip install uvicorn

**Code Execution**
1. Navigate to your application's local code directory in the command line.
2. To run fast api app using uvicorn, use following command : uvicorn main:app --reload [NOTE: main (**main.py**) is the entry point for our FastAPI application without extension.]
3. You can access the application on http://localhost:/8000
