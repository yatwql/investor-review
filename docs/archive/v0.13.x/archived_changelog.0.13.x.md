# 变更日志归档 — v0.13.x

> 归档时间：2026-10-13（v0.13.0 发布当日并入，0.13 系列首份）
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.13.0（2026-10-13）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.13.0] - 2026-10-13

### Fixed

- 智囊团深度复盘：结构化决策头机器载荷（`决策头：{...}` 单行 JSON）不再直出 HTML 报告正文与 Excel「智囊团深度复盘」页签——报告装配点在决策登记完成后对 LLM 内容四元组单点剥离（`strip_structured_header`，与解析侧共用标记常量与括号配对扫描），缓存保留原始内容；补正常形态/畸形矩阵单测与装配接线测试。

- 报告图表图注（图注纪律）：corrRollingChart 补 `.chart-caption` 图注；新增 `.note-caption` 类承载表格/统计口径说明附注（与图注同视觉档位、语义分离），回撤区 4 处误用图注类名的说明块改用——`.chart-caption` 现专属图表，由结构契约测试全量机检。
- 东方财富行业/概念接口（push2）：请求前节流从自建随机 sleep 迁移为 `RateLimiter` 原语（登记键 + 最小间隔 0.1s + 抖动 0.5，惰性单例 + 测试隔离 reset），节流算式纳入 C27 单源纪律，与 cninfo/datasink/eastmoney 分页同模式。
- 新闻抓取预算：`per_source = max(500, top_n×2)` 折算收敛为 `fetcher/news.py::news_fetch_limits` 单源函数（抓取预算单源纪律），缓存层与报告层两处内联计算收编，调用方不再各自复制算式。
- 调仓 What-if 回测窗口：`compute_backtest_days` 的自然日×5/7 近似折算替换为交易日历精确计数（交易日历单源 `count_trading_days_elapsed`，日历不可用时内部回退排除周六日），长假前后的窗口请求天数不再偏差。
- 代码形态判定：A 股六位代码/美股字母代码判定收敛为 `core/code_utils` 语义原语（`is_six_digit_code` / `is_letter_based_code`），配置校验、天天基金申购、因子指标、组合历史、费用估算五处内联判定收编（代码形态判定中心化）。

### Changed

- 发布门禁扩展：`release.py gate`（P2）在十守护之后追加 `check-style-guardrails --ci` 设计护栏段（E 级 finding 拦截 / W 级观察统计随发布留档）——开发期快反馈仍由 unit 测试承担，护栏不入十守护清单与 pre-commit/CI guards；gate 测试补护栏调用与失败传播 2 例。
- 样式护栏观察项治理（`plan-121`）：`check-style-guardrails.py` 裸色值 132→0、圆角档外 8→0——修 HTML 数字实体误报（`&#9888;` 等）、豁免域精确化（引号区间行 / var 回退 / print 块 / 暗色 override 块，与契约护栏例外同源）、存量白名单 15 条带理由登记；模板等值收敛（徽章 10px→999 胶囊档、source-tag 3px→4px、whatif hover→var(--table-hover)）；W 级管控三定档（永不自动转阻塞/白名单只减不增/收敛优先于豁免）+ 观察数基线断言机制化（`TestBaselineNoGrowth`）。

- 技术设计文档：架构约束表增「env 初始化期注册」例外脚注（`html_jinja_env.py` 无状态过滤器注册与 fail-closed 默认值合法，渲染期数据仍禁入全局）；新闻抓取预算/交易日历约束行补单源指引与 whatif 回测接入点；`schemas/history.py` 模块 docstring 修正为数据契约职责（原子写入由 `report/history_snapshot.py::save` 经 `core/atomic_write` 承担）。
- 自审挂账：style 护栏观察项（裸色值/圆角档位外，E 级不判 finding）纳入 `plan-121` 治理——退出判据为观察期（≥2 个发布版本）观察数不再增长 + 存量收敛计划或逐条白名单。

## [0.13.1] - 2026-10-14

### Added

- 报告「投资分析汇总」市场温度行下新增**计算逻辑**与**分级标准**两行说明（低估＜30 分 / 合理 30~70 分 / 高估＞70 分，边界值归合理档；三因子权重 50%/30%/20%，波动率反向越波动越冷）——文案由计算层权重/阈值常量单源派生，改常量自动跟随；展示构建器缺字段时两行静默省略（旧契约兼容）。

### Changed

- 脚本目录优化批次：`release.py` 拆 `_release/` 内部实现包（共享原语/版本号纯函数/changelog 归档/演进快照四模块，入口保留 CLI 与命令壳，869→517 行）；文档路径常量上收 `_checklib`（5 检查脚本与 doc-drift 内部包的内联拼路径收编）；`check-script-contract` 规则② 增加 `args.verbose` 消费侧 AST 检查（防空开关，`check-svg.py` 的空 -v 同步实现消费）；三守护同次运行双扫消除（doc-traces 四遍目录走查收敛为一遍 / doc-drift `-v` 模式二次全量读复用首轮 / semantic-index 指纹面与扫描面同源）；演进统计对测试文件的全量二次读消除；三个 sh 启动垫片加 `set -euo pipefail`。
