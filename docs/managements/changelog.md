# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.4]**（2026-10-27）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.5-dev] - 开发中（未发布）

### 修复

- **模块日志器名称统一**（日志统一约束：模块日志器名称）：`report/holding_change_panel.py`、`tui/status_line.py` 用 `getLogger(__name__)` 自取名称，日志落到另一棵 logger 树——`invest` 的 handler / 级别 / 格式与落盘全部不生效，这两个模块的诊断信息**静默丢失**（不进 `logs/app.log`）；改为 `getLogger("invest")`
- **LLM 缓存键写侧回归单源**（LLM 缓存键单源约束）：`llm/skeleton.py` 落盘路径自拼 `f"{cache_key}_{provider_name}"`，绕过唯一构造点 `_build_provider_cache_key`——写侧与预检侧任一侧改后缀格式即永久不等，表现为「开关/参数看似生效但每次仍全量调用 LLM」（费用与耗时翻倍、无异常难察觉）；改为调用共享构建函数
- **预检取数空链时的未绑定变量**：`llm/skeleton._resolve_first_provider` 在 provider 链为空时 `first_model` / `first_endpoint` 从未赋值，`return` 处抛 `UnboundLocalError` 只能由外层 `except Exception` 兑成「无预检」——真实异常与空链无法区分且 debug 日志被常态污染；三个返回值改为显式初值
- **TUI 首次使用指引指向错误入口**：持仓缺失提示原写「通过菜单 `[D]` 配置持仓目录/文件名」（`[D]` 是诊断与排查，无此入口），LLM 未配置提示原写「菜单 `[S]` 查看状态」（`[S]` 是章节内容呈现）——均改为实际路径 `[G]`（`[H]`/`[F]`）与 `[G] → [L]`，并补页头 `LLM ○` 状态说明
- **用户手册菜单路径与实现对齐**：`faq.md` 三处把 LLM 调优入口写成「主菜单 `[D]` → `[L]`」（实为 `[G]` → `[L]`，`[D]`→`[L]` 是日志设置）、把 `[T]` 系统自检说成「恒出现在主菜单中」（实为 `[D]` 的二级项）；`requirements.md` 的 R-DIAG-05 同步改写为「`[D]` 二级恒提供」；手册术语按上屏口径统一（「强刷」→「重新生成」、`Enter`→「回车」）
- **LLM 多链面板横幅缺结构色**：`handlers_llm_providers.py` 单线路分支的横幅裸 `truncate_display("── … ──")`，与同文件多线路分支不一致（一处有色一处无色），违反「结构色统一经 `style_heading` 产出」

### 变更

- **日志器名称纳入机检**：`check-code-traces.py` 日志统一支路新增 AST 判定「绑定到 `logger` / `_logger` 且名称非 `invest`」（第三方日志器静音与 `core/logger.py` 的构造链豁免），此前该守卫只查 `print()`，日志器名称长期无人守
- **测试标记合规检查收口两处空洞**：① 目录期望原为「至少命中其一」且期望集含通用 `unit`——任何只标 `unit` 的文件都能通过，域绑定形同虚设；改为「通用标记不计域归属，域标记必须命中其一」。② 标记提取只认 `pytestmark = [...]` 列表写法，`pytestmark = pytest.mark.x` 单值与元组写法被漏读；抽出 `_markers_from_value` 统一三种形态
- **手册菜单引用机检扩两条规则**（`check-doc-drift` 第 18 项域）：① **主菜单归属**——分句内把二级项说成在主菜单里即报（已声明「二级 / 不在 / 箭头路径」的分句豁免），上线即检出 `requirements.md` 的一处残留错误陈述；② **箭头路径合法性**——`[X] → [Y]` 要求 `X` 为 `[G]`/`[D]` 且 `Y` 属其二级项，杜绝把无二级项的键写成路径
- **`unit/handlers` 目录期望表修正**：原声明 `{unit, unit_core}` 与实况不符（TUI 处理层实际标 `unit_ui`），改为 `{unit, unit_core, unit_ui}`；`unit/web/test_cost_preflight_contract.py` 补 `unit_web`（原只标 `unit_llm`，`-m unit_web` 选不到它）

### 文档

- **统计口径与数字去写死**（`folders.md`）：文档总数分项由 `managements 12 / manuals 10 / plan 8 / archive 160` 校正为实测 `13 / 12 / 3 / 183`（合计 216 与统计表对齐），并删去写死的 pytest 收集项数（改指向 `test-coverage.md`「模式对应测试量」的 `all` 行）与 `README.md（211 行）`、`CLAUDE.md（89 行）`、`157 md 50,492 行` 等与受检列重复的过期数字
- **失效路径与错误陈述**（`CLAUDE.md` / `developer-guide.md` / `technical.md` / `docs/plan/`）：`scripts/_checklib.py` → `scripts/_shared/checklib.py`（3 处）；`technical.md` 更正「`_shared/traces_common.py` 已并入删除」（该文件仍在，由两个痕迹脚本共同 import）；集成契约「42 例 / 5.5s」改为「50+ 例 / ~5s」
- **`src/static/README.md` 结构归一**：单文件两个 H1 合并为一（后半降为 `##` 分组），清理 9 处任务代号（改为语义表述），`chart-init.js`「6 张图表初始化」校正为实测 12 张
- **菜单描述与实现对齐**（`README.md` / `how-to-use-tui-menu.md`）：`[Q]` 受功能开关控制、`[T]` 系统自检恒上屏（原 README 两处称 `[Q]`/`[T]` 均由开关控制且「在 `[S]` 里开启」）；`[D]` 二级项补 `L 日志设置`（原文漏写）；`/` 筛选示例由不存在的 `T` 改为 `Q` 并注明二级项不在筛选域；手册内「`[Q]` 与 `[T]` 同机制裁剪」与「`[T]` 恒上屏」的自相矛盾改正
- **手册新增「界面词与技术词对照」并试点术语本地化**：总索引新增 10 行对照表（降级→备用/失败标记、熔断→健康面板「失败 N」、退避→「等久一点才出结果」、强刷→`--force-llm` 强制重新生成、游标→行首 `>` 选中项、配置漂移→行尾 `*` 等），说明手册保留技术词但界面按右列说法；`datasource-reliability.md` §1 的失败路径流程追加「在界面上是什么样」五步对照（切换备用/熔断/退避/过期缓存/占位），把运维视角落回用户可见信号
- **TUI 手册补三端对照表**：新增「同一个操作在三端的位置」10 行表（生成报告 / 调仓模拟 / 章节显隐 / 章内开关 / 全局设置 / 缓存管理 / 系统自检 / 健康历史 / 运行日志 / 报告追问），与 Web 手册既有的「TUI 入口对照」形成双向；同时点明报告追问无 CLI 子命令
- **代码注释中的过期菜单引用**：`handlers_cache.py`「菜单 `[1][2][3][4]`」→ 实际 `[1]/[2]/[3]`；`status_line.py`「LLM 状态与 `[S]` 同源」→ `[G] → [L]`

- **超长配置手册拆篇**：`how-to-config.md` 979 → **426 行主篇**（目录 / 出厂 `config.json` 样例 / 字段总表 / D 市场时段与缓存 / N 功能开关 / 随版本更新）+ **`how-to-config-fields.md` 596 行详解**（A/B/C/E…S 逐节逐键，顺带改正 R 与 S 的错序）；`how-to-config-llm.md` 1138 → **746 行主篇** + **`how-to-config-llm-reference.md` 414 行参考**（逐家 provider 配置示例、完整模型定价表）。主篇保留「照抄改值」入口，详解篇承担「这项到底管什么」
- **拆篇后机检不断档**：`check-doc-drift` 配置默认值支路改为**双文件扫描**（B/C/E/G/M 节的默认值行随内容迁入详解篇，仍逐行对账，未静默丢 34 行覆盖）；目录树补两文件、总索引补两条；`faq`/`developer-guide`/TUI 手册中 4 处指向已迁移锚点的引用改指新文件
- **新增「错误信息索引」附录**（`faq.md`）：三渠道共用的 7 类提示（取自 `core/error_hints.py` 单一映射）、Web 的 15 个 `error_code`（含 HTTP 状态与处置）、CLI 四个退出码，整理成「按消息原文反查」表——此前只能按「我想……」进入，拿到报错无从下手。内容按代码调用点（`_err(...)`、退出码分支）逐条核对而非手写
- **界面用词对照表去重合并**：总索引原有两节（「界面用词对照」5 行、「界面词与技术词对照」10 行）语义重叠，合并为「界面用词与技术词对照」两层——界面上的词（含义/代价）+ 手册日志里的技术词（→ 界面说法），锚点与引用同步

### 测试

- 新增回归 13 例：日志器名称 8 例（检出 / 豁免 / 全仓基线自洽）、缓存键单源 3 例（写侧与预检侧同源结构断言 / 键一致 / 空链不走异常分支）、测试标记 4 例（单值与元组 `pytestmark` 提取 / 通用标记不足以满足域期望 / 真实测试树全域绑定）与 TUI 指引 2 例（持仓必须指向 `[G]`+`[H]`/`[F]`、LLM 必须指向 `[G]`+`[L]`，且不得出现旧键）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.4（2026-10-25 ~ 2026-10-27）
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
