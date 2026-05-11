from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd

from fastapi.middleware.cors import CORSMiddleware
import os


app = FastAPI(title="Personnel Costs Analytics API")

# Настройка CORS
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8501")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from config import (
    APP_TITLE, CORS_ORIGINS,
    DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
)
from database import Base, engine, get_db, SessionLocal
from models import User, Department, Employee, ForecastRun, AuditLog, ChatMessage
from schemas import (
    LoginRequest, TokenResponse, UserCreate, UserOut,
    DepartmentCreate, DepartmentOut, EmployeeCreate, EmployeeOut,
    CostRecordIn, ForecastRequest, ChatRequest, AuditLogOut
)
from security import (
    authenticate_user, create_access_token, get_password_hash,
    get_current_user, require_roles
)
from services import (
    normalize_period, log_action, upsert_cost_record, filter_costs_query,
    build_summary, build_structure, build_by_department, build_time_series,
    build_forecast, save_chat_message, generate_ai_answer
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_default_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if not user:
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


create_default_admin()


@app.get("/")
def root():
    return {"message": APP_TITLE}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token({"sub": user.username, "role": user.role})
    log_action(db, user.id, "login", "Успешный вход в систему")
    db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role
    }


@app.post("/admin/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    if payload.role not in ["admin", "analyst", "manager"]:
        raise HTTPException(status_code=400, detail="Некорректная роль")

    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=True
    )
    db.add(user)
    log_action(db, current_user.id, "create_user", f"Создан пользователь {payload.username}")
    db.commit()
    db.refresh(user)
    return user


@app.get("/admin/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    return db.query(User).order_by(User.id).all()


@app.get("/admin/logs", response_model=list[AuditLogOut])
def get_logs(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()


@app.post("/admin/demo/load")
def load_demo_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin"))
):
    demo_records = [
        # 2025-01
        {"period": "2025-01", "department": "Сборка", "employee": "Иванов И.И.", "position": "Сборщик", "base_salary": 80000, "bonus": 10000, "insurance": 24000, "other_costs": 3000, "planned_cost": 115000, "hours_worked": 168, "units_produced": 42, "source_system": "demo"},
        {"period": "2025-01", "department": "Сборка", "employee": "Смирнов А.А.", "position": "Сборщик", "base_salary": 78000, "bonus": 8000, "insurance": 23400, "other_costs": 2500, "planned_cost": 110000, "hours_worked": 168, "units_produced": 39, "source_system": "demo"},
        {"period": "2025-01", "department": "ОТК", "employee": "Петров П.П.", "position": "Контролер", "base_salary": 70000, "bonus": 5000, "insurance": 21000, "other_costs": 2000, "planned_cost": 98000, "hours_worked": 168, "units_produced": 40, "source_system": "demo"},
        {"period": "2025-01", "department": "Аддитивные установки", "employee": "Кузнецов Д.Д.", "position": "Оператор", "base_salary": 76000, "bonus": 7000, "insurance": 22800, "other_costs": 2500, "planned_cost": 106000, "hours_worked": 168, "units_produced": 18, "source_system": "demo"},
        {"period": "2025-01", "department": "Администрация", "employee": "Соколова Е.В.", "position": "HR-менеджер", "base_salary": 85000, "bonus": 4000, "insurance": 25500, "other_costs": 3500, "planned_cost": 118000, "hours_worked": 168, "units_produced": 0, "source_system": "demo"},

        # 2025-02
        {"period": "2025-02", "department": "Сборка", "employee": "Иванов И.И.", "position": "Сборщик", "base_salary": 80000, "bonus": 12000, "insurance": 24000, "other_costs": 3000, "planned_cost": 116000, "hours_worked": 160, "units_produced": 45, "source_system": "demo"},
        {"period": "2025-02", "department": "Сборка", "employee": "Смирнов А.А.", "position": "Сборщик", "base_salary": 78000, "bonus": 8500, "insurance": 23400, "other_costs": 2500, "planned_cost": 111000, "hours_worked": 160, "units_produced": 41, "source_system": "demo"},
        {"period": "2025-02", "department": "ОТК", "employee": "Петров П.П.", "position": "Контролер", "base_salary": 70000, "bonus": 5500, "insurance": 21000, "other_costs": 2000, "planned_cost": 98500, "hours_worked": 160, "units_produced": 43, "source_system": "demo"},
        {"period": "2025-02", "department": "Аддитивные установки", "employee": "Кузнецов Д.Д.", "position": "Оператор", "base_salary": 76000, "bonus": 7200, "insurance": 22800, "other_costs": 2500, "planned_cost": 106500, "hours_worked": 160, "units_produced": 19, "source_system": "demo"},
        {"period": "2025-02", "department": "Администрация", "employee": "Соколова Е.В.", "position": "HR-менеджер", "base_salary": 85000, "bonus": 4500, "insurance": 25500, "other_costs": 3500, "planned_cost": 118500, "hours_worked": 160, "units_produced": 0, "source_system": "demo"},

        # 2025-03
        {"period": "2025-03", "department": "Сборка", "employee": "Иванов И.И.", "position": "Сборщик", "base_salary": 82000, "bonus": 13000, "insurance": 24600, "other_costs": 3200, "planned_cost": 118000, "hours_worked": 168, "units_produced": 46, "source_system": "demo"},
        {"period": "2025-03", "department": "Сборка", "employee": "Смирнов А.А.", "position": "Сборщик", "base_salary": 80000, "bonus": 9000, "insurance": 24000, "other_costs": 2600, "planned_cost": 113000, "hours_worked": 168, "units_produced": 43, "source_system": "demo"},
        {"period": "2025-03", "department": "ОТК", "employee": "Петров П.П.", "position": "Контролер", "base_salary": 72000, "bonus": 6000, "insurance": 21600, "other_costs": 2100, "planned_cost": 101000, "hours_worked": 168, "units_produced": 44, "source_system": "demo"},
        {"period": "2025-03", "department": "Аддитивные установки", "employee": "Кузнецов Д.Д.", "position": "Оператор", "base_salary": 77000, "bonus": 7400, "insurance": 23100, "other_costs": 2600, "planned_cost": 108000, "hours_worked": 168, "units_produced": 20, "source_system": "demo"},
        {"period": "2025-03", "department": "Администрация", "employee": "Соколова Е.В.", "position": "HR-менеджер", "base_salary": 86000, "bonus": 4500, "insurance": 25800, "other_costs": 3600, "planned_cost": 119000, "hours_worked": 168, "units_produced": 0, "source_system": "demo"},

        # 2025-04
        {"period": "2025-04", "department": "Сборка", "employee": "Иванов И.И.", "position": "Сборщик", "base_salary": 82000, "bonus": 14000, "insurance": 24600, "other_costs": 3200, "planned_cost": 119000, "hours_worked": 176, "units_produced": 48, "source_system": "demo"},
        {"period": "2025-04", "department": "Сборка", "employee": "Смирнов А.А.", "position": "Сборщик", "base_salary": 80000, "bonus": 9500, "insurance": 24000, "other_costs": 2600, "planned_cost": 114000, "hours_worked": 176, "units_produced": 44, "source_system": "demo"},
        {"period": "2025-04", "department": "ОТК", "employee": "Петров П.П.", "position": "Контролер", "base_salary": 72000, "bonus": 6200, "insurance": 21600, "other_costs": 2100, "planned_cost": 101500, "hours_worked": 176, "units_produced": 45, "source_system": "demo"},
        {"period": "2025-04", "department": "Аддитивные установки", "employee": "Кузнецов Д.Д.", "position": "Оператор", "base_salary": 77000, "bonus": 7600, "insurance": 23100, "other_costs": 2600, "planned_cost": 108500, "hours_worked": 176, "units_produced": 21, "source_system": "demo"},
        {"period": "2025-04", "department": "Администрация", "employee": "Соколова Е.В.", "position": "HR-менеджер", "base_salary": 86000, "bonus": 4700, "insurance": 25800, "other_costs": 3600, "planned_cost": 119500, "hours_worked": 176, "units_produced": 0, "source_system": "demo"},
    ]

    for item in demo_records:
        upsert_cost_record(db, CostRecordIn(**item))

    log_action(db, current_user.id, "load_demo_data", f"Загружено записей: {len(demo_records)}")
    db.commit()

    return {"message": f"Демо-данные загружены: {len(demo_records)} записей"}

@app.post("/departments", response_model=DepartmentOut)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "analyst"))
):
    exists = db.query(Department).filter(Department.name == payload.name.strip()).first()
    if exists:
        raise HTTPException(status_code=400, detail="Подразделение уже существует")

    department = Department(name=payload.name.strip())
    db.add(department)
    log_action(db, current_user.id, "create_department", f"Создано подразделение {payload.name}")
    db.commit()
    db.refresh(department)
    return department


@app.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Department).order_by(Department.name).all()


@app.post("/employees", response_model=EmployeeOut)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "analyst"))
):
    department = db.query(Department).filter(Department.id == payload.department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")

    exists = db.query(Employee).filter(
        Employee.full_name == payload.full_name.strip(),
        Employee.department_id == payload.department_id
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Сотрудник уже существует в данном подразделении")

    employee = Employee(
        full_name=payload.full_name.strip(),
        position=payload.position,
        department_id=payload.department_id,
        is_active=payload.is_active
    )
    db.add(employee)
    log_action(
        db,
        current_user.id,
        "create_employee",
        f"Создан сотрудник {payload.full_name} в подразделении ID={payload.department_id}"
    )
    db.commit()
    db.refresh(employee)
    return employee


@app.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    department_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Employee)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    return query.order_by(Employee.full_name).all()


@app.post("/costs")
def create_cost_record(
    payload: CostRecordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "analyst"))
):
    item = upsert_cost_record(db, payload)
    log_action(
        db,
        current_user.id,
        "upsert_cost_record",
        f"Период={payload.period}, подразделение={payload.department}, сотрудник={payload.employee}"
    )
    db.commit()
    return {"message": "Запись сохранена", "id": item.id}


@app.post("/costs/import_excel")
def import_costs_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "analyst"))
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только Excel-файлы")

    try:
        df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel: {str(e)}")

    required_columns = [
        "period", "department", "employee",
        "base_salary", "bonus", "insurance", "other_costs"
    ]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Отсутствуют обязательные колонки: {', '.join(missing)}"
        )

    imported = 0
    for _, row in df.iterrows():
        payload = CostRecordIn(
            period=row.get("period"),
            department=str(row.get("department")).strip(),
            employee=str(row.get("employee")).strip(),
            position=None if pd.isna(row.get("position")) else str(row.get("position")).strip(),
            base_salary=row.get("base_salary", 0),
            bonus=row.get("bonus", 0),
            insurance=row.get("insurance", 0),
            other_costs=row.get("other_costs", 0),
            planned_cost=row.get("planned_cost", 0),
            hours_worked=row.get("hours_worked", 0),
            units_produced=row.get("units_produced", 0),
            source_system="excel"
        )
        upsert_cost_record(db, payload)
        imported += 1

    log_action(db, current_user.id, "import_excel", f"Импортировано строк: {imported}")
    db.commit()
    return {"message": f"Импорт завершен. Обработано строк: {imported}"}


@app.get("/analytics/summary")
def analytics_summary(
    period_from: str | None = None,
    period_to: str | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(
        db,
        period_from=period_from,
        period_to=period_to,
        department_id=department_id,
        employee_id=employee_id
    ).all()
    return build_summary(rows)


@app.get("/analytics/structure")
def analytics_structure(
    period_from: str | None = None,
    period_to: str | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(
        db,
        period_from=period_from,
        period_to=period_to,
        department_id=department_id,
        employee_id=employee_id
    ).all()
    return build_structure(rows)


@app.get("/analytics/by_department")
def analytics_by_department(
    period_from: str | None = None,
    period_to: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(
        db,
        period_from=period_from,
        period_to=period_to
    ).all()
    return build_by_department(rows)


@app.get("/analytics/time_series")
def analytics_time_series(
    period_from: str | None = None,
    period_to: str | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(
        db,
        period_from=period_from,
        period_to=period_to,
        department_id=department_id,
        employee_id=employee_id
    ).all()
    return build_time_series(rows)


@app.get("/analytics/compare")
def analytics_compare(
    period_a: str,
    period_b: str,
    department_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows_a = filter_costs_query(db, period_from=period_a, period_to=period_a, department_id=department_id).all()
    rows_b = filter_costs_query(db, period_from=period_b, period_to=period_b, department_id=department_id).all()

    summary_a = build_summary(rows_a)
    summary_b = build_summary(rows_b)

    return {
        "period_a": normalize_period(period_a),
        "period_b": normalize_period(period_b),
        "summary_a": summary_a,
        "summary_b": summary_b,
        "difference": {
            "total_cost": round(summary_b["total_cost"] - summary_a["total_cost"], 2),
            "planned_cost": round(summary_b["planned_cost"] - summary_a["planned_cost"], 2),
            "deviation": round(summary_b["deviation"] - summary_a["deviation"], 2),
            "avg_cost_per_employee": round(summary_b["avg_cost_per_employee"] - summary_a["avg_cost_per_employee"], 2),
            "cost_per_unit": round(summary_b["cost_per_unit"] - summary_a["cost_per_unit"], 2),
        }
    }


@app.post("/forecast")
def forecast_costs(
    payload: ForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(db, department_id=payload.department_id).all()
    series_data = build_time_series(rows)
    series = [(x["period"], x["total_cost"]) for x in series_data]

    if len(series) < 1:
        raise HTTPException(status_code=400, detail="Недостаточно данных для прогноза")

    result = build_forecast(series, payload.periods_ahead)

    if result["history"]:
        forecast_run = ForecastRun(
            user_id=current_user.id,
            model_name=result["model_name"],
            period_start=result["history"][0]["period"],
            period_end=result["history"][-1]["period"],
            periods_ahead=payload.periods_ahead,
            mae=result["mae"]
        )
        db.add(forecast_run)

    log_action(
        db,
        current_user.id,
        "forecast",
        f"Модель={result['model_name']}, horizon={payload.periods_ahead}, department_id={payload.department_id}"
    )
    db.commit()
    return result


@app.get("/chat/history")
def chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).order_by(ChatMessage.created_at).all()
    return [
        {
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat()
        }
        for row in rows
    ]


@app.post("/chat/ask")
def chat_ask(
    payload: ChatRequest,
    period_from: str | None = None,
    period_to: str | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = filter_costs_query(
        db,
        period_from=period_from,
        period_to=period_to,
        department_id=department_id,
        employee_id=employee_id
    ).all()

    summary = build_summary(rows)
    structure = build_structure(rows)
    by_department = build_by_department(rows)

    answer = generate_ai_answer(payload.question, summary, structure, by_department)

    save_chat_message(db, current_user.id, "user", payload.question)
    save_chat_message(db, current_user.id, "assistant", answer)
    log_action(db, current_user.id, "chat_ask", f"Вопрос: {payload.question[:200]}")
    db.commit()

    return {"answer": answer}

