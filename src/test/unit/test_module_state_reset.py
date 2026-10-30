"""模块级会话态复位契约：任何 ``global`` 改写的单例都要有测试复位入口。

为什么是个契约测试而不是逐条手写：``conftest`` 里那串复位调用是**约定**，靠人记住
「新增模块级状态时顺手加一行」必然漏；漏了的表现是测试顺序相关（xdist 换分片随机红），
而本地单进程顺序常常看不出来。本用例反向枚举 `src/python` 里所有经 ``global`` 改写的
模块级变量，要求所在模块提供复位入口**且**该入口被 ``conftest`` 调用——新增状态忘了
接线就直接红，不必等某次 CI 分片炸。

复位接线有两种形态，判据都认：调用模块的 ``reset_*()``，或在 fixture 里快照后
逐属性回填（日志生效值与定价时段走后者——它们由配置推导后原地改写，用 reload API
复位等于每条用例都读一次文件并重配 handler）。

豁免只留「无跨用例语义」的少数常量（如按需创建的线程池），表内注明理由；另有案例
断言豁免项仍然持有状态，防止表被当成免死金牌长期挂着。
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


def _snapshot_restored(rel: str, names: set[str], conftest_source: str) -> bool:
    """该模块的状态是否由 conftest 以「属性级快照回填」的方式复位。

    两种接线形态都成立：调模块的 ``reset_*()``，或在 fixture 里快照后逐属性回填
    （``logger_mod._LOG_FILE = ...`` / ``pricing.PRICING_TZ = snapshot[...]``）。后者无法
    用「函数名出现」判定，故按「全限定属性名出现在赋值左侧」认。
    """
    stem = Path(rel).stem.lstrip("_")
    for name in names:
        qualified = rf"\b\w*(?:{re.escape(stem)})\w*\.{re.escape(name)}\s*(?:=|[:+]?=|\.clear\(|\.update\()"
        if re.search(qualified, conftest_source):
            return True
    return False


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
            if not wired and not _snapshot_restored(rel, names, conftest_source):
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

    def test_logger_constants_roll_back_after_pollution(self):
        """回归：日志生效值由配置推导后原地改写，用例改了必须回填。

        实例：``test_logging_config`` 用临时 ``_LOGGER_CONFIG_PATH`` 调
        ``reload_logger_config()``，monkeypatch 只还原路径、不还原推导结果——不回填就
        把临时日志路径与 DEBUG 级别留给同 worker 的后续用例。
        """
        from src.python.core import logger as logger_mod
        from src.test.conftest import _restore_logger_state

        baseline = (logger_mod._LOG_FILE, logger_mod._CONFIG_FILE_LEVEL, logger_mod._LOG_MAX_BYTES)
        steps = getattr(_restore_logger_state, "__wrapped__")()
        next(steps)  # 进入阶段：快照
        logger_mod._LOG_FILE = "/tmp/上一条用例留下的日志.log"
        logger_mod._CONFIG_FILE_LEVEL = "DEBUG"
        logger_mod._LOG_MAX_BYTES = 123
        next(steps, None)  # 收尾阶段：回填

        assert (
            logger_mod._LOG_FILE,
            logger_mod._CONFIG_FILE_LEVEL,
            logger_mod._LOG_MAX_BYTES,
        ) == baseline

    def test_injected_transport_factory_does_not_survive_a_test(self):
        """回归：注入的传输层工厂不得带到下一条用例（否则后续用例静默不走真实传输层）。"""
        from src.python.core.http_client import _TRANSPORT_FACTORY

        assert _TRANSPORT_FACTORY is None
