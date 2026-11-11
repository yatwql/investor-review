# LLM 并行编排拆分 —— 结构契约（plan-250）

> 状态：**已完成**（实施结果见文末 §8；文件与契约用例同步落地）
> 对象：`src/python/llm/generators_orchestrator.py::generate_all_llm`（392 行）
> 关联：`plan.md` → `plan-250`

## 1. 立项背景

`generate_all_llm` 是四模块 LLM 生成的唯一入口：装配 5 个上下文块 → 缓存预检 → 派发并行批 → 事实锚定校验 → 生成后自检 → 跨模块一致性核对 → 返回结果元组。392 行里混着「块装配」「键与指纹对齐」「并发编排」「生成后一遍」，其中**最容易错且最难看出来**的是：同一份上下文块实例必须既进缓存指纹又进提示词正文——两处若各自渲染一次，缓存键与请求体就脱钩（同一输入算出两个键，或换输入命中旧键）。

## 2. 现状结构（阶段）

| 顺序 | 阶段 | 说明 |
|---|---|---|
| ① | 强刷范围归一 | `force` + `force_modules` → 模块键集合（`resolve_force_scope`） |
| ② | 上下文块装配 ×5 | 竞争语境块 / 数据质量详细块 / 申购限购块 / 持仓变动块 / 事件窗块 / 调仓纪律回放块（均「渲染一次，实例同时进指纹与提示词」） |
| ③ | 缓存预检 | 命中即跳过派发（辩论模式强制不走标准 expert_review 预检） |
| ④ | 并行派发 | `_dispatch_llm_workers`（含辩论路由、thinking 闸门） |
| ⑤ | 事实锚定校验 | 四模块产出逐模块校验 + 缓存回写 |
| ⑥ | 生成后自检 | 开关开启时串行执行，输入为 ④⑤ 的产出 |
| ⑦ | 跨模块一致性核对 | 确定性，零 token |
| ⑧ | 返回 | 8 元组（辩论模式 9 元组，多一个辩论信息位） |

## 3. 结构契约

| # | 契约 | 违反后果 | 守护方式 |
|---|---|---|---|
| 返回位序 | 返回元组**前 8 位语义与顺序固定**（4 模块正文 + 4 命中标志），第 9 位仅在辩论模式出现；调用方以 `*_` 兼容两者 | 调用方按位置解包串位 → 正文与命中标志互换（缓存判定全错） | 结构用例：固定输入下返回长度与位序；既有 `test_generate_all_llm*` 全绿 |
| 门面 patch 点 | `_dispatch_llm_workers` 由门面 `generators_orchestrator` re-export，`generate_all_llm` 也必须在**门面内**消费它 | `patch("…generators_orchestrator._dispatch_llm_workers")` 静默 no-op：用例照样绿，而真实分发根本没被替换 | 既有 `test_debate_pipeline` 的两处 patch 用例（拆后仍须绿） |
| 块实例单次渲染 | 上下文块**只渲染一次**，同一实例既进指纹又进提示词（对象身份不重建） | 指纹与请求体脱钩：换输入命中旧缓存、或同输入永不命中 | 身份断言用例（`is` 比对指纹入参与提示词入参） |
| 阶段顺序 | 阶段顺序不变：预检 → 派发 → 锚定 → 自检 → 跨模块核对（自检必须在四模块产出之后串行） | 自检读到未锚定的正文 → 复核结论与最终正文不一致 | 既有自检/锚定用例 + 顺序断言（阶段表顺序） |
| 失败隔离 | 单模块失败**隔离**：失败模块返回 `None` 且命中标志 `False`，不抛异常 | 一个模块挂掉使整份报告无 LLM 章 | 既有失败隔离用例 |
| 强刷范围单一点 | 强刷范围归一单点（`resolve_force_scope`），模块内不得二次解释 force | 强刷与缓存矩阵行为不一致（改配置不生效） | `test_force_scope` 现有用例 |
| 空块键不变 | 块空与块缺省**逐字节等价**（不追加分隔符） | 空块改变缓存键 → 存量缓存无谓全量失效 | 黄金值基线用例（现有 `_PRE_WIRE_BASELINE`） |

## 3b. 与既往拆分的关系（避免重复分析）

同一方向已经做过**文件级**一刀：`f0f18601`（rf-582，2026-10-06）把 `generators_orchestrator.py` 的
「worker 装配 + 线程池分发 + 辩论路由」整体下沉到新建 `llm/_llm_dispatch.py`，门面降到 480 行，
并确立了「门面 re-export 保持既有 patch 点」的纪律。本项是同一方向的**函数级续拆**，边界如下：

| 维度 | rf-582（已做） | plan-250（本项） |
|---|---|---|
| 粒度 | 文件体量（798 → 480），按职责整体搬家 | 函数体量（392 行），把函数内的阶段拆成可断言的顺序 |
| 产出 | 新模块 + 门面 re-export | 上下文块整组与生成后一遍各自成模块，门面只剩编排壳 |
| 未覆盖 | `generate_all_llm` 函数体原样留在门面 | 正是本项要解决的：块装配 / 预检 / 派发 / 锚定 / 自检 / 核对的分界与契约 |

事实补充：文件此后因自检（rf-1111）、跨模块核对、数据质量块等新增又长到 **863 行**，
距 1000 行红线 137 行——本项同时是这条红线的提前处置。

## 4. 拆分方案（目标形态）

- `generate_all_llm` 保留为**编排壳**（阶段表 + 返回值组装），目标 ≤ 100 行；
- 块装配整组移到 `_llm_context_blocks.py`（返回一个「块快照」结构体，指纹与提示词共用同一实例）；
- 生成后一遍（锚定 + 自检 + 跨模块核对）移到 `_llm_post_pass.py`；
- 预检/派发保持现有归属（`_llm_dispatch`），本项只做调用面收窄。

## 5. 验收口径

1. 结构用例：返回元组位序（含辩论模式第 9 位）+ 块实例身份 + 阶段表顺序；
2. 缓存矩阵用例（命中/未命中/强刷/模块级 force）与 `test_llm_cache_*` 全绿，黄金值基线不变；
3. `generate_all_llm` ≤ 100 行；
4. 一次真实报告（隔离演示工作区）产出与拆分前逐章 diff 为空。

## 6. 风险与回滚

- 风险最高：「块实例单次渲染」与「空块键不变」——两者都会「静默改缓存键」，表现为全量重算或命中旧值。缓解：先加身份断言与黄金值用例，再动代码；拆分期间不碰任何提示词文本。
- 回滚粒度：块装配 / 生成后一遍 两笔独立提交。

## 7. 非目标

- 不改提示词文本、不加盐、不动 `PROMPT_SCHEMA_VERSION`；
- 不改 `_llm_dispatch` 的并发与 thinking 闸门（另项 `plan-251`）；
- 不改辩论模式的生成实现（`generators.generate_debate_*`）。

## 8. 实施结果

| 项 | 结果 |
|---|---|
| 编排壳 | `generate_all_llm` 函数体 392 → 101 行（含 docstring 152 行），新增 `_plan_generation` / `_plan_module_needs` / `_finalize_llm_run` 三个编排辅助 |
| 块装配外移 | 新模块 `llm/_llm_context_blocks.py`：六块单次渲染/提取收成不可变快照 `LlmContextBlocks`，`fingerprint_kwargs()` 与 `prompt_kwargs()` 同源输出；四个 `extract_*` 与 `extract_historical_codes` 一并迁入，门面继续 re-export（`from src.python.llm import extract_*` 不变） |
| 生成后一遍外移 | 新模块 `llm/_llm_post_pass.py`：`anchor_fact_checks`（逐模块锚定 + 缓存回写 + 摘要）/ `apply_generation_post_pass`（自检 → 跨模块核对）/ `review_text`（剥页脚与校验产物）/ `contents_from_results`（按位取四模块正文与标志） |
| 契约守护 | `test_generate_all_llm_contract.py` 7 条结构用例（返回位序 / 块实例身份 / 门面 patch 点 / 生成后一遍顺序 / 配置缺席短路 / needs 并入 holding_change）在拆分前后均绿 |
| patch 点迁移 | 块渲染器与 `run_fact_check` 的调用点随实现迁至新模块，7 处既有 patch 目标同步迁移（`_llm_context_blocks._build_*` / `_llm_post_pass.run_fact_check`）；门面侧已无这两个名字，漏迁即 AttributeError 响亮失败 |
| 门禁 | `src/test/unit/llm` + `integration` 1780 项、`dev-verify` 全绿；ruff / 类型 / 文档守护全过 |
