# План: проверка собранных в CSV параметров по заданным значениям

## Цель

Добавить в проект проверку данных, собранных в 5 CSV-файлов, по правилам из
конфиг-файла. Результаты проверок сохраняются в `checks.csv` и выводятся в
HTML-отчёт секцией «Проверки».

## Поток

```
сбор данных → CSV (5 файлов) → checks.run(run_dir) → checks.csv → report.html (секция «Проверки»)
```

## Согласованные решения

| Решение | Выбор |
|---------|-------|
| Источник правил | Отдельный JSON-конфиг `checks_config.json` (без зависимостей) |
| Типы проверок | `eq`, `not_empty`, `in`, `range`, `regex`, `date_range` |
| Сущности | Все 5: gosts, iterations, tests, tasks, task_links |
| Хранение результатов | Отдельный CSV `checks.csv` |
| Отчёт | Секция «Проверки» в `report.html` (сводка + таблица нарушений) |
| Запуск | Автоматически в `main.py` после сбора, перед отчётом |
| Структура конфига | Ключ = имя CSV, проверка всех строк файла |
| Exit code | Всегда 0 (нарушения не ломают сбор) |
| Пустое значение | = `fail` для всех типов |
| Формат дат | ISO `YYYY-MM-DD` в конфиге, парсер пробует форматы из CSV |
| Имя конфига | `checks_config.json` + пример `checks_config.example.json` |
| Идентификатор строки | `entity_id` из id-поля строки |
| Колонки checks.csv | `entity, entity_id, field, check_type, expected, actual, status, message` |
| Статус | `ok` / `fail` |
| Секция отчёта | Сводка (всего/ok/fail по сущностям) + таблица только нарушений (fail) |
| Интеграция report.py | Читает `checks.csv`, если есть — секция появляется автоматически |
| Порядок в main.py | После закрытия writer'ов → `checks.run(run_dir)` → `report.build_report(run_dir)` |
| Маппинг id-полей | Хардкод: gosts→gost_id, iterations→iteration_id, tests→test_id, tasks→task_id, task_links→link_id |
| Нет конфига | Пропуск проверок с логом-предупреждением, отчёт без секции |

## Структура конфига

```json
{
  "gosts": [
    {"field": "status", "type": "eq", "value": "..."},
    {"field": "name", "type": "not_empty"},
    {"field": "type_of_test", "type": "in", "values": ["...", "..."]},
    {"field": "test_count", "type": "range", "min": 0, "max": 100},
    {"field": "url", "type": "regex", "pattern": "^https://"},
    {"field": "start_gost_date", "type": "date_range", "from": "2026-01-01", "to": "2026-12-31"}
  ],
  "iterations": [...],
  "tests": [...],
  "tasks": [...],
  "task_links": [...]
}
```

## Файлы

- **Новый** [`checks.py`](checks.py) — модуль проверок: чтение конфига, чтение CSV,
  выполнение правил, запись `checks.csv`.
- **Новый** [`checks_config.json`](checks_config.json) — реальные правила.
- **Новый** [`checks_config.example.json`](checks_config.example.json) — шаблон.
- **Правка** [`main.py`](main.py) — вызов `checks.run(run_dir)` после закрытия writer'ов.
- **Правка** [`report.py`](report.py) — секция «Проверки» при наличии `checks.csv`.
- **Правка** [`AGENT.md`](AGENT.md) — документация по проверкам.

## Шаги реализации

1. Создать `checks_config.example.json` — шаблон правил (все 6 типов).
2. Создать `checks.py`:
   - маппинг сущность → id-поле;
   - чтение конфига (нет файла → вернуть None);
   - чтение CSV через `csv.DictReader`;
   - выполнение правил (пустое = fail);
   - запись `checks.csv` (utf-8-sig, колонки выше).
3. Интегрировать `checks.run(run_dir)` в `main.py` после закрытия writer'ов,
   перед `report.build_report(run_dir)`.
4. Расширить `report.py`: если есть `checks.csv` — секция «Проверки»
   (сводка по сущностям + таблица нарушений).
5. Обновить `AGENT.md` — описание проверок.