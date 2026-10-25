# 变更日志归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.1 发布并入；已并入 2 段：v0.16.0（10-25）、v0.16.1（10-25））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.16.0 ~ v0.16.1（2026-10-25 ~ 2026-10-25）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.16.0] - 2026-10-25

- **LLM 调用日志行单独上品红（TUI / 控制台）**：报告运行时每次真实 LLM API 调用都以 `[LLM]` 开头（`[LLM] <模块>: 输入/输出 tokens`、`[LLM] 正在调用 …`），控制台格式器与 `[D]→[V]` 日志查看器凭此前缀上品红，滚屏进度行里一眼能看出“真的花钱调用了”；`[LLM 预检]`、`缓存命中`、`已禁用` 等判定/跳过行不上色——颜色只承诺“这里真的调用了”。级别色优先：`[LLM]` 行若同时是 WARNING/ERROR 仍按状态色。判据单点实现在 `core/logger.is_llm_call_message`，配色角色已登记 `DESIGN-TUI.md`（新增「事件（LLM 调用）」一行）；回归用例 9 例（前缀判据 / 品红上色 / 级别色优先 / 无色模式 / 查看器同源）。

## [0.16.1] - 2026-10-25

- **归还 360 小时（15 天）实施变更的技术债（rf-889 / rf-890 / rf-891 / rf-892）**：① 删掉评测包 `llm_call.py` 里三处与 `holdings.py` 逐字重复的持仓侧函数（其中一份引用已搬走的 `fact_checker._calc_portfolio_values`，被调即 ImportError，属潜在哑弹）——rf-889；② 三家行情源（sina / sina_kline / tencent）各自一份逐字相同的 `_add_prefix` 收敛为 `providers/utils.with_exchange_prefix`，改一处即三处同步，不再能静默取错代码——rf-890；③ 因子动物园评测脚本内联的 3 个公式（有意避开 src 私有名）加同源数值测试，公式漂移即红——rf-891；④ 生产代码 6 处拿 `assert` 当类型收窄/入参校验（`python -O` 下会被剥离，炸点后移且信息更差）改为显式分支/告警，现全仓生产代码 `assert` 清零——rf-892。
- **归还 36 小时实施变更的技术债（rf-882 / rf-883 / rf-884 / rf-885 / rf-886 / rf-887 / rf-888）**：① 注释混入西里尔字母已改正（rf-882）；② 配置时效自检把「文件解析失败」与「缺新键」分开报，原先语法错会被说成「缺全部 40 个新键」（rf-883），非 UTF-8 文件不再冒泡异常（rf-884），`import json` 提到模块顶部（rf-885）；③ 删掉零调用的 `core/costs.add_cost_bucket`（rf-886）；④ 重算原因改为引用 `observation.RECOMPUTE_*` 常量（此前字符串字面量散在预检/骨架两路），并对域外值告警一次（rf-887）；⑤ 补 provider 默认模板与路线说明的对齐回归，新增线路漏写说明会红（rf-888）。
- **`llm_providers.json` 出厂默认换成 DeepSeek + OpenCode Go**：`_DEFAULT_LLM_PROVIDERS` 由通用示例（`deepseek-main` + `gemini-fallback`）改为两条 Anthropic 兼容线路——`deepseek-main`（priority 10，按量付费、不限速）与 `opencode-go`（priority 20，订阅制编码中转，带 `pacing` 限速：间隔 ≥5s / 在途 ≤1）；模板注释也改成针对这两条线写（各自配哪个凭据块、pacing 为何只加在第二条、调序入口），不再是通用说明（新增 `_PROVIDER_NOTES` 按线路名对齐注释，改线路只动 dict）。配置指南同步给出两套配法示例（DeepSeek + OpenCode Go / DeepSeek + Gemini）。
- **系统自检新增「配置说明时效」**（`[D]`→`[T]` / CLI `doctor` 的「配置」组）：对比 `config.json` / `llm_settings.json` / `llm_providers.json` 与当前生成器模板——**缺新键**判失败（新功能开关在用户文件里不存在），**仅缺说明**判通过但建议重生成（注释可能指向已改名的菜单键）。背景：菜单键从 P 改到 C、新增 `notify`/`scheduler` 等键后，用户持有的旧文件不会自动跟随，只会照着旧注释找不到入口（实现 `config/_config_freshness.py`，注释抽取对字符串内的 `//` 免疫——`https://…` 不会被当成注释）。
- **`features.json` 重建带逐项说明**：紧凑单行文件将被重排版时，每行尾部自动附上注册表的「显示名：一句话说明」，用户手工编辑不必回查文档；末项不带尾逗号、整体可被注释剥离器解析。
- **配置指南新增「配置文件随版本更新」节**：说清键与注释只在生成时写入、自检怎么提示、各文件重生成前需要抄回哪段自定义值。
