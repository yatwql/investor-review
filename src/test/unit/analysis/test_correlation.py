"""持仓相关性矩阵纯计算层单元测试。

覆盖：
  1. 已知答案：完全正相关（r=1）、完全负相关（r=-1）、缩放不改变 r
  2. 不显著配对：sin vs cos → p≥0.05，significant=False
  3. 矩阵布局：下三角（row>col 有值）、对角=1.0、上三角 None
  4. 配对明细按 |r| 降序
  5. 数据不足分支：重叠样本 <60 / 单品种 → available=False，status="insufficient"
  6. 名称回退：names_by_code 缺失时回退 code 本身
  7. 数据契约键完整性（含 unavailable_result 工厂）
  8. 常数序列 → (0.0, 1.0) 不显著（绝不硬算）
  9. 数值真值：p 链（df / t / 1-r² / 2(1-CDF)）与 _pearson_r 对齐手算值与解析解
     （df=1 Cauchy、df=2 闭式、大偏移窄幅的中心化精度、±1 端点）
 10. 阈值边界：常数检测与显著性判定均为严格小于（等值不触发）
 11. 滚动端点首个 (date, r) 手算值、完整窗等值端点、全窗皆空的降级结构与 notes 文案

运行：
  python -m pytest src/test/unit/analysis/test_correlation.py -v
"""

from __future__ import annotations

import math

import pytest

from src.python.analysis import correlation as correlation_module
from src.python.analysis.correlation import (
    DEFAULT_WINDOW,
    MIN_SAMPLES,
    ROLLING_WINDOWS,
    SIGNIFICANCE_LEVEL,
    _pearson_pvalue,
    _pearson_r,
    compute_correlation_matrix,
    unavailable_result,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]

_CONTRACT_KEYS = {
    "available",
    "status",
    "window",
    "sample_count",
    "codes",
    "names",
    "matrix",
    "p_values",
    "pairs",
    "insufficient_codes",
    "note",
}


def _dates(n: int, start: str = "2026-01-05") -> list[str]:
    """生成 n 个连续 ISO 日期（升序）。"""
    from datetime import date, timedelta

    d = date.fromisoformat(start)
    out: list[str] = []
    for _ in range(n):
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _returns(series: list[float], n: int | None = None) -> list[dict]:
    """将数值序列包装为 [{"date", "return"}]（升序）。"""
    dates = _dates(len(series) if n is None else n)
    if n is not None and len(series) < n:
        # 头部补零对齐长度（等价于无交易日期收益 0）
        series = [0.0] * (n - len(series)) + list(series)
    return [{"date": dates[i], "return": float(series[i])} for i in range(len(series))]


def _sin(n: int, freq: float = 5.0) -> list[float]:
    return [math.sin(i / freq) for i in range(n)]


class TestKnownAnswerCorrelation:
    """完全正/负相关已知答案验证。"""

    def test_identical_sequences_corr_is_one(self):
        """完全相同序列 → r=1.0，p=0，显著。"""
        x = _sin(80)
        res = compute_correlation_matrix(
            {"a": _returns(x), "b": _returns(x)},
            {"a": "A", "b": "B"},
        )
        assert res["available"] is True
        # 下三角：matrix[1][0] = r(a, b)
        assert abs(res["matrix"][1][0] - 1.0) < 1e-9
        pair = res["pairs"][0]
        assert pair["code_a"] == "b" and pair["code_b"] == "a"
        assert abs(pair["pearson"] - 1.0) < 1e-9
        assert pair["significant"] is True

    def test_negated_sequences_corr_is_minus_one(self):
        """完全相反序列 → r=-1.0，p=0，显著。"""
        x = _sin(80)
        y = [-v for v in x]
        res = compute_correlation_matrix(
            {"a": _returns(x), "b": _returns(y)},
            {"a": "A", "b": "B"},
        )
        assert res["available"] is True
        assert abs(res["matrix"][1][0] + 1.0) < 1e-9
        pair = res["pairs"][0]
        assert abs(pair["pearson"] + 1.0) < 1e-9
        assert pair["significant"] is True

    def test_scale_and_shift_do_not_change_r(self):
        """y = a + b*x 线性变换不改变相关系数。"""
        x = _sin(80)
        y = [3.0 + 2.0 * v for v in x]
        res = compute_correlation_matrix({"a": _returns(x), "b": _returns(y)})
        assert abs(res["matrix"][1][0] - 1.0) < 1e-9

    def test_pearson_pvalue_constant_series(self):
        """常数序列 → (0.0, 1.0) 不显著，绝不硬算。"""
        const = [0.01] * 60
        noise = _sin(60)
        r, p = _pearson_pvalue(const, noise)
        # 容差断言：CPython sum 实现差异（3.12+ 误差补偿求和 vs 3.11 朴素累加）
        # 使常数序列标准差可能是 ~1e-17 的极小非零值而非精确 0.0，
        # 断言应验证"行为"（不硬算）而非精确等于 0.0
        assert abs(r) < 1e-12 and p == 1.0

    def test_pearson_pvalue_near_constant_series(self):
        """近常数序列（波动 ~1e-14）→ 仍判常数返回 (0.0, 1.0)，不因浮点误差硬算。"""
        const = [0.01] * 60
        # 叠加 1e-14 量级抖动，模拟均值舍入误差导致的极小非零标准差
        const = [v + 1e-14 * (i % 3) for i, v in enumerate(const)]
        noise = _sin(60)
        r, p = _pearson_pvalue(const, noise)
        assert abs(r) < 1e-12 and p == 1.0


class TestPearsonStatisticNumericTruth:
    """(r, p) 数值真值：df / t / 1-r² / 双侧 p 每一环都必须精确（手推 + 解析解）。"""

    def test_three_samples_compute_against_cauchy_closed_form(self):
        """n=3（df=1，合法下限）必须参与计算：r=9/√84，p=1-2·atan(3√3)/π。

        手推：x=[1,2,3]、y=[1,2,4] → mx=2、my=7/3、num=3、sx=√2、sy=√42/3
        → r=9/√84；df=1 时 t 分布即标准 Cauchy，p = 1 - 2·atan(t)/π
        （t²=r²/(1-r²)=27 → t=3√3），此式不经被测 _t_cdf。
        """
        r, p = _pearson_pvalue([1.0, 2.0, 3.0], [1.0, 2.0, 4.0])
        assert r == pytest.approx(9.0 / math.sqrt(84.0), rel=1e-12)
        assert p == pytest.approx(1.0 - 2.0 * math.atan(3.0 * math.sqrt(3.0)) / math.pi, rel=1e-9)

    def test_four_samples_compute_against_df2_closed_form(self):
        """n=4（df=2）→ r=6/√50；df=2 的 t CDF 有闭式，故 p = 1-|r|。

        手推：x=[1,2,3,4]、y=[2,1,4,5] → num=6、sx=√5、sy=√10 → r=6/√50；
        df=2 时 t²/(2+t²)=r²，p = 1 - |r| = 1 - 6/√50。
        """
        r, p = _pearson_pvalue([1.0, 2.0, 3.0, 4.0], [2.0, 1.0, 4.0, 5.0])
        assert r == pytest.approx(6.0 / math.sqrt(50.0), rel=1e-12)
        assert p == pytest.approx(1.0 - 6.0 / math.sqrt(50.0), rel=1e-9)
        # p 关于 |r| 单调递减：同 df 下更弱的相关（r=0.6）必须给出更大的 p
        _, p_weak = _pearson_pvalue([1.0, 2.0, 3.0, 4.0], [2.0, 1.0, 4.0, 3.0])
        assert p_weak == pytest.approx(0.4, rel=1e-9)
        assert p < p_weak


class TestPearsonRKnownAnswers:
    """_pearson_r 数值真值：中心化、平方项与归一化分母任一错位都会被手算值判出。"""

    def test_three_sample_lower_bound_computes(self):
        """n=3（合法下限）→ 正常返回 r=1 而非 None（不落 <3 的早退）。"""
        assert _pearson_r([1.0, 2.0, 3.0], [3.0, 5.0, 7.0]) == pytest.approx(1.0, abs=1e-9)

    def test_perfect_linear_map_hits_both_endpoints(self):
        """y=3+2x → r=1；y=5-x → r=-1（端点钳位，符号不得翻转）。"""
        x = [1.0, 2.0, 3.0, 4.0]
        assert _pearson_r(x, [3.0 + 2.0 * v for v in x]) == pytest.approx(1.0, abs=1e-9)
        assert _pearson_r(x, [5.0 - v for v in x]) == pytest.approx(-1.0, abs=1e-9)

    def test_hand_computed_half_correlation(self):
        """x=[1..4]、y=[2,1,4,3]：num=3、sx=sy=√5 → r=3/5=0.6。

        归一化分母必须是 sx·sy：写成 sx/sy 会得 num·(sy/sx)=3 再被钳成 1.0。
        """
        assert _pearson_r([1.0, 2.0, 3.0, 4.0], [2.0, 1.0, 4.0, 3.0]) == pytest.approx(0.6, rel=1e-12)

    def test_large_offset_narrow_spread_keeps_centering(self):
        """均值 1e7、振幅 1e-2 的同构数据仍须给出 r=0.6（中心化只能减均值）。

        均值未精确可表示时 Σ(b-my) 留有 ~n·ulp(1e7) 的浮点残差；把 (a-mx) 写成
        (a+mx)，该残差被 2·mx 放大到 num 量级（r 由 0.6 变成钳位后的 -1.0）。
        """
        offset, step = 1e7, 1e-2
        x = [offset + i * step for i in range(4)]
        y = [offset + (k - 1) * step for k in (2, 1, 4, 3)]
        assert _pearson_r(x, y) == pytest.approx(0.6, rel=1e-9)
        # _pearson_pvalue 的 num 用同一中心化口径，同一残差同样会把它带偏
        r_pvalue, _ = _pearson_pvalue(x, y)
        assert r_pvalue == pytest.approx(0.6, rel=1e-9)


class TestThresholdBoundaries:
    """阈值边界：常数检测与显著性判定都用严格小于——等值不得触发。"""

    def test_constant_threshold_equal_to_std_still_computes(self, monkeypatch):
        """标准差恰等于常数阈值 → 不判常数，仍返回真实 (r, p)。

        阈值语义是「低于才判常数」；放宽成 <= 会让等值序列退化成虚假的不显著白格。
        x=[1,2,3,4] 与 y=[2,1,4,3] 的离差集合相同，故 sx=sy，取 sx 作为阈值即落在等值点。
        """
        x = [1.0, 2.0, 3.0, 4.0]
        y = [2.0, 1.0, 4.0, 3.0]
        mx = math.fsum(x) / len(x)
        sx = math.sqrt(math.fsum((a - mx) ** 2 for a in x))
        monkeypatch.setattr(correlation_module, "_CONSTANT_EPS", sx)
        r, p = _pearson_pvalue(x, y)
        assert r == pytest.approx(0.6, rel=1e-9)
        assert p == pytest.approx(0.4, rel=1e-9)
        assert _pearson_r(x, y) == pytest.approx(0.6, rel=1e-9)

    def test_significance_threshold_equal_to_p_is_not_significant(self, monkeypatch):
        """p 恰等于显著性阈值 → 不显著（判定口径是 p < 阈值，不是 <=）。"""
        n = MIN_SAMPLES  # 窗口即全部样本：生产侧与本侧用同一批浮点值算出同一个 p
        x = _sin(n)
        y = [math.cos(i / 7.0) for i in range(n)]
        _, raw_p = _pearson_pvalue(x, y)
        assert raw_p < SIGNIFICANCE_LEVEL  # 该对在默认阈值下显著，阈值调到 p 上即成等值边界
        monkeypatch.setattr(correlation_module, "SIGNIFICANCE_LEVEL", raw_p)
        res = compute_correlation_matrix({"a": _returns(x), "b": _returns(y)})
        assert res["pairs"][0]["significant"] is False


class TestInsignificantPair:
    """不显著配对（p≥0.05 → 白色格）。"""

    def test_sin_cos_pair_insignificant(self):
        """sin vs cos（正交近零相关）→ p≥0.05，significant=False。"""
        x = _sin(80, 7.0)
        y = [math.cos(i / 7.0) for i in range(80)]
        res = compute_correlation_matrix(
            {"a": _returns(x), "b": _returns(y)},
            {"a": "A", "b": "B"},
        )
        assert res["available"] is True
        r_val = res["matrix"][1][0]
        p_val = res["p_values"][1][0]
        assert p_val >= SIGNIFICANCE_LEVEL
        assert abs(r_val) < 0.5
        assert res["pairs"][0]["significant"] is False


class TestMatrixLayout:
    """下三角矩阵布局。"""

    def _three_code_result(self):
        x = _sin(80)
        y = [math.cos(i / 7.0) for i in range(80)]
        z = [-v for v in x]
        return compute_correlation_matrix(
            {"a": x and _returns(x), "b": _returns(y), "c": _returns(z)},
            {"a": "A", "b": "B", "c": "C"},
        )

    def test_lower_triangular_layout(self):
        """row>col 有值、对角=1.0、上三角 None。"""
        res = self._three_code_result()
        matrix = res["matrix"]
        n = len(res["codes"])
        for i in range(n):
            assert matrix[i][i] == 1.0  # 对角
            for j in range(i + 1, n):
                assert matrix[i][j] is None  # 上三角留空
        # 下三角非 None
        for i in range(n):
            for j in range(i):
                assert matrix[i][j] is not None

    def test_pairs_sorted_by_abs_r_desc(self):
        """配对明细按 |r| 降序。"""
        res = self._three_code_result()
        rs = [abs(p["pearson"]) for p in res["pairs"]]
        assert rs == sorted(rs, reverse=True)

    def test_each_pair_has_required_fields(self):
        """每条配对含 code_a/name_a/code_b/name_b/pearson/p_value/significant/samples。"""
        res = self._three_code_result()
        for p in res["pairs"]:
            for field in ("code_a", "name_a", "code_b", "name_b", "pearson", "p_value", "significant", "samples"):
                assert field in p, f"配对缺少字段 {field}: {p}"


class TestInsufficientData:
    """数据不足（§1.4.5 降级治理）。"""

    def test_overlap_below_min_samples(self):
        """重叠样本 < MIN_SAMPLES → available=False，status="insufficient"。"""
        # a 只有 30 期、b 有 80 期，但日期完全错开（无重叠）
        dates_a = _dates(30, "2026-01-05")
        dates_b = _dates(80, "2026-03-05")
        a = [{"date": d, "return": 0.01} for d in dates_a]
        b = [{"date": d, "return": 0.02} for d in dates_b]
        res = compute_correlation_matrix({"a": a, "b": b})
        assert res["available"] is False
        assert res["status"] == "insufficient"
        assert res["pairs"] == []
        assert "a" in res["insufficient_codes"] and "b" in res["insufficient_codes"]

    def test_single_holding(self):
        """单品种（<MIN_HOLDINGS）→ 数据不足。"""
        x = _sin(80)
        res = compute_correlation_matrix({"a": _returns(x)})
        assert res["available"] is False
        assert res["status"] == "insufficient"

    def test_no_valid_returns(self):
        """全部品种无有效收益 → 数据不足。"""
        res = compute_correlation_matrix({"a": [], "b": []})
        assert res["available"] is False
        assert res["status"] == "insufficient"


class TestNameFallback:
    """名称回退。"""

    def test_missing_names_fall_back_to_code(self):
        """names_by_code 缺失 → 回退 code 本身。"""
        x = _sin(80)
        y = [-v for v in x]
        res = compute_correlation_matrix({"AAA": _returns(x), "BBB": _returns(y)})
        assert res["names"]["AAA"] == "AAA"
        pair = res["pairs"][0]
        assert pair["name_a"] == "BBB" and pair["name_b"] == "AAA"


class TestContract:
    """数据契约键完整性。"""

    def test_result_contains_contract_keys(self):
        x = _sin(80)
        y = [-v for v in x]
        res = compute_correlation_matrix({"a": _returns(x), "b": _returns(y)})
        assert set(res.keys()) >= _CONTRACT_KEYS

    def test_unavailable_result_carries_contract_keys(self):
        res = unavailable_result("insufficient", sample_count=10, insufficient_codes=["a"])
        assert set(res.keys()) >= _CONTRACT_KEYS
        assert res["available"] is False
        assert res["status"] == "insufficient"
        assert res["sample_count"] == 10
        assert res["insufficient_codes"] == ["a"]

    def test_window_and_sample_count(self):
        """window 不超过实际重叠样本数。"""
        x = _sin(80)
        y = [math.cos(i / 7.0) for i in range(80)]
        res = compute_correlation_matrix({"a": _returns(x), "b": _returns(y)})
        assert res["sample_count"] >= MIN_SAMPLES
        assert res["window"] <= DEFAULT_WINDOW


# ═══════════════════════════════════════════════════════════════
#  滚动趋势（组合平均 + 重点品对）
# ═══════════════════════════════════════════════════════════════


def _rolling_returns(n: int = 140) -> dict[str, list[dict]]:
    """合成三品种日收益底座：A 基准、B 同向强正、C 强反向（确定性波形，无随机源）。

    B = 0.9A + 异频小波、C = -0.9A + 异频小波 → A×B 强正、A×C 强负、B×C 强负。
    """
    base = _sin(n, freq=7.0)
    w_b = _sin(n, freq=3.1)
    w_c = [math.cos(i / 5.3) for i in range(n)]
    series_b = [0.9 * base[i] + 0.05 * w_b[i] for i in range(n)]
    series_c = [-0.9 * base[i] + 0.05 * w_c[i] for i in range(n)]
    return {
        "AAA": _returns(base),
        "BBB": _returns(series_b),
        "CCC": _returns(series_c),
    }


class TestRollingCorrelations:
    """compute_rolling_correlations：结构、同轴、截断口径与已知方向。"""

    CONTRACT_KEYS = {
        "available",
        "status",
        "windows",
        "min_samples",
        "portfolio",
        "focus_pairs",
        "coverage",
        "notes",
    }

    def test_contract_and_shared_axis(self):
        """契约键齐全；60/120 两窗共享同一端点轴；值域与 n_pairs 合法。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(
            _rolling_returns(),
            focus_pairs=[("AAA", "BBB")],
        )
        assert set(res.keys()) == self.CONTRACT_KEYS
        assert res["available"] is True and res["status"] == "ok"
        p60, p120 = res["portfolio"]["60"], res["portfolio"]["120"]
        assert p60 and p120
        # 同轴：两窗端点日期序列完全一致（渲染层共享 labels 的结构前提）
        assert [p["date"] for p in p60] == [p["date"] for p in p120]
        # 端点轴单调升序
        dates = [p["date"] for p in p60]
        assert dates == sorted(dates)
        for p in p60:
            assert -1.0 <= p["value"] <= 1.0
            assert p["n_pairs"] >= 1
        assert res["coverage"]["dates"] > 0
        assert res["coverage"]["first_date"] <= res["coverage"]["last_date"]
        assert res["notes"], "口径句必须外送（渲染层只引用不复述）"

    def test_focus_pair_direction_matches_construction(self):
        """构造方向可验证：A×B 末点强正、A×C 末点强负；日期 ⊆ 组合端点轴。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(
            _rolling_returns(),
            focus_pairs=[("AAA", "BBB"), ("AAA", "CCC")],
        )
        focus = {(f["code_a"], f["code_b"]): f for f in res["focus_pairs"]}
        s_ab = focus[("AAA", "BBB")]["series"]["60"]
        s_ac = focus[("AAA", "CCC")]["series"]["60"]
        assert s_ab and s_ac
        assert s_ab[-1]["value"] > 0.8, f"A×B 应强正，实际 {s_ab[-1]['value']}"
        assert s_ac[-1]["value"] < -0.8, f"A×C 应强负，实际 {s_ac[-1]['value']}"
        axis = {p["date"] for p in res["portfolio"]["60"]}
        assert all(pt["date"] in axis for pt in s_ab)
        assert all(pt["date"] in axis for pt in s_ac)

    def test_portfolio_avg_consistent_with_static_matrix(self):
        """滚动末点组合平均 ≈ 静态矩阵（同 60 窗）配对 r 的均值——两层口径同源。"""
        from src.python.analysis.correlation import (
            compute_correlation_matrix,
            compute_rolling_correlations,
        )

        data = _rolling_returns()
        static = compute_correlation_matrix(data)
        assert static["available"]
        expected = sum(p["pearson"] for p in static["pairs"]) / len(static["pairs"])
        res = compute_rolling_correlations(data)
        last_avg = res["portfolio"]["60"][-1]["value"]
        assert abs(last_avg - expected) < 0.01, f"滚动末点 {last_avg} vs 静态均值 {expected}"

    def test_short_history_truncates_window_with_note(self):
        """历史 < 120 期 → 120 窗按可得区间截断（序列仍产出 + notes 标注 + full_from=None）。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(n=80), focus_pairs=None)
        assert res["available"] is True
        p120 = res["portfolio"]["120"]
        assert p120, "历史不足时 120 窗应按可得区间截断计算，而非整段缺席"
        assert res["coverage"]["full_window_from"]["120"] is None
        assert any("120" in n and "按可得区间" in n for n in res["notes"]), res["notes"]

    def test_long_history_records_full_window_start(self):
        """历史 ≥ 120 期 → full_window_from 记录完整窗起始，截断段在 notes 说明。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(n=140))
        full_120 = res["coverage"]["full_window_from"]["120"]
        assert full_120 is not None
        assert any("120 日窗完整重叠自" in n for n in res["notes"]), res["notes"]

    def test_insufficient_single_code_keeps_structure(self):
        """单品种 → 不可用，但结构键仍在（渲染层无需分支判空）。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations({"AAA": _rolling_returns()["AAA"]})
        assert res["available"] is False and res["status"] == "insufficient"
        assert res["portfolio"] == {"60": [], "120": []}
        assert res["focus_pairs"] == [] and res["notes"] == []

    def test_unknown_focus_pair_skipped_with_note(self):
        """焦点对代码不在数据中 → 跳过并给出重点品对说明句。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(), focus_pairs=[("AAA", "ZZZ")])
        assert res["available"] is True
        assert res["focus_pairs"] == []
        assert any("重点品对" in n for n in res["notes"])

    def test_constant_code_contributes_no_pair(self):
        """常数收益品种与任何品种算不出 r → 其配对序列为空、组合平均只计其余对。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        data = _rolling_returns()
        flat = [{"date": r["date"], "return": 0.0} for r in data["AAA"]]
        data["DDD"] = flat
        res = compute_rolling_correlations(data, focus_pairs=[("AAA", "DDD")])
        assert res["available"] is True
        # A×D 全程常数 → 该对不产出任何端点 r；焦点对序列为空（渲染层写 --）
        focus_ad = next(f for f in res["focus_pairs"] if f["code_a"] == "AAA" and f["code_b"] == "DDD")
        assert focus_ad["series"]["60"] == []
        # 组合平均仍由 A×B/B×C/A×C 等有效对构成
        assert all(p["n_pairs"] >= 1 for p in res["portfolio"]["60"])

    def test_first_endpoint_value_is_hand_computable(self):
        """最小窗配置下首个端点 (date, r) 可手算：x=[1,2,3] vs y=[1,3,2] → r=1/(√2·√2)=0.5。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [1.0, 3.0, 2.0, 5.0, 4.0]
        dates = _dates(5)
        data = {
            "a": [{"date": d, "return": v} for d, v in zip(dates, xs)],
            "b": [{"date": d, "return": v} for d, v in zip(dates, ys)],
        }
        res = compute_rolling_correlations(data, windows=(3,), min_samples=3)
        assert res["available"] is True
        p3 = res["portfolio"]["3"]
        assert p3, "凑满 min_samples 的端点不得缺席"
        assert p3[0]["date"] == dates[2], "端点应为首个凑满 3 期的日期"
        assert p3[0]["value"] == pytest.approx(0.5, abs=1e-9)
        assert p3[0]["n_pairs"] == 1
        # 完整窗起点恰等首个端点：完整窗判定含等值端点（<= 而非 <）
        assert res["coverage"]["full_window_from"]["3"] == dates[2]

    def test_all_windows_empty_degrades_to_contract(self):
        """全窗皆空（两品种均为常数收益）→ 降级返回完整空结构，绝不返回 None。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        dates = _dates(MIN_SAMPLES + 10)
        data = {
            "a": [{"date": d, "return": 0.01} for d in dates],
            "b": [{"date": d, "return": 0.02} for d in dates],
        }
        res = compute_rolling_correlations(data)
        assert isinstance(res, dict)
        assert res["available"] is False and res["status"] == "insufficient"
        assert res["portfolio"] == {str(w): [] for w in ROLLING_WINDOWS}
        assert res["notes"] == []
        assert res["coverage"]["dates"] == 0

    def test_truncated_window_note_exact_text(self):
        """重叠 80 期 < 120 窗 → 截断分支文案带实际重叠期数与窗口期数。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(n=80))
        assert "历史仅 80 期重叠 < 120 日窗，该窗全程按可得区间截断计算" in res["notes"]

    def test_full_window_exactly_reaching_window_is_not_truncated(self):
        """重叠期数恰等于窗口期数（120）→ 走完整窗分支，不得误判为截断。"""
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(n=120))
        notes = res["notes"]
        assert any(n.startswith("120 日窗完整重叠自") for n in notes), notes
        assert not any("历史仅" in n for n in notes), notes
        assert res["coverage"]["full_window_from"]["120"] == _dates(120)[-1]

    def test_full_window_from_first_endpoint_needs_no_truncation_note(self):
        """首个端点即已完整窗（窗长 == min_samples）→ 无"更早端点按可得区间"标注。

        该标注只在完整窗起点晚于首个端点时才有意义；起点与首端点重合时并无更早的
        截断端点，标注必须同时满足"完整窗起点存在"与"起点晚于首端点"两个条件。
        """
        from src.python.analysis.correlation import compute_rolling_correlations

        res = compute_rolling_correlations(_rolling_returns(n=70), windows=(60,), min_samples=60)
        first_endpoint = res["portfolio"]["60"][0]["date"]
        assert res["coverage"]["full_window_from"]["60"] == first_endpoint
        assert not any("完整重叠自" in n for n in res["notes"]), res["notes"]
