# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.8-dev
> **编号源**：`rf-next = 836`（新增问题取此编号，完成后更新为 +1；已用最大 rf-835，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）
> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余项已由自动化用例覆盖 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 当前无待办项。

### P3 — 持续监控：文件膨胀登记（按任务号组织；登记线 = 警告线：主程序 >700 / 脚本 >600 / 测试 >900 / 薄壳 >200）

> **单一事实源**：行数与优先级以 `scripts/check-file-length.py -v` 输出为真值（清单 = 主程序 >700 / 脚本 >600 / 测试 >900、薄壳 >200，并按「行数 × 近 90 天改动次数」给出拆分优先级）。本表是**逼近红线档的处置登记**，**入表线 = 警告线**（单一口径：警告即登记，不另立数字），行数快照随复核刷新。
> **红线体系**：主程序警告 >700 / 硬上限 >1000；`scripts/` 警告 >600 / 红线 >1000；测试 >900 警告 / >1200 红线；`__init__.py` 薄壳 >200 警告（同域红线）。体系口径与理由见 `docs/managements/technical.md` C28（大文件红线体系）。
> **测试文件口径**：行数 >900 警告 / >1200 红线；测试项 >80 警告 / >120 红线；≥900 行即入本表。
> **破线豁免**：无（`check-file-length.py --ci` 豁免在列 0 项）。

**当前无登记项**——`check-file-length.py -v` 的可选优化清单为空，三域均在登记线以下；新增文件触线时按上表口径登记，行数以 `-v` 输出为准。

## 已解决问题

### 归档档案
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
