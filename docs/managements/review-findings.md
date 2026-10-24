# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.15.2
> **编号源**：`rf-next = 867`（新增问题取此编号，完成后更新为 +1；已用最大 rf-866，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 **4 类人工项**：真实 basic/full 进度观察（3.1c / 3.2 / 3.3 / 3.4）、结果区按钮（4.5）、提交即禁用（5.3）、真实拖拽与 Tab / Enter 抽验（2.5 / 2.6） | 判定标准见 [`../archive/v0.15.x/web-browser-verification/web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)（启动 / 收尾命令 + 复验清单）；复跑 `.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全部通过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定，且不与在办功能争抢同一批文件。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-864** | **手机窄终端报告收尾按 `y` 未打开新目录**：报告结束后提示「是否打开报告目录与报告？(y/N)」，按 `y` 未启动文件管理器/打开报告目录，而是直接回到主界面；疑似键读取未命中、`sys.stdin.isatty()` 在移动终端为假、或 `open_artifacts` 平台分派失败且窄屏未显示失败反馈 | 复现并逐层定位：① `_ask_open` 的 `get_key` 实际返回（`y/Y`、`y\r`、Esc、回车）；② `prompt_open_artifacts` 的 `isatty` 分支；③ `open_artifacts` 在 Android/Termux/远程移动终端的平台分派与失败提示。补 mock 回归：`y/Y` 必须调用 opener（目录 + 产物）、`n/回车/Esc` 不调用、非 TTY 只列清单、opener 失败必须上屏 `[!]` 提示；真机复验 Termux/手机浏览器终端 |


### P3 — 持续监控：文件膨胀登记

> **单一事实源**：行数、登记线与拆分优先级以 `scripts/check-file-length.py -v` 为准（主程序警告 >700 / 红线 >1000；`scripts/` >600 / >1000；测试 >900 / >1200，且 >80 用例告警；`__init__.py` 薄壳 >200）。口径与理由见 `technical.md` C28。
> **入表规则**：达到警告线即登记在此表（登记线 = 警告线，不另立数字），行数快照随复核刷新；破线豁免当前为 0。

**当前无登记项**——三域均在登记线以下，新增文件触线时按上述口径登记。

## 已解决问题

当前无已解决待归档项。

### 归档档案
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-24）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) 
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md)
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md)
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md)
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md)
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md)
