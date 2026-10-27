"""Web 配置编辑模块测试（web/config_edit.py + GET/POST /api/config/edit 路由）。

覆盖设计矩阵 T1~T10：白名单完备 / 隐藏 LLM 键拒绝 / 面板全量读取 / 标量写 /
嵌套 dict 写（子模块 + 对比指数池增删重置）/ llm_settings 写 / features 写 /
校验与守卫（未知键/类型/枚举/同源 403/写失败 500）/ 写前 .bak 备份。

隔离（conftest _isolate_sensitive_paths）：config.json / llm_settings.json /
features.json 均已重定向到临时目录，本测试不触碰真实 data/config/。
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.web.app import create_app
from src.python.web.config_edit import config_edit_whitelist
from src.python.web.runs import RunManager

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """构造 Flask test_client（fake executor 管线，配置路径已由 conftest 隔离）。"""
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
    invalidate_config_cache()

    rm = RunManager(executor=lambda state, params: 0)
    app = create_app(rm)
    app.config["TESTING"] = True
    return app.test_client()


class TestApplyScalarWrite:
    """T4：标量/枚举编辑走对应写入原语，写后读回正确。"""

    def test_holdings_dir_write(self, app_client):
        """holdings_dir 写：set_config 单键 patch，写后 get_config 读回。"""
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "holdings_dir", "value": "/tmp/config-edit-holdings"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["key"] == "holdings_dir"
        assert data["value"] == "/tmp/config-edit-holdings"

        from src.python.config import get_config

        assert get_config()["holdings_dir"] == "/tmp/config-edit-holdings"

    def test_enable_news_write(self, app_client):
        """enable_news 写：bool 值持久化到 config.json。"""
        resp = app_client.post("/api/config/edit", json={"key": "enable_news", "value": False})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is False

        from src.python.config import get_config

        assert get_config()["enable_news"] is False

    def test_anonymization_mode_write(self, app_client):
        """anonymization.mode 写：set_anonymization_mode（写顶层键），读回生效。"""
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "anonymization.mode", "value": "code_display"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] == "code_display"

        from src.python.config.anonymizer import get_anonymization_mode

        assert get_anonymization_mode() == "code_display"


class TestApplyLlmSettingsWrite:
    """T6：enabled_llm 写 llm_settings.json（注释保留 + 原子写）。"""

    def test_enabled_llm_write_preserves_comments(self, app_client):
        """enabled_llm.news_correlation 写：文件注释保留，字段更新。"""
        from src.python.config._llm_settings import get_llm_settings_path

        from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

        path = get_llm_settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = _get_default_llm_settings_template().replace("{", '{\n  "// 模型配置": true, // 模型配置', 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

        resp = app_client.post(
            "/api/config/edit",
            json={"key": "enabled_llm.news_correlation", "value": True},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is True

        raw = open(path, encoding="utf-8").read()
        assert "// 模型配置" in raw  # 注释保留
        assert '"// 模型配置": true' in raw  # 其余键保留
        assert '"enabled": true' in raw  # 字段更新


class TestApplyFeaturesWrite:
    """T7：实验性功能开关写 features.json（save_feature_overrides + 运行时生效）。"""

    def test_debate_flag_write_takes_effect(self, app_client):
        """llm_debate_conditional 写：features.json 含覆写，运行时开关生效。"""
        from src.python.config.features import FEATURES_FILE, is_feature_enabled

        assert is_feature_enabled("llm_debate_conditional") is True  # 转正后默认开

        resp = app_client.post(
            "/api/config/edit",
            json={"key": "llm_debate_conditional", "value": False},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is False
        assert is_feature_enabled("llm_debate_conditional") is False

        raw = open(FEATURES_FILE, encoding="utf-8").read()
        assert '"llm_debate_conditional": false' in raw

    def test_decision_reflection_flag_write_takes_effect(self, app_client):
        """decision_reflection 写：features.json 含覆写，运行时开关生效。"""
        from src.python.config.features import FEATURES_FILE, is_feature_enabled

        assert is_feature_enabled("decision_reflection") is False  # 默认关

        resp = app_client.post(
            "/api/config/edit",
            json={"key": "decision_reflection", "value": True},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is True
        assert is_feature_enabled("decision_reflection") is True

        raw = open(FEATURES_FILE, encoding="utf-8").read()
        assert '"decision_reflection": true' in raw

    def test_deterministic_signal_flag_write_takes_effect(self, app_client):
        """deterministic_signal 写：features.json 含覆写，运行时开关生效。"""
        from src.python.config.features import FEATURES_FILE, is_feature_enabled

        assert is_feature_enabled("deterministic_signal") is True  # 转正后默认开

        resp = app_client.post(
            "/api/config/edit",
            json={"key": "deterministic_signal", "value": False},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is False
        assert is_feature_enabled("deterministic_signal") is False

        raw = open(FEATURES_FILE, encoding="utf-8").read()
        assert '"deterministic_signal": false' in raw

    def test_standard_switch_write_takes_effect(self, app_client):
        """常规开关（持仓成本区间位置）写：features.json 含覆写，运行时开关生效。

        缺陷场景：非实验开关曾无任何界面通道，用户只能手改 features.json；
        本用例锁定 Web 面板对常规（非实验）开关的写入路径与实验项同源可用。
        """
        from src.python.config.features import FEATURES_FILE, is_feature_enabled

        assert is_feature_enabled("cost_position") is True  # 默认开

        resp = app_client.post("/api/config/edit", json={"key": "cost_position", "value": False})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"] is False
        assert is_feature_enabled("cost_position") is False

        raw = open(FEATURES_FILE, encoding="utf-8").read()
        assert '"cost_position": false' in raw


# ═══════════════════════════════════════════════════════════════
# T9 校验与守卫
# ═══════════════════════════════════════════════════════════════


class TestValidationAndGuard:
    """T9：未知键/类型/枚举/comparison 非法 → 400；同源失败 → 403；写失败 → 500。"""

    def test_unknown_key_400(self, app_client):
        """未知点分键 → 400 BAD_PARAM（不落盘）。"""
        resp = app_client.post("/api/config/edit", json={"key": "no_such_key", "value": "x"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    @pytest.mark.parametrize(
        "payload",
        [
            {"key": "enable_news", "value": 1},  # 伪 bool int
            {"key": "enable_news", "value": "true"},  # 伪 bool str
            {"key": "enable_news"},  # 缺 value
            {"key": "holdings_dir", "value": ""},  # 空串
            {"key": "holdings_dir", "value": "   "},  # 纯空白
            {"key": "holdings_filename", "value": "sub/持仓.xlsx"},  # 含路径分隔符
            {"key": "anonymization.mode", "value": "bogus"},  # 非法枚举
        ],
    )
    def test_invalid_value_400(self, app_client, payload):
        """类型/格式/枚举校验失败 → 400 BAD_PARAM。"""
        resp = app_client.post("/api/config/edit", json=payload)
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    @pytest.mark.parametrize(
        "payload",
        [
            {"key": "comparison_indices", "action": "add", "code": "ab", "name": "x"},  # code <3
            {"key": "comparison_indices", "action": "add", "code": "../sh000300", "name": "x"},  # 非法字符
            {"key": "comparison_indices", "action": "add", "code": "sh000300", "name": ""},  # 空名称
            {"key": "comparison_indices", "action": "add", "code": "sh000300", "name": "   "},  # 空白名称
            {"key": "comparison_indices", "action": "remove", "code": "not_exists"},  # 不在池
            {"key": "comparison_indices", "action": "bogus"},  # 非法 action
        ],
    )
    def test_comparison_invalid_400(self, app_client, payload):
        """对比指数池 action/code/name 校验失败 → 400 BAD_PARAM。"""
        resp = app_client.post("/api/config/edit", json=payload)
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_add_duplicate_code_400(self, app_client):
        """重复 add 已在池中的 code → 400。"""
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "comparison_indices", "action": "add", "code": "sh000300", "name": "沪深300"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_cross_origin_403(self, app_client):
        """非同一来源（伪造 Origin）→ 403 BAD_PARAM。"""
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "enable_news", "value": True},
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_write_failure_500(self, app_client):
        """写入原语抛异常 → 500 CONFIG_WRITE_FAILED（详情记日志）。"""
        with patch("src.python.config.set_config", side_effect=OSError("disk full")):
            resp = app_client.post("/api/config/edit", json={"key": "enable_news", "value": True})
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "CONFIG_WRITE_FAILED"

    def test_non_dict_payload_400(self, app_client):
        """请求体非 JSON object → 400 BAD_PARAM。"""
        resp = app_client.post(
            "/api/config/edit",
            data=json.dumps(["enable_news", True]),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"


# ═══════════════════════════════════════════════════════════════
# T10 写前 .bak 备份（单槽轮转）
# ═══════════════════════════════════════════════════════════════


class TestConfigBackup:
    """T10：写共享配置前单槽 .bak 备份。"""

    def test_backup_created_on_first_write(self, app_client):
        """已有 config.json 时写前生成 .bak，内容=写前旧值；新值落盘。"""
        from src.python.config._config_defaults import get_config_path

        path = get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"enable_news": True}, f, ensure_ascii=False)
        invalidate_config_cache()

        resp = app_client.post("/api/config/edit", json={"key": "enable_news", "value": False})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["backup"] == path + ".bak"

        bak = json.loads(open(path + ".bak", encoding="utf-8").read())
        assert bak["enable_news"] is True  # 备份写前旧值
        current = json.loads(open(path, encoding="utf-8").read())
        assert current["enable_news"] is False

    def test_backup_none_when_file_missing(self, app_client):
        """首次写入（无原文件）→ backup=None。"""
        resp = app_client.post("/api/config/edit", json={"key": "enable_news", "value": False})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["backup"] is None


class TestReportScopeOverWeb:
    """报告产物开关：经 features 通道读写（作用域横跨分析增强 / 独立章两组）。"""

    def test_whitelist_has_bare_flag_keys_not_config_paths(self):

        assert not [k for k in config_edit_whitelist if k.startswith("report_submodules.")], "旧 config 路径应已移除"
        for flag in ("summary_highlights", "market_temperature", "stock_fundamentals"):
            assert config_edit_whitelist[flag] == {"kind": "bool", "target": "features", "writer": "features"}

    def test_surface_groups_derive_from_registry(self):
        from src.python.config.features import GROUP_LABELS, GROUP_ORDER, experimental_flags, switches_in_group
        from src.python.web.config_edit import get_config_edit_surface

        surface = get_config_edit_surface()
        features = surface["features"]
        assert [g["key"] for g in features["groups"]] == list(GROUP_ORDER)
        for group in features["groups"]:
            assert group["title"] == GROUP_LABELS[group["key"]]
            assert set(group["switches"]) == {flag for flag, _d in switches_in_group(group["key"])}
            assert "labels" not in group  # 显示名由 features.labels 同源下发
        assert set(features["experimental"]) == {flag for flag, _d in experimental_flags()}

    def test_writing_report_flag_lands_in_features_store(self):
        from src.python.config.features import is_feature_enabled, set_feature_enabled
        from src.python.web.config_edit import apply_config_edit

        set_feature_enabled("cost_lots", False)
        apply_config_edit({"key": "cost_lots", "value": True})
        assert is_feature_enabled("cost_lots") is True
        set_feature_enabled("cost_lots", False)


class TestWebPanelCoversAllSwitches:
    """Web 配置面板的开关面必须覆盖注册表全部开关（四组全覆盖），防渠道层漏渲染。"""

    def test_surface_flags_cover_registry(self):
        from src.python.config.features import feature_switch_registry
        from src.python.web.config_edit import get_config_edit_surface

        surface = get_config_edit_surface()
        shown = set()
        for group in surface["features"]["groups"]:
            shown |= set(group["switches"])
        missing = set(feature_switch_registry) - shown
        assert not missing, f"Web 面板未渲染这些开关：{sorted(missing)}"


class TestLlmProvidersBlock:
    """LLM 多链线路优先级块：GET surface 按 priority 排序展示 + POST reorder 落盘（与 CLI/TUI 同源编辑层）。"""

    @staticmethod
    def _write_providers_file(tmp_path, priorities=(10, 20)) -> str:
        path = os.path.join(str(tmp_path), "llm_providers.json")
        data = {
            "strategy": "priority",
            "providers": [
                {"name": "main", "provider": "claude", "credentials_ref": "env:CRED1", "priority": priorities[0]},
                {"name": "aux", "provider": "openai", "credentials_ref": "env:CRED2", "priority": priorities[1]},
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path

    def test_surface_lists_providers_sorted_by_priority(self, monkeypatch):
        """surface：providers 按 priority 升序（数值小 = 链序靠前），策略一并回传。"""
        fake = {
            "strategy": "weighted",
            "providers": [
                {"name": "b", "provider": "openai", "priority": 20},
                {"name": "a", "provider": "claude", "priority": 10},
            ],
        }
        monkeypatch.setattr("src.python.config.get_llm_providers", lambda: fake)
        from src.python.web.config_edit import get_config_edit_surface

        block = get_config_edit_surface()["llm_providers"]
        assert block["strategy"] == "weighted"
        assert [p["name"] for p in block["providers"]] == ["a", "b"]

    def test_post_reorder_persists(self, app_client, tmp_path, monkeypatch):
        """POST reorder → 200 + 生效 order 回传；文件 priority 归一化为 10/20 写盘。"""
        providers_path = self._write_providers_file(tmp_path)
        monkeypatch.setattr("src.python.config._llm_providers._get_llm_providers_path", lambda: providers_path)
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "llm_providers.priority", "action": "reorder", "order": ["aux", "main"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["value"]["order"] == ["aux", "main"]
        with open(providers_path, encoding="utf-8") as f:
            by_name = {p["name"]: p for p in json.load(f)["providers"]}
        assert by_name["aux"]["priority"] == 10
        assert by_name["main"]["priority"] == 20

    def test_post_reorder_invalid_returns_400(self, app_client, tmp_path, monkeypatch):
        """非置换 order → 400 BAD_PARAM，原文件不动。"""
        providers_path = self._write_providers_file(tmp_path)
        monkeypatch.setattr("src.python.config._llm_providers._get_llm_providers_path", lambda: providers_path)
        resp = app_client.post(
            "/api/config/edit",
            json={"key": "llm_providers.priority", "action": "reorder", "order": ["main"]},
        )
        assert resp.status_code == 400
        with open(providers_path, encoding="utf-8") as f:
            by_name = {p["name"]: p for p in json.load(f)["providers"]}
        assert by_name["main"]["priority"] == 10


class TestLlmTuningSurface:
    """LLM 调优项下发：清单/范围/说明来自共享白名单 `edit_ops.LLM_TUNING_SPECS`。"""

    def test_surface_lists_all_tuning_keys(self):
        from src.python.config.edit_ops import LLM_TUNING_SPECS
        from src.python.web.config_edit import _llm_tuning_surface

        rows = _llm_tuning_surface()
        assert [row["key"] for row in rows] == list(LLM_TUNING_SPECS)
        for row in rows:
            spec = LLM_TUNING_SPECS[row["key"]]
            assert row["min"] == spec["min"] and row["max"] == spec["max"]
            assert row["label"] and row["hint"]
            assert isinstance(row["value"], (int, float))
