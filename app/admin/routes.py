from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.admin import security
from app.admin.security import AdminError
from app.admin.settings import FIELDS, LIST_FIELDS, merge, read_overrides, values_from
from app.admin.storage import transaction
from app.config import get_base_settings

templates = Jinja2Templates(directory="app/templates")


def allow_http():
    return os.getenv("PICKAFLICK_ADMIN_ALLOW_HTTP", "").lower() == "true"


def transport(request: Request):
    if request.url.scheme != "https" and not allow_http():
        raise AdminError(
            "Beheer vereist HTTPS. Alleen voor een vertrouwd thuisnetwerk kun je "
            "PICKAFLICK_ADMIN_ALLOW_HTTP=true instellen.", 403
        )
    if request.method == "POST":
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            raise AdminError("Dit formulier komt niet van deze website.", 403)


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(transport)])


def token(request):
    value = request.cookies.get(security.COOKIE, "")
    return value if len(value) == 43 else ""


def set_cookie(response, value, request, *, authenticated):
    response.set_cookie(
        security.COOKIE, value, httponly=True, secure=request.url.scheme == "https", samesite="strict",
        max_age=security.MAX_SECONDS if authenticated else security.LOGIN_SECONDS,
        path="/admin",
    )


def page(request, name, context=None, status=200):
    return templates.TemplateResponse(
        request=request, name="admin/" + name + ".html",
        context=context or {}, status_code=status,
    )


@router.get("", response_class=HTMLResponse)
def admin_home(request: Request):
    security.current_session(token(request))
    return RedirectResponse("/admin/settings", 303)


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    value, csrf, authenticated = security.login_form(token(request))
    if authenticated:
        return RedirectResponse("/admin/settings", 303)
    response = page(request, "login", {"csrf": csrf, "http_mode": allow_http()})
    set_cookie(response, value, request, authenticated=False)
    return response


@router.post("/login")
def sign_in(request: Request, csrf: str = Form(...), password: str = Form(...)):
    value, _ = security.authenticate(token(request), csrf, password)
    response = RedirectResponse("/admin/settings", 303)
    set_cookie(response, value, authenticated=True)
    return response


@router.post("/logout")
def sign_out(request: Request, csrf: str = Form(...)):
    security.logout(token(request), csrf)
    response = RedirectResponse("/admin/login", 303)
    response.delete_cookie(security.COOKIE, path="/admin")
    return response


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    session = security.current_session(token(request))
    overrides, revision = read_overrides()
    base = get_base_settings()
    effective = merge(base, overrides)
    return page(request, "settings", {
        "csrf": session["csrf"], "fields": FIELDS, "lists": LIST_FIELDS,
        "values": values_from(effective), "base": values_from(base),
        "overrides": overrides, "revision": revision, "http_mode": allow_http(),
        "saved": request.query_params.get("saved") == "1",
    })


def save_settings(session_token, csrf, raw_revision, overrides):
    try:
        revision = int(raw_revision)
    except (TypeError, ValueError):
        raise AdminError("Ongeldig formulier.", 400) from None
    with transaction() as db:
        import time
        security._session(
            db, session_token, time.time(), authenticated=True, csrf=csrf
        )
        current = db.execute("SELECT revision FROM settings_overrides WHERE id=1").fetchone()
        if current["revision"] != revision:
            raise AdminError("Instellingen zijn intussen gewijzigd. Laad de pagina opnieuw.", 409)
        try:
            merge(get_base_settings(), overrides)
        except (ValidationError, KeyError, TypeError, ValueError):
            raise AdminError(
                "Controleer land- en taalcodes, providercodes en filmjaar. "
                "Voorkeurstalen moeten ook toegestaan zijn. Er is niets opgeslagen.", 400
            ) from None
        db.execute(
            "UPDATE settings_overrides SET payload=?, revision=revision+1 WHERE id=1",
            (json.dumps(overrides),),
        )


@router.post("/settings")
async def settings_save(request: Request):
    form = await request.form(max_files=0, max_fields=30)
    selected = form.getlist("override")
    if any(name not in FIELDS for name in selected):
        raise AdminError("Onbekende instelling.", 400)
    overrides = {}
    for name in selected:
        raw = form.get(name, "")
        if not isinstance(raw, str) or len(raw) > 1000:
            raise AdminError("Ongeldige waarde.", 400)
        if name in LIST_FIELDS:
            overrides[name] = [v.strip().lower() for v in raw.split(",") if v.strip()]
        elif name == "adult_content":
            if raw not in {"true", "false"}:
                raise AdminError("Ongeldige waarde.", 400)
            overrides[name] = raw == "true"
        elif name == "earliest_movie_year":
            try:
                overrides[name] = int(raw)
            except ValueError:
                raise AdminError("Vul een geldig filmjaar in.", 400) from None
        else:
            overrides[name] = raw.strip().upper()
    csrf = form.get("csrf", "")
    if not isinstance(csrf, str):
        raise AdminError("Ongeldig formulier.", 403)
    await run_in_threadpool(
        save_settings, token(request), csrf, form.get("revision"), overrides
    )
    return RedirectResponse("/admin/settings?saved=1", 303)


@router.get("/password", response_class=HTMLResponse)
def password_page(request: Request):
    session = security.current_session(token(request))
    return page(request, "password", {"csrf": session["csrf"]})


@router.post("/password")
def password_save(
    request: Request, csrf: str = Form(...), old_password: str = Form(...),
    new_password: str = Form(...), confirmation: str = Form(...),
):
    security.change_password(token(request), csrf, old_password, new_password, confirmation)
    response = RedirectResponse("/admin/login", 303)
    response.delete_cookie(security.COOKIE, path="/admin")
    return response
