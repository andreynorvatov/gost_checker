"""Оркестрация обхода: summary → ГОСТ → итерация → тест + задача.

Каждый запуск создаёт новую папку {alias}_{quarter}_{timestamp} с 5 CSV:
gosts.csv, iterations.csv, tests.csv, tasks.csv, task_links.csv,
и HTML-отчётом report.html.
"""

import logging
import os
import sys
from urllib.parse import urlencode

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
            for link in links:
                task_link_writer.write(link)

    finally:
        gost_writer.close()
        iter_writer.close()
        test_writer.close()
        task_writer.close()
        task_link_writer.close()

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
