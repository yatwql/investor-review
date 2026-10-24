"""缓存命中 —— 真实配置加载链路（不 patch `get_llm_config`）。

为什么单开一个文件：`test_cache_matrix.py` 通过 patch 注入配置，这能精确控制输入，
但会绕过「config.json → llm_settings.json（v2 嵌套）+ llm_key.json / llm_providers.json
→ 展平 → 链注入」这一段真实接线。预检侧与写侧各拼一份键的偏差，正是绕开接线后
才没被发现。本文件的用例只 mock **网络调用**（`skeleton.call_llm`），其余全走真实代码。

覆盖：
1. 真实 v2 嵌套配置 + 多链 Provider → 第二份报告预检 4/4 命中；
2. 落盘文件名 = 预检键 + 缓存键版本（预检与写侧逐字节同源，端到端证明）；
3. 单 Provider（仅 llm_key.json）升级兼容：键无 provider 后缀，第二份仍命中；
4. 缓存文件损坏 → 当作未命中并重新生成，不抛异常；
5. 大内容走 gzip 分支 → 第二份仍命中（压缩路径与明文路径同契约）；
6. 并发两份报告 → 不抛异常且缓存可用（原子写）；
7. LLM 调用失败 → 不写缓存，下次仍会重试。
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from src.test.unit.llm._cache_helpers import (
    LLM_REPLY_DEFAULT,
    MODULE_INDEX,
    make_inputs,
    run_generate_all_llm,
)

# `unit_core` 横切标记：缓存命中契约属核心基础设施行为，需随 P0 `dev-verify` 跑
# （该档选择面不含 `unit_llm`，只标 llm 域会让这批回归只在 P1 才执行）。
pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]

_IDX_LOCAL = MODULE_INDEX

_SETTINGS_V2 = {
    "schema_version": 2,
    "modules": {
        "global_macro": {"enabled": True},
        "expert_review": {"enabled": True},
        "health_check": {"enabled": True},
        "penetration_deep": {"enabled": True},
        "news_correlation": {"enabled": False},
        "self_review": {"enabled": False},
        "holding_change": {"enabled": False},
    },
    "runtime": {"max_concurrency": 2},
}

_PROVIDERS = {
    "strategy": "priority",
    "preferred_providers": {},
    "providers": [
        {"name": "probe-main", "provider": "claude", "credentials_ref": "probe-main", "priority": 10},
        {"name": "probe-backup", "provider": "claude", "credentials_ref": "probe-backup", "priority": 20},
    ],
}

_KEYS = {
    "provider": "claude",
    "api_key": "sk-probe",
    "model": "probe-model",
    "endpoint": "https://example.invalid/v1/messages",
    "probe-main": {
        "provider": "claude",
        "api_key": "sk-probe",
        "model": "probe-model",
        "endpoint": "https://example.invalid/v1/messages",
    },
    "probe-backup": {
        "provider": "claude",
        "api_key": "sk-probe",
        "model": "probe-model",
        "endpoint": "https://example.invalid/v1/messages",
    },
}


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture()
def real_config(tmp_path, monkeypatch):
    """把三个 LLM 配置文件指向 tmp，并清掉配置缓存（走真实加载链路）。"""
    from src.python import config as cfg
    from src.python.config import _core

    settings = _write(tmp_path / "config" / "llm_settings.json", _SETTINGS_V2)
    providers = _write(tmp_path / "config" / "llm_providers.json", _PROVIDERS)
    keys = _write(tmp_path / "config" / "llm_key.json", _KEYS)
    cfg.set_config("llm_settings_file", settings)
    cfg.set_config("llm_providers_file", providers)
    cfg.set_config("llm_key_file", keys)
    _core._clear_config_cache()
    cfg.invalidate_llm_config_cache()
    yield {"settings": settings, "providers": providers, "keys": keys, "dir": tmp_path}
    _core._clear_config_cache()
    cfg.invalidate_llm_config_cache()


def _run(
    inputs: dict,
    reply=None,
    error: BaseException | None = None,
    *,
    patch_call: bool = True,
) -> tuple[bool, bool, bool, bool]:
    """真实配置链路的编排调用：只 mock 网络层，配置从磁盘文件加载。

    `patch_call=False` 供并发用例在外部单点 patch（多线程各自 patch 同一目标会让
    mock 的保存/恢复交错，`call_llm` 会永久留在 Mock 上）。
    """
    return run_generate_all_llm(
        inputs,
        reply=reply,
        error=error,
        patch_config=False,
        patch_call=patch_call,
    )


def _cache_files(llm_cache_dir: Path) -> list[Path]:
    return sorted(llm_cache_dir.glob("*.json*")) if llm_cache_dir.exists() else []


class TestRealConfigChain:
    def test_second_report_hits_with_real_settings_files(self, real_config, llm_cache_dir):
        """真实 v2 嵌套配置 + 多链 → 第二份预检 4/4 命中。"""
        base = make_inputs()
        assert not any(_run(base)), "首份不应命中"
        assert all(_run(base)), "第二份应全部命中"

    def test_disk_key_matches_precheck_key_plus_version(self, real_config, llm_cache_dir, caplog):
        """端到端同源：预检实际使用的键 + 缓存键版本 = 磁盘上的文件名。

        交叉比对两个独立来源（预检命中日志 vs 缓存目录文件名）：预检或写侧任何一侧
        漏拼/多拼一段（如 provider 后缀）都会在此暴露。
        """
        import logging

        from src.python.cache._paths import _CACHE_KEY_VERSION

        base = make_inputs()
        _run(base)
        with caplog.at_level(logging.DEBUG, logger="invest"):
            _run(base)
        hit_keys = [r.args[0] for r in caplog.records if r.getMessage().startswith("缓存命中:") and r.args]
        names = [p.name for p in _cache_files(llm_cache_dir)]
        assert hit_keys, "第二份报告应产生缓存命中日志"
        for key in hit_keys:
            assert f"{key}_{_CACHE_KEY_VERSION}.json" in names, f"预检键 {key} 无对应磁盘文件：{names}"

    def test_single_provider_key_has_no_suffix_and_still_hits(self, real_config, llm_cache_dir):
        """单 Provider 配置（无 llm_providers.json）：键不加后缀，升级后旧缓存仍命中。"""
        from src.python import config as cfg
        from src.python.config import _core

        Path(real_config["providers"]).unlink()
        _core._clear_config_cache()
        cfg.invalidate_llm_config_cache()

        base = make_inputs()
        _run(base)
        names = [p.name for p in _cache_files(llm_cache_dir)]
        assert any("_probe-main" not in n and "llm_global_macro" in n for n in names), names
        assert all(_run(base)), "单 Provider 第二份应命中"


class TestCacheFileRobustness:
    def test_corrupt_cache_is_miss_not_crash(self, real_config, llm_cache_dir):
        base = make_inputs()
        _run(base)
        victim = next(p for p in _cache_files(llm_cache_dir) if "llm_global_macro" in p.name)
        victim.write_text("{ this is not json", encoding="utf-8")
        flags = _run(base)
        assert flags[0] is False, "损坏缓存必须按未命中处理"
        assert victim.exists(), "重新生成后应重写该缓存"
        assert json.loads(victim.read_text(encoding="utf-8")), "重写内容应可解析"

    def test_large_content_uses_gzip_and_still_hits(self, real_config, llm_cache_dir):
        """超过压缩阈值的内容走 `.json.gz`，第二份仍命中（压缩路径同契约）。"""
        big = "<p>" + ("长内容" * 20000) + "</p>"
        base = make_inputs()
        _run(base, reply=(big, {"input_tokens": 1, "output_tokens": 1}, LLM_REPLY_DEFAULT[2]))
        names = [p.name for p in _cache_files(llm_cache_dir)]
        assert any(n.endswith(".json.gz") for n in names), names
        assert all(_run(base)), "gzip 缓存第二份应命中"

    def test_failed_call_does_not_cache(self, real_config, llm_cache_dir):
        """LLM 调用失败 → 不落缓存，下次仍重试。"""
        base = make_inputs()
        _run(base, error=RuntimeError("boom"))
        failed_names = [p.name for p in _cache_files(llm_cache_dir) if "llm_global_macro" in p.name]
        assert failed_names == [], f"失败结果不得入缓存：{failed_names}"
        # 失败后重跑：先正常生成（未命中），再下一份才命中——失败不留毒缓存
        assert not any(_run(base)), "失败后首次重跑必须真实调用而非命中"
        assert all(_run(base)), "重跑成功后第三份应命中"


class TestConcurrency:
    def test_two_threads_same_inputs(self, real_config, llm_cache_dir):
        """并发两份报告：不抛异常，缓存可读（原子写不得产生半写文件）。"""
        base = make_inputs()
        errors: list[BaseException] = []

        def _worker() -> None:
            try:
                _run(base, patch_call=False)
            except BaseException as exc:  # noqa: BLE001 — 收集后再断言
                errors.append(exc)

        threads = [Thread(target=_worker) for _ in range(2)]
        # 单点 patch（主线程）：多线程各自 patch 同一目标会让 mock 的保存/恢复交错
        with patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_DEFAULT):
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, f"并发执行异常：{errors}"
        assert all(_run(base)), "并发后第三份应命中"


class TestFailoverWriteThrough:
    def test_write_key_follows_actual_provider(self, real_config, llm_cache_dir):
        """主 provider 失败、备 provider 成功 → 落盘键带**实际** provider 名。

        下一轮预检按首选 provider 读不到（乐观预检键不同）→ 会重新调用，这是
        刻意的：不把备链产出的结论当成主链缓存复用。
        """
        from src.python.cache._paths import _CACHE_KEY_VERSION

        base = make_inputs()
        reply_backup = (
            "<p>备链产出</p>",
            {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0},
            {"name": "probe-backup", "model": "probe-model", "endpoint": "https://example.invalid"},
        )
        _run(base, reply=reply_backup)
        names = [p.name for p in _cache_files(llm_cache_dir)]
        assert any(n.endswith(f"_probe-backup_{_CACHE_KEY_VERSION}.json") for n in names), names
        assert not any(n.endswith(f"_probe-main_{_CACHE_KEY_VERSION}.json") for n in names), names


class TestModuleEnableToggle:
    def test_disabled_module_is_not_generated_or_cached(self, real_config, llm_cache_dir):
        """`enabled_llm.x=false` → 该模块不生成、不落盘。"""
        from src.python import config as cfg
        from src.python.config import _core

        doc = json.loads(Path(real_config["settings"]).read_text(encoding="utf-8"))
        doc["modules"]["penetration_deep"]["enabled"] = False
        Path(real_config["settings"]).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        _core._clear_config_cache()
        cfg.invalidate_llm_config_cache()

        flags = _run(make_inputs())
        assert flags[_IDX_LOCAL["penetration_deep"]] is False
        names = [p.name for p in _cache_files(llm_cache_dir)]
        assert not any("llm_penetration_deep" in n for n in names), names


class TestHitContentConsistency:
    def test_second_report_returns_same_content(self, real_config, llm_cache_dir):
        """命中缓存返回的内容与首次生成逐字节一致（除页脚时间信息相同）。"""
        from src.python.llm import generators_orchestrator as go

        base = make_inputs()
        with patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_DEFAULT):
            first = go.generate_all_llm(
                base["a_indices"],
                base["us_indices"],
                120.0,
                100.0,
                20.0,
                1.0,
                1,
                base["categories"],
                penetrated_assets=base["penetrated_assets"],
                holdings_details=base["holdings_details"],
                pipeline_data=base["pipeline_data"],
                history_data=base["history_data"],
            )
            second = go.generate_all_llm(
                base["a_indices"],
                base["us_indices"],
                120.0,
                100.0,
                20.0,
                1.0,
                1,
                base["categories"],
                penetrated_assets=base["penetrated_assets"],
                holdings_details=base["holdings_details"],
                pipeline_data=base["pipeline_data"],
                history_data=base["history_data"],
            )
        assert second[4:8] == (True, True, True, True)
        # 命中路径会在页脚追加缓存标记（「…缓存（原始模型：m）」），正文主体必须一致
        body = lambda text: text.split('<p style="color:#888')[0]  # noqa: E731
        assert body(first[0]) == body(second[0]), "命中内容正文应与首次生成一致"
        assert second[0] != first[0], "命中路径应追加缓存来源标记（可观测）"
