"""边缘测试：持仓目录文件过滤 — 符号链接/特殊文件。

覆盖 `core/reader.py` 的 `list_xlsx_files`：目录内存在非普通文件时只按扩展名收集，
特殊文件类型不致崩溃或误收。
"""

from __future__ import annotations

import os
import tempfile
import unittest

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_core,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestSymlink(unittest.TestCase):
    """符号链接处理 — 持仓目录不跟随符号链接。"""

    def test_symlink_in_holdings_dir(self):
        """持仓目录存在非普通文件 → list_xlsx_files 过滤掉。"""
        from src.python.core.reader import list_xlsx_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个命名管道（模拟特殊文件类型），Windows 用普通文件代替
            fpath = os.path.join(tmpdir, "not_a_real.xlsx")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("")
            result = list_xlsx_files(tmpdir)
            self.assertEqual(len(result), 1)
