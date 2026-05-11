from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # admin / analyst / manager
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    forecasts = relationship("ForecastRun", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    employees = relationship("Employee", back_populates="department", cascade="all, delete-orphan")
    costs = relationship("PersonnelCost", back_populates="department", cascade="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("full_name", "department_id", name="uq_employee_department"),
    )

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    position = Column(String(150), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department", back_populates="employees")
    costs = relationship("PersonnelCost", back_populates="employee", cascade="all, delete-orphan")


class PersonnelCost(Base):
    __tablename__ = "personnel_costs"
    __table_args__ = (
        UniqueConstraint("period", "employee_id", name="uq_period_employee"),
    )

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(7), index=True, nullable=False)  # YYYY-MM

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)

    base_salary = Column(Float, default=0)
    bonus = Column(Float, default=0)
    insurance = Column(Float, default=0)
    other_costs = Column(Float, default=0)
    total_cost = Column(Float, default=0)

    planned_cost = Column(Float, default=0)
    hours_worked = Column(Float, default=0)
    units_produced = Column(Float, default=0)

    source_system = Column(String(50), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="costs")
    department = relationship("Department", back_populates="costs")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_name = Column(String(100), nullable=False)
    period_start = Column(String(7), nullable=False)
    period_end = Column(String(7), nullable=False)
    periods_ahead = Column(Integer, default=3)
    mae = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="forecasts")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")
