# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.14.9-dev
> **编号源**：`rf-next = 839`（新增问题取此编号，完成后更新为 +1；已用最大 rf-838，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 **4 类人工项**：真实 basic/full 进度观察（3.1c / 3.2 / 3.3 / 3.4）、结果区按钮（4.5）、提交即禁用（5.3）、真实拖拽与 Tab / Enter 抽验（2.5 / 2.6）；其余项已由自动化用例覆盖 | 判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（启动 / 收尾命令 + 复验清单）；复跑 `.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全部通过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

当前无待办项。

### P3 — 持续监控：文件膨胀登记

> **单一事实源**：行数、登记线与拆分优先级以 `scripts/check-file-length.py -v` 为准（主程序警告 >700 / 红线 >1000；`scripts/` >600 / >1000；测试 >900 / >1200，且 >80 用例告警；`__init__.py` 薄壳 >200）。口径与理由见 `technical.md` C28。
> **入表规则**：达到警告线即登记在此表（登记线 = 警告线，不另立数字），行数快照随复核刷新；破线豁免当前为 0。

**当前无登记项**——三域均在登记线以下，新增文件触线时按上述口径登记。

## 已解决问题

### 开发期已修复（随发布归档）

| # | 问题 | 修复 |
|---|------|------|
| **rf-838** | `test_json_comments` 的叶子模块边界用例用 `subprocess.run(text=True)` 未指定编码——`PYTHONWARNDEFAULTENCODING=1` 下直接告警为错误（`error::EncodingWarning`），`LC_ALL=C` 等非 UTF-8 locale 还会按 cp936/latin-1 解码子进程输出 | 显式 `encoding="utf-8"` + `errors="replace"`；由 portability 隐式编码严格档拦截，无需新增用例 |
| **rf-836** | 事实校验自动修正器产出用户可见畸形数值（`持仓收益率+-9.0%`）：把占比当收益率改写、同句多代码主体归属错、替换不处理原符号 | 三条同修：① 数值前文语义（占比/最大持仓/份额/市值/仓位等局部窗口）→ 不参与收益率修正；② 主体归属改为括号 > 分句 > 全句三级作用域；③ 替换时剥除原符号（新值符号优先，正值且原文有 `+` 时延续）并按 `[+-]{2,}` 做畸形自检，命中整批不写回。回归用例 6 例（`TestNonReturnMetricAndSignNormalization`） |
| **rf-837** | 计价模块懒加载标志与显式重载不一致：显式 `reload_pricing()` 后 `_PRICING_LOADED` 仍为 False，进程内首次计费会再读一次配置文件并覆盖已装载的定价（用例单独执行失败、整文件通过） | `reload_pricing()` 在 `finally` 置 `_PRICING_LOADED = True`；新增回归用例 `test_explicit_reload_is_not_undone_by_lazy_init`（断言显式重载后计费直接使用已装载的定价） |

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
