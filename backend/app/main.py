"""CampusFix FastAPI application factory, middleware, exception handlers, and routing."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.database import close_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    yield
    # Gracefully dispose of connection pool on application shutdown
    await close_db_engine()


def create_app() -> FastAPI:
    """Factory creating and configuring the primary FastAPI application instance."""
    app = FastAPI(
        title="CampusFix API",
        version="0.1.0",
        description="University Campus Facility Issue Reporting, Triage, and Operational Resolution Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Transforms standard HTTPExceptions into CampusFix error envelopes."""
        code: str
        message: str
        details: Any = None

        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "HTTP_ERROR")
            message = exc.detail.get("message", "An error occurred.")
            details = exc.detail.get("details", None)
        else:
            message = str(exc.detail)
            status_code_map = {
                status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
                status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
                status.HTTP_403_FORBIDDEN: "FORBIDDEN",
                status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
                status.HTTP_409_CONFLICT: "CONFLICT",
                status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
            }
            code = status_code_map.get(exc.status_code, "ERROR")

        content = {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Transforms Pydantic validation failures into standardized validation error envelopes."""
        errors_summary = []
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            errors_summary.append(
                {
                    "field": loc,
                    "message": err.get("msg", "Invalid value"),
                    "type": err.get("type", "validation_error"),
                }
            )

        content = {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed. Please check the supplied parameters.",
                "details": errors_summary,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=content,
        )

    # Mount API routers
    app.include_router(api_v1_router)

    return app


app = create_app()
