"""模块级会话态复位契约：任何 ``global`` 改写的单例都要有测试复位入口。

为什么是个契约测试而不是逐条手写：``conftest`` 里那串复位调用是**约定**，靠人记住
「新增模块级状态时顺手加一行」必然漏；漏了的表现是测试顺序相关（xdist 换分片随机红），
而本地单进程顺序常常看不出来。本用例反向枚举 `src/python` 里所有经 ``global`` 改写的
模块级变量，要求所在模块提供复位入口**且**该入口被 ``conftest`` 调用——新增状态忘了
接线就直接红，不必等某次 CI 分片炸。

豁免只给「导入期常量」：它们的值来自环境/配置文件解析结果，用例改它属于改环境，
复位入口由各自的 reload/invalidate API 承担（已在表内注明理由）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PY_ROOT = _REPO_ROOT / "src" / "python"
_CONFTEST = _REPO_ROOT / "src" / "test" / "conftest.py"

#: 复位函数名口径（与 conftest 里那一串调用同源命名）
_RESET_NAME = re.compile(r"(reset|clear|invalidate|reload|discard|close)", re.IGNORECASE)

#: 导入期常量：值在 import 时定稿，用例改它属于改环境，复位由各自 API 承担
_INIT_TIME_CONSTANTS: dict[str, str] = {
    "src/python/core/logger.py": "日志路径/级别/颜色在导入期由环境解析，改动走 reload_logger_config()",
    "src/python/llm/pricing.py": "定价时区与时段常量由 reload_pricing() 整体重建（该入口已在 conftest）",
    "src/python/config/_config_defaults.py": "配置路径覆写由专用 setter 显式设置，用例自带复位",
    "src/python/config/_core.py": "配置缓存由 _clear_config_cache() 复位（该入口已在 conftest）",
    "src/python/cache/_cache_refresh.py": "按需创建的线程池单例：无结果缓存、不跨用例保留语义",
}


def _module_globals(path: Path) -> set[str]:
    """该模块里经 ``global`` 语句改写的模块级变量名（= 运行期会被重新绑定的状态）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            names.update(node.names)
    return names


def _reset_functions(path: Path) -> list[str]:
    """模块顶层定义的复位类函数名（reset/clear/invalidate/reload/discard/close）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef) and _RESET_NAME.search(node.name)]


def _modules_with_global_state() -> dict[str, set[str]]:
    """``相对路径 → 被 global 改写的变量集合``（只列非空者）。"""
    found: dict[str, set[str]] = {}
    for path in sorted(_PY_ROOT.rglob("*.py")):
        names = _module_globals(path)
        if names:
            found[path.relative_to(_REPO_ROOT).as_posix()] = names
    return found


class TestModuleStateResetContract:
    """每个持有运行期模块状态的模块都必须有复位入口，且该入口被 conftest 调用。"""

    def test_every_stateful_module_is_reset_by_conftest(self):
        conftest_source = _CONFTEST.read_text(encoding="utf-8")
        offenders: list[str] = []
        for rel, names in _modules_with_global_state().items():
            if rel in _INIT_TIME_CONSTANTS:
                continue
            resets = _reset_functions(_REPO_ROOT / rel)
            wired = [name for name in resets if f"{name}(" in conftest_source]
            if not wired:
                offenders.append(f"{rel} :: globals={sorted(names)} resets={resets}")
        assert not offenders, "以下模块级状态没有接入 conftest 复位：\n" + "\n".join(offenders)

    def test_allowlist_entries_still_hold_state(self):
        """豁免表不得成为陈货：被豁免的文件仍须真的持有 ``global`` 状态。"""
        stateful = _modules_with_global_state()
        stale = [rel for rel in _INIT_TIME_CONSTANTS if rel not in stateful]
        assert not stale, f"豁免表里的模块已不再持有模块级状态，请删除：{stale}"


class TestResetFixtureBehaviour:
    """复位不是「写着好看」：污染态经 fixture 进入阶段即被清回基线。"""

    def test_fixture_clears_polluted_carriers(self):
        from src.python.core import http_client
        from src.python.fetcher import factor_catalog_loader
        from src.python.providers import news_aggregator
        from src.python.tui import report_artifacts, tui_handlers, tui_keys
        from src.test.conftest import _auto_reset_module_state

        http_client._TRANSPORT_FACTORY = lambda: None
        factor_catalog_loader._CATALOG_CACHE = {"version": 1}
        news_aggregator._last_src_results["某源"] = (3, "hit")
        report_artifacts._OPEN_FAILED_IN_SESSION = True
        tui_handlers._busy = True
        tui_keys._esc_residue_pending = True
        tui_keys._seq_prefix_pending = "\x1b["

        steps = getattr(_auto_reset_module_state, "__wrapped__")()
        next(steps)

        assert http_client._TRANSPORT_FACTORY is None
        assert factor_catalog_loader._CATALOG_CACHE is None
        assert news_aggregator._last_src_results == {}
        assert report_artifacts._OPEN_FAILED_IN_SESSION is False
        assert tui_handlers._busy is False
        assert tui_keys._esc_residue_pending is False
        assert tui_keys._seq_prefix_pending == ""
        next(steps, None)  # 收尾段同样可跑（不抛错）

    def test_injected_transport_factory_does_not_survive_a_test(self):
        """回归：注入的传输层工厂不得带到下一条用例（否则后续用例静默不走真实传输层）。"""
        from src.python.core.http_client import _TRANSPORT_FACTORY

        assert _TRANSPORT_FACTORY is None
