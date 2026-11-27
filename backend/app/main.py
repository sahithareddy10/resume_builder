import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.api.v1.routes import router as api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
	logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
	from app.services.ai_engine import model_manager
	try:
		model_manager.load()
		logger.info("LLM brain loaded: %s", model_manager.get_status())
	except Exception as e:
		logger.warning(f"Model pre-load failed: {e}")
	yield
	logger.info("Shutting down")


def create_app() -> FastAPI:
	app = FastAPI(
		title=settings.APP_NAME,
		version=settings.APP_VERSION,
		lifespan=lifespan,
		docs_url="/docs",
	)

	# Global exception handler — always return JSON, never HTML error pages
	@app.exception_handler(Exception)
	async def global_exception_handler(request: Request, exc: Exception):
		logger.error(f"Unhandled error: {exc}", exc_info=True)
		return JSONResponse(
			status_code=200,
			content={
				"success": False,
				"resume": {"optimized_text": "", "sections": {}},
				"analysis": {"alignment_score": 0, "matched_keywords": [], "supported_skills": [], "unsupported_requirements": [], "evidence": []},
				"safety": {"passed": False, "issues": [str(exc)]},
				"error": str(exc),
			},
		)

	# CORS - allow the frontend origin(s)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.cors_origins,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	# Routes mounted at /api (spec requirement)
	app.include_router(api_router, prefix="/api")

	@app.get("/")
	async def root():
		return {
			"app": settings.APP_NAME,
			"version": settings.APP_VERSION,
			"health": "/api/health",
			"model_status": "/api/model/status",
			"docs": "/docs",
		}

	return app


app = create_app()
