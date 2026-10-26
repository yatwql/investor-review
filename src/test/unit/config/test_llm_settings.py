"""LLM 设置单元测试 — write_llm_settings 注释保留 / 原子写 / 缓存刷新 + 合并缓存失效。

合并缓存失效三面：判据覆盖三合并输入文件（含 llm_providers.json）、
写原语写后主动失效、面板 reorder 同进程可见（手工改 / 互换后无需重启）。

TUI 与 Web 配置编辑共用的 llm_settings.json 写入原语（自 tui/handlers_config 抽取）。
"""

from __future__ import annotations

import json
import logging
import os
import time

import pytest

from src.python.config._llm_settings import write_llm_settings

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestWriteLlmSettingsShared:
    """write_llm_settings：字段级替换保留注释 + 原子写 + 刷新 LLM 配置缓存。"""

    @staticmethod
    def _v2_text() -> str:
        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

        return _get_default_llm_settings_template()

    def test_scalar_change_preserves_comments(self, tmp_path):
        """标量字段替换：保留文件内的中文分类注释与未变更字段。"""
        path = tmp_path / "llm_settings.json"
        path.write_text("// 全局说明\n" + self._v2_text(), encoding="utf-8")

        write_llm_settings({"llm_max_concurrency": 5}, str(path))

        raw = path.read_text(encoding="utf-8")
        assert "// 全局说明" in raw
        assert "运行约束" in raw  # 生成器分类注释仍在
        assert '"max_concurrency": 5' in raw
        assert '"max_tokens": 36000' in raw  # 未变更模块参数原样保留

    def test_dict_change_keeps_other_keys(self, tmp_path):
        """enabled_llm 更新只改模块启停，其余顶层键与未知键保留。"""
        path = tmp_path / "llm_settings.json"
        path.write_text(
            self._v2_text().replace("{", '{\n  "model": "claude",', 1),
            encoding="utf-8",
        )

        write_llm_settings({"enabled_llm": {"global_macro": False}}, str(path))

        from src.python.core.json_comments import loads

        data = loads(path.read_text(encoding="utf-8"))
        assert data["model"] == "claude"
        assert data["modules"]["global_macro"]["enabled"] is False
        assert data["modules"]["expert_review"]["enabled"] is True

    def test_dict_change_keeps_file_indent_style(self, tmp_path):
        """文本 patch 不改动既有排版（模块字段缩进保持 6 空格）。"""
        path = tmp_path / "llm_settings.json"
        path.write_text(self._v2_text(), encoding="utf-8")
        before = next(line for line in path.read_text(encoding="utf-8").splitlines() if '"max_tokens"' in line)
        indent_before = len(before) - len(before.lstrip())

        write_llm_settings({"enabled_llm": {"global_macro": False}}, str(path))

        after = next(line for line in path.read_text(encoding="utf-8").splitlines() if '"max_tokens"' in line)
        assert len(after) - len(after.lstrip()) == indent_before

    def test_create_when_missing(self, tmp_path):
        """文件不存在：按 v2 模板创建（含中文注释），落盘值经展平可见。"""
        path = tmp_path / "nested" / "llm_settings.json"

        write_llm_settings({"enabled_llm": {"news_correlation": True}}, str(path))

        raw = path.read_text(encoding="utf-8")
        from src.python.config._llm_schema import flatten
        from src.python.core.json_comments import loads

        doc = loads(raw)
        assert doc["schema_version"] == 2
        assert "//" in raw
        assert flatten(doc)["enabled_llm"]["news_correlation"] is True

    def test_refreshes_llm_cache(self, tmp_path, monkeypatch):
        """写入完成后刷新 LLM 配置缓存（get_llm_config 被调用）。"""
        path = tmp_path / "llm_settings.json"
        path.write_text(self._v2_text(), encoding="utf-8")

        import src.python.config._llm_settings as llm_mod

        calls = []
        monkeypatch.setattr(llm_mod, "get_llm_config", lambda: calls.append(1) or None)

        write_llm_settings({"max_retries": 3}, str(path))

        assert calls == [1]


class TestTokenCapHeadroom:
    """模块 token 上限基线：思考型模型须给正文留余量（防「思考耗尽 max_tokens」）。

    背景：`max_tokens_{module}` 是 thinking + 正文**共享预算**。实测智囊团复盘
    在预算偏紧时思考占满预算、响应无正文（日志「LLM 输出思考部分耗尽 max_tokens
    预算，未生成最终文本」），程序只能关闭 thinking 重试一次（多一次调用）。
    2026-09-16 按 +50% 整体上调各模块 max_tokens / thinking_budget，本用例锁定基线，
    防止误改回旧值导致思考耗尽复发。
    """

    EXPECTED = {
        "max_tokens_global_macro": 3072,
        "thinking_budget_global_macro": 6000,
        "max_tokens_expert_review": 36000,
        "thinking_budget_expert_review": 24000,
        "max_tokens_health_check": 24000,
        "thinking_budget_health_check": 18000,
        "max_tokens_penetration_deep": 12288,
        "thinking_budget_penetration_deep": 12000,
        "max_tokens_news_correlation": 3000,
        "thinking_budget_news_correlation": 6000,
    }

    def test_module_token_caps_match_baseline(self):
        """各模块 max_tokens / thinking_budget 默认值须为 +50% 后的基线值。"""
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        actual = {k: _DEFAULT_LLM_SETTINGS[k] for k in self.EXPECTED}
        assert actual == self.EXPECTED

    def test_thinking_enabled_modules_keep_body_headroom(self):
        """开启 thinking 的模块：max_tokens 必须大于 thinking_budget（否则无正文余量）。"""
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        d = _DEFAULT_LLM_SETTINGS
        for module in ("expert_review", "health_check"):
            assert d[f"thinking_enabled_{module}"] is True, f"{module} 应默认开启 thinking"
            assert d[f"max_tokens_{module}"] > d[f"thinking_budget_{module}"], (
                f"{module}: max_tokens({d[f'max_tokens_{module}']}) 须大于 "
                f"thinking_budget({d[f'thinking_budget_{module}']})，否则思考会占满预算"
            )

    def test_debate_stage_caps_sized_for_thinking(self):
        """辩论每阶段上限与总预算：18432/72000（三段 3×18432=55296 < 72000，守卫不早trigger）。"""
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        debate = _DEFAULT_LLM_SETTINGS["debate"]
        assert debate["procon"]["per_call_max_tokens"] == 18432
        assert debate["max_total_tokens_per_report"] == 72000
        assert 3 * debate["procon"]["per_call_max_tokens"] < debate["max_total_tokens_per_report"]


class TestFullFailRetryDelayDeclared:
    """全链延迟重试等待键须为已登记 llm_settings 键。

    回归：该键曾被 ``skeleton._execute_llm_with_finalize`` 直接读取、却不在
    ``_DEFAULT_LLM_SETTINGS`` 中——用户在 llm_settings.json 设置它会触发
    「未知配置项…请核对后删除」告警，与消费端的实际读取相矛盾。
    """

    def test_defaults_all_known_and_key_not_reported_unknown(self, caplog):
        from src.python.config._llm_settings import _KNOWN_LLM_SETTINGS_KEYS
        from src.python.config._llm_settings import _check_unknown_llm_keys
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        # 默认集中每个键都须已知（否则用户照默认写进文件即被判「未知配置项」）
        assert set(_DEFAULT_LLM_SETTINGS) <= _KNOWN_LLM_SETTINGS_KEYS
        with caplog.at_level(logging.WARNING):
            _check_unknown_llm_keys({"llm_full_fail_retry_delay": 5})
        assert not [r for r in caplog.records if "未知配置项" in r.getMessage()]


# ── 合并缓存失效（三合并输入文件判据 / 写原语写后失效 / 同进程可见） ──────


def _seed_merged_inputs(tmp_path, monkeypatch):
    """llm_settings/llm_key/llm_providers 三文件落临时目录并重定向读取器（隔离真实配置）。"""
    import src.python.config._llm_providers as providers_mod
    import src.python.config._llm_settings as settings_mod
    from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS

    settings_path = tmp_path / "llm_settings.json"
    key_path = tmp_path / "llm_key.json"
    providers_path = tmp_path / "llm_providers.json"
    from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

    settings_path.write_text(_get_default_llm_settings_template(), encoding="utf-8")
    key_path.write_text(json.dumps({"legacy-default": {"api_key": "test-key"}}, ensure_ascii=False), encoding="utf-8")
    providers_path.write_text(json.dumps(_DEFAULT_LLM_PROVIDERS, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(settings_mod, "get_llm_settings_path", lambda: str(settings_path))
    monkeypatch.setattr(providers_mod, "_get_llm_key_path", lambda: str(key_path))
    monkeypatch.setattr(providers_mod, "_get_llm_providers_path", lambda: str(providers_path))
    return providers_path


@pytest.fixture(autouse=True)
def _reset_merged_llm_cache():
    """合并缓存状态隔离（本文件用例直读模块级缓存断言，前后清空防串扰）。"""
    from src.python.config._llm_settings import invalidate_llm_config_cache

    invalidate_llm_config_cache()
    yield
    invalidate_llm_config_cache()


class TestMergedCacheInvalidation:
    """合并缓存失效三面：判据覆盖三文件 / 写原语写后失效 / 面板重排同进程可见。"""

    @staticmethod
    def _first_two_swapped():
        """模板前两条线路 priority 对换（模板保证 ≥2 条且数值互异）。"""
        from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS

        entries = _DEFAULT_LLM_PROVIDERS["providers"]
        assert entries[0]["priority"] != entries[1]["priority"]
        return entries

    def test_manual_providers_edit_bypasses_merge_cache(self, tmp_path, monkeypatch):
        """手工改 providers（等长对换 priority）后，下一次合并读取立见新值。"""
        from src.python.config._llm_settings import get_llm_config

        providers_path = _seed_merged_inputs(tmp_path, monkeypatch)
        entries = self._first_two_swapped()
        before = {p["name"]: p["priority"] for p in entries}
        after = {p["name"]: p["priority"] for p in entries}
        after[entries[0]["name"]], after[entries[1]["name"]] = entries[1]["priority"], entries[0]["priority"]

        first = get_llm_config()
        assert first is not None
        assert {p["name"]: p["priority"] for p in first["_provider_list"]} == before

        # 等长对换（位数相同 → size 不变）+ 显式前移 mtime（不依赖文件系统时间粒度）
        raw = json.loads(providers_path.read_text(encoding="utf-8"))
        raw["providers"][0]["priority"], raw["providers"][1]["priority"] = (
            entries[1]["priority"],
            entries[0]["priority"],
        )
        providers_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        future = time.time() + 2
        os.utime(providers_path, (future, future))

        second = get_llm_config()
        assert second is not None
        assert {p["name"]: p["priority"] for p in second["_provider_list"]} == after

    def test_write_primitive_invalidates_merge_cache(self, tmp_path, monkeypatch):
        """写原语落盘后合并缓存立即置空（主动失效，不等 mtime 判据追赶）。"""
        import src.python.config._llm_settings as settings_mod
        from src.python.config._llm_providers import write_llm_providers
        from src.python.config._llm_settings import get_llm_config

        providers_path = _seed_merged_inputs(tmp_path, monkeypatch)
        get_llm_config()  # 预热合并缓存
        assert settings_mod._llm_config_cache is not None

        entries = self._first_two_swapped()
        raw = json.loads(providers_path.read_text(encoding="utf-8"))
        raw["providers"][0]["priority"], raw["providers"][1]["priority"] = (
            entries[1]["priority"],
            entries[0]["priority"],
        )
        write_llm_providers({"providers": raw["providers"]}, str(providers_path))

        assert settings_mod._llm_config_cache is None  # 写后立即置空
        refreshed = get_llm_config()
        by_name = {p["name"]: p["priority"] for p in refreshed["_provider_list"]}
        assert by_name[entries[0]["name"]] == entries[1]["priority"]
        assert by_name[entries[1]["name"]] == entries[0]["priority"]

    def test_reorder_action_visible_to_merged_read(self, tmp_path, monkeypatch):
        """面板重排（共享编辑层 reorder）后，同进程合并读取立见归一化新链序。"""
        from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS
        from src.python.config._llm_settings import get_llm_config
        from src.python.config.edit_ops import apply_config_edit

        _seed_merged_inputs(tmp_path, monkeypatch)
        order = [p["name"] for p in reversed(_DEFAULT_LLM_PROVIDERS["providers"])]
        expected = {name: 10 * (i + 1) for i, name in enumerate(order)}

        apply_config_edit({"key": "llm_providers.priority", "action": "reorder", "order": order})

        second = get_llm_config()
        assert second is not None
        assert {p["name"]: p["priority"] for p in second["_provider_list"]} == expected


class TestWriteLlmProvidersFilePermission:
    """write_llm_providers 写盘后凭据文件权限收紧为仅所有者可读写（0o600）。

    llm_providers.json 含 api_key，与 cache 域敏感文件同标准；
    非 POSIX 平台不支持完整 chmod，跳过断言。
    """

    @pytest.mark.skipif(os.name != "posix", reason="POSIX 文件权限语义")
    def test_written_file_restricted_to_owner_only(self, tmp_path):
        """新写文件权限为 0o600（组/其他位全部剥离）。"""
        import stat

        from src.python.config._llm_providers import write_llm_providers

        path = tmp_path / "llm_providers.json"
        write_llm_providers({"providers": []}, str(path))

        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    @pytest.mark.skipif(os.name != "posix", reason="POSIX 文件权限语义")
    def test_rewrite_tightens_existing_broad_mode(self, tmp_path):
        """已存在的宽权限文件重写后同样收紧（chmod 在写盘后执行）。"""
        import stat

        from src.python.config._llm_providers import write_llm_providers

        path = tmp_path / "llm_providers.json"
        path.write_text(json.dumps({"providers": []}), encoding="utf-8")
        os.chmod(path, 0o644)

        write_llm_providers({"providers": []}, str(path))

        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
