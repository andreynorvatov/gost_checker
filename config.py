"""Константы и настройки скрипта обхода ГОСТ отчетов."""

import os

from dotenv import load_dotenv

# Загрузка переменных окружения из .env (COOKIE_STRING и др.)
load_dotenv()

# Базовый URL сервиса
BASE_URL = "https://autoreportkns.mos.ru"

# Значимые куки для всех запросов (задаются в .env)
COOKIE_STRING = os.getenv("COOKIE_STRING", "")

# Параметры запроса summary (одна комбинация за запуск)
QUERY_PARAMS = {
    "quarter": "2026_3",
    "alias": "mpgu_pri",
    "type_of_test": "",
    "gost_sys": "100",
    "editor": "",
    "curator": "",
}

# HTTP-настройки
TIMEOUT = 30          # таймаут запроса, сек
RETRIES = 3           # число попыток запроса
RETRY_BACKOFF = 2.0   # базовая задержка между ретраями, сек (умножается на номер попытки)

# Заголовки запросов
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

# Каталог, куда складываются папки запусков
OUTPUT_ROOT = "output"
