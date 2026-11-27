"""变异评测的结果类型（内置变异器与可选后端 mutmut 共用同一套计数与判定口径）。

`MutationCounts` 的**分母口径**是整套评测的关键：只有「判定得了」的变异体（killed / survived）
进分母，超时与错误单独计数——否则工具故障会被算成测试质量问题。
"""

from __future__ import annotations

from dataclasses import dataclass

from _eval_mutation.operators import Mutant

#: 变异体判定四态（killed / survived 参与得分，timeout / error 不计入分母）
STATUS_KILLED = "killed"
STATUS_SURVIVED = "survived"
STATUS_TIMEOUT = "timeout"
STATUS_ERROR = "error"


@dataclass(frozen=True)
class MutationCounts:
    """一次切片评测的变异体计数（`generated`/`executed` 对未来后端可能不可知，故可空）。"""

    killed: int
    survived: int
    timed_out: int = 0
    errored: int = 0
    generated: int | None = None
    executed: int | None = None

    @property
    def evaluated(self) -> int:
        """参与得分的变异体数（超时/错误不计入分母，与得分口径一致）。"""
        return self.killed + self.survived

    @property
    def score(self) -> float | None:
        """变异得分（百分比）；无参与得分的变异体时返回 None（不编造 0 分）。"""
        return None if self.evaluated == 0 else self.killed * 100.0 / self.evaluated


@dataclass(frozen=True)
class MutantOutcome:
    """单个变异体的执行结果（`summary` 供判读：失败用例首行或错误摘要）。"""

    mutant: Mutant
    status: str
    summary: str = ""


@dataclass(frozen=True)
class SliceRun:
    """一个切片的执行结果（`notes` 如实记录截断/超时/跳过等口径信息）。"""

    counts: MutationCounts
    survivors: tuple[MutantOutcome, ...] = ()
    notes: tuple[str, ...] = ()
