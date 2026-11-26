"""Проверка собранных в CSV параметров по правилам из checks_config.json.

Читает CSV-файлы папки запуска, применяет правила из конфига и пишет
checks.csv (utf-8-sig) с результатами каждой проверки.

Типы проверок:
  eq            — равенство значению (value)
  not_empty     — поле не пустое
  in            — значение в списке допустимых (values)
  range         — числовой диапазон (min/max)
  regex         — совпадение с шаблоном (pattern)
  date_range    — дата в интервале (from/to, ISO YYYY-MM-DD)
  count_max     — агрегатная: количество строк в каждой группе по полю ≤ max
  all_not_empty — все поля строки заполнены (кроме id-поля и url)
  name          — значение — фамилия и имя (2+ кириллических слова)
  link_type_count — агрегатная: у каждой задачи ровно count ссылок каждого
                    типа из types (например, methodology/report/artifacts по 2)
  test_belongs   — тест из test_list относится к одному из ГОСТов и одной
                    из итераций (iteration_id/gost_id существуют в данных)

Пустое значение поля = нарушение (fail) для всех типов.
"""

import csv
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime

logger = logging.getLogger("gost_checker")

# Имя конфига с правилами (в корне проекта)
CONFIG_PATH = "checks_config.json"

# Маппинг сущность (имя CSV без расширения) → id-поле строки
ENTITY_ID_FIELDS = {
    "gosts": "gost_id",
    "iterations": "iteration_id",
    "tests": "test_id",
    "test_list": "test_id",
    "tasks": "task_id",
    "task_links": "link_id",
    "projects": "project_id",
}

# Колонки checks.csv
CHECK_FIELDS = [
    "entity", "entity_id", "field", "check_type",
    "expected", "actual", "status", "message", "description",
]

# Форматы дат, которые пробуем при разборе значений из CSV
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d.%m.%Y",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
]


def _is_empty(value: str) -> bool:
    """Пустое значение: None или строка без значимых символов."""
    return value is None or str(value).strip() == ""


def _parse_date(value: str) -> datetime | None:
    """Пробует распарсить дату из CSV по известным форматам."""
    value = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _check_rule(rule: dict, actual: str) -> tuple[bool, str]:
    """Выполняет одно правило. Возвращает (ok, message)."""
    check_type = rule.get("type", "")
    expected = ""

    if _is_empty(actual):
        return False, "значение пустое"

    if check_type == "eq":
        expected = str(rule.get("value", ""))
        return actual == expected, f"ожидалось: {expected}"

    if check_type == "not_empty":
        return True, "поле заполнено"

    if check_type == "in":
        values = [str(v) for v in rule.get("values", [])]
        expected = ", ".join(values)
        return actual in values, f"ожидалось одно из: {expected}"

    if check_type == "range":
        try:
            num = float(actual)
        except ValueError:
            return False, f"не число: {actual}"
        lo = rule.get("min")
        hi = rule.get("max")
        expected = f"[{lo}, {hi}]"
        if lo is not None and num < float(lo):
            return False, f"{actual} < min {lo}"
        if hi is not None and num > float(hi):
            return False, f"{actual} > max {hi}"
        return True, f"в диапазоне {expected}"

    if check_type == "regex":
        pattern = rule.get("pattern", "")
        expected = pattern
        try:
            return re.search(pattern, actual) is not None, f"шаблон: {pattern}"
        except re.error as exc:
            return False, f"ошибка шаблона: {exc}"

    if check_type == "date_range":
        from_str = rule.get("from")
        to_str = rule.get("to")
        expected = f"[{from_str}, {to_str}]"
        dt = _parse_date(actual)
        if dt is None:
            return False, f"не дата: {actual}"
        if from_str:
            from_dt = _parse_date(from_str)
            if from_dt is None:
                return False, f"неверный from в конфиге: {from_str}"
            if dt < from_dt:
                return False, f"{actual} < from {from_str}"
        if to_str:
            to_dt = _parse_date(to_str)
            if to_dt is None:
                return False, f"неверный to в конфиге: {to_str}"
            if dt > to_dt:
                return False, f"{actual} > to {to_str}"
        return True, f"в интервале {expected}"

    if check_type == "name":
        pattern = r"^[А-ЯЁ][а-яё]+(?: [А-ЯЁ][а-яё]+)+$"
        return (
            re.fullmatch(pattern, actual.strip()) is not None,
            "ожидалось: фамилия и имя",
        )

    return False, f"неизвестный тип проверки: {check_type}"


def _check_count_max(entity: str, rows: list[dict], rule: dict) -> list[dict]:
    """Агрегатная проверка: количество строк в каждой группе по полю ≤ max.

    Одна строка результата на группу. entity_id = значение группы.
    """
    field = rule.get("field", "")
    max_count = rule.get("max")
    results: list[dict] = []

    if field not in rows[0]:
        results.append({
            "entity": entity,
            "entity_id": "",
            "field": field,
            "check_type": "count_max",
            "expected": f"≤ {max_count}",
            "actual": "",
            "status": "fail",
            "message": f"поле {field} отсутствует в данных",
        })
        return results

    counts = Counter(row.get(field, "") for row in rows)
    for value, count in counts.items():
        if _is_empty(value):
            results.append({
                "entity": entity,
                "entity_id": value,
                "field": field,
                "check_type": "count_max",
                "expected": f"≤ {max_count}",
                "actual": str(count),
                "status": "fail",
                "message": "значение пустое",
            })
            continue
        ok = max_count is None or count <= int(max_count)
        results.append({
            "entity": entity,
            "entity_id": value,
            "field": field,
            "check_type": "count_max",
            "expected": f"≤ {max_count}",
            "actual": str(count),
            "status": "ok" if ok else "fail",
            "message": (
                f"ГОСТов {count} ≤ {max_count}" if ok
                else f"ГОСТов {count} > max {max_count}"
            ),
        })
    return results


def _check_link_type_count(
    entity: str, rows: list[dict], rule: dict,
) -> list[dict]:
    """Проверка: у каждой задачи ровно count ссылок каждого типа из types.

    Группирует строки по task_id, для каждого типа считает количество ссылок
    с таким link_type и сравнивает с ожидаемым count.
    Одна строка результата на (task_id, тип ссылки).
    """
    types = [str(t) for t in rule.get("types", [])]
    expected = rule.get("count")
    results: list[dict] = []

    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(row.get("task_id", ""), []).append(row)

    for task_id, task_rows in by_task.items():
        for link_type in types:
            count = sum(
                1 for r in task_rows
                if str(r.get("link_type", "")).strip() == link_type
            )
            ok = expected is None or count == int(expected)
            results.append({
                "entity": entity,
                "entity_id": task_id,
                "field": "link_type",
                "check_type": "link_type_count",
                "expected": f"{link_type} = {expected}",
                "actual": str(count),
                "status": "ok" if ok else "fail",
                "message": (
                    f"ссылок {link_type}: {count} = {expected}" if ok
                    else f"ссылок {link_type}: {count} ≠ {expected}"
                ),
            })
    return results


def _check_all_not_empty(
    entity: str, rows: list[dict], rule: dict, id_field: str
) -> list[dict]:
    """Проверка: все поля строки заполнены (кроме id-поля и url).

    Одна строка результата на строку данных. field = "all",
    actual = список пустых полей.
    """
    results: list[dict] = []
    for row in rows:
        entity_id = row.get(id_field, "")
        empty_fields = [
            key for key, value in row.items()
            if key not in (id_field, "url") and _is_empty(value)
        ]
        ok = not empty_fields
        results.append({
            "entity": entity,
            "entity_id": entity_id,
            "field": "all",
            "check_type": "all_not_empty",
            "expected": "все поля заполнены",
            "actual": ", ".join(empty_fields) if empty_fields else "все заполнены",
            "status": "ok" if ok else "fail",
            "message": (
                "все поля заполнены" if ok
                else f"пустые поля: {', '.join(empty_fields)}"
            ),
        })
    return results


def _dates_equal(a: str, b: str) -> bool:
    """Сравнение дат: только дата (время отбрасывается), если обе парсятся,
    иначе строково."""
    da, db = _parse_date(a), _parse_date(b)
    if da is not None and db is not None:
        return da.date() == db.date()
    return str(a).strip() == str(b).strip()


def _check_has_tests(
    entity: str, rows: list[dict], rule: dict, id_field: str,
    tests_by_iter: dict[str, list[dict]],
) -> list[dict]:
    """Проверка: у итерации есть 1 и более тестов."""
    results: list[dict] = []
    for row in rows:
        iid = row.get(id_field, "")
        count = len(tests_by_iter.get(iid, []))
        ok = count >= 1
        results.append({
            "entity": entity,
            "entity_id": iid,
            "field": "test_count",
            "check_type": "has_tests",
            "expected": "≥ 1 тест",
            "actual": str(count),
            "status": "ok" if ok else "fail",
            "message": f"тестов {count} ≥ 1" if ok else f"тестов {count} < 1",
        })
    return results


def _check_test_dates_match(
    entity: str, rows: list[dict], rule: dict, id_field: str,
    tests_by_iter: dict[str, list[dict]],
) -> list[dict]:
    """Проверка: first_test_date/last_test_date совпадают с фактическими
    датами тестов итерации (min start_date / max end_date)."""
    results: list[dict] = []
    for row in rows:
        iid = row.get(id_field, "")
        tests = tests_by_iter.get(iid, [])
        if not tests:
            results.append({
                "entity": entity,
                "entity_id": iid,
                "field": "first_test_date",
                "check_type": "test_dates_match",
                "expected": "min start_date / max end_date",
                "actual": "",
                "status": "fail",
                "message": "нет тестов для сравнения дат",
            })
            continue
        start_dates = [t.get("start_date", "") for t in tests if t.get("start_date")]
        end_dates = [t.get("end_date", "") for t in tests if t.get("end_date")]
        if not start_dates or not end_dates:
            results.append({
                "entity": entity,
                "entity_id": iid,
                "field": "first_test_date",
                "check_type": "test_dates_match",
                "expected": "min start_date / max end_date",
                "actual": "",
                "status": "fail",
                "message": "у тестов нет start_date/end_date",
            })
            continue
        first = min(start_dates, key=lambda d: _parse_date(d) or datetime.max)
        last = max(end_dates, key=lambda d: _parse_date(d) or datetime.min)
        actual_first = row.get("first_test_date", "")
        actual_last = row.get("last_test_date", "")
        ok = _dates_equal(actual_first, first) and _dates_equal(actual_last, last)
        results.append({
            "entity": entity,
            "entity_id": iid,
            "field": "first_test_date",
            "check_type": "test_dates_match",
            "expected": f"{first} / {last}",
            "actual": f"{actual_first} / {actual_last}",
            "status": "ok" if ok else "fail",
            "message": (
                "даты совпадают" if ok
                else f"ожидалось {first} / {last}, фактически {actual_first} / {actual_last}"
            ),
        })
    return results


def _check_test_count_max(
    entity: str, rows: list[dict], rule: dict, id_field: str,
    tests_by_iter: dict[str, list[dict]],
) -> list[dict]:
    """Проверка: в итерации не более max тестов."""
    max_count = rule.get("max")
    results: list[dict] = []
    for row in rows:
        iid = row.get(id_field, "")
        count = len(tests_by_iter.get(iid, []))
        ok = max_count is None or count <= int(max_count)
        results.append({
            "entity": entity,
            "entity_id": iid,
            "field": "test_count",
            "check_type": "test_count_max",
            "expected": f"≤ {max_count}",
            "actual": str(count),
            "status": "ok" if ok else "fail",
            "message": (
                f"тестов {count} ≤ {max_count}" if ok
                else f"тестов {count} > max {max_count}"
            ),
        })
    return results


def _check_or_min(
    entity: str, rows: list[dict], rule: dict, id_field: str,
) -> list[dict]:
    """Проверка: хотя бы одно из полей > min (по умолчанию 0)."""
    fields = rule.get("fields", [])
    min_value = rule.get("min", 0)
    results: list[dict] = []
    for row in rows:
        iid = row.get(id_field, "")
        values = []
        for f in fields:
            raw = row.get(f, "")
            try:
                values.append(float(raw) if not _is_empty(raw) else None)
            except ValueError:
                values.append(None)
        ok = any(v is not None and v > float(min_value) for v in values)
        actual = ", ".join(f"{f}={row.get(f, '')}" for f in fields)
        results.append({
            "entity": entity,
            "entity_id": iid,
            "field": ", ".join(fields),
            "check_type": "or_min",
            "expected": f"хотя бы одно > {min_value}",
            "actual": actual,
            "status": "ok" if ok else "fail",
            "message": (
                "условие выполнено" if ok
                else f"ни одно из полей не > {min_value}: {actual}"
            ),
        })
    return results


def _check_has_iterations(
    entity: str, rows: list[dict], rule: dict, id_field: str,
    iters_by_gost: dict[str, list[dict]],
) -> list[dict]:
    """Проверка: у ГОСТа есть 1 и более итераций."""
    results: list[dict] = []
    for row in rows:
        gid = row.get(id_field, "")
        count = len(iters_by_gost.get(gid, []))
        ok = count >= 1
        results.append({
            "entity": entity,
            "entity_id": gid,
            "field": "iteration_count",
            "check_type": "has_iterations",
            "expected": "≥ 1 итерация",
            "actual": str(count),
            "status": "ok" if ok else "fail",
            "message": f"итераций {count} ≥ 1" if ok else f"итераций {count} < 1",
        })
    return results


def _check_gost_dates_match(
    entity: str, rows: list[dict], rule: dict, id_field: str,
    iters_by_gost: dict[str, list[dict]],
) -> list[dict]:
    """Проверка: start_actual_date/end_actual_date ГОСТа совпадают с
    начальной и конечной датами итераций (min first_test_date /
    max last_test_date)."""
    results: list[dict] = []
    for row in rows:
        gid = row.get(id_field, "")
        iters = iters_by_gost.get(gid, [])
        if not iters:
            results.append({
                "entity": entity,
                "entity_id": gid,
                "field": "start_actual_date",
                "check_type": "gost_dates_match",
                "expected": "min first_test_date / max last_test_date",
                "actual": "",
                "status": "fail",
                "message": "нет итераций для сравнения дат",
            })
            continue
        first_dates = [it.get("first_test_date", "") for it in iters if it.get("first_test_date")]
        last_dates = [it.get("last_test_date", "") for it in iters if it.get("last_test_date")]
        if not first_dates or not last_dates:
            results.append({
                "entity": entity,
                "entity_id": gid,
                "field": "start_actual_date",
                "check_type": "gost_dates_match",
                "expected": "min first_test_date / max last_test_date",
                "actual": "",
                "status": "fail",
                "message": "у итераций нет first_test_date/last_test_date",
            })
            continue
        first = min(first_dates, key=lambda d: _parse_date(d) or datetime.max)
        last = max(last_dates, key=lambda d: _parse_date(d) or datetime.min)
        actual_first = row.get("start_actual_date", "")
        actual_last = row.get("end_actual_date", "")
        ok = _dates_equal(actual_first, first) and _dates_equal(actual_last, last)
        results.append({
            "entity": entity,
            "entity_id": gid,
            "field": "start_actual_date",
            "check_type": "gost_dates_match",
            "expected": f"{first} / {last}",
            "actual": f"{actual_first} / {actual_last}",
            "status": "ok" if ok else "fail",
            "message": (
                "даты совпадают" if ok
                else f"ожидалось {first} / {last}, фактически {actual_first} / {actual_last}"
            ),
        })
    return results


def _load_config() -> dict | None:
    """Читает конфиг правил. Нет файла/ошибка → None."""
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Конфиг проверок %s не найден — проверки пропущены", CONFIG_PATH)
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Ошибка чтения конфига проверок %s: %s — проверки пропущены", CONFIG_PATH, exc)
        return None
    if not isinstance(data, dict) or not data:
        logger.warning("Конфиг проверок %s пуст — проверки пропущены", CONFIG_PATH)
        return None
    return data


def _load_csv(path: str) -> list[dict]:
    """Чтение CSV (utf-8-sig) в список словарей."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _add_desc(results: list[dict], rule: dict) -> list[dict]:
    """Проставляет description правила в каждую запись результата."""
    desc = rule.get("description", "")
    for r in results:
        r["description"] = desc
    return results


def run(run_dir: str) -> str | None:
    """Запускает проверки для папки запуска. Пишет checks.csv.

    Возвращает путь к checks.csv или None, если проверки не выполнялись.
    """
    config = _load_config()
    if config is None:
        return None

    results: list[dict] = []

    for entity, rules in config.items():
        if entity not in ENTITY_ID_FIELDS:
            logger.warning("Неизвестная сущность в конфиге: %s — пропущена", entity)
            continue
        if not isinstance(rules, list) or not rules:
            continue

        id_field = ENTITY_ID_FIELDS[entity]
        rows = _load_csv(os.path.join(run_dir, f"{entity}.csv"))
        if not rows:
            logger.warning("Нет данных для проверки: %s.csv", entity)
            continue

        # Тесты итераций (для межтабличных проверок iterations)
        tests_by_iter: dict[str, list[dict]] = {}
        if entity == "iterations":
            for t in _load_csv(os.path.join(run_dir, "tests.csv")):
                tests_by_iter.setdefault(t.get("iteration_id", ""), []).append(t)

        # Итерации ГОСТов (для межтабличных проверок gosts)
        iters_by_gost: dict[str, list[dict]] = {}
        if entity == "gosts":
            for it in _load_csv(os.path.join(run_dir, "iterations.csv")):
                iters_by_gost.setdefault(it.get("gost_id", ""), []).append(it)

        for rule in rules:
            if rule.get("type") == "count_max":
                results.extend(_add_desc(_check_count_max(entity, rows, rule), rule))
                continue
            if rule.get("type") == "link_type_count":
                results.extend(_add_desc(_check_link_type_count(entity, rows, rule), rule))
                continue
            if rule.get("type") == "all_not_empty":
                results.extend(_add_desc(_check_all_not_empty(entity, rows, rule, id_field), rule))
                continue
            if rule.get("type") == "has_tests":
                results.extend(_add_desc(_check_has_tests(entity, rows, rule, id_field, tests_by_iter), rule))
                continue
            if rule.get("type") == "test_dates_match":
                results.extend(_add_desc(_check_test_dates_match(entity, rows, rule, id_field, tests_by_iter), rule))
                continue
            if rule.get("type") == "test_count_max":
                results.extend(_add_desc(_check_test_count_max(entity, rows, rule, id_field, tests_by_iter), rule))
                continue
            if rule.get("type") == "or_min":
                results.extend(_add_desc(_check_or_min(entity, rows, rule, id_field), rule))
                continue
            if rule.get("type") == "has_iterations":
                results.extend(_add_desc(_check_has_iterations(entity, rows, rule, id_field, iters_by_gost), rule))
                continue
            if rule.get("type") == "gost_dates_match":
                results.extend(_add_desc(_check_gost_dates_match(entity, rows, rule, id_field, iters_by_gost), rule))
                continue
            for row in rows:
                entity_id = row.get(id_field, "")
                field = rule.get("field", "")
                if field not in row:
                    results.append({
                        "entity": entity,
                        "entity_id": entity_id,
                        "field": field,
                        "check_type": rule.get("type", ""),
                        "expected": "",
                        "actual": "",
                        "status": "fail",
                        "message": f"поле {field} отсутствует в данных",
                        "description": rule.get("description", ""),
                    })
                    continue
                actual = row.get(field, "")
                ok, message = _check_rule(rule, actual)
                results.append({
                    "entity": entity,
                    "entity_id": entity_id,
                    "field": field,
                    "check_type": rule.get("type", ""),
                    "expected": _expected_str(rule),
                    "actual": actual,
                    "status": "ok" if ok else "fail",
                    "message": message,
                    "description": rule.get("description", ""),
                })

    if not results:
        logger.warning("Проверки не дали результатов (нет правил/данных)")
        return None

    out_path = os.path.join(run_dir, "checks.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CHECK_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    fails = sum(1 for r in results if r["status"] == "fail")
    logger.info("Проверки: всего %d, нарушений %d → %s", len(results), fails, out_path)
    return out_path


def _expected_str(rule: dict) -> str:
    """Человекочитаемое ожидаемое значение для checks.csv."""
    check_type = rule.get("type", "")
    if check_type == "eq":
        return str(rule.get("value", ""))
    if check_type == "in":
        return ", ".join(str(v) for v in rule.get("values", []))
    if check_type == "range":
        return f"[{rule.get('min')}, {rule.get('max')}]"
    if check_type == "regex":
        return rule.get("pattern", "")
    if check_type == "date_range":
        return f"[{rule.get('from')}, {rule.get('to')}]"
    if check_type == "count_max":
        return f"≤ {rule.get('max')}"
    if check_type == "link_type_count":
        return f"{', '.join(str(t) for t in rule.get('types', []))} = {rule.get('count')}"
    if check_type == "name":
        return "фамилия и имя"
    return ""


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    if len(sys.argv) < 2:
        print("Использование: python checks.py <папка_запуска>")
        sys.exit(1)
    path = run(sys.argv[1])
    print(f"Результаты проверок: {path}" if path else "Проверки не выполнялись")
