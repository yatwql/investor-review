# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.8]**（2026-10-23）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.9-dev] - 开发中（未发布）

### Changed

- **配置系统重构第 8 轮：TUI 菜单与分层**：主菜单收敛为 **14 项**（生成 E/B/L/W · 数据 Q/1/2/3 · 配置 P/S/G/R · 诊断 D · 退出 X），顶层 M/I/A/V/H/T 全部下沉；新增 `[G] 全局设置` 七项（D/F/O/L/I/A/M，数字为主入口、字母为别名）与 `[D] 诊断与排查` 四级（L 日志设置 / V 运行日志 / H 健康历史 / T 系统自检，缺省选中 T，`0` 返回主菜单）；`[D]→[L]` 日志设置六项（级别/轮转/查看器，越界拒绝）。`[G]→L` 调优面板补第 7 项「多链线路优先级」。菜单标签统一收敛到 ≤48 显示宽；`_CONFIG_ENTRY_MAP`、目录信息子菜单返回文案同步新层级。文档同批更新 `how-to-start.md`/`how-to-use-tui-menu.md` 菜单块与章节层级、`requirements.md` §3.2、`how-to-config.md` 路由、`datasource-reliability.md`/`how-to-config-llm.md`/`how-to-use-cli-mode.md`/`scripts-reference.md`/`technical.md` 菜单键引用与 `folders.md` 目录树。回归 13 例：菜单 14 项与分组序、标签宽度、[G]/[D] 路由/双通道/返回语义、日志设置写入与非法拒绝。
- **配置系统重构第 7 轮：日志配置独立成 logger.json**：新增 `data/config/logger.json`（`version=1` + `file`/`console`/`viewer`）与 `config/_logging.py`（读取/校验/写入，加载与面板共用范围表；写回文本 patch 保注释）；`core/logger.py` 启动时内联读取（不导入 config 包），按配置创建控制台/轮转文件 handler（路径、级别、maxBytes、backupCount、颜色），`INVEST_LOG_FILE_LEVEL` / `INVEST_LOG_CONSOLE_LEVEL` 环境变量优先级更高；日志目录不可写时告警并降级为仅控制台。非法级别/越界数值/含 `..` 路径：加载告警回落默认、保存拒绝且不落盘；`version` 不符拒绝并提示重新生成。同批更新 `how-to-config.md` §S、`requirements.md` §11.1.2、`technical.md` 配置矩阵、`developer-guide.md` 环境变量说明与 `folders.md` 目录树。回归 16 例：默认生成/加载回落/保存拒绝/环境变量优先/轮转参数/不可写降级/颜色关闭。
- **配置系统重构第 6 轮：计价参考独立成文件**：新增 `data/config/llm_pricing_ref.json`（`version=1` + 策略 + `models` 逐模型覆盖）与 `config/_llm_pricing.py`（读取/校验/逐模型合并/mtime 缓存/默认生成器，含中文注释模板）；`llm/pricing.py::reload_pricing()` 数据源切换为该文件，`PRICING_MERGED` / `reload_pricing` 接口不变。合并口径：内置 `MODEL_PRICING` 为基础价，文件只覆盖出现的模型与字段；文件缺失 → 仅内置价；单条非法 → 告警跳过；`version` 不符 → 拒绝加载并提示重新生成（内置价兜底，报告仍可生成）。`pricing` 从 `llm_settings.json` 移除（混入按未知键告警），仓库内 `data/config/llm_settings.json` 已重建为 v2。同批更新 `how-to-config-llm.md` 覆盖方式、`requirements.md` §11.1.1、`technical.md` 配置矩阵与 `folders.md` 目录树。回归 10 例：缺失回退/部分覆盖/非法跳过/策略回落/版本拒绝/计费等价（浮点容差）。
- **配置系统重构第 5 轮：生成参数入指纹**：`llm/module_fingerprint.py` 新增 `generation_params_suffix(module)`，把模块的温度 / 输出上限 / 思考开关、预算与强度统一并入指纹；`cache`、并发、重试等与生成无关的项不参与（避免无谓失效）。七个构造器（global_macro / expert_review / health_check / penetration_deep / self_review / debate_procon / debate_synthesis）全部接入；辩论综合另并入 `debate.procon.synthesis_temperature`。预检侧与写侧继续共用同一构造器，同源由结构保证；`get_llm_config()` 不可用时后缀为空，存量缓存不整体失效。同批更新 `technical.md` 指纹说明与 `folders.md` 目录树。回归 15 例（参数变化换键 / 无关项不变 / 两次调用一致 / 配置不可用保持原键）。
- **配置系统重构第 4 轮：LLM 参数校验**：`config/_validation_llm.py` 新增 `LLM_PARAM_RANGES`（temperature 0–2 / max_tokens 1–200000 / timeout 5–600 / thinking.budget 1024–100000 / effort 枚举 / 辩论合成温度 0–2 / 辩论单报告预算 1024–500000 / 辩论单次超时 5–600）与 `param_violation()`（文案含键名/当前值/合法范围）。加载路径经 `sanitize_document()` 越界回落出厂默认并逐条告警（只改内存视图、不改写用户文件）；面板写入统一拒绝（`edit_ops` 数值越界文案改为「取值 X 超出范围 [min, max]」），非法值不落盘。同批更新 `how-to-config-llm.md` 参数合法范围表、`requirements.md` §11 引言、`technical.md` 校验说明与 `folders.md` 目录树。回归 17 例：八参数合法/越界/类型错误表驱动、加载回落与不改写文件、面板拒绝与写后原值。
- **配置系统重构第 3 轮：LLM 配置 v2 结构与默认生成器**：`llm_settings.json` 落盘改为 schema v2 嵌套结构（`defaults` / `modules` / `runtime` / `advanced`），新增 `config/_llm_schema.py` 负责版本校验（缺失或 ≠2 拒绝加载并提示删除重生成）、三层缺省合并（模块值 → `defaults` → 内置默认）、`flatten()` 展平与 `apply_flat_updates()` 反展平、未知段/键保留，以及写回用的 v2 文本 patch（保注释）。对外契约仍为扁平键（`model_*` / `thinking_*` / `enabled_llm` / `llm_max_*` / `debate` / `fact_check` / `pricing`），`llm/` 包零改动。`_llm_settings_defaults.py` 生成器改为输出 v2 JSONC（分类注释 + 逐项中文说明），扁平默认值 `_DEFAULT_LLM_SETTINGS` 由 v2 展开派生；`write_llm_settings()` 接受扁平更新、反展平后写盘（值变化走文本 patch 保注释，结构变化才重排）；`read_llm_settings_file()` 返回展平视图。`DataModuleDef.llm_settings_keys()` 取消 news_correlation 的 output_brief 例外（v2 参数面对所有模块统一）。同批更新 `how-to-config-llm.md` 结构参考、`requirements.md` §11 引言、`technical.md` 解析矩阵与 `folders.md` 目录树。回归 17 例：生成器与扁平默认互展、版本拒绝（含文件名与重生成指引）、三层优先级矩阵、展平契约键、未知段/键保留。
- **配置系统重构第 2 轮：注释契约**：新增叶子模块 `core/json_comments.py`（`strip_json_comments` / `loads` / `load`，仅标准库），`config/_comments.py` 改为再导出——`core/logger.py`、计价等 core 级读取方不必导入 `config` 包（依赖不成环）。`features.json` 读取改经统一剥离器；写入改为**键级文本 patch**（改值替换、恢复默认删键、紧凑单行自动重排），读—改—写后分类注释与逐项说明保留；文件缺失时首次写入以中文说明模板（`_FEATURES_TEMPLATE`）为底。同批更新 `technical.md` 配置解析矩阵/注释段、`requirements.md` §11 引言、`how-to-config.md` 注释说明与 `folders.md` 目录树。回归 18 例：注释剥离（字符串内 `//`、`/* */` 与转义引号不误伤）、五份配置文件注释样本读取、features round-trip（保存/恢复默认/模板生成/紧凑重排）、叶子模块导入边界（不拉入 config）与 `core/logger.py` 无 config 导入。
- **配置系统重构第 1 轮：注册表与域模型**：功能开关从「四组作用域」改为**八组内容位置**（持仓与交易 4 / 市场与估值 4 / 基金与风格 3 / 事件与摘要 4 / 呈现与交互 2 / 机制与质量 3 / 独立章节与回放 4 / 章节内选项 2，共 26 项），新增 `GROUP_DOMAIN`（组→五域）、`DOMAIN_ORDER`/`DOMAIN_LABELS`/`DOMAIN_HINTS`（Web 五域编排与提示）、`PANEL_GROUPS`（`[S]` 六内容组 / `[P]` 独立章＋章节选项）与 `FeatureSwitchDef.needs_hint`；`crisis_replay` 归市场与估值、`prosperity_framework` 归市场与估值、`report_qa` 归呈现与交互、辩论两项归 `chapter_options`（由 `[P]` 作章节子项渲染，不占 `[S]` 编号）。**系统自检转恒上屏**：移除 `doctor_check` 开关（TUI `[T]`、Web 自检卡与 `GET /api/doctor` 恒可用，`doctor` 子命令不变），`FEATURE_GATED_ITEMS` 只保留 `Q → report_qa`。同批同步 `how-to-config.md` 开关表与面板归属表、`how-to-use-tui-menu.md` 的 `[S]` 编号表（8-33）与键名映射、`requirements.md` §11.5/§3.6、`technical.md` 注册表与自检段、`developer-guide.md` 分组表、`scripts-reference.md`/`testplan.md` 描述。回归：注册表不变式/门控用例按 `GROUP_DOMAIN` 与八组重写。
- **`plan-182`（决策不做）迁入归档 + `plan.md` 收敛为最新状态**：`release.py` 的「已完成任务节」识别口径扩到 `❌ 决策不做`（与 ✅ 同为「不再在办」，标记保留以区分做完/不做），plan-182 按机械规则迁入 `archived_plan.0.14.x.md`（标题降为二级）；`plan.md` 去掉流转叙述（「均已实施」「已落地」「已由」一类），plan-185 与 plan-70 的现状改写为可直接执行的态与判据（含 plan-185 实测验收数据），归档索引的 0.14.x 覆盖区间校正为实际日期。回归 2 例（决策不做节被收集 / 「当前迭代」不计入该节）。
- **TUI 追问的报告选择默认项改为本期主报告**：候选列表按「档位优先 + 修改时间倒序」排序——`个人投资分析报告.html` 恒为第 1 项（回车默认），其它报告居中，`调仓模拟.html` 排末档；首项标注「← 回车默认」使默认目标可见，提示语同步为「回车=本期主报告」。根因：调仓模拟每跑一次即覆盖自己的固定名产物、把 mtime 顶到最新，纯按时间排序会把回车默认项落到模拟报告上（同目录并列产物，但语义上属少数派）。同批把 `调仓模拟.xlsx/.html` 与归档名前缀收敛为 `core/constants` 常量（`WHATIF_FILE_BASE` / `LATEST_WHATIF_*`），写入器不再写字面量。


（本次发布内容见下方归档索引）

## 归档

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
