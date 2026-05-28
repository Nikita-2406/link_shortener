import json
import os
import secrets
from typing import Optional, TypedDict
from hashlib import sha256
import heapq


def _make_short_code(long_url: str) -> str:
    # генерируем "случайный" seed
    seed = secrets.token_hex(16)  # 16 байт → 32 hex
    # смешиваем с URL
    combined = seed + long_url
    # хэшируем
    h = sha256(combined.encode()).hexdigest()
    # берём первые N символов
    return h[:8]


class URLEntry(TypedDict):
        long_url: str
        count_use: int


class URLShortener:
    def __init__(self, data_file: str = "url_shortener.json",
                 max_count_url: int = 1000,
                 base_url: str = "http://short.ru/"):
        self.data: dict[str, URLEntry] = {}  # short_code -> {long_url:..., count_use:...}
        self.long_to_short: dict[str, str] = {}  # long_url -> short_code для поиска сложностью O(1)
        self.heap: list[tuple] = []

        self.data_file = data_file
        self.max_count_url = max_count_url
        self.base_url = base_url

        self._count = 0
        self._next_insert_order: int = 0
        self.number_transit = 0

        self.load()

    def _del_unused_url(self):
        """
            Удаляет одну ссылку, которая:
              * использовалась реже всех
              * и из всех таких — самая старая по insert_order.

            Возвращает True, если удаление прошло, False — если нечего удалять.

            Алгоритмическая сложность O(log n)
        """

        while self.heap:
            count_use, insert_order, short_code = heapq.heappop(self.heap)

            if short_code not in self.data:
                continue

            if self.data[short_code]["count_use"] != count_use:
                continue

            long_url = self.data[short_code]["long_url"]
            del self.data[short_code]
            del self.long_to_short[long_url]
            self._count -= 1
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
            new_count = self.data[short_code]["count_use"]
            self._next_insert_order += 1
            heapq.heappush(self.heap, (new_count, self._next_insert_order, short_code))
            return self.base_url + short_code

        if self._count >= self.max_count_url:
            is_deleted = self._del_unused_url()
            if not is_deleted:
                raise RuntimeError("Не удалось освободить место: хранилище переполнено")

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
                self.number_transit += 1
                return self.base_url + short_code

    def resolve(self, short_url: str) -> Optional[str]:
        """
            Возвращает оригинальный url по сокращенному url

            Алгоритмическая сложность O(1)
        """
        short_code = short_url.rstrip("/").split("/")[-1]
        if not short_code:
            return None
        data = self.data.get(short_code)
        if data is None:
            return None
        data["count_use"] += 1
        return data["long_url"]

    def get_count_transit(self):
        """
            Возвращает количество переходов из длинной ссылки в короткую

            Алгоритмическая сложность O(1)
        """
        return f'Количество переходов из длинного url в короткий = {self.number_transit}'

    def save(self):
        """
            Сохранение сокращенных ссылок в JSON

            Алгоритмическая сложность O(n)
        """
        tmp_file = self.data_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp_file, self.data_file)

    def load(self):
        """
            Выгрузка данных из JSON и восстановление вспомогательных структур

            Алгоритмическая сложность O(n)
        """
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Неверный формат данных при загрузке")
            self.data = raw
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