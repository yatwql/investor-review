"""边缘测试：配置反序列化与落盘安全 — 原型污染与原子写。

覆盖 `config` 的 JSON 解析（`__proto__` 只作普通键）与 `config/_core.py` 的原子落盘
（mkstemp + os.replace，防半写）。
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pytest

from src.python.core.constants import PROJECT_ROOT

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_config,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestJsonPrototypePollution(unittest.TestCase):
    """JSON 反序列化 — Python 原生 JSON 无原型污染风险。"""

    def test_stdlib_json_treats_proto_as_plain_key(self):
        """契约：解析器把 __proto__ 当普通键（防将来换成支持原型链的解析器）。"""
        malicious = '{"__proto__": {"admin": true}, "name": "test"}'
        result = json.loads(malicious)
        self.assertIsInstance(result, dict)
        self.assertIn("__proto__", result)  # 被当作普通键
        self.assertEqual(result["__proto__"]["admin"], True)
        # Python 对象不受影响
        self.assertFalse(hasattr({}, "admin"))

    def test_config_json_with_proto(self):
        """config.json 含 __proto__ → 不被特殊处理。"""
        from src.python.config import get_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"__proto__": {"admin": True}, "output_dir": "reports"}, f)
            with patch("src.python.config._config_defaults._CONFIG_FILE", config_path):
                config = get_config()
            self.assertIn("__proto__", config)
            self.assertEqual(config["output_dir"], os.path.join(PROJECT_ROOT, "reports"))


class TestTempFileRace(unittest.TestCase):
    """临时文件安全 — mkstemp 原子写入。"""

    def test_mkstemp_used_for_config(self):
        """set_config 原子写防半写（经 _persist_config_patch 委托 _atomic_write，内含 mkstemp + os.replace）。

        set_config → _persist_config_patch（校验 JSON 合法性 + 原子落盘）→ _atomic_write（mkstemp + os.replace）。
        """
        from src.python.config import set_config
        from src.python.config._core import _atomic_write, _persist_config_patch
        import inspect

        # 原子写实现（_atomic_write）必须使用 mkstemp + os.replace 防半写
        source_atomic = inspect.getsource(_atomic_write)
        self.assertIn("mkstemp", source_atomic)
        self.assertIn("os.replace", source_atomic)
        # set_config 必须经 _persist_config_patch 委托原子写（而非直接写文件）
        source_set = inspect.getsource(set_config)
        self.assertIn("_persist_config_patch", source_set)
        source_patch = inspect.getsource(_persist_config_patch)
        self.assertIn("_atomic_write", source_patch)
