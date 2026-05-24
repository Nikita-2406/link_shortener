import json
import secrets
import string
from typing import Dict, Optional
from hashlib import sha256
import heapq

ALPHABET = string.ascii_lowercase + string.digits


def _make_short_code(long_url: str) -> str:
    # генерируем "случайный" seed
    seed = secrets.token_hex(16)  # 16 байт → 32 hex
    # смешиваем с URL
    combined = seed + long_url
    # хэшируем
    h = sha256(combined.encode()).hexdigest()
    # берём первые N символов
    return h[:8]


class URLShortener:
    def __init__(self, data_file: str = "url_shortener.json", max_count_url: int = 1000):
        self.data: Dict[str, dict] = {}  # short_code -> {long_url:..., count_use:...}
        self.long_to_short: Dict[str, str] = {}  # long_url -> short_code для поиска сложностью O(1)
        self.data_file = data_file
        self.max_count_url = max_count_url
        self.base_url = "http://short.ru/"
        self.heap: list[tuple] = []
        self._count = 0
        self._next_insert_order: int = 0

        self.load()

    def _del_unused_url(self):
        """
            Удаляет одну ссылку, которая:
              * использовалась реже всех
              * и из всех таких — самая старая по insert_order.

            Возвращает True, если удаление прошло, False — если нечего удалять.

            Алгоритмическая сложность O(log n)
        """
        if not self.heap:
            return False

        while self.heap:
            count_use, insert_order, short_code = heapq.heappop(self.heap)

            if short_code not in self.data:
                continue

            data = self.data[short_code]
            long_url = data["long_url"]

            del self.data[short_code]
            del self.long_to_short[long_url]

            return True

        return False

    def shorten(self, long_url: str) -> str:
        """
            Возвращает короткую ссылку по длинной

            Алгоритмическая сложность O(1)
        """
        # если этот URL уже есть, возвращаем его старую короткую ссылку
        if long_url in self.long_to_short:
            short_code = self.long_to_short[long_url]
            self.data[short_code]["count_use"] += 1
            return self.base_url + short_code

        if self._count >= self.max_count_url:
            self._del_unused_url()
            self._count -= 1

        # генерим новый код, пока не найдём свободный, коллизия практически невозможна, но на всякий случай есть цикл
        while True:
            short_code = _make_short_code(long_url)
            if short_code not in self.data:
                self._next_insert_order += 1
                self.data[short_code] = {
                    "long_url": long_url,
                    "count_use": 0
                }
                self.long_to_short[long_url] = short_code

                heapq.heappush(self.heap, (0, self._next_insert_order, short_code))

                self._count += 1
                return self.base_url + short_code

    def resolve(self, short_url: str) -> Optional[str]:
        """
            Возвращает оригинальный url по сокращенному url

            Алгоритмическая сложность O(1)
        """
        path = short_url.rstrip("/").split("/")[-1]
        if not path:
            return None
        return self.data.get(path)["long_url"]

    def save(self):
        """
            Сохранение сокращенных ссылок в JSON

            Алгоритмическая сложность O(n)
        """
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f)

    def load(self):
        """
            Выгрузка данных из JSON и восстановление вспомогательных структур

            Алгоритмическая сложность O(n)
        """
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}
            return

        # Восстанавливаем все вспомогательные структуры
        for short_code, info in self.data.items():
            long_url = info["long_url"]
            count_use = info["count_use"]

            self.long_to_short[long_url] = short_code

            heapq.heappush(self.heap, (count_use, self._next_insert_order, short_code))
            self._next_insert_order += 1

        self._count = len(self.data)