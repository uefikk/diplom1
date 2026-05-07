import pandas as pd


def _filter_period(df: pd.DataFrame, period: str | None) -> pd.DataFrame:
    if period is None:
        return df.copy()
    return df[df["period"] == period].copy()


def safe_divide(a, b) -> float:
    if a is None or pd.isna(a):
        return 0.0
    if b is None or pd.isna(b) or b == 0:
        return 0.0
    return float(a) / float(b)


def total_personnel_costs(accruals_df: pd.DataFrame, period: str | None = None) -> float:
    df = _filter_period(accruals_df, period)
    return float(df["amount"].sum())


def employee_count(accruals_df: pd.DataFrame, period: str | None = None) -> int:
    df = _filter_period(accruals_df, period)
    return int(df["employee_id"].nunique())


def average_cost_per_employee(accruals_df: pd.DataFrame, period: str | None = None) -> float:
    total_cost = total_personnel_costs(accruals_df, period)
    count = employee_count(accruals_df, period)
    return safe_divide(total_cost, count)


def cost_per_unit(accruals_df: pd.DataFrame, production_df: pd.DataFrame, period: str | None = None) -> float:
    total_cost = total_personnel_costs(accruals_df, period)
    prod_df = _filter_period(production_df, period)
    total_units = float(prod_df["units_produced"].sum())
    return safe_divide(total_cost, total_units)


def monthly_costs(accruals_df: pd.DataFrame) -> pd.DataFrame:
    return (
        accruals_df.groupby("period", as_index=False)["amount"]
        .sum()
        .sort_values("period")
        .reset_index(drop=True)
    )


def growth_rate(monthly_df: pd.DataFrame) -> pd.DataFrame:
    df = monthly_df.sort_values("period").copy()
    df["prev_amount"] = df["amount"].shift(1)

    def calc(row):
        prev_amount = row["prev_amount"]
        amount = row["amount"]
        if pd.isna(prev_amount) or prev_amount == 0:
            return None
        return ((amount / prev_amount) - 1) * 100

    df["growth_rate_percent"] = df.apply(calc, axis=1)
    return df


def growth_for_period(monthly_df: pd.DataFrame, period: str) -> float | None:
    df = growth_rate(monthly_df)
    row = df[df["period"] == period]
    if row.empty:
        return None
    value = row.iloc[0]["growth_rate_percent"]
    if pd.isna(value):
        return None
    return float(value)


def costs_by_department(accruals_df: pd.DataFrame, period: str | None = None) -> pd.DataFrame:
    df = _filter_period(accruals_df, period)
    return (
        df.groupby("department_name", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )


def cost_structure_by_pay_type(accruals_df: pd.DataFrame, period: str | None = None) -> pd.DataFrame:
    df = _filter_period(accruals_df, period)

    result = (
        df.groupby("pay_type_name", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )

    total = result["amount"].sum()
    result["share_percent"] = result["amount"].apply(lambda x: safe_divide(x * 100, total))
    return result


def overall_plan_fact(accruals_df: pd.DataFrame, plan_df: pd.DataFrame, period: str) -> dict:
    actual = total_personnel_costs(accruals_df, period)
    planned = float(plan_df[plan_df["period"] == period]["planned_cost"].sum())
    deviation = actual - planned

    return {
        "actual_cost": actual,
        "planned_cost": planned,
        "deviation": deviation
    }


def plan_fact_by_department(accruals_df: pd.DataFrame, plan_df: pd.DataFrame, period: str) -> pd.DataFrame:
    actual_df = costs_by_department(accruals_df, period).rename(columns={"amount": "actual_cost"})

    plan_period = (
        plan_df[plan_df["period"] == period]
        .groupby("department_name", as_index=False)["planned_cost"]
        .sum()
    )

    merged = pd.merge(actual_df, plan_period, on="department_name", how="outer")
    merged["actual_cost"] = merged["actual_cost"].fillna(0)
    merged["planned_cost"] = merged["planned_cost"].fillna(0)
    merged["deviation"] = merged["actual_cost"] - merged["planned_cost"]

    return merged.sort_values("actual_cost", ascending=False).reset_index(drop=True)


def overview_metrics(accruals_df: pd.DataFrame, production_df: pd.DataFrame, period: str) -> dict:
    month_df = monthly_costs(accruals_df)

    return {
        "period": period,
        "total_cost": total_personnel_costs(accruals_df, period),
        "employee_count": employee_count(accruals_df, period),
        "avg_cost_per_employee": average_cost_per_employee(accruals_df, period),
        "cost_per_unit": cost_per_unit(accruals_df, production_df, period),
        "growth_percent": growth_for_period(month_df, period)
    }