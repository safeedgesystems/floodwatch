@echo off
REM One-command start for Windows: creates a venv, installs deps, runs the app.
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
cd backend
echo FloodWatch running at http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
