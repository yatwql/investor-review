"""全局状态泄漏守卫的纯逻辑测试（快照差异比对与失败文案）。

守卫本体是 pytest 插件（`src/test/_conftest_state_guard.py`），真实触发要靠整套跑；
这里对它的两个纯函数下钻：差异识别必须逐字段生效、失败文案必须可操作——
否则守卫要么静默放过泄漏，要么给出查不动的报错。
"""

from __future__ import annotations

import pytest
from src.test import _conftest_state_guard as guard

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def test_snapshot_diff_is_empty_for_identical_state():
    snapshot = guard._snapshot_globals()

    assert guard._diff_snapshots(snapshot, guard._snapshot_globals()) == []


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("config_path_override", "text"),
        ("config_cache_count", "bump"),
        ("invest_logger_level", "bump"),
        ("cwd", "text"),
        ("sys_path_len", "bump"),
        ("sys_path_has_repo_root", "flip"),
    ],
)
def test_snapshot_diff_reports_any_changed_field(field, mutation):
    before = guard._snapshot_globals()
    current = getattr(before, field)
    if mutation == "text":
        mutated = f"/tmp/leaked-{field}"
    elif mutation == "bump":
        mutated = int(current) + 1
    else:
        mutated = not current
    after = before._replace(**{field: mutated})

    diffs = guard._diff_snapshots(before, after)

    assert len(diffs) == 1, diffs
    assert field in diffs[0] or guard._ITEM_LABELS.get(field, field) in diffs[0]
    assert repr(mutated) in diffs[0], "差异行须给出结束时的值，便于定位"


def test_snapshot_diff_reports_multiple_fields_in_one_message():
    before = guard._snapshot_globals()
    after = before._replace(config_path_override="/leaked", cwd="/elsewhere")

    diffs = guard._diff_snapshots(before, after)

    assert len(diffs) == 2
    message = guard._leak_message(diffs)
    assert "全局状态泄漏" in message
    assert all(line in message for line in diffs)


def test_leak_message_is_actionable():
    message = guard._leak_message(["  - 某全局：a → b"])

    assert "pytest -p no:randomly --lf" in message, "须给出复跑命令"
    assert "二分" in message, "须给出定位方法"
    assert "monkeypatch" in message, "须给出修复口径"


def test_item_labels_cover_every_snapshot_field():
    """每个快照字段都要有中文名：新增字段忘了登记会给出不可读的英文键名。"""
    assert set(guard._GlobalSnapshot._fields) <= set(guard._ITEM_LABELS)
