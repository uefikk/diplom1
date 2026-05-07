import os

import pandas as pd
import plotly.express as px
import streamlit as st

from database import init_db
from etl import read_excel_file, prepare_accruals, prepare_production, prepare_plan
from analytics import (
    overview_metrics,
    monthly_costs,
    growth_rate,
    costs_by_department,
    cost_structure_by_pay_type,
    overall_plan_fact,
    plan_fact_by_department,
)
from forecast import next_period_forecast, next_period_label, moving_average_forecast
from ai_helper import generate_ai_report
from repository import (
    save_upload_batch,
    save_analysis_run,
    get_upload_batches_df,
    get_analysis_history_df,
    get_ai_history_df,
)
from exports import build_excel_report, build_pdf_report


st.set_page_config(page_title="HR Analytics AI 2.0", layout="wide")
init_db()

st.title("Аналитическая система управления затратами на персонал 2.0")
st.caption("Версия с БД, ИИ-модулем, историей запусков и экспортом отчетов")


def fmt_money(value: float) -> str:
    return f"{value:,.2f} руб.".replace(",", " ")


if "saved_batch_id" not in st.session_state:
    st.session_state.saved_batch_id = None

if "saved_run_id" not in st.session_state:
    st.session_state.saved_run_id = None


page = st.sidebar.radio(
    "Раздел",
    ["Аналитика", "История БД"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Загрузка данных")

accruals_file = st.sidebar.file_uploader("Файл начислений (Excel)", type=["xlsx"])
production_file = st.sidebar.file_uploader("Файл производственных показателей (Excel)", type=["xlsx"])
plan_file = st.sidebar.file_uploader("Файл плана (необязательно)", type=["xlsx"])

st.sidebar.markdown(
    """
**Начисления:**
- `employee_id`
- `department_name`
- `pay_type_name`
- `period`
- `amount`

**Производство:**
- `employee_id`
- `period`
- `units_produced`
- `hours_worked` *(необязательно)*

**План:**
- `department_name`
- `period`
- `planned_cost`
"""
)

data_loaded = False
accruals_df = None
production_df = None
plan_df = None

if accruals_file and production_file:
    try:
        accruals_raw = read_excel_file(accruals_file)
        production_raw = read_excel_file(production_file)

        accruals_df = prepare_accruals(accruals_raw)
        production_df = prepare_production(production_raw)

        if plan_file:
            plan_raw = read_excel_file(plan_file)
            plan_df = prepare_plan(plan_raw)

        data_loaded = True

    except Exception as e:
        st.error(f"Ошибка при обработке данных: {e}")
        st.stop()


if page == "Аналитика":
    if not data_loaded:
        st.info("Загрузите файл начислений и файл производственных показателей, чтобы начать анализ.")
        st.stop()

    periods = sorted(accruals_df["period"].dropna().unique().tolist())
    if not periods:
        st.warning("В файле начислений не найдены корректные периоды.")
        st.stop()

    selected_period = st.sidebar.selectbox("Выберите период анализа", periods, index=len(periods) - 1)

    metrics = overview_metrics(accruals_df, production_df, selected_period)
    month_df = monthly_costs(accruals_df)
    growth_df = growth_rate(month_df)
    dep_df = costs_by_department(accruals_df, selected_period)
    pay_df = cost_structure_by_pay_type(accruals_df, selected_period)

    pf_total = None
    pf_dep_df = None
    if plan_df is not None and not plan_df.empty:
        pf_total = overall_plan_fact(accruals_df, plan_df, selected_period)
        pf_dep_df = plan_fact_by_department(accruals_df, plan_df, selected_period)

    forecast_value = next_period_forecast(month_df, window=3)
    forecast_period = next_period_label(month_df)
    forecast_history_df = moving_average_forecast(month_df, window=3)

    ai_result = generate_ai_report(metrics, dep_df, pay_df, pf_dep_df)

    st.subheader("Ключевые показатели")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Общие затраты", fmt_money(metrics["total_cost"]))
    c2.metric("Сотрудников", str(metrics["employee_count"]))
    c3.metric("Средние затраты на сотрудника", fmt_money(metrics["avg_cost_per_employee"]))
    c4.metric("Затраты на единицу продукции", f"{metrics['cost_per_unit']:,.2f} руб.".replace(",", " "))

    c5, c6, c7 = st.columns(3)
    growth_value = metrics.get("growth_percent")
    c5.metric(
        "Темп роста к пред. периоду",
        "н/д" if growth_value is None else f"{growth_value:.2f}%"
    )
    c6.metric(
        "Прогноз на следующий период",
        fmt_money(forecast_value)
    )
    c7.metric(
        "Период прогноза",
        forecast_period if forecast_period else "н/д"
    )

    if pf_total:
        st.info(
            f"План: {fmt_money(pf_total['planned_cost'])} | "
            f"Факт: {fmt_money(pf_total['actual_cost'])} | "
            f"Отклонение: {fmt_money(pf_total['deviation'])}"
        )

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Графики", "ИИ-анализ", "Экспорт", "Сохранение в БД"])

    with tab1:
        left, right = st.columns(2)

        with left:
            st.subheader("Затраты по подразделениям")
            if dep_df.empty:
                st.info("Нет данных для отображения.")
            else:
                fig_dep = px.bar(
                    dep_df,
                    x="department_name",
                    y="amount",
                    title=f"Затраты по подразделениям за {selected_period}",
                    text_auto=".2s"
                )
                fig_dep.update_layout(xaxis_title="Подразделение", yaxis_title="Сумма")
                st.plotly_chart(fig_dep, use_container_width=True)

        with right:
            st.subheader("Структура затрат по видам выплат")
            if pay_df.empty:
                st.info("Нет данных для отображения.")
            else:
                fig_pay = px.pie(
                    pay_df,
                    names="pay_type_name",
                    values="amount",
                    title=f"Структура затрат за {selected_period}"
                )
                st.plotly_chart(fig_pay, use_container_width=True)

        st.subheader("Динамика затрат")
        fig_line = px.line(
            month_df,
            x="period",
            y="amount",
            markers=True,
            title="Динамика затрат на персонал"
        )
        st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("Таблица динамики и темпов роста")
        st.dataframe(growth_df, use_container_width=True)

        st.subheader("История расчета прогноза")
        st.dataframe(forecast_history_df, use_container_width=True)

        if pf_dep_df is not None:
            st.subheader("План-факт анализ по подразделениям")

            pf_chart_df = pf_dep_df.melt(
                id_vars="department_name",
                value_vars=["actual_cost", "planned_cost"],
                var_name="indicator",
                value_name="value"
            )

            fig_pf = px.bar(
                pf_chart_df,
                x="department_name",
                y="value",
                color="indicator",
                barmode="group",
                title=f"План-факт анализ за {selected_period}"
            )
            st.plotly_chart(fig_pf, use_container_width=True)
            st.dataframe(pf_dep_df, use_container_width=True)

    with tab2:
        st.success(f"Режим генерации: {ai_result['mode']}")
        st.markdown("**Краткий аналитический вывод**")
        st.write(ai_result["summary"])

        st.markdown("**Рекомендации**")
        st.write(ai_result["recommendation"])

    with tab3:
        st.subheader("Экспорт отчета")

        excel_bytes = build_excel_report(
            metrics=metrics,
            dep_df=dep_df,
            pay_df=pay_df,
            growth_df=growth_df,
            forecast_history_df=forecast_history_df,
            ai_result=ai_result,
            pf_dep_df=pf_dep_df,
            pf_total=pf_total,
        )

        st.download_button(
            label="Скачать отчет Excel",
            data=excel_bytes,
            file_name=f"hr_report_{selected_period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        try:
            pdf_bytes = build_pdf_report(
                metrics=metrics,
                dep_df=dep_df,
                pay_df=pay_df,
                ai_result=ai_result,
                pf_total=pf_total,
                font_path="assets/fonts/DejaVuSans.ttf"
            )

            st.download_button(
                label="Скачать отчет PDF",
                data=pdf_bytes,
                file_name=f"hr_report_{selected_period}.pdf",
                mime="application/pdf"
            )
        except FileNotFoundError as e:
            st.warning(str(e))
            st.caption("Скачайте шрифт DejaVuSans.ttf и поместите его в папку assets/fonts/")

    with tab4:
        st.subheader("Сохранение в базу данных")

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Сохранить текущий набор данных в БД"):
                try:
                    batch_id = save_upload_batch(
                        accruals_df=accruals_df,
                        production_df=production_df,
                        plan_df=plan_df,
                        accruals_file_name=accruals_file.name if accruals_file else None,
                        production_file_name=production_file.name if production_file else None,
                        plan_file_name=plan_file.name if plan_file else None,
                    )
                    st.session_state.saved_batch_id = batch_id
                    st.success(f"Набор данных сохранен. ID batch = {batch_id}")
                except Exception as e:
                    st.error(f"Ошибка сохранения набора данных: {e}")

        with col_b:
            if st.button("Сохранить результаты анализа в БД"):
                try:
                    run_id = save_analysis_run(
                        batch_id=st.session_state.saved_batch_id,
                        metrics=metrics,
                        plan_fact_total=pf_total,
                        forecast_period=forecast_period,
                        forecast_value=forecast_value,
                        ai_result=ai_result,
                    )
                    st.session_state.saved_run_id = run_id
                    st.success(f"Результаты анализа сохранены. ID run = {run_id}")
                except Exception as e:
                    st.error(f"Ошибка сохранения анализа: {e}")

        st.caption(
            f"Текущий сохраненный batch_id: {st.session_state.saved_batch_id}, "
            f"run_id: {st.session_state.saved_run_id}"
        )

        with st.expander("Показать очищенные данные"):
            st.markdown("**Начисления**")
            st.dataframe(accruals_df, use_container_width=True)

            st.markdown("**Производственные показатели**")
            st.dataframe(production_df, use_container_width=True)

            if plan_df is not None:
                st.markdown("**Плановые данные**")
                st.dataframe(plan_df, use_container_width=True)

elif page == "История БД":
    st.subheader("История загрузок")
    uploads_df = get_upload_batches_df(limit=100)
    if uploads_df.empty:
        st.info("История загрузок пока отсутствует.")
    else:
        st.dataframe(uploads_df, use_container_width=True)

    st.subheader("История запусков анализа")
    runs_df = get_analysis_history_df(limit=100)
    if runs_df.empty:
        st.info("История запусков пока отсутствует.")
    else:
        st.dataframe(runs_df, use_container_width=True)

    st.subheader("История ИИ-выводов")
    ai_df = get_ai_history_df(limit=100)
    if ai_df.empty:
        st.info("История ИИ-выводов пока отсутствует.")
    else:
        st.dataframe(ai_df, use_container_width=True)

    st.caption(
        "Если используешь PostgreSQL, просто измени DATABASE_URL в .env, "
        "например: postgresql+psycopg2://user:password@localhost:5432/hr_analytics"
    )
