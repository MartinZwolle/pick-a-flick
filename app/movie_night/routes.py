from fastapi import APIRouter,Depends,Form,HTTPException,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.movie_night import service
from app.movie_night.models import MovieNightCandidate
from app.profiles import service as profiles_service
router=APIRouter(prefix="/filmavond",tags=["movie-night"]);templates=Jinja2Templates(directory="app/templates")
@router.get("",response_class=HTMLResponse)
def start(request:Request,db:Session=Depends(get_db)):
    return templates.TemplateResponse(request=request,name="movie_night/start.html",context={"profiles":profiles_service.list_profiles(db)})
@router.post("")
def create(viewers:list[int]=Form(...),moods:list[str]=Form(default=[]),runtime_max:str=Form(default=""),mode:str=Form(default="normal"),db:Session=Depends(get_db)):
    night=service.create_night(db,viewers,moods,int(runtime_max) if runtime_max.isdigit() else None,mode);return RedirectResponse(f"/filmavond/{night.id}",303)
@router.get("/{night_id}",response_class=HTMLResponse)
def show(night_id:int,request:Request,db:Session=Depends(get_db)):
    night,viewers,candidates=service.get_night(db,night_id)
    if not night:raise HTTPException(404,"Filmavond niet gevonden")
    selected=next((c for c in candidates if c.record.movie_id==night.selected_movie_id),None)
    state=service.round_state(candidates)
    return templates.TemplateResponse(request=request,name="movie_night/night.html",
        context={"night":night,"viewers":viewers,"candidates":candidates,"selected":selected,"state":state})
@router.post("/{night_id}/candidates/{candidate_id}")
def decision(night_id:int,candidate_id:int,decision:str=Form(...),db:Session=Depends(get_db)):
    night,viewers,_=service.get_night(db,night_id);candidate=db.get(MovieNightCandidate,candidate_id)
    if not night or not candidate or candidate.movie_night_id!=night_id:raise HTTPException(404)
    service.decide(db,night,candidate,decision,[v.profile_id for v in viewers]);return RedirectResponse(f"/filmavond/{night_id}",303)


@router.get("/{night_id}/feedback",response_class=HTMLResponse)
def feedback_form(night_id:int,request:Request,db:Session=Depends(get_db)):
    night,viewers,candidates=service.get_night(db,night_id)
    if not night or not night.selected_movie_id:
        raise HTTPException(404,"Geen gekozen film voor deze filmavond")
    selected=next((c for c in candidates if c.record.movie_id==night.selected_movie_id),None)
    event=service.get_watch_event(db,night_id)
    return templates.TemplateResponse(
        request=request,
        name="movie_night/feedback.html",
        context={"night":night,"viewers":viewers,"selected":selected,"event":event},
    )


@router.post("/{night_id}/feedback")
async def save_feedback(night_id:int,request:Request,db:Session=Depends(get_db)):
    night,viewers,_=service.get_night(db,night_id)
    if not night or not night.selected_movie_id:
        raise HTTPException(404,"Geen gekozen film voor deze filmavond")

    form=await request.form()
    feedback={}
    for viewer in viewers:
        raw=form.get(f"rating_{viewer.profile_id}")
        feedback[viewer.profile_id]={
            "rating": int(raw) if raw in {"-1","0","1","2"} else None,
            "rewatchable": form.get(f"rewatchable_{viewer.profile_id}")=="on",
            "abandoned": form.get(f"abandoned_{viewer.profile_id}")=="on",
        }

    service.save_post_watch_feedback(db,night,viewers,feedback)
    return RedirectResponse(f"/filmavond/{night_id}",status_code=303)


@router.post("/{night_id}/not-watched")
def not_watched(night_id:int,db:Session=Depends(get_db)):
    night,_,_=service.get_night(db,night_id)
    if not night:
        raise HTTPException(404)
    service.mark_not_watched(db,night)
    return RedirectResponse("/filmavond",status_code=303)
