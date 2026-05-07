from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    accruals_file_name = Column(String(255), nullable=True)
    production_file_name = Column(String(255), nullable=True)
    plan_file_name = Column(String(255), nullable=True)

    accruals_rows = Column(Integer, default=0)
    production_rows = Column(Integer, default=0)
    plan_rows = Column(Integer, default=0)

    accruals = relationship("AccrualRecord", back_populates="batch", cascade="all, delete-orphan")
    productions = relationship("ProductionRecord", back_populates="batch", cascade="all, delete-orphan")
    plans = relationship("PlanRecord", back_populates="batch", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="batch")


class AccrualRecord(Base):
    __tablename__ = "accrual_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=False)

    employee_id = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=True)
    department_name = Column(String(255), nullable=False)
    pay_type_name = Column(String(255), nullable=False)
    period = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)

    batch = relationship("UploadBatch", back_populates="accruals")


class ProductionRecord(Base):
    __tablename__ = "production_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=False)

    employee_id = Column(String(100), nullable=False)
    period = Column(String(20), nullable=False)
    units_produced = Column(Float, nullable=False, default=0)
    hours_worked = Column(Float, nullable=False, default=0)

    batch = relationship("UploadBatch", back_populates="productions")


class PlanRecord(Base):
    __tablename__ = "plan_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=False)

    department_name = Column(String(255), nullable=False)
    period = Column(String(20), nullable=False)
    planned_cost = Column(Float, nullable=False)

    batch = relationship("UploadBatch", back_populates="plans")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=True)

    period = Column(String(20), nullable=False)

    total_cost = Column(Float, nullable=False)
    employee_count = Column(Integer, nullable=False)
    avg_cost_per_employee = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False)
    growth_percent = Column(Float, nullable=True)

    planned_cost = Column(Float, nullable=True)
    deviation = Column(Float, nullable=True)

    forecast_period = Column(String(20), nullable=True)
    forecast_value = Column(Float, nullable=False)

    ai_mode = Column(String(100), nullable=True)

    batch = relationship("UploadBatch", back_populates="analysis_runs")
    insights = relationship("AIInsightLog", back_populates="analysis_run", cascade="all, delete-orphan")


class AIInsightLog(Base):
    __tablename__ = "ai_insight_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    mode = Column(String(100), nullable=True)

    summary = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)

    analysis_run = relationship("AnalysisRun", back_populates="insights")