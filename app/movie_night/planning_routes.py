import time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.admin import security
from app.admin.routes import token, transport
from app.admin.security import AdminError
from app.admin.storage import transaction
from app.movie_night import planning

router = APIRouter()
admin_router = APIRouter(prefix="/admin", dependencies=[Depends(transport)])
templates = Jinja2Templates(directory="app/templates")


def same_origin(request):
    origin = request.headers.get("origin")
    if ((origin and origin != str(request.base_url).rstrip("/"))
            or request.headers.get("sec-fetch-site") == "cross-site"):
        raise AdminError("Dit formulier komt niet van deze website.", 403)


@router.get("/filmavonden")
def overview(request: Request):
    config, items = planning.snapshot()
    return templates.TemplateResponse(request=request, name="movie_night/planned.html", context={
        "items": items, "timezone": config["timezone"],
    })


@router.post("/filmavond/{night_id}/planning")
def plan(request: Request, night_id: int, revision: int = Form(...),
         day: str = Form(...), clock: str = Form(...)):
    same_origin(request)
    planning.schedule(night_id, day, clock, revision)
    return RedirectResponse(f"/filmavond/{night_id}", 303)


@router.get("/filmavond/{night_id}/annuleren")
def cancel_page(request: Request, night_id: int):
    _, items = planning.snapshot(night_id)
    if not items or items[0]["history"]:
        raise AdminError("Geen komende filmavond gevonden.", 404)
    return templates.TemplateResponse(request=request, name="movie_night/cancel.html",
                                      context={"item": items[0]})


@router.post("/filmavond/{night_id}/annuleren")
def cancel(request: Request, night_id: int, revision: int = Form(...),
           confirm: str = Form(default="")):
    same_origin(request)
    if confirm != "yes":
        raise AdminError("Bevestig dat je deze filmavond wilt annuleren.")
    planning.schedule(night_id, "", "", revision, cancel=True)
    return RedirectResponse(f"/filmavond/{night_id}", 303)


@admin_router.post("/planning")
async def planning_settings(request: Request):
    form = await request.form(max_files=0, max_fields=15)
    with transaction() as db:
        security._session(db, token(request), time.time(), authenticated=True,
                          csrf=str(form.get("csrf", "")))
        planning.save_config(db, form)
    return RedirectResponse("/admin/settings?saved=1", 303)


@admin_router.post("/telegram-test")
def telegram_test(request: Request, csrf: str = Form(...)):
    with transaction() as db:
        security._session(db, token(request), time.time(), authenticated=True, csrf=csrf)
        config = planning.settings(db)
        if not config["enabled"]:
            raise AdminError("Sla eerst een actieve Telegram-configuratie op.")
        result = planning.send(config, "Pick a Flick: Telegram-testbericht.")
    if result != "sent":
        raise AdminError("Testbericht niet bevestigd. Controleer bot-token, chat-ID en verbinding.")
    return RedirectResponse("/admin/settings?telegram=sent", 303)
