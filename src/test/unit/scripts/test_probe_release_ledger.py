"""发布台账按版本汇总（`scripts/probe-release-ledger.py`）——切段与增量口径。

本工具不是门禁：台账是 append-only 的第一现场记录，`session_usage` 是 agent 会话级累加值，
所以「这一版花了多少墙钟/token」只能靠切段 + 相邻行取增量还原。用例锁：
  - 切段口径：`X.Y.Z-dev` 与 `X.Y.Z` 同属一版；跨版本文本不串账；
  - token 增量：同会话取前后差、新会话首行记 0、回退（累计变小）记 0；
  - 失败步与「是否已发布」的判定；
  - `--version` / `--last` 选择与台账缺失/脏行容错。
"""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_PROBE = "probe-release-ledger.py"


def _probe_module():
    from src.test._script_loader import load_script

    return load_script(_PROBE, module_name="probe_release_ledger")


def _rec(
    version: str,
    command: str,
    *,
    ok: bool = True,
    elapsed: float = 1.0,
    total: int | None = None,
    session: str = "s1",
    steps: list[dict] | None = None,
    failure: dict | None = None,
) -> dict:
    record: dict = {
        "ts": f"2026-11-19T10:00:00+08:00-{version}-{command}",
        "command": command,
        "ok": ok,
        "elapsed_s": elapsed,
        "version": version,
        "steps": steps or [],
    }
    if total is not None:
        record["session_usage"] = {"total": total}
        record["agent"] = {"session_id": session}
    if failure is not None:
        record["failure"] = failure
    return record


class TestGrouping:
    def test_dev_and_release_share_one_version_group(self):
        mod = _probe_module()
        items = mod.summarize(
            [
                _rec("0.18.6-dev", "check"),
                _rec("0.18.6-dev", "prepare"),
                _rec("0.18.6", "publish"),
            ]
        )
        assert [item["version"] for item in items] == ["0.18.6"]
        assert items[0]["commands"] == ["check", "prepare", "publish"]
        assert items[0]["published"] is True

    def test_versions_do_not_mix(self):
        mod = _probe_module()
        items = mod.summarize([_rec("0.18.6", "publish"), _rec("0.18.7-dev", "check")])
        assert [item["version"] for item in items] == ["0.18.6", "0.18.7"]
        assert items[1]["published"] is False, "只有 check 没有 publish 的版本不算已发布"

    def test_failed_publish_is_not_published(self):
        mod = _probe_module()
        items = mod.summarize([_rec("0.18.6", "publish", ok=False, failure={"step": "gate"})])
        assert items[0]["published"] is False
        assert items[0]["failures"] == [{"command": "publish", "failure": {"step": "gate"}}]

    def test_steps_aggregate_across_commands(self):
        mod = _probe_module()
        items = mod.summarize(
            [
                _rec("0.18.6", "prepare", steps=[{"step": "切版提交", "elapsed_s": 2.0}]),
                _rec("0.18.6", "devbump", steps=[{"step": "切版提交", "elapsed_s": 1.5}]),
            ]
        )
        assert items[0]["steps"] == {"切版提交": 3.5}
        assert items[0]["wall_seconds"] == pytest.approx(2.0)


class TestTokenDelta:
    def test_same_session_uses_difference(self):
        mod = _probe_module()
        items = mod.summarize(
            [
                _rec("0.18.6", "check", total=1000),
                _rec("0.18.6", "prepare", total=1600),
            ]
        )
        assert items[0]["tokens"] == 600, "同会话取前后差，累加值本身不算成本"

    def test_new_session_first_row_counts_zero(self):
        mod = _probe_module()
        items = mod.summarize(
            [
                _rec("0.18.6", "check", total=5000, session="s1"),
                _rec("0.18.7-dev", "check", total=900, session="s2"),
            ]
        )
        assert items[0]["tokens"] == 0
        assert items[1]["tokens"] == 0, "新会话首行记 0，避免把上一会话的累计算进本版"

    def test_decreasing_total_is_not_counted_negative(self):
        mod = _probe_module()
        items = mod.summarize(
            [
                _rec("0.18.6", "check", total=2000),
                _rec("0.18.6", "prepare", total=1500),
            ]
        )
        assert items[0]["tokens"] == 0

    def test_missing_usage_fields_are_ignored(self):
        mod = _probe_module()
        items = mod.summarize([_rec("0.18.6", "check")])
        assert items[0]["tokens"] == 0


class TestCli:
    def test_ledger_read_skips_broken_lines_and_missing_file(self, tmp_path):
        mod = _probe_module()
        assert mod._read_ledger(tmp_path / "nope.jsonl") == []
        ledger = tmp_path / "release.jsonl"
        ledger.write_text(
            json.dumps(_rec("0.18.6", "check")) + "\n{不是 json}\n\n",
            encoding="utf-8",
        )
        assert [row["command"] for row in mod._read_ledger(ledger)] == ["check"]

    def test_version_filter_and_last(self, tmp_path, capsys):
        mod = _probe_module()
        ledger = tmp_path / "release.jsonl"
        ledger.write_text(
            "\n".join(json.dumps(_rec(v, "publish")) for v in ("0.18.4", "0.18.5", "0.18.6")) + "\n",
            encoding="utf-8",
        )
        assert mod.main(["--ledger", str(ledger), "--last", "2", "--ci"]) == 0
        out = capsys.readouterr().out
        assert "0.18.4" not in out and "0.18.5" in out and "0.18.6" in out

        assert mod.main(["--ledger", str(ledger), "--version", "0.18.5", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [item["version"] for item in payload] == ["0.18.5"]
        assert "records" not in payload[0], "JSON 输出不带原始行（体积可控）"

    def test_unreadable_ledger_exits_1(self, tmp_path):
        mod = _probe_module()
        target = tmp_path / "dir.jsonl"
        target.mkdir()  # 目录当文件读 → OSError
        assert mod.main(["--ledger", str(target)]) == 1

    def test_ci_omits_notes_and_never_reports_findings(self, tmp_path, capsys):
        """`--ci` 只隐去说明段：表格照出、失败步照列，绝不以退出码 2 表达 finding。

        本脚本不是门禁（失败步是台账事实，不是它的判断），故不复用检查脚本的公共
        `--ci`（那个口径是「仅输出 文件:描述，发现即退出 2」）。
        """
        mod = _probe_module()
        ledger = tmp_path / "release.jsonl"
        ledger.write_text(
            json.dumps(_rec("0.18.6", "publish", ok=False, failure={"step": "gate"})) + "\n",
            encoding="utf-8",
        )
        assert mod.main(["--ledger", str(ledger), "--ci"]) == 0
        out = capsys.readouterr().out
        assert "0.18.6" in out and "publish" in out, "表格行照出（含失败步）"
        assert "注：" not in out, "说明段在 --ci 下隐去"

    def test_ci_help_describes_its_own_semantics(self, capsys):
        """`--ci` 的帮助文本如实描述本脚本口径（不是检查脚本的「退出码 2」）。"""
        mod = _probe_module()
        with pytest.raises(SystemExit) as exc:
            mod.main(["--help"])
        assert exc.value.code == 0
        help_line = next(line for line in capsys.readouterr().out.splitlines() if line.strip().startswith("--ci"))
        assert "退出码 2" not in help_line, "--ci 不表达 finding，帮助文本不得沿用检查脚本口径"
        assert "非门禁" in help_line
