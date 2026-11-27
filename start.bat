@echo off
chcp 65001 >nul
echo ========================================
echo AI Resume Optimizer - Quick Start
echo ========================================
echo.
echo Step 1: Setting up backend...
cd backend
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To run the application:
echo.
echo 1. Configure backend\.env with your model settings:
echo - MODEL_NAME=your-model-path-or-id
echo - MODEL_ADAPTER_PATH=path-to-your-adapter
echo.
echo 2. Start the backend (Terminal 1):
echo cd backend
echo venv\Scripts\activate
echo uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo 3. Start the frontend (Terminal 2):
echo cd frontend
echo npm install
echo npm run dev
echo.
echo 4. Open http://localhost:3001
echo.
pause
