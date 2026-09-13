from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.catalog import service as catalog_service
from app.database import get_db
from app.onboarding import service
from app.profiles import service as profile_service
from app.providers.metadata.tmdb import TMDbError

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="app/templates")


def _profile(db: Session, profile_id: int):
    profile = profile_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    return profile


@router.get("/{profile_id}", response_class=HTMLResponse)
def onboarding(profile_id: int, request: Request, db: Session = Depends(get_db)):
    profile = _profile(db, profile_id)
    if profile.onboarding_completed:
        return RedirectResponse(url=f"/profiles/{profile.id}", status_code=303)

    anchor, position = service.next_anchor(db, profile)
    if anchor is None:
        return RedirectResponse(
            url=f"/onboarding/{profile.id}/favorites", status_code=303
        )

    try:
        movie = catalog_service.get_or_fetch_movie(db, anchor.tmdb_id)
    except TMDbError as exc:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/error.html",
            context={"profile": profile, "error": str(exc)},
            status_code=502,
        )

    return templates.TemplateResponse(
        request=request,
        name="onboarding/anchor.html",
        context={
            "profile": profile,
            "movie": movie,
            "position": position,
            "total": service.ANCHOR_COUNT,
            "progress": int(((position - 1) / service.ANCHOR_COUNT) * 100),
        },
    )


@router.post("/{profile_id}/anchor/{tmdb_id}")
def answer_anchor(
    profile_id: int,
    tmdb_id: int,
    response: str = Form(...),
    db: Session = Depends(get_db),
):
    profile = _profile(db, profile_id)
    allowed = {anchor.tmdb_id for anchor in service.anchor_set(profile)}
    if tmdb_id not in allowed:
        raise HTTPException(status_code=400, detail="Film hoort niet bij deze smaaktest")
    try:
        service.save_anchor_response(db, profile, tmdb_id, response)
    except (ValueError, TMDbError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/onboarding/{profile.id}", status_code=303)


@router.get("/{profile_id}/favorites", response_class=HTMLResponse)
def favorites(
    profile_id: int,
    request: Request,
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    profile = _profile(db, profile_id)
    if profile.onboarding_completed:
        return RedirectResponse(url=f"/profiles/{profile.id}", status_code=303)

    anchor, _ = service.next_anchor(db, profile)
    if anchor is not None:
        return RedirectResponse(url=f"/onboarding/{profile.id}", status_code=303)

    results = []
    error = None
    if q.strip():
        try:
            results = catalog_service.search_movies(q)
        except TMDbError as exc:
            error = str(exc)

    current_favorites = service.favorite_ratings(db, profile.id)
    favorite_tmdb_ids = {item.movie.tmdb_id for item in current_favorites}
    return templates.TemplateResponse(
        request=request,
        name="onboarding/favorites.html",
        context={
            "profile": profile,
            "query": q,
            "results": results,
            "error": error,
            "favorites": current_favorites,
            "favorite_tmdb_ids": favorite_tmdb_ids,
            "minimum": service.MIN_FAVORITES,
            "target": service.TARGET_FAVORITES,
        },
    )


@router.post("/{profile_id}/favorites/{tmdb_id}")
def add_favorite(
    profile_id: int,
    tmdb_id: int,
    q: str = Form(default=""),
    db: Session = Depends(get_db),
):
    profile = _profile(db, profile_id)
    try:
        service.add_favorite(db, profile, tmdb_id)
    except TMDbError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    suffix = f"?q={q}" if q else ""
    return RedirectResponse(
        url=f"/onboarding/{profile.id}/favorites{suffix}", status_code=303
    )


@router.post("/{profile_id}/finish")
def finish(profile_id: int, db: Session = Depends(get_db)):
    profile = _profile(db, profile_id)
    if not service.finish(db, profile):
        return RedirectResponse(
            url=f"/onboarding/{profile.id}/favorites", status_code=303
        )
    return RedirectResponse(url=f"/profiles/{profile.id}", status_code=303)
