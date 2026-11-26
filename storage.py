"""Сохранение данных: папка запуска и запись CSV (utf-8-sig)."""

import csv
import os
from datetime import datetime

import config


def create_run_dir(alias: str, quarter: str) -> str:
    """Создаёт папку запуска {alias}_{quarter}_{timestamp} в OUTPUT_ROOT."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{alias}_{quarter}_{timestamp}"
    path = os.path.join(config.OUTPUT_ROOT, dir_name)
    os.makedirs(path, exist_ok=True)
    return path


class CsvWriter:
    """Запись строк в CSV-файл с заголовками. Кодировка utf-8-sig (для Excel)."""

    def __init__(self, path: str, fieldnames: list[str]):
        self.path = path
        self.fieldnames = fieldnames
        self._file = open(path, "w", newline="", encoding="utf-8-sig")
        self._writer = csv.DictWriter(self._file, fieldnames=fieldnames, extrasaction="ignore")
        self._writer.writeheader()

    def write(self, row: dict) -> None:
        """Записывает строку (лишние ключи игнорируются, отсутствующие — пустые)."""
        self._writer.writerow(row)

    def close(self) -> None:
        self._file.close()


# Поля CSV-файлов
GOST_FIELDS = [
    "gost_id", "name", "url", "type_of_test", "is_stats_prom",
    "kg", "ke", "rs", "ak", "status", "quarter",
    "test_count", "iteration_count", "gost_sys", "share_url",
    "editor", "curator", "request", "p_number", "test_dates",
    "start_gost_date", "end_gost_date",
    "alias", "testing_result", "bottlenecks", "recommendation",
    "url_preview", "review", "start_actual_date", "end_actual_date", "version",
]

ITERATION_FIELDS = [
    "iteration_id", "gost_id", "url", "created_at",
    "emulator_count", "generator_count", "developed_script_count", "updated_script_count",
    "testing_result", "bottlenecks", "recommendation",
    "task_id", "iter_num", "test_count", "first_test_date", "last_test_date",
]

TEST_FIELDS = [
    "test_id", "iteration_id", "url", "number", "detailing",
    "name_of_test", "from_ts", "to_ts", "test_description", "test_results",
    "grafana_url", "start_date", "end_date", "duration", "engineer",
    "url_preview", "from_vp", "to_vp",
]

TASK_FIELDS = [
    "task_id", "name", "url", "created_at", "title", "jira_id", "page_id",
    "wiki_url", "status", "testing_result", "grafana_url",
    "station_metrics", "server_metrics", "bottlenecks", "recommendation",
    "purposes", "requirements", "restriction", "test_data",
    "project", "engineer", "curator", "updated_at",
]

TASK_LINK_FIELDS = [
    "link_id", "task_id", "url", "link_type", "link_url", "description",
]
