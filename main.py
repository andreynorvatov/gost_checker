"""Оркестрация обхода: summary → ГОСТ → итерация → тест + задача.

Каждый запуск создаёт новую папку {alias}_{quarter}_{timestamp} с 5 CSV:
gosts.csv, iterations.csv, tests.csv, tasks.csv, task_links.csv,
и HTML-отчётом report.html.
"""

import logging
import os
import sys
from datetime import datetime
from urllib.parse import urlencode

import checks
import config
import parsers
import report
import storage
from http_client import HttpClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gost_checker")


def build_summary_url() -> str:
    """URL summary с параметрами фильтра."""
    query = urlencode(config.QUERY_PARAMS)
    return f"{config.BASE_URL}/gost/summary/?{query}"


def main() -> int:
    client = HttpClient()
    errors = []

    # Папка запуска
    run_dir = storage.create_run_dir(
        config.QUERY_PARAMS["alias"], config.QUERY_PARAMS["quarter"]
    )
    logger.info("Папка запуска: %s", run_dir)

    gost_writer = storage.CsvWriter(
        os.path.join(run_dir, "gosts.csv"), storage.GOST_FIELDS
    )
    iter_writer = storage.CsvWriter(
        os.path.join(run_dir, "iterations.csv"), storage.ITERATION_FIELDS
    )
    test_writer = storage.CsvWriter(
        os.path.join(run_dir, "tests.csv"), storage.TEST_FIELDS
    )
    task_writer = storage.CsvWriter(
        os.path.join(run_dir, "tasks.csv"), storage.TASK_FIELDS
    )
    task_link_writer = storage.CsvWriter(
        os.path.join(run_dir, "task_links.csv"), storage.TASK_LINK_FIELDS
    )

    task_ids: set[str] = set()
    project_ids: set[str] = set()
    project_writer = None

    # Метаданные тестов для построения test_list.csv (changelist)
    iter_gost: dict[str, str] = {}   # iteration_id -> gost_id
    test_meta: dict[str, dict] = {}  # test_id -> {iteration_id, gost_id, engineer_id, start_date, end_date}

    try:
        # 1. Summary
        summary_url = build_summary_url()
        logger.info("Запрос summary: %s", summary_url)
        try:
            summary_html = client.get_html(summary_url)
            gosts = parsers.parse_summary(summary_html)
        except Exception as exc:
            logger.error("Не удалось получить summary: %s", exc)
            errors.append(f"summary: {exc}")
            gosts = []
        logger.info("Найдено ГОСТ отчетов: %d", len(gosts))

        # 2. ГОСТы
        for gost in gosts:
            logger.info("ГОСТ %s: %s", gost["gost_id"], gost["name"])

            try:
                gost_html = client.get_html(gost["url"])
                gost_data, iterations = parsers.parse_gost(gost_html, gost["url"])
            except Exception as exc:
                logger.error("Ошибка ГОСТ %s: %s", gost["gost_id"], exc)
                errors.append(f"gost {gost['gost_id']}: {exc}")
                gost_writer.write(gost)  # summary-версия
                continue

            # Обновляем поля ГОСТа данными со страницы и пишем один раз
            for key, value in gost_data.items():
                if key not in ("gost_id", "name", "url"):
                    gost[key] = value
            gost_writer.write(gost)

            # 3. Итерации
            for iteration in iterations:
                logger.info(
                    "  Итерация %s (ГОСТ %s)", iteration["iteration_id"], gost["gost_id"]
                )

                try:
                    iter_html = client.get_html(iteration["url"])
                    iter_data, tests = parsers.parse_iteration(iter_html, iteration["url"])
                except Exception as exc:
                    logger.error(
                        "Ошибка итерации %s: %s", iteration["iteration_id"], exc
                    )
                    errors.append(f"iteration {iteration['iteration_id']}: {exc}")
                    iter_writer.write(iteration)  # inline-версия
                    continue

                for key, value in iter_data.items():
                    if key not in ("iteration_id", "gost_id", "url"):
                        iteration[key] = value
                iter_writer.write(iteration)
                iter_gost[iteration["iteration_id"]] = gost["gost_id"]

                if iteration.get("task_id"):
                    task_ids.add(iteration["task_id"])

                # 4. Тесты
                for test in tests:
                    try:
                        test_html = client.get_html(test["url"])
                        extra = parsers.parse_test(test_html, test["url"])
                    except Exception as exc:
                        logger.error("Ошибка теста %s: %s", test["test_id"], exc)
                        errors.append(f"test {test['test_id']}: {exc}")
                        extra = {}

                    for key, value in extra.items():
                        if key not in ("test_id", "url"):
                            test[key] = value
                    test_writer.write(test)

                    # Метаданные для test_list.csv
                    test_meta[test["test_id"]] = {
                        "iteration_id": test.get("iteration_id", ""),
                        "gost_id": iter_gost.get(test.get("iteration_id", ""), ""),
                        "engineer_id": test.get("engineer_id", ""),
                        "start_date": test.get("start_date", ""),
                        "end_date": test.get("end_date", ""),
                    }

        # 5. Задачи (дедупликация по task_id)
        logger.info("Уникальных задач: %d", len(task_ids))
        for task_id in sorted(task_ids):
            task_url = f"{config.BASE_URL}/admin/autoreport/task/{task_id}/change/"
            logger.info("Задача %s", task_id)
            try:
                task_html = client.get_html(task_url)
                task_data, links = parsers.parse_task(task_html, task_url)
            except Exception as exc:
                logger.error("Ошибка задачи %s: %s", task_id, exc)
                errors.append(f"task {task_id}: {exc}")
                continue

            task_writer.write(task_data)
            if task_data.get("project_id"):
                project_ids.add(task_data["project_id"])
            for link in links:
                task_link_writer.write(link)

        # 6. Проекты (дедупликация по project_id)
        logger.info("Уникальных проектов: %d", len(project_ids))
        projects = []
        for project_id in sorted(project_ids):
            project_url = f"{config.BASE_URL}/admin/autoreport/project/{project_id}/change/"
            logger.info("Проект %s", project_id)
            try:
                project_html = client.get_html(project_url)
                project_data = parsers.parse_project(project_html, project_url)
            except Exception as exc:
                logger.error("Ошибка проекта %s: %s", project_id, exc)
                errors.append(f"project {project_id}: {exc}")
                continue
            projects.append(project_data)

        # Поля projects.csv: объединение всех полей (project_id, name, url + остальные)
        project_fields = ["project_id", "name", "url"]
        for p in projects:
            for key in p:
                if key not in project_fields:
                    project_fields.append(key)
        project_writer = storage.CsvWriter(
            os.path.join(run_dir, "projects.csv"), project_fields
        )
        for p in projects:
            project_writer.write(p)

        # 7. Список проведенных тестов из changelist (test_list.csv)
        test_list_writer = None
        try:
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

            start_dates = [_date_only(m["start_date"]) for m in test_meta.values()]
            start_dates = [d for d in start_dates if d]
            end_dates = [_date_only(m["end_date"]) for m in test_meta.values()]
            end_dates = [d for d in end_dates if d]
            engineer_ids = sorted({m["engineer_id"] for m in test_meta.values() if m["engineer_id"]})

            if not engineer_ids or not start_dates:
                logger.warning(
                    "Нет инженеров или дат тестов — test_list.csv будет пустым"
                )
                test_list_writer = storage.CsvWriter(
                    os.path.join(run_dir, "test_list.csv"), storage.TEST_LIST_FIELDS
                )
            else:
                period_from = min(start_dates)
                period_to = max(end_dates) if end_dates else max(start_dates)
                logger.info(
                    "Сбор test_list: инженеров=%d, период %s..%s",
                    len(engineer_ids), period_from, period_to,
                )
                test_list_rows: dict[str, dict] = {}
                for eid in engineer_ids:
                    url = (
                        f"{config.BASE_URL}/admin/autoreport/test/"
                        f"?all=&engineer__id__exact={eid}"
                        f"&period_from={period_from}&period_to={period_to}&q="
                    )
                    try:
                        changelist_html = client.get_html(url)
                        for row in parsers.parse_test_list(changelist_html):
                            test_list_rows[row["test_id"]] = row
                    except Exception as exc:
                        logger.error(
                            "Ошибка changelist тестов (инженер %s): %s", eid, exc
                        )
                        errors.append(f"test_list engineer {eid}: {exc}")

                # Связываем с tests.csv по test_id
                for tid, row in test_list_rows.items():
                    meta = test_meta.get(tid, {})
                    row["iteration_id"] = meta.get("iteration_id", "")
                    row["gost_id"] = meta.get("gost_id", "")
                    row["engineer_id"] = meta.get("engineer_id", "")

                # Поля: test_id, url + все колонки changelist
                test_list_fields = list(storage.TEST_LIST_FIELDS)
                for row in test_list_rows.values():
                    for key in row:
                        if key not in test_list_fields:
                            test_list_fields.append(key)
                test_list_writer = storage.CsvWriter(
                    os.path.join(run_dir, "test_list.csv"), test_list_fields
                )
                for row in test_list_rows.values():
                    test_list_writer.write(row)
                logger.info("Собрано тестов в test_list.csv: %d", len(test_list_rows))
        except Exception as exc:
            logger.error("Ошибка сбора test_list: %s", exc)
            errors.append(f"test_list: {exc}")

    finally:
        gost_writer.close()
        iter_writer.close()
        test_writer.close()
        task_writer.close()
        task_link_writer.close()
        if project_writer:
            project_writer.close()
        if test_list_writer:
            test_list_writer.close()

    # Проверки собранных данных по правилам из checks_config.json
    try:
        checks.run(run_dir)
    except Exception as exc:
        logger.error("Ошибка проверок: %s", exc)
        errors.append(f"checks: {exc}")

    # HTML-отчёт
    try:
        report_path = report.build_report(run_dir)
        logger.info("Отчёт: %s", report_path)
    except Exception as exc:
        logger.error("Не удалось сформировать отчёт: %s", exc)
        errors.append(f"report: {exc}")

    # Сводка
    logger.info("=" * 50)
    logger.info("Запуск завершён. Ошибок: %d", len(errors))
    for err in errors:
        logger.warning("  - %s", err)
    logger.info("Результаты: %s", run_dir)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
