from datetime import datetime, date
from typing import List, Tuple
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlalchemy.orm import Session

from models import Department, Employee, PersonnelCost, AuditLog, ChatMessage


def normalize_period(value) -> str:
    if value is None:
        raise ValueError("Период не задан")

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.strftime("%Y-%m")

    text = str(value).strip().replace("/", "-")
    if len(text) >= 7:
        return text[:7]
    raise ValueError(f"Некорректный формат периода: {value}")


def safe_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and np.isnan(value):
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def log_action(db: Session, user_id: int | None, action: str, details: str = ""):
    db.add(AuditLog(user_id=user_id, action=action, details=details))


def get_or_create_department(db: Session, name: str) -> Department:
    name = name.strip()
    department = db.query(Department).filter(Department.name == name).first()
    if department:
        return department

    department = Department(name=name)
    db.add(department)
    db.flush()
    return department


def get_or_create_employee(db: Session, full_name: str, department_id: int, position: str | None = None) -> Employee:
    full_name = full_name.strip()
    employee = db.query(Employee).filter(
        Employee.full_name == full_name,
        Employee.department_id == department_id
    ).first()

    if employee:
        if position and employee.position != position:
            employee.position = position
        return employee

    employee = Employee(
        full_name=full_name,
        department_id=department_id,
        position=position
    )
    db.add(employee)
    db.flush()
    return employee


def upsert_cost_record(db: Session, record) -> PersonnelCost:
    period = normalize_period(record.period)
    department = get_or_create_department(db, record.department)
    employee = get_or_create_employee(db, record.employee, department.id, record.position)

    base_salary = safe_float(record.base_salary)
    bonus = safe_float(record.bonus)
    insurance = safe_float(record.insurance)
    other_costs = safe_float(record.other_costs)
    planned_cost = safe_float(record.planned_cost)
    hours_worked = safe_float(record.hours_worked)
    units_produced = safe_float(record.units_produced)
    total_cost = base_salary + bonus + insurance + other_costs

    existing = db.query(PersonnelCost).filter(
        PersonnelCost.period == period,
        PersonnelCost.employee_id == employee.id
    ).first()

    if existing:
        existing.department_id = department.id
        existing.base_salary = base_salary
        existing.bonus = bonus
        existing.insurance = insurance
        existing.other_costs = other_costs
        existing.total_cost = total_cost
        existing.planned_cost = planned_cost
        existing.hours_worked = hours_worked
        existing.units_produced = units_produced
        existing.source_system = record.source_system
        db.flush()
        return existing

    item = PersonnelCost(
        period=period,
        employee_id=employee.id,
        department_id=department.id,
        base_salary=base_salary,
        bonus=bonus,
        insurance=insurance,
        other_costs=other_costs,
        total_cost=total_cost,
        planned_cost=planned_cost,
        hours_worked=hours_worked,
        units_produced=units_produced,
        source_system=record.source_system
    )
    db.add(item)
    db.flush()
    return item


def filter_costs_query(db: Session, period_from=None, period_to=None, department_id=None, employee_id=None):
    query = db.query(PersonnelCost)

    if period_from:
        query = query.filter(PersonnelCost.period >= normalize_period(period_from))
    if period_to:
        query = query.filter(PersonnelCost.period <= normalize_period(period_to))
    if department_id:
        query = query.filter(PersonnelCost.department_id == department_id)
    if employee_id:
        query = query.filter(PersonnelCost.employee_id == employee_id)

    return query


def build_summary(rows: list[PersonnelCost]) -> dict:
    total_cost = sum(x.total_cost for x in rows)
    planned_cost = sum(x.planned_cost for x in rows)
    deviation = total_cost - planned_cost
    total_units = sum(x.units_produced for x in rows)
    unique_employees = len(set(x.employee_id for x in rows))

    avg_cost_per_employee = total_cost / unique_employees if unique_employees else 0
    cost_per_unit = total_cost / total_units if total_units else 0

    return {
        "total_cost": round(total_cost, 2),
        "planned_cost": round(planned_cost, 2),
        "deviation": round(deviation, 2),
        "avg_cost_per_employee": round(avg_cost_per_employee, 2),
        "cost_per_unit": round(cost_per_unit, 2),
        "records_count": len(rows),
        "employees_count": unique_employees
    }


def build_structure(rows: list[PersonnelCost]) -> list[dict]:
    totals = {
        "Оклад": sum(x.base_salary for x in rows),
        "Премии": sum(x.bonus for x in rows),
        "Страховые начисления": sum(x.insurance for x in rows),
        "Прочие затраты": sum(x.other_costs for x in rows),
    }

    grand_total = sum(totals.values())
    result = []
    for k, v in totals.items():
        share = (v / grand_total * 100) if grand_total else 0
        result.append({
            "type": k,
            "value": round(v, 2),
            "share_percent": round(share, 2)
        })
    return result


def build_by_department(rows: list[PersonnelCost]) -> list[dict]:
    grouped = {}
    for row in rows:
        dept_name = row.department.name if row.department else f"Department {row.department_id}"
        grouped.setdefault(dept_name, 0)
        grouped[dept_name] += row.total_cost

    result = [{"department": k, "total_cost": round(v, 2)} for k, v in grouped.items()]
    result.sort(key=lambda x: x["department"])
    return result


def build_time_series(rows: list[PersonnelCost]) -> list[dict]:
    grouped = {}
    for row in rows:
        grouped.setdefault(row.period, 0)
        grouped[row.period] += row.total_cost

    result = [{"period": p, "total_cost": round(v, 2)} for p, v in grouped.items()]
    result.sort(key=lambda x: x["period"])
    return result


def next_periods(last_period: str, periods_ahead: int) -> list[str]:
    dt = datetime.strptime(f"{last_period}-01", "%Y-%m-%d")
    result = []
    for i in range(1, periods_ahead + 1):
        result.append((dt + relativedelta(months=i)).strftime("%Y-%m"))
    return result


def build_forecast(series: List[Tuple[str, float]], periods_ahead: int) -> dict:
    series = sorted(series, key=lambda x: x[0])

    if not series:
        raise ValueError("Недостаточно данных для прогноза")

    y = np.array([x[1] for x in series], dtype=float)

    if len(y) >= 3:
        x = np.arange(len(y)).reshape(-1, 1)
        model = LinearRegression()
        model.fit(x, y)
        fitted = model.predict(x)
        mae = float(np.mean(np.abs(fitted - y)))

        x_future = np.arange(len(y), len(y) + periods_ahead).reshape(-1, 1)
        future = model.predict(x_future)
        future = [max(0.0, float(v)) for v in future]
        model_name = "LinearRegression"
    else:
        avg = float(np.mean(y))
        future = [avg for _ in range(periods_ahead)]
        mae = 0.0
        model_name = "MovingAverageFallback"

    future_periods = next_periods(series[-1][0], periods_ahead)

    return {
        "model_name": model_name,
        "mae": round(mae, 2),
        "history": [{"period": p, "value": round(v, 2)} for p, v in series],
        "forecast": [{"period": p, "value": round(v, 2)} for p, v in zip(future_periods, future)]
    }


def save_chat_message(db: Session, user_id: int, role: str, content: str):
    db.add(ChatMessage(user_id=user_id, role=role, content=content))


def generate_ai_answer(question: str, summary: dict, structure: list[dict], by_department: list[dict]) -> str:
    q = question.lower()

    total_cost = summary.get("total_cost", 0)
    planned_cost = summary.get("planned_cost", 0)
    deviation = summary.get("deviation", 0)
    avg_cost = summary.get("avg_cost_per_employee", 0)
    cost_per_unit = summary.get("cost_per_unit", 0)

    max_structure = max(structure, key=lambda x: x["value"]) if structure else None
    max_dept = max(by_department, key=lambda x: x["total_cost"]) if by_department else None

    if "отклон" in q or "план" in q:
        if deviation > 0:
            trend = "фактические затраты превышают план"
        elif deviation < 0:
            trend = "фактические затраты ниже плановых"
        else:
            trend = "фактические затраты соответствуют плану"

        return (
            f"По текущей выборке общая сумма затрат составляет {total_cost:.2f}, "
            f"плановое значение — {planned_cost:.2f}, отклонение — {deviation:.2f}. "
            f"Это означает, что {trend}. Для уточнения причин следует проанализировать "
            f"структуру выплат и распределение затрат по подразделениям."
        )

    if "структур" in q or "из чего" in q:
        if max_structure:
            return (
                f"Наибольшую долю в затратах формирует категория «{max_structure['type']}», "
                f"ее сумма составляет {max_structure['value']:.2f}, "
                f"что соответствует {max_structure['share_percent']:.2f}% совокупных затрат. "
                f"Это подтверждает, что основное влияние на общую сумму расходов оказывает именно этот элемент."
            )
        return "Для анализа структуры пока недостаточно данных."

    if "подраздел" in q or "отдел" in q:
        if max_dept:
            return (
                f"Наибольшие затраты зафиксированы по подразделению «{max_dept['department']}» "
                f"в объеме {max_dept['total_cost']:.2f}. "
                f"Рекомендуется сопоставить этот показатель с численностью персонала, "
                f"объемом выпуска продукции и долей премиальных выплат."
            )
        return "Для анализа по подразделениям пока недостаточно данных."

    if "рекоменд" in q or "что делать" in q:
        return (
            f"Рекомендуется: 1) сопоставить отклонение {deviation:.2f} с динамикой выработки; "
            f"2) проверить долю премий и прочих затрат в структуре выплат; "
            f"3) отдельно проанализировать подразделения с наибольшими расходами; "
            f"4) использовать прогноз для оценки фонда оплаты труда на следующий период."
        )

    return (
        f"Система рассчитала следующие показатели: общие затраты — {total_cost:.2f}, "
        f"план — {planned_cost:.2f}, отклонение — {deviation:.2f}, "
        f"средние затраты на одного сотрудника — {avg_cost:.2f}, "
        f"затраты на единицу продукции — {cost_per_unit:.2f}. "
        f"Вы можете уточнить вопрос, например: "
        f"«проанализируй отклонение от плана», «покажи структуру затрат», "
        f"«какое подразделение наиболее затратное?» или «дай рекомендации»."
    )
