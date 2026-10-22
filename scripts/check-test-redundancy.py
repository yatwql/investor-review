#!/usr/bin/env python3
"""测试用例冗余与无效检查（test redundancy / dead test check）—— 静态扫测试源，找「跑不到」「测不出」「同义反复」「重复」的用例。

八类检查（全部基于 AST 静态分析，不执行测试、不依赖网络）：

  A. **死用例（不可收集 / 被覆盖）** — pytest 永远不会执行的用例：
     - 同文件同类内同名重复定义（后者覆盖前者）
     - 类名不以 `Test` 开头的方法形式的 `test_*`（pytest 不收集）
     - `Test*` 类定义了 `__init__`（pytest 整类跳过）
  B. **无断言用例** — 既无 `assert`、也无 `pytest.raises/warns/fail`、也无 mock 断言（`assert_called*`）
  C. **完全重复用例** — 去掉 docstring 后「函数体 + 参数 + 装饰器」AST 归一化完全相同（同一被测对象同一断言）。
     为避免把「同名方法绑定不同被测对象」的并行覆盖误判为重复，`self.<attr>` 间接调用先三档解析绑定：
     类体赋值 / 方法返回值 / setUp(setUpClass) 内 `self.<attr> = <值>` 赋值；类内定义但无单一
     return 的分支型 helper（如 `_run`/`_call`）取方法体哈希为绑定。三档均无法解析（求值目标
     来自基类/外部模块/mock fixture）才跳过比对——跳过是保底而非默认，能解析的必须参与比对。
  D. **自证用例（mock 替代被测对象）** — 同一用例内既 patch 了某个符号（`@patch("<mod>.<fn>")`），
     又直接调用同名函数，且把该 mock 的 `.return_value` 设成某个字面量、再用断言与该字面量比较——
     此时断言恒真，等于没测（常见于「顺手把被测函数也 patch 了」）。
  E. **硬编码「会演进的总数」** — 把需求/章节/开关等可增长集合的条数写死在断言里（如
     `assert len(req_ids) == 276`）。这类总数是文档真值来源的派生量，新增一条需求就会把测试打红，
     且与门禁脚本的全域覆盖断言职责重复。正确做法：结构关系断言（集合双向相等 / 域覆盖 / 序号连续）。
  F. **恒真断言** — `assert True` / `assert x == x`：形式上有断言、实际不验证任何行为。
  G. **死 fixture** — test 文件内定义（排除 conftest 与 autouse）且全仓语料（测试 + conftest）
     无任何引用——定义后从未被用例/夹具消费的死代码。
  H. **弱 mock 断言** — `assert <mock>.<属性>` 作真值 / `assertIsNotNone(<mock>)`：Mock 对象
     恒真且不为 None，断言恒成立不验证行为（`.called` / `assert_called*` 等专用断言不算弱）。

按设计排除：`src/test/live/`（`pytest.ini` 刻意排除的 opt-in 真网套件，默认不扫，`--include-live` 可纳入）、
`*_edge.py` 不特殊对待（同为测试，同样受检）。

用法：
  python scripts/check-test-redundancy.py                 # 八类全查
  python scripts/check-test-redundancy.py -v              # 详细输出（打印被跳过的间接调用用例数等）
  python scripts/check-test-redundancy.py --ci            # CI 模式：仅输出 文件:描述，退出码 2
  python scripts/check-test-redundancy.py --include-live  # 连带扫描 src/test/live/
  python scripts/check-test-redundancy.py --audit         # 附加建议性骨架审计（同名同骨架分组，找复制粘贴嫌疑）
  python scripts/check-test-redundancy.py --audit --audit-all  # 骨架审计连带文件内组（默认仅跨文件高信号）

退出码：
  0 — 全部通过
  2 — 发现死用例 / 无断言 / 完全重复 / 自证用例 / 硬编码演进总数 / 恒真断言 / 死 fixture / 弱 mock 断言
  注：`--audit` 为建议性附加输出，恒不改变退出码（骨架同构多为合法矩阵契约，须人工判读）

性能（增量事实缓存）：
  按文件「size:mtime_ns」签名缓存每文件检查事实，未变更文件免解析免检查；跨文件重复
  比对仍跨全集归并（质量不降）。缓存逻辑版本（本脚本 + 同目录 _checklib + 解释器大版本）
  任一变化全量重算；缓存读写失败静默降级（只影响速度不影响结论）。
"""

from __future__ import annotations

import argparse
import ast  # noqa: F401 — 测试按 redundancy.ast 打桩（与原单文件行为一致）
import os
import sys

# 入口与实现包分开后，需要把 scripts/ 放进 sys.path（load_script 只加载入口文件）
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# 八类检查已按 finding 分类拆到 scripts/_test_redundancy/（各检查一个模块，共用
# _common 的 AST 原语，runner 负责编排）；入口只保留 CLI 与兼容 re-export，
# 使 load_script 的既有直调面（run_checks / check_* / cases_in_module …）不变。
from _test_redundancy._common import (  # noqa: F401 — 兼容 load_script 直调面
    TestCase,
    _iter_test_files,
    _strip_docstring,
    _dump,
    _class_attr_binding,
    _method_body_hash,
    _self_attrs,
    _call_name,
    _assertion_in,
    _same_scope_helpers,
    _assertions,
    _patch_targets,
    _called_names,
    _mock_return_literals,
    _asserted_literals,
    cases_in_module,
    _TEST_ROOT,
    _LIVE_DIR,
    _MOCK_ASSERT,
    _PYTEST_ASSERT,
    _SUT_ATTRS,
)

from _test_redundancy.cases import (  # noqa: F401 — 兼容 load_script 直调面
    check_dead_tests,
    check_assertion_free,
)

from _test_redundancy.duplicates import (  # noqa: F401 — 兼容 load_script 直调面
    body_signature,
    _group_duplicate_entries,
    check_duplicate_bodies,
)

from _test_redundancy.similar import (  # noqa: F401 — 兼容 load_script 直调面
    _Skeletonizer,
    _skeleton_hash,
    audit_similar_bodies,
)

from _test_redundancy.self_fulfilling import (  # noqa: F401 — 兼容 load_script 直调面
    check_self_fulfilling,
)

from _test_redundancy.hardcoded import (  # noqa: F401 — 兼容 load_script 直调面
    check_hardcoded_evolving_totals,
)

from _test_redundancy.trivial import (  # noqa: F401 — 兼容 load_script 直调面
    check_trivially_true,
)

from _test_redundancy.weak_mock import (  # noqa: F401 — 兼容 load_script 直调面
    _is_mock_name,
    check_weak_mock_assertions,
)

from _test_redundancy.dead_fixtures import (  # noqa: F401 — 兼容 load_script 直调面
    _fixture_exposed_name,
    check_dead_fixtures,
)

from _test_redundancy.facts_cache import (  # noqa: F401 — 兼容 load_script 直调面
    _facts_cache_path,
    _cache_version,
    _file_signature,
    _load_facts_cache,
    _save_facts_cache,
    _file_facts,
    _collect_facts,
    _CACHE_ENV,
    _CACHE_FILE,
)

from _test_redundancy.runner import (  # noqa: F401 — 兼容 load_script 直调面
    run_checks,
)

from _shared.checklib import add_common_args, report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "测试用例冗余与无效检查（死用例 / 无断言 / 完全重复 / 自证用例 / 硬编码演进总数 / "
            "恒真断言 / 死 fixture / 弱 mock 断言）"
        ),
    )
    add_common_args(parser)
    parser.add_argument("--include-live", action="store_true", help="连带扫描 src/test/live/（默认按 pytest.ini 排除）")
    parser.add_argument(
        "--audit", action="store_true", help="附加建议性骨架审计（同名同骨架分组，找复制粘贴嫌疑；恒不参与退出码）"
    )
    parser.add_argument("--audit-all", action="store_true", help="--audit 连带文件内组（默认仅跨文件高信号）")
    args = parser.parse_args()

    findings, stats = run_checks(include_live=args.include_live)

    if args.verbose:
        print(
            f"  扫描测试文件 {stats['files']} 个 / 用例 {stats['cases']} 个"
            f"（live 目录{'纳入' if args.include_live else '跳过'}）"
        )
        print(
            f"  死用例 {stats['dead']} / 无断言 {stats['assertion_free']} /"
            f" 完全重复 {stats['duplicate']} / 自证用例 {stats['self_fulfilling']} /"
            f" 硬编码演进总数 {stats['hardcoded_totals']} / 恒真断言 {stats['trivial']} /"
            f" 死 fixture {stats['dead_fixtures']} / 弱 mock 断言 {stats['weak_mock']}"
        )
        print(f"  因不可解析的 self 间接调用而跳过重复比对的用例：{stats['duplicate_skipped']}")

    if args.audit:
        audit_lines, audit_stats = audit_similar_bodies(include_live=args.include_live, include_intra=args.audit_all)
        hidden = (
            "" if args.audit_all else f"（另文件内组 {audit_stats['intra_groups_total']} 未列，--audit-all 可显示）"
        )
        print(f"\n[..] 骨架审计（建议性，恒不参与退出码）：同名同骨架组 {audit_stats['groups']}{hidden}")
        for line in audit_lines:
            print(f"  {line}")
        if audit_lines:
            print("  说明：同构多为合法矩阵契约（同场景×不同模块），人工判读后如为复制粘贴须合并或差异化断言")

    sys.exit(
        report(
            findings,
            "[OK] 测试用例冗余与无效检查通过（无死用例 / 无断言 / 完全重复 / 自证用例 / 硬编码演进总数 / "
            "恒真断言 / 死 fixture / 弱 mock 断言）",
            ci=args.ci,
            fail_message="[!] 发现 {n} 处测试用例问题，须修正后提交",
        )
    )


if __name__ == "__main__":
    main()
