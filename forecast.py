import pandas as pd


def moving_average_forecast(monthly_costs_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    df = monthly_costs_df.sort_values("period").copy()
    df["forecast"] = df["amount"].rolling(window=window).mean().shift(1)
    return df


def next_period_label(monthly_costs_df: pd.DataFrame) -> str | None:
    if monthly_costs_df.empty:
        return None

    last_period = str(monthly_costs_df.sort_values("period").iloc[-1]["period"])
    try:
        next_period = pd.Period(last_period, freq="M") + 1
        return str(next_period)
    except Exception:
        return None


def next_period_forecast(monthly_costs_df: pd.DataFrame, window: int = 3) -> float:
    df = monthly_costs_df.sort_values("period").copy()

    if df.empty:
        return 0.0

    if len(df) < window:
        return float(df["amount"].mean())

    return float(df["amount"].tail(window).mean())