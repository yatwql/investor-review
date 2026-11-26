"""TUI 配置面板（`tui/handlers_config`）分支覆盖：会话撤销、编辑派发与各入口面板。

覆盖点：
  - ConfigSession：按键去重计数、逆序撤销、逆操作失败即止
  - `_apply_edit`：成功记录前值供撤销；校验失败走黄色提示；写入异常走 emit_error
  - `u` / `U` 撤销语义（无改动时不得喊「已撤销」）
  - `_edit_single_config`：EOF / 空输入 / 成功三分支，pre_hook 先于提示
  - [G] 全局设置：编号与字母两种入口、无效选择不误派发
  - LLM 调优 / 对比指数池 / 匿名化 / 配置刷新各面板的渲染与派发
"""

from __future__ import annotations

from typing import Any

import pytest

from src.python.config.edit_ops import ConfigEditError
from src.python.tui import handlers_config as hc
from src.python.tui.panel_runtime import NavState

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

#: 面板循环真源模块（`_cmd_config_llm_tuning` 在函数内 import，patch 模块级名字无效）
_PANEL_SOURCE = "src.python.tui.panel_runtime"


@pytest.fixture(autouse=True)
def _deterministic_panel_width(monkeypatch):
    """固定终端宽度：面板版面按列数分档，断言需绑定确定档位。"""
    monkeypatch.setenv("COLUMNS", "120")


def _nav(count: int) -> NavState:
    return NavState(count=count)


class TestConfigSession:
    def test_count_and_keys_dedupe(self):
        session = hc.ConfigSession()
        session.record("a", 1)
        session.record("a", 2)
        session.record("b", 3)

        assert session.count == 2
        assert session.keys == ["a", "b"]

    def test_undo_last_returns_key_and_pops(self, monkeypatch):
        monkeypatch.setattr(hc, "_apply_inverse", lambda payload: True)
        session = hc.ConfigSession()
        session.record("a", 1)

        assert session.undo_last() == "a"
        assert session.undo_last() is None

    def test_undo_last_stops_when_inverse_fails(self, monkeypatch):
        monkeypatch.setattr(hc, "_apply_inverse", lambda payload: False)
        session = hc.ConfigSession()
        session.record("a", 1)

        assert session.undo_last() is None
        assert session.count == 0, "逆操作失败也应出栈，避免同一载荷被反复重放"

    def test_restore_all_counts_successful_keys(self, monkeypatch):
        seen: list[dict] = []

        def _inverse(payload):
            seen.append(payload)
            return payload.get("key") != "bad"

        monkeypatch.setattr(hc, "_apply_inverse", _inverse)
        session = hc.ConfigSession()
        session.record("a", 1)
        session.record("bad", 2)
        session.record("a", 3)

        assert session.restore_all() == 1
        assert [p["key"] for p in seen] == ["a", "bad", "a"], "全量还原必须按逆序重放"

    def test_record_payload_keeps_action_payload(self):
        session = hc.ConfigSession()
        session.record_payload({"key": "idx", "action": "remove", "code": "sh000905"})

        assert session.keys == ["idx"]
        assert session._changes[0].payload["action"] == "remove"


class TestHandleConfigUndo:
    def _session(self, monkeypatch, *, restored: int, undone: str | None) -> hc.ConfigSession:
        session = hc.ConfigSession()
        monkeypatch.setattr(session, "restore_all", lambda: restored)
        monkeypatch.setattr(session, "undo_last", lambda: undone)
        monkeypatch.setattr(hc, "refresh_config", lambda: None)
        return session

    def test_restore_all_reports_count(self, monkeypatch):
        lines: list[str] = []
        session = self._session(monkeypatch, restored=3, undone=None)

        assert hc.handle_config_undo("U", session, lines.append) is True
        assert any("3 项" in line for line in lines)

    def test_restore_all_with_nothing_says_no_change(self, monkeypatch):
        lines: list[str] = []
        session = self._session(monkeypatch, restored=0, undone=None)

        hc.handle_config_undo("U", session, lines.append)

        assert any("尚无改动" in line for line in lines)
        assert not any("已全部还原" in line for line in lines)

    def test_undo_one_reports_key(self, monkeypatch):
        lines: list[str] = []
        session = self._session(monkeypatch, restored=0, undone="holdings_dir")

        assert hc.handle_config_undo("u", session, lines.append) is True
        assert any("holdings_dir" in line for line in lines)

    def test_undo_one_with_nothing_says_no_change(self, monkeypatch):
        lines: list[str] = []
        session = self._session(monkeypatch, restored=0, undone=None)

        hc.handle_config_undo("u", session, lines.append)

        assert any("尚无改动" in line for line in lines)

    def test_other_keys_not_consumed(self, monkeypatch):
        session = self._session(monkeypatch, restored=0, undone=None)

        assert hc.handle_config_undo("1", session, lambda _l: None) is False


class TestApplyEdit:
    def test_success_records_before_value(self, monkeypatch):
        applied: list[dict] = []
        monkeypatch.setattr("src.python.config.edit_ops.apply_config_edit", lambda p: applied.append(p))
        monkeypatch.setattr("src.python.config.edit_ops.read_config_value", lambda key: "旧值")
        monkeypatch.setattr("src.python.tui.status_line.reset_status_memo", lambda: None)
        session = hc.reset_config_session()
        try:
            assert hc._apply_edit({"key": "holdings_dir", "value": "new"}) is True
        finally:
            hc.close_config_session()

        assert applied == [{"key": "holdings_dir", "value": "new"}]
        assert session._changes[0].payload == {"key": "holdings_dir", "value": "旧值"}

    def test_validation_error_prints_yellow_hint(self, monkeypatch, capsys):
        def _reject(_p):
            raise ConfigEditError("值不合法")

        monkeypatch.setattr("src.python.config.edit_ops.apply_config_edit", _reject)

        assert hc._apply_edit({"key": "port", "value": "-1"}) is False
        assert "值不合法" in capsys.readouterr().out

    def test_unexpected_error_routes_to_emit_error(self, monkeypatch):
        errors: list[str] = []
        monkeypatch.setattr(
            "src.python.config.edit_ops.apply_config_edit", lambda _p: (_ for _ in ()).throw(OSError("disk"))
        )
        monkeypatch.setattr(hc, "emit_error", lambda msg, _domain, advice=None: errors.append(msg))

        assert hc._apply_edit({"key": "port", "value": "1"}) is False
        assert errors == ["配置写入失败"]

    def test_read_before_value_failure_does_not_block_write(self, monkeypatch):
        monkeypatch.setattr("src.python.config.edit_ops.apply_config_edit", lambda _p: None)
        monkeypatch.setattr(
            "src.python.config.edit_ops.read_config_value", lambda _k: (_ for _ in ()).throw(KeyError("nope"))
        )
        monkeypatch.setattr("src.python.tui.status_line.reset_status_memo", lambda: None)
        hc.reset_config_session()
        try:
            assert hc._apply_edit({"key": "holdings_dir", "value": "x"}) is True
            assert hc._session.count == 0, "读不到前值时跳过撤销记录，而不是放弃写入"
        finally:
            hc.close_config_session()


class TestApplyInverse:
    def test_success_resets_status_memo(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr("src.python.config.edit_ops.apply_config_edit", lambda _p: calls.append("apply"))
        monkeypatch.setattr("src.python.tui.status_line.reset_status_memo", lambda: calls.append("reset"))

        assert hc._apply_inverse({"key": "a", "value": 1}) is True
        assert calls == ["apply", "reset"]

    def test_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.config.edit_ops.apply_config_edit", lambda _p: (_ for _ in ()).throw(OSError("disk"))
        )

        assert hc._apply_inverse({"key": "a", "value": 1}) is False


class TestEditSingleConfig:
    def _setup(self, monkeypatch, *, inputs: list[Any], applied: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {"applied": []}
        monkeypatch.setattr(
            hc,
            "refresh_config",
            lambda: record.setdefault("refreshed", 0) or record.update(refreshed=record.get("refreshed", 0) + 1),
        )
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"holdings_dir": "data/holdings"})
        monkeypatch.setattr(hc, "input_choice", lambda _p="": inputs.pop(0))
        monkeypatch.setattr(hc, "_apply_edit", lambda payload: (record["applied"].append(payload), applied)[1])
        return record

    def test_eof_returns_silently(self, monkeypatch, capsys):
        self._setup(monkeypatch, inputs=[])
        monkeypatch.setattr(hc, "input_choice", lambda _p="": (_ for _ in ()).throw(EOFError()))

        hc._edit_single_config("holdings_dir", "目录")

        assert "已更新" not in capsys.readouterr().out

    def test_empty_input_keeps_value(self, monkeypatch, capsys):
        record = self._setup(monkeypatch, inputs=[""])

        hc._edit_single_config("holdings_dir", "目录")

        assert record["applied"] == []
        assert "未修改" in capsys.readouterr().out

    def test_value_is_applied_and_confirmed(self, monkeypatch, capsys):
        record = self._setup(monkeypatch, inputs=["data/holdings2"])

        hc._edit_single_config("holdings_dir", "目录")

        assert record["applied"] == [{"key": "holdings_dir", "value": "data/holdings2"}]
        assert "已更新为" in capsys.readouterr().out

    def test_pre_hook_runs_before_prompt(self, monkeypatch):
        self._setup(monkeypatch, inputs=[""])
        order: list[str] = []

        hc._edit_single_config("holdings_dir", "目录", pre_hook=lambda: order.append("hook"))

        assert order == ["hook"]

    def test_failed_apply_prints_no_confirmation(self, monkeypatch, capsys):
        self._setup(monkeypatch, inputs=["x"], applied=False)

        hc._edit_single_config("holdings_dir", "目录")

        assert "已更新为" not in capsys.readouterr().out


class TestSmallHelpers:
    def test_list_xlsx_preview_prints_files(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"holdings_dir": "d"})
        monkeypatch.setattr(hc, "list_xlsx_files", lambda _d: ["/x/a.xlsx", "/x/b.xlsx"])

        hc._list_xlsx_preview()

        out = capsys.readouterr().out
        assert "a.xlsx" in out and "b.xlsx" in out

    def test_list_xlsx_preview_silent_when_empty(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"holdings_dir": "d"})
        monkeypatch.setattr(hc, "list_xlsx_files", lambda _d: [])

        hc._list_xlsx_preview()

        assert capsys.readouterr().out == ""

    def test_dir_commands_delegate(self, monkeypatch):
        seen: list[tuple[str, str]] = []
        monkeypatch.setattr(
            hc, "_edit_single_config", lambda key, label, default="", pre_hook=None: seen.append((key, label))
        )

        hc._cmd_config_dir()
        hc._cmd_config_filename()
        hc._cmd_config_output_dir()

        assert [k for k, _ in seen] == ["holdings_dir", "holdings_filename", "output_dir"]

    def test_entry_map_renders_all_rows_in_box_mode(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "use_panel_box", lambda _c: True)

        hc._render_config_entry_map()

        out = capsys.readouterr().out
        for label, _key, _hint in hc._CONFIG_ENTRY_MAP:
            assert label in out

    def test_entry_map_renders_all_rows_in_narrow_mode(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "use_panel_box", lambda _c: False)

        hc._render_config_entry_map()

        out = capsys.readouterr().out
        for label, _key, _hint in hc._CONFIG_ENTRY_MAP:
            assert label in out


class TestGlobalSettingsPanel:
    def _run(self, monkeypatch, inputs: list[Any]) -> list[str]:
        dispatched: list[str] = []
        for letter, _label, handler, _group in hc.GLOBAL_SETTINGS_ITEMS:
            monkeypatch.setattr(hc, handler, lambda name=handler: dispatched.append(name))
        monkeypatch.setattr("src.python.tui.tui_keys.input_choice", lambda _p="": inputs.pop(0))
        hc._cmd_global_settings()
        return dispatched

    def test_eof_returns(self, monkeypatch):
        dispatched: list[str] = []
        monkeypatch.setattr(hc, "_cmd_config_dir", lambda: dispatched.append("dir"))
        monkeypatch.setattr("src.python.tui.tui_keys.input_choice", lambda _p="": (_ for _ in ()).throw(EOFError()))

        hc._cmd_global_settings()

        assert dispatched == [], "EOF 后不得派发任何配置入口"

    def test_number_dispatches_corresponding_handler(self, monkeypatch):
        dispatched = self._run(monkeypatch, ["1", "0"])

        assert dispatched == ["_cmd_config_dir"]

    def test_letter_dispatches_corresponding_handler(self, monkeypatch):
        dispatched = self._run(monkeypatch, ["m", "0"])

        assert dispatched == ["_render_config_entry_map"]

    def test_invalid_choice_then_return_dispatches_nothing(self, monkeypatch, capsys):
        dispatched = self._run(monkeypatch, ["zzz", "0"])

        assert dispatched == []
        assert "无效选择" in capsys.readouterr().out

    def test_empty_input_returns_without_dispatch(self, monkeypatch):
        assert self._run(monkeypatch, [""]) == []

    def test_out_of_range_number_is_rejected(self, monkeypatch):
        assert self._run(monkeypatch, ["99", "0"]) == []


def _fake_panel_loop(record: dict[str, Any]) -> Any:
    """panel_loop 替身：渲染一次、派发全部 action、喂 on_text 输入。"""

    def _loop(items, *, render=None, on_text=None, **_kwargs):
        record["items"] = list(items)
        record["rendered"] = list(render(_nav(len(items)))) if render else None
        if record.get("dispatch"):
            for item in items:
                if item.action is not None and item.kind != "return":
                    item.action()
        for text in record.get("texts", []):
            if on_text is not None:
                on_text(text)

    return _loop


class TestLlmTuningPanel:
    def test_edit_items_and_provider_entry_dispatch(self, monkeypatch):
        record: dict[str, Any] = {"applied": [], "texts": ["u", "garbage"], "undone": [], "dispatch": True}

        def _undo(text, session, emit):
            record["undone"].append(text)
            return False

        monkeypatch.setattr(_PANEL_SOURCE + ".panel_loop", _fake_panel_loop(record))
        monkeypatch.setattr(hc, "input_choice", lambda _p="", **_k: "3")
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record["applied"].append(p) or True)
        monkeypatch.setattr(hc, "refresh_config", lambda: None)
        monkeypatch.setattr(hc, "handle_config_undo", _undo)
        monkeypatch.setattr(hc, "_cmd_config_llm_providers", lambda: record.setdefault("providers", True))

        hc._cmd_config_llm_tuning()

        assert record["applied"], "侧栏编辑项必须经共享编辑层落盘"
        assert record["undone"] == ["u", "garbage"]
        assert record["providers"] is True, "最后一项应导流到多链线路面板"
        assert hc._session is None, "面板退出必须关闭会话"

    def test_empty_input_keeps_current_value(self, monkeypatch, capsys):
        record: dict[str, Any] = {"applied": [], "dispatch": True}
        monkeypatch.setattr(_PANEL_SOURCE + ".panel_loop", _fake_panel_loop(record))
        monkeypatch.setattr(hc, "input_choice", lambda _p="", **_k: "")
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record["applied"].append(p) or True)
        monkeypatch.setattr(hc, "_cmd_config_llm_providers", lambda: None)
        monkeypatch.setattr(hc, "handle_config_undo", lambda *a: False)

        hc._cmd_config_llm_tuning()

        assert record["applied"] == []
        assert "未修改" in capsys.readouterr().out

    def test_eof_closes_session(self, monkeypatch):
        monkeypatch.setattr(_PANEL_SOURCE + ".panel_loop", lambda *a, **k: (_ for _ in ()).throw(EOFError()))

        hc._cmd_config_llm_tuning()

        assert hc._session is None


class TestComparisonIndexPanel:
    def test_render_and_reset(self, monkeypatch, capsys):
        record: dict[str, Any] = {"applied": [], "dispatch": True}
        monkeypatch.setattr(hc, "panel_loop", _fake_panel_loop(record))
        monkeypatch.setattr(hc, "refresh_config", lambda: None)
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"comparison_indices": {"sh000905": "中证500"}})
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record["applied"].append(p) or True)
        monkeypatch.setattr(hc, "input_choice", lambda _p="", **_k: "")

        hc._cmd_config_comparison_indices()

        assert record["applied"] == [{"key": "comparison_indices", "action": "reset"}]
        out = capsys.readouterr().out
        assert "sh000905" in out

    def test_empty_pool_renders_placeholder(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "panel_loop", _fake_panel_loop({}))
        monkeypatch.setattr(hc, "refresh_config", lambda: None)
        monkeypatch.setattr(hc, "get_config_cache", lambda: {})
        monkeypatch.setattr("src.python.config.get_default", lambda _k: None)
        monkeypatch.setattr(hc, "input_choice", lambda _p="", **_k: "")

        hc._cmd_config_comparison_indices()

        assert "空池" in capsys.readouterr().out

    def test_non_dict_pool_treated_as_empty(self, monkeypatch, capsys):
        monkeypatch.setattr(hc, "panel_loop", _fake_panel_loop({}))
        monkeypatch.setattr(hc, "refresh_config", lambda: None)
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"comparison_indices": ["sh000905"]})
        monkeypatch.setattr(hc, "input_choice", lambda _p="", **_k: "")

        hc._cmd_config_comparison_indices()

        assert "空池" in capsys.readouterr().out


class TestAddComparisonIndex:
    def _run(self, monkeypatch, inputs: list[Any], applied: bool = True) -> list[dict]:
        record: list[dict] = []
        monkeypatch.setattr(hc, "input_choice", lambda _p="": inputs.pop(0))
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record.append(p) or applied)
        hc._add_comparison_index()
        return record

    def test_success_records_add_payload(self, monkeypatch):
        assert self._run(monkeypatch, ["sh000905", "中证500"]) == [
            {"key": "comparison_indices", "action": "add", "code": "sh000905", "name": "中证500"}
        ]

    def test_empty_code_rejected(self, monkeypatch, capsys):
        assert self._run(monkeypatch, [""]) == []
        assert "代码不能为空" in capsys.readouterr().out

    def test_empty_name_rejected(self, monkeypatch, capsys):
        assert self._run(monkeypatch, ["sh000905", ""]) == []
        assert "名称不能为空" in capsys.readouterr().out

    def test_eof_returns_without_error(self, monkeypatch):
        monkeypatch.setattr(hc, "input_choice", lambda _p="": (_ for _ in ()).throw(EOFError()))
        monkeypatch.setattr(hc, "_apply_edit", lambda _p: pytest.fail("EOF 后不得落盘"))

        hc._add_comparison_index()

    def test_none_code_returns(self, monkeypatch):
        monkeypatch.setattr(hc, "input_choice", lambda _p="": None)
        monkeypatch.setattr(hc, "_apply_edit", lambda _p: pytest.fail("None 后不得落盘"))

        hc._add_comparison_index()

    def test_apply_failure_prints_no_confirmation(self, monkeypatch, capsys):
        self._run(monkeypatch, ["sh000905", "中证500"], applied=False)

        assert "已添加" not in capsys.readouterr().out


class TestRemoveComparisonIndex:
    def _run(self, monkeypatch, pool: dict[str, str], choice: Any) -> list[dict]:
        record: list[dict] = []
        monkeypatch.setattr(hc, "input_choice", lambda _p="": choice)
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record.append(p) or True)
        hc._remove_comparison_index(pool)
        return record

    def test_empty_pool_returns_early(self, monkeypatch, capsys):
        assert self._run(monkeypatch, {}, "1") == []
        assert "对比池为空" in capsys.readouterr().out

    def test_invalid_number(self, monkeypatch, capsys):
        assert self._run(monkeypatch, {"sh000905": "中证500"}, "x") == []
        assert "无效编号" in capsys.readouterr().out

    def test_zero_cancels(self, monkeypatch):
        assert self._run(monkeypatch, {"sh000905": "中证500"}, "0") == []

    def test_out_of_range(self, monkeypatch, capsys):
        assert self._run(monkeypatch, {"sh000905": "中证500"}, "7") == []
        assert "编号超出范围" in capsys.readouterr().out

    def test_valid_choice_removes(self, monkeypatch):
        assert self._run(monkeypatch, {"sh000905": "中证500"}, "1") == [
            {"key": "comparison_indices", "action": "remove", "code": "sh000905"}
        ]

    def test_eof_and_none_return_without_write(self, monkeypatch):
        monkeypatch.setattr(hc, "input_choice", lambda _p="": (_ for _ in ()).throw(EOFError()))
        monkeypatch.setattr(hc, "_apply_edit", lambda _p: pytest.fail("EOF 后不得落盘"))
        hc._remove_comparison_index({"sh000905": "中证500"})

        monkeypatch.setattr(hc, "input_choice", lambda _p="": None)
        hc._remove_comparison_index({"sh000905": "中证500"})


class TestRefreshConfig:
    def _stub(self, monkeypatch, *, llm: dict | None) -> list[str]:
        calls: list[str] = []
        for target, label in [
            ("src.python.config.invalidate_config_cache", "invalidate"),
            ("src.python.config.invalidate_llm_config_cache", "invalidate_llm"),
            ("src.python.llm.pricing.reload_pricing", "pricing"),
            ("src.python.fetcher.batch.clear_rate_limiter_cache", "limiter"),
            ("src.python.tui.status_line.reset_status_memo", "status"),
        ]:
            monkeypatch.setattr(target, lambda _label=label: calls.append(_label))
        monkeypatch.setattr(hc, "refresh_config", lambda: calls.append("menu_cache"))
        monkeypatch.setattr("src.python.config.get_config", lambda: {"a": 1})
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: llm)
        monkeypatch.setattr(hc, "get_config_cache", lambda: {"a": 1})
        return calls

    def test_all_caches_invalidated(self, monkeypatch, capsys):
        calls = self._stub(monkeypatch, llm={"model": "x"})

        hc._cmd_refresh_config()

        assert calls == ["invalidate", "invalidate_llm", "status", "pricing", "limiter", "menu_cache"]
        assert "LLM 配置已重新加载" in capsys.readouterr().out

    def test_unconfigured_llm_reports_warning(self, monkeypatch, capsys):
        self._stub(monkeypatch, llm=None)

        hc._cmd_refresh_config()

        assert "LLM 未配置" in capsys.readouterr().out


class TestAnonymizationPanel:
    def _run(self, monkeypatch, *, current: str, texts: list[str], applied: bool = True) -> list[dict]:
        record: list[dict] = []
        monkeypatch.setattr(hc, "panel_loop", _fake_panel_loop({"texts": texts}))
        monkeypatch.setattr("src.python.config.anonymizer.get_anonymization_mode", lambda: current)
        monkeypatch.setattr(hc, "_apply_edit", lambda p: record.append(p) or applied)
        hc._cmd_config_anonymization_mode()
        return record

    def test_switch_to_new_mode(self, monkeypatch, capsys):
        record = self._run(monkeypatch, current="off", texts=["3"])

        assert record == [{"key": "anonymization.mode", "value": "full_anonymous"}]
        assert "已切换为" in capsys.readouterr().out

    def test_same_mode_reports_no_change(self, monkeypatch, capsys):
        record = self._run(monkeypatch, current="off", texts=["1"])

        assert record == []
        assert "已是当前模式" in capsys.readouterr().out

    def test_invalid_text_and_out_of_range(self, monkeypatch, capsys):
        record = self._run(monkeypatch, current="off", texts=["x", "9"])

        assert record == []
        out = capsys.readouterr().out
        assert "请输入有效编号" in out and "无效编号" in out

    def test_undo_text_consumed_before_number_parse(self, monkeypatch, capsys):
        record = self._run(monkeypatch, current="off", texts=["u"])

        assert record == []
        assert "尚无改动" in capsys.readouterr().out

    def test_eof_closes_session(self, monkeypatch):
        monkeypatch.setattr(hc, "panel_loop", lambda *a, **k: (_ for _ in ()).throw(EOFError()))

        hc._cmd_config_anonymization_mode()

        assert hc._session is None


class TestDelegatingEntries:
    def test_content_options_delegates(self, monkeypatch):
        called: list[str] = []
        monkeypatch.setattr("src.python.tui.handlers_switch.run_content_options_panel", lambda: called.append("switch"))
        monkeypatch.setattr(
            "src.python.tui.handlers_report_chapters.run_report_chapters_panel", lambda: called.append("chapters")
        )
        monkeypatch.setattr(
            "src.python.tui.handlers_llm_providers.run_llm_providers_panel", lambda: called.append("providers")
        )

        hc._cmd_config_content_options()
        hc._cmd_config_report_boards()
        hc._cmd_config_llm_providers()

        assert called == ["switch", "chapters", "providers"]
