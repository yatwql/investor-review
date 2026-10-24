# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.15.1-dev
> **编号源**：`rf-next = 844`（新增问题取此编号，完成后更新为 +1；已用最大 rf-843，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 **4 类人工项**：真实 basic/full 进度观察（3.1c / 3.2 / 3.3 / 3.4）、结果区按钮（4.5）、提交即禁用（5.3）、真实拖拽与 Tab / Enter 抽验（2.5 / 2.6）；其余项已由自动化用例覆盖 | 判定标准见 [`../archive/v0.15.x/web-browser-verification/web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)（启动 / 收尾命令 + 复验清单）；复跑 `.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全部通过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定，且不与在办功能争抢同一批文件。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-839** | `llm/fact_checker/_numerical.py::_evaluate_percent_value` **参数蔓延**：单函数 22 个参数（7 个基础值 + 10 个「语境开关」布尔 + 5 个数据映射），一次调用要传 22 个实参；新增一种语境（如本轮的「数值前文非收益率度量」）就得同时改签名、改文档串、改唯一调用点与所有直接调用它的用例。语境开关之间还有隐式顺序（先变化率/胜率等非收益率早退，再回撤，再收益语境），顺序只能靠读函数体推断，参数列表本身不表达约束 | 收进一个上下文对象（如 `PercentContext` dataclass：数值三元组 + 持仓映射 + 派生语境开关），函数签名收敛为 `_evaluate_percent_value(ctx)`；语境开关的判定顺序在构造侧单源声明（按「非收益率早退 → 回撤 → 收益」的优先级显式排序），避免顺序知识散落在函数体。<br>**前置**：先补一张「语境词 → 期望结果」对照表测试（现有 30+ 用例散在 5 个测试文件），把该表作为两种实现等价的判定依据、达标后再动签名；`_evaluate_percent_value` 的唯一生产调用点在 `check_numerical_consistency`，回归面可圈定 |

### P3 — 持续监控：文件膨胀登记

> **单一事实源**：行数、登记线与拆分优先级以 `scripts/check-file-length.py -v` 为准（主程序警告 >700 / 红线 >1000；`scripts/` >600 / >1000；测试 >900 / >1200，且 >80 用例告警；`__init__.py` 薄壳 >200）。口径与理由见 `technical.md` C28。
> **入表规则**：达到警告线即登记在此表（登记线 = 警告线，不另立数字），行数快照随复核刷新；破线豁免当前为 0。

**当前无登记项**——三域均在登记线以下，新增文件触线时按上述口径登记。

## 已解决问题

### 开发期已修复（0.15.1-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-843** | Web 配置面板的块标题回退成内部块 id：`renderBoolBlock` 用 `labels[blockKey]` 取标题，而 labels 只登记可编辑键；`sections` / `llm` 等块在面板上直接显示英文 id（中文块标题只有 `features.*` 组与少数写死项）。同批发现 `renderTuningGroup` 签名与块标题取源不一致（引用未定义 `surface`）导致整面板渲染失败 | 块标题改为**服务端随面下发**（`block_titles`，单一来源），前端一律取服务端下发的标题（不回退到 id、不写死中文）；`renderTuningGroup` / `renderAnonGroup` 改为接收 `surface`；契约测试补「每块都有中文标题且标题≠块 id」 |

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
