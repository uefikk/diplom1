import pandas as pd


def read_excel_file(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    return normalize_columns(df)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def ensure_required_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют обязательные столбцы: {', '.join(missing)}")


def normalize_text_column(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
    )


def normalize_period_value(value):
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    if len(text) == 7 and text[4] == "-":
        return text

    dt = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return text

    return dt.strftime("%Y-%m")


def prepare_accruals(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)

    required = [
        "employee_id",
        "department_name",
        "pay_type_name",
        "period",
        "amount"
    ]
    ensure_required_columns(df, required)

    df = df.copy()
    df["employee_id"] = df["employee_id"].astype("string").str.strip().replace("", pd.NA)
    df["department_name"] = normalize_text_column(df["department_name"])
    df["pay_type_name"] = normalize_text_column(df["pay_type_name"])
    df["period"] = df["period"].apply(normalize_period_value)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    if "full_name" not in df.columns:
        df["full_name"] = pd.NA
    else:
        df["full_name"] = normalize_text_column(df["full_name"])

    df = df.dropna(subset=["employee_id", "department_name", "pay_type_name", "period", "amount"])
    df = df[df["amount"] >= 0]

    return df.reset_index(drop=True)


def prepare_production(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)

    required = [
        "employee_id",
        "period",
        "units_produced"
    ]
    ensure_required_columns(df, required)

    df = df.copy()
    df["employee_id"] = df["employee_id"].astype("string").str.strip().replace("", pd.NA)
    df["period"] = df["period"].apply(normalize_period_value)
    df["units_produced"] = pd.to_numeric(df["units_produced"], errors="coerce").fillna(0)

    if "hours_worked" not in df.columns:
        df["hours_worked"] = 0

    df["hours_worked"] = pd.to_numeric(df["hours_worked"], errors="coerce").fillna(0)

    df = df.dropna(subset=["employee_id", "period"])

    return df.reset_index(drop=True)


def prepare_plan(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)

    required = [
        "department_name",
        "period",
        "planned_cost"
    ]
    ensure_required_columns(df, required)

    df = df.copy()
    df["department_name"] = normalize_text_column(df["department_name"])
    df["period"] = df["period"].apply(normalize_period_value)
    df["planned_cost"] = pd.to_numeric(df["planned_cost"], errors="coerce")

    df = df.dropna(subset=["department_name", "period", "planned_cost"])
    df = df[df["planned_cost"] >= 0]

    return df.reset_index(drop=True)