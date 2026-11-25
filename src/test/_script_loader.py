"""测试域共享的脚本加载器 — `scripts/` 下脚本按文件名动态加载的唯一实现。

`scripts/` 不在 import 路径上，`check-*` 这类连字符文件名也不是合法模块名，
测试只能按文件路径动态加载。同一套 `importlib.util.spec_from_file_location` 样板
过去散落在各测试文件（约 30 处、4 种变体），改造加载面（sys.modules 注册、模块名
派生规则）时需逐文件同步。此处收敛为单一实现：

    from src.test._script_loader import load_script
    mod = load_script("test-runner.py")

新测试一律复用本模块，不再自带样板（样板唯一性由
`src/test/unit/scripts/test_script_loader.py` 机检）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

#: 仓库根 `scripts/` 目录（本文件位于 `src/test/`，向上 2 级即仓库根）
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def load_script(name: str, *, module_name: str | None = None) -> ModuleType:
    """加载 `scripts/` 下的脚本为模块。

    Args:
        name: 相对 `scripts/` 的脚本路径，如 ``"test-runner.py"``、
            ``"_test_runner/modes.py"``。
        module_name: 注册进 ``sys.modules`` 的模块名。缺省由文件名派生
            （``test-runner.py`` → ``test_runner``）；需与真实模块名区隔
            （测试期补丁不外溢到同名真实导入）时显式指定。

    Returns:
        执行完毕的模块对象。每次调用都**重新执行**脚本、返回新实例，
        保证用例之间模块状态互不串扰。
    """
    fpath = SCRIPTS_DIR / name
    resolved = module_name or Path(name).stem.replace("-", "_")
    return load_module_file(fpath, resolved)


def load_module_file(fpath: str | Path, module_name: str) -> ModuleType:
    """按文件路径加载任意 Python 源文件为模块（脚本外的按文件重载场景同用本实现）。

    适用场景：需要在「模块导入期副作用」下拿到一个**全新实例**的模块（如验证
    模块导入时对 `sys.path` 的自助修补）。这类需要同样只能有一处样板，否则
    `spec_from_file_location` 会再次散布到各测试文件。

    Args:
        fpath: 源文件路径。
        module_name: 注册进 ``sys.modules`` 的模块名（调用方负责清理）。

    Returns:
        执行完毕的模块对象。
    """
    path = Path(fpath)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法为源文件创建模块 spec：{path}")
    module = importlib.util.module_from_spec(spec)
    # 注册进 sys.modules：`@dataclass` 解析类命名空间时按 cls.__module__ 回查模块
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
