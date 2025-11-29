from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
from solver import solve_quiz
import os

app = FastAPI()

EMAIL = os.getenv("STUDENT_EMAIL")
SECRET = os.getenv("STUDENT_SECRET")

@app.post("/")
async def quiz_handler(request: Request):
    try:
        payload = await request.json()
    except:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    if "secret" not in payload or payload.get("secret") != SECRET:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    # valid request
    quiz_url = payload.get("url")
    if not quiz_url:
        return JSONResponse({"error": "missing url"}, status_code=400)

    try:
        result = await solve_quiz(
            email=EMAIL,
            secret=SECRET,
            initial_url=quiz_url
        )
        return JSONResponse(result, status_code=200)
    except Exception as e:
        print("SOLVER ERROR:", type(e), str(e))
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
