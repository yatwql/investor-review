# LLM worker 派发拆分 —— 结构契约（plan-251）

> 状态：**已完成**（实施结果见文末 §8）
> 对象：`src/python/llm/_llm_dispatch.py::_dispatch_llm_workers`（256 行）
> 关联：`plan.md` → `plan-251`

## 1. 立项背景

派发函数承担五件事：并发上限解析（含 thinking 模块的额外闸门）、worker 包装（HTTP/2 降级、心跳/等待记账）、辩论模式路由替换、线程池执行、结果字典归集。256 行里有 6 个嵌套闭包，**「哪个模块被提交、返回什么形状、失败如何沉淀」全靠读闭包**；而这三件事恰好是缓存与并发测试反复依赖的契约面。

## 2. 现状结构

| 顺序 | 片段 | 说明 |
|---|---|---|
| ① | 并发上限 | `_max_workers` 来自配置并 clamp；thinking 模块额外受 `_thinking_sem` 约束 |
| ② | `_make_runner(label, fn)` | 返回 `_run`：thinking 模块先取信号量并记等待时长，再 `_execute` |
| ③ | `_execute(label, fn)` | 打「正在生成」，建 client，HTTP/2 不可用时降级，调用 `fn(client, llm_config)` |
| ④ | 辩论路由 | 以 `_debate_wrapper` 替换 `expert_review` 槽：pro → con → synthesis 串行 |
| ⑤ | 线程池执行 | `with ThreadPoolExecutor(max_workers=...)` 提交并 `as_completed` 归集 |
| ⑥ | 返回 | `{module_key: (content, from_cache)}` |

## 3. 结构契约

| # | 契约 | 违反后果 | 守护方式 |
|---|---|---|---|
| 结果键集合 | 结果字典的 **键集合与提交的模块键集合相等**（含辩论模式下的键名） | 调用方取不到某模块 → 该章永久缺失且无失败原因 | 结构用例：断言键集合相等（不写死条数，按提交集合比较） |
| worker 返回形状 | 每个 worker 返回 `(content, from_cache)` 二元组；`content` 为 `None` 表示失败 | 调用方解包错位或把 `None` 当命中标志 | 返回值形状用例 + 既有 `test_generate_all_llm*` |
| 失败只登记一次 | 失败**不外抛**：worker 内异常被吞并登记到失败原因载体（`LLM_MODULE_FAILURE`），且只登记一次 | 单模块异常让整批失败，或原因被后续成功覆盖 | 既有失败原因用例 |
| 并发闸门 | 并发上限：普通模块受 `_max_workers`，thinking 模块**额外**受 `_thinking_sem`；上限不因重试/降级二次放宽 | 限速源被打爆（429 风暴），或实际并发与配置不符 | 既有并发用例（`test_generate_all_llm_concurrency`） |
| 辩论槽位替换 | 辩论路由是**槽位替换**：`expert_review` 键名不变（结果字典仍以该键返回），内部串行 pro/con/synthesis；任一子步失败回退原始实现 | 键名变化 → 下游章找不到内容；回退缺失 → 一次失败丢整章 | 既有辩论用例（`test_debate_pipeline`） |
| client 复用 | 共享 client 生命周期与 HTTP/2 降级判定单点（不得每个 worker 自建） | 连接数暴涨、降级判定不一致 | 现有 client 复用用例 |

## 3b. 与既往拆分的关系（避免重复分析）

本文件本身就是 rf-582（`f0f18601`）的产物：那次把「worker 装配 + 线程池分发 + 辩论路由」从
`generators_orchestrator.py`（798 行）整体下沉到 `llm/_llm_dispatch.py`（341 行），文件体量解了，
但**函数体量留在这里**——`_dispatch_llm_workers` 目前 256 行、6 个嵌套闭包。因此：

- 本项**不重复**「要不要把分发独立成模块」的论证（已定）；
- 只解决该模块内部的分界：并发闸门 / worker 包装 / 辩论路由 / 提交与归集；
- rf-582 确立的门面 re-export 与 patch 点纪律，在本项中继续有效（见契约表「client 复用」行同一层的约束）。

## 4. 拆分方案（目标形态）

- 保留 `_dispatch_llm_workers` 为**提交与归集壳**（上限解析 → 构造 runner → 提交 → 归集），目标 ≤ 80 行；
- `_worker_runner.py`：`make_runner` / `_execute` / thinking 闸门与等待记账；
- `_debate_router.py`：辩论槽位替换（含回退原始实现）；
- 三者之间只传「模块键 → 生成函数」映射与 client 工厂，闭包捕获改为显式参数。

## 5. 验收口径

1. 结构用例：结果键集合 == 提交集合；worker 返回形状合法；失败仅登记既不抛出也不覆盖；
2. 并发用例（上限/thinking 闸门/辩论槽位）全绿；
3. `_dispatch_llm_workers` ≤ 80 行；
4. 一次真实报告（隔离演示工作区）：LLM 章产出与拆分前一致，`[LLM]` 用量行数不变。

## 6. 风险与回滚

- 风险：闭包改显式参数时漏传（thinking 开关、限速器、标签映射），表现为并发/限速静默失效。
- 缓解：拆分前先把「上限与闸门」写成可观测断言（注入计数桩，断言最大并发），再动代码；三个片段各自独立提交，逐个回滚。

## 7. 非目标

- 不改各生成函数（`generate_global_macro` 等）的实现与提示词；
- 不改 `run_fact_check` / 自检链路（属 `plan-250` 的生成后一遍）；
- 不改限速器与 provider 选择策略。

## 8. 实施结果

| 项 | 结果 |
|---|---|
| 派发壳 | `_dispatch_llm_workers` 函数体 256 → 75 行：只留早退、thinking 闸门与等待记账接线、`_build_module_fns` 装配、辩论路由安装、`_run_workers` 调用 |
| worker 装配外移 | 新模块 `llm/_worker_runner.py`：`thinking_concurrency_limit`（非法值回落 1）/ `is_thinking_module` / `make_module_runner`（thinking 闸门 → client 装配与缺 h2 降级 → 调用生成函数 → span 记录）。`make_http_client` 的消费点随之迁移 |
| 辩论路由外移 | 新模块 `llm/_debate_router.py`：`install_debate_route` 槽位替换 + 两级回退（synthesis 失败 → pro+con 拼接；pro/con 失败或异常 → 回退普通生成并清空辩论信息容器）、`debate_mode_combination` |
| 提交与归集 | `_run_workers`（28 行）：自建预算闸 → 只提交 `needs=True` → 异常不外抛且留 WARNING → 结果键集合与提交集合相等；`_log_dispatch_tail` 记预算跳过清单与 thinking 串行等待量化 |
| 契约守护 | `test_llm_dispatch_contract.py` 11 条结构用例在拆分前后均绿（结果键集合 / 返回形状 / 线程异常隔离 / 并发上限回落 / 预算闸 / 辩论槽位 / client 降级） |
| patch 点迁移 | `make_http_client` 6 处迁到 `_worker_runner`；辩论生成函数按「延迟导入 → patch 源模块」指向 `llm.generators`；另清掉 9 处从未生效的 `_llm_dispatch.httpx.Client` patch（client 一律经 `make_http_client` 构造） |
| 门禁 | `src/test/unit/llm` + `integration` 1791 项、`dev-verify` 全绿；ruff / 类型 / 文档守护全过 |
