"""Парсинг HTML-страниц Django admin: summary, ГОСТ, итерация, тест, задача."""

import re

from bs4 import BeautifulSoup

import config


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _text(tag) -> str:
    """Текст элемента с очисткой пробелов."""
    if tag is None:
        return ""
    return " ".join(tag.get_text(" ", strip=True).split())


def _input_value(tag) -> str:
    """Значение input-элемента."""
    if tag is None:
        return ""
    return tag.get("value", "").strip()


def _textarea_text(tag) -> str:
    """Текст textarea."""
    if tag is None:
        return ""
    return tag.get_text("\n", strip=True).strip()


def _select_selected(tag) -> str:
    """Текст выбранной option в select."""
    if tag is None:
        return ""
    opt = tag.find("option", selected=True)
    return _text(opt) if opt else ""


def _select_selected_value(tag) -> str:
    """Значение выбранной option в select."""
    if tag is None:
        return ""
    opt = tag.find("option", selected=True)
    return opt.get("value", "").strip() if opt else ""


def _checkbox_checked(tag) -> str:
    """Флаг чекбокса: '1' если отмечен, иначе ''."""
    if tag is None:
        return ""
    return "1" if tag.has_attr("checked") else ""


def _readonly_text(soup, field_name: str) -> str:
    """Текст readonly-поля .form-row.field-<name>."""
    row = soup.select_one(f".form-row.field-{field_name}")
    if row is None:
        return ""
    return _text(row.select_one(".readonly"))


def _full_url(path: str) -> str:
    """Полный URL с доменом."""
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return config.BASE_URL + path


def _row_id(row, prefix: str) -> str:
    """id из hidden input вида <prefix>-N-id."""
    inp = row.find("input", attrs={"name": re.compile(rf"^{re.escape(prefix)}-\d+-id$")})
    return inp.get("value", "").strip() if inp else ""


# ---------------------------------------------------------------------------
# Summary: список ГОСТ отчетов
# ---------------------------------------------------------------------------

def parse_summary(html: str) -> list[dict]:
    """Парсит таблицу #gost-summary-table. Возвращает список ГОСТов."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("#gost-summary-table")
    if table is None:
        return []

    gosts = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 20:
            continue

        link = tds[0].find("a", href=True)
        if link is None:
            continue
        gost_url = _full_url(link["href"])
        m = re.search(r"/gostreport/(\d+)/change/", link["href"])
        gost_id = m.group(1) if m else ""

        # Пром статистика: иконка fa-check-square = да, fa-ban = нет
        is_stats_prom = "1" if tds[2].select_one(".fa-check-square") else ""

        # Ссылки на отчеты (share_url)
        share_url = ""
        share_td = tds[12]
        a = share_td.find("a", href=True)
        if a:
            share_url = a["href"].strip()

        gosts.append({
            "gost_id": gost_id,
            "name": _text(link),
            "url": gost_url,
            "type_of_test": _text(tds[1]),
            "is_stats_prom": is_stats_prom,
            "kg": _text(tds[3]),
            "ke": _text(tds[4]),
            "rs": _text(tds[5]),
            "ak": _text(tds[6]),
            "status": _select_selected(tds[7].find("select")),
            "quarter": _input_value(tds[8].find("input")),
            "test_count": _text(tds[9]),
            "iteration_count": _text(tds[10]),
            "gost_sys": _text(tds[11]),
            "share_url": share_url,
            "editor": _text(tds[13]),
            "curator": _text(tds[14]),
            "request": _input_value(tds[15].find("input")),
            "p_number": _input_value(tds[16].find("input")),
            "test_dates": _text(tds[17]),
            "start_gost_date": _input_value(tds[18].find("input")),
            "end_gost_date": _input_value(tds[19].find("input")),
        })
    return gosts


# ---------------------------------------------------------------------------
# ГОСТ отчет: форма + inline-итерации
# ---------------------------------------------------------------------------

def parse_gost(html: str, url: str) -> tuple[dict, list[dict]]:
    """Парсит страницу ГОСТ отчета. Возвращает (данные ГОСТа, список итераций)."""
    soup = BeautifulSoup(html, "lxml")

    def field(field_name: str):
        return soup.select_one(f".form-row.field-{field_name}")

    gost = {
        "gost_id": "",
        "name": _text(soup.select_one("h2")),
        "url": url,
        "alias": _input_value(field("alias").select_one("input") if field("alias") else None),
        "quarter": _input_value(field("quarter").select_one("input") if field("quarter") else None),
        "is_stats_prom": _checkbox_checked(field("is_stats_prom").select_one("input") if field("is_stats_prom") else None),
        "type_of_test": _select_selected(field("type_of_test").select_one("select") if field("type_of_test") else None),
        "testing_result": _textarea_text(field("testing_result").select_one("textarea") if field("testing_result") else None),
        "bottlenecks": _textarea_text(field("bottlenecks").select_one("textarea") if field("bottlenecks") else None),
        "recommendation": _textarea_text(field("recommendation").select_one("textarea") if field("recommendation") else None),
        "url_preview": "",
        "gost_sys": _select_selected(field("gost_sys").select_one("select") if field("gost_sys") else None),
        "review": _select_selected(field("review").select_one("select") if field("review") else None),
        "editor": _select_selected(field("editor").select_one("select") if field("editor") else None),
        "status": _select_selected(field("status").select_one("select") if field("status") else None),
        "start_actual_date": _input_value(field("start_actual_date").select_one("input") if field("start_actual_date") else None),
        "end_actual_date": _input_value(field("end_actual_date").select_one("input") if field("end_actual_date") else None),
        "request": _input_value(field("request").select_one("input") if field("request") else None),
        "p_number": _input_value(field("p_number").select_one("input") if field("p_number") else None),
        "start_gost_date": _input_value(field("start_gost_date").select_one("input") if field("start_gost_date") else None),
        "end_gost_date": _input_value(field("end_gost_date").select_one("input") if field("end_gost_date") else None),
        "share_url": _input_value(field("share_url").select_one("input") if field("share_url") else None),
        "version": _readonly_text(soup, "version"),
    }

    # Превью результата
    preview = field("url_preview")
    if preview:
        a = preview.find("a", href=True)
        if a:
            gost["url_preview"] = _full_url(a["href"])

    # id ГОСТа из URL
    m = re.search(r"/gostreport/(\d+)/change/", url)
    if m:
        gost["gost_id"] = m.group(1)

    # Inline-итерации
    iterations = []
    group = soup.select_one("#iterations-group")
    if group:
        for tr in group.select("tbody tr.form-row.has_original"):
            it_id = _row_id(tr, "iterations")
            if not it_id:
                continue
            created = tr.select_one(".field-created_at")
            created_date = _input_value(created.select_one("input[name$='-created_at_0']")) if created else ""
            created_time = _input_value(created.select_one("input[name$='-created_at_1']")) if created else ""
            task_td = tr.select_one(".field-task")
            task_id = _input_value(task_td.select_one("input")) if task_td else ""
            iterations.append({
                "iteration_id": it_id,
                "gost_id": gost["gost_id"],
                "url": _full_url(f"/admin/autoreport/iteration/{it_id}/change/"),
                "created_at": f"{created_date} {created_time}".strip(),
                "emulator_count": _input_value(tr.select_one(".field-emulator_count input")),
                "generator_count": _input_value(tr.select_one(".field-generator_count input")),
                "developed_script_count": _input_value(tr.select_one(".field-developed_script_count input")),
                "updated_script_count": _input_value(tr.select_one(".field-updated_script_count input")),
                "testing_result": _textarea_text(tr.select_one(".field-testing_result textarea")),
                "bottlenecks": _textarea_text(tr.select_one(".field-bottlenecks textarea")),
                "recommendation": _textarea_text(tr.select_one(".field-recommendation textarea")),
                "task_id": task_id,
                "iter_num": _text(tr.select_one(".field-iter_num")),
                "test_count": _text(tr.select_one(".field-test_count")),
                "first_test_date": _text(tr.select_one(".field-first_test_date")),
                "last_test_date": _text(tr.select_one(".field-last_test_date")),
            })
    return gost, iterations


# ---------------------------------------------------------------------------
# Итерация: форма + inline-тесты
# ---------------------------------------------------------------------------

def parse_iteration(html: str, url: str) -> tuple[dict, list[dict]]:
    """Парсит страницу итерации. Возвращает (данные итерации, список тестов)."""
    soup = BeautifulSoup(html, "lxml")

    def field(field_name: str):
        return soup.select_one(f".form-row.field-{field_name}")

    created = field("created_at")
    created_date = _input_value(created.select_one("input[name='created_at_0']")) if created else ""
    created_time = _input_value(created.select_one("input[name='created_at_1']")) if created else ""

    iteration = {
        "iteration_id": "",
        "gost_id": _select_selected_value(field("gost_report").select_one("select") if field("gost_report") else None),
        "url": url,
        "created_at": f"{created_date} {created_time}".strip(),
        "emulator_count": _input_value(field("emulator_count").select_one("input") if field("emulator_count") else None),
        "generator_count": _input_value(field("generator_count").select_one("input") if field("generator_count") else None),
        "developed_script_count": _input_value(field("developed_script_count").select_one("input") if field("developed_script_count") else None),
        "updated_script_count": _input_value(field("updated_script_count").select_one("input") if field("updated_script_count") else None),
        "testing_result": _textarea_text(field("testing_result").select_one("textarea") if field("testing_result") else None),
        "bottlenecks": _textarea_text(field("bottlenecks").select_one("textarea") if field("bottlenecks") else None),
        "recommendation": _textarea_text(field("recommendation").select_one("textarea") if field("recommendation") else None),
        "task_id": _select_selected_value(field("task").select_one("select") if field("task") else None),
        "iter_num": _readonly_text(soup, "iter_num"),
        "first_test_date": _readonly_text(soup, "first_test_date"),
        "last_test_date": _readonly_text(soup, "last_test_date"),
    }

    m = re.search(r"/iteration/(\d+)/change/", url)
    if m:
        iteration["iteration_id"] = m.group(1)

    # Inline-тесты
    tests = []
    group = soup.select_one("#tests-group")
    if group:
        for tr in group.select("tbody tr.form-row.has_original"):
            test_id = _row_id(tr, "tests")
            if not test_id:
                continue
            grafana = tr.select_one(".field-grafana a")
            engineer = tr.select_one(".field-engineer select")
            tests.append({
                "test_id": test_id,
                "iteration_id": iteration["iteration_id"],
                "url": _full_url(f"/admin/autoreport/test/{test_id}/change/"),
                "number": _text(tr.select_one(".field-number")),
                "detailing": _checkbox_checked(tr.select_one(".field-detailing input")),
                "name_of_test": _input_value(tr.select_one(".field-name_of_test input")),
                "from_ts": _input_value(tr.select_one(".field-from_ts input")),
                "to_ts": _input_value(tr.select_one(".field-to_ts input")),
                "test_description": _textarea_text(tr.select_one(".field-test_description textarea")),
                "test_results": _textarea_text(tr.select_one(".field-test_results textarea")),
                "grafana_url": grafana["href"].strip() if grafana else "",
                "start_date": _text(tr.select_one(".field-start_date")),
                "end_date": _text(tr.select_one(".field-end_date")),
                "duration": _text(tr.select_one(".field-duration")),
                "engineer": _select_selected(engineer),
                "url_preview": "",
                "from_vp": "",
                "to_vp": "",
            })
    return iteration, tests


# ---------------------------------------------------------------------------
# Тест: добираем url_preview, from_vp, to_vp
# ---------------------------------------------------------------------------

def parse_test(html: str, url: str) -> dict:
    """Парсит страницу теста. Возвращает дополнительные поля."""
    soup = BeautifulSoup(html, "lxml")

    def field(field_name: str):
        return soup.select_one(f".form-row.field-{field_name}")

    result = {
        "test_id": "",
        "url": url,
        "url_preview": "",
        "from_vp": _readonly_text(soup, "from_vp"),
        "to_vp": _readonly_text(soup, "to_vp"),
    }

    m = re.search(r"/test/(\d+)/change/", url)
    if m:
        result["test_id"] = m.group(1)

    preview = field("url_preview")
    if preview:
        a = preview.find("a", href=True)
        if a:
            result["url_preview"] = _full_url(a["href"])
    return result


# ---------------------------------------------------------------------------
# Задача: форма + inline-ссылки
# ---------------------------------------------------------------------------

def parse_task(html: str, url: str) -> tuple[dict, list[dict]]:
    """Парсит страницу задачи. Возвращает (данные задачи, список ссылок)."""
    soup = BeautifulSoup(html, "lxml")

    def field(field_name: str):
        return soup.select_one(f".form-row.field-{field_name}")

    created = field("created_at")
    created_date = _input_value(created.select_one("input[name='created_at_0']")) if created else ""
    created_time = _input_value(created.select_one("input[name='created_at_1']")) if created else ""

    engineer_sel = field("engineer").select_one("select") if field("engineer") else None
    engineers = []
    if engineer_sel:
        engineers = [_text(o) for o in engineer_sel.find_all("option", selected=True)]

    task = {
        "task_id": "",
        "name": _text(soup.select_one("h2")),
        "url": url,
        "created_at": f"{created_date} {created_time}".strip(),
        "title": _input_value(field("title").select_one("input") if field("title") else None),
        "jira_id": _input_value(field("jira_id").select_one("input") if field("jira_id") else None),
        "page_id": _input_value(field("page_id").select_one("input") if field("page_id") else None),
        "wiki_url": _select_selected(field("wiki_url").select_one("select") if field("wiki_url") else None),
        "status": _select_selected(field("status").select_one("select") if field("status") else None),
        "testing_result": _textarea_text(field("testing_result").select_one("textarea") if field("testing_result") else None),
        "grafana_url": _input_value(field("grafana_url").select_one("input") if field("grafana_url") else None),
        "station_metrics": _textarea_text(field("station_metrics").select_one("textarea") if field("station_metrics") else None),
        "server_metrics": _textarea_text(field("server_metrics").select_one("textarea") if field("server_metrics") else None),
        "bottlenecks": _textarea_text(field("bottlenecks").select_one("textarea") if field("bottlenecks") else None),
        "recommendation": _textarea_text(field("recommendation").select_one("textarea") if field("recommendation") else None),
        "purposes": _textarea_text(field("purposes").select_one("textarea") if field("purposes") else None),
        "requirements": _textarea_text(field("requirements").select_one("textarea") if field("requirements") else None),
        "restriction": _textarea_text(field("restriction").select_one("textarea") if field("restriction") else None),
        "test_data": _textarea_text(field("test_data").select_one("textarea") if field("test_data") else None),
        "project": _select_selected(field("project").select_one("select") if field("project") else None),
        "project_id": _select_selected_value(field("project").select_one("select") if field("project") else None),
        "engineer": "; ".join(engineers),
        "curator": _select_selected(field("curator").select_one("select") if field("curator") else None),
        "updated_at": _readonly_text(soup, "updated_at"),
    }

    m = re.search(r"/task/(\d+)/change/", url)
    if m:
        task["task_id"] = m.group(1)

    # Inline-ссылки задач
    links = []
    group = soup.select_one("#links-group")
    if group:
        for tr in group.select("tbody tr.form-row.has_original"):
            link_id = _row_id(tr, "links")
            if not link_id:
                continue
            links.append({
                "link_id": link_id,
                "task_id": task["task_id"],
                "url": url,
                "link_type": _select_selected_value(tr.select_one(".field-link_type select")),
                "link_url": _input_value(tr.select_one(".field-url input")),
                "description": _input_value(tr.select_one(".field-description input")),
            })
    return task, links


# ---------------------------------------------------------------------------
# Проект: все поля формы .form-row.field-* автоматически
# ---------------------------------------------------------------------------

def parse_project(html: str, url: str) -> dict:
    """Парсит страницу проекта. Возвращает все поля формы.

    Поля извлекаются автоматически из каждого .form-row.field-<name> по типу
    элемента: checkbox → флаг, select → текст выбранной option, textarea → текст,
    .readonly → текст, иначе input → value.
    """
    soup = BeautifulSoup(html, "lxml")

    project = {
        "project_id": "",
        "name": _text(soup.select_one("h2")),
        "url": url,
    }

    m = re.search(r"/project/(\d+)/change/", url)
    if m:
        project["project_id"] = m.group(1)

    for row in soup.select(".form-row"):
        # имя поля из класса field-<name>
        cls = [c for c in row.get("class", []) if c.startswith("field-")]
        if not cls:
            continue
        field_name = cls[0][len("field-"):]
        if not field_name:
            continue

        # datetime: два input name="<field>_0" и name="<field>_1" (дата + время)
        dt_date = row.select_one('input[name$="_0"]')
        dt_time = row.select_one('input[name$="_1"]')
        if dt_date is not None and dt_time is not None:
            project[field_name] = (
                f"{_input_value(dt_date)} {_input_value(dt_time)}".strip()
            )
            continue

        # checkbox
        checkbox = row.select_one('input[type="checkbox"]')
        if checkbox is not None:
            project[field_name] = _checkbox_checked(checkbox)
            continue

        # select
        select = row.select_one("select")
        if select is not None:
            project[field_name] = _select_selected(select)
            continue

        # textarea
        textarea = row.select_one("textarea")
        if textarea is not None:
            project[field_name] = _textarea_text(textarea)
            continue

        # readonly
        readonly = row.select_one(".readonly")
        if readonly is not None:
            project[field_name] = _text(readonly)
            continue

        # input
        inp = row.select_one("input")
        if inp is not None:
            project[field_name] = _input_value(inp)
            continue

        # иначе — текст строки
        project[field_name] = _text(row)

    return project
