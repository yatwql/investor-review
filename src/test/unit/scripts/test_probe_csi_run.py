"""`_probes/csi.run`（CSI 风格指数可用性探测主流程）单元测试。

run 的职责是「把逐代码探测收敛成一条可行性结论」，因此测试关注：参数收敛
（--days/--codes/--no-extra 的实际生效）、单代码异常不中断整轮、
「条数够但停更」被判不可用、以及三档结论的打印分支。取数函数注入替身，不触网。
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _probes import csi  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _bars(count: int, days_ago: int = 1) -> list[dict]:
    """count 根日 K，最新一根距今 days_ago 天（用于控制新鲜度）。"""
    latest = date.today() - timedelta(days=days_ago)
    return [{"date": (latest - timedelta(days=count - 1 - i)).isoformat(), "close": 100.0 + i} for i in range(count)]


def _record_probe(monkeypatch, bars_by_code: dict[str, list[dict]], raising: set[str] | None = None):
    """把 probe_code 换成按代码返回的替身，并记录每次调用的参数。"""
    calls: list[dict] = []
    raising = raising or set()

    def _probe(code: str, days: int, provider: str = "tencent"):
        calls.append({"code": code, "days": days, "provider": provider})
        if code in raising:
            raise RuntimeError(f"{code} 上游异常")
        return bars_by_code.get(code, [])

    monkeypatch.setattr(csi, "probe_code", _probe)
    return calls


def test_run_reports_full_five_factor_feasibility(monkeypatch, capsys):
    """5 个主候选条数足且新鲜 → 全量 5 因子可行；窗口参数被夹到 provider 上限。"""
    fresh = {code: _bars(40) for code, _name in csi._CSI_CANDIDATES}
    fresh[csi._CSI_EXTRA[0][0]] = _bars(40)
    calls = _record_probe(monkeypatch, fresh)

    args = csi.build_parser().parse_args(["--days", "5000", "--threshold", "20"])
    code = csi.run(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "全量 5 因子可行" in out
    assert "窗口 2000 天" in out, "--days 须被夹到 Tencent K 线上限 2000"
    assert all(call["days"] == 2000 for call in calls)
    # 附加探测代码也参与取数并由「可作补充候选」一行点名
    assert {call["code"] for call in calls} >= {code for code, _name in csi._CSI_EXTRA}
    assert f"附加探测 {csi._CSI_EXTRA[0][0]}" in out


def test_run_reports_stopped_indices_as_unusable(monkeypatch, capsys):
    """条数够但最新日期过旧 → 判停更不可用（只按条数判会误判有效）。"""
    stale = {code: _bars(40, days_ago=400) for code, _name in csi._CSI_CANDIDATES}
    _record_probe(monkeypatch, stale)

    code = csi.run(csi.build_parser().parse_args(["--stale", "120"]))

    out = capsys.readouterr().out
    assert code == 0
    assert "停更代码" in out
    assert any(symbol in out for symbol in (code_name for code_name, _ in csi._CSI_CANDIDATES))
    assert "不可行" in out, "主候选全部停更时结论应为不可行"


def test_run_survives_single_code_exception(monkeypatch, caplog, capsys):
    """单代码探测抛异常 → 记警告并当作无数据，其余候选继续评估（3 因子档带停更提示）。"""
    healthy = {code: _bars(40) for code, _name in csi._CSI_CANDIDATES[1:]}
    stopped = csi._CSI_CANDIDATES[1][0]
    healthy[stopped] = _bars(40, days_ago=400)  # 另一个候选条数够但停更
    raising = {csi._CSI_CANDIDATES[0][0]}
    _record_probe(monkeypatch, healthy, raising=raising)

    with caplog.at_level(logging.WARNING, logger="invest"):
        code = csi.run(csi.build_parser().parse_args([]))

    out = capsys.readouterr().out
    assert code == 0
    assert "探测异常" in caplog.text
    assert "[ERR]" in out
    assert "MVP 3 因子" in out, "剩 3 个可用候选时应落到 3 因子档"
    assert "停更指数" in out, "3 因子档须提示停更指数要找替代代理"


def test_run_marks_short_series_and_probes_extra(monkeypatch, capsys):
    """条数不足（但非空）在逐代码行判 [!]；附加代码新鲜时提示可作低波补充候选。"""
    codes = [code for code, _name in csi._CSI_CANDIDATES]
    extra_code = csi._CSI_EXTRA[0][0]
    bars = {code: _bars(3) for code in codes}
    bars[codes[0]] = _bars(40)  # 仅一个候选条数达标
    bars[extra_code] = _bars(40)
    _record_probe(monkeypatch, bars)

    csi.run(csi.build_parser().parse_args(["--threshold", "20"]))

    out = capsys.readouterr().out
    assert f"[OK] {codes[0]}" in out, "条数达标的代码判可用"
    assert f"[!] {codes[1]}" in out, "条数不足（非空）的代码判不可用"
    assert f"附加探测 {extra_code}" in out, "新鲜的低波代码应提示可作补充候选"


def test_run_honours_codes_override_and_no_extra(monkeypatch, capsys):
    """--codes 覆盖候选表（对照验证用），--no-extra 不再附带低波代码。"""
    calls = _record_probe(monkeypatch, {"sh000919": _bars(40)})

    args = csi.build_parser().parse_args(["--codes", "sh000919", "--no-extra", "--provider", "sina"])
    csi.run(args)

    out = capsys.readouterr().out
    assert [call["code"] for call in calls] == ["sh000919"]
    assert calls[0]["provider"] == "sina"
    assert "1 个候选代码" in out
    assert "附加探测" not in out


def test_run_with_no_data_prints_infeasible_verdict(monkeypatch, capsys):
    """全部候选无数据 → 逐代码 ERR + 不可行结论（不除零、不崩）。"""
    _record_probe(monkeypatch, {})

    csi.run(csi.build_parser().parse_args(["--no-extra"]))

    out = capsys.readouterr().out
    assert "无有效数据" in out
    assert "不可行" in out
    assert "主候选（5 因子）有效代码: 无" in out
