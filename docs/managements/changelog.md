# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.10]**（2026-10-29）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.11-dev] - 开发中（未发布）

### 新增

- TUI 长任务可观测与可中止：报告生成期末行常驻**状态条**（阶段 · 已耗时 · 预计剩余 · 中止键，单行原地刷新），阶段文案复用 `core.perf.format_stage_status` 三渠道同源；按 `q` 为**有序中止**——在下一阶段边界生效、回主菜单，已完成产物与缓存保留并提示「重跑只补缺失」（`core/cancel.py` 的 `CancelToken` + `StageCancelled`，`PerfCollector.start` 为唯一生效点，编排层复用既有中断收口）。键不可用时状态条降级提示 `Ctrl+C 中断`。
- TUI 长输出分页查看器：运行日志 / 数据源健康历史 / 系统自检超出一屏时进分页视图（`空格`·`↓`·`j` 下翻、`↑`·`k`·`b` 上翻、`g`/`G` 首末、`/` 搜索命中置顶并计数、`q`/`Esc`/`0` 退出）；不足一屏或非 TTY 整段直打且不读键，「按任意键」闸门由 5 处收敛为 2 处。新增 `tui/pager.py` 与 `text_layout.terminal_rows()`。
- TUI 可发现性：首页 `?` 键位速查（菜单键一览 + 分组索引 + 三条常用动线 + 首用未就绪详情）；`/` 筛选从主菜单扩到列表面板（`NavState` 可见集合协议，`[S]` 18 项与 `[M]` 线路表已接入，帧顶显示 `筛选「x」：N/M 项`，`0` 先清筛选）；`j`/`k` 与 `↑`/`↓` 同义；未登记键与未知键在全档统一为一行反馈。
- TUI 配置面板「可试可退」：`ConfigSession` 记录每个键的变更前值，`[S]` 面板 `u` 撤销上次、`U` 还原到进入面板时，页脚出现「本次改动 N 项」事实行；改动仍即时写盘（不做草稿态）。
- TUI 反馈闭环：错误行统一为「原因 → 下一步动作」（新增 `tui/action_hints.py` + `tui/error_tail.py`，短语与页头状态行同源，按终端宽度折行）；页头首用未就绪项折叠为一行（检测移出渲染路径并 TTL 记忆，详情进 `?`）。
- TUI 环境适配：`TUI_ASCII=1` 把装饰符号降级为 ASCII（一字符换一字符，**列宽按定义不变**，`tui/symbols.py`）、`TUI_PLAIN=1` 关闭原地重绘与状态条（整屏追加，便于日志抓取/朗读/录屏）。

- 持仓录入（TUI）：首页新增「持仓维护」组 `[U] 持仓录入（买入 / 卖出 / 保存）`，二级菜单编号为主入口、字母为别名（`1`/`L` 查看持仓、`2`/`P` 录入买入、`3`/`S` 录入卖出、`4`/`W` 保存到持仓文件、`5`/`U` 撤销上一笔、`0` 返回）。录入只进内存变更清单（不动文件），保存回显本次全部变更并确认后原子写回持仓文件（写前校验文件未被其他程序改动、留 `.bak`，可选记入交易流水页签）。查看持仓时本次未保存的行行首标红 `*`（账户标题同标、底部给图例），已落盘的行不标。
- 买入按份额加权平均成本、卖出保留原每份成本并校验超卖；场内必填成交价（回车可取当前行情），场外按交易日取官方净值并回显实际净值日期。
- 录入期校验：`00` 重叠区先按行情源反推场内/场外、仍不确定再问一次（避免场外基金被当股票要求录成交价）；价格与参考价偏离 > 20% 需确认（防小数点位错）；与本次已录笔完全相同的重复提交需确认。写盘后回读文件逐行核对份额/成本，不一致即报错并保留变更。
- 二级菜单含 `5`/`U` 撤销上一笔（以文件为基线重放剩余变更）；退出面板有未保存变更时为三选一（保存后退出 / 丢弃退出 / 继续编辑，默认继续编辑）。
- 场外买入区分「按金额 / 按份额」：交易日当天只允许按金额（份额 = 金额 / 当日官方净值），当日净值未公布时本笔不成立并提示净值公布后再录，不使用估算净值写入持仓文件。
- 新增模块 `core/holdings_editor.py`（读→内存变更清单→原子写回单源，含写后回读校验与撤销重放）、`fetcher/nav_lookup.py`（交易日→官方净值、金额→份额）、`tui/handlers_holdings.py`（录入面板）；新增需求 R-HLD-06~13 与对应需求追溯映射。

### 文档

- 管理文档同步（TUI 三批）：`DESIGN-TUI.md`（Keys 表补 `?`/`j k`/`u U`/分页键位块、Feedback 补长任务状态条与错误单源、新增「分页视图」节、Known Gaps 更新闸门处数与部分覆盖项）、`requirements.md`（R-TUI-05 扩写 + 新增 R-TUI-11~20）、`testplan.md`（追溯映射补 10 条 + 第 14/15 项补新机检与击键说明）、`technical.md`（语义命名表登记 `pager` / `live_status` / `symbols` / `error_tail` / `action_hints` / `first_run_notices` / `ConfigSession` / `apply_filter` / `cancel_token`）、`folders.md` 与 `test-coverage.md` 计数同步。
- 用户文档同步：`README.md`（五组菜单表述 + 状态条/中止/分页/筛选/退回/环境变量）、`how-to-use-tui-menu.md`（`j`/`k`、`?` 速查、长输出分页、面板内筛选、`u`/`U`、生成中状态条与 `q` 中止、`TUI_PLAIN`/`TUI_ASCII`）。
- 设计文档：新增 `docs/plan/tui-interaction-design.md`（议题稿，含 7 节迭代状态与决策结果）与三份批次实施方案（`tui-interaction-batch1-plan.md` / `batch2-plan.md` / `batch3-plan.md`）。

- 管理文档同步：`requirements.md`（§3.2 菜单表新增「持仓维护」组 + R-HLD-06~13，R-HLD-06 键位按最终编号/字母表述）、`testplan.md`（新增三条需求追溯映射）、`technical.md`（功能语义命名表新增 `holdings_editor` / `price_kind` / `nav_lookup` / `resolve_nav_on_trade_date` / `resolve_purchase_shares` / `ambiguous_price_kind` / `price_kind_from_quote` / `revert_last`）、`folders.md`（新增 3 个源码 + 4 个测试 + 设计文件条目）、`test-coverage.md` 与统计行、`plan.md`（plan-238 / plan-239 仅留任务号与简述，设计细节归 `docs/plan/holdings-entry-design.md`）。
- 用户文档同步：`README.md`（主菜单四组 14 项 → 五组 15 项，补 `[U]` 说明）、`how-to-start.md` 与 `how-to-use-tui-menu.md` 主菜单块 + 「持仓录入类」详解（别名、未保存标记、撤销、三选一退出、三项录入期校验、保存后回读校验）、`how-to-use-web-mode.md`（在线改持仓当前仅 TUI，Web 走上传覆盖）、`faq.md`（新增 2 问：能否不手改 Excel 改持仓 / 改完为何报告仍是旧数据）。

- Web 渠道持仓录入（`plan-239`）：新增「持仓录入」页签与 `GET /api/holdings`、`POST /api/holdings/preview`、`POST /api/holdings/save`；与 TUI `[U]` 共用 `core/holdings_editor` + `fetcher/nav_lookup`，支持账户/新代码/场内场外/份额或申购金额/价格留空取行情或净值；预览不落盘，写回走 mtime 闸门（409 `HOLDINGS_STALE`）+ `.bak` + 原子写 + 回读校验，可选记入交易流水。

- 演示截图流水线可重复执行：`demo` 工作区补 `src/` 软链（`PROJECT_ROOT` 搬到演示根后模板/静态资产仍可解析，报告 HTML 不再 `TemplateNotFound`）；`make-screenshots.py web --serve-demo` 自起演示服务（环境统一走 `isolation_env`，不再手工拼 env）；README 配图按虚构持仓重拍（TUI / Web 工作台·持仓录入·配置 / 报告首屏·汇总·图表 / CLI），新增 `web-holdings.png`。
- 截图/演示隔离补全（rf-973）：`PROJECT_ROOT` 支持 `INVEST_PROJECT_ROOT` 覆盖，演示工作区整体搬根（配置/持仓/产物同在演示目录）；`make-screenshots.py` 增加 `assert_demo_holdings()` 护栏，环境没带上即拒绝出图，杜绝真实持仓入图。

### 重构

- 持仓录入两日的技术债清理：① 主表表头判定（四列 + 跳过流水页签）上收为 `reader.match_holdings_header` / `reader.is_holdings_sheet` 公开单源，编辑层不再跨模块引私有 `_match_header`/`_EXPECTED_HEADER`，也不再自带一份重复判定；② 交易流水表头提为 `reader.TRADE_HEADER` 公开常量，写回侧不再复制字面量；③ 「按行情源反推品种形态」从 `core/holdings_editor` 下沉到 `fetcher/price.price_kind_from_quote`（`source_api` 属取数层内部标识，core 不解析 provider 名）；④ 三个测试文件各自的持仓 xlsx 构造器收敛为 `src/test/_holdings_fixture.py`（表头/账户/流水页签单源）；⑤ `list_xlsx_files` 的文件枚举加目录与 mtime 容错（并发删除不再抛错打断枚举）。

- 技术债清理：① 品种形态判定抽为 `core/holdings_editor.resolve_entry_kind` 单源（显式声明优先 / 歧义区统一抛错），TUI 与 Web 不再各写一份；② 测试持仓构造器复用 `reader.HOLDINGS_HEADER` / `TRADE_HEADER`（不再复制字面量）；③ Web 路由的请求体解析收敛为 `_json_payload()`（新增路由复用，非对象统一 400）；④ 补 `INVEST_PROJECT_ROOT` 覆盖回归 2 例（未设置回落仓库根 / 设置后持仓与产物随根切换）。

### 修复

- TUI 自查技术债：`KeyWatcher` 双实例导致 `q` 中止在真实终端不生效（保留的轮询器从未进入 cbreak）、状态条阶段文案与 `format_stage_status` 双源、配置会话在面板退出后仍存活（后续面板写盘记进旧会话）、分页器 `_start_rendered` 隐式属性；四项均补回归用例。

- 历史走势终点回填（消除「走势终值 vs 报告头市值」口径差）：`get_combined_timeseries` 新增 `latest_quotes`（由 `_snapshot.latest_quotes_from_detail_rows` 从持仓明细派生，无估值日不入表），某标的历史末条早于最新行情日时按最新价追加一条终点 bar——回填走副本不改会话缓存序列，as-if 份额语义不变。实测上轮残留的 1,608 元差异（011506 历史停在 10-27、实时已到 10-29）随之归零，末端日收益与回撤不再被低估。
- 终点滞后的双端呈现与日志去重：Excel「数据质量仪表盘」把源健康「历史走势」行转降级并列出滞后标的（`_apply_history_staleness`），品种覆盖行写「净值数据滞后 N 个交易日」——此前只有 HTML 数据状态有提示，Excel 仍写「✅ 正常 / 行情净值正常」，同一份报告双端说法相反；子块长窗（同一次运行的第二次全量计算）改传 `warn_on_terminal_staleness=False`，同一事实不再在日志里报两遍。
- 指数历史日线会话缓存复用补 INFO 标注（`[index] … 会话缓存复用（已有 N 根，请求 M 天）`）：此前基准归一化无论是否真取数都打「获取完成」，日志看起来像同一指数被取了 3 次。
- 历史走势终点口径校验（`history_data.terminal_staleness`）：LOCF 合并会把未刷新的标的沿用上次净值，此前只有「净值落后组合终点 ≥2 个交易日」时也静默混用不同日期的估值——实测某次报告走势终值 272,424.45 与报告头总市值 269,163.02 相差 3,261 元（1.2%），末端日收益与回撤同步偏低，而同数据重跑此前 10 次两者差额恰为 0。现在按「落后 ≥2 个交易日」判定（T-1 属常态不提示），命中即追加 `warnings`、写 WARNING 日志并给出滞后标的/滞后日/占比，同时在数据状态区渲染新增状态 `history_nav_stale`。
- 指数历史日线会话缓存复用判据补三条（`fetcher/index.py`）：记下的请求窗口 ≥ 需求、已存序列长度 ≥ 需求天数（日线是截至今日的连续序列，根数 ≥ 天数即覆盖窗口）、或已存序列达源单次上限（约 2000 根）。此前只比「请求窗口天数」，同一份报告内先用 90 天取过、再按 730 天/3650 天取会各重发一次请求（实测沪深300 一轮被取 3 次，且第二、三次拿到 2000/2002 根不同长度的序列，各面板口径可能不一致）。
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
