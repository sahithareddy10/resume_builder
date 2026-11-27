"""
API routes - matches the product specification exactly.

Endpoints:
 GET /api/health
 GET /api/model/status
 POST /api/resume/optimize
 GET /api/pdf/{pdf_id}

Request: POST /api/resume/optimize
{
 "resume": "<base64 encoded resume text or parsed structure>",
 "company_name": "...",
 "target_role": "...",
 "job_description": "..."
}

Response:
{
 "success": true,
 "resume": { "optimized_text": "...", "sections": {} },
 "analysis": {
 "alignment_score": 92,
 "matched_keywords": [],
 "supported_skills": [],
 "unsupported_requirements": [],
 "evidence": []
 },
 "safety": { "passed": true, "issues": [] },
 "pdf": { "id": "...", "download_url": "..." }
}
"""

import base64
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.models.schemas import (
	ContactInfo,
	Education,
	FileType,
	FileUploadResponse,
	OptimizationRequest,
	OptimizationResponse,
	OptimizationStatus,
	ParsedResume,
	Project,
	Skill,
	WorkExperience,
)
from app.services.ai_engine import model_manager
from app.services.optimizer import OptimizationEngine
from app.services.pdf_generator import PDFGenerator
from app.services.resume_parser import ResumeParser

logger = logging.getLogger(__name__)

# Use /api prefix as specified
router = APIRouter()

# In-memory stores (replace with DB/Redis in production)
_uploads: dict[str, dict] = {}
_pdf_files: dict[str, str] = {}

engine = OptimizationEngine()
parser = ResumeParser()


# ───────────────────────────── Health ─────────────────────────────────────

@router.get("/health")
async def health_check() -> dict:
	"""Health check - does not require model to be loaded."""
	return {
		"status": "healthy",
		"app": settings.APP_NAME,
		"version": settings.APP_VERSION,
	}


@router.get("/model/status")
async def model_status() -> dict:
	"""Detailed model loading status. Safe to call during startup."""
	return model_manager.get_status()


@router.post("/model/load")
async def load_model() -> dict:
	"""Load or reload the local LLM brain."""
	model_manager.is_loaded = False
	model_manager.load()
	status = model_manager.get_status()
	if not status.get("model_loaded"):
		raise HTTPException(status_code=503, detail=status)
	return status


# ───────────────────────────── Resume Upload ───────────────────────────────

@router.post("/resume/upload", response_model=FileUploadResponse)
async def upload_resume(file: UploadFile = File(...)) -> FileUploadResponse:
	"""Upload a resume file (PDF, DOCX, TXT) and parse it."""
	task_id = f"upload_{uuid.uuid4().hex[:12]}"
	filename = file.filename or "resume"
	ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

	if ext not in settings.allowed_extensions:
		raise HTTPException(
			status_code=400,
			detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(settings.allowed_extensions))}",
		)

	content = await file.read()
	if len(content) > settings.max_upload_size:
		raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

	file_path = Path(settings.UPLOAD_DIR) / f"{task_id}.{ext}"
	file_path.write_bytes(content)

	try:
		text = parser.parse_file(str(file_path), ext)
		parsed = parser.parse(text)
	except Exception as e:
		logger.error(f"Parse failed for {task_id}: {e}")
		raise HTTPException(status_code=422, detail=f"Failed to parse resume: {e}")

	try:
		# Convert contact dict to ContactInfo if needed
		contact_data = parsed.get("contact", {})
		if not isinstance(contact_data, ContactInfo):
			contact_data = ContactInfo(**contact_data)

		# Convert experience items to WorkExperience
		exp_list = []
		for exp in parsed.get("experience", []):
			if isinstance(exp, dict):
				exp_list.append(WorkExperience(
					title=exp.get("title", ""),
					company=exp.get("company", ""),
					start_date=exp.get("start_date", ""),
					end_date=exp.get("end_date"),
					description=exp.get("description", []),
					achievements=exp.get("achievements", []),
				))
		# Convert education items to Education
		edu_list = []
		for edu in parsed.get("education", []):
			if isinstance(edu, dict):
				edu_list.append(Education(
					institution=edu.get("institution", ""),
					degree=edu.get("degree", ""),
					field_of_study=edu.get("field_of_study", ""),
					start_date=edu.get("start_date", ""),
					end_date=edu.get("end_date"),
				))
		# Convert skills to Skill objects
		skill_list = []
		for s in parsed.get("skills", []):
			if isinstance(s, dict):
				skill_list.append(Skill(name=s.get("name", ""), category=s.get("category", "Technical")))
			elif isinstance(s, str):
				skill_list.append(Skill(name=s, category="Technical"))
		# Convert projects to Project objects
		proj_list = []
		for p in parsed.get("projects", []):
			if isinstance(p, dict):
				proj_list.append(Project(
					name=p.get("name", ""),
					description=p.get("description", ""),
					technologies=p.get("technologies", []),
				))
			elif isinstance(p, str):
				proj_list.append(Project(name=p, description="", technologies=[]))

		parsed_resume = ParsedResume(
			contact=contact_data,
			summary=parsed.get("summary", ""),
			experience=exp_list,
			education=edu_list,
			skills=skill_list,
			projects=proj_list,
			certifications=parsed.get("certifications", []),
			raw_text=parsed.get("raw_text", ""),
			word_count=parsed.get("word_count", 0),
			page_count=parsed.get("page_count", 1),
		)
	except Exception as e:
		logger.error(f"Schema validation failed for {task_id}: {e}", exc_info=True)
		raise HTTPException(status_code=422, detail=f"Failed to build resume schema: {e}")

	response = FileUploadResponse(
		task_id=task_id,
		filename=filename,
		file_type=FileType(ext),
		status=OptimizationStatus.COMPLETED,
		parsed_resume=parsed_resume,
		message="Resume parsed successfully",
	)
	_uploads[task_id] = {"response": response, "text": text}
	return response


# ───────────────────────────── Optimize ───────────────────────────────────

@router.post("/resume/optimize", response_model=OptimizationResponse)
async def optimize_resume(request: OptimizationRequest) -> OptimizationResponse:
	"""
	Optimize a resume against a job description.

	Accepts resume as parsed ParsedResume or raw text.
	Falls back to deterministic heuristic optimization if model is unavailable.
	"""
	task_id = f"opt_{uuid.uuid4().hex[:12]}"

	logger.info(f"Starting optimization: {task_id}")

	try:
		result = await engine.optimize(request)
		logger.info(f"Optimization done: {task_id} in {result.processing_time_ms}ms")
		return result
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Optimization error: {e}", exc_info=True)
		# Return a structured JSON error instead of HTTP 500 so the frontend can parse it
		from fastapi.responses import JSONResponse
		return JSONResponse(
			status_code=200,
			content={
				"success": False,
				"resume": {"optimized_text": "", "sections": {}},
				"analysis": {"alignment_score": 0, "matched_keywords": [], "supported_skills": [], "unsupported_requirements": [], "evidence": []},
				"safety": {"passed": False, "issues": [str(e)]},
				"error": str(e),
			},
		)


# ───────────────────────────── PDF Download ────────────────────────────────

@router.get("/pdf/{pdf_id}")
async def download_pdf(pdf_id: str) -> FileResponse:
	"""Download a generated PDF by ID."""
	if pdf_id not in _pdf_files:
		# Try filesystem
		path = Path(settings.OUTPUT_DIR) / f"{pdf_id}.pdf"
		if path.exists():
			_pdf_files[pdf_id] = str(path)
		else:
			raise HTTPException(status_code=404, detail="PDF not found")

	return FileResponse(
		_pdf_files[pdf_id],
		filename=f"optimized_resume_{pdf_id}.pdf",
		media_type="application/pdf",
	)
