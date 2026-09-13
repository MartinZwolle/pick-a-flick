from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.availability import service as availability_service
from app.catalog import service
from app.database import get_db
from app.profiles import service as profile_service
from app.providers.metadata.tmdb import TMDbError

router = APIRouter(tags=["catalog"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/movies/search", response_class=HTMLResponse)
def movie_search(request: Request, profile_id: int = Query(...), q: str = Query(default=""), db: Session = Depends(get_db)):
    profile = profile_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    results = []
    error = None
    if q.strip():
        try:
            results = service.search_movies(q)
        except TMDbError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        request=request, name="catalog/search.html",
        context={"profile": profile, "query": q, "results": results, "error": error},
    )


@router.get("/movies/tmdb/{tmdb_id}", response_class=HTMLResponse)
def movie_from_tmdb(tmdb_id: int, request: Request, profile_id: int = Query(...), db: Session = Depends(get_db)):
    profile = profile_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    try:
        movie = service.get_or_fetch_movie(db, tmdb_id)
    except TMDbError as exc:
        return templates.TemplateResponse(
            request=request, name="catalog/error.html",
            context={"profile": profile, "error": str(exc)}, status_code=502,
        )
    rating = service.get_profile_rating(db, profile.id, movie.id)
    availability = availability_service.get_for_movie(db, movie)
    return templates.TemplateResponse(
        request=request, name="catalog/detail.html",
        context={"profile": profile, "movie": movie, "rating": rating, "availability": availability},
    )


@router.post("/movies/{movie_id}/rate")
def rate_movie(
    movie_id: int,
    profile_id: int = Form(...),
    rating: str = Form(default=""),
    favorite: str | None = Form(default=None),
    rewatchable: str | None = Form(default=None),
    veto: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    profile = profile_service.get_profile(db, profile_id)
    movie = service.get_movie(db, movie_id)
    if profile is None or movie is None:
        raise HTTPException(status_code=404, detail="Profiel of film niet gevonden")
    parsed_rating = int(rating) if rating in {"-1", "0", "1", "2"} else None
    service.save_profile_rating(
        db, profile, movie, rating=parsed_rating,
        favorite=favorite == "on", rewatchable=rewatchable == "on", veto=veto == "on",
    )
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.post("/movies/{movie_id}/remove-rating")
def remove_rating(movie_id: int, profile_id: int = Form(...), db: Session = Depends(get_db)):
    profile = profile_service.get_profile(db, profile_id)
    movie = service.get_movie(db, movie_id)
    if profile is None or movie is None:
        raise HTTPException(status_code=404, detail="Profiel of film niet gevonden")
    service.remove_profile_rating(db, profile.id, movie.id)
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)
