"""Jinja 字节码缓存的故障面与过滤器兜底（`report/html_jinja_env`）。

两条独立契约：
  - 字节码缓存**纯属加速**：读不到、写不进、清理扫不动都只留 DEBUG，绝不影响报告产出；
  - 模板过滤器收到脏值（None/字符串/缺字段）时输出 ``--`` 而不是抛异常，
    否则任何一个字段取数异常就会把整页 HTML 渲染打断。
"""

from __future__ import annotations

import os
import time

import pytest

from src.python.report import html_jinja_env as env_mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _FakeBucket:
    def __init__(self, key: str, payload: bytes = b"", *, dump_error: Exception | None = None) -> None:
        self.key = key
        self.payload = payload
        self._dump_error = dump_error

    def bytecode_to_string(self) -> bytes:
        if self._dump_error is not None:
            raise self._dump_error
        return self.payload

    def bytecode_from_string(self, data: bytes) -> None:
        self.payload = data


@pytest.fixture()
def cache_root(tmp_path, monkeypatch):
    """把字节码缓存目录重定向到 tmp（缓存根按需解析，故在用例内改即可）。"""
    import src.python.cache as cache_pkg

    monkeypatch.setattr(cache_pkg, "get_cache_dir", lambda: str(tmp_path))
    return tmp_path


class TestPruneStale:
    def test_fresh_and_foreign_entries_survive(self, cache_root):
        fresh = cache_root / "jinja" / "fresh.cache"
        fresh.parent.mkdir(parents=True)
        fresh.write_bytes(b"x")
        foreign = cache_root / "jinja" / "notes.txt"
        foreign.write_bytes(b"x")

        env_mod._JinjaBytecodeCache._prune_stale(str(fresh.parent))

        assert fresh.exists(), "保留期内条目不得删除"
        assert foreign.exists(), "非 .cache 条目不在清理范围"

    def test_expired_entry_removed(self, cache_root):
        stale = cache_root / "jinja" / "stale.cache"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"x")
        old = time.time() - (env_mod.BYTECODE_CACHE_TTL_DAYS + 1) * 86400
        os.utime(stale, (old, old))

        env_mod._JinjaBytecodeCache._prune_stale(str(stale.parent))

        assert not stale.exists(), "超过保留期的条目须回收（改模板会不断换键）"

    def test_entry_stat_failure_is_skipped(self, cache_root, monkeypatch):
        """单个条目 stat 失败（并发删除）→ 跳过它，继续扫其余条目。"""
        target = cache_root / "jinja" / "gone.cache"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x")

        class _Entry:
            name = "gone.cache"
            path = str(target)

            def stat(self):
                raise OSError("vanished")

        class _Scandir:
            def __enter__(self):
                return iter([_Entry()])

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(env_mod.os, "scandir", lambda directory: _Scandir())

        env_mod._JinjaBytecodeCache._prune_stale(str(target.parent))

        assert target.exists()

    def test_missing_directory_returns_quietly(self, tmp_path, caplog):
        """缓存目录尚不存在（首跑）→ 直接返回：不抛异常，也不告警刷屏。"""
        env_mod._JinjaBytecodeCache._prune_stale(str(tmp_path / "absent"))

        assert not [r for r in caplog.records if r.levelno >= 30], "首跑缺目录属预期，不得告警"


class TestLoadDumpFaults:
    def test_unreadable_cache_falls_back_to_compile(self, cache_root, monkeypatch, caplog):
        """缓存文件不可读（权限/损坏）→ DEBUG 后回退编译，不影响报告。"""
        cache = env_mod._JinjaBytecodeCache()
        cache.dump_bytecode(_FakeBucket("abc", b"payload"))
        target = cache_root / "jinja" / "abc.cache"
        assert target.exists()

        def _raise(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(env_mod, "open", _raise, raising=False)

        cache.load_bytecode(_FakeBucket("abc"))

        assert "字节码缓存读取失败" in caplog.text

    def test_unwritable_cache_is_ignored(self, cache_root, monkeypatch, caplog):
        """缓存写不进（磁盘满/只读）→ DEBUG 后继续，报告照常产出。"""
        cache = env_mod._JinjaBytecodeCache()

        def _raise(*args, **kwargs):
            raise OSError("no space left on device")

        monkeypatch.setattr(env_mod.os, "makedirs", _raise)

        cache.dump_bytecode(_FakeBucket("abc", b"payload"))

        assert "字节码缓存写入失败" in caplog.text

    def test_dump_prunes_after_success(self, cache_root):
        cache = env_mod._JinjaBytecodeCache()
        stale = cache_root / "jinja" / "stale.cache"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"x")
        old = time.time() - (env_mod.BYTECODE_CACHE_TTL_DAYS + 1) * 86400
        os.utime(stale, (old, old))

        cache.dump_bytecode(_FakeBucket("newkey", b"payload"))

        assert (cache_root / "jinja" / "newkey.cache").exists()
        assert not stale.exists(), "写入成功后顺带回收过期条目"


class TestFormatFilters:
    @pytest.mark.parametrize("bad", [None, "abc", object(), {"a": 1}])
    def test_money_pct_price_shares_change_fallback(self, bad):
        """脏值（None/非数值/对象）→ `--`，不得抛异常打断渲染。"""
        assert env_mod._jinja_money(bad) == "--"
        assert env_mod._jinja_pct(bad) == "--"
        assert env_mod._jinja_price(bad) == "--"
        assert env_mod._jinja_shares(bad) == "--"
        assert env_mod._jinja_change(bad) == "--"

    def test_valid_numbers_format(self):
        assert env_mod._jinja_money(1234.5) == "1,234.50"
        assert env_mod._jinja_pct(0.155) == "+15.50%"
        assert env_mod._jinja_price(3.14159) == "3.1416"
        assert env_mod._jinja_change(-1.5) == "-1.50%"

    def test_thousands_falls_back_to_original_text(self):
        """整数格式化失败时原样返回（不丢信息，也不抛）。"""
        assert env_mod._jinja_thousands("12.5%") == "12.5%"
        assert env_mod._jinja_thousands(1234) == "1,234"

    def test_profit_class_three_states(self):
        assert env_mod._jinja_profit_class(1.5) == "profit"
        assert env_mod._jinja_profit_class(-1.5) == "loss"
        assert env_mod._jinja_profit_class(0) == ""
        assert env_mod._jinja_profit_class(None) == ""

    def test_price_type_class_rules(self):
        """取价方式着色：T 日口径与 QDII 旧一日净值视为稳定。"""
        assert env_mod._jinja_price_type_class("场内收盘价(T)") == "rating-stable"
        assert env_mod._jinja_price_type_class(env_mod.PRICE_TYPE_OFFICIAL_NAV_T1, "华夏全球(QDII)") == (
            "rating-stable"
        )
        assert env_mod._jinja_price_type_class(env_mod.PRICE_TYPE_OFFICIAL_NAV_T1, "沪深300ETF") == ""
        assert env_mod._jinja_price_type_class("估算值") == ""

    def test_sentiment_colorize(self):
        """[利好]/[利空] 标记转为跟随主题的内联样式；空文本原样返回。"""
        rendered = env_mod._jinja_sentiment_colorize("[利好] 降准 [利空] 违约")

        assert "var(--profit)" in rendered
        assert "var(--loss)" in rendered
        assert env_mod._jinja_sentiment_colorize("") == ""


class TestAnonCodeFilter:
    """代码折叠过滤器：off/未命中零副作用，命中才换成脱敏代号。"""

    @pytest.mark.parametrize("empty", ["", None, 0, []])
    def test_non_string_or_empty_returns_as_is(self, empty):
        assert env_mod._jinja_anon_code({}, empty) == empty

    def test_hit_replaces_with_alias(self):
        ctx = {"anon_code_map": {"600900.SS": "标的A"}}

        assert env_mod._jinja_anon_code(ctx, "600900.SS") == "标的A"

    def test_miss_keeps_original_code(self):
        assert env_mod._jinja_anon_code({"anon_code_map": {}}, "600900.SS") == "600900.SS"
        assert env_mod._jinja_anon_code({}, "600900.SS") == "600900.SS"
