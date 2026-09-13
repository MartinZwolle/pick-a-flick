import json
from collections import defaultdict
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.availability import service as availability_service
from app.catalog import service as catalog_service
from app.catalog.models import Movie,ProfileMovieRating
from app.config import get_settings
from app.movie_night.models import GroupMovieVeto,MovieNight,MovieNightCandidate,MovieNightViewer,WatchEvent,WatchParticipant
from app.providers.metadata.tmdb import TMDbProvider
from app.providers.availability.tmdb import provider_slug
MOODS={"licht":[35,10749],"spannend":[53,9648],"actie":[28,12],"slim":[878,9648],"warm":[18,10751],"donker":[53,80,27]}
@dataclass
class CandidateView:
    record:MovieNightCandidate; availability:object; reasons:list[str]
def viewer_key(ids): return ",".join(map(str,sorted(set(ids))))
def _taste(db,ids):
    gs=defaultdict(float); ac=defaultdict(float); ds=defaultdict(float); seen=defaultdict(set); veto=set()
    rs=list(db.scalars(select(ProfileMovieRating).where(ProfileMovieRating.profile_id.in_(ids))).all())
    for r in rs:
        if r.seen: seen[r.movie_id].add(r.profile_id)
        if r.veto: veto.add(r.movie_id)
        if r.veto or r.rating is None or r.rating<=0: continue
        w=1 if r.rating==1 else 2
        if r.favorite:w+=2
        if r.rewatchable:w+=.5
        for g in r.movie.genres:gs[g.name]+=w
        for c in r.movie.credits:
            if c.role_type=="director":ds[c.name]+=w
            elif c.role_type=="actor" and (c.billing_order is None or c.billing_order<3):ac[c.name]+=w
    return gs,ac,ds,veto,seen
def _score(movie,gs,ac,ds,n):
    score=0; reasons=[]
    gh=sorted([(gs.get(g.name,0),g.name) for g in movie.genres],reverse=True); gh=[x for x in gh if x[0]>0]
    if gh: score+=min(sum(x[0] for x in gh)*.35/max(n,1),5); reasons.append("Past bij jullie smaak voor "+", ".join(x[1] for x in gh[:2]))
    dh=sorted([(ds.get(c.name,0),c.name) for c in movie.credits if c.role_type=="director"],reverse=True); dh=[x for x in dh if x[0]>0]
    if dh: score+=min(dh[0][0]*.8/max(n,1),4); reasons.append("Regisseur "+dh[0][1]+" scoort bij jullie")
    ah=sorted([(ac.get(c.name,0),c.name) for c in movie.credits if c.role_type=="actor"],reverse=True); ah=[x for x in ah if x[0]>0]
    if ah: score+=min(sum(x[0] for x in ah[:2])*.3/max(n,1),3); reasons.append("Met "+", ".join(x[1] for x in ah[:2]))
    return round(score,2),reasons[:3]
MODES={"normal","surprise","gems","era","rewatch"}

def create_night(db,profile_ids,moods,runtime_max,mode="normal"):
    mode=mode if mode in MODES else "normal"
    night=MovieNight(mode=mode,moods=",".join(moods[:2]),runtime_max=runtime_max)
    db.add(night);db.flush()
    for pid in sorted(set(profile_ids)):
        db.add(MovieNightViewer(movie_night_id=night.id,profile_id=pid))
    db.commit();db.refresh(night)
    discover(db,night,profile_ids,moods,runtime_max,mode)
    return night
def _provider_ids(settings,provider):
    wanted=set(settings.streaming.subscriptions)|set(settings.streaming.rental)
    return [p["provider_id"] for p in provider.list_movie_watch_providers()
            if provider_slug(p.get("provider_name","")) in wanted]
def _era_window(db,ids,earliest):
    from app.profiles.models import Profile
    years=[p.birth_year for p in db.scalars(select(Profile).where(Profile.id.in_(ids))).all() if p.birth_year]
    if not years:return earliest,None
    return max(earliest,min(years)+10),max(years)+30
def _candidate_ok(db,movie,ids,hard,group_veto,seen,mode):
    if movie.id in hard or movie.id in group_veto:return False
    if mode=="rewatch":
        ratings=list(db.scalars(select(ProfileMovieRating).where(
            ProfileMovieRating.profile_id.in_(ids),ProfileMovieRating.movie_id==movie.id,
            ProfileMovieRating.rewatchable.is_(True))).all())
        return bool(ratings)
    return len(seen.get(movie.id,set()))<len(set(ids))
def _local_rewatch_candidates(db,ids):
    rows=list(db.scalars(select(ProfileMovieRating).where(
        ProfileMovieRating.profile_id.in_(ids),ProfileMovieRating.rewatchable.is_(True),
        ProfileMovieRating.veto.is_(False))).all())
    movies={};who=defaultdict(list)
    for r in rows:movies[r.movie_id]=r.movie;who[r.movie_id].append(r.profile_id)
    return list(movies.values()),who

def _recent_candidate_penalties(db,night_id,ids,lookback=3):
    """Penalty for movies already surfaced to any of these viewers recently."""
    previous_ids=list(db.scalars(
        select(MovieNightViewer.movie_night_id)
        .where(MovieNightViewer.profile_id.in_(ids),MovieNightViewer.movie_night_id < night_id)
        .distinct().order_by(MovieNightViewer.movie_night_id.desc()).limit(lookback)
    ).all())
    if not previous_ids:return {}
    penalties={}
    rows=list(db.scalars(select(MovieNightCandidate).where(
        MovieNightCandidate.movie_night_id.in_(previous_ids))).all())
    for row in rows:
        # A finalist may genuinely be worth another chance; "Nu niet" should rotate away hardest.
        if row.decision=="skip": penalty=4.0
        elif row.decision in {"maybe","contender","surprise"}: penalty=1.25
        elif row.decision=="choose": penalty=5.0
        else: penalty=2.75
        penalties[row.movie_id]=max(penalties.get(row.movie_id,0),penalty)
    return penalties

def discover(db,night,ids,moods,runtime_max,mode="normal"):
    settings=get_settings(); provider=TMDbProvider(settings)
    gids=[]
    for m in moods[:2]:gids+=MOODS.get(m,[])
    gids=list(dict.fromkeys(gids));pids=_provider_ids(settings,provider)
    gs,ac,ds,hard,seen=_taste(db,ids)
    gv={x.movie_id for x in db.scalars(select(GroupMovieVeto).where(GroupMovieVeto.viewer_key==viewer_key(ids))).all()}
    recent=_recent_candidate_penalties(db,night.id,ids)
    found=[];movie_ids=set()
    if mode=="rewatch":
        movies,who=_local_rewatch_candidates(db,ids)
        from app.profiles.models import Profile
        names={p.id:p.name for p in db.scalars(select(Profile).where(Profile.id.in_(ids))).all()}
        for movie in movies:
            if movie.id in hard or movie.id in gv:continue
            if runtime_max and movie.runtime_minutes and movie.runtime_minutes>runtime_max:continue
            av=availability_service.get_for_movie(db,movie)
            if not(av.watchable_now or av.fallback_available):continue
            score,reasons=_score(movie,gs,ac,ds,len(set(ids)))
            reasons.insert(0,(", ".join(names.get(pid,"Iemand") for pid in who[movie.id]))+" wil deze nog eens zien")
            found.append((score+4,movie,reasons[:3]))
    else:
        attempts=[];common=dict(provider_ids=pids or None)
        if mode=="gems":
            attempts=[
                dict(genre_ids=gids or None,runtime_max=runtime_max,sort_by="vote_average.desc",vote_count_min=250,vote_average_min=6.5,**common),
                dict(genre_ids=gids or None,runtime_max=(runtime_max+20 if runtime_max else None),sort_by="vote_average.desc",vote_count_min=100,vote_average_min=6.2,**common)]
        elif mode=="era":
            ymin,ymax=_era_window(db,ids,settings.household.earliest_movie_year)
            attempts=[
                dict(genre_ids=gids or None,runtime_max=runtime_max,release_year_min=ymin,release_year_max=ymax,sort_by="vote_average.desc",vote_count_min=75,**common),
                dict(genre_ids=gids[:1] or None,runtime_max=(runtime_max+20 if runtime_max else None),release_year_min=ymin,release_year_max=ymax,sort_by="vote_average.desc",vote_count_min=40,**common)]
        elif mode=="surprise":
            attempts=[
                dict(genre_ids=None,runtime_max=runtime_max,sort_by="vote_average.desc",vote_count_min=100,**common),
                dict(genre_ids=None,runtime_max=(runtime_max+20 if runtime_max else None),sort_by="vote_average.desc",vote_count_min=40,**common)]
        else:
            # Important M9.2 change: do not let TMDb popularity choose the pool.
            # Rating + a modest vote floor gives us quality without Netflix-style popularity bias.
            attempts=[
                dict(genre_ids=gids or None,runtime_max=runtime_max,sort_by="vote_average.desc",vote_count_min=75,**common),
                dict(genre_ids=gids or None,runtime_max=(runtime_max+20 if runtime_max else None),sort_by="vote_average.desc",vote_count_min=40,**common),
                dict(genre_ids=gids[:1] or None,runtime_max=(runtime_max+20 if runtime_max else None),sort_by="vote_average.desc",vote_count_min=25,**common)]
        relaxed_at=None
        # Wider pool: up to six pages. Taste + rotation decide what survives, not page-one popularity.
        for attempt_no,kwargs in enumerate(attempts):
            for page in (1,2,3,4,5,6):
                for hit in provider.discover_movies(page=page,**kwargs):
                    movie=catalog_service.get_or_fetch_movie(db,hit.tmdb_id)
                    if movie.id in movie_ids or not _candidate_ok(db,movie,ids,hard,gv,seen,mode):continue
                    av=availability_service.get_for_movie(db,movie)
                    if not(av.watchable_now or av.fallback_available):continue
                    score,reasons=_score(movie,gs,ac,ds,len(set(ids)))
                    rotation_penalty=recent.get(movie.id,0)
                    if rotation_penalty:
                        score-=rotation_penalty
                        reasons.append("Onlangs al voorbijgekomen; daarom nu lager gerangschikt")
                    if mode=="surprise":
                        score=score*.45+1
                        reasons=["Een bewuste stap buiten jullie vaste keuzes"]+(reasons[:2] if reasons else [])
                    elif mode=="gems":
                        score=score*.65+2
                        reasons=["Een minder voor de hand liggende film met sterke publiekswaardering"]+(reasons[:2] if reasons else [])
                    elif mode=="era":
                        reasons=["Uit de filmjaren die bij jullie generatie passen"]+(reasons[:2] if reasons else [])
                    if not reasons:reasons=["Beschikbaar vanavond en buiten jullie bekende lijst"]
                    found.append((score,movie,reasons[:3]));movie_ids.add(movie.id)
                    if attempt_no>0 and relaxed_at is None:relaxed_at=attempt_no
                    # Collect a broad pool before ranking.
                    if len(found)>=60:break
                if len(found)>=60:break
            if len(found)>=30:break
        if relaxed_at:
            night.relaxation_note=("Niet genoeg perfecte matches; de speelduur is iets verruimd." if runtime_max
                                   else "Niet genoeg perfecte matches; de zoekopdracht is iets verruimd.")
    if mode=="surprise":
        found.sort(key=lambda x:((x[1].id*1103515245+night.id*12345)%2147483647,-x[0]))
    elif mode=="gems":
        found.sort(key=lambda x:(-x[0],x[1].title.lower()))
    else:
        found.sort(key=lambda x:(-x[0],-(x[1].release_year or 0),x[1].title.lower()))
    for score,movie,reasons in found[:20]:
        db.add(MovieNightCandidate(movie_night_id=night.id,movie_id=movie.id,score=score,reasons_json=json.dumps(reasons)))
    db.commit()
def get_night(db,nid):
    night=db.get(MovieNight,nid)
    viewers=list(db.scalars(select(MovieNightViewer).where(MovieNightViewer.movie_night_id==nid)).all()) if night else []
    rows=list(db.scalars(select(MovieNightCandidate).where(MovieNightCandidate.movie_night_id==nid).order_by(MovieNightCandidate.score.desc())).all()) if night else []
    return night,viewers,[CandidateView(r,availability_service.get_for_movie(db,r.movie),json.loads(r.reasons_json or "[]")) for r in rows]
def decide(db,night,candidate,decision,ids):
    candidate.decision=decision
    if decision=="never":
        key=viewer_key(ids)
        if not db.scalar(select(GroupMovieVeto).where(GroupMovieVeto.viewer_key==key,GroupMovieVeto.movie_id==candidate.movie_id)):
            db.add(GroupMovieVeto(viewer_key=key,movie_id=candidate.movie_id))
    if decision=="choose":night.selected_movie_id=candidate.movie_id;night.status="selected"
    db.commit()
FINALIST_DECISIONS={"maybe","contender","surprise"}
DISMISSED_DECISIONS={"never","skip"}
def round_state(candidates):
    finalists=[c for c in candidates if c.record.decision in FINALIST_DECISIONS]
    undecided=[c for c in candidates if c.record.decision is None]
    current=undecided[0] if undecided and len(finalists)<4 else None
    reviewed=sum(1 for c in candidates if c.record.decision is not None)
    finished=(len(finalists)>=4) or (not undecided)
    return {"finalists":finalists,"current":current,"reviewed":reviewed,"total":len(candidates),"finished":finished}
def get_watch_event(db,night_id):
    return db.scalar(select(WatchEvent).where(WatchEvent.movie_night_id==night_id))
def mark_not_watched(db,night):
    night.status="not_watched";db.commit()
def _upsert_profile_feedback(db,profile_id,movie_id,rating,rewatchable,abandoned):
    existing=db.scalar(select(ProfileMovieRating).where(ProfileMovieRating.profile_id==profile_id,ProfileMovieRating.movie_id==movie_id))
    if abandoned:rating=-1
    if existing is None:
        existing=ProfileMovieRating(profile_id=profile_id,movie_id=movie_id,rating=rating,favorite=False,rewatchable=rewatchable,veto=False)
        db.add(existing)
    else:
        if rating is not None:existing.rating=rating
        if rewatchable:existing.rewatchable=True
    return existing
def save_post_watch_feedback(db,night,viewer_rows,feedback):
    if night.selected_movie_id is None:raise ValueError("Movie night has no selected movie")
    event=get_watch_event(db,night.id)
    if event is None:
        event=WatchEvent(movie_night_id=night.id,movie_id=night.selected_movie_id,status="watched");db.add(event);db.flush()
    for viewer in viewer_rows:
        data=feedback.get(viewer.profile_id,{})
        raw_rating=data.get("rating");abandoned=bool(data.get("abandoned",False))
        rewatchable=bool(data.get("rewatchable",False)) and not abandoned;rating=-1 if abandoned else raw_rating
        participant=db.scalar(select(WatchParticipant).where(WatchParticipant.watch_event_id==event.id,WatchParticipant.profile_id==viewer.profile_id))
        if participant is None:
            participant=WatchParticipant(watch_event_id=event.id,profile_id=viewer.profile_id);db.add(participant)
        participant.rating=rating;participant.rewatchable=rewatchable;participant.abandoned=abandoned
        if rating is not None or rewatchable or abandoned:
            _upsert_profile_feedback(db,viewer.profile_id,night.selected_movie_id,rating,rewatchable,abandoned)
    event.status="watched";night.status="watched";db.commit();db.refresh(event);return event
