"""`_eval_halluc_sampler.self_review`（离线自检抽样 / 附录拼装 / dry-run 提示词）。

自检抽样的定位是「辅助信号，不构成质量保证」，所以三件事必须分开测：调用骨架
（失败/空产出都不允许拖垮评测）、附录拼装（无产出也要留痕，不能静默消失）、
dry-run 提示词（零花费路径）。LLM 一律打桩，不触网。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _eval_halluc_sampler import self_review  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_MODULE_OUTPUTS = {"expert_review": "智囊团正文", "health_check": "体检正文"}
_HOLDINGS = [{"name": "贵州茅台", "code": "600519"}]


@pytest.fixture
def generate_mock(monkeypatch):
    """把自检生成器换成 Mock（默认返回 (清单正文, 未命中缓存)）。"""
    import src.python.llm.generators as generators

    mock = Mock(name="generate_self_review", return_value=("复核 `expert_review` 的数值", False))
    monkeypatch.setattr(generators, "generate_self_review", mock)
    monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"provider": "claude", "model": "fake"})
    return mock


# ── 调用骨架 ────────────────────────────────────────────────


def test_sample_forwards_inputs_and_returns_dual_form(generate_mock):
    """抽样以 force 重跑并把产物转成「中文名（内部键）」双写形态。"""
    out = self_review._run_self_review_sample(_MODULE_OUTPUTS, _HOLDINGS, [{"code": "600519"}])

    generate_mock.assert_called_once()
    args, kwargs = generate_mock.call_args
    assert args[0] == _MODULE_OUTPUTS
    assert args[1] == _HOLDINGS
    assert args[2] == [{"code": "600519"}]
    assert kwargs["force"] is True
    assert kwargs["llm_config"] == {"provider": "claude", "model": "fake"}
    assert out is not None
    assert "智囊团深度复盘（expert_review）" in out
    assert "`expert_review`" not in out


def test_sample_failure_is_swallowed_with_warning(generate_mock, caplog):
    """自检失败只记警告并返回 None（幻觉率统计不受影响）。"""
    generate_mock.side_effect = RuntimeError("LLM 超时")

    with caplog.at_level(logging.WARNING, logger="invest"):
        out = self_review._run_self_review_sample(_MODULE_OUTPUTS, _HOLDINGS, None)

    assert out is None
    assert "自检抽样失败" in caplog.text


def test_sample_returns_none_on_empty_output(generate_mock):
    """空产出返回 None（空清单进附录会渲染成一段空白，看起来像「无问题」）。"""
    generate_mock.return_value = ("", True)

    assert self_review._run_self_review_sample(_MODULE_OUTPUTS, None, None) is None


# ── 附录拼装 ────────────────────────────────────────────────


def test_section_renders_each_dataset_with_content():
    """有产出：每数据集一段，正文去首尾空白后原样进入附录。"""
    text = self_review._generate_self_review_section(
        [
            {"dataset": "数据集甲", "content": "  清单正文  ", "error": None},
            {"dataset": "数据集乙", "content": "另一份清单", "error": None},
        ]
    )

    assert text.startswith("\n## 自检抽样（离线）")
    assert text.count("### 数据集") == 2
    assert "### 数据集甲" in text and "### 数据集乙" in text
    assert "清单正文\n" in text and "  清单正文  " not in text
    assert "另一份清单" in text
    assert "未产出" not in text


def test_section_marks_missing_output_with_reason():
    """无产出：显式写「未产出：<原因>」，原因缺失时退化为「空输出」。"""
    text = self_review._generate_self_review_section(
        [
            {"dataset": "失败集", "content": None, "error": "上游 502"},
            {"dataset": "空集", "content": None, "error": None},
        ]
    )

    assert "（未产出：上游 502）" in text
    assert "（未产出：空输出）" in text


def test_section_without_samples_keeps_header_only():
    """零样本：只留章节标题与说明（章节本身照常存在，便于比对历次产物结构）。"""
    text = self_review._generate_self_review_section([])

    assert "## 自检抽样（离线）" in text
    assert "### " not in text
    assert "模型层复核" in text


# ── dry-run 提示词 ─────────────────────────────────────────


def test_dry_run_prompt_has_system_and_user_blocks():
    """dry-run 返回「### System / ### User」两段完整提示词，不触发任何调用。"""
    text = self_review._build_self_review_dry_run_prompt(_MODULE_OUTPUTS, _HOLDINGS, None)

    assert text.startswith("### System")
    system_part, user_part = text.split("### User", 1)
    assert system_part.strip() != "### System"
    assert user_part.strip(), "用户提示词应包含各模块产物"
