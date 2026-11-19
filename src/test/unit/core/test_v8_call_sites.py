"""契约：主进程内不得直接调用「内部建 py_mini_racer 上下文」的 akshare 接口。

**为什么要这条测试**：V8 上下文与创建线程绑定，在别的线程被 GC 回收会段错误或挂死进程，
属原生崩溃（`try/except` 拦不住、pytest 抓不到）。哪些 akshare 接口会触 V8 由 akshare 自己
的实现决定，**升级 akshare 就可能把新接口变成 V8 用户**——靠人记住接线必然漏（实测漏掉
`stock_fund_flow_industry` 导致报告基准进程必崩）。

判定口径：
1. 扫 `src/python` 全部 `ak.<name>(...)` 调用点（以及 `_ak.<name>(...)` 这类别名写法）；
2. 用 akshare 自身源码判定该接口是否引用 `MiniRacer`（直接引用即算，含其同文件辅助函数）；
3. 引用 V8 的调用点一律判失败——它们必须改走 `core.v8_subprocess.run_akshare_v8`
   （子进程隔离；主进程内无论怎么调度都可能段错误/退出死锁，见该模块说明）。

akshare 未安装时跳过（可选依赖）。
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import types
from pathlib import Path

import pytest

from src.python.core.akshare_compat import candidate_names

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PYTHON = _REPO_ROOT / "src" / "python"

#: akshare 局部别名（`import akshare as ak` / 模块级 `ak = ...`）
_AK_ALIASES = {"ak", "_ak"}


def _akshare_attr_calls() -> list[tuple[Path, int, str]]:
    """扫出所有 `ak.<name>(...)` 调用点：(文件, 行号, 接口名)。"""
    found: list[tuple[Path, int, str]] = []
    for path in _SRC_PYTHON.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in _AK_ALIASES:
                found.append((path, node.lineno, func.attr))
    return found


def _uses_v8(akshare: object, name: str) -> bool:
    """该 akshare 接口是否引用 py_mini_racer（自身源码或同文件被它调用的辅助函数）。"""
    fn = getattr(akshare, name, None)
    if fn is None:
        return False
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return False
    if "MiniRacer" in source or "mini_racer" in source:
        return True
    # 同文件辅助函数：`stock_fund_flow_industry` 经 `_get_file_content_ths` 间接取 JS 解码上下文
    module = inspect.getmodule(fn)
    for helper in set(re.findall(r"\b(_[a-zA-Z0-9_]+)\(", source)):
        helper_fn = getattr(module, helper, None)
        if helper_fn is None or not callable(helper_fn):
            continue
        try:
            helper_source = inspect.getsource(helper_fn)
        except (OSError, TypeError):
            continue
        if "MiniRacer" in helper_source or "mini_racer" in helper_source:
            return True
    return False


@pytest.mark.unit
class TestAkshareV8CallSitesAreRouted:
    def test_every_v8_using_akshare_call_goes_through_v8_thread(self):
        """主进程内不得直接调 V8 类 akshare 接口（必须经 run_akshare_v8 子进程）。"""
        try:
            import akshare
        except ImportError:  # 可选依赖缺失：契约无对象可验
            pytest.skip("akshare 未安装")

        offenders: list[str] = []
        for path, lineno, name in _akshare_attr_calls():
            if not _uses_v8(akshare, name):
                continue
            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{lineno} ak.{name}")

        assert not offenders, (
            "以下 akshare 调用会在主进程内创建 py_mini_racer 上下文，"
            "必须改为 core.v8_subprocess.run_akshare_v8（子进程隔离）：\n" + "\n".join(offenders)
        )

    def test_known_v8_interfaces_are_detected(self):
        """检测逻辑本身有效：已知 V8 接口被判定为 True，已知纯 HTTP 接口为 False。

        按**逻辑名**的整条候选链判定：akshare 会就地重命名接口（如
        `tool_trade_date_hist_sina` 与 `stock_fund_flow_industry` 都换过名），只查单一名字
        会让本用例在依赖解析到另一种名字的机器上假红（真因是接口名，不是检测能力）。
        """
        try:
            import akshare
        except ImportError:
            pytest.skip("akshare 未安装")

        def _detected(logical_name: str) -> bool:
            return any(_uses_v8(akshare, name) for name in candidate_names(logical_name))

        assert _detected("stock_fund_flow_industry") is True
        assert _detected("tool_trade_date_hist_sina") is True
        assert _uses_v8(akshare, "stock_financial_abstract") is False

    def test_detection_logic_on_synthetic_sources(self, tmp_path):
        """检测能力的**确定性**回归：不依赖 akshare 当前实现（版本一变就假红/假绿）。"""
        source = (
            "import py_mini_racer\n\n"
            "def v8_api():\n"
            "    ctx = py_mini_racer.MiniRacer()\n"
            "    return ctx\n\n"
            "def _helper():\n"
            "    return py_mini_racer.MiniRacer()\n\n"
            "def indirect_via_helper():\n"
            "    return _helper()\n\n"
            "def plain_http_api():\n"
            "    return {'ok': True}\n"
        )
        module_path = tmp_path / "fake_akshare.py"
        module_path.write_text(source, encoding="utf-8")

        # 直接编译成模块对象（文件名指向真实文件，`inspect.getsource` 才读得到源码）：
        # 不走「按路径 import」的样板，避免测试里出现第二处脚本加载器
        fake = types.ModuleType("fake_akshare")
        fake.__file__ = str(module_path)
        sys.modules["fake_akshare"] = fake
        try:
            try:
                exec(compile(source, str(module_path), "exec"), fake.__dict__)
            except ImportError:  # py_mini_racer 未安装：替身模块导入失败即无法造样本
                pytest.skip("py_mini_racer 未安装")

            assert _uses_v8(fake, "v8_api") is True, "直接建 V8 上下文的接口必须被识别"
            assert _uses_v8(fake, "indirect_via_helper") is True, "经同文件辅助函数间接取 V8 的接口同样必须被识别"
            assert _uses_v8(fake, "plain_http_api") is False, "纯 HTTP 接口不得误判为 V8"
            assert _uses_v8(fake, "no_such_api") is False, "接口不存在时不得报错或误判"
        finally:
            sys.modules.pop("fake_akshare", None)
