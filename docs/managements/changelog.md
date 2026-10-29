# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.10]**（2026-10-29）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.11-dev] - 开发中（未发布）

### 新增

- 持仓录入（TUI）：首页新增「持仓维护」组 `[U] 持仓录入（买入 / 卖出 / 保存）`，二级菜单编号为主入口、字母为别名（`1`/`L` 查看持仓、`2`/`P` 录入买入、`3`/`S` 录入卖出、`4`/`W` 保存到持仓文件、`5`/`U` 撤销上一笔、`0` 返回）。录入只进内存变更清单（不动文件），保存回显本次全部变更并确认后原子写回持仓文件（写前校验文件未被其他程序改动、留 `.bak`，可选记入交易流水页签）。查看持仓时本次未保存的行行首标红 `*`（账户标题同标、底部给图例），已落盘的行不标。
- 买入按份额加权平均成本、卖出保留原每份成本并校验超卖；场内必填成交价（回车可取当前行情），场外按交易日取官方净值并回显实际净值日期。
- 录入期校验：`00` 重叠区先按行情源反推场内/场外、仍不确定再问一次（避免场外基金被当股票要求录成交价）；价格与参考价偏离 > 20% 需确认（防小数点位错）；与本次已录笔完全相同的重复提交需确认。写盘后回读文件逐行核对份额/成本，不一致即报错并保留变更。
- 二级菜单含 `5`/`U` 撤销上一笔（以文件为基线重放剩余变更）；退出面板有未保存变更时为三选一（保存后退出 / 丢弃退出 / 继续编辑，默认继续编辑）。
- 场外买入区分「按金额 / 按份额」：交易日当天只允许按金额（份额 = 金额 / 当日官方净值），当日净值未公布时本笔不成立并提示净值公布后再录，不使用估算净值写入持仓文件。
- 新增模块 `core/holdings_editor.py`（读→内存变更清单→原子写回单源，含写后回读校验与撤销重放）、`fetcher/nav_lookup.py`（交易日→官方净值、金额→份额）、`tui/handlers_holdings.py`（录入面板）；新增需求 R-HLD-06~13 与对应需求追溯映射。

### 文档

- 管理文档同步：`requirements.md`（§3.2 菜单表新增「持仓维护」组 + R-HLD-06~13，R-HLD-06 键位按最终编号/字母表述）、`testplan.md`（新增三条需求追溯映射）、`technical.md`（功能语义命名表新增 `holdings_editor` / `price_kind` / `nav_lookup` / `resolve_nav_on_trade_date` / `resolve_purchase_shares` / `ambiguous_price_kind` / `price_kind_from_quote` / `revert_last`）、`folders.md`（新增 3 个源码 + 4 个测试 + 设计文件条目）、`test-coverage.md` 与统计行、`plan.md`（plan-238 / plan-239 仅留任务号与简述，设计细节归 `docs/plan/holdings-entry-design.md`）。
- 用户文档同步：`README.md`（主菜单四组 14 项 → 五组 15 项，补 `[U]` 说明）、`how-to-start.md` 与 `how-to-use-tui-menu.md` 主菜单块 + 「持仓录入类」详解（别名、未保存标记、撤销、三选一退出、三项录入期校验、保存后回读校验）、`how-to-use-web-mode.md`（在线改持仓当前仅 TUI，Web 走上传覆盖）、`faq.md`（新增 2 问：能否不手改 Excel 改持仓 / 改完为何报告仍是旧数据）。

### 修复

- 生成后自检输出上限默认 `max_tokens_self_review` 4608 → 8192（rf-970）：满编持仓下 4608 仍被截断触发自动重生成，同一份自检付两次 LLM 调用。
- 缓存未命中告警判据从「同前缀 ≥5 次」改为「同键 ≥3 次」（rf-971）：冷启动一批资产各取一次不再误报；负缓存/纠偏计数探测键（`_miss_`、`_correction_streak`）不进未命中分桶。
- 同花顺 provider 的「该源无此标的/能力」错误码（1002/3001/3002/3004）降为 INFO（rf-972）：中证 800 行业指数不再每轮刷十几条告警，其余业务错误仍按 WARNING。
- 读取持仓不再对「交易流水」「分红流水」页签刷「表头不匹配，跳过」告警（rf-969）：主表解析在解析前跳过已知流水页签名，流水页签仍由 `read_flow_sheets` 正常解析；未知页签的告警行为不变。
- 持仓录入入口键位从借用的字母 `T` 改为 `U`（rf-968）：`T` 原属 `[D]` 二级系统自检，借用需改动既有守卫；改用未占用的 `U` 后四处守卫原样保留、无需放宽。同时把主菜单「14 项」写死条数断言改为唯一性结构断言（良性新增不再误判回归），并同步 `requirements.md` 菜单表新增「持仓维护」组。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.10（2026-10-25 ~ 2026-10-29）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
