"""`_eval_factor_zoo.stages` 阶段编排（catalog/fields/signals/timing）单元测试。

阶段编排的价值在于「把一次取数探测固化成可复算的产物」——本文件因此不测阈值，
而是测**产物契约与阶段编排的分支**：股票池从盘上复用 / 缺失时重建、探测结果经
落盘 JSON 传给 signals（避免重复打源）、指标 A 不过时提前终态、冷样本采集把
「已缓存」与「成功」分开计数。

取数一律打桩到真实调用点的模块属性（`probe.py` 在函数内 import 取数函数，
patch 上游 provider 模块不生效），因此全程零网络、零 LLM。异常/缺文件场景见
`test_eval_factor_zoo_stages_edge.py`。
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]

#: 探测用的池内代码（数量只需 ≥3：横截面序列按 MIN_CODES_PER_DAY 剔日）
POOL_CODES = ["600519", "000858", "300750", "601318"]


@pytest.fixture(scope="module")
def zoo():
    return load_script("eval-factor-zoo.py")


def _bars(days: int, start_price: float = 100.0) -> list[dict]:
    """构造 days 根日 K（日期连续、价格有涨有跌、量能递增）。"""
    start = date(2025, 1, 1)
    out: list[dict] = []
    price = start_price
    for i in range(days):
        price *= 1.004 if i % 3 else 0.997
        out.append(
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "open": round(price * 0.995, 3),
                "high": round(price * 1.012, 3),
                "low": round(price * 0.988, 3),
                "close": round(price, 3),
                "volume": 1_000_000 + i * 1_000,
            }
        )
    return out


def _index_bars() -> list[dict]:
    """基准指数 200 根（信号族最长的 120 日温度窗口也够）。"""
    return _bars(200, start_price=3_500.0)


def _code_bars() -> dict[str, list[dict]]:
    """池内各标的取指数尾部窗口（日期与指数对齐，供 qlib_beta_60 对齐收益率）。"""
    tail = _index_bars()[-90:]
    return {code: [dict(bar) for bar in tail] for code in POOL_CODES}


def _patch_fetchers(monkeypatch, bars_by_code: dict[str, list[dict]], index: list[dict]) -> None:
    """把取数打桩到 `probe.py` 函数内真实 import 的模块属性上。"""
    import src.python.fetcher.chain_incremental as chain_incremental
    import src.python.fetcher.financial_indicator as financial_indicator
    import src.python.fetcher.index as index_mod
    import src.python.fetcher.industry as industry

    monkeypatch.setattr(
        chain_incremental,
        "fetch_with_incremental_fallback",
        lambda _name, code, _days=None, **_kw: [dict(bar) for bar in bars_by_code.get(code, [])],
    )
    monkeypatch.setattr(index_mod, "fetch_index_history", lambda *_a, **_kw: [dict(bar) for bar in index])
    monkeypatch.setattr(
        industry,
        "fetch_valuation_fields",
        lambda _code: {"pb": 2.5, "pe": 18.0, "market_cap": 1.2e10},
    )
    monkeypatch.setattr(
        financial_indicator,
        "fetch_latest_indicator",
        lambda _code: {"roe": 12.5, "revenue_yoy": 8.0, "gross_margin": 31.0},
    )


@pytest.fixture
def staged_dir(zoo, tmp_path, monkeypatch):
    """跑完 catalog + fields 阶段的评测目录（指标 A 全通过）。"""
    from _eval_factor_zoo import stages

    _patch_fetchers(monkeypatch, _code_bars(), _index_bars())
    stages.stage_catalog(tmp_path)
    (tmp_path / "stock_pool.json").write_text(
        json.dumps({"codes": list(POOL_CODES)}, ensure_ascii=False), encoding="utf-8"
    )
    fields_report = stages.stage_fields(tmp_path)
    assert fields_report["pass"] is True, "打桩数据应让全部因子可计算，否则后续阶段会被提前终态"
    stages.stage_signals(tmp_path)
    return tmp_path


# ── 阶段 2：股票池 + 字段探测 ────────────────────────────────


def test_stage_fields_writes_report_and_probe_cache(zoo, tmp_path, monkeypatch):
    """字段阶段产物契约：报告字段齐全、原始探测数据落盘供 signals 复用。"""
    from _eval_factor_zoo import stages

    _patch_fetchers(monkeypatch, _code_bars(), _index_bars())
    catalog = stages.stage_catalog(tmp_path)
    (tmp_path / "stock_pool.json").write_text(json.dumps({"codes": POOL_CODES}), encoding="utf-8")

    report = stages.stage_fields(tmp_path)

    assert {"metric", "total", "computable", "ratio", "pass", "timings"} <= set(report)
    assert report["total"] == len(catalog)
    assert set(report["computable"]) == {item["slug"] for item in catalog}
    assert report["pool_size"] == len(POOL_CODES)
    assert set(report["timings"]) >= {"bars", "index", "valuation", "fin_indicator"}
    assert isinstance(report["captured_at"], str) and report["captured_at"]
    assert stages._read_json(tmp_path / "fields_report.json") == report

    probe = stages._read_json(tmp_path / "probe_cache.json")
    assert set(probe) == {"bars_by_code", "index_bars", "valuation", "fin_indicator"}
    assert set(probe["bars_by_code"]) == set(POOL_CODES)
    assert probe["index_bars"], "指数 bars 应随探测结果落盘（signals 阶段直接复用）"
    assert set(probe["valuation"]) == set(POOL_CODES)


def test_stage_fields_reports_missing_factors_when_coverage_low(zoo, tmp_path, monkeypatch, capsys):
    """池内只有 1/4 代码有市值/财务时指标 A 不过，且逐因子列出缺失字段类型。"""
    from _eval_factor_zoo import stages

    bars = _code_bars()
    thin = {code: bars[code] for code in POOL_CODES[:1]}  # 覆盖率 1/4 < 80%
    _patch_fetchers(monkeypatch, thin, _index_bars())
    stages.stage_catalog(tmp_path)
    (tmp_path / "stock_pool.json").write_text(json.dumps({"codes": POOL_CODES}), encoding="utf-8")

    report = stages.stage_fields(tmp_path)

    assert report["pass"] is False
    missing_printed = [line for line in capsys.readouterr().out.splitlines() if "缺:" in line]
    assert missing_printed, "指标 A 不过时须逐因子打印缺失字段类型"
    assert all(info["missing"] for info in report["per_factor"].values() if not info["ok"])


def test_stage_fields_rebuilds_pool_when_absent(zoo, tmp_path, monkeypatch):
    """盘上无股票池时重建并落盘（持仓路径与穿透池解析在此打桩，不读真实持仓）。"""
    from _eval_factor_zoo import stages

    _patch_fetchers(monkeypatch, _code_bars(), _index_bars())
    stages.stage_catalog(tmp_path)
    monkeypatch.setattr("src.python.config.resolve_holdings_path", lambda: "/tmp/fake_holdings.xlsx")
    monkeypatch.setattr(
        stages,
        "build_stock_pool",
        lambda path: {
            "codes": list(POOL_CODES),
            "holdings_file": path,
            "direct_stocks": list(POOL_CODES),
            "penetration_stocks": [],
            "penetration_note": "",
        },
    )

    report = stages.stage_fields(tmp_path)

    pool = stages._read_json(tmp_path / "stock_pool.json")
    assert pool["holdings_file"] == "/tmp/fake_holdings.xlsx"
    assert pool["codes"] == POOL_CODES
    assert report["pool_size"] == len(POOL_CODES)


def test_stage_fields_refresh_pool_ignores_cached_pool(zoo, tmp_path, monkeypatch):
    """refresh_pool=True 时不复用盘上池（旧池可能已过期）。"""
    from _eval_factor_zoo import stages

    _patch_fetchers(monkeypatch, _code_bars(), _index_bars())
    stages.stage_catalog(tmp_path)
    (tmp_path / "stock_pool.json").write_text(json.dumps({"codes": ["旧代码"]}), encoding="utf-8")
    monkeypatch.setattr("src.python.config.resolve_holdings_path", lambda: "/tmp/refresh_holdings.xlsx")
    monkeypatch.setattr(
        stages,
        "build_stock_pool",
        lambda path: {
            "codes": list(POOL_CODES),
            "holdings_file": path,
            "direct_stocks": list(POOL_CODES),
            "penetration_stocks": [],
            "penetration_note": "穿透失败回退直接持仓",
        },
    )

    report = stages.stage_fields(tmp_path, refresh_pool=True)

    assert stages._read_json(tmp_path / "stock_pool.json")["codes"] == POOL_CODES
    assert report["pool_size"] == len(POOL_CODES)


# ── 阶段 3：信号简并 ─────────────────────────────────────────


def test_stage_signals_writes_report_from_staged_artifacts(zoo, staged_dir):
    """signals 阶段只读前段产物：报告结构、可计算因子全集、快照族降级如实记录。"""
    from _eval_factor_zoo import catalog, stages

    fields_report = stages._read_json(staged_dir / "fields_report.json")
    report = stages._read_json(staged_dir / "signals_report.json")

    assert report["skipped"] is False
    assert report["denom"] == len(fields_report["computable"])
    assert set(report["factor_series_sizes"]) <= set(fields_report["computable"])
    assert report["factor_series_sizes"], "打桩 90 根日 K 应产出至少一个因子的横截面序列"
    assert not set(report["family_series_sizes"]) & set(report["family_degraded"]), "每族只在「有序列/降级」其一"
    assert catalog.FAMILY_REBALANCE in report["family_degraded"], "快照域族须降级不参与相关性"
    assert stages._read_json(staged_dir / "signals_report.json") == report


def test_stage_signals_short_circuits_when_metric_a_fails(zoo, tmp_path):
    """指标 A 不过 → 提前终态：写入 skipped 报告并返回 skipped 标记（不进 B/C）。"""
    from _eval_factor_zoo import stages

    (tmp_path / "fields_report.json").write_text(
        json.dumps({"pass": False, "computable": [], "total": 25}), encoding="utf-8"
    )

    result = stages.stage_signals(tmp_path)

    assert result == {"skipped": True, "pass": False}
    written = stages._read_json(tmp_path / "signals_report.json")
    assert written["skipped"] is True and written["pass"] is False
    assert written["ratio"] == 0.0


# ── 阶段 4：冷启动样本与耗时预算 ─────────────────────────────


def _timed(value):
    """返回「耗时约 2ms 再给值」的探针替身（保证冷延迟非 0，可被均值采纳）。"""

    def _probe(*_args, **_kwargs):
        time.sleep(0.002)
        return value

    return _probe


def test_stage_signals_tolerates_empty_bars_and_string_scalars(zoo, staged_dir):
    """空 bars 代码不参与横截面；财报字段为字符串时先试转 float（不可转按缺失计）。"""
    from _eval_factor_zoo import stages

    baseline = stages._read_json(staged_dir / "signals_report.json")
    probe = stages._read_json(staged_dir / "probe_cache.json")
    probe["bars_by_code"]["EMPTY001"] = []
    probe["fin_indicator"][POOL_CODES[0]] = {"roe": "12.5", "revenue_yoy": "n/a", "gross_margin": 31}
    stages._write_json(staged_dir / "probe_cache.json", probe)

    report = stages.stage_signals(staged_dir)

    assert report["factor_series_sizes"] == baseline["factor_series_sizes"], "无 bars 的代码不改变横截面序列"
    assert "fund_roe" in report["factor_series_sizes"], "可转 float 的字符串财报值应照常入序列"
    assert report["denom"] == baseline["denom"]


def test_stage_signals_degrades_families_with_empty_series(zoo, tmp_path):
    """指数窗口过短 → 各信号族序列为空，按「数据不足」降级而非异常。"""
    from _eval_factor_zoo import catalog, stages

    stages._write_json(
        tmp_path / "factor_catalog.json",
        {"catalog": [{"slug": "fund_pb", "label": "市净率", "fields": ["bars", "valuation"], "min_bars": 25}]},
    )
    stages._write_json(
        tmp_path / "fields_report.json",
        {"pass": True, "computable": ["fund_pb"], "total": 1},
    )
    stages._write_json(
        tmp_path / "probe_cache.json",
        {
            "bars_by_code": {code: _bars(3) for code in POOL_CODES},
            "index_bars": _bars(3),
            "valuation": {code: {"pb": 1.5} for code in POOL_CODES},
            "fin_indicator": {},
        },
    )

    report = stages.stage_signals(tmp_path)

    assert report["skipped"] is False
    assert report["family_series_sizes"] == {}
    daily = {k: v for k, v in report["family_degraded"].items() if k != catalog.FAMILY_REBALANCE}
    assert daily, "日频信号族应全部因序列为空而降级"
    assert set(daily.values()) == {"序列为空（数据不足）"}
    assert catalog.FAMILY_REBALANCE in report["family_degraded"]


def test_pool_mean_returns_skips_bars_without_valid_date_or_close(zoo):
    """池均值日收益只采纳「日期是字符串且收益非 NaN」的样本（缺日期日不入序列）。"""
    from _eval_factor_zoo import stages

    bars = {
        code: [
            {"close": 10.0},  # 首根缺日期且无前值 → 收益 NaN
            {"date": "2025-01-02", "close": 11.0},
            {"date": "2025-01-03", "close": 12.0},
        ]
        for code in POOL_CODES
    }
    mean = stages._pool_mean_returns(bars, [])

    assert set(mean) == {"2025-01-02", "2025-01-03"}
    assert mean["2025-01-02"] == pytest.approx(0.1)


def test_measure_cold_sample_counts_only_cold_successes(zoo, tmp_path, monkeypatch):
    """冷样本采集：成功的冷请求计入均值，失败样本单独记录错误且不计入。"""
    from _eval_factor_zoo import catalog, stages

    monkeypatch.setattr(stages, "PROJECT_ROOT", tmp_path)  # 空缓存目录 → 全部按冷请求计
    monkeypatch.setattr(stages, "probe_bars", _timed([{"date": "2025-01-02", "close": 1.0}]))
    monkeypatch.setattr(stages, "probe_valuation", _timed({"pb": 1.0}))

    def _broken_fin(_code):
        raise RuntimeError("财务接口不可用")

    monkeypatch.setattr(stages, "probe_fin_indicator", _broken_fin)
    monkeypatch.setattr(stages, "probe_index", _timed([{"date": "2025-01-02", "close": 3.0}]))

    out = stages.measure_cold_sample()

    assert len(out["samples"]) == len(catalog.COLD_SAMPLE_CODES)
    assert out["index_ok"] is True
    for entry in out["samples"]:
        assert set(entry) >= {"code", "bars", "valuation", "fin_indicator"}
        assert entry["bars"]["cached"] is False and entry["bars"]["ok"] is True
        assert entry["valuation"]["ok"] is True
        assert entry["fin_indicator"]["ok"] is False
        assert "fin_indicator_error" in entry
        assert entry["fin_indicator"]["seconds"] >= 0.0
    # 冷请求数 = 样本数 × 成功字段类型数（bars+valuation），失败样本不计
    assert out["cold_request_count"] == len(catalog.COLD_SAMPLE_CODES) * 2
    assert out["mean_cold_request_seconds"] > 0.0


def test_measure_cold_sample_marks_cached_samples_warm(zoo, tmp_path, monkeypatch):
    """命中缓存的样本按暖值标记，不计入冷均值（否则冷启动估算会被缓存命中稀释）。"""
    from _eval_factor_zoo import catalog, stages

    cache_dir = tmp_path / "data" / "cache"
    cache_dir.mkdir(parents=True)
    for code in catalog.COLD_SAMPLE_CODES:
        (cache_dir / f"history_stock_{code}_2025.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(stages, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(stages, "probe_bars", _timed([{"date": "2025-01-02", "close": 1.0}]))
    monkeypatch.setattr(stages, "probe_valuation", _timed({"pb": 1.0}))
    monkeypatch.setattr(stages, "probe_fin_indicator", _timed({"roe": 1.0}))
    monkeypatch.setattr(stages, "probe_index", _timed([{"date": "2025-01-02", "close": 3.0}]))

    out = stages.measure_cold_sample()

    assert all(entry["bars"]["cached"] is True for entry in out["samples"])
    assert out["cold_request_count"] == len(catalog.COLD_SAMPLE_CODES) * 2  # bars 暖、其余冷
    assert out["mean_cold_request_seconds"] > 0.0


def test_measure_cold_sample_index_failure_is_recorded(zoo, tmp_path, monkeypatch):
    """指数探针失败只落 index_ok=False，不中断采集（估算是性能评测，不该整体失败）。"""
    from _eval_factor_zoo import stages

    monkeypatch.setattr(stages, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(stages, "probe_bars", _timed([{"date": "2025-01-02", "close": 1.0}]))
    monkeypatch.setattr(stages, "probe_valuation", _timed({"pb": 1.0}))
    monkeypatch.setattr(stages, "probe_fin_indicator", _timed({"roe": 1.0}))

    def _broken_index():
        raise OSError("指数源不可达")

    monkeypatch.setattr(stages, "probe_index", _broken_index)

    out = stages.measure_cold_sample()

    assert out["index_ok"] is False
    assert out["index_probe_seconds"] >= 0.0
    assert out["cold_request_count"] == len(out["samples"]) * 3


def test_stage_timing_estimates_cold_from_sample_mean(zoo, staged_dir, monkeypatch):
    """耗时阶段：冷启动估算 = 冷样本均延迟 × 全量请求数 + 指数探测，并落 timing_report.json。"""
    from _eval_factor_zoo import stages

    monkeypatch.setattr(stages, "PROJECT_ROOT", staged_dir)  # 空缓存 → 样本按冷请求计
    monkeypatch.setattr(stages, "probe_bars", _timed([{"date": "2025-01-02", "close": 1.0}]))
    monkeypatch.setattr(stages, "probe_valuation", _timed({"pb": 1.0}))
    monkeypatch.setattr(stages, "probe_fin_indicator", _timed({"roe": 1.0}))
    monkeypatch.setattr(stages, "probe_index", _timed([{"date": "2025-01-02", "close": 3.0}]))
    monkeypatch.setattr(
        stages,
        "read_report_baseline",
        lambda _path=None: {"available": True, "n": 3, "median_seconds": 60.0},
    )

    fields_report = stages._read_json(staged_dir / "fields_report.json")
    report = stages.stage_timing(staged_dir)

    assert report["metric"] == "C"
    assert report["estimated_requests"] == fields_report["pool_size"] * 3 + 1
    assert report["skipped_signals"] is False
    assert report["warm_seconds"] >= 0.0
    assert report["cold_seconds"] > 0.0
    assert report["cold_seconds"] == pytest.approx(
        report["cold_sample"]["mean_cold_request_seconds"] * report["estimated_requests"]
        + report["cold_sample"]["index_probe_seconds"],
        abs=1e-3,
    )
    assert report["cold_basis"].startswith("池外冷样本均延迟")
    assert stages._read_json(staged_dir / "timing_report.json") == report


def test_stage_timing_warm_is_zero_when_signals_skipped(zoo, staged_dir, monkeypatch):
    """signals 提前终态时温态耗时按 0 计，并在报告标记 skipped_signals。"""
    from _eval_factor_zoo import stages

    signals = stages._read_json(staged_dir / "signals_report.json")
    stages._write_json(staged_dir / "signals_report.json", {**signals, "skipped": True, "compute_seconds": 9.5})
    monkeypatch.setattr(
        stages,
        "measure_cold_sample",
        lambda: {"samples": [], "mean_cold_request_seconds": 0.05, "index_probe_seconds": 0.1},
    )
    monkeypatch.setattr(
        stages,
        "read_report_baseline",
        lambda _path=None: {"available": True, "n": 1, "median_seconds": 100.0},
    )

    report = stages.stage_timing(staged_dir)

    assert report["skipped_signals"] is True
    assert report["warm_seconds"] == 0.0
    assert "ratio" in report


def test_stage_timing_reports_undetermined_without_cold_requests(zoo, staged_dir, monkeypatch):
    """无有效冷请求 → 冷启动不可判定（fail-closed 不通过），并如实写明原因。"""
    from _eval_factor_zoo import stages

    monkeypatch.setattr(
        stages,
        "measure_cold_sample",
        lambda: {"samples": [], "mean_cold_request_seconds": None, "index_probe_seconds": 0.2},
    )
    monkeypatch.setattr(
        stages,
        "read_report_baseline",
        lambda _path=None: {"available": True, "n": 1, "median_seconds": 100.0},
    )

    report = stages.stage_timing(staged_dir)

    assert "ratio" not in report
    assert report["pass"] is False
    assert report["cold_basis"] == "冷样本无有效冷请求（全部缓存命中或失败）"
