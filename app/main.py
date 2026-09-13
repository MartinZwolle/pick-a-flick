from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.routes import router as catalog_router
from app.config import get_settings
from app.database import get_db
from app.observability.logging import configure_logging
from app.observability.metrics import metrics_middleware
from app.onboarding.routes import router as onboarding_router
from app.profiles.routes import router as profiles_router
from app.recommendations.routes import router as recommendations_router
from app.movie_night.routes import router as movie_night_router

settings = get_settings()
configure_logging(settings.app.log_level)
app = FastAPI(title=settings.app.name, version="0.7.0")
app.middleware("http")(metrics_middleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(profiles_router)
app.include_router(catalog_router)
app.include_router(onboarding_router)
app.include_router(recommendations_router)
app.include_router(movie_night_router)
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/health", response_class=PlainTextResponse, include_in_schema=False)
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return "ok"


@app.get("/metrics", include_in_schema=False)
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
