# GOST Checker — обход ГОСТ отчетов autoreportkns.mos.ru

Скрипт обходит данные ГОСТ отчетов на `https://autoreportkns.mos.ru` (Django admin) и
сохраняет их в CSV. Каждый запуск создаёт новую папку `{alias}_{quarter}_{timestamp}`
в `output/` с 5 CSV-файлами и HTML-отчётом `report.html`.

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
| [`parsers.py`](parsers.py) | Парсеры HTML: `parse_summary`, `parse_gost`, `parse_iteration`, `parse_test`, `parse_task` |
| [`storage.py`](storage.py) | Папка запуска, запись CSV (utf-8-sig), поля CSV-файлов |
| [`report.py`](report.py) | Сборщик HTML-отчёта `report.html` из CSV (можно запускать отдельно: `python report.py <папка>`) |
| [`main.py`](main.py) | Оркестрация обхода, логирование в консоль, сводка ошибок, генерация отчёта |
| [`requirements.txt`](requirements.txt) | Зависимости: requests, beautifulsoup4, lxml, python-dotenv |

## Логика обхода (5 уровней)

```
summary (/gost/summary/) → ГОСТ (/admin/autoreport/gostreport/<id>/change/)
  → итерация (/admin/autoreport/iteration/<id>/change/)
    → тест (/admin/autoreport/test/<id>/change/) — добираем url_preview, from_vp, to_vp
  → задача (/admin/autoreport/task/<id>/change/) — дедупликация по task_id
```

1. **Summary** — таблица `#gost-summary-table`: список ГОСТов со статистикой и ссылками.
2. **ГОСТ** — форма `#gostreport_form` + inline-итерации `#iterations-group`.
3. **Итерация** — форма `#iteration_form` + inline-тесты `#tests-group`.
4. **Тест** — форма `#test_form`: добираем `url_preview`, `from_vp`, `to_vp`
   (остальные поля теста берутся из inline-таблицы итерации).
5. **Задача** — форма `#task_form` + inline-ссылки `#links-group`.
   Уникальные `task_id` собираются из итераций, каждая задача обходится один раз.

## Выходные CSV

| Файл | Содержимое |
|------|------------|
| `gosts.csv` | Данные ГОСТов из summary + страницы (alias, url_preview, review, version и т.д.) |
| `iterations.csv` | Итерации: КЭ/КГ/РС/АС, результаты, узкие места, рекомендации, task_id |
| `tests.csv` | Тесты: inline-данные + url_preview/from_vp/to_vp со страницы теста |
| `tasks.csv` | Все поля задач (title, jira_id, status, purposes, requirements и т.д.) |
| `task_links.csv` | Ссылки задач: link_type, url, description |
| `report.html` | Красивый HTML-отчёт со всеми данными (сводка, ГОСТы с итерациями и тестами, задачи со ссылками) |

Все URL в CSV — полные, с доменом. Кодировка — utf-8-sig (корре��тно открывается в Excel).
Отч��т генерируется автоматически в конце обхода; можно перегенерировать отдельно:
`.venv/bin/python report.py output/<папка_запуска>`.

## Ключевые решения

- **Синхронный `requests`**, без лимитов и задержек.
- **3 ретрая** с backoff; при неудаче — ошибка в лог, обход продолжается.
- **Лог только в консоль** (без файла).
- **Параметры фильтра** задаются константами в [`config.py`](config.py:17) — одна комбинация за запуск, CLI нет.
- **Без докачки**: каждый запуск — новый сбор данных в новую папку.
- Парсинг по CSS-селекторам Django admin (стабильная вёрстка) + URL-паттерны для ссылок.

## Примечания по парсингу

- Пром статистика (`is_stats_prom`): иконка `fa-check-square` = да, `fa-ban` = нет.
- Поле "Ссылка отсутствует" в summary → пустое значение `share_url`.
- Многострочные textarea в CSV корректно экранируются (кавычки + переносы).
- JSON-поля задачи (`station_metrics`, `server_metrics`) сохраняются как текст.
