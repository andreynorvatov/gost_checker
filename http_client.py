"""HTTP-клиент: сессия requests, куки, ретраи с backoff."""

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


class HttpClient:
    """Обёртка над requests.Session с ретраями и обработкой ошибок."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        # Куки из строки вида "k1=v1;k2=v2"
        for part in config.COOKIE_STRING.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, _, value = part.partition("=")
            self.session.cookies.set(key, value, domain="autoreportkns.mos.ru")

    def get_html(self, url: str) -> str:
        """GET-запрос с ретраями. Возвращает HTML-текст ответа.

        При исчерпании попыток бросает последнее исключение.
        """
        last_exc = None
        for attempt in range(1, config.RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=config.TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                logger.warning(
                    "Ошибка запроса %s (попытка %d/%d): %s",
                    url, attempt, config.RETRIES, exc,
                )
                if attempt < config.RETRIES:
                    time.sleep(config.RETRY_BACKOFF * attempt)
        raise last_exc
