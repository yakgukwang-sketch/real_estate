"""공용 HTTP 클라이언트 - 재시도, rate-limit, 로깅."""

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ApiClient:
    """재시도 및 rate-limit 기능이 내장된 HTTP 클라이언트."""

    def __init__(
        self,
        base_url: str = "",
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        rate_limit_delay: float = 0.2,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self._last_request_time = 0.0

        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

    def get(self, url: str, params: dict | None = None, **kwargs) -> requests.Response:
        self._wait_for_rate_limit()
        if url.startswith(("http://", "https://")):
            full_url = url
        elif self.base_url:
            full_url = f"{self.base_url}/{url.lstrip('/')}"
        else:
            full_url = url
        logger.debug("GET %s params=%s", full_url, params)
        self._last_request_time = time.time()
        response = self.session.get(
            full_url, params=params, timeout=self.timeout, **kwargs
        )
        response.raise_for_status()
        return response

    def get_json(self, url: str, params: dict | None = None, **kwargs) -> dict | list:
        return self.get(url, params=params, **kwargs).json()

    def get_xml(self, url: str, params: dict | None = None, **kwargs) -> str:
        return self.get(url, params=params, **kwargs).text
