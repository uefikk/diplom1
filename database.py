import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///hr_analytics.db")

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)

Base = declarative_base()


def init_db():
    from models import UploadBatch, AccrualRecord, ProductionRecord, PlanRecord, AnalysisRun, AIInsightLog
    Base.metadata.create_all(bind=engine)