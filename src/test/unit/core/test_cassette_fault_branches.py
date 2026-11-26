"""数据源记录-回放引擎的故障支路：读写失败、索引降级与录制传输委托。

三条契约在此逐条落断言：读不出来时抛 ``CassetteError``（不把裸 ``OSError`` 递给
调用方）、索引遇到并发删除窗口时按空/零降级而非整表中止、录制传输必须把响应体
读全后再录（否则录到的是未消费的空流）。
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import httpx
import pytest

from src.python.core import cassette as cs

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _write_cassette(directory, name: str) -> str:
    """落一份最小合法 cassette 文件（结构校验只需版本/名称/交互表）。"""
    path = os.path.join(str(directory), f"{name}.json")
    payload = {
        "version": 1,
        "name": name,
        "source": "test",
        "recorded_at": "2026-09-10T12:00:00+08:00",
        "interactions": [],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def test_load_cassette_unreadable_file_reports_cassette_error(tmp_path):
    """文件在但读取抛 ``OSError`` → 转成带原因的 ``CassetteError``。"""
    (tmp_path / "demo.json").write_text("{}", encoding="utf-8")
    with patch("builtins.open", side_effect=OSError("permission denied")):
        with pytest.raises(cs.CassetteError, match="无法读取"):
            cs.load_cassette("demo", str(tmp_path))


def test_save_cassette_write_failure_raises(tmp_path):
    """原子写盘失败 → 抛 ``OSError``（录制流程以显式失败终结）。"""
    cassette = cs.Cassette(name="demo", source="test", recorded_at="2026-09-10T12:00:00+08:00")
    with patch("src.python.core.cassette.write_text_atomic", return_value=False):
        with pytest.raises(OSError, match="写盘失败"):
            cs.save_cassette(cassette, str(tmp_path))


def test_list_cassettes_unreadable_dir_returns_empty(tmp_path):
    """列目录抛 ``OSError``（isdir 与 listdir 之间被并发删除）→ 索引按空处理。"""
    with patch("src.python.core.cassette.os.listdir", side_effect=OSError("gone")):
        assert cs.list_cassettes(str(tmp_path)) == []


def test_list_cassettes_size_failure_falls_back_to_zero(tmp_path):
    """单文件取大小失败 → 该条 ``size_bytes`` 记 0，条目本身仍进索引。"""
    _write_cassette(tmp_path, "demo")
    with patch("src.python.core.cassette.os.path.getsize", side_effect=OSError("gone")):
        entries = cs.list_cassettes(str(tmp_path))

    assert [entry["name"] for entry in entries] == ["demo"]
    assert entries[0]["size_bytes"] == 0
    assert "error" not in entries[0], "文件本身可读，不得被计为损坏条目"


def test_record_transport_reads_body_then_observes_interaction():
    """录制传输：原样返回内层响应，并把读全后的响应体录进会话。"""
    session = cs.RecordingSession("demo", source="test")
    inner = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"payload"))
    with patch("src.python.core.cassette.make_transport", return_value=inner):
        transport = cs._RecordTransport(session)

    response = transport.handle_request(httpx.Request("GET", "https://example.com/x"))

    assert response.content == b"payload"
    recorded = session.cassette.lookup(cs.normalize_request_key("GET", "https://example.com/x"))
    assert recorded is not None, "请求必须被录进会话"
    assert recorded.body == "payload", "录制的是读全后的响应体（未消费流会录成空）"
