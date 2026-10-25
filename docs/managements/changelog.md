# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.0]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.1-dev] - 开发中（未发布）

- **归还 360 小时（15 天）实施变更的技术债（rf-889 / rf-890 / rf-891 / rf-892）**：① 删掉评测包 `llm_call.py` 里三处与 `holdings.py` 逐字重复的持仓侧函数（其中一份引用已搬走的 `fact_checker._calc_portfolio_values`，被调即 ImportError，属潜在隷弹）——rf-889；② 三家行情源（sina / sina_kline / tencent）各自一份逐字相同的 `_add_prefix` 收敛为 `providers/utils.with_exchange_prefix`，改一处即三处同步，不再能静默取错代码——rf-890；③ 因子动物园评测脚本内联的 3 个公式（有意避开 src 私有名）加同源数值测试，公式漂移即红——rf-891；④ 生产代码 6 处拿 `assert` 当类型收窄/入参校验（`python -O` 下会被剥离，炸点后移且信息更差）改为显式分支/告警，现全仓生产代码 `assert` 清零——rf-892。
- **归还 36 小时实施变更的技术债（rf-882 / rf-883 / rf-884 / rf-885 / rf-886 / rf-887 / rf-888）**：① 注释混入西里尔字母已改正（rf-882）；② 配置时效自检把「文件解析失败」与「缺新键」分开报，原先语法错会被说成「缺全部 40 个新键」（rf-883），非 UTF-8 文件不再冒泡异常（rf-884），`import json` 提到模块顶部（rf-885）；③ 删掉零调用的 `core/costs.add_cost_bucket`（rf-886）；④ 重算原因改为引用 `observation.RECOMPUTE_*` 常量（此前字符串字面量散在预检/骨架两路），并对域外值告警一次（rf-887）；⑤ 补 provider 默认模板与路线说明的对齐回归，新增线路漏写说明会红（rf-888）。
- **`llm_providers.json` 出厂默认换成 DeepSeek + OpenCode Go**：`_DEFAULT_LLM_PROVIDERS` 由通用示例（`deepseek-main` + `gemini-fallback`）改为两条 Anthropic 兼容线路——`deepseek-main`（priority 10，按量付费、不限速）与 `opencode-go`（priority 20，订阅制编码中转，带 `pacing` 限速：间隔 ≥5s / 在途 ≤1）；模板注释也改成针对这两条线写（各自配哪个凭据块、pacing 为何只加在第二条、调序入口），不再是通用说明（新增 `_PROVIDER_NOTES` 按线路名对齐注释，改线路只动 dict）。配置指南同步给出两套配法示例（DeepSeek + OpenCode Go / DeepSeek + Gemini）。
- **系统自检新增「配置说明时效」**（`[D]`→`[T]` / CLI `doctor` 的「配置」组）：对比 `config.json` / `llm_settings.json` / `llm_providers.json` 与当前生成器模板——**缺新键**判失败（新功能开关在用户文件里不存在），**仅缺说明**判通过但建议重生成（注释可能指向已改名的菜单键）。背景：菜单键从 P 改到 C、新增 `notify`/`scheduler` 等键后，用户持有的旧文件不会自动跟随，只会照着旧注释找不到入口（实现 `config/_config_freshness.py`，注释抽取对字符串内的 `//` 免疫——`https://…` 不会被当成注释）。
- **`features.json` 重建带逐项说明**：紧凑单行文件将被重排版时，每行尾部自动附上注册表的「显示名：一句话说明」，用户手工编辑不必回查文档；末项不带尾逗号、整体可被注释剥离器解析。
- **配置指南新增「配置文件随版本更新」节**：说清键与注释只在生成时写入、自检怎么提示、各文件重生成前需要抄回哪段自定义值。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0（2026-10-25）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
