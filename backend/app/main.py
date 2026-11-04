import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel
from app.core.config import settings
from app.core.db import engine as default_engine
from app.core.security import get_password_hash
from app.lab.api import router
from app.lab.worker import worker_loop
from app.lab.seed import seed

log = logging.getLogger("lablink")
FRONTEND = Path(__file__).parent / "frontend"


def create_app(engine=None, demo=None, worker=None):
    db = engine if engine is not None else default_engine
    demo = settings.SEED_DEMO if demo is None else demo
    worker = settings.WORKER_ENABLED if worker is None else worker
    if settings.APP_ENV == "production" and (
        demo
        or "SECRET_KEY" not in settings.model_fields_set
        or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError(
            "Production requires explicit SECRET_KEY (32+ characters) and SEED_DEMO=false"
        )

    @asynccontextmanager
    async def lifespan(app):
        if db.dialect.name == "sqlite":
            SQLModel.metadata.create_all(db)
        if demo:
            seed(db)
        task = asyncio.create_task(worker_loop(db)) if worker else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.engine = db
    app.state.dummy_hash = get_password_hash("not-a-real-login-password")

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(
            {"detail": "记录重复或时段冲突，请刷新后重试"}, status_code=409
        )

    @app.middleware("http")
    async def trace(request: Request, call_next):
        request_id = uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Server-Timing"] = (
            f"app;dur={(time.perf_counter() - start) * 1000:.1f}"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        log.info(
            "%s %s %s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
        )
        return response

    @app.get("/api/health")
    def health():
        from sqlalchemy import text

        with db.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": db.dialect.name,
            "demo": demo,
            "worker": worker,
            "version": "1.0.0",
        }

    app.include_router(router)
    if (FRONTEND / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "接口不存在"}, status_code=404)
        if not (FRONTEND / "index.html").exists():
            return JSONResponse(
                {"detail": "Frontend not built; run npm run build in frontend/"},
                status_code=503,
            )
        return FileResponse(FRONTEND / "index.html")

    return app


app = create_app()
