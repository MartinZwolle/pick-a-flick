from datetime import datetime
from sqlalchemy import DateTime,Float,ForeignKey,Integer,String,Text,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.database import Base

class MovieNight(Base):
    __tablename__="movie_nights"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    status:Mapped[str]=mapped_column(String(20),nullable=False,default="choosing")
    moods:Mapped[str|None]=mapped_column(String(120))
    runtime_max:Mapped[int|None]=mapped_column(Integer)
    selected_movie_id:Mapped[int|None]=mapped_column(ForeignKey("movies.id",ondelete="SET NULL"))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class MovieNightViewer(Base):
    __tablename__="movie_night_viewers"; __table_args__=(UniqueConstraint("movie_night_id","profile_id",name="uq_movie_night_viewer"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    movie_night_id:Mapped[int]=mapped_column(ForeignKey("movie_nights.id",ondelete="CASCADE"),nullable=False)
    profile_id:Mapped[int]=mapped_column(ForeignKey("profiles.id",ondelete="CASCADE"),nullable=False)
    profile=relationship("Profile",lazy="joined")

class MovieNightCandidate(Base):
    __tablename__="movie_night_candidates"; __table_args__=(UniqueConstraint("movie_night_id","movie_id",name="uq_movie_night_candidate"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    movie_night_id:Mapped[int]=mapped_column(ForeignKey("movie_nights.id",ondelete="CASCADE"),nullable=False)
    movie_id:Mapped[int]=mapped_column(ForeignKey("movies.id",ondelete="CASCADE"),nullable=False)
    score:Mapped[float]=mapped_column(Float,nullable=False,default=0)
    reasons_json:Mapped[str]=mapped_column(Text,nullable=False,default="[]")
    decision:Mapped[str|None]=mapped_column(String(30))
    movie=relationship("Movie",lazy="joined")

class GroupMovieVeto(Base):
    __tablename__="group_movie_vetoes"; __table_args__=(UniqueConstraint("viewer_key","movie_id",name="uq_group_movie_veto"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    viewer_key:Mapped[str]=mapped_column(String(200),nullable=False,index=True)
    movie_id:Mapped[int]=mapped_column(ForeignKey("movies.id",ondelete="CASCADE"),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
