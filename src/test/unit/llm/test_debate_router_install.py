"""辩论路由装配（`llm/_debate_router.install_debate_route`）两级回退与信息容器口径。

覆盖点：
  - 开关关闭 / 该槽位不需要生成 / 槽位没有可替换的函数 → 不替换（返回 False）
  - pro+con+synthesis 成功 → 返回 synthesis 且写入辩论信息容器
  - synthesis 失败 → 返回 pro+con 拼接（仍标记命中，容器保留）
  - pro 或 con 失败 → 回退普通生成，且**清空**容器（残留会显示并不存在的辩论结论）
  - 整段抛异常 → 同样回退普通生成并清空容器
  - 辩论模式组合标识随开关拼接
"""

from __future__ import annotations

import pytest

from src.python.llm import _debate_router as router

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


def _kwargs(**overrides) -> dict:
    base = dict(
        needs={"expert_review": True},
        total_mv=1.0,
        total_cost=1.0,
        total_profit=0.0,
        total_today_profit=0.0,
        holdings_count=1,
        categories={},
        penetrated_assets=None,
        holdings_details=None,
        force=False,
        force_modules=None,
        pipeline_data=None,
        competitive_context="ctx",
        metrics=None,
        purchase_constraint_block="",
        holding_change_block="",
        event_impact_block="",
        schedule_replay_block="",
        debate_info_container=[None],
    )
    base.update(overrides)
    return base


def _enable(monkeypatch, *, procon: bool = True, conditional: bool = False) -> None:
    monkeypatch.setattr(
        "src.python.config.features.is_feature_enabled",
        lambda name: {"llm_debate_procon": procon, "llm_debate_conditional": conditional}.get(name, False),
    )


def _stub_debate(monkeypatch, result) -> None:
    def _gen(*_a, **_k):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("src.python.llm.generators.generate_debate_procon", _gen)


class TestInstallGate:
    def test_feature_off_keeps_original(self, monkeypatch):
        _enable(monkeypatch, procon=False)
        fns = {"expert_review": lambda c, cfg: ("普通", True)}

        assert router.install_debate_route(fns, **_kwargs()) is False
        assert fns["expert_review"](None, None) == ("普通", True)

    def test_slot_not_needed_keeps_original(self, monkeypatch):
        _enable(monkeypatch)
        fns = {"expert_review": lambda c, cfg: ("普通", True)}

        assert router.install_debate_route(fns, **_kwargs(needs={"expert_review": False})) is False
        assert fns["expert_review"](None, None) == ("普通", True)

    def test_missing_original_slot_returns_false(self, monkeypatch):
        _enable(monkeypatch)

        assert router.install_debate_route({}, **_kwargs()) is False


class TestDebateWrapper:
    def test_synthesis_success_sets_container(self, monkeypatch):
        _enable(monkeypatch, conditional=True)
        _stub_debate(monkeypatch, ("正面", "反面", "综合"))
        container: list = [None]
        fns = {"expert_review": lambda c, cfg: ("普通", False)}

        assert router.install_debate_route(fns, **_kwargs(debate_info_container=container)) is True
        assert fns["expert_review"](object(), {"k": 1}) == ("综合", True)
        assert container[0] is not None
        assert container[0]["mode_combination"] == "正反辩论+条件推理"
        assert container[0]["pro_text"] == "正面" and container[0]["con_text"] == "反面"

    def test_synthesis_missing_concatenates_pro_and_con(self, monkeypatch):
        _enable(monkeypatch)
        _stub_debate(monkeypatch, ("正面", "反面", ""))
        container: list = [None]
        fns = {"expert_review": lambda c, cfg: ("普通", False)}
        router.install_debate_route(fns, **_kwargs(debate_info_container=container))

        text, hit = fns["expert_review"](None, None)

        assert hit is True, "synthesis 失败仍是辩论产出，必须标记命中"
        assert "正面" in text and "反面" in text
        assert container[0]["mode_combination"] == "正反辩论"

    def test_procon_failure_falls_back_and_clears_container(self, monkeypatch):
        _enable(monkeypatch)
        _stub_debate(monkeypatch, ("", "反面", "综合"))
        container: list = [{"pro_text": "旧残留"}]
        fns = {"expert_review": lambda c, cfg: ("普通", True)}
        router.install_debate_route(fns, **_kwargs(debate_info_container=container))

        assert fns["expert_review"](None, None) == ("普通", True)
        assert container[0] is None, "回退普通生成时必须清空辩论信息，否则报告显示不存在的辩论结论"

    def test_exception_falls_back_and_clears_container(self, monkeypatch):
        _enable(monkeypatch)
        _stub_debate(monkeypatch, RuntimeError("boom"))
        container: list = [{"pro_text": "旧残留"}]
        fns = {"expert_review": lambda c, cfg: ("普通", False)}
        router.install_debate_route(fns, **_kwargs(debate_info_container=container))

        assert fns["expert_review"](None, None) == ("普通", False)
        assert container[0] is None

    def test_force_modules_forwarded_to_generator(self, monkeypatch):
        _enable(monkeypatch)
        seen: dict[str, object] = {}

        def _gen(*_a, **kwargs):
            seen.update(kwargs)
            return ("正面", "反面", "综合")

        monkeypatch.setattr("src.python.llm.generators.generate_debate_procon", _gen)
        fns = {"expert_review": lambda c, cfg: ("普通", False)}
        router.install_debate_route(fns, **_kwargs(force=False, force_modules=["expert_review"]))
        fns["expert_review"](None, None)

        assert seen["force"] is True, "force_modules 命中该槽位时应等价于强制刷新"

    def test_container_none_tolerated(self, monkeypatch):
        _enable(monkeypatch)
        _stub_debate(monkeypatch, ("正面", "反面", ""))
        fns = {"expert_review": lambda c, cfg: ("普通", False)}
        router.install_debate_route(fns, **_kwargs(debate_info_container=None))

        assert fns["expert_review"](None, None)[1] is True


class TestDebateModeCombination:
    def test_empty_when_both_switches_off(self, monkeypatch):
        _enable(monkeypatch, procon=False)
        assert router.debate_mode_combination() == ""

    def test_only_procon(self, monkeypatch):
        _enable(monkeypatch)
        assert router.debate_mode_combination() == "正反辩论"
