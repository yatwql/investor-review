# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.1-dev
> **编号源**：`rf-next = 889`（新增问题取此编号，完成后更新为 +1；已用最大 rf-888，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 4 类人工项（进度观察 3.1c/3.2/3.3/3.4、结果区按钮 4.5、提交即禁用 5.3、拖拽与 Tab/Enter 抽验 2.5/2.6） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` + `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

当前无 P2 项（入选标准：重构收益明确、回归面可圈定）。

### P3 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。**当前无登记项**。

## 已解决问题

### 开发期已修复（0.16.1-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-882** | `cache/_cleanup._fmt_span` docstring 混入西里尔字母（应为「两」），全文扫描仅此一处非中文外文字符 | 改为「两」，并反向核对希腊字母使用均为公式符号（Σ/σ/Π）属合法 |
| **rf-883** | `config/_config_freshness._keys_of` 解析失败返回空集 → 自检把「文件语法坏」报成「缺全部 40 个新键」，误导修复方向 | 返回 `None` 表示不可比较；`_diff` 增加 `parse_error` 字段；自检单独报「无法解析」并给编码/语法提示；回归 2 例 |
| **rf-884** | 同模块 `check_config_freshness` 只捕 `OSError`，非 UTF-8 配置文件解码失败时冒泡成「对比失败」 | 同时捕 `UnicodeDecodeError`（跳过，由配置加载检查负责报错）；回归 1 例 |
| **rf-885** | 同模块 `import json` 写在函数体内（风格与分层不一致） | 提到模块顶部 |
| **rf-886** | 审计误判：把 `core/costs.add_cost_bucket` 判为「死代码」（只 grep 了 `src/`，漏掉 `scripts/_perf_history` 两处调用），删除后 dev-verify 才暴露 | 已恢复并补 docstring 调用方说明（core / llm / scripts 三方共用）；教训：死代码判定必须扫全仓（含 `scripts/`），且以门禁实跑兜底 |
| **rf-887** | 重算原因（forced/fingerprint_changed/ttl_expired/cache_miss）以字符串字面量散落在预检与骨架两条路径，新增的 `RECOMPUTE_REASONS` 取值域无人使用 | 两处改引用 `observation.RECOMPUTE_*` 常量；`note_recompute_reason` 对域外值告警一次（仍计数，避免静默多出无人认识的统计桶）；回归 3 例 |
| **rf-888** | `_llm_providers_defaults._PROVIDER_NOTES` 与默认线路未配对时静默无注释（新增线路漏写说明不会被发现） | 补对齐回归 2 例：每条默认线路必须有非空说明 + 模板可被注释剥离器解析且订阅制线路保留 `pacing` |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-25）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x 开发期已修复批次
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x 开发期已修复批次
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x 开发期已修复批次
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x 开发期已修复批次
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x 开发期已修复批次
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x 开发期已修复批次
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本记录
