import streamlit as st
import requests
import pandas as pd
import os

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Personnel Costs Analytics 3.0", layout="wide")


def get_headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def api_get(path, params=None):
    resp = requests.get(f"{API_URL}{path}", headers=get_headers(), params=params)
    if resp.status_code == 401:
        st.session_state.clear()
        st.error("Сессия истекла. Выполните вход заново.")
        st.stop()
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise Exception(detail)
    return resp.json()


def api_post(path, json=None, files=None, params=None):
    resp = requests.post(
        f"{API_URL}{path}",
        headers=get_headers() if not files else {"Authorization": get_headers().get("Authorization", "")},
        json=json,
        files=files,
        params=params
    )
    if resp.status_code == 401:
        st.session_state.clear()
        st.error("Сессия истекла. Выполните вход заново.")
        st.stop()
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise Exception(detail)
    return resp.json()


def login_page():
    st.title("Вход в систему")
    username = st.text_input("Логин")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти", use_container_width=True):
        try:
            data = api_post("/auth/login", json={"username": username, "password": password})
            st.session_state["token"] = data["access_token"]
            st.session_state["role"] = data["role"]
            st.session_state["username"] = data["username"]
            st.success("Успешный вход")
            st.rerun()
        except Exception as e:
            st.error(str(e))


def get_departments():
    try:
        return api_get("/departments")
    except Exception:
        return []


def get_employees(department_id=None):
    params = {"department_id": department_id} if department_id else None
    try:
        return api_get("/employees", params=params)
    except Exception:
        return []


def sidebar_filters():
    st.sidebar.header("Фильтры")

    period_from = st.sidebar.text_input("Период с (YYYY-MM)", value="2025-01")
    period_to = st.sidebar.text_input("Период по (YYYY-MM)", value="2025-12")

    departments = get_departments()
    dept_options = {0: "Все подразделения"}
    for d in departments:
        dept_options[d["id"]] = d["name"]

    selected_dept_id = st.sidebar.selectbox(
        "Подразделение",
        options=list(dept_options.keys()),
        format_func=lambda x: dept_options[x]
    )

    employees = get_employees(selected_dept_id) if selected_dept_id != 0 else get_employees()
    emp_options = {0: "Все сотрудники"}
    for e in employees:
        emp_options[e["id"]] = e["full_name"]

    selected_emp_id = st.sidebar.selectbox(
        "Сотрудник",
        options=list(emp_options.keys()),
        format_func=lambda x: emp_options[x]
    )

    return {
        "period_from": period_from or None,
        "period_to": period_to or None,
        "department_id": None if selected_dept_id == 0 else selected_dept_id,
        "employee_id": None if selected_emp_id == 0 else selected_emp_id
    }


def dashboard_page(filters):
    st.title("Дашборд")

    summary = api_get("/analytics/summary", params=filters)
    structure = api_get("/analytics/structure", params=filters)
    ts = api_get("/analytics/time_series", params=filters)
    by_department = api_get("/analytics/by_department", params={
        "period_from": filters["period_from"],
        "period_to": filters["period_to"]
    })

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Общие затраты", f"{summary['total_cost']:.2f}")
    c2.metric("План", f"{summary['planned_cost']:.2f}")
    c3.metric("Отклонение", f"{summary['deviation']:.2f}")
    c4.metric("Сотрудники", summary["employees_count"])

    c5, c6 = st.columns(2)
    c5.metric("Средние затраты на сотрудника", f"{summary['avg_cost_per_employee']:.2f}")
    c6.metric("Затраты на единицу продукции", f"{summary['cost_per_unit']:.2f}")

    st.subheader("Динамика затрат")
    ts_df = pd.DataFrame(ts)
    if not ts_df.empty:
        ts_df = ts_df.set_index("period")
        st.line_chart(ts_df["total_cost"])
        st.dataframe(ts_df, use_container_width=True)
    else:
        st.info("Нет данных для отображения")

    st.subheader("Структура затрат")
    struct_df = pd.DataFrame(structure)
    if not struct_df.empty:
        st.bar_chart(struct_df.set_index("type")["value"])
        st.dataframe(struct_df, use_container_width=True)
    else:
        st.info("Нет данных для структуры")

    st.subheader("По подразделениям")
    dept_df = pd.DataFrame(by_department)
    if not dept_df.empty:
        st.bar_chart(dept_df.set_index("department")["total_cost"])
        st.dataframe(dept_df, use_container_width=True)
    else:
        st.info("Нет данных по подразделениям")


def reports_page(filters):
    st.title("Отчеты")

    summary = api_get("/analytics/summary", params=filters)
    structure = api_get("/analytics/structure", params=filters)
    ts = api_get("/analytics/time_series", params=filters)

    st.subheader("Сводный отчет")
    st.json(summary)

    st.subheader("Структура затрат")
    struct_df = pd.DataFrame(structure)
    st.dataframe(struct_df, use_container_width=True)

    st.subheader("Временной ряд")
    ts_df = pd.DataFrame(ts)
    st.dataframe(ts_df, use_container_width=True)


def compare_page():
    st.title("Сравнение периодов")

    departments = get_departments()
    dept_options = {0: "Все подразделения"}
    for d in departments:
        dept_options[d["id"]] = d["name"]

    col1, col2, col3 = st.columns(3)
    period_a = col1.text_input("Период A", value="2025-03", key="cmp_a")
    period_b = col2.text_input("Период B", value="2025-04", key="cmp_b")
    department_id = col3.selectbox(
        "Подразделение",
        options=list(dept_options.keys()),
        format_func=lambda x: dept_options[x],
        key="cmp_dept"
    )

    if st.button("Сравнить", use_container_width=True):
        params = {
            "period_a": period_a,
            "period_b": period_b,
            "department_id": None if department_id == 0 else department_id
        }
        result = api_get("/analytics/compare", params=params)

        st.subheader("Период A")
        st.json(result["summary_a"])

        st.subheader("Период B")
        st.json(result["summary_b"])

        st.subheader("Разница")
        diff_df = pd.DataFrame([result["difference"]]).T.reset_index()
        diff_df.columns = ["Показатель", "Разница"]
        st.dataframe(diff_df, use_container_width=True)


def forecast_page():
    st.title("Прогнозирование")

    departments = get_departments()
    dept_options = {0: "Все подразделения"}
    for d in departments:
        dept_options[d["id"]] = d["name"]

    col1, col2 = st.columns(2)
    periods_ahead = col1.number_input("Горизонт прогноза", min_value=1, max_value=24, value=3)
    department_id = col2.selectbox(
        "Подразделение",
        options=list(dept_options.keys()),
        format_func=lambda x: dept_options[x],
        key="forecast_dept"
    )

    if st.button("Построить прогноз", use_container_width=True):
        result = api_post("/forecast", json={
            "periods_ahead": int(periods_ahead),
            "department_id": None if department_id == 0 else department_id
        })

        st.success(f"Модель: {result['model_name']} | MAE: {result['mae']}")

        hist_df = pd.DataFrame(result["history"])
        hist_df["type"] = "history"
        fc_df = pd.DataFrame(result["forecast"])
        fc_df["type"] = "forecast"

        all_df = pd.concat([hist_df, fc_df], ignore_index=True)
        chart_df = all_df.pivot_table(index="period", values="value", columns="type", aggfunc="sum")
        st.line_chart(chart_df)
        st.dataframe(all_df, use_container_width=True)


def ai_chat_page(filters):
    st.title("ИИ-чат")

    history = api_get("/chat/history")
    for msg in history:
        with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
            st.write(msg["content"])

    question = st.chat_input("Введите вопрос по аналитике затрат...")
    if question:
        with st.chat_message("user"):
            st.write(question)

        result = api_post(
            "/chat/ask",
            json={"question": question},
            params=filters
        )

        with st.chat_message("assistant"):
            st.write(result["answer"])

        st.rerun()


def import_page():
    st.title("Импорт Excel")

    st.markdown(
        """
        Ожидаемые колонки в Excel:
        - `period`
        - `department`
        - `employee`
        - `position` *(необязательно)*
        - `base_salary`
        - `bonus`
        - `insurance`
        - `other_costs`
        - `planned_cost` *(необязательно)*
        - `hours_worked` *(необязательно)*
        - `units_produced` *(необязательно)*
        """
    )

    uploaded = st.file_uploader("Выберите Excel-файл", type=["xlsx", "xls"])

    if uploaded and st.button("Импортировать", use_container_width=True):
        try:
            result = api_post(
                "/costs/import_excel",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            )
            st.success(result["message"])
        except Exception as e:
            st.error(str(e))


def references_page():
    st.title("Справочники")

    tabs = st.tabs(["Подразделения", "Сотрудники"])

    with tabs[0]:
        st.subheader("Создать подразделение")
        dept_name = st.text_input("Название подразделения", key="new_dept_name")
        if st.button("Создать подразделение", key="create_dept_btn", use_container_width=True):
            try:
                result = api_post("/departments", json={"name": dept_name})
                st.success(f"Создано: {result['name']}")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        st.subheader("Список подразделений")
        dept_df = pd.DataFrame(get_departments())
        st.dataframe(dept_df, use_container_width=True)

    with tabs[1]:
        st.subheader("Создать сотрудника")
        departments = get_departments()
        if not departments:
            st.warning("Сначала создайте подразделение")
        else:
            dept_map = {d["name"]: d["id"] for d in departments}
            full_name = st.text_input("ФИО", key="emp_name")
            position = st.text_input("Должность", key="emp_position")
            dept_name = st.selectbox("Подразделение", list(dept_map.keys()), key="emp_dept")
            is_active = st.checkbox("Активен", value=True, key="emp_active")

            if st.button("Создать сотрудника", key="create_emp_btn", use_container_width=True):
                try:
                    result = api_post("/employees", json={
                        "full_name": full_name,
                        "position": position,
                        "department_id": dept_map[dept_name],
                        "is_active": is_active
                    })
                    st.success(f"Создан сотрудник: {result['full_name']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        st.subheader("Список сотрудников")
        employees = get_employees()
        emp_df = pd.DataFrame(employees)
        st.dataframe(emp_df, use_container_width=True)


def admin_page():
    st.title("Администрирование")

    tab1, tab2, tab3 = st.tabs(["Пользователи", "Журнал", "Демо-данные"])

    with tab1:
        st.subheader("Создать пользователя")
        username = st.text_input("Логин", key="admin_user_username")
        email = st.text_input("Email", key="admin_user_email")
        password = st.text_input("Пароль", type="password", key="admin_user_password")
        role = st.selectbox("Роль", ["admin", "analyst", "manager"], key="admin_user_role")

        if st.button("Создать пользователя", key="admin_create_user", use_container_width=True):
            try:
                result = api_post("/admin/users", json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "role": role
                })
                st.success(f"Создан пользователь: {result['username']}")
            except Exception as e:
                st.error(str(e))

        st.subheader("Список пользователей")
        try:
            users = api_get("/admin/users")
            st.dataframe(pd.DataFrame(users), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    with tab2:
        st.subheader("Журнал действий")
        try:
            logs = api_get("/admin/logs", params={"limit": 200})
            st.dataframe(pd.DataFrame(logs), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    with tab3:
        st.subheader("Загрузка демонстрационных данных")
        if st.button("Загрузить демо-данные", key="load_demo_data_btn", use_container_width=True):
            try:
                result = api_post("/admin/demo/load")
                st.success(result["message"])
            except Exception as e:
                st.error(str(e))


def manual_input_page():
    st.title("Ручной ввод записи")

    departments = get_departments()
    dept_names = [d["name"] for d in departments]

    period = st.text_input("Период (YYYY-MM)", value="2025-05")
    department = st.selectbox("Подразделение", dept_names) if dept_names else st.text_input("Подразделение")
    employee = st.text_input("Сотрудник")
    position = st.text_input("Должность")
    c1, c2, c3, c4 = st.columns(4)
    base_salary = c1.number_input("Оклад", min_value=0.0, value=0.0)
    bonus = c2.number_input("Премия", min_value=0.0, value=0.0)
    insurance = c3.number_input("Страховые начисления", min_value=0.0, value=0.0)
    other_costs = c4.number_input("Прочие затраты", min_value=0.0, value=0.0)

    c5, c6, c7 = st.columns(3)
    planned_cost = c5.number_input("Плановая сумма", min_value=0.0, value=0.0)
    hours_worked = c6.number_input("Отработано часов", min_value=0.0, value=0.0)
    units_produced = c7.number_input("Единиц продукции", min_value=0.0, value=0.0)

    if st.button("Сохранить запись", use_container_width=True):
        try:
            result = api_post("/costs", json={
                "period": period,
                "department": department,
                "employee": employee,
                "position": position,
                "base_salary": base_salary,
                "bonus": bonus,
                "insurance": insurance,
                "other_costs": other_costs,
                "planned_cost": planned_cost,
                "hours_worked": hours_worked,
                "units_produced": units_produced,
                "source_system": "manual"
            })
            st.success(result["message"])
        except Exception as e:
            st.error(str(e))


def main_app():
    st.sidebar.title("Навигация")
    st.sidebar.write(f"Пользователь: **{st.session_state.get('username')}**")
    st.sidebar.write(f"Роль: **{st.session_state.get('role')}**")

    if st.sidebar.button("Выйти"):
        st.session_state.clear()
        st.rerun()

    filters = sidebar_filters()

    role = st.session_state.get("role")

    pages = {
        "Дашборд": lambda: dashboard_page(filters),
        "Отчеты": lambda: reports_page(filters),
        "Сравнение периодов": compare_page,
        "Прогнозирование": forecast_page,
        "ИИ-чат": lambda: ai_chat_page(filters),
    }

    if role in ["admin", "analyst"]:
        pages["Ручной ввод"] = manual_input_page
        pages["Импорт Excel"] = import_page
        pages["Справочники"] = references_page

    if role == "admin":
        pages["Администрирование"] = admin_page

    selected = st.sidebar.radio("Раздел", list(pages.keys()))
    pages[selected]()


if "token" not in st.session_state:
    login_page()
else:
    main_app()
