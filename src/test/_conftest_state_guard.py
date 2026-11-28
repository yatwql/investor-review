"""conftest 夹具实现 — 会话级全局状态泄漏守卫（session-scoped autouse + 收集期/收尾期基线）。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）。与 `_conftest_isolation`（用例级路径隔离）分离：那条防线管「每个用例内不被
污染」，这条管「整套跑完有没有把进程级全局留在脏状态」——后者只在整套运行时暴露，单跑某
文件通常看不出来（实测事故：某用例遗留 `_CONFIG_PATH_OVERRIDE`，跨用例盖掉隔离路径；
另一用例换掉 logger 类后 `patch("logging.Logger.warning")` 拦截不到真实告警）。

做法：两个基线 + 会话末比对，不一致即以 `pytest.fail` 报出并给定位线索：

  - `pytest_collection_finish` 取**主基线**：收集期 import 的副作用已经发生，而用例级隔离
    夹具（改配置路径、换 `socket.connect`）尚未生效，基线是未打桩的真值。
  - `pytest_runtest_teardown` 首个用例收尾后取 **logger 级别基线**：会话级基础设施夹具的
    setup 会引入生产模块，其中少数在 import 期调用 `setup_logger()` 把 `invest` 定到 DEBUG，
    属一次性初始化而非泄漏（发生在收集之后，故单独一个基线）。

白名单口径（**只放单测不该改变的项；缓存与开关字典只比结构，不比逐项值**）：

  - `config._config_defaults._CONFIG_PATH_OVERRIDE`：配置路径覆写，遗留即跨用例盖掉隔离路径
  - `config._config_defaults._CONFIG_FILE`：配置默认路径，遗留即读写用户真实配置
  - `config._core._config_cache`：键集合 + 键数（值含 `tmp_path` 派生路径，比值必误报）
  - `config.features.FEATURE_FLAGS`：**键集合**（键增删 = 注册表被改写；逐项值不入判据——
    用例按需开关、下个用例 setup 由 `_auto_reset_feature_flags` 复位，属常态）
  - `config._feature_registry._FEATURE_FLAGS_DEFAULT`：键 + 默认值（复位目标本身，被改即泄漏）
  - `logging.getLogger("invest")`：级别 + logger 类名 + `logging.Logger.warning` 是否原函数
    （级别由 `_restore_invest_logger_level` 逐用例回填，故会话末仍可比）
  - `os.getcwd()`：工作目录（未复位的 chdir 会让后续用例的相对路径落错地方）
  - `sys.path`：长度 + 是否仍含仓库根（模块级插入属收集期，运行期再变即泄漏）
  - `socket.socket.connect`：须仍是收集结束时的原函数（网络守卫被换掉 = 真实外网请求放行）
"""

from __future__ import annotations

import logging
import os
import socket
import sys
from typing import NamedTuple

import pytest

from src.python.core.constants import PROJECT_ROOT


#: 收集结束时的基线（未受用例级夹具打桩影响的真值）
_BASELINE: "_GlobalSnapshot | None" = None

#: 首个用例收尾后的 logger 级别基线（会话基础设施 import 的一次性副作用已发生）
_SETTLED_LOGGER_LEVEL: int | None = None


class _GlobalSnapshot(NamedTuple):
    """白名单全局的一次取值（逐项比对，不给「整块相等」的模糊结论）。"""

    config_path_override: str | None
    config_file: str
    config_cache_keys: frozenset[str]
    config_cache_count: int
    feature_flag_keys: frozenset[str]
    feature_flag_defaults: tuple[tuple[str, bool], ...]
    invest_logger_level: int
    invest_logger_class: str
    logger_warning_func: object
    cwd: str
    sys_path_len: int
    sys_path_has_repo_root: bool
    socket_connect: object


#: 每一项的中文名（失败信息要可操作，不只是一句「不一致」）
_ITEM_LABELS: dict[str, str] = {
    "config_path_override": "配置路径覆写 `config._config_defaults._CONFIG_PATH_OVERRIDE`",
    "config_file": "配置路径 `config._config_defaults._CONFIG_FILE`",
    "config_cache_keys": "配置缓存键集合 `config._core._config_cache`",
    "config_cache_count": "配置缓存键数 `config._core._config_cache`",
    "feature_flag_keys": "功能开关字典键集合 `config.features.FEATURE_FLAGS`",
    "feature_flag_defaults": "开关默认值 `config._feature_registry._FEATURE_FLAGS_DEFAULT`",
    "invest_logger_level": '项目 logger 级别 `logging.getLogger("invest").level`',
    "invest_logger_class": '项目 logger 类 `logging.getLogger("invest").__class__`',
    "logger_warning_func": "`logging.Logger.warning`",
    "cwd": "工作目录 `os.getcwd()`",
    "sys_path_len": "`sys.path` 长度",
    "sys_path_has_repo_root": "`sys.path` 是否含仓库根",
    "socket_connect": "网络守卫 `socket.socket.connect`（须仍是原函数）",
}


def _snapshot_globals() -> _GlobalSnapshot:
    """取一次白名单全局快照（import 推迟到调用点：收集期不引入额外模块加载）。"""
    import src.python.config._config_defaults as config_defaults
    import src.python.config._core as config_core
    from src.python.config._feature_registry import _FEATURE_FLAGS_DEFAULT
    from src.python.config.features import FEATURE_FLAGS

    cache = config_core._config_cache or {}
    logger = logging.getLogger("invest")
    return _GlobalSnapshot(
        config_path_override=config_defaults._CONFIG_PATH_OVERRIDE,
        config_file=config_defaults._CONFIG_FILE,
        config_cache_keys=frozenset(cache),
        config_cache_count=len(cache),
        feature_flag_keys=frozenset(FEATURE_FLAGS),
        feature_flag_defaults=tuple(sorted(_FEATURE_FLAGS_DEFAULT.items())),
        invest_logger_level=logger.level,
        invest_logger_class=type(logger).__name__,
        logger_warning_func=logging.Logger.warning,
        cwd=os.getcwd(),
        sys_path_len=len(sys.path),
        sys_path_has_repo_root=str(PROJECT_ROOT) in sys.path,
        socket_connect=socket.socket.connect,
    )


def _diff_snapshots(before: _GlobalSnapshot, after: _GlobalSnapshot) -> list[str]:
    """逐项比对，返回「哪个全局、前后值」的可读差异行（空列表 = 无泄漏）。"""
    diffs: list[str] = []
    for field in before._fields:
        old, new = getattr(before, field), getattr(after, field)
        if old == new:
            continue
        label = _ITEM_LABELS.get(field, field)
        diffs.append(f"  - {label}：开跑前 {old!r} → 结束时 {new!r}")
    return diffs


def _leak_message(diffs: list[str]) -> str:
    return (
        "[全局状态泄漏] 会话结束时以下进程级全局与开跑时不一致——它们只在「整套跑」时暴露，"
        "单跑某个文件通常看不出来（泄漏会让后续用例读到上一个用例的状态）：\n"
        + "\n".join(diffs)
        + "\n定位方法：先 `pytest -p no:randomly --lf` 复跑上次失败/受影响的用例；"
        "仍复现不了时用 `pytest -x` 二分文件集合（每次去掉一半文件，看泄漏是否消失）锁定来源文件，"
        "再把该文件的直接赋值改为 monkeypatch / 自带 teardown 复位。"
    )


def pytest_collection_finish(session):
    """收集结束即取主基线（所有测试模块 import 完、任何用例夹具都还没生效）。"""
    global _BASELINE
    _BASELINE = _snapshot_globals()


def pytest_runtest_teardown(item, nextitem):
    """首个用例收尾后取 logger 级别基线（此时会话基础设施 import 的一次性副作用已发生）。"""
    global _SETTLED_LOGGER_LEVEL
    if _SETTLED_LOGGER_LEVEL is None:
        _SETTLED_LOGGER_LEVEL = logging.getLogger("invest").level


@pytest.fixture(autouse=True)
def _restore_invest_logger_level():
    """逐用例回填项目 logger 级别：级别是用例按需调整的合法状态，回填后跨用例才不串。

    只回填级别（零 I/O）：不给它接 `setup_logger`/`reload_logger_config`——那会重配 handler，
    与 pytest 自己的捕获 handler 抢位置。
    """
    logger = logging.getLogger("invest")
    level = logger.level
    yield
    logger.setLevel(level)


@pytest.fixture(scope="session", autouse=True)
def _guard_global_state_leaks():
    """会话级守卫：全部用例与其夹具 teardown 后比对白名单全局，不一致即报泄漏。"""
    global _BASELINE, _SETTLED_LOGGER_LEVEL
    yield
    before, settled_level = _BASELINE, _SETTLED_LOGGER_LEVEL
    _BASELINE, _SETTLED_LOGGER_LEVEL = None, None
    if before is None:  # 本次会话没收集到用例（如 --collect-only）：无数可比
        return
    if settled_level is not None:
        before = before._replace(invest_logger_level=settled_level)
    diffs = _diff_snapshots(before, _snapshot_globals())
    if diffs:
        pytest.fail(_leak_message(diffs), pytrace=False)
