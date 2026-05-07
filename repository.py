import pandas as pd
from sqlalchemy import select, desc

from database import SessionLocal
from models import (
    UploadBatch,
    AccrualRecord,
    ProductionRecord,
    PlanRecord,
    AnalysisRun,
    AIInsightLog,
)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    safe_df = df.where(pd.notnull(df), None).copy()
    return safe_df.to_dict(orient="records")


def save_upload_batch(
    accruals_df: pd.DataFrame,
    production_df: pd.DataFrame,
    plan_df: pd.DataFrame | None = None,
    accruals_file_name: str | None = None,
    production_file_name: str | None = None,
    plan_file_name: str | None = None,
) -> int:
    session = SessionLocal()
    try:
        batch = UploadBatch(
            accruals_file_name=accruals_file_name,
            production_file_name=production_file_name,
            plan_file_name=plan_file_name,
            accruals_rows=len(accruals_df),
            production_rows=len(production_df),
            plan_rows=0 if plan_df is None else len(plan_df),
        )
        session.add(batch)
        session.flush()

        accrual_records = []
        for row in _df_to_records(accruals_df):
            accrual_records.append(
                {
                    "batch_id": batch.id,
                    "employee_id": row.get("employee_id"),
                    "full_name": row.get("full_name"),
                    "department_name": row.get("department_name"),
                    "pay_type_name": row.get("pay_type_name"),
                    "period": row.get("period"),
                    "amount": float(row.get("amount", 0) or 0),
                }
            )

        production_records = []
        for row in _df_to_records(production_df):
            production_records.append(
                {
                    "batch_id": batch.id,
                    "employee_id": row.get("employee_id"),
                    "period": row.get("period"),
                    "units_produced": float(row.get("units_produced", 0) or 0),
                    "hours_worked": float(row.get("hours_worked", 0) or 0),
                }
            )

        plan_records = []
        if plan_df is not None and not plan_df.empty:
            for row in _df_to_records(plan_df):
                plan_records.append(
                    {
                        "batch_id": batch.id,
                        "department_name": row.get("department_name"),
                        "period": row.get("period"),
                        "planned_cost": float(row.get("planned_cost", 0) or 0),
                    }
                )

        if accrual_records:
            session.bulk_insert_mappings(AccrualRecord, accrual_records)
        if production_records:
            session.bulk_insert_mappings(ProductionRecord, production_records)
        if plan_records:
            session.bulk_insert_mappings(PlanRecord, plan_records)

        session.commit()
        return batch.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_analysis_run(
    batch_id: int | None,
    metrics: dict,
    plan_fact_total: dict | None,
    forecast_period: str | None,
    forecast_value: float,
    ai_result: dict,
) -> int:
    session = SessionLocal()
    try:
        run = AnalysisRun(
            batch_id=batch_id,
            period=metrics.get("period"),
            total_cost=float(metrics.get("total_cost", 0) or 0),
            employee_count=int(metrics.get("employee_count", 0) or 0),
            avg_cost_per_employee=float(metrics.get("avg_cost_per_employee", 0) or 0),
            cost_per_unit=float(metrics.get("cost_per_unit", 0) or 0),
            growth_percent=metrics.get("growth_percent"),
            planned_cost=None if not plan_fact_total else float(plan_fact_total.get("planned_cost", 0) or 0),
            deviation=None if not plan_fact_total else float(plan_fact_total.get("deviation", 0) or 0),
            forecast_period=forecast_period,
            forecast_value=float(forecast_value or 0),
            ai_mode=ai_result.get("mode"),
        )
        session.add(run)
        session.flush()

        insight = AIInsightLog(
            analysis_run_id=run.id,
            mode=ai_result.get("mode"),
            summary=ai_result.get("summary", ""),
            recommendation=ai_result.get("recommendation", ""),
        )
        session.add(insight)

        session.commit()
        return run.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_upload_batches_df(limit: int = 100) -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(UploadBatch).order_by(desc(UploadBatch.id)).limit(limit)
        ).scalars().all()

        data = [
            {
                "id": row.id,
                "created_at": row.created_at,
                "accruals_file_name": row.accruals_file_name,
                "production_file_name": row.production_file_name,
                "plan_file_name": row.plan_file_name,
                "accruals_rows": row.accruals_rows,
                "production_rows": row.production_rows,
                "plan_rows": row.plan_rows,
            }
            for row in rows
        ]
        return pd.DataFrame(data)
    finally:
        session.close()


def get_analysis_history_df(limit: int = 100) -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(AnalysisRun).order_by(desc(AnalysisRun.id)).limit(limit)
        ).scalars().all()

        data = [
            {
                "id": row.id,
                "created_at": row.created_at,
                "batch_id": row.batch_id,
                "period": row.period,
                "total_cost": row.total_cost,
                "employee_count": row.employee_count,
                "avg_cost_per_employee": row.avg_cost_per_employee,
                "cost_per_unit": row.cost_per_unit,
                "growth_percent": row.growth_percent,
                "planned_cost": row.planned_cost,
                "deviation": row.deviation,
                "forecast_period": row.forecast_period,
                "forecast_value": row.forecast_value,
                "ai_mode": row.ai_mode,
            }
            for row in rows
        ]
        return pd.DataFrame(data)
    finally:
        session.close()


def get_ai_history_df(limit: int = 100) -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(AIInsightLog).order_by(desc(AIInsightLog.id)).limit(limit)
        ).scalars().all()

        data = [
            {
                "id": row.id,
                "created_at": row.created_at,
                "analysis_run_id": row.analysis_run_id,
                "mode": row.mode,
                "summary": row.summary,
                "recommendation": row.recommendation,
            }
            for row in rows
        ]
        return pd.DataFrame(data)
    finally:
        session.close()
