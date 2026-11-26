# План: извлечение проекта из задачи, обход проекта, CSV, отчёт, проверки

## Цель

Из ответа задачи извлекать номер проекта из `<option value="517" selected>mpgu_pri</option>`
(параметр `value`). Получить данные по
`https://autoreportkns.mos.ru/admin/autoreport/project/517/change/`, сохранить в CSV,
добавить данные в отчёт и проверки.

## Решения (согласовано с пользователем)

1. **Поля проекта** — парсить все `.form-row.field-*` автоматически + `project_id` из URL + `name` из `<h2>`.
2. **Связь** — добавить `project_id` в `tasks.csv` и `parse_task` (value option).
3. **Обход** — дедупликация по `project_id`, обход после задач.
4. **Проверки** — только `all_not_empty` для `projects`.
5. **Отчёт** — отдельная секция «Проекты» + stat-карточка + сайдбар + ссылка в задаче.
6. **Парсер значений** — по типу элемента: checkbox/select/textarea/readonly/input.
7. **Поля CSV** — собрать проекты в память, вычислить объединение полей, потом писать.
8. **Рендер карточки** — горизонтальная таблица всех полей + `name` заголовок + `url` ссылка.
9. **Ошибка обхода** — в лог и `errors`, проект пропускается, обход продолжается.
10. **Документация** — обновить `AGENT.md` и `checks_config.example.json`.
11. **Ссылки в проверках** — добавить `projects` в `ENTITY_LABELS` и `ENTITY_URL_PATTERNS`.
12. **Расположение секции** — «Проекты» после «Задачи», сайдбар после «Задачи».
13. **Ссылка в задаче** — только если проект есть в `projects.csv`, иначе текст `project_id`.

## Изменения по файлам

### parsers.py
- `parse_task`: добавить `project_id` через `_select_selected_value(field("project")...)`.
- Новый `parse_project(html, url) -> dict`:
  - `project_id` из URL `/project/(\d+)/change/`.
  - `name` из `<h2>`.
  - `url` = полный URL.
  - Для каждого `.form-row.field-<name>` определить тип и извлечь значение:
    - `input[type=checkbox]` → флаг (`1`/``).
    - `select` → текст выбранной option.
    - `textarea` → текст.
    - `.readonly` → текст.
    - иначе `input` → value.

### storage.py
- В `TASK_FIELDS` добавить `project_id` (после `project`).

### main.py
- Собрать `project_ids: set[str]` из задач (из `task_data["project_id"]`).
- После обхода задач: для каждого уникального `project_id` обойти
  `/admin/autoreport/project/{id}/change/`, распарсить `parse_project`.
- Собрать все проекты в память, вычислить объединение полей
  (`["project_id", "name", "url"] + остальные`), затем создать `CsvWriter` и записать `projects.csv`.
- Ошибка проекта → лог + `errors`, обход продолжается.

### checks.py
- В `ENTITY_ID_FIELDS` добавить `"projects": "project_id"`.

### checks_config.json
- Добавить секцию `"projects"` с правилом `all_not_empty`.

### report.py
- `ENTITY_LABELS["projects"] = "Проекты"`.
- `ENTITY_URL_PATTERNS["projects"] = .../project/{id}/change/`.
- Stat-карточка «Проектов».
- Секция «Проекты» после «Задачи»: карточки, горизонтальная таблица всех полей,
  `name` — заголовок-ссылка, `url` — ссылка.
- Сайдбар: пункт «Проекты» после «Задачи».
- В карточке задачи: ссылка на проект по `project_id` (если проект есть в `projects.csv`,
  иначе текст `project_id`).

### checks_config.example.json
- Добавить пример правила `all_not_empty` для `projects`.

### AGENT.md
- Обновить структуру проекта, выходные CSV, логику обхода (уровень проекта).

## Схема

```mermaid
flowchart TD
  A[parse_task] -->|project_id из value option| B[task_ids + project_ids]
  B --> C[обход задач]
  B --> D[обход уникальных проектов]
  D --> E[parse_project: все .form-row.field-*]
  E --> F[projects.csv: объединение полей]
  F --> G[checks: all_not_empty]
  F --> H[report: секция Проекты + stat + сайдбар + ссылка в задаче]