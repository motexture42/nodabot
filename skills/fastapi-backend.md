# Skill: FastAPI Backend Developer

## Overview
Use this skill when asked to build or modify a Python backend API using FastAPI.

## Tools & Ecosystem
- `fastapi` for the web framework.
- `uvicorn` as the ASGI server.
- `pydantic` for data validation and settings management.

## Workflow
1. Create a `main.py` file to hold the FastAPI app instance.
2. Use Pydantic `BaseModel` classes to define request and response schemas. Do not use raw dictionaries for API inputs.
3. Organize routes using `APIRouter` if the application grows beyond a single file.
4. Use standard HTTP status codes (200 OK, 201 Created, 400 Bad Request, 404 Not Found, 500 Internal Server Error).
5. Always implement error handling using `HTTPException`.

## Execution
- To run the server for testing, use: `uvicorn main:app --reload --port 8000`. 
- Remember that `uvicorn` will block the terminal. If you need to start it and do other things, you must run it in the background or instruct the user to run it.