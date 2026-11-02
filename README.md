# AI Resume Optimizer

A production-style full-stack AI Resume Builder and Optimizer with local LLM inference, safety-first optimization, and professional PDF generation.

## Quick Start

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your MODEL_NAME and MODEL_ADAPTER_PATH
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
# Open http://localhost:3001
```

## Docker

```bash
docker-compose up --build
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/model/status` | GET | Model loading status |
| `/api/resume/upload` | POST | Upload PDF/DOCX/TXT |
| `/api/resume/optimize` | POST | Run full optimization pipeline |
| `/api/pdf/{pdf_id}` | GET | Download generated PDF |

## Pipeline

1. Resume normalization
2. JD analysis (dynamic extraction)
3. Candidate evidence extraction (original resume only)
4. JD/evidence mapping
5. Generate 3 candidate versions (A/B/C)
6. Safety validation on each version
7. Alignment scoring on each version
8. Select best SAFE candidate (safety > score)
9. One-page compression
10. Final safety check + PDF generation
# resume
# resume_builder
# resume
