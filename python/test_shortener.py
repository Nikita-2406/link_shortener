import os
import pytest
from .shortener_url import _make_short_code, URLShortener


# ──────────────────────────────────────────────
# _make_short_code
# ──────────────────────────────────────────────

class TestMakeShortCode:
    def test_returns_8_chars(self):
        code = _make_short_code("https://example.com")
        assert len(code) == 8

    def test_returns_hex_string(self):
        code = _make_short_code("https://example.com")
        assert all(c in "0123456789abcdef" for c in code)

    def test_different_calls_return_different_codes(self):
        """Из-за secrets.token_hex каждый вызов уникален"""
        code1 = _make_short_code("https://example.com")
        code2 = _make_short_code("https://example.com")
        # С вероятностью 1 - 1/2^256 они различаются
        assert code1 != code2

    def test_different_urls_produce_different_codes(self):
        code1 = _make_short_code("https://a.com")
        code2 = _make_short_code("https://b.com")
        assert code1 != code2

    def test_empty_url(self):
        code = _make_short_code("")
        assert len(code) == 8


# ──────────────────────────────────────────────
# Фикстура — изолированный экземпляр с temp-файлом
# ──────────────────────────────────────────────

@pytest.fixture
def shortener(tmp_path):
    data_file = str(tmp_path / "test_urls.json")
    return URLShortener(data_file=data_file, max_count_url=5)


@pytest.fixture
def shortener_capacity_1(tmp_path):
    data_file = str(tmp_path / "test_urls_cap1.json")
    return URLShortener(data_file=data_file, max_count_url=1)


# ──────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────

class TestInit:
    def test_default_state(self, shortener):
        assert shortener.data == {}
        assert shortener.long_to_short == {}
        assert shortener._count == 0
        assert shortener.heap == []
        assert shortener._next_insert_order == 0

    def test_base_url(self, shortener):
        assert shortener.base_url == "http://short.ru/"

    def test_max_count_url_custom(self, tmp_path):
        s = URLShortener(str(tmp_path / "f.json"), max_count_url=42)
        assert s.max_count_url == 42


# ──────────────────────────────────────────────
# shorten
# ──────────────────────────────────────────────

class TestShorten:
    def test_returns_base_url_prefix(self, shortener):
        result = shortener.shorten("https://example.com")
        assert result.startswith("http://short.ru/")

    def test_short_code_is_8_chars(self, shortener):
        result = shortener.shorten("https://example.com")
        code = result.split("/")[-1]
        assert len(code) == 8

    def test_same_url_returns_same_short(self, shortener):
        r1 = shortener.shorten("https://example.com")
        r2 = shortener.shorten("https://example.com")
        assert r1 == r2

    def test_same_url_increments_count_use(self, shortener):
        r = shortener.shorten("https://example.com")
        shortener.resolve(r)
        code = r.split("/")[-1]
        assert shortener.data[code]["count_use"] == 1

    def test_different_urls_different_shorts(self, shortener):
        r1 = shortener.shorten("https://a.com")
        r2 = shortener.shorten("https://b.com")
        assert r1 != r2

    def test_count_increments(self, shortener):
        shortener.shorten("https://a.com")
        shortener.shorten("https://b.com")
        assert shortener._count == 2

    def test_long_to_short_populated(self, shortener):
        url = "https://example.com"
        r = shortener.shorten(url)
        code = r.split("/")[-1]
        assert shortener.long_to_short[url] == code

    def test_eviction_at_max_capacity(self, shortener_capacity_1):
        """При переполнении вытесняется наименее используемая ссылка"""
        s = shortener_capacity_1
        r1 = s.shorten("https://first.com")
        r2 = s.shorten("https://second.com")  # вытесняет первую
        assert s._count == 1
        # первая ссылка должна быть удалена
        code1 = r1.split("/")[-1]
        assert code1 not in s.data

    def test_eviction_keeps_most_used(self, tmp_path):
        """Вытесняется наименее используемая, а не та, что была популярнее"""
        s = URLShortener(str(tmp_path / "f.json"), max_count_url=2)
        r1 = s.shorten("https://popular.com")
        # используем первую ссылку несколько раз
        s.resolve(r1)
        s.resolve(r1)

        r2 = s.shorten("https://rarely.com")
        # добавляем третью — должна вытесниться rarely.com (count_use=0)
        r3 = s.shorten("https://new.com")

        short_code_u2 = r2.split("/")[-1]
        assert short_code_u2 not in s.data
        # popular.com должна остаться
        assert "https://popular.com" in s.long_to_short


# ──────────────────────────────────────────────
# resolve
# ──────────────────────────────────────────────

class TestResolve:
    def test_resolve_valid(self, shortener):
        long_url = "https://example.com"
        short = shortener.shorten(long_url)
        assert shortener.resolve(short) == long_url

    def test_resolve_with_trailing_slash(self, shortener):
        long_url = "https://example.com"
        short = shortener.shorten(long_url)
        assert shortener.resolve(short + "/") == long_url

    def test_resolve_unknown_returns_none(self, shortener):
        assert shortener.resolve("http://short.ru/notexist") is None

    def test_resolve_empty_path_returns_none(self, shortener):
        assert shortener.resolve("http://short.ru/") is None

    def test_resolve_base_url_only(self, shortener):
        assert shortener.resolve("http://short.ru/") is None


# ──────────────────────────────────────────────
# _del_unused_url
# ──────────────────────────────────────────────

class TestDelUnusedUrl:
    def test_empty_heap_returns_false(self, shortener):
        assert shortener._del_unused_url() is False

    def test_deletes_least_used(self, shortener):
        shortener.shorten("https://a.com")
        shortener.shorten("https://b.com")
        shortener.shorten("https://b.com")  # b используется 1 раз
        assert shortener._count == 2
        shortener._del_unused_url()
        assert shortener._count == 1

    def test_stale_heap_entries_skipped(self, shortener):
        """Записи в heap, которых уже нет в data, пропускаются"""
        import heapq
        # Добавляем фантомную запись прямо в heap
        heapq.heappush(shortener.heap, (0, 999, "phantom"))
        # Добавляем реальную
        shortener.shorten("https://real.com")
        shortener._del_unused_url()
        # phantom скипнулся, real.com удалён
        assert shortener._count == 0

    def test_returns_true_on_success(self, shortener):
        shortener.shorten("https://a.com")
        assert shortener._del_unused_url() is True

    def test_returns_false_when_all_stale(self, shortener):
        """Если в heap только фантомные записи — вернуть False"""
        import heapq
        heapq.heappush(shortener.heap, (0, 1, "ghost"))
        # data пустой — ghost будет пропущен
        assert shortener._del_unused_url() is False


# ──────────────────────────────────────────────
# save / load
# ──────────────────────────────────────────────

class TestSaveLoad:
    def test_save_creates_file(self, shortener):
        shortener.shorten("https://example.com")
        shortener.save()
        assert os.path.exists(shortener.data_file)

    def test_save_load_roundtrip(self, tmp_path):
        data_file = str(tmp_path / "urls.json")
        s1 = URLShortener(data_file=data_file)
        long_url = "https://example.com"
        short = s1.shorten(long_url)
        s1.save()

        s2 = URLShortener(data_file=data_file)
        assert s2.resolve(short) == long_url

    def test_load_restores_count(self, tmp_path):
        data_file = str(tmp_path / "urls.json")
        s1 = URLShortener(data_file=data_file)
        s1.shorten("https://a.com")
        s1.shorten("https://b.com")
        s1.save()

        s2 = URLShortener(data_file=data_file)
        assert s2._count == 2

    def test_load_restores_long_to_short(self, tmp_path):
        data_file = str(tmp_path / "urls.json")
        s1 = URLShortener(data_file=data_file)
        url = "https://example.com"
        short = s1.shorten(url)
        s1.save()

        s2 = URLShortener(data_file=data_file)
        code = short.split("/")[-1]
        assert s2.long_to_short[url] == code

    def test_load_restores_heap(self, tmp_path):
        data_file = str(tmp_path / "urls.json")
        s1 = URLShortener(data_file=data_file)
        s1.shorten("https://a.com")
        s1.save()

        s2 = URLShortener(data_file=data_file)
        assert len(s2.heap) == 1

    def test_load_file_not_found(self, tmp_path):
        s = URLShortener(str(tmp_path / "nonexistent.json"))
        assert s.data == {}
        assert s._count == 0

    def test_load_invalid_json(self, tmp_path):
        data_file = str(tmp_path / "bad.json")
        with open(data_file, "w") as f:
            f.write("not valid json {{{{")
        s = URLShortener(data_file=data_file)
        assert s.data == {}

    def test_load_increments_insert_order(self, tmp_path):
        data_file = str(tmp_path / "urls.json")
        s1 = URLShortener(data_file=data_file)
        s1.shorten("https://a.com")
        s1.shorten("https://b.com")
        s1.shorten("https://c.com")
        s1.save()

        s2 = URLShortener(data_file=data_file)
        assert s2._next_insert_order == 3