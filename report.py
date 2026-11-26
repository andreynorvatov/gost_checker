"""Сборщик HTML-отчёта из CSV-файлов папки запуска.

Читает gosts.csv, iterations.csv, tests.csv, tasks.csv, task_links.csv
и формирует красивый отчёт report.html в той же папке.
"""

import csv
import html
import os
from datetime import datetime

import config

# Человекочитаемые названия полей
FIELD_LABELS = {
    # ГОСТ
    "gost_id": "ID ГОСТа",
    "name": "Название",
    "url": "Ссылка",
    "type_of_test": "Тип теста",
    "is_stats_prom": "Пром статистика (НиО)",
    "kg": "КГ",
    "ke": "КЭ",
    "rs": "РС",
    "ak": "АК",
    "status": "Статус",
    "quarter": "Квартал",
    "test_count": "Кол. тестов",
    "iteration_count": "Кол. итераций",
    "gost_sys": "ГОСТ система",
    "share_url": "Ссылка на sharepoint",
    "editor": "Инженер",
    "curator": "Лид",
    "request": "Номер заявки",
    "p_number": "ПП номер",
    "test_dates": "Даты тестов",
    "start_gost_date": "ГОСТ дата (начало)",
    "end_gost_date": "ГОСТ дата (конец)",
    "alias": "Алиас проекта",
    "testing_result": "Результаты тестирования",
    "bottlenecks": "Узкие места",
    "recommendation": "Рекомендации",
    "url_preview": "Превью",
    "review": "Ревьювер",
    "start_actual_date": "Начало тестирования",
    "end_actual_date": "Конец тестирования",
    "version": "Версия",
    # Итерация
    "iteration_id": "ID итерации",
    "created_at": "Дата добавления",
    "emulator_count": "КЭ",
    "generator_count": "КГ",
    "developed_script_count": "РС",
    "updated_script_count": "АС",
    "task_id": "ID задачи",
    "iter_num": "Номер итерации",
    "first_test_date": "Дата первого теста",
    "last_test_date": "Дата последнего теста",
    # Тест
    "test_id": "ID теста",
    "number": "№",
    "detailing": "Детализация",
    "name_of_test": "Наименование теста",
    "from_ts": "Начало (timestamp)",
    "to_ts": "Конец (timestamp)",
    "test_description": "Описание теста",
    "test_results": "Результаты теста",
    "grafana_url": "Grafana",
    "start_date": "Начало теста",
    "end_date": "Конец теста",
    "duration": "Длительность (сек)",
    "engineer": "Инженер",
    "engineer_id": "ID инженера",
    "from_vp": "From vp",
    "to_vp": "To vp",
    # Список тестов (changelist)
    "test_name": "Название теста",
    "grafana": "Grafana",
    # Задача
    "title": "Имя задачи",
    "jira_id": "JIRA_ID",
    "page_id": "ID родительской страницы",
    "wiki_url": "Ссылка на wiki",
    "grafana_url_task": "Grafana url",
    "station_metrics": "Station metrics",
    "server_metrics": "Server metrics",
    "purposes": "Цели",
    "requirements": "Требования",
    "restriction": "Ограничения",
    "test_data": "Тестовые данные",
    "project": "Проект",
    "project_id": "ID проекта",
    "project_name_shrt": "Наименование проекта",
    "project_name_full": "Полное наименование системы",
    "project_description": "Описание",
    "project_url": "Точки доступа",
    "gitlab_url": "Скрипты gitlab",
    "sub_systems": "Подсистемы",
    "product": "Продукт",
    "default_sla_time": "SLA",
    "influxdb": "Конфигурация influxdb",
    "updated_at": "Дата обновления",
    # Ссылки задач
    "link_id": "ID ссылки",
    "link_type": "Тип",
    "link_url": "URL",
    "description": "Описание",
}

# Поля, которые не показываем в карточках (служебные/дублирующие)
HIDDEN_FIELDS = {"gost_id", "iteration_id", "test_id", "task_id", "link_id"}

# Всплывающие подсказки для шапки таблицы ГОСТов
FIELD_TOOLTIPS = {
    "kg": "Количество генераторов",
    "ke": "Количество эмуляторов",
    "rs": "Количество разработанных скриптов",
    "ak": "Актуализировано скриптов",
    "generator_count": "Количество генераторов",
    "emulator_count": "Количество эмуляторов",
    "developed_script_count": "Количество разработанных скриптов",
    "updated_script_count": "Актуализировано скриптов",
}

# Поля-ссылки (рендерятся как <a>)
URL_FIELDS = {"url", "url_preview", "share_url", "grafana_url", "grafana_url_task", "link_url", "grafana"}

# Поля с длинным текстом (рендерятся с переносами)
TEXT_FIELDS = {
    "testing_result", "bottlenecks", "recommendation", "test_description",
    "test_results", "station_metrics", "server_metrics", "purposes",
    "requirements", "restriction", "test_data",
}

# Порядок полей для карточек
GOST_ORDER = [
    "name", "url", "type_of_test", "is_stats_prom", "status", "quarter",
    "gost_sys", "alias", "editor", "curator", "review", "request", "p_number",
    "kg", "ke", "rs", "ak", "test_count", "iteration_count", "test_dates",
    "start_actual_date", "end_actual_date", "start_gost_date", "end_gost_date",
    "share_url", "url_preview", "version", "testing_result", "bottlenecks", "recommendation",
]

# Поля ГОСТа, выносимые над таблицей (пустое значение → «не контролируется»)
GOST_ABOVE_FIELDS = ["request", "p_number", "start_gost_date", "end_gost_date", "share_url", "version"]

ITERATION_ORDER = [
    "url", "created_at", "iter_num", "emulator_count", "generator_count",
    "developed_script_count", "updated_script_count", "first_test_date",
    "last_test_date", "testing_result", "bottlenecks", "recommendation",
]

TEST_ORDER = [
    "number", "name_of_test", "detailing", "timestamps", "dates",
    "engineer", "test_description", "test_results",
]

TASK_ORDER = [
    "url", "title", "jira_id", "status", "project", "engineer", "curator",
    "created_at", "updated_at", "wiki_url", "page_id", "grafana_url_task",
    "purposes", "requirements", "restriction", "test_data", "testing_result",
    "bottlenecks", "recommendation", "station_metrics", "server_metrics",
]

# Текстовые поля задачи — выносятся в отдельную таблицу ниже горизонтальной
TASK_TEXT_FIELDS = [
    "purposes", "requirements", "restriction", "test_data", "testing_result",
    "bottlenecks", "recommendation", "station_metrics", "server_metrics",
]

LINK_ORDER = ["link_type", "link_url", "description"]


def _esc(value: str) -> str:
    """Экранирование для HTML."""
    return html.escape(str(value or ""), quote=True)


def _fmt(value: str) -> str:
    """Форматирование значения: переносы строк в <br>."""
    return _esc(value).replace("\n", "<br>")


def _render_value(key: str, value: str, url_fields: set | None = None) -> str:
    """Рендер значения поля: ссылка, длинный текст или обычный текст."""
    value = str(value or "")
    if not value:
        return '<span class="empty">—</span>'
    if key == "url_preview":
        return f'<a href="{_esc(value)}" target="_blank" rel="noopener">Превью</a>'
    if key in ("grafana", "grafana_url"):
        return f'<a href="{_esc(value)}" target="_blank" rel="noopener">Grafana</a>'
    if key in URL_FIELDS or (url_fields and key in url_fields):
        return f'<a href="{_esc(value)}" target="_blank" rel="noopener">{_esc(value)}</a>'
    if key in TEXT_FIELDS:
        return f'<div class="multiline">{_fmt(value)}</div>'
    return _esc(value)


def _field_table(data: dict, order: list[str]) -> str:
    """Таблица «поле — значение» для карточки."""
    rows = []
    for key in order:
        if key not in data:
            continue
        label = FIELD_LABELS.get(key, key)
        rows.append(
            f'<tr><th>{_esc(label)}</th><td>{_render_value(key, data.get(key, ""))}</td></tr>'
        )
    return f'<table class="fields">{"" .join(rows)}</table>'


def _horizontal_table(data: dict, order: list[str], url_fields: set | None = None) -> str:
    """Горизонтальная таблица: одна строка заголовков + одна строка значений."""
    keys = [k for k in order if k in data]
    if not keys:
        return ""
    headers = []
    for k in keys:
        label = FIELD_LABELS.get(k, k)
        tip = FIELD_TOOLTIPS.get(k)
        if tip:
            headers.append(f'<th class="has-tip" data-tip="{_esc(tip)}">{_esc(label)}</th>')
        else:
            headers.append(f"<th>{_esc(label)}</th>")
    values = "".join(
        f"<td>{_render_value(k, data.get(k, ""), url_fields)}</td>" for k in keys
    )
    return f'<table class="hfields"><tr>{"".join(headers)}</tr><tr>{values}</tr></table>'


def _above_fields(data: dict, order: list[str]) -> str:
    """Строка полей над таблицей. Значения подставляются из данных."""
    items = []
    for k in order:
        if k not in data:
            continue
        label = FIELD_LABELS.get(k, k)
        value = str(data.get(k, "") or "")
        val_html = _render_value(k, value) if value else '<span class="empty">—</span>'
        items.append(
            f'<span class="af-item"><span class="af-label">{_esc(label)}:</span> {val_html}</span>'
        )
    if not items:
        return ""
    info = '<span class="has-tip info-icon" data-tip="Параметры для инфо">ℹ️</span>'
    return f'<div class="above-fields">{info}{"".join(items)}</div>'


def _data_table(rows: list[dict], order: list[str], id_key: str, link_col: str | None = None) -> str:
    """Таблица данных (итерации/тесты/ссылки).

    Если задан link_col, значение этой колонки рендерится ссылкой на url строки.
    Спец-колонка "timestamps" объединяет from_ts/to_ts/duration в одну ячейку.
    """
    if not rows:
        return '<p class="empty">Нет данных</p>'
    headers = []
    for k in order:
        if k == "timestamps":
            headers.append("<th>Начало<br>Конец<br>Длительность (сек)</th>")
        elif k == "dates":
            headers.append("<th>Начало<br>Конец</th>")
        elif k in rows[0]:
            cls = ' class="wide"' if k in ("test_description", "test_results") else ""
            headers.append(f"<th{cls}>{_esc(FIELD_LABELS.get(k, k))}</th>")
    thead = "".join(headers)
    body = []
    for row in rows:
        tds = []
        for k in order:
            if k == "timestamps":
                parts = [row.get("from_ts", ""), row.get("to_ts", ""), row.get("duration", "")]
                val = "<br>".join(_esc(p) for p in parts if p)
                if row.get("grafana_url"):
                    val += (
                        f'<br><a href="{_esc(row["grafana_url"])}" target="_blank" rel="noopener">'
                        f"Grafana</a>"
                    )
                tds.append(f"<td>{val}</td>")
                continue
            if k == "dates":
                parts = [row.get("start_date", ""), row.get("end_date", "")]
                val = "<br>".join(_esc(p) for p in parts if p)
                tds.append(f"<td>{val}</td>")
                continue
            if k not in row:
                continue
            if k == link_col and row.get("url"):
                val = (
                    f'<a href="{_esc(row["url"])}" target="_blank" rel="noopener">'
                    f'{_esc(row.get(k, ""))}</a>'
                )
                if row.get("url_preview"):
                    val += (
                        f' <a href="{_esc(row["url_preview"])}" target="_blank" rel="noopener">'
                        f"превью</a>"
                    )
            else:
                val = _render_value(k, row.get(k, ""))
            cls = ' class="wide"' if k in ("test_description", "test_results") else ""
            tds.append(f"<td{cls}>{val}</td>")
        body.append(f"<tr>{''.join(tds)}</tr>")
    return f'<table class="data"><thead><tr>{thead}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _load_csv(path: str) -> list[dict]:
    """Чтение CSV (utf-8-sig) в список словарей."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _date_only(value: str) -> str:
    """Нормализует дату теста до YYYY-MM-DD."""
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value[:10]


def _stat_card(label: str, value: int, icon: str) -> str:
    return (
        f'<div class="stat"><div class="stat-icon">{icon}</div>'
        f'<div class="stat-value">{value}</div>'
        f'<div class="stat-label">{_esc(label)}</div></div>'
    )


ENTITY_LABELS = {
    "gosts": "ГОСТы",
    "iterations": "Итерации",
    "tests": "Тесты",
    "tasks": "Задачи",
    "task_links": "Ссылки задач",
    "projects": "Проекты",
}

# URL-паттерны страниц портала по сущности
ENTITY_URL_PATTERNS = {
    "gosts": f"{config.BASE_URL}/admin/autoreport/gostreport/{{id}}/change/",
    "iterations": f"{config.BASE_URL}/admin/autoreport/iteration/{{id}}/change/",
    "tests": f"{config.BASE_URL}/admin/autoreport/test/{{id}}/change/",
    "tasks": f"{config.BASE_URL}/admin/autoreport/task/{{id}}/change/",
    "projects": f"{config.BASE_URL}/admin/autoreport/project/{{id}}/change/",
}


def _entity_url(entity: str, entity_id: str) -> str | None:
    """URL страницы элемента на портале. None, если ссылки нет
    (например, entity_id — значение группы, а не id)."""
    pattern = ENTITY_URL_PATTERNS.get(entity)
    if not pattern or not entity_id:
        return None
    if not str(entity_id).strip().isdigit():
        return None
    return pattern.format(id=entity_id)


def _summary_url() -> str:
    """URL страницы summary с текущими параметрами фильтра из config.QUERY_PARAMS."""
    params = "&".join(f"{k}={v}" for k, v in config.QUERY_PARAMS.items())
    return f"{config.BASE_URL}/gost/summary/?{params}"


def _checks_section(checks: list[dict]) -> str:
    """Секция «Проверки»: сводка по сущностям + таблица нарушений (fail)."""
    if not checks:
        return ""

    total = len(checks)
    fails = [c for c in checks if c.get("status") == "fail"]

    # Сводка по сущностям
    by_entity: dict[str, dict[str, int]] = {}
    for c in checks:
        ent = c.get("entity", "")
        agg = by_entity.setdefault(ent, {"total": 0, "ok": 0, "fail": 0})
        agg["total"] += 1
        if c.get("status") == "fail":
            agg["fail"] += 1
        else:
            agg["ok"] += 1

    summary_rows = []
    for ent, agg in by_entity.items():
        label = ENTITY_LABELS.get(ent, ent)
        cls = "bad" if agg["fail"] else "good"
        summary_rows.append(
            f'<tr><td>{_esc(label)}</td><td>{agg["total"]}</td>'
            f'<td>{agg["ok"]}</td><td class="{cls}">{agg["fail"]}</td></tr>'
        )
    summary_html = (
        f'<table class="data checks-summary"><thead><tr>'
        f"<th>Сущность</th><th>Всего</th><th>OK</th><th>Нарушений</th>"
        f"</tr></thead><tbody>{''.join(summary_rows)}</tbody></table>"
    )

    # Полная таблица всех проверок (ok + fail) с фильтром по кнопке
    all_rows = []
    for c in checks:
        status = c.get("status", "")
        cls = "row-fail" if status == "fail" else "row-ok"
        entity_id = c.get("entity_id", "")
        url = _entity_url(c.get("entity", ""), entity_id)
        id_html = (
            f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(entity_id)}</a>'
            if url else _esc(entity_id)
        )
        all_rows.append(
            f'<tr class="{cls}" data-status="{_esc(status)}">'
            f'<td>{_esc(ENTITY_LABELS.get(c.get("entity", ""), c.get("entity", "")))}</td>'
            f'<td>{id_html}</td>'
            f'<td>{_esc(FIELD_LABELS.get(c.get("field", ""), c.get("field", "")))}</td>'
            f'<td>{_esc(c.get("check_type", ""))}</td>'
            f'<td>{_esc(c.get("expected", ""))}</td>'
            f'<td>{_esc(c.get("actual", ""))}</td>'
            f'<td>{_esc(c.get("message", ""))}</td>'
            f'<td>{_esc(c.get("description", ""))}</td>'
            f'<td class="status-cell">{_esc(status)}</td></tr>'
        )
    table_html = (
        f'<div class="checks-toolbar">'
        f'<button class="btn-check" id="btn-all" onclick="filterChecks(\'all\')">Все ({total})</button>'
        f'<button class="btn-check active" id="btn-fails" onclick="filterChecks(\'fails\')">Только нарушения ({len(fails)})</button>'
        f'</div>'
        f'<table class="data checks-table" id="checks-table"><thead><tr>'
        f"<th>Сущность</th><th>ID</th><th>Поле</th><th>Тип</th>"
        f"<th>Ожидалось</th><th>Фактически</th><th>Сообщение</th><th>Описание</th><th>Статус</th>"
        f"</tr></thead><tbody>{''.join(all_rows)}</tbody></table>"
    )

    return (
        f'<h2 id="checks">Проверки</h2>'
        f'<div class="card">'
        f'<div class="checks-total">Всего проверок: {total} · Нарушений: '
        f'<span class="{"bad" if fails else "good"}">{len(fails)}</span></div>'
        f"{summary_html}{table_html}"
        f'<script>'
        f"function filterChecks(mode) {{"
        f"  var rows = document.querySelectorAll('#checks-table tbody tr');"
        f"  var btnAll = document.getElementById('btn-all');"
        f"  var btnFails = document.getElementById('btn-fails');"
        f"  rows.forEach(function(r) {{"
        f"    r.style.display = (mode === 'fails' && r.getAttribute('data-status') !== 'fail') ? 'none' : '';"
        f"  }});"
        f"  btnAll.classList.toggle('active', mode === 'all');"
        f"  btnFails.classList.toggle('active', mode === 'fails');"
        f"}}"
        f"filterChecks('fails');"
        f"</script>"
        f"</div>"
    )


def build_report(run_dir: str) -> str:
    """Формирует report.html в папке запуска. Возвращает путь к файлу."""
    gosts = _load_csv(os.path.join(run_dir, "gosts.csv"))
    iterations = _load_csv(os.path.join(run_dir, "iterations.csv"))
    tests = _load_csv(os.path.join(run_dir, "tests.csv"))
    tasks = _load_csv(os.path.join(run_dir, "tasks.csv"))
    links = _load_csv(os.path.join(run_dir, "task_links.csv"))
    projects = _load_csv(os.path.join(run_dir, "projects.csv"))
    test_list = _load_csv(os.path.join(run_dir, "test_list.csv"))
    checks = _load_csv(os.path.join(run_dir, "checks.csv"))

    # Индексы по id
    iters_by_gost: dict[str, list[dict]] = {}
    for it in iterations:
        iters_by_gost.setdefault(it.get("gost_id", ""), []).append(it)
    tests_by_iter: dict[str, list[dict]] = {}
    for t in tests:
        tests_by_iter.setdefault(t.get("iteration_id", ""), []).append(t)
    links_by_task: dict[str, list[dict]] = {}
    for lk in links:
        links_by_task.setdefault(lk.get("task_id", ""), []).append(lk)
    projects_by_id: dict[str, dict] = {}
    for p in projects:
        projects_by_id[p.get("project_id", "")] = p

    # Сводка
    stats = (
        _stat_card("ГОСТ отчетов", len(gosts), "📋")
        + _stat_card("Итераций", len(iterations), "🔁")
        + _stat_card("Тестов", len(tests), "🧪")
        + _stat_card("Задач", len(tasks), "📌")
        + _stat_card("Ссылок задач", len(links), "🔗")
        + _stat_card("Проектов", len(projects), "📁")
        + _stat_card("Тестов (список)", len(test_list), "📋")
    )

    # Секция ГОСТов
    gost_sections = []
    gost_h_order = [
        k for k in GOST_ORDER
        if k not in (
            "name", "url", "url_preview", "testing_result", "bottlenecks",
            "recommendation", *GOST_ABOVE_FIELDS,
        )
    ]
    for g in gosts:
        gid = g.get("gost_id", "")
        gname = g.get("name", gid)
        gurl = g.get("url", "")
        gpreview = g.get("url_preview", "")
        its = iters_by_gost.get(gid, [])
        iter_blocks = []
        iter_h_order = [
            k for k in ITERATION_ORDER
            if k not in ("url", "testing_result", "bottlenecks", "recommendation")
        ]
        for it in its:
            iid = it.get("iteration_id", "")
            iurl = it.get("url", "")
            ts = tests_by_iter.get(iid, [])
            ititle = (
                f'<a href="{_esc(iurl)}" target="_blank" rel="noopener">Итерация {_esc(iid)}</a>'
                if iurl else f'Итерация {_esc(iid)}'
            )
            iter_blocks.append(
                f'<div class="card sub" id="iter-{_esc(iid)}"><h4>{ititle}</h4>'
                f'{_horizontal_table(it, iter_h_order)}'
                f'{_field_table(it, ["testing_result", "bottlenecks", "recommendation"])}'
                f'<h5>Тесты ({len(ts)})</h5>'
                f'{_data_table(ts, TEST_ORDER, "test_id", link_col="number")}'
                f"</div>"
            )
        iter_html = "".join(iter_blocks) if iter_blocks else '<p class="empty">Нет итераций</p>'
        title = f'<a href="{_esc(gurl)}" target="_blank" rel="noopener">{_esc(gname)}</a>' if gurl else _esc(gname)
        preview_link = (
            f'<a class="preview-link" href="{_esc(gpreview)}" target="_blank" rel="noopener">Превью результата</a>'
            if gpreview else ""
        )
        gost_sections.append(
            f'<div class="card" id="gost-{_esc(gid)}"><h3>ГОСТ {title} {preview_link}</h3>'
            f'{_above_fields(g, GOST_ABOVE_FIELDS)}'
            f'{_horizontal_table(g, gost_h_order)}'
            f'{_field_table(g, ["testing_result", "bottlenecks", "recommendation"])}'
            f'<h4>Итерации ({len(its)})</h4>'
            f"{iter_html}"
            f"</div>"
        )

    # Секция задач
    task_sections = []
    task_h_order = [k for k in TASK_ORDER if k not in ("url",) + tuple(TASK_TEXT_FIELDS)]
    for t in tasks:
        tid = t.get("task_id", "")
        tname = t.get("name", tid)
        turl = t.get("url", "")
        lks = links_by_task.get(tid, [])
        title = (
            f'<a href="{_esc(turl)}" target="_blank" rel="noopener">{_esc(tname)}</a>'
            if turl else _esc(tname)
        )
        pid = t.get("project_id", "")
        proj = projects_by_id.get(pid)
        if proj and proj.get("url"):
            project_link = (
                f'<a class="preview-link" href="{_esc(proj["url"])}" target="_blank" rel="noopener">'
                f'Проект {_esc(proj.get("name", pid))}</a>'
            )
        elif pid:
            project_link = f'<span class="preview-link">Проект {_esc(pid)}</span>'
        else:
            project_link = ""
        task_sections.append(
            f'<div class="card"><h3>Задача {title} {project_link}</h3>'
            f'{_horizontal_table(t, task_h_order)}'
            f'{_field_table(t, TASK_TEXT_FIELDS)}'
            f'<h4>Ссылки задач ({len(lks)})</h4>'
            f'{_data_table(lks, LINK_ORDER, "link_id")}'
            f"</div>"
        )

    # Секция проектов
    project_text_fields = ["project_name_shrt", "project_name_full", "project_description"]
    project_sections = []
    for p in projects:
        pid = p.get("project_id", "")
        pname = p.get("name", pid)
        purl = p.get("url", "")
        title = (
            f'<a href="{_esc(purl)}" target="_blank" rel="noopener">{_esc(pname)}</a>'
            if purl else _esc(pname)
        )
        p_order = [
            k for k in p
            if k not in ("project_id", "name", "url", "project_url", *project_text_fields)
        ]
        project_sections.append(
            f'<div class="card" id="project-{_esc(pid)}"><h3>Проект {title}</h3>'
            f'{_horizontal_table(p, p_order, url_fields={"gitlab_url", "wiki_url"})}'
            f'{_field_table(p, project_text_fields)}'
            f"</div>"
        )

    # Секция списка тестов (changelist)
    test_list_section = ""
    test_list_title = ""
    if test_list:
        test_list_order = ["test_id", "iteration_id", "gost_id"]
        for k in test_list[0]:
            if k not in test_list_order and k not in ("url", "engineer_id"):
                test_list_order.append(k)
        test_list_section = _data_table(
            test_list, test_list_order, "test_id", link_col="test_id"
        )

        # Период из дат тестов (для заголовка и ссылки на changelist)
        start_dates = [_date_only(r.get("start_date", "")) for r in test_list]
        start_dates = [d for d in start_dates if d]
        end_dates = [_date_only(r.get("end_date", "")) for r in test_list]
        end_dates = [d for d in end_dates if d]
        period_from = min(start_dates) if start_dates else ""
        period_to = max(end_dates) if end_dates else (max(start_dates) if start_dates else "")
        period_label = f"с {period_from} по {period_to}" if period_from and period_to else ""
        engineer_id = test_list[0].get("engineer_id", "") if test_list else ""
        changelist_url = (
            f"{config.BASE_URL}/admin/autoreport/test/"
            f"?all=&engineer__id__exact={engineer_id}"
            f"&period_from={period_from}&period_to={period_to}&q="
        )
        test_list_title = (
            f'Список тестов {_esc(period_label)} '
            f'<span class="count">({len(test_list)})</span>'
            f'<a class="preview-link" href="{_esc(changelist_url)}" '
            f'target="_blank" rel="noopener">Список на портале</a>'
        )
    else:
        test_list_title = "Список тестов"

    checks_html = _checks_section(checks)

    # Панель навигации: разделы + подразделы ГОСТов по итерациям
    sidebar_items = []
    if checks_html:
        sidebar_items.append('<a href="#checks">Проверки</a>')
    sidebar_items.append('<a href="#gosts">ГОСТ отчеты</a>')
    for g in gosts:
        gid = g.get("gost_id", "")
        gname = g.get("name", gid)
        sidebar_items.append(f'<a class="sub-link" href="#gost-{_esc(gid)}">ГОСТ {_esc(gname)}</a>')
        for it in iters_by_gost.get(gid, []):
            iid = it.get("iteration_id", "")
            sidebar_items.append(f'<a class="sub-link2" href="#iter-{_esc(iid)}">Итерация {_esc(iid)}</a>')
    sidebar_items.append('<a href="#tasks">Задачи</a>')
    sidebar_items.append('<a href="#projects">Проекты</a>')
    if test_list:
        sidebar_items.append('<a href="#test_list">Список тестов</a>')
    sidebar_html = "".join(sidebar_items)

    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    dir_name = os.path.basename(run_dir)

    html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Отчёт: {_esc(dir_name)}</title>
<style>
:root {{
  --bg: #f4f6fb;
  --card: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --muted: #64748b;
  --accent: #2563eb;
  --accent-soft: #eff6ff;
  --green: #16a34a;
  --red: #dc2626;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5; padding: 20px;
}}
.container {{ max-width: 1700px; margin: 0 auto; }}
.layout {{ display: flex; gap: 20px; align-items: flex-start; }}
.sidebar {{
  position: sticky;
  top: 20px;
  width: 200px;
  flex-shrink: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}}
.sidebar-title {{ font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }}
.sidebar a {{
  display: block;
  padding: 6px 10px;
  margin-bottom: 2px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text);
}}
.sidebar a:hover {{ background: var(--accent-soft); color: var(--accent); text-decoration: none; }}
.sidebar a.sub-link {{ padding-left: 20px; font-size: 12.5px; color: var(--muted); }}
.sidebar a.sub-link2 {{ padding-left: 34px; font-size: 12px; color: var(--muted); }}
.content {{ flex: 1; min-width: 0; }}
h1 {{ font-size: 26px; margin-bottom: 4px; }}
h2 {{ font-size: 20px; margin: 28px 0 12px; color: var(--accent); border-bottom: 2px solid var(--border); padding-bottom: 6px; }}
h3 {{ font-size: 17px; margin-bottom: 10px; }}
h4 {{ font-size: 15px; margin: 14px 0 8px; color: var(--muted); }}
h5 {{ font-size: 14px; margin: 12px 0 6px; color: var(--muted); }}
.preview-link {{ display: inline-block; margin-left: 10px; padding: 2px 10px; font-size: 12px; font-weight: 600; background: var(--accent-soft); border: 1px solid #dbeafe; border-radius: 20px; color: var(--accent); vertical-align: middle; }}
.preview-link:hover {{ background: #dbeafe; text-decoration: none; }}
.count {{ color: var(--muted); font-weight: 600; }}
.above-fields {{ display: flex; flex-wrap: wrap; gap: 6px 20px; margin-bottom: 10px; padding: 8px 10px; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; font-size: 12.5px; }}
.af-item {{ white-space: nowrap; }}
.af-label {{ color: var(--muted); font-weight: 600; }}
.nc {{ color: var(--muted); font-style: italic; }}
.subtitle {{ color: var(--muted); margin-bottom: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: center; }}
.stat-icon {{ font-size: 24px; }}
.stat-value {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: 13px; color: var(--muted); }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }}
.card.sub {{ background: var(--accent-soft); border-color: #dbeafe; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.fields {{ margin-bottom: 8px; }}
table.fields th {{ text-align: left; width: 200px; color: var(--muted); font-weight: 600; padding: 3px 8px 3px 0; vertical-align: top; }}
table.fields td {{ padding: 3px 0; word-break: break-word; }}
table.hfields {{ margin-bottom: 8px; table-layout: fixed; }}
table.hfields th {{ background: #f1f5f9; text-align: left; padding: 4px 6px; font-size: 11px; color: var(--muted); font-weight: 600; white-space: normal; word-break: break-word; overflow-wrap: anywhere; }}
.has-tip {{ position: relative; cursor: help; }}
.has-tip::after {{
  content: attr(data-tip);
  position: absolute;
  left: 0;
  bottom: 100%;
  margin-bottom: 6px;
  z-index: 20;
  display: none;
  width: max-content;
  max-width: 220px;
  padding: 5px 8px;
  background: #1e293b;
  color: #fff;
  font-size: 11px;
  font-weight: 400;
  line-height: 1.35;
  border-radius: 5px;
  box-shadow: 0 3px 8px rgba(0,0,0,.2);
  white-space: normal;
  word-break: break-word;
}}
.has-tip:hover::after {{ display: block; }}
.info-icon {{ margin-right: 8px; font-size: 15px; vertical-align: -2px; }}
table.hfields td {{ padding: 4px 6px; border-top: 1px solid var(--border); vertical-align: top; word-break: break-word; overflow-wrap: anywhere; font-size: 12px; }}
table.hfields td a {{ word-break: break-all; }}
table.data {{ margin-top: 6px; table-layout: fixed; }}
table.data th {{ background: #f1f5f9; text-align: left; padding: 4px 6px; font-size: 11.5px; color: var(--muted); white-space: normal; word-break: break-word; overflow-wrap: anywhere; }}
table.data td {{ padding: 4px 6px; border-top: 1px solid var(--border); vertical-align: top; word-break: break-word; overflow-wrap: anywhere; font-size: 12px; }}
table.data td a {{ word-break: break-all; }}
table.data th.wide, table.data td.wide {{ width: 30%; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.multiline {{ white-space: pre-wrap; }}
.empty {{ color: var(--muted); font-style: italic; }}
.checks-total {{ font-size: 14px; font-weight: 600; margin-bottom: 10px; }}
.checks-summary {{ max-width: 500px; margin-bottom: 16px; }}
.checks-summary td.good {{ color: var(--green); font-weight: 700; }}
.checks-summary td.bad {{ color: var(--red); font-weight: 700; }}
.checks-total .good {{ color: var(--green); }}
.checks-total .bad {{ color: var(--red); }}
.checks-toolbar {{ margin-bottom: 10px; }}
.btn-check {{
  padding: 6px 14px;
  margin-right: 8px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--card);
  color: var(--muted);
  cursor: pointer;
}}
.btn-check:hover {{ border-color: var(--accent); color: var(--accent); }}
.btn-check.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.checks-table tbody tr.row-fail {{ background: #fef2f2; }}
.checks-table tbody tr.row-fail td {{ border-top: 1px solid #fecaca; }}
.checks-table td.status-cell {{ font-weight: 700; }}
.checks-table td.status-cell:first-letter {{ text-transform: uppercase; }}
.checks-table tbody tr.row-fail td.status-cell {{ color: var(--red); }}
.checks-table tbody tr.row-ok td.status-cell {{ color: var(--green); }}
.footer {{ margin-top: 30px; color: var(--muted); font-size: 12.5px; text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <h1>Отчёт по ГОСТ отчетам</h1>
  <div class="subtitle">Папка: {_esc(dir_name)} · Сформирован: {_esc(now)}</div>
  <div class="stats">{stats}</div>
  <div class="layout">
    <nav class="sidebar">
      <div class="sidebar-title">Разделы</div>
      {sidebar_html}
    </nav>
    <div class="content">
      {checks_html}

      <h2 id="gosts">ГОСТ отчеты
        <a class="preview-link" href="{_esc(_summary_url())}" target="_blank" rel="noopener">Сводка на портале</a>
      </h2>
      {''.join(gost_sections) if gost_sections else '<p class="empty">Нет данных</p>'}

      <h2 id="tasks">Задачи</h2>
      {''.join(task_sections) if task_sections else '<p class="empty">Нет данных</p>'}

      <h2 id="projects">Проекты</h2>
      {''.join(project_sections) if project_sections else '<p class="empty">Нет данных</p>'}

      <h2 id="test_list">{test_list_title}</h2>
      {test_list_section if test_list_section else '<p class="empty">Нет данных</p>'}

      <div class="footer">Сформировано автоматически скриптом GOST Checker</div>
    </div>
  </div>
</div>
</body>
</html>"""

    out_path = os.path.join(run_dir, "report.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return out_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python report.py <папка_запуска>")
        sys.exit(1)
    path = build_report(sys.argv[1])
    print(f"Отчёт сохранён: {path}")
