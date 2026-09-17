"""
Paytm MerchantMind — Backend Application Entry Point.
Initializes FastAPI app, sets up middleware, registers routes, and configures error handling.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import logger
from app.core.database import init_db
from app.api.router import api_router
from app.schemas.common import ErrorResponse
import app.models  # noqa: F401  # Explicit model registration on app startup

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle events: startup and shutdown management."""
    logger.info(f"Starting {settings.app_name} in [{settings.app_env}] environment...")
    logger.info(f"Target Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")
    
    # Safe database schema initialization
    init_success = init_db()
    if init_success:
        logger.info("Database tables verified.")
    else:
        logger.warning("Database unavailable or deferred; continuing with startup.")

    yield

    logger.info(f"Shutting down {settings.app_name}...")


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for Paytm MerchantMind — The AI Business Partner for Every Merchant. "
        "Hackathon Track: Merchant Growth AI. "
        "DISCLOSURE: All data used and presented is synthetic demo data. Not real Paytm data."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Centralized Exception Handlers ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors with clean structured response."""
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            success=False,
            error_code="VALIDATION_ERROR",
            message="Invalid request payload or parameters",
            details=exc.errors()
        ).model_dump()
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions with unified error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail)
        ).model_dump()
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors safely without exposing internal queries or stack traces."""
    logger.error(f"Database error during {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            success=False,
            error_code="DATABASE_ERROR",
            message="A database error occurred. The requested service is temporarily unavailable."
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled application exceptions."""
    logger.critical(f"Unhandled server exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please try again later."
        ).model_dump()
    )


# --- Register API Routers ---
app.include_router(api_router, prefix="/api")


# Root health redirect/convenience route
@app.get("/", tags=["Root"])
async def root_status():
    """Root entry providing basic API information and documentation link."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health"
    }
