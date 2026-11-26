"""上传清理与生成执行体的降级分支单元测试（web/upload.py、web/run_generation.py）。

锁住的契约：
  - 过期上传清理：只删过期项并从注册表注销，未过期项保留；返回清理数量
  - 原子落盘失败（唯一写原语返回 False）→ 抛 OSError，不返回半成品路径
  - 持仓预检解析失败 → 统一映射 BAD_FILE（不泄漏内部异常类型）
  - 尽力删除：删不掉（权限/占用）返回 False，不抛
  - 正式模式上传已过期 / 未配置正式持仓路径 → 严重退出并给出中文可行动提示
  - 执行体内部异常 → 严重退出 + 统一提示（不冒泡）
  - output_dir 未建立时产物清单为空（无产物可点）
"""

from __future__ import annotations

import time

import pytest

import src.python.web.upload as upload
from src.python.web.run_generation import _build_artifacts, _run_generation
from src.python.web.runs import RunState

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]

_EXIT_SEVERE = 2


@pytest.fixture()
def _upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "_UPLOAD_DIR", str(tmp_path))
    upload._file_registry.clear()
    yield tmp_path
    upload._file_registry.clear()


class TestCleanupExpired:
    def test_only_expired_entries_removed_and_counted(self, _upload_dir):
        stale = _upload_dir / "stale.xlsx"
        stale.write_bytes(b"x")
        fresh = _upload_dir / "fresh.xlsx"
        fresh.write_bytes(b"x")
        upload._file_registry["stale"] = (str(stale), 0.0)
        upload._file_registry["fresh"] = (str(fresh), time.time())

        assert upload.cleanup_expired() == 1
        assert not stale.exists(), "过期文件须删除"
        assert fresh.exists(), "未过期文件不得被清理"
        assert set(upload._file_registry) == {"fresh"}


class TestPersistAtomic:
    def test_write_failure_raises_instead_of_returning_path(self, _upload_dir, monkeypatch):
        monkeypatch.setattr(upload, "write_bytes_atomic", lambda *_a, **_k: False)

        with pytest.raises(OSError):
            upload._persist_atomic(b"data")


class TestPrevalidateReaderFailure:
    def test_reader_exception_mapped_to_bad_file(self):
        def _boom(_path: str):
            raise RuntimeError("内部解析崩溃")

        with pytest.raises(upload.UploadError) as excinfo:
            upload._prevalidate(
                "x.xlsx",
                get_xlsx_info=lambda _p: {"sheet_names": ["Sheet1"], "total_rows": 1},
                read_holdings=_boom,
            )

        assert excinfo.value.error_code == upload.UPLOAD_BAD_FILE


class TestRemoveQuiet:
    def test_oserror_returns_false(self, monkeypatch):
        def _deny(_path: str) -> None:
            raise OSError("权限不足")

        monkeypatch.setattr(upload.os, "remove", _deny)

        assert upload._remove_quiet("/any/path.xlsx") is False


def _formal_params(file_id: str | None) -> dict:
    params = {"mode": "formal", "report_type": "basic"}
    if file_id is not None:
        params["file_id"] = file_id
    return params


class TestFormalModeSevereExits:
    def test_expired_upload_in_formal_mode_exits_severe(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.config.get_config", lambda: {"holdings_dir": "/tmp", "holdings_filename": "h.xlsx"}
        )
        monkeypatch.setattr("src.python.web.upload.resolve_file", lambda _fid: None)
        params = _formal_params("gone")
        state = RunState("r-expired", params)

        assert _run_generation(state, params) == _EXIT_SEVERE
        assert any("上传文件已过期" in err for err in state.errors)

    def test_missing_formal_holdings_path_exits_severe(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        monkeypatch.setattr("src.python.web.upload.resolve_file", lambda _fid: "/tmp/uploaded.xlsx")
        params = _formal_params("fid")
        state = RunState("r-nopath", params)

        assert _run_generation(state, params) == _EXIT_SEVERE
        assert any("未配置正式持仓文件路径" in err for err in state.errors)


class TestExecutionExceptionMapping:
    def test_unexpected_exception_maps_to_severe_exit(self, monkeypatch):
        def _boom(_path: str):
            raise RuntimeError("管线崩溃")

        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        monkeypatch.setattr("src.python.web.upload.resolve_file", lambda _fid: "/tmp/uploaded.xlsx")
        monkeypatch.setattr("src.python.core.reader.read_holdings_with_flows", _boom)
        params = {"file_id": "fid", "report_type": "basic"}
        state = RunState("r-boom", params)

        assert _run_generation(state, params) == _EXIT_SEVERE
        assert any("生成任务执行异常" in err for err in state.errors)


class TestArtifactsWithoutOutputDir:
    def test_no_output_dir_yields_empty_artifacts(self):
        state = RunState("r", {"report_type": "both"})
        state.output_dir = None

        assert _build_artifacts(state.params, state) == []
