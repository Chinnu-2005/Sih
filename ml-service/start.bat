@echo off
echo Starting ML Classification Microservice (Gemini Powered)...

echo Installing Python dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt

echo Starting FastAPI ML Service...
start "ML Service" venv\Scripts\python.exe app.py

echo Starting Worker...
start "ML Worker" venv\Scripts\python.exe worker.py

echo ML Microservice started!
echo ML Service: http://localhost:8000
echo Worker: Processing jobs from Redis queue
pause