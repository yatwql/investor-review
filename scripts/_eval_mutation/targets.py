"""变异评测的目标切片表与默认参数（改目标/改口径只改这一张表）。

每个切片 = 一次评测的边界，同时给出三件事：
  - `paths`   —— 要被变异的源码（相对仓库根，可含 glob）
  - `tests`   —— 逐变异体只跑**这些**测试（相对仓库根，文件或目录）——不逐变异体跑全树是
                 可承受的唯一前提：单次 pytest 秒级，乘上变异体数是分钟级
  - `rationale` —— 为什么盯这块（写给人看，不参与判定）
"""

from __future__ import annotations

from dataclasses import dataclass

#: 后端名：内置有界变异器（默认，无外部依赖）/ 可选后端 mutmut（需 3.x 兼容配置）
BACKEND_BUILTIN = "builtin"
BACKEND_MUTMUT = "mutmut"

#: 默认变异得分阈值（百分比）：killed / (killed + survived)
DEFAULT_THRESHOLD = 80

#: 单切片默认变异体上限：无界会跑成小时级（每变异体一次 pytest），故默认截断
DEFAULT_MAX_MUTANTS = 60

#: 单变异体默认超时（秒）：正常切片一次 pytest 是秒级，超 3 分钟说明变异体把用例挂住了
DEFAULT_MUTANT_TIMEOUT = 180

#: 单切片默认总时限（秒）：到点即停（未执行的不计入分母并如实注明），兜住整轮墙钟
DEFAULT_SLICE_TIMEOUT = 1800

#: 默认并行度：串行（多文件切片并行需文件互斥，跨文件依赖会造成误 kill，故不默认开）
DEFAULT_JOBS = 1

#: 声明口径的变异算子集（实现在 `operators.py`，逐类对应一组等价算术/比较/布尔变换）
OPERATORS: tuple[str, ...] = ("算术替换", "比较取反", "布尔取反", "返回值替换")


@dataclass(frozen=True)
class MutationTarget:
    """一个变异目标切片（= 一次评测的边界，逐切片跑避免一次全仓）。"""

    name: str
    paths: tuple[str, ...]
    tests: tuple[str, ...]
    rationale: str
    operators: tuple[str, ...] = OPERATORS


#: 首期变异目标清单（新增/调整目标只改这张表）
TARGETS: tuple[MutationTarget, ...] = (
    MutationTarget(
        name="analysis-metrics",
        paths=("src/python/analysis/metrics*.py",),
        tests=(
            "src/test/unit/analysis/test_metrics.py",
            "src/test/unit/analysis/test_metrics_risk.py",
            "src/test/unit/analysis/test_metrics_edge.py",
            "src/test/unit/analysis/test_property_metric_invariants.py",
            "src/test/unit/analysis/test_tail_risk.py",
        ),
        rationale="指标计算全家桶（收益率/风险/派生）：纯算术，算术替换与返回值替换最能曝出弱断言",
    ),
    MutationTarget(
        name="analysis-correlation",
        paths=("src/python/analysis/correlation.py",),
        tests=(
            "src/test/unit/analysis/test_correlation.py",
            "src/test/unit/analysis/test_correlation_edge.py",
            "src/test/unit/analysis/test_property_correlation_invariants.py",
        ),
        rationale="相关性计算：比较取反会翻转符号判定，断言只查范围而不查方向的用例在此暴露",
    ),
    MutationTarget(
        name="cache-ttl-atomic-write",
        paths=("src/python/cache/",),
        tests=("src/test/unit/cache/",),
        rationale="缓存 TTL 与原子写：边界比较（> / >=）与布尔取反决定过期与覆盖语义，最易漏测",
    ),
    MutationTarget(
        name="report-pipeline-data",
        paths=("src/python/report/pipeline_data_builder.py",),
        tests=(
            "src/test/unit/report/test_pipeline_data_builder.py",
            "src/test/unit/report/test_pipeline_data_builder_branches.py",
        ),
        rationale="报告数据契约（C19）：未注册键 / 缺键 / 占位语义错了会静默污染 Excel 与 HTML 两处呈现",
    ),
    MutationTarget(
        name="analysis-factor-formulas",
        paths=("src/python/analysis/_factor_formulas.py",),
        tests=("src/test/unit/analysis/",),
        rationale="因子公式纯算术：算术替换与返回值替换最能暴露「只查范围不查值」的断言",
    ),
    MutationTarget(
        name="core-dates",
        paths=("src/python/core/dates.py",),
        tests=("src/test/unit/core/test_dates.py",),
        rationale="交易日历与日期换算：比较取反与算术替换会错位日期边界，静默影响全仓取数窗口",
    ),
)
