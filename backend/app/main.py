"""FastAPI app: versioned API, request_id middleware, JSON errors, rate limits, OpenAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, new_request_id, request_id_ctx
from app.core.rate_limit import limiter

configure_logging()
log = get_logger("app")
settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Legal Metrology Packaged Commodities Compliance Scanner (CPU-only)",
    )
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request_id_ctx.set(rid)
        try:
            resp = await call_next(request)
        except Exception:
            log.error("unhandled_error", path=request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal error", "request_id": rid})
        resp.headers["X-Request-ID"] = rid
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422, content={"detail": str(exc.errors()), "request_id": request_id_ctx.get()}
        )

    app.include_router(router, prefix=settings.api_v1_prefix)
    return app


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429, content={"detail": "Rate limit exceeded", "request_id": request_id_ctx.get()}
    )


app = create_app()
