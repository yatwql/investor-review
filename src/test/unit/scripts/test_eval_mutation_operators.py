"""`_eval_mutation/operators.py` 单测：四类算子的正反例、单点性与 UTF-8 偏移正确性。

全部是纯函数（AST 解析 + 文本替换），不读写任何文件、不起子进程、不触碰仓库真实源码；
临时源码一律写成字符串常量。
"""

from __future__ import annotations

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mutation")
def fixture_mutation():
    """加载算子实现模块（被测面；入口只做 argparse 装配与调用）。"""
    load_script("eval-mutation-score.py")  # 先接上 scripts/ 的 sys.path
    return load_script("_eval_mutation/operators.py", module_name="_eval_mutation_operators")


def _mutants(mutation, source: str, operator: str) -> list:
    """某算子在给定源码上的全部变异体（其余算子的产物过滤掉，断言才够窄）。"""
    return [mutant for mutant in mutation.iter_mutants("m.py", source) if mutant.operator == operator]


class TestCompareFlip:
    """比较取反：四组配对互换，`is` 之类不属声明口径的算子不动。"""

    @pytest.mark.parametrize(
        ("expression", "flipped", "detail"),
        [
            ("a < b", "a <= b", "< → <="),
            ("a <= b", "a < b", "<= → <"),
            ("a > b", "a >= b", "> → >="),
            ("a >= b", "a > b", ">= → >"),
            ("a == b", "a != b", "== → !="),
            ("a != b", "a == b", "!= → =="),
            ("a in b", "a not in b", "in → not in"),
            ("a not in b", "a in b", "not in → in"),
        ],
    )
    def test_each_pair_flips_to_its_counterpart(self, mutation, expression, flipped, detail):
        source = f"def f(a, b):\n    return {expression}\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_COMPARE)
        assert len(mutants) == 1
        assert mutants[0].source == source.replace(expression, flipped)
        assert mutants[0].detail == detail

    def test_identity_comparison_is_out_of_scope(self, mutation):
        source = "def f(a, b):\n    return a is b\n"
        assert _mutants(mutation, source, mutation.OPERATOR_COMPARE) == []

    def test_chained_comparison_mutates_one_link_at_a_time(self, mutation):
        source = "def f(a, b, c):\n    return a < b < c\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_COMPARE)
        assert [mutant.source for mutant in mutants] == [
            "def f(a, b, c):\n    return a <= b < c\n",
            "def f(a, b, c):\n    return a < b <= c\n",
        ]


class TestBoolFlip:
    """布尔取反：`and`↔`or`、`not x` → `(x)`；跨行书写跳过不猜。"""

    def test_and_becomes_or(self, mutation):
        source = "def f(a, b):\n    return a and b\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_BOOL)
        assert [mutant.source for mutant in mutants] == ["def f(a, b):\n    return a or b\n"]

    def test_or_becomes_and(self, mutation):
        source = "def f(a, b):\n    return a or b\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_BOOL)
        assert [mutant.source for mutant in mutants] == ["def f(a, b):\n    return a and b\n"]

    def test_not_is_dropped_with_the_operand_wrapped(self, mutation):
        source = "def f(a):\n    return not a\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_BOOL)
        assert [mutant.source for mutant in mutants] == ["def f(a):\n    return (a)\n"]

    def test_boolean_operator_split_across_lines_is_skipped(self, mutation):
        source = "def f(a, b):\n    return (\n        a\n        and b\n    )\n"
        assert _mutants(mutation, source, mutation.OPERATOR_BOOL) == []


class TestArithmeticFlip:
    """算术替换：`+`↔`-`、`*`↔`/`；取模与幂运算不属于声明口径。"""

    @pytest.mark.parametrize(
        ("expression", "flipped"),
        [("a + b", "a - b"), ("a - b", "a + b"), ("a * b", "a / b"), ("a / b", "a * b")],
    )
    def test_each_pair_flips_to_its_counterpart(self, mutation, expression, flipped):
        source = f"def f(a, b):\n    return {expression}\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_ARITH)
        assert len(mutants) == 1
        assert mutants[0].source == source.replace(expression, flipped)

    @pytest.mark.parametrize("expression", ["a % b", "a ** b"])
    def test_out_of_scope_arithmetic_is_skipped(self, mutation, expression):
        source = f"def f(a, b):\n    return {expression}\n"
        assert _mutants(mutation, source, mutation.OPERATOR_ARITH) == []


class TestReturnReplacement:
    """返回值替换：`return X` → `return None`，但 `return None` / 裸 `return` 不算变异体。"""

    def test_non_none_return_becomes_none(self, mutation):
        source = "def f(a):\n    return a + 1\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_RETURN)
        assert [mutant.source for mutant in mutants] == ["def f(a):\n    return None\n"]

    def test_constant_return_true_becomes_none(self, mutation):
        source = "def f():\n    return True\n"
        mutants = _mutants(mutation, source, mutation.OPERATOR_RETURN)
        assert [mutant.source for mutant in mutants] == ["def f():\n    return None\n"]

    @pytest.mark.parametrize("body", ["return None", "return"])
    def test_none_and_bare_return_produce_nothing(self, mutation, body):
        source = f"def f():\n    {body}\n"
        assert _mutants(mutation, source, mutation.OPERATOR_RETURN) == []


class TestSinglePointAndOffsets:
    """单点性（只改一处）与 UTF-8 偏移（`col_offset` 是字节偏移，非字符偏移）。"""

    def test_only_one_spot_changes_per_mutant(self, mutation):
        source = "def f(a, b):\n    x = a < b\n    y = a > b\n    return x and y\n"
        mutations = [mutant.source for mutant in mutation.iter_mutants("m.py", source)]
        # 4 个变异点（两处比较取反 + 一处布尔取反 + 一处返回值），每次只动其中一处
        assert len(mutations) == 4
        assert len({mutated for mutated in mutations}) == 4
        for mutated in mutations:
            differing = [pair for pair in zip(source.splitlines(), mutated.splitlines()) if pair[0] != pair[1]]
            assert len(differing) == 1

    def test_chinese_comment_before_the_mutation_point_keeps_offsets_aligned(self, mutation):
        source = '"""中文文档字符串（多字节，col_offset 按字节算）。"""\n\ndef f(a, b):\n    # 中文注释：比较\n    return a == b\n'
        mutants = _mutants(mutation, source, mutation.OPERATOR_COMPARE)
        assert [mutant.source for mutant in mutants] == [source.replace("a == b", "a != b")]

    def test_every_mutant_stays_syntactically_valid(self, mutation):
        source = (
            "def f(items, flag, other):\n"
            "    if not flag and items in other:\n"
            "        return len(items) * 2 + 1\n"
            "    if flag or items:\n"
            "        return [item for item in items if item != other]\n"
            "    return None\n"
        )
        mutants = mutation.iter_mutants("m.py", source)
        assert mutants
        for mutant in mutants:
            compile(mutant.source, "m.py", "exec")  # 语法错误会在这里炸掉

    def test_mutants_are_deterministic_and_line_ordered(self, mutation):
        source = "def f(a, b):\n    x = a < b\n    return x + 1\n"
        first = [mutant.label for mutant in mutation.iter_mutants("m.py", source)]
        second = [mutant.label for mutant in mutation.iter_mutants("m.py", source)]
        assert first == second
        lines = [mutant.line for mutant in mutation.iter_mutants("m.py", source)]
        assert lines == sorted(lines)


class TestUnparsableSource:
    """解析不了就抛 SyntaxError（由调用方如实报出），不静默返回空清单。"""

    def test_syntax_error_propagates(self, mutation):
        with pytest.raises(SyntaxError):
            mutation.iter_mutants("m.py", "def f(:\n    pass\n")
