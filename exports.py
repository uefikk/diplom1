import os
from io import BytesIO

import pandas as pd
from fpdf import FPDF


def _fmt_money(value: float) -> str:
    return f"{value:,.2f} руб.".replace(",", " ")


def build_excel_report(
    metrics: dict,
    dep_df: pd.DataFrame,
    pay_df: pd.DataFrame,
    growth_df: pd.DataFrame,
    forecast_history_df: pd.DataFrame,
    ai_result: dict,
    pf_dep_df: pd.DataFrame | None = None,
    pf_total: dict | None = None,
) -> bytes:
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        metrics_rows = [
            ["Период", metrics.get("period")],
            ["Общие затраты", metrics.get("total_cost")],
            ["Количество сотрудников", metrics.get("employee_count")],
            ["Средние затраты на сотрудника", metrics.get("avg_cost_per_employee")],
            ["Затраты на единицу продукции", metrics.get("cost_per_unit")],
            ["Темп роста, %", metrics.get("growth_percent")],
        ]

        if pf_total:
            metrics_rows.extend([
                ["Плановая сумма", pf_total.get("planned_cost")],
                ["Отклонение факт-план", pf_total.get("deviation")],
            ])

        pd.DataFrame(metrics_rows, columns=["Показатель", "Значение"]).to_excel(
            writer, index=False, sheet_name="Сводка"
        )

        dep_df.to_excel(writer, index=False, sheet_name="Подразделения")
        pay_df.to_excel(writer, index=False, sheet_name="Виды выплат")
        growth_df.to_excel(writer, index=False, sheet_name="Динамика")
        forecast_history_df.to_excel(writer, index=False, sheet_name="Прогноз")

        if pf_dep_df is not None and not pf_dep_df.empty:
            pf_dep_df.to_excel(writer, index=False, sheet_name="План-факт")

        ai_df = pd.DataFrame(
            [
                ["Режим", ai_result.get("mode")],
                ["Вывод", ai_result.get("summary")],
                ["Рекомендации", ai_result.get("recommendation")],
            ],
            columns=["Параметр", "Значение"]
        )
        ai_df.to_excel(writer, index=False, sheet_name="AI")

    buffer.seek(0)
    return buffer.getvalue()


def build_pdf_report(
    metrics: dict,
    dep_df: pd.DataFrame,
    pay_df: pd.DataFrame,
    ai_result: dict,
    pf_total: dict | None = None,
    font_path: str = "assets/fonts/DejaVuSans.ttf",
) -> bytes:
    if not os.path.exists(font_path):
        raise FileNotFoundError(
            "Для PDF с кириллицей нужен файл шрифта assets/fonts/DejaVuSans.ttf"
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.add_font("DejaVu", "", font_path)
    pdf.set_font("DejaVu", size=14)
    pdf.cell(0, 10, "Отчет по затратам на персонал", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("DejaVu", size=10)
    pdf.cell(0, 8, f"Период: {metrics.get('period')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("DejaVu", size=11)
    pdf.cell(0, 8, "Ключевые показатели", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("DejaVu", size=10)
    lines = [
        f"Общие затраты: {_fmt_money(metrics.get('total_cost', 0))}",
        f"Количество сотрудников: {metrics.get('employee_count', 0)}",
        f"Средние затраты на сотрудника: {_fmt_money(metrics.get('avg_cost_per_employee', 0))}",
        f"Затраты на единицу продукции: {metrics.get('cost_per_unit', 0):,.2f} руб.".replace(",", " "),
        f"Темп роста: {metrics.get('growth_percent') if metrics.get('growth_percent') is not None else 'н/д'}",
    ]

    if pf_total:
        lines.append(f"Плановая сумма: {_fmt_money(pf_total.get('planned_cost', 0))}")
        lines.append(f"Отклонение факт-план: {_fmt_money(pf_total.get('deviation', 0))}")

    for line in lines:
        pdf.multi_cell(0, 7, line)

    pdf.ln(2)
    pdf.set_font("DejaVu", size=11)
    pdf.cell(0, 8, "Краткий аналитический вывод", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=10)
    pdf.multi_cell(0, 7, ai_result.get("summary", ""))

    pdf.ln(2)
    pdf.set_font("DejaVu", size=11)
    pdf.cell(0, 8, "Рекомендации", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=10)
    pdf.multi_cell(0, 7, ai_result.get("recommendation", ""))

    pdf.ln(2)
    pdf.set_font("DejaVu", size=11)
    pdf.cell(0, 8, "Топ подразделений", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=10)

    for _, row in dep_df.head(5).iterrows():
        pdf.multi_cell(0, 7, f"{row['department_name']}: {_fmt_money(float(row['amount']))}")

    pdf.ln(2)
    pdf.set_font("DejaVu", size=11)
    pdf.cell(0, 8, "Топ видов выплат", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=10)

    for _, row in pay_df.head(5).iterrows():
        pdf.multi_cell(
            0,
            7,
            f"{row['pay_type_name']}: {_fmt_money(float(row['amount']))} ({float(row['share_percent']):.2f}%)"
        )

    return bytes(pdf.output())
