import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _format_money(value: float) -> str:
    return f"{value:,.2f} руб.".replace(",", " ")


def rule_based_summary(metrics: dict, dep_df, pay_df, plan_fact_df=None) -> dict:
    total_cost = metrics.get("total_cost", 0)
    employee_count = metrics.get("employee_count", 0)
    avg_cost = metrics.get("avg_cost_per_employee", 0)
    cost_per_unit = metrics.get("cost_per_unit", 0)
    growth = metrics.get("growth_percent")

    summary_parts = [
        f"За период {metrics.get('period')} общая сумма затрат на персонал составила {_format_money(total_cost)}.",
        f"Количество работников в анализируемом наборе данных: {employee_count}.",
        f"Средние затраты на одного работника составили {_format_money(avg_cost)}.",
        f"Затраты на единицу продукции составили {cost_per_unit:,.2f} руб.".replace(",", " "),
    ]

    recommendation_parts = []

    if growth is not None:
        if growth > 10:
            summary_parts.append(f"По сравнению с предыдущим периодом затраты выросли на {growth:.2f}%.")
            recommendation_parts.append(
                "Рекомендуется проверить причины роста фонда оплаты труда и сопоставить их с изменением производительности."
            )
        elif growth < 0:
            summary_parts.append(f"По сравнению с предыдущим периодом затраты снизились на {abs(growth):.2f}%.")
        else:
            summary_parts.append(f"Темп изменения затрат относительно предыдущего периода составил {growth:.2f}%.")

    if dep_df is not None and not dep_df.empty:
        top_dep = dep_df.iloc[0]
        summary_parts.append(
            f"Наибольшие затраты зафиксированы в подразделении «{top_dep['department_name']}» "
            f"— {_format_money(float(top_dep['amount']))}."
        )

    if pay_df is not None and not pay_df.empty:
        top_pay = pay_df.iloc[0]
        summary_parts.append(
            f"Наибольшую долю в структуре затрат занимает вид выплаты «{top_pay['pay_type_name']}» "
            f"— {float(top_pay['share_percent']):.2f}%."
        )

    if plan_fact_df is not None and not plan_fact_df.empty:
        over_plan = plan_fact_df[plan_fact_df["deviation"] > 0]
        if not over_plan.empty:
            top_over = over_plan.sort_values("deviation", ascending=False).iloc[0]
            summary_parts.append(
                f"Максимальное превышение плана выявлено в подразделении «{top_over['department_name']}» "
                f"на {_format_money(float(top_over['deviation']))}."
            )
            recommendation_parts.append(
                "Следует провести детальный план-факт анализ подразделений с превышением бюджета."
            )

    if cost_per_unit > 0:
        recommendation_parts.append(
            "Целесообразно анализировать показатель затрат на единицу продукции в динамике и по подразделениям."
        )

    if not recommendation_parts:
        recommendation_parts.append(
            "Существенных негативных отклонений не выявлено, рекомендуется продолжить регулярный мониторинг."
        )

    return {
        "summary": " ".join(summary_parts),
        "recommendation": " ".join(recommendation_parts),
        "mode": "rule-based"
    }


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start >= end:
        return None

    payload = text[start:end + 1]

    try:
        return json.loads(payload)
    except Exception:
        return None


def generate_llm_summary(metrics: dict, dep_df, pay_df, plan_fact_df=None) -> dict:
    try:
        from openai import OpenAI
    except Exception:
        return rule_based_summary(metrics, dep_df, pay_df, plan_fact_df)

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key:
        return rule_based_summary(metrics, dep_df, pay_df, plan_fact_df)

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    dep_records = dep_df.head(10).to_dict(orient="records") if dep_df is not None else []
    pay_records = pay_df.head(10).to_dict(orient="records") if pay_df is not None else []
    pf_records = plan_fact_df.head(10).to_dict(orient="records") if plan_fact_df is not None else []

    prompt_data = {
        "metrics": metrics,
        "costs_by_department": dep_records,
        "cost_structure_by_pay_type": pay_records,
        "plan_fact_by_department": pf_records
    }

    system_prompt = (
        "Ты аналитик системы управления затратами на персонал. "
        "Сформируй краткий деловой вывод на русском языке. "
        "Верни ответ строго в JSON-формате: "
        "{\"summary\":\"...\",\"recommendation\":\"...\"}. "
        "Без markdown, без списков, без лишнего текста."
    )

    user_prompt = (
        "Проанализируй данные:\n"
        f"{json.dumps(prompt_data, ensure_ascii=False, indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content if response.choices else ""
        parsed = _extract_json(content)

        if parsed and "summary" in parsed and "recommendation" in parsed:
            return {
                "summary": parsed["summary"],
                "recommendation": parsed["recommendation"],
                "mode": f"llm: {model}"
            }

    except Exception:
        pass

    return rule_based_summary(metrics, dep_df, pay_df, plan_fact_df)


def generate_ai_report(metrics: dict, dep_df, pay_df, plan_fact_df=None) -> dict:
    return generate_llm_summary(metrics, dep_df, pay_df, plan_fact_df)