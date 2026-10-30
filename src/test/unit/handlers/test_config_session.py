# -*- coding: utf-8 -*-
"""配置面板会话快照（`ConfigSession`）：`u` 撤销上次、`U` 还原进入时。

语义边界：改动仍即时写盘（功能开关要立刻影响菜单裁剪），会话只记变更前值——
所以验的是「写回的值对不对」，不是「有没有拦住写入」。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.tui.handlers_config import ConfigSession, reset_config_session

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestSessionRecording:
    """记录与计数。"""

    def test_count_dedupes_by_key(self):
        """同一键改两次只算一项改动。"""
        session = ConfigSession()
        session.record("report_qa", False)
        session.record("report_qa", True)
        assert session.count == 1
        assert session.keys == ["report_qa"]

    def test_keys_keep_first_seen_order(self):
        """键按首次出现顺序返回（页脚与撤销都按这个顺序理解）。"""
        session = ConfigSession()
        session.record("b", 1)
        session.record("a", 2)
        assert session.keys == ["b", "a"]

    def test_empty_session(self):
        session = ConfigSession()
        assert session.count == 0
        assert session.keys == []


class TestUndo:
    """`u` 撤销最近一次改动。"""

    def test_undo_restores_previous_value(self):
        session = ConfigSession()
        session.record("daily_cost_limit", 5)
        with patch("src.python.config.edit_ops.apply_config_edit") as apply:
            undone = session.undo_last()
        apply.assert_called_once_with({"key": "daily_cost_limit", "value": 5})
        assert undone == "daily_cost_limit"

    def test_undo_twice_steps_back_further(self):
        """连续撤销按改动逆序逐条退回（不是一次退到原点）。"""
        session = ConfigSession()
        session.record("k", 1)
        session.record("k", 2)
        with patch("src.python.config.edit_ops.apply_config_edit") as apply:
            assert session.undo_last() == "k"
            first = apply.call_args.args[0]
            assert session.undo_last() == "k"
            second = apply.call_args.args[0]
        assert first == {"key": "k", "value": 2}
        assert second == {"key": "k", "value": 1}

    def test_undo_without_changes_returns_none(self):
        assert ConfigSession().undo_last() is None

    def test_write_failure_keeps_change_off_stack(self):
        """写回失败：该条已出栈且不返回键（避免页脚显示已撤销但实际没退）。"""
        session = ConfigSession()
        session.record("k", 1)
        with patch("src.python.config.edit_ops.apply_config_edit", side_effect=OSError("disk")):
            assert session.undo_last() is None


class TestRestoreAll:
    """`U` 还原到进入面板时的状态。"""

    def test_restore_uses_earliest_value_per_key(self):
        """多键多次改动：每键退回**最早**记录的前值（即进入时状态）。"""
        session = ConfigSession()
        session.record("a", 10)
        session.record("b", 20)
        session.record("a", 11)
        with patch("src.python.config.edit_ops.apply_config_edit") as apply:
            restored = session.restore_all()
        assert restored == 2
        calls = {call.args[0]["key"]: call.args[0]["value"] for call in apply.call_args_list}
        assert calls == {"a": 10, "b": 20}

    def test_restore_clears_session(self):
        session = ConfigSession()
        session.record("a", 1)
        with patch("src.python.config.edit_ops.apply_config_edit"):
            session.restore_all()
        assert session.count == 0

    def test_restore_without_changes(self):
        assert ConfigSession().restore_all() == 0


class TestApplyEditRecording:
    """`_apply_edit` 在有会话时自动记录前值（各面板写路径共用这一处）。"""

    def test_records_before_value_when_session_active(self):
        from src.python.tui import handlers_config

        session = reset_config_session()
        with (
            patch("src.python.config.edit_ops.read_config_value", return_value=False),
            patch("src.python.config.edit_ops.apply_config_edit"),
        ):
            assert handlers_config._apply_edit({"key": "report_qa", "value": True}) is True
        assert session.count == 1
        assert session._changes[0].before is False

    def test_no_session_records_nothing(self):
        from src.python.tui import handlers_config

        handlers_config._session = None
        with (
            patch("src.python.config.edit_ops.read_config_value") as read,
            patch("src.python.config.edit_ops.apply_config_edit"),
        ):
            handlers_config._apply_edit({"key": "report_qa", "value": True})
        read.assert_not_called()

    def test_failed_write_records_nothing(self):
        """写失败不记录（否则撤销会退回一个从未生效的值）。"""
        from src.python.config.edit_ops import ConfigEditError
        from src.python.tui import handlers_config

        session = reset_config_session()
        with (
            patch("src.python.config.edit_ops.read_config_value", return_value=False),
            patch("src.python.config.edit_ops.apply_config_edit", side_effect=ConfigEditError("校验失败")),
        ):
            assert handlers_config._apply_edit({"key": "report_qa", "value": True}) is False
        assert session.count == 0


class TestSessionIsolation:
    """会话不得跨用例残留（``conftest._auto_reset_config_session`` 兜底）。"""

    def test_session_is_clean_at_test_entry(self):
        """上一条用例把会话开着也不影响本用例（``_apply_edit`` 先读这个全局）。"""
        from src.python.tui import handlers_config

        assert handlers_config._session is None

    def test_fixture_clears_polluted_session(self):
        """复现 autouse fixture：进/出两侧都把模块级会话复位。"""
        from src.python.tui import handlers_config
        from src.test.conftest import _auto_reset_config_session

        reset_config_session()
        assert handlers_config._session is not None
        steps = getattr(_auto_reset_config_session, "__wrapped__")()
        next(steps)
        assert handlers_config._session is None
        handlers_config.reset_config_session()  # 模拟本用例自己的面板进/出
        next(steps, None)
        assert handlers_config._session is None


class TestSwitchPanelUndoKeys:
    """`[S]` 面板端到端：改一项 → `u` 撤销 → `U` 全还原（写回值须正确）。"""

    @staticmethod
    def _drive(keys: list[str]) -> list[dict]:
        from src.python.tui import handlers_config, handlers_switch

        seq = iter(keys)
        writes: list[dict] = []

        def _read(prompt: str = "", arrows: bool = False):  # noqa: ARG001
            try:
                return next(seq)
            except StopIteration:
                return "0"

        def _apply(payload: dict) -> dict:
            writes.append(payload)
            return {"key": payload.get("key"), "value": payload.get("value"), "backup": None}

        with (
            patch.object(handlers_config, "input_choice", _read),
            patch.object(handlers_config, "refresh_config"),
            patch.object(handlers_config, "_read_llm_settings", return_value=({"enabled_llm": {}}, "/tmp/x.json")),
            patch("src.python.config.edit_ops.apply_config_edit", side_effect=_apply),
            patch("src.python.config.edit_ops.read_config_value", return_value=False),
        ):
            handlers_switch.run_content_options_panel()
        return writes

    def test_undo_restores_previous_value(self):
        """改一项 → `u`：写回变更前值（此后会话已无待退条目）。"""
        writes = self._drive(["1", "u", "0"])
        assert len(writes) == 2, writes
        assert writes[0]["value"] is True, "首键切换应写入新值"
        assert writes[1] == {"key": writes[0]["key"], "value": False}, "u 应退回变更前值"

    def test_restore_all_returns_every_touched_key(self):
        """改两项 → `U`：两个键各写回一次进入时的值。"""
        writes = self._drive(["1", "2", "U", "0"])
        assert len(writes) == 4, writes
        touched = [writes[0]["key"], writes[1]["key"]]
        restored = {write["key"]: write["value"] for write in writes[2:]}
        assert set(restored) == set(touched), restored
        assert all(value is False for value in restored.values()), "每个键都退回进入时的关"


class TestSessionScope:
    """D3 回归：会话作用域限定为「一次面板进入」，面板退出即失效。"""

    def test_panel_exit_closes_session(self):
        from unittest.mock import MagicMock

        from src.python.tui import handlers_config, handlers_switch

        with (
            patch.object(handlers_config, "input_choice", return_value="0"),
            patch.object(handlers_config, "refresh_config"),
            patch.object(handlers_config, "_read_llm_settings", return_value=({"enabled_llm": {}}, "/tmp/x.json")),
            patch.object(handlers_config, "panel_loop", MagicMock(return_value=None)),
        ):
            handlers_switch.run_content_options_panel()
        assert handlers_config._session is None, "面板退出后会话必须失效（避免后续面板写盘记进旧会话）"

    def test_writes_after_panel_exit_are_not_recorded(self):
        from src.python.tui import handlers_config

        assert handlers_config._session is None
        with (
            patch("src.python.config.edit_ops.read_config_value") as read,
            patch("src.python.config.edit_ops.apply_config_edit"),
        ):
            handlers_config._apply_edit({"key": "report_qa", "value": True})
        read.assert_not_called()


class TestActionPayloadUndo:
    """动作型键（线路重排等）：逆操作是「重放相反动作」，按逆序回放。"""

    def test_record_payload_undo_replays_payload(self):
        session = ConfigSession()
        session.record_payload({"key": "llm_providers.priority", "action": "reorder", "order": ["A", "B", "C"]})
        with patch("src.python.config.edit_ops.apply_config_edit") as apply:
            undone = session.undo_last()
        assert undone == "llm_providers.priority"
        assert apply.call_args.args[0] == {
            "key": "llm_providers.priority",
            "action": "reorder",
            "order": ["A", "B", "C"],
        }

    def test_restore_all_replays_in_reverse_order(self):
        """多次改动按逆序回放（动作型键的语义只有逆序回放才对得上进入时状态）。"""
        session = ConfigSession()
        session.record("a", 1)
        session.record_payload({"key": "llm_providers.priority", "action": "reorder", "order": ["X", "Y"]})
        session.record("a", 2)
        with patch("src.python.config.edit_ops.apply_config_edit") as apply:
            restored = session.restore_all()
        assert restored == 2, "两个键各退回一次"
        payloads = [call.args[0] for call in apply.call_args_list]
        assert payloads[0] == {"key": "a", "value": 2}, "最后一条先回放"
        assert payloads[1]["action"] == "reorder"
        assert payloads[2] == {"key": "a", "value": 1}, "最早一条最后回放（回到进入时）"


class TestProvidersPanelUndo:
    """`[M]` 线路面板端到端：交换 → `u` 重放逆序动作（动作型键靠逆操作回退）。"""

    def _drive(self, keys: list[str]) -> list[dict]:
        from src.python.tui import handlers_config, handlers_llm_providers

        seq = iter(keys)
        writes: list[dict] = []

        def _apply(payload: dict) -> bool:
            writes.append(payload)
            return True

        with (
            patch("src.python.config.order_providers_by_chain", side_effect=lambda raw: list(raw)),
            # 局部导入：patch 必须指向导入源（config 模块），而非消费方
            patch(
                "src.python.config.get_llm_providers",
                return_value={
                    "strategy": "priority",
                    "providers": [{"name": "甲", "priority": 1}, {"name": "乙", "priority": 2}],
                },
            ),
            patch.object(handlers_llm_providers, "input_choice", lambda prompt="", arrows=False: next(seq, "0")),
            patch.object(handlers_config, "_apply_edit", side_effect=_apply),
            # 退回路径走共享编辑层（_apply_inverse → apply_config_edit），同样收进写盘记录
            patch(
                "src.python.config.edit_ops.apply_config_edit",
                side_effect=lambda payload: (writes.append(payload), {"key": payload.get("key")})[1],
            ),
        ):
            handlers_llm_providers.run_llm_providers_panel()
        return writes

    def test_swap_then_undo_replays_previous_order(self):
        writes = self._drive(["1 2", "u", "0"])
        assert len(writes) == 2, writes
        assert writes[0]["order"] == ["乙", "甲"], "交换写入新顺序"
        assert writes[1]["order"] == ["甲", "乙"], "u 应重放交换前的顺序"
