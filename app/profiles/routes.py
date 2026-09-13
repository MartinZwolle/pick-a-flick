from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.service import list_profile_movies, profile_taste_summary
from app.database import get_db
from app.profiles import service

router = APIRouter(prefix="/profiles", tags=["profiles"])
templates = Jinja2Templates(directory="app/templates")


def current_year() -> int:
    return datetime.now().year


@router.get("", response_class=HTMLResponse)
def profiles_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="profiles/index.html",
        context={"profiles": service.list_profiles(db)},
    )


@router.get("/new", response_class=HTMLResponse)
def new_profile_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profiles/form.html",
        context={"profile": None, "error": None, "current_year": current_year()},
    )


@router.post("/new")
def create_profile(
    request: Request,
    name: str = Form(...),
    birth_year: int = Form(...),
    db: Session = Depends(get_db),
):
    if not name.strip() or not (1900 <= birth_year <= current_year()):
        return templates.TemplateResponse(
            request=request,
            name="profiles/form.html",
            context={
                "profile": None,
                "error": "Vul een geldige naam en geboortejaar in.",
                "current_year": current_year(),
            },
            status_code=400,
        )
    try:
        profile = service.create_profile(db, name, birth_year)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="profiles/form.html",
            context={
                "profile": None,
                "error": "Er bestaat al een profiel met deze naam.",
                "current_year": current_year(),
            },
            status_code=409,
        )
    return RedirectResponse(url=f"/onboarding/{profile.id}", status_code=303)


@router.get("/{profile_id}", response_class=HTMLResponse)
def profile_detail(profile_id: int, request: Request, db: Session = Depends(get_db)):
    profile = service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")

    if not profile.onboarding_completed:
        return RedirectResponse(url=f"/onboarding/{profile.id}", status_code=303)

    movie_ratings = list_profile_movies(db, profile.id)
    favorites = [item for item in movie_ratings if item.favorite and not item.veto]
    rewatchables = [item for item in movie_ratings if item.rewatchable and not item.veto]
    vetoes = [item for item in movie_ratings if item.veto]

    return templates.TemplateResponse(
        request=request,
        name="profiles/detail.html",
        context={
            "profile": profile,
            "movie_ratings": movie_ratings,
            "favorites": favorites,
            "rewatchables": rewatchables,
            "vetoes": vetoes,
            "taste": profile_taste_summary(db, profile.id),
        },
    )


@router.get("/{profile_id}/edit", response_class=HTMLResponse)
def edit_profile_page(profile_id: int, request: Request, db: Session = Depends(get_db)):
    profile = service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    return templates.TemplateResponse(
        request=request,
        name="profiles/form.html",
        context={"profile": profile, "error": None, "current_year": current_year()},
    )


@router.post("/{profile_id}/edit")
def edit_profile(
    profile_id: int,
    request: Request,
    name: str = Form(...),
    birth_year: int = Form(...),
    db: Session = Depends(get_db),
):
    profile = service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    try:
        service.update_profile(db, profile, name, birth_year)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="profiles/form.html",
            context={
                "profile": profile,
                "error": "Er bestaat al een profiel met deze naam.",
                "current_year": current_year(),
            },
            status_code=409,
        )
    return RedirectResponse(url=f"/profiles/{profile_id}", status_code=303)


@router.post("/{profile_id}/delete")
def remove_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profiel niet gevonden")
    service.delete_profile(db, profile)
    return RedirectResponse(url="/profiles", status_code=303)
