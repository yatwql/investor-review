"""变异评测内部实现包（入口 `eval-mutation-score.py` 仅留 CLI、判定与门面 re-export）。

targets        — 目标切片表（路径 + 算子口径 + 每个切片跑哪些测试）
operators      — 内置变异器的算子层（AST 单点变异，纯函数）
runner         — 内置变异器的执行协议层（备份 → 写入 → 跑测试 → 还原校验 → 分类）
mutmut_backend — 可选后端 mutmut 的命令拼装与输出解析（保留但不作默认）

入口脚本已把 `scripts/` 放入 `sys.path`，包内模块统一用
`from _eval_mutation.<module> import …` / `from _shared.checklib import …` 引用。
"""
