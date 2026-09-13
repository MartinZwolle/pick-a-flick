from __future__ import annotations
import httpx
from app.config import Settings
from app.providers.metadata.base import CreditData, GenreData, MovieDetails, MovieSearchResult

class TMDbError(RuntimeError): pass

class TMDbProvider:
    BASE_URL="https://api.themoviedb.org/3"
    def __init__(self,settings:Settings):
        self.settings=settings; self.api_key=settings.tmdb_api_key
        if not self.api_key: raise TMDbError("TMDB_API_KEY is niet ingesteld.")
    def _get(self,path:str,params:dict|None=None)->dict:
        try:
            r=httpx.get(f"{self.BASE_URL}{path}",params={"api_key":self.api_key,**(params or {})},
                timeout=10.0,headers={"Accept":"application/json","User-Agent":"Pick-a-Flick/0.7"})
            r.raise_for_status()
        except httpx.HTTPError as exc: raise TMDbError(f"TMDb kon niet worden bereikt: {exc}") from exc
        return r.json()
    def _results(self,payload:dict)->list[MovieSearchResult]:
        out=[]
        for item in payload.get("results",[]):
            rd=item.get("release_date") or None; ry=_year(rd)
            if ry and ry<self.settings.household.earliest_movie_year: continue
            if item.get("adult") and not self.settings.household.adult_content: continue
            out.append(MovieSearchResult(tmdb_id=item["id"],title=item.get("title") or item.get("original_title") or "Onbekende titel",
                original_title=item.get("original_title"),release_date=rd,release_year=ry,
                original_language=item.get("original_language"),overview=item.get("overview") or None,
                poster_path=item.get("poster_path"),adult=bool(item.get("adult",False))))
        return out[:20]
    def search_movies(self,query:str)->list[MovieSearchResult]:
        return self._results(self._get("/search/movie",{"query":query,"include_adult":str(self.settings.household.adult_content).lower(),
            "language":"nl-NL","region":self.settings.household.country}))
    def discover_movies(self,*,page:int=1,genre_ids:list[int]|None=None,runtime_max:int|None=None,
                        provider_ids:list[int]|None=None,release_year_min:int|None=None,
                        release_year_max:int|None=None,sort_by:str="popularity.desc",
                        vote_count_min:int|None=None,vote_average_min:float|None=None)->list[MovieSearchResult]:
        p={"include_adult":str(self.settings.household.adult_content).lower(),"include_video":"false","language":"nl-NL",
           "region":self.settings.household.country,"watch_region":self.settings.household.country,
           "with_watch_monetization_types":"flatrate|rent",
           "primary_release_date.gte":f"{release_year_min or self.settings.household.earliest_movie_year}-01-01",
           "sort_by":sort_by,"page":page}
        if release_year_max: p["primary_release_date.lte"]=f"{release_year_max}-12-31"
        if genre_ids: p["with_genres"]="|".join(map(str,genre_ids))
        if provider_ids: p["with_watch_providers"]="|".join(map(str,provider_ids))
        if runtime_max: p["with_runtime.lte"]=runtime_max
        if vote_count_min is not None: p["vote_count.gte"]=vote_count_min
        if vote_average_min is not None: p["vote_average.gte"]=vote_average_min
        return self._results(self._get("/discover/movie",p))
    def list_movie_watch_providers(self)->list[dict]:
        payload=self._get("/watch/providers/movie",{"watch_region":self.settings.household.country,"language":"en-US"})
        return payload.get("results",[])

    def get_movie(self,external_id:int)->MovieDetails:
        item=self._get(f"/movie/{external_id}",{"append_to_response":"credits","language":"nl-NL"})
        rd=item.get("release_date") or None
        cast=sorted(item.get("credits",{}).get("cast",[]),key=lambda c:c.get("order",999))[:8]
        dirs=[x for x in item.get("credits",{}).get("crew",[]) if x.get("job")=="Director"][:3]
        credits=[CreditData(tmdb_person_id=x["id"],name=x.get("name") or "Onbekend",role_type="actor",
            character=x.get("character") or None,billing_order=x.get("order")) for x in cast]
        credits += [CreditData(tmdb_person_id=x["id"],name=x.get("name") or "Onbekend",role_type="director") for x in dirs]
        return MovieDetails(tmdb_id=item["id"],title=item.get("title") or item.get("original_title") or "Onbekende titel",
            original_title=item.get("original_title"),release_date=rd,release_year=_year(rd),runtime_minutes=item.get("runtime"),
            original_language=item.get("original_language"),overview=item.get("overview") or None,poster_path=item.get("poster_path"),
            adult=bool(item.get("adult",False)),genres=[GenreData(tmdb_genre_id=g["id"],name=g["name"]) for g in item.get("genres",[])],
            credits=credits)

def _year(v):
    try: return int(v[:4]) if v and len(v)>=4 else None
    except ValueError: return None
