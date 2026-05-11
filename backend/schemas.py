from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class EmployeeCreate(BaseModel):
    full_name: str
    position: Optional[str] = None
    department_id: int
    is_active: bool = True


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    position: Optional[str]
    department_id: int
    is_active: bool


class CostRecordIn(BaseModel):
    period: str
    department: str
    employee: str
    position: Optional[str] = None

    base_salary: float = 0
    bonus: float = 0
    insurance: float = 0
    other_costs: float = 0
    planned_cost: float = 0
    hours_worked: float = 0
    units_produced: float = 0

    source_system: str = "api"


class ForecastRequest(BaseModel):
    periods_ahead: int = 3
    department_id: Optional[int] = None


class ChatRequest(BaseModel):
    question: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int]
    action: str
    details: Optional[str]
