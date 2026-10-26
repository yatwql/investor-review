# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.2-dev
> **编号源**：`rf-next = 909`（新增问题取此编号，完成后更新为 +1；已用最大 rf-908，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。本轮为「架构约束 / 设计契约 / 内部兼容适配」全面审查结果——约束项逐条机检未见违背，以下为内部兼容层存量。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-901** | 旧单 Provider 配置兼容簇：`llm/api.py::call_llm` 无 `_provider_list` 时回退 `_call_llm_legacy()`（单 Provider 直连，绕过 `strategy.py` 链路由，违背「Provider Chain 必经」约束），并读顶层 `provider`/`api_key`/`endpoint`/`model`；`config/_llm_settings.get_llm_config` 把 `llm_key.json` 整份 merge 进顶层；连带 `core/system_info.py` 的 flat 模式分支与路由行、`core/doctor.py` 的 flat 凭据分支、`llm/generators_news.py` 与 `llm/api_base.py` 的顶层字段读取 | 删 `_call_llm_legacy` 与回退分支（无链配置显式失败）、密钥文件只承载凭据块（不进顶层合并）、删 flat 分支。**前置**：约 63 例测试以旧形态构造 `llm_config`（`{"provider": ..., "api_key": ...}`），须先加 `make_chain_config()` 测试夹具并整体迁移，再删实现（本次尝试已确认该前置，回退未落） |
| **rf-902** | `llm_key.json` 单凭据旧格式自动升级：`config/_llm_providers._load_llm_key_credentials` 顶层见 `api_key` 即包裹为 `{"_default": ...}` | 随 rf-901 同批：删除自动包裹，旧格式告警并拒绝（提示改 `credentials_ref` 命名块）；迁移受影响的密钥文件用例 |
### P3 — 持续监控：待核兼容形态

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 待办 |
|---|------|----------|
| **rf-907** | 持仓明细渠道双输入：`analysis/rebalance_advisor._channel_of_holding` 兼容旧调用的 `account` 字段（规范字段为 `channel`，报告层 `_orchestrator_data.py` 已按账户判定填充） | 先核分析层调用面与 fixture，再删 `account` 回退，让「渠道」只有 `channel` 一个来源 |
| **rf-908** | 快照双形态读取：`analysis/prosperity_signals.py` 的 `snap.get("holdings") or snap.get("details")` 兼容两种快照字段（行情 bars 的 `close`/`nav` 属基金与股票多源差异，非历史兼容，不动） | 先定快照唯一字段并核 `data/state/` 历史文件，再删回退 |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。当前无登记项。

## 已解决问题

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-25）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.0 ~ v0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
