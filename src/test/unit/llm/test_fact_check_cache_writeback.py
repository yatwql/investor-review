"""事实校验自动修正回写缓存 — 同一批修正不在每轮重做。

现象：修正（数值/代码笔误）只作用于当轮输出，缓存里存的仍是修正前正文 → 每次
运行都对同一份缓存内容再做一次同样的修正（`counters.fact_fix:*` 恒为同一数），
且报告展示的正文与缓存存储的正文口径不一致（不可复现）。

判定口径：命中轮次对「已修正过的正文」再校验应得零修正 —— 即修正读回即幂等。
键不变（指纹是生成输入的内容地址），只改缓存里的产出正文。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.test.unit.llm._cache_fixtures import LLM_REPLY_DEFAULT, make_inputs, run_generate_all_llm

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.usefixtures("offline_external_sources"),
]

#: 数值与持仓/历史数据不一致的正文（历史最大回撤 19.0% vs 实际 -15.0%）→ 必然触发修正
_REPLY_WITH_WRONG_NUMBERS = (
    "<p>组合累计收益率为 5.0%，历史最大回撤 19.0%，整体偏弱。</p>",
    {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0},
    {"name": "probe-main", "model": "deepseek-v4-flash", "endpoint": "e"},
)


def _fact_fix_counts() -> dict[str, int]:
    from src.python.llm.fact_checker import auto_correction_counts

    return {k: v for k, v in auto_correction_counts().items() if k.startswith("fact_fix:")}


class TestWriteBackPrimitive:
    """回写原语：键解析（显式键 / 骨架记录键）、空输入不写。"""

    def test_explicit_key_is_used(self, llm_cache_dir):
        from src.python.cache import get as cache_get
        from src.python.llm.skeleton import write_back_module_cache

        assert write_back_module_cache("<p>修正后</p>", cache_key="llm_demo_key", module_key="demo", cached=True)
        assert cache_get("llm_demo_key", 3600) == "<p>修正后</p>"

    def test_falls_back_to_skeleton_module_key(self, llm_cache_dir, monkeypatch):
        from src.python.cache import get as cache_get
        from src.python.llm import skeleton

        monkeypatch.setattr(skeleton, "_PREV_MODULE_CACHE_KEY", {"demo": "llm_skeleton_key"})
        assert skeleton.write_back_module_cache("<p>修正后</p>", module_key="demo")
        assert cache_get("llm_skeleton_key", 3600) == "<p>修正后</p>"

    def test_no_key_or_empty_content_is_noop(self, llm_cache_dir):
        from src.python.llm.skeleton import write_back_module_cache

        assert write_back_module_cache("<p>修正后</p>", module_key="unknown") is False
        assert write_back_module_cache("", cache_key="llm_demo_key") is False

    def test_cache_write_failure_does_not_raise(self, llm_cache_dir, monkeypatch):
        """缓存不可写只记日志，不得中断报告生成。"""
        from src.python.llm import skeleton

        monkeypatch.setattr(skeleton, "cache_set", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        assert skeleton.write_back_module_cache("<p>修正后</p>", cache_key="llm_demo_key") is False


class TestCachedCorrectionIsNotRepeated:
    """回归主用例：命中轮次不得重做同一批修正。"""

    def test_second_run_does_not_repeat_correction(self, llm_cache_dir):
        from src.python.llm.fact_checker import reset_auto_correction_counts

        inputs = make_inputs()
        reset_auto_correction_counts()
        run_generate_all_llm(inputs, reply=_REPLY_WITH_WRONG_NUMBERS)
        first = _fact_fix_counts()
        assert first, "用例前提：首轮必须真的触发修正（否则断言无意义）"

        reset_auto_correction_counts()
        flags = run_generate_all_llm(inputs)
        assert all(flags), "第二轮应全部命中缓存（用例前提）"
        assert _fact_fix_counts() == {}, "缓存已存修正后正文，命中轮次不得重做同一批修正"

    def test_write_back_keeps_render_content_corrected(self, llm_cache_dir):
        """回写不清空渲染正文：修正后的数值仍然出现在本轮输出里。"""
        from src.python.llm.fact_checker import reset_auto_correction_counts

        inputs = make_inputs()
        reset_auto_correction_counts()
        with patch("src.python.llm.skeleton.write_back_module_cache") as write_back:
            run_generate_all_llm(inputs, reply=_REPLY_WITH_WRONG_NUMBERS)
        assert write_back.called, "修正发生时应触发回写"
        args, kwargs = write_back.call_args
        assert args[0] != _REPLY_WITH_WRONG_NUMBERS[0], "回写的是修正后正文（与原始产出不同）"
        assert kwargs.get("cache_key"), "回写必须带预检/写侧同源的缓存键"
        assert kwargs.get("cached") in (True, False)


def test_default_reply_needs_no_write_back(llm_cache_dir):
    """无修正即无回写（不产生多余写盘）。"""
    from src.python.llm.fact_checker import reset_auto_correction_counts

    inputs = make_inputs()
    reset_auto_correction_counts()
    with patch("src.python.llm.skeleton.write_back_module_cache") as write_back:
        run_generate_all_llm(inputs, reply=LLM_REPLY_DEFAULT)
    assert not write_back.called
