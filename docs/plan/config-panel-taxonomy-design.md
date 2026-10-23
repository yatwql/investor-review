# 配置面板分类与描述重整设计

> **关联**：配置面板（Web「配置」页签 / TUI `[S]` 面板）的分类轴与文案来源；设计图样见 [`config-panel-mockup/index.html`](config-panel-mockup/index.html)（浏览器打开，可切换布局/说明密度/标记/主题四种视图）。
> **范围**：呈现层与注册表元数据——新增域轴、组顺序调整与第 5 组、Web 面契约、TUI 编号派生。**不含**新增配置键、改写入语义（`config/edit_ops.py` 的白名单/校验/`.bak` 备份全部不动）、改配置文件落盘格式。

---

## 1. 目标

1. **一级分区回答「我要改什么」**：面板按域分区，改一个意图不必跨区找。
2. **二级分组回答「开了长出什么」**：组表达作用域，与生命周期（`experimental`）正交不变。
3. **文案与顺序单源在服务端**：块的顺序、显示名、一句话说明、出厂默认值全部由后端下发，前端不含任何中文文案表。
4. **非开关项有明确归属**：报告章节、路径、指数池、线路、调优参数都进「域」，由声明表显式编排。

---

## 2. 模型：域 + 组 + 项

```
域 DOMAIN      —— 「我要改什么」：报告内容 / 呈现与机制 / 数据与线路 / LLM 运行
 └ 块 BLOCK    —— 一个可渲染单元：一个开关组，或一个非开关类面板
     └ 项 ITEM —— 单个可编辑项（开关 / 数字 / 文本 / 枚举 / 动作）
```

- **域** 常量在 `config/_feature_registry.py`：`DOMAIN_ORDER`、`DOMAIN_LABELS`、`DOMAIN_HINTS`、`GROUP_DOMAIN`。
- **组** 在 `_feature_registry.py`：`GROUP_ORDER`；组的域归属由 `GROUP_DOMAIN` 决定。
- **非开关类块**的域在 `web/config_edit.py::_BLOCK_DOMAIN` 声明，域内块顺序由 `_DAILY_BLOCKS` 声明；features 组按 `GROUP_ORDER` 追加到所属域（LLM 域的调优参数排在组之后）。

---

## 3. 域与组

### 3.1 四个域

| 域 | 键 | 上屏标题 | 域说明（`DOMAIN_HINTS`） | 域内块 |
|:--|:--|:--|:--|:--|
| 报告内容 | `report_content` | 报告内容 | 改这里会改变报告里出现什么：顶层章节取舍、章内附加块、整章回放 | `sections` → `features.analysis` → `features.standalone` |
| 呈现与机制 | `presentation_mechanism` | 呈现与机制 | 只改呈现口径、匿名化与内部机制/诊断接缝：内容主体不变或仅影响入口显隐 | `anonymization` → `features.presentation` → `features.mechanism` |
| 数据与线路 | `data_and_routes` | 数据与线路 | 数据从哪读、跟什么基准比、LLM 走哪条线路 | `paths` → `indices` → `providers` |
| LLM 运行 | `llm_run` | LLM 运行 | LLM 章节启停、调用内增强（辩论/情景）与运行参数（并发/重试/预算） | `llm` → `features.llm_enhance` → `tuning` |

`DOMAIN_ORDER` 即面板分区顺序。「报告章节」（`enable_*`）与「独立章节与回放」同域相邻——两者同属「报告里出现什么」；LLM 章节启停、调用内增强、运行参数同域相邻。

### 3.2 五个组

| 顺序 | 组键 | 上屏标题 | 域 | 项数 |
|:--|:--|:--|:--|--:|
| 1 | `analysis` | 🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表） | 报告内容 | 14 |
| 2 | `standalone` | 📑 独立章节与回放（默认关闭 · 新增整页签或多期回放） | 报告内容 | 5 |
| 3 | `presentation` | 📊 呈现与体验（默认开启 · 只改呈现不改内容） | 呈现与机制 | 1 |
| 4 | `mechanism` | ⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验） | 呈现与机制 | 5 |
| 5 | `llm_enhance` | 🧠 LLM 分析增强（默认关闭 · 在 LLM 章节内追加辩论/情景段，无独立章节） | LLM 运行 | 2 |

`GROUP_ORDER` 为「内容域 → 呈现与机制 → LLM 运行」的阅读顺序（机制收尾）。`llm_enhance` 收纳 `llm_debate_procon`（三段式白脸→黑脸→综合）与 `llm_debate_conditional`（情景化分析），二者在既有 LLM 调用内追加段落、不新增章节，故独立成组而不属「分析增强」的章内追加语义。

### 3.3 开关归属

| 组 | 开关 |
|:--|:--|
| `analysis` | `factor_catalog` / `event_window_impact` / `data_quality` / `industry_beta` / `candidate_compare` / `cost_lots` / `valuation_percentile` / `market_temperature` / `market_sentiment` / `fund_purchase_limit` / `cost_position` / `risk_adjusted_excess` / `summary_highlights` / `prosperity_framework` |
| `standalone` | `rebalance_schedule_replay` / `holding_change_review` / `whatif_trade_cost` / `stock_fundamentals` / `crisis_replay` |
| `presentation` | `metrics_enabled` |
| `mechanism` | `decision_reflection` / `report_qa` / `deterministic_signal` / `module_quality_gate` / `doctor_check` |
| `llm_enhance` | `llm_debate_procon` / `llm_debate_conditional` |

显示名、说明、默认值、产物影响、实验身份仍由 `FeatureSwitchDef` 六字段承载，注册表是唯一登记点。

---

## 4. Web 面板契约

`GET /api/config/edit` 在既有键之外增加编排与文案四块（既有键保持不变）。

### 4.1 编排：`domains`

```json
"domains": [
  {"key": "report_content", "title": "报告内容", "hint": "改这里会改变报告里出现什么…",
   "blocks": ["sections", "features.analysis", "features.standalone"]}
]
```

前端按顺序遍历 `domains` → `blocks`，按块 id 取渲染器：`features.<组键>` 查 `surface.features.groups`，其余查块渲染器表；渲染器返回 `null` 即跳过该块（多链线路为空时不渲染该块）。

### 4.2 文案：`labels` / `descriptions` / `defaults`

| 键空间 | 覆盖 | 来源 |
|:--|:--|:--|
| `labels` | 路径 3 项、报告章节 5 项、功能开关 27 项、`enabled_llm.<模块>` 7 项 | 路径/章节文案表 + 注册表 `label` + `get_llm_module_names()` |
| `descriptions` | 同上全覆盖（调优项不在其中：其说明随 `llm_tuning[].hint` 下发） | 路径/章节说明表 + 注册表 `desc` + LLM 章节说明模板 |
| `defaults` | **仅布尔与数值可编辑项**：功能开关 27 项、报告章节 5 项、`enabled_llm` 7 项、调优参数 6 项 | `FeatureSwitchDef.default` / 章节与模块默认 `true` / `LLM_TUNING_SPECS` 默认值；枚举项（匿名化）由 `anonymization.mode` 表达"当前选中"，动作项（指数池增删、线路调序）本就没有默认值，不下发 |
| `features.descriptions` / `features.defaults` / `features.needs_hint` | 27 项（组内渲染直接取，避免前端跨表拼键）；`needs_hint` 为「需显副行」的 flag 清单 | 注册表 |
| `anonymization.labels` | 4 档 | `anonymizer.ANONYMIZATION_MODE_DESCRIPTIONS` |
| `llm_providers.strategy_label` / `order_is_chain` | 4 种策略中文名 + 当前策略下顺序是否等于实际链序 | 策略中文表（`priority`→按优先级排序 / `weighted`→加权随机 / `cost_first`→价格最低优先 / `fallback_only`→仅回退） |

前端职责边界：不含任何中文标签、说明、块顺序表；`main.js` 只保留渲染器与「按 id 取渲染器」的分发。

### 4.3 标记口径

| 标记 | 判定 | 覆盖 |
|:--|:--|:--|
| 「影响报告」 | `affects_report` 为真；章节与 `enabled_llm` 模块按同一判据（关闭即整章隐藏） | 功能开关组 + 报告章节 5 项 + LLM 模块 7 项 |
| ⚗ | `experimental` 为真 | 功能开关组 |
| 说明副行 | `descriptions` 有值 | 全部组（密度见 4.4） |

**降噪规则**：「影响报告」标记会同时出现在 5 个章节、7 个 LLM 模块与功能开关组，为避免每行都挂着徽标——标记固定渲染在**行末同一列**（右对齐、不随标签长度漂移），组标题只保留分组语义、不重复"关闭即整章隐藏"的说明文字；只有 `affects_report` 为真的项才有标记，其余项该列留空。⚗ 与「已改」标记同处行尾区，顺序固定为 `⚗ › 影响报告 › 已改`。

### 4.4 说明密度

默认「仅非常识项显副行」：解释成本高的项（路径、LLM 调优参数、`factor_catalog`、`event_window_impact`、`deterministic_signal` 等）渲染 12px 副行说明；常识项（`metrics_enabled`、`doctor_check`、`module_quality_gate`、`data_quality`、`market_temperature`、`fund_purchase_limit` 等）说明存 `title`，悬停可读。

**"哪些算常识项"不下发给前端做字典**（否则又是第四份中文清单）：由注册表新增字段 `FeatureSwitchDef.needs_hint`（布尔，默认 `False` = 常识项不显副行，显式标注"需要副行"的项才显）承载，`features.needs_hint`（需要副行的 flag 清单）同源下发。路径/调优项固定显副行（项数少且解释成本高），不需要字段标记。切换为「全部显示」= 前端忽略该字段。

### 4.5 块 id ↔ 渲染器 ↔ 空数据行为

块 id 由服务端 `domains[].blocks` 给出，前端按 id 取渲染器；`features.<组键>` 单独走一组分支（查 `features.groups`）。**空数据不得渲染空壳标题**：

| 块 id | 渲染器 | 数据为空时 |
|:--|:--|:--|
| `paths` | `renderPathsGroup` | 不出现（配置读取失败时整个面板已走错误态） |
| `sections` | `renderBoolGroup` | 不出现 |
| `features.<组键>` | `renderBoolGroup`（数据取 `features.groups[i]`） | 组内 0 项则不出现 |
| `anonymization` | `renderAnonGroup` | 不出现 |
| `indices` | `renderIndicesGroup` | 不出现（保留"添加"入口则至少渲染表单） |
| `providers` | `renderProvidersGroup` | 不出现（多链线路为空时的既有行为） |
| `llm` | `renderBoolGroup`（`enabled_llm.*`） | 不出现 |
| `tuning` | `renderTuningGroup` | 不出现 |

### 4.6 「已改」标记：与 TUI 同源

TUI `[S]` 面板用行尾 `*` 标注"与出厂默认不一致"。Web 面板沿用同一语义与同一数据源（`defaults`），以行尾 `✻` 呈现，图例统一为「✻ 与出厂默认不同」。两侧都不新增判定逻辑——比较对象就是 `defaults`，因此 TUI 与 Web 的"已改"恒等。

### 4.7 样式规格（`style.css`，须含暗色配对）

| 元素 | 规格 | 取值 |
|:--|:--|:--|
| 域分区 | 相邻域之间 `border-top: 1px solid var(--border)` + 上间距 | `margin-top: 26px; padding-top: 22px` |
| 域标题 | 字阶「卡片/小节标题」档，字重 600，左侧品牌蓝竖线（单强调色） | `16px / 1.4`，`padding-left: 10px; border-left: 3px solid var(--primary)` |
| 域说明 | 脚注档，次要墨色 | `12px / 1.5`，`var(--text-secondary)`，`margin-left: 13px` |
| 项说明副行 | 脚注档，次要墨色，与勾选框文字左对齐 | `12px / 1.5`，`margin-left: 22px` |
| 「影响报告」标记 | 小徽标：1px 边框 + accent 色 | 亮色 `var(--accent)`；**暗色覆盖为 `#6ecf9f`**（`--accent` 在暗色面上对比不足，标记位单独取值） |

---

## 5. TUI `[S]` 面板编号

编号 = LLM 可见模块数（7）+ 按 `GROUP_ORDER` 连续派生，运行时由注册表计算，非硬编码：

| 区间 | 内容 | 项数 |
|:--|:--|--:|
| 1-7 | LLM 分析章节 | 7 |
| 8-21 | 分析增强·既有章内追加 | 14 |
| 22-26 | 独立章节与回放 | 5 |
| 27-27 | 呈现与体验 | 1 |
| 28-32 | 机制与诊断 | 5 |
| 33-34 | LLM 分析增强 | 2 |

编号由注册表派生（运行时计算，非硬编码）。**稳定入口是键名**：面板与手册始终并列展示键名，`?` 详情、`?编号` 查询、`键名=on|off` 赋值三条通道均以键名为准，编号仅作当前版本的快捷定位。

`?编号` 详情沿用注册表 `desc` / `GROUP_LABELS` / `default` 三源。手册 `[S]` 面板编号表、五个组块标题、features 键名→编号映射表按上表维护，`check-doc-drift` 第 8 项按注册表派生校验。

---

## 6. 影响面

### 6.1 代码

| 文件 | 改动 |
|:--|:--|
| `config/_feature_registry.py` | 5 个域常量 + `DOMAIN_ORDER/LABELS/HINTS` + `GROUP_DOMAIN`；新增 `GROUP_LLM` 并确定 `GROUP_ORDER` 为五组顺序；辩论两项归入该组；`FeatureSwitchDef` 新增 `needs_hint` 字段（说明密度判定） |
| `config/features.py` | 导入/导出面扩展（域常量 + `GROUP_DOMAIN`）；模块 docstring 分组说明 |
| `web/config_edit.py` | `_BLOCK_DOMAIN` / `_DAILY_BLOCKS` / 路径与章节文案表 / `_panel_domains` / `_panel_labels` / `_panel_descriptions` / `_panel_defaults`；`_llm_providers_surface` 增 `strategy_label`、`order_is_chain`；surface 增四块 |
| `static/web/main.js` | `renderConfigEdit` 按 `domains` 分区渲染；删除 `CONFIG_LABELS` / `ANON_LABELS`；`renderBoolGroup` 支持 `descriptions`/`defaults`/`fullKey` 查表；`renderPathsGroup` 用服务端文案；线路组用 `strategy_label` |
| `static/web/style.css` | §4.5 四个 class + 暗色配对 |
| `tui/*` | 无需改：面板渲染与编号派生已按 `GROUP_ORDER` / `GROUP_LABELS` 跟随 |

### 6.2 文档

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-use-tui-menu.md` | `[S]` 面板编号表 + 五个组块标题 + features 键名映射表 + 「五块」措辞（编号见本文件第 5 节） |
| `manuals/how-to-config.md` | 功能开关表（组内行序 + 新组两项迁入）；`[S]` 布局段与 Web 面板分组段的分组枚举 |
| `manuals/how-to-config-llm.md` | `[S]` 面板分块与显式编号区间（呈现/分析/独立/机制四段）；辩论两项所在组名 |
| `manuals/how-to-use-web-mode.md` | 配置面板分组表按四域/块重写；分组与顺序说明段改域轴口径 |
| `manuals/how-to-start.md` | 首页「配置编辑」面板可编辑项枚举（组数与本组分组名） |
| `manuals/how-to-use-cli-mode.md` | `--feature` / `--experiment` 说明中的分组措辞 |
| `managements/requirements.md` | 功能开关分组说明（五组、组数与默认态）与菜单表 `[S]`/`[D]` 行 |
| `managements/technical.md` | 菜单表 `[S]` 行、功能开关注册表章节 |
| `managements/testplan.md` | `[S]` 面板与 features 覆盖描述 |
| `managements/DESIGN.md` | 域标题（卡片/小节标题档 + 左侧品牌蓝竖线）与「影响报告」标记组件、域标题、说明行登记，含暗色取值（见本文件「样式规格」）；契约结构测试同步 |
| 全库措辞 | 分组计数连写链与「四组」表述（`check-doc-drift` 第 4 项按 `GROUP_ORDER` 派生校验） |

### 6.3 机检

`check-doc-drift` 第 4 项（分组计数链）、第 8 项（面板编号）、第 18 项（菜单块）均按注册表派生，脚本侧无需改动，只需文档措辞对齐；`folders.md` 目录树与统计表随本次新增文件同步。

### 6.4 测试

| 用例文件 | 断言 |
|:--|:--|
| `unit/web/test_config_edit.py` | `domains` 覆盖全部 features 组且每块 id 有渲染器；`labels`/`descriptions` 覆盖全部开关与章节键；匿名化标签来自服务端；策略中文映射 |
| `unit/config/test_features.py` | `GROUP_DOMAIN` 键集 = `GROUP_ORDER`、值域 ⊆ `DOMAIN_ORDER`；每域至少一块；`llm_enhance` 组内为辩论两项；`needs_hint` 字段为布尔；`features.needs_hint` 清单 ⊆ `GROUP_ORDER` 全量键 |
| `unit/handlers/test_handlers_config_switch.py` | `[S]` 渲染顺序 = `GROUP_ORDER`、编号连续（结构断言，不写死项数） |

断言遵守「测试真值单一来源」：用集合相等 / 覆盖 / 序号连续表达，不写死可增长集合的条数。

---

## 7. 验证计划

1. 单测：§6.4 三个文件 + `unit/ui/test_tui_menu.py`。
2. 门禁：`scripts/test-runner.py --mode dev-verify`；提交时由 pre-commit 钩子跑十守护。
3. 人工：Web 页签检查四域顺序、块内副行说明、章节/模块「影响报告」标记与 ⚗、线路策略中文、暗色主题下域标题与标记可读；TUI `[S]` 检查编号 8-34 连续与五个组块标题。

---

## 8. 设计图样

[`config-panel-mockup/index.html`](config-panel-mockup/index.html) 为自包含原型（数据内联，无外部依赖）：顶部四组开关切换「按文件编排 / 按域编排」「说明密度」「影响报告标记」「亮/暗主题」，底部给出 `[S]` 编号映射图与编号对照表。数据取自注册表与 `LLM_TUNING_SPECS` 真实条目，改注册表后可重新采集数据刷新。

配套的配置文件纵切设计见 [`llm-settings-nesting-design.md`](llm-settings-nesting-design.md)（图样 `config-panel-mockup/llm-config.html`）：`llm_settings.json` 的调优参数将落为 `runtime.*`、模块设置落为 `modules.<m>.*`。**对面板零影响**——面板读的是扁平视图与 `LLM_TUNING_SPECS`，对外键名不变。
