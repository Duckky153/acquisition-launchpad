from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from acquisition_launchpad.api import router
from acquisition_launchpad.config import get_settings
from acquisition_launchpad.errors import ConflictError, DomainError, NotFoundError


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Synthetic-data Phase 1 control plane for multi-entity finance onboarding. "
            "Independent portfolio project; not affiliated with Entry Inc."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Request-Id"],
    )

    @application.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    @application.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        del request
        if isinstance(error, NotFoundError):
            status_code = 404
            code = "NOT_FOUND"
        elif isinstance(error, ConflictError):
            status_code = 409
            code = "CONFLICT"
        else:
            status_code = 422
            code = "DOMAIN_VALIDATION_FAILED"
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": str(error)}},
        )

    application.include_router(router)
    return application


app = create_app()
