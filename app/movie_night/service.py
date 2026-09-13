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

def create_night(db,profile_ids,moods,runtime_max):
    night=MovieNight(moods=",".join(moods[:2]),runtime_max=runtime_max); db.add(night);db.flush()
    for pid in sorted(set(profile_ids)):db.add(MovieNightViewer(movie_night_id=night.id,profile_id=pid))
    db.commit();db.refresh(night); discover(db,night,profile_ids,moods,runtime_max); return night

def discover(db,night,ids,moods,runtime_max):
    settings=get_settings(); provider=TMDbProvider(settings); gids=[]
    for m in moods[:2]:gids+=MOODS.get(m,[])
    wanted_slugs=set(settings.streaming.subscriptions)|set(settings.streaming.rental)
    provider_ids=[
        p["provider_id"] for p in provider.list_movie_watch_providers()
        if provider_slug(p.get("provider_name","")) in wanted_slugs
    ]
    gs,ac,ds,hard,seen=_taste(db,ids); gv={x.movie_id for x in db.scalars(select(GroupMovieVeto).where(GroupMovieVeto.viewer_key==viewer_key(ids))).all()}
    found=[]; tmdb_seen=set()
    for page in (1,2,3):
        for hit in provider.discover_movies(page=page,genre_ids=list(dict.fromkeys(gids)) or None,runtime_max=runtime_max,provider_ids=provider_ids or None):
            if hit.tmdb_id in tmdb_seen:continue
            tmdb_seen.add(hit.tmdb_id); movie=catalog_service.get_or_fetch_movie(db,hit.tmdb_id)
            if movie.id in hard or movie.id in gv:continue
            if len(seen.get(movie.id,set()))==len(set(ids)):continue
            av=availability_service.get_for_movie(db,movie)
            if not(av.watchable_now or av.fallback_available):continue
            score,reasons=_score(movie,gs,ac,ds,len(set(ids)))
            if not reasons:reasons=["Beschikbaar vanavond en buiten jullie bekende lijst"]
            found.append((score,movie,reasons))
            if len(found)>=20:break
        if len(found)>=20:break
    found.sort(key=lambda x:(-x[0],-(x[1].release_year or 0),x[1].title.lower()))
    for score,movie,reasons in found:db.add(MovieNightCandidate(movie_night_id=night.id,movie_id=movie.id,score=score,reasons_json=json.dumps(reasons)))
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
    return {
        "finalists": finalists,
        "current": current,
        "reviewed": reviewed,
        "total": len(candidates),
        "finished": finished,
    }


def get_watch_event(db,night_id):
    return db.scalar(select(WatchEvent).where(WatchEvent.movie_night_id==night_id))


def mark_not_watched(db,night):
    # No watch event and no taste signal.
    night.status="not_watched"
    db.commit()


def _upsert_profile_feedback(db,profile_id,movie_id,rating,rewatchable,abandoned):
    existing=db.scalar(select(ProfileMovieRating).where(
        ProfileMovieRating.profile_id==profile_id,
        ProfileMovieRating.movie_id==movie_id,
    ))

    if abandoned:
        rating=-1

    if existing is None:
        existing=ProfileMovieRating(
            profile_id=profile_id,
            movie_id=movie_id,
            rating=rating,
            favorite=False,
            rewatchable=rewatchable,
            veto=False,
        )
        db.add(existing)
    else:
        if rating is not None:
            existing.rating=rating
        if rewatchable:
            existing.rewatchable=True

    return existing


def save_post_watch_feedback(db,night,viewer_rows,feedback):
    if night.selected_movie_id is None:
        raise ValueError("Movie night has no selected movie")

    event=get_watch_event(db,night.id)
    if event is None:
        event=WatchEvent(
            movie_night_id=night.id,
            movie_id=night.selected_movie_id,
            status="watched",
        )
        db.add(event)
        db.flush()

    for viewer in viewer_rows:
        data=feedback.get(viewer.profile_id,{})
        raw_rating=data.get("rating")
        abandoned=bool(data.get("abandoned",False))
        rewatchable=bool(data.get("rewatchable",False)) and not abandoned
        rating=-1 if abandoned else raw_rating

        participant=db.scalar(select(WatchParticipant).where(
            WatchParticipant.watch_event_id==event.id,
            WatchParticipant.profile_id==viewer.profile_id,
        ))
        if participant is None:
            participant=WatchParticipant(
                watch_event_id=event.id,
                profile_id=viewer.profile_id,
            )
            db.add(participant)

        participant.rating=rating
        participant.rewatchable=rewatchable
        participant.abandoned=abandoned

        # Blank feedback records attendance only and doesn't touch taste.
        if rating is not None or rewatchable or abandoned:
            _upsert_profile_feedback(
                db,
                viewer.profile_id,
                night.selected_movie_id,
                rating,
                rewatchable,
                abandoned,
            )

    event.status="watched"
    night.status="watched"
    db.commit()
    db.refresh(event)
    return event
