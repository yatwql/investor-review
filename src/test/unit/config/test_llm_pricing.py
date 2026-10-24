"""llm_pricing_ref.json：缺失回退内置价、逐模型部分覆盖、非法跳过、版本拒绝、计费等价。"""

from __future__ import annotations

import json

import pytest

from src.python.config import _llm_pricing
from src.python.core.constants import MODEL_PRICING

pytestmark = pytest.mark.unit_config


def _base_ref() -> dict:
    return {
        "version": 1,
        "currency": "CNY",
        "timezone": "Asia/Shanghai",
        "peak_periods": ["09:00-12:00"],
        "idle_periods": [],
        "weekend_always_idle": True,
        "holiday_always_idle": True,
        "models": {},
    }


@pytest.fixture
def pricing_file(tmp_path, monkeypatch):
    path = tmp_path / "llm_pricing_ref.json"
    monkeypatch.setattr(_llm_pricing, "get_llm_pricing_path", lambda: str(path))
    _llm_pricing.invalidate_pricing_cache()
    return path


def _write(path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


@pytest.mark.unit
class TestMissingAndGenerator:
    def test_missing_file_uses_builtin_prices(self, pricing_file):
        config = _llm_pricing.load_pricing_config()

        assert config["models"] == {m: dict(p) for m, p in MODEL_PRICING.items()}
        assert config["currency"] == "CNY"
        assert config["peak_periods"] == [(540, 720), (840, 1080)]

    def test_generated_file_parses_and_has_chinese_comments(self):
        text = _llm_pricing.render_default_pricing_ref()
        from src.python.core.json_comments import loads

        doc = loads(text)
        assert doc["version"] == 1
        assert "models" in doc
        assert "计价参考" in text and "覆盖" in text

    def test_generator_does_not_overwrite_existing(self, pricing_file):
        pricing_file.write_text("custom", encoding="utf-8")
        assert _llm_pricing.ensure_llm_pricing_file() is False
        assert pricing_file.read_text(encoding="utf-8") == "custom"


@pytest.mark.unit
class TestMerge:
    def test_partial_model_override_inherits_other_fields(self, pricing_file):
        ref = _base_ref()
        ref["models"] = {"deepseek-v4-flash": {"input_price": 9.0}}
        _write(pricing_file, ref)

        models = _llm_pricing.load_pricing_config()["models"]
        builtin = MODEL_PRICING["deepseek-v4-flash"]

        assert models["deepseek-v4-flash"]["input"] == 9.0
        assert models["deepseek-v4-flash"]["output"] == builtin["output"]
        assert models["deepseek-v4-flash"]["peak"] == builtin["peak"]

    def test_new_model_entry_added(self, pricing_file):
        ref = _base_ref()
        ref["models"] = {"future-model": {"input_price": 1.5, "output_price": 3.0}}
        _write(pricing_file, ref)

        models = _llm_pricing.load_pricing_config()["models"]
        assert models["future-model"] == {
            "input": 1.5,
            "output": 3.0,
            "input_cache_hit": 0.0,
        }

    def test_invalid_entries_warn_and_skip(self, pricing_file, caplog):
        ref = _base_ref()
        ref["models"] = {
            "bad-type": "not-a-dict",
            "bad-price": {"input_price": -1, "output_price": "x"},
            "good": {"input_price": 2.0},
        }
        _write(pricing_file, ref)

        with caplog.at_level("WARNING"):
            models = _llm_pricing.load_pricing_config()["models"]

        assert "bad-type" not in models
        assert models["bad-price"] == dict(
            MODEL_PRICING.get("bad-price", {"input": 0.0, "output": 0.0, "input_cache_hit": 0.0})
        )
        assert models["good"]["input"] == 2.0
        assert any("已跳过" in record.getMessage() or "已忽略" in record.getMessage() for record in caplog.records)

    def test_invalid_peak_field_skipped(self, pricing_file, caplog):
        ref = _base_ref()
        ref["models"] = {"deepseek-v4-flash": {"peak": {"input_price": -5}}}
        _write(pricing_file, ref)

        with caplog.at_level("WARNING"):
            models = _llm_pricing.load_pricing_config()["models"]

        assert models["deepseek-v4-flash"]["peak"] == MODEL_PRICING["deepseek-v4-flash"]["peak"]
        assert any("peak" in record.getMessage() for record in caplog.records)

    def test_invalid_policy_falls_back_to_defaults(self, pricing_file, caplog):
        ref = _base_ref()
        ref["peak_periods"] = ["25:00-26:00"]
        ref["weekend_always_idle"] = "yes"
        _write(pricing_file, ref)

        with caplog.at_level("WARNING"):
            config = _llm_pricing.load_pricing_config()

        assert config["peak_periods"] == [(540, 720), (840, 1080)]
        assert config["weekend_always_idle"] is True


@pytest.mark.unit
class TestVersionRejection:
    def test_wrong_version_logs_error_with_guidance(self, pricing_file, caplog):
        ref = _base_ref()
        ref["version"] = 99
        _write(pricing_file, ref)

        with caplog.at_level("ERROR"):
            config = _llm_pricing.load_pricing_config()

        assert config["models"] == {m: dict(p) for m, p in MODEL_PRICING.items()}
        messages = [r.getMessage() for r in caplog.records]
        assert any("llm_pricing_ref.json" in msg and "99" in msg and "重新生成" in msg for msg in messages)


@pytest.mark.unit
class TestCostEquivalence:
    def test_same_prices_produce_same_cost(self, pricing_file):
        """覆盖为与内置相同的价格时，费用计算结果与基线一致（浮点容差）。"""
        from src.python.llm.pricing import compute_cost_value, reload_pricing

        reload_pricing()
        baseline = compute_cost_value("deepseek-v4-flash", 1_000_000, 1_000_000)

        ref = _base_ref()
        builtin = MODEL_PRICING["deepseek-v4-flash"]
        ref["models"] = {
            "deepseek-v4-flash": {
                "input_price": builtin["input"],
                "output_price": builtin["output"],
                "peak": {"input_price": builtin["peak"]["input"], "output_price": builtin["peak"]["output"]},
            }
        }
        _write(pricing_file, ref)
        _llm_pricing.invalidate_pricing_cache()
        reload_pricing()
        overridden = compute_cost_value("deepseek-v4-flash", 1_000_000, 1_000_000)

        assert overridden == pytest.approx(baseline, rel=1e-12, abs=1e-12)
