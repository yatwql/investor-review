"""报告管线测试必须声明离线桩 —— 否则会真起健康检查线程（真实网络 + akshare V8）。

背景：`generate_report()` / `prepare_report_data()` 会顺带提交数据源健康检查
（`run_health_checks`）到后台线程。单测里让它真跑有两个后果：一是探针真的发包、
撞网络守卫后退避重试把整套从 1.5 分钟拖到十几分钟；二是 akshare 的
`py_mini_racer`（V8）在多线程并发初始化时会**段错误**直接崩掉 xdist worker
（CI 表现为 `worker 'gwN' crashed`，且偶发、难定位）。

契约：任何测试文件在模块级出现对上述三个入口的**真实调用**时，必须声明
`offline_external_sources`（HTTP 出口换离线桩、交易日历回空集、退避置 0、
akshare 换空桩 —— 探针即时失败，零等待零 V8）。

豁免表只留给「虽然出现调用但不会真的跑管线」的文件（如整体 patch 掉入口），
并要求豁免项仍含该调用，防止表被当成长期免死金牌。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_TEST_ROOT = Path(__file__).resolve().parents[1]

#: 会触发数据源健康检查/真实取数的管线入口（语句位置的调用，不含 patch/@patch 目标）
_PIPELINE_CALL = re.compile(
    r"^\s*(?:\w+\s*=\s*)?(?:orchestrator\.)?(generate_report|prepare_report_data|run_health_checks)\(",
    re.MULTILINE,
)

#: 离线桩声明（`pytest.mark.usefixtures(...)` 或 fixture 形参都算）
_OFFLINE_MARKER = "offline_external_sources"

#: 豁免表：相对 `src/test/` 的路径 → 理由（须写明为何不会真跑管线）
_EXEMPT: dict[str, str] = {}


def _test_files() -> list[Path]:
    return sorted(_TEST_ROOT.rglob("test_*.py"))


def _declares_offline(source: str) -> bool:
    return _OFFLINE_MARKER in source


def _pipeline_callers() -> dict[str, set[str]]:
    """``相对路径 → 命中的管线入口集合``（只列真实调用者）。"""
    found: dict[str, set[str]] = {}
    for path in _test_files():
        source = path.read_text(encoding="utf-8")
        hits = set(_PIPELINE_CALL.findall(source))
        if hits:
            found[path.relative_to(_TEST_ROOT).as_posix()] = hits
    return found


class TestOfflinePipelineContract:
    """真实跑报告管线的测试文件必须声明离线桩。"""

    def test_pipeline_tests_declare_offline_fixture(self):
        offenders: list[str] = []
        for rel, hits in _pipeline_callers().items():
            if rel in _EXEMPT:
                continue
            if not _declares_offline((_TEST_ROOT / rel).read_text(encoding="utf-8")):
                offenders.append(f"{rel} :: {sorted(hits)}")
        assert not offenders, (
            "以下测试真实调用报告管线却未声明 offline_external_sources"
            "（会真起健康检查线程：网络退避拖慢 + akshare V8 并发段错误）：\n" + "\n".join(offenders)
        )

    def test_exemptions_still_call_pipeline(self):
        """豁免表不得成陈货：被豁免的文件仍须真的调用管线入口。"""
        callers = _pipeline_callers()
        stale = [rel for rel in _EXEMPT if rel not in callers]
        assert not stale, f"豁免表里的文件已不再调用管线入口，请删除豁免：{stale}"

    def test_scanner_covers_known_pipeline_files(self):
        """扫描器自身不能退化成空跑（正则失效时本契约会静默放行）。

        用「已知文件是子集」表达，不写死总数——新增管线测试不需要改本条。
        """
        known = {
            "unit/report/test_orchestrator_generate_report.py",
            "unit/report/test_orchestrator.py",
            "unit/report/test_run_integrity.py",
            "scenario/basic/test_pipeline_smoke.py",
        }
        detected = set(_pipeline_callers())
        assert known <= detected, f"扫描器未识别到这些已知管线测试：{sorted(known - detected)}"
