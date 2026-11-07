"""Jinja 模板字节码缓存（回归：每次跑报告都重新编译 18 个模板）。

现场：`HTML 生成` 阶段的耗时几乎全是模板**编译**——实测 18 个模板（主模板 + 17 个
partial）编译占 0.65s ≈ 97%，而渲染本身只有 ~0.02s、落盘 0.003s；冷缓存时还得从挂载盘
读 18 个模板文件，这正是该阶段在 0.02s~21s 间大幅抖动的来源。

锁定：①缓存目录随 `cache` 根走（测试/`INVEST_CACHE_DIR` 重定向必须生效，否则会写进
真实 `data/cache`）；②`_ENV` 已接线；③第二个进程/环境命中缓存时**不再编译**模板。
"""

from __future__ import annotations

import pytest

from src.python.report.html_jinja_env import _ENV, _JinjaBytecodeCache, _TEMPLATE_DIR

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _FakeBucket:
    """Jinja `Bucket` 替身：只保留缓存读写所需的最小面。"""

    def __init__(self, key: str, payload: bytes = b"") -> None:
        self.key = key
        self.payload = payload

    def bytecode_to_string(self) -> bytes:
        return self.payload

    def bytecode_from_string(self, data: bytes) -> None:
        self.payload = data


def test_roundtrip_writes_and_reads():
    cache = _JinjaBytecodeCache()
    cache.dump_bytecode(_FakeBucket("deadbeef", b"bytecode!"))

    read_back = _FakeBucket("deadbeef")
    cache.load_bytecode(read_back)

    assert read_back.payload == b"bytecode!"


def test_missing_key_is_silent():
    """缓存缺失只是「本次要编译」，不得抛错。"""
    read_back = _FakeBucket("never-written")
    _JinjaBytecodeCache().load_bytecode(read_back)

    assert read_back.payload == b""


def test_cache_dir_follows_cache_root(tmp_path, monkeypatch):
    """缓存目录按需解析：缓存根重定向后立即生效（否则测试会写进真实 data/cache）。"""
    import src.python.cache._paths as cache_paths

    monkeypatch.setattr(cache_paths, "_CACHE_DIR", str(tmp_path / "cache-root"))

    cache = _JinjaBytecodeCache()
    cache.dump_bytecode(_FakeBucket("cafebabe", b"x"))

    assert (tmp_path / "cache-root" / "jinja" / "cafebabe.cache").is_file()


def test_env_wires_bytecode_cache():
    assert isinstance(_ENV.bytecode_cache, _JinjaBytecodeCache)


def test_second_environment_skips_compilation(tmp_path, monkeypatch):
    """同源模板的第二次加载走字节码缓存，不再编译（编译即本阶段主要开销）。"""
    from jinja2 import Environment, FileSystemLoader

    import src.python.cache._paths as cache_paths

    monkeypatch.setattr(cache_paths, "_CACHE_DIR", str(tmp_path / "cache-root"))
    name = "partials/action_section.html"

    def _load_with_compile_count() -> tuple[int, str]:
        # 独立 Environment（不复用 _ENV 的模板缓存，否则测不到字节码缓存这一层），
        # 过滤器/全局变量从生产环境克隆，保证模板能编译通过
        env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=True,
            bytecode_cache=_JinjaBytecodeCache(),
        )
        env.filters.update(_ENV.filters)
        env.globals.update(_ENV.globals)
        calls = {"n": 0}
        original = Environment.compile

        def _counted(self, *args, **kwargs):
            calls["n"] += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Environment, "compile", _counted)
        try:
            template = env.get_template(name)
        finally:
            monkeypatch.setattr(Environment, "compile", original)
        return calls["n"], template.filename or ""

    first_calls, first_path = _load_with_compile_count()
    second_calls, second_path = _load_with_compile_count()

    assert first_calls >= 1, "首次加载必须编译（否则缓存无从产生）"
    assert second_calls == 0, f"命中字节码缓存时不得再编译（实测 0.65s → 0.03s）: {second_calls} 次"
    assert first_path == second_path


def test_stale_entries_pruned_on_write(tmp_path, monkeypatch):
    """改模板会换缓存键：旧键须按保留期回收，否则只增不减。"""
    import os
    import time as _time

    import src.python.cache._paths as cache_paths
    from src.python.report.html_jinja_env import BYTECODE_CACHE_TTL_DAYS

    monkeypatch.setattr(cache_paths, "_CACHE_DIR", str(tmp_path / "cache-root"))
    cache = _JinjaBytecodeCache()
    cache.dump_bytecode(_FakeBucket("stale-key", b"old"))

    directory = tmp_path / "cache-root" / "jinja"
    stale = directory / "stale-key.cache"
    aged = _time.time() - (BYTECODE_CACHE_TTL_DAYS + 1) * 86400
    os.utime(stale, (aged, aged))

    cache.dump_bytecode(_FakeBucket("fresh-key", b"new"))

    assert not stale.exists(), "超过保留期的旧字节码须被回收"
    assert (directory / "fresh-key.cache").is_file()
