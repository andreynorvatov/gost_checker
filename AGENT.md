# GOST Checker — обход ГОСТ отчетов autoreportkns.mos.ru

Скрипт обходит данные ГОСТ отчетов на `https://autoreportkns.mos.ru` (Django admin) и
сохраняет их в CSV. Каждый запуск создаёт новую папку `{alias}_{quarter}_{timestamp}`
в `output/` с 6 CSV-файлами и HTML-отчётом `report.html`.

## Запуск

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Структура проекта

| Файл | Назначение |
|------|------------|
| [`.env`](.env) | Секреты: `COOKIE_STRING` (куки для авторизации). Не коммитится (в `.gitignore`) |
| [`config.py`](config.py) | Константы: `BASE_URL`, параметры запроса, таймауты, ретраи; `COOKIE_STRING` читается из `.env` |
| [`http_client.py`](http_client.py) | Сессия `requests` с куками, ретраи с backoff, `get_html(url)` |
| [`parsers.py`](parsers.py) | Парсеры HTML: `parse_summary`, `parse_gost`, `parse_iteration`, `parse_test`, `parse_task`, `parse_project` |
| [`storage.py`](storage.py) | Папка запуска, запись CSV (utf-8-sig), поля CSV-файлов |
| [`checks.py`](checks.py) | Проверка собранных CSV по правилам из `checks_config.json`, запись `checks.csv` (можно запускать отдельно: `python checks.py <папка>`) |
| [`checks_config.json`](checks_config.json) | Правила проверок (JSON): сущность → список правил (поле + тип + параметры) |
| [`checks_config.example.json`](checks_config.example.json) | Шаблон конфига проверок со всеми типами правил |
| [`report.py`](report.py) | Сборщик HTML-отчёта `report.html` из CSV (можно запускать отдельно: `python report.py <папка>`) |
| [`main.py`](main.py) | Оркестрация обхода, логирование в консоль, сводка ошибок, проверки, генерация отчёта |
| [`requirements.txt`](requirements.txt) | Зависимости: requests, beautifulsoup4, lxml, python-dotenv |

## Логика обхода (6 уровней)

```
summary (/gost/summary/) → ГОСТ (/admin/autoreport/gostreport/<id>/change/)
  → итерация (/admin/autoreport/iteration/<id>/change/)
    → тест (/admin/autoreport/test/<id>/change/) — добираем url_preview, from_vp, to_vp
  → задача (/admin/autoreport/task/<id>/change/) — дедупликация по task_id
    → проект (/admin/autoreport/project/<id>/change/) — дедупликация по project_id
```

1. **Summary** — таблица `#gost-summary-table`: список ГОСТов со статистикой и ссылками.
2. **ГОСТ** — форма `#gostreport_form` + inline-итерации `#iterations-group`.
3. **Итерация** — форма `#iteration_form` + inline-тесты `#tests-group`.
4. **Тест** — форма `#test_form`: добираем `url_preview`, `from_vp`, `to_vp`
   (остальные поля теста берутся из inline-таблицы итерации).
5. **Задача** — форма `#task_form` + inline-ссылки `#links-group`.
   Уникальные `task_id` собираются из итераций, каждая задача обходится один раз.
   Из поля «Проект» извлекается `project_id` (value выбранной option).
6. **Проект** — форма проекта: все поля `.form-row.field-*` парсятся автоматически
   (checkbox/select/textarea/readonly/input). Уникальные `project_id` собираются из задач,
   каждый проект обходится один раз.

## Выходные CSV

| Файл | Содержимое |
|------|------------|
| `gosts.csv` | Данные ГОСТов из summary + страницы (alias, url_preview, review, version и т.д.) |
| `iterations.csv` | Итерации: КЭ/КГ/РС/АС, результаты, узкие места, рекомендации, task_id |
| `tests.csv` | Тесты: inline-данные + url_preview/from_vp/to_vp со страницы теста |
| `tasks.csv` | Все поля задач (title, jira_id, status, purposes, requirements, project_id и т.д.) |
| `task_links.csv` | Ссылки задач: link_type, url, description |
| `projects.csv` | Все поля проектов (парсятся автоматически из `.form-row.field-*`) |
| `checks.csv` | Результаты проверок: entity, entity_id, field, check_type, expected, actual, status, message, description |
| `report.html` | Красивый HTML-отчёт со всеми данными (сводка, ГОСТы с итерациями и тестами, задачи со ссылками, проекты, секция «Проверки») |

Все URL в CSV — полные, с доменом. Кодировка — utf-8-sig (корре��тно открывается в Excel).
Отч��т генерируется автоматически в конце обхода; можно перегенерировать отдельно:
`.venv/bin/python report.py output/<папка_запуска>`.

## Проверки данных (checks)

После сбора данных `main.py` запускает проверки по правилам из
[`checks_config.json`](checks_config.json) и пишет `checks.csv`. Результаты
выводятся в `report.html` секцией «Проверки» (сводка по сущностям + таблица
нарушений). Проверки можно перегенерировать отдельно:
`.venv/bin/python checks.py output/<папка_запуска>`.

Структура конфига — ключ = имя CSV, правило = поле + тип + параметры +
описание (`description` — что за проверка, выводится в checks.csv и отчёте):

```json
{
  "gosts": [
    {"field": "iteration_count", "type": "has_iterations", "description": "У ГОСТа есть 1 и более итераций"},
    {"field": "editor", "type": "not_empty", "description": "Поле «Инженер» не пустое"},
    {"field": "type_of_test", "type": "count_max", "max": 6, "description": "ГОСТ отчетов по каждому типу НиО/НТ не более 6"}
  ]
}
```

Типы проверок: `eq` (value), `not_empty`, `in` (values), `range` (min/max),
`regex` (pattern), `date_range` (from/to, ISO `YYYY-MM-DD`),
`count_max` (max) — агрегатная: количество строк в каждой группе по полю ≤ max
(например, ГОСТ отчетов по каждому типу НиО/НТ не более 6),
`all_not_empty` — все поля строки заполнены (кроме id-поля и url),
`has_tests` — у итерации есть 1 и более тестов (по tests.csv),
`test_dates_match` — first_test_date/last_test_date совпадают с фактическими
датами тестов итерации (min start_date / max end_date),
`test_count_max` (max) — в итерации не более max тестов,
`or_min` (fields, min) — хотя бы одно из полей > min
(например, разработанных ИЛИ актуализированных скриптов > 0),
`has_iterations` — у ГОСТа есть 1 и более итераций (по iterations.csv),
`gost_dates_match` — start_actual_date/end_actual_date ГОСТа совпадают с
начальной и конечной датами итераций (min first_test_date / max last_test_date),
`name` — значение — фамилия и имя (2+ кириллических слова, например «Иванов Иван»).

Правила:
- Проверяются все строки файла; `entity_id` берётся из id-поля
  (`gost_id`, `iteration_id`, `test_id`, `task_id`, `link_id`, `project_id`).
- Пустое значение поля = нарушение (`fail`) для всех типов.
- Статус: `ok` / `fail`. Нарушения не влияют на exit code (всегда 0).
- Нет конфига или он пуст → проверки пропускаются с предупреждением,
  секция «Проверки» в отчёте не появляется.

## Ключевые решения

- **Синхронный `requests`**, без лимитов и задержек.
- **3 ретрая** с backoff; при неудаче — ошибка в лог, обход продолжается.
- **Лог только в консоль** (без файла).
- **Куки** (`COOKIE_STRING`) хранятся в `.env` и загружаются через `python-dotenv`; без них скрипт не авторизуется.
- **Параметры фильтра** задаются константами в [`config.py`](config.py:17) — одна комбинация за запуск, CLI нет.
- **Без докачки**: каждый запуск — новый сбор данных в новую папку.
- Парсинг по CSS-селекторам Django admin (стабильная вёрстка) + URL-паттерны для ссылок.

## Примечания по парсингу

- Пром статистика (`is_stats_prom`): иконка `fa-check-square` = да, `fa-ban` = нет.
- Поле "Ссылка отсутствует" в summary → пустое значение `share_url`.
- Многострочные textarea в CSV корректно экранируются (кавычки + переносы).
- JSON-поля задачи (`station_metrics`, `server_metrics`) сохраняются как текст.
