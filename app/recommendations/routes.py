from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.availability import service as availability_service
from app.database import get_db
from app.profiles import service as profile_service
from app.recommendations.service import recommendations_for_profile

router=APIRouter(prefix="/recommendations",tags=["recommendations"])
templates=Jinja2Templates(directory="app/templates")

@router.get("/{profile_id}",response_class=HTMLResponse)
def recommendations(profile_id:int,request:Request,db:Session=Depends(get_db)):
    profile=profile_service.get_profile(db,profile_id)
    if profile is None: raise HTTPException(status_code=404,detail="Profiel niet gevonden")
    raw=recommendations_for_profile(db,profile,limit=30)
    results=[]
    for rec in raw:
        availability=availability_service.get_for_movie(db,rec.movie)
        if availability.watchable_now or availability.fallback_available:
            results.append((rec,availability))
        if len(results)>=12: break
    return templates.TemplateResponse(request=request,name="recommendations/index.html",
        context={"profile":profile,"results":results,"catalog_candidates":len(raw)})
