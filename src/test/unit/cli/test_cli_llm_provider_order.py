"""CLI ``--llm-provider-order`` 测试：参数解析校验 + 经共享编辑层持久化写盘。"""

from __future__ import annotations

import pytest

from unittest.mock import patch

from src.python.cli._parser import _build_parser
from src.python.cli.cli import _apply_cli_llm_provider_order
from src.python.cli._handlers import _EXIT_SEVERE, _EXIT_SUCCESS
from src.python.config.edit_ops import ConfigEditError

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


class TestProviderOrderParser:
    """--llm-provider-order 参数层校验（覆盖性校验在共享编辑层）。"""

    def test_parses_valid_comma_list(self) -> None:
        """合法逗号列表 → args.llm_provider_order 为字符串列表。"""
        args = _build_parser().parse_args(["--llm-provider-order", "b,a", "report"])
        assert args.llm_provider_order == ["b", "a"]

    def test_empty_part_rejected(self) -> None:
        """空线路名（如 a,,b）→ 解析失败退出。"""
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["--llm-provider-order", "a,,b", "report"])

    def test_duplicate_rejected(self) -> None:
        """重复线路名 → 解析失败退出。"""
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["--llm-provider-order", "a,a", "report"])


class TestApplyCliLlmProviderOrder:
    """写路径：apply_config_edit（llm_providers.priority / reorder）薄适配。"""

    def test_success_prints_effective_order(self) -> None:
        """成功：打印生效链序 + 返回 0。"""
        with (
            patch(
                "src.python.config.edit_ops.apply_config_edit",
                return_value={"value": {"order": ["deepseek-main", "gemini-fallback"]}},
            ) as mocked,
            patch("builtins.print") as printed,
        ):
            code = _apply_cli_llm_provider_order(["deepseek-main", "gemini-fallback"])
        assert code == _EXIT_SUCCESS
        mocked.assert_called_once_with(
            {"key": "llm_providers.priority", "action": "reorder", "order": ["deepseek-main", "gemini-fallback"]}
        )
        output = " ".join(str(call) for call in printed.call_args_list)
        assert "deepseek-main → gemini-fallback" in output

    def test_config_error_returns_severe(self) -> None:
        """校验失败（非置换等）：打印 [!] 原因 + 返回 2，不写盘。"""
        with (
            patch(
                "src.python.config.edit_ops.apply_config_edit",
                side_effect=ConfigEditError("order 须恰好覆盖全部线路"),
            ),
            patch("builtins.print") as printed,
        ):
            code = _apply_cli_llm_provider_order(["only-one"])
        assert code == _EXIT_SEVERE
        output = " ".join(str(call) for call in printed.call_args_list)
        assert "order 须恰好覆盖全部线路" in output
