# 配置面板分类与描述设计（TUI 与 Web 共用一套概念）

> **关联**：[`llm-settings-nesting-design.md`](llm-settings-nesting-design.md)（`llm_settings.json` 纵切）；设计图样 [`config-panel-mockup/index.html`](config-panel-mockup/index.html)（Web）、[`tui.html`](config-panel-mockup/tui.html)（TUI 全层级）。
> **范围**：TUI 菜单与面板层级、Web 配置面编排、两渠道共用的概念与文案来源。**不含**新增可编辑项、改写入语义、改配置文件结构（见纵切设计）。
> **两渠道**：终端与浏览器表现形式不同（排布、键位、组件形态），但**域、组、显示名、标记口径、说明文案同源**。

---

## 1. 目标

1. **一套概念三渠道共用**：域、组、入口名、标记与说明只有一个来源，TUI 与 Web 只是排布不同。
2. **TUI 层级清晰**：主菜单 → 二级 → 三级（→ 线路面板），高频操作不超过两层。
3. **Web 按业务域编排**：块的顺序、标题、说明、默认值全部由服务端下发，前端不持有中文文案表。
4. **可增长**：新增开关/入口只改注册表与声明表，面板与文档自动跟随。

---

## 2. 共用概念（单一来源）

### 2.1 域（一级分区，Web 用；TUI 以菜单分组体现）

| 域键 | 上屏标题 | 域说明 | 收纳内容 | TUI 对应入口 |
|:--|:--|:--|:--|:--|
| `report_content` | 报告内容 | 改这里会改变报告里出现什么：哪些章出现、章内追加什么、整章回放是否启用 | 顶层章节 + LLM 章节（含智囊团下的辩论两项）+ 整章增补 + 分析增强组 | `[P]` 全部、`[S]`（分析增强组） |
| `presentation_mechanism` | 呈现与机制 | 只改呈现口径、匿名化与内部机制/诊断接缝：内容主体不变或仅影响入口显隐 | 匿名化 + 呈现与体验组 + 机制与诊断组 | `[G]`→`[A]`、`[S]`（呈现与机制组） |
| `data_and_routes` | 数据与线路 | 数据从哪读、跟什么基准比、LLM 走哪条线路 | 目录与文件名 + 对比基准指数 + 多链线路 | `[G]`→`[C]/[F]/[O]`、`[G]`→`[I]`、`[G]`→`[L]`（线路） |
| `llm_run` | LLM 运行 | LLM 调用的运行约束（并发/重试/预算） | 运行参数 6 项 | `[G]`→`[L]`（1-6） |
| `ops_diagnostics` | 运行与诊断 | 日志写盘与控制台输出、日志查看器默认筛选；级别与轮转在下次启动生效 | 日志设置 6 项（见 [`logging-config-design.md`](logging-config-design.md)） | `[D]`→`[L]` |

域与 TUI 菜单**不一一对应**：TUI 按"操作位置"（章节 / 开关 / 全局设置）组织，Web 按"意图域"组织；两者共用同一批**条目名**与**标记口径**，不共用排布。

### 2.2 组（作用域轴）

组只描述「开了长出什么」；**每组归属且仅归属一个面板**（声明见下）。

| 顺序 | 组键 | 上屏标题 | 所属面板 | 项数 |
|:--|:--|:--|:--|--:|
| 1 | `analysis` | 🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表） | `[S]` | 14 |
| 2 | `standalone` | 📑 独立章节与回放（默认关闭 · 新增整页签或多期回放） | `[P]` | 5 |
| 3 | `presentation` | 📊 呈现与体验（默认开启 · 只改呈现不改内容） | `[S]` | 1 |
| 4 | `mechanism` | ⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验） | `[S]` | 4 |

辩论两项（`llm_debate_procon` / `llm_debate_conditional`）**不属任何组**：它们不新增章节、也不渲染独立块，只改变智囊团章内的生成内容，因此在 `[P]` 里作为「智囊团深度复盘」的子项呈现（编号 `7.1` / `7.2`）。

组内共 24 项（14+5+1+4），加上作为 `[P]` 子项的辩论 2 项，合 26 项功能开关。

`PANEL_GROUPS` 声明给出"组 → 面板"的唯一归属，两面板各自只渲染自己的组；覆盖完整性可断言（每组恰属一个面板）。

### 2.3 条目名（TUI 逐字等于 Web 标签）

| 条目 | 统一名称 |
|:--|:--|
| 顶层章节 | 基金深度分析 / 市场新闻 / 组合历史走势+回撤 / 组合演进 / 行动建议 |
| 目录 | 持仓信息目录 / 持仓信息文件名 / 报告输出目录 |
| 指数 | 对比基准指数 |
| 匿名化 | 持仓匿名化（代码 / 名称脱敏） |
| LLM | LLM 设置（运行参数 / 多链线路）、LLM 分析章节、多链线路优先级 |
| 索引 | 配置入口地图 |

### 2.4 标记口径（三渠道同义）

| 标记 | 判定 | 呈现 |
|:--|:--|:--|
| 「影响报告」 | `affects_report` 为真（含报告章节、LLM 模块：关闭即整章隐藏） | Web 行末同列徽标；TUI 用「（影响报告）」纯文本 |
| `⚗` | `experimental` 为真 | 两渠道行首/行尾固定位置 |
| 「已改」 | 当前值 ≠ `defaults` | Web 行尾 `✻`；TUI 行尾 `*`；两渠道以同一对象（`defaults`）为比较基准 |
| 顺序 | 固定为 `⚗ › 影响报告 › 已改` | 行末区右对齐、不随标签长度漂移 |

### 2.5 文案来源

- 组标题、组说明、条目显示名、一句话说明、出厂默认值：**注册表**（`FeatureSwitchDef` 六字段 + `needs_hint`）。
- 域标题与域说明：`DOMAIN_LABELS` / `DOMAIN_HINTS`。
- 路径 / 章节 / 调优项的说明：服务端声明表与 `LLM_TUNING_SPECS.hint`。
- 前端与 TUI 渲染层**不持有**任何中文标签或说明表。

---

## 3. TUI 设计

### 3.0 层级导航与键语义

```
主菜单（一级 · 14 项）
├─ 生成报告      [E] [B] [L] [W]
├─ 数据与查看    [Q] [1] [2] [3]
├─ 配置
│   ├─ [P] 报告章节        二级 · 数字 1-17（顶层 5 / LLM 7 / 整章增补 5）
│   │   └─ 7.1 / 7.2         智囊团章生成选项（辩论两项，子项编号）
│   ├─ [S] 报告呈现与增强  二级 · 数字 1-19（分析 14 / 呈现 1 / 机制与诊断 4）
│   ├─ [G] 全局设置        二级 · 字母键 C/F/O/L/I/A/M（分组：目录与文件 / LLM / 基准与呈现 / 索引）
│   │   ├─ [L] LLM 设置         三级 · 数字 1-7 · 0 返回
│   │   │     ├─ 1-6 运行参数        输入新值（范围校验）
│   │   │     └─ 7 多链线路优先级    四级 · 输入两个编号交换
│   │   ├─ [C]/[F]/[O]          目录 / 文件名 / 输出目录
│   │   ├─ [I] 对比基准指数     增删 / 重置
│   │   ├─ [A] 持仓匿名化       数字 1-4 选档
│   │   └─ [M] 配置入口地图     只读打印
│   └─ [R] 刷新配置
└─ 诊断与排查    [D]      二级 · 字母键 V/H/T/L · 0 返回
                ├─ [V] 运行日志
                ├─ [H] 数据源健康历史
                ├─ [T] 系统自检（恒上屏）
                └─ [L] 日志设置（三级 · 数字 1-6）
```

| 层级 | 键的类型 | 用途 | 返回 |
|:--|:--|:--|:--|
| 一级主菜单 | 字母 / 数字（E/B/L/W/Q/1/2/3/P/S/G/R/D） | 进入功能 | `0` / `X` / Ctrl+C |
| 二级面板 | **数字编号**（`[P]` 1-17、`[S]` 1-19）或**字母键**（`[G]` C/F/O/L/I/A/M、`[D]` V/H/T） | 切换章节/开关，或选子项 | `0` 回主菜单 |
| 子项编号 | **十进制**（`7.1` / `7.2`） | 只用于某章节下的生成选项，章节编号保持稳定 | 不单独返回，仍在 `[P]` |
| 三级面板 | 数字编号（`[G]`→`[L]` 1-7） | 改一个值或再进一层 | `0` 回上一级 |
| 四级（线路） | 两个数字（如 `3 1`） | 交换两条线路优先级 | 回车返回 |

**返回规则（遵循 `DESIGN-TUI.md` 键分工）**：

| 面板层级 | 末项固定为 | 返回目标 | Esc |
|:--|:--|:--|:--|
| 二级（`[P]` / `[S]` / `[G]` / `[D]`） | `0. 返回主菜单` | 主菜单 | 同 `0`（不退出程序） |
| 三级（`[G]`→`[L]`） | `0. 返回全局设置` | `[G]` 二级面板 | 同 `0` |
| 四级（线路面板） | `0. 返回 LLM 设置` | `[G]`→`[L]` | 同 `0` |

- 每个面板的最后一项恒为 `0`，且文案按"上一层"命名（不是统一的"返回"）。
- 子项（`7.1`/`7.2`）不占返回位，输入后仍停在同一面板。
- 返回后重绘上一层面板，用户可继续操作（不必回到主菜单再进）。

四条容易混淆的边界：

1. **`[P]` 的 17 个编号是"章节"**：1-5 顶层章节、6-12 LLM 章节、13-17 整章增补；`7.1`/`7.2` 是第 7 项（智囊团）的生成选项，不算独立章节。
2. **`[S]` 的 20 个编号是"章内内容"**：分析增强 14（因子目录/估值分位/市场温度等）、呈现 1、机制 5；LLM 章节与整章增补只在 `[P]` 中出现。
3. **`?编号` 不换层级**：面板内只读查询，打印说明后回到同一提示符，不写配置。
4. **编号随组序派生**：两面板的编号都由所属组的顺序与注册表顺序派生；稳定入口是键名（`?键名` / `键名=on|off`）。

### 3.1 主菜单：14 项，四组

```
── 生成报告 ──          [E] [B] [L] [W]
── 数据与查看 ──        [Q] [1] [2] [3]
── 配置 ──              [P] [S] [G] [R]
── 诊断与排查 ──        [D] 诊断与排查（日志 / 健康历史 / 自检）
                        [X] 退出（0 亦可）
```

配置组四项（标签显示宽均 ≤ 48，80 列不折行）：

```
  [P] 报告章节（顶层 / LLM / 增补）                ← 29
  [S] 报告呈现与增强                               ← 14
  [G] 全局设置（目录 / LLM / 指数 / 匿名化 / 索引）  ← 45
  [R] 刷新配置
```

定位与边界：

| 项 | 管什么 | 不管什么 |
|:--|:--|:--|
| `[P]` | **哪些章节出现**：顶层、LLM、整章增补三类；以及智囊团的生成选项（`7.1`/`7.2`） | 章内追加块（在 `[S]`） |
| `[S]` | **报告内的呈现与增强**：分析增强 14、呈现 1、机制与诊断 4 | 章节显隐与整章增补（在 `[P]`） |
| `[G]` | 目录与文件名、LLM 运行参数与多链线路、对比基准指数、持仓匿名化、配置入口地图 | 章节与章内开关 |
| `[D]` | 诊断入口：运行日志 `V`、数据源健康历史 `H`、系统自检 `T`（恒上屏，无开关） | 章节、开关与全局配置（本层只做入口聚合） |
| `[R]` | 重读全部配置文件 | — |

`[P]` 面板结构（17 项 + 两个子项）：

```
  ── 报告章节 ──
   ── 顶层章节 ──
    1. 基金深度分析            [启用]
    2. 市场新闻                [启用]
    3. 组合历史走势+回撤        [启用]
    4. 组合演进                [启用]
    5. 行动建议                [启用]
   ── LLM 章节 ──
    6. 全球政经局势            [启用]
    7. 智囊团深度复盘          [启用]
       7.1 辩论-正反辩论        [关闭]
       7.2 辩论-条件推理        [开启]
    8. 财经新闻热点与持仓关联   [启用]
    9. 持仓体检报告            [启用]
   10. 穿透深度分析            [启用]
   11. 生成后自检              [启用]
   12. 持仓变动复盘归因        [启用]
   ── 整章增补 ──
   13. 调仓纪律回放            [启用]
   14. 持仓变动复盘            [启用]
   15. What-if 交易成本对比    [启用]
   16. 个股基本面              [启用]
   17. 危机回放                [启用]
    0. 返回主菜单
```

- 三块来源不同但语义统一：顶层章节写 `config.json` 的 `enable_*`，LLM 章节写 `llm_settings.enabled_llm`，整章增补写 `features.json`；面板不暴露来源差异。
- 「影响报告」语义在面板顶部统一说明一次（这些项关闭即整章不出现），不在每行重复徽标。
- 子项（`7.1`/`7.2`）只在智囊团启用时可切换；智囊团关闭时置灰并提示"启用第 7 项后可切换"。
- 输入 `7.1` / `7.2` 直接切换子项，输入 `7` 切换章节本身。

### 3.2 `[G]` 二级：7 项

```
  ── 全局设置 ──
     ── 目录与文件 ──
       [C] 持仓信息目录
       [F] 持仓信息文件名
       [O] 报告输出目录
     ── LLM ──
       [L] LLM 设置（运行参数 / 多链线路）
     ── 基准与呈现 ──
       [I] 对比基准指数
       [A] 持仓匿名化（代码 / 名称脱敏）
     ── 索引 ──
       [M] 配置入口地图（各配置项所在菜单）
       [0] 返回主菜单
```

分类标题只影响排版（键位、层级与返回语义不变）：`[C]/[F]/[O]` 目录与文件、`[L]` LLM、`[I]/[A]` 基准与呈现、`[M]` 索引。选择提示、无效输入提示与面板标题（「全局设置」）覆盖全部 7 键。`[I]` `[A]` 的面板本体与写路径（`edit_ops` 的 `comparison_indices` / `anonymization.mode`）独立于入口层级。

### 3.3 `[G]` → `[L]` 三级：7 项

```
  ── LLM 设置 ──
   1. thinking 模块并发上限（当前 2）
   2. LLM 模块并发线程数（当前 3）
   3. 单请求重试次数（当前 2）
   4. 整链失败后的重试等待（秒）（当前 30）
   5. LLM 总时间预算（秒）（当前 0）
   6. LLM 日费用上限（当前 0）
   7. 多链线路优先级（2 条，当前链首 deepseek-main）
   0. 返回全局设置
```

1~6 为数值编辑：输入新值即写盘，超出范围直接拒绝；7 为**入口**——进入线路面板（按链序展示 + 输入两个编号交换），返回后回到本面板。线路面板与写路径独立于本面板。行尾摘要给出线路条数与链首，不进第四级即可判断链序。

### 3.4 `[S]` 面板与编号

编号 = 按 `PANEL_GROUPS["[S]"]` 的组顺序连续派生（运行时计算）：

| 区间 | 内容 | 项数 |
|:--|:--|--:|
| 1-14 | 分析增强·既有章内追加 | 14 |
| 15-15 | 呈现与体验 | 1 |
| 16-19 | 机制与诊断 | 4 |

面板不出现 LLM 章节与整章增补（在 `[P]`）；系统自检恒上屏、无开关；末项为 `0. 返回主菜单`，面板底部一行提示「章节显隐见 [P]」。稳定入口仍是键名：`?键名` 查询、`键名=on|off` 赋值。

### 3.5 `[D]` 二级：诊断与排查

```
  ── 诊断与排查 ──
   [V] 运行日志（可按级别筛选）
   [H] 数据源健康历史
   [T] 系统自检（环境 / 配置 / 目录 / 数据源）
   [L] 日志设置（级别 / 轮转 / 查看器）
   [0] 返回主菜单
```

`[L]` 三级（数字编号，`0` 返回诊断与排查）：

```
  ── 日志设置 ──
   1. 写盘级别（当前 INFO）
   2. 控制台级别（当前 INFO）
   3. 单文件上限 MB（当前 10）
   4. 备份份数（当前 5）
   5. 查看器默认级别（当前 INFO）
   6. 查看器首屏行数（当前 500）
   0. 返回诊断与排查
```

- 日志设置写入独立的 `logger.json`（详见 [`logging-config-design.md`](logging-config-design.md)）；级别与轮转改动下次启动生效，查看器两项即时生效。
- `[T]` 恒上屏：不设功能开关，也不受任何开关门控。
- 返回语义：`0` 回主菜单；Esc 同义。

### 3.6 键位纪律

- 顶层字母分配：配置组取 `P`/`S`/`G`/`R`（`G`=Global），诊断组取 `D`；`[G]` 二级取 `C`/`F`/`O`/`L`/`I`/`A`/`M`，`[D]` 二级取 `V`/`H`/`T`/`L`。
- `default_menu_key` 的合法取值即主菜单键集合（出厂 `L`）；取值为不存在的键时回落首项 `E`。
- 二级键在各面板内唯一（`[G]`：C/F/O/L/I/A/M；`[D]`：V/H/T/L），与顶层键不冲突。

---

## 4. Web 设计（对齐 TUI）

### 4.1 编排：`domains`

```json
"domains": [
  {"key": "report_content", "title": "报告内容", "hint": "改这里会改变报告里出现什么…",
   "blocks": ["sections", "features.analysis", "features.standalone"]}
]
```

前端按顺序遍历 `domains` → `blocks`，按块 id 取渲染器：`features.<组键>` 查 `surface.features.groups`，其余查块渲染器表；渲染器返回 `null` 即跳过该块。

四个域与块的完整对应见 §2.1；域内块顺序：报告内容（章节 → LLM 章节（含辩论子行） → 整章增补 → 分析增强）、呈现与机制（匿名化 → 呈现 → 机制）、数据与线路（目录 → 指数 → 线路）、LLM 运行（运行参数）。

### 4.2 文案：`labels` / `descriptions` / `defaults`

| 键空间 | 覆盖 | 来源 |
|:--|:--|:--|
| `labels` | 目录 3 项、顶层章节 5 项、功能开关 26 项、`enabled_llm.<模块>` 7 项 | 声明表 + 注册表 `label` + 模块注册表（名称与 §2.3 逐字一致） |
| `descriptions` | 同上全覆盖（调优项说明随 `llm_tuning[].hint` 下发） | 声明表 + 注册表 `desc` + 模块说明模板 |
| `defaults` | 布尔与数值类：开关 27、章节 5、LLM 模块 7、调优 6 | `FeatureSwitchDef.default` / 默认 `true` / `LLM_TUNING_SPECS`；枚举与动作类无默认值 |
| `features.descriptions` / `features.defaults` / `features.needs_hint` | 26 项 | 注册表 |
| `anonymization.labels` | 4 档 | `anonymizer.ANONYMIZATION_MODE_DESCRIPTIONS` |
| `llm_providers.strategy_label` / `order_is_chain` | 4 种策略中文名 + 顺序是否等于实际链序 | 策略中文表 |

### 4.3 块 id 与渲染器

| 块 id | 渲染器 | 数据为空时 |
|:--|:--|:--|
| `paths` | `renderPathsGroup` | 不出现 |
| `sections` | `renderBoolGroup` | 不出现 |
| `features.<组键>` | `renderBoolGroup`（取 `features.groups[i]`） | 组内 0 项则不出现 |
| `anonymization` | `renderAnonGroup` | 不出现 |
| `indices` | `renderIndicesGroup` | 不出现（保留"添加"表单则至少渲染表单） |
| `providers` | `renderProvidersGroup` | 不出现（无多链线路） |
| `llm` | `renderBoolGroup`（`enabled_llm.*`） | 不出现 |
| `tuning` | `renderTuningGroup` | 不出现 |

### 4.4 说明密度

默认"仅需提示的项显副行"：路径、运行参数与解释成本高的开关（`factor_catalog`、`event_window_impact`、`deterministic_signal` 等）渲染 12px 副行；其余说明存 `title`，悬停可读。"哪些项需要副行"由注册表 `FeatureSwitchDef.needs_hint` 承载，`features.needs_hint` 同源下发——不在前端维护清单。切换为"全部显示"= 前端忽略该字段。

### 4.5 样式规格（`style.css`，须含暗色配对）

| 元素 | 规格 | 取值 |
|:--|:--|:--|
| 域分区 | 相邻域之间上间距 + 分隔线 | `margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--border)` |
| 域标题 | 字阶「卡片/小节标题」，字重 600，左侧品牌蓝竖线 | `16px / 1.4`，`padding-left: 10px; border-left: 3px solid var(--primary)` |
| 域说明 | 脚注档，次要墨色 | `12px / 1.5`，`var(--text-secondary)`，`margin-left: 13px` |
| 项说明副行 | 脚注档，次要墨色，与勾选框文字左对齐 | `12px / 1.5`，`margin-left: 22px` |
| 「影响报告」徽标 | 1px 边框 + accent 色 | 亮色 `var(--accent)`；暗色覆盖 `#6ecf9f`（`--accent` 在暗色面对比不足） |

---

## 5. 影响面

### 5.1 代码

| 文件 | 改动 |
|:--|:--|
| `config/_feature_registry.py` | 域常量 + `DOMAIN_ORDER/LABELS/HINTS` + `GROUP_DOMAIN`；`GROUP_ORDER` 四组（`analysis`/`standalone`/`presentation`/`mechanism`；辩论作为 `[P]` 的子项、不入组）；新增 `PANEL_GROUPS`（组 → 面板归属）；`FeatureSwitchDef` 新增 `needs_hint`；注册表不含 `doctor_check`（系统自检恒上屏） |
| `config/features.py` | 导出面扩展（域常量、`GROUP_DOMAIN`、`PANEL_GROUPS`） |
| `tui/tui_menu.py` | `MENU_ITEMS` 移除 `M`/`I`/`A`/`V`/`H`/`T`、`D`→`G`、新增 `D`（诊断与排查）、`P`/`S` 换标签；`MENU_GROUPS` 配置组改 `P/S/G/R`、诊断组改 `D`；`FEATURE_GATED_ITEMS` 去掉 `T` 门控 |
| `tui/handlers_config.py` | `_cmd_config_report_boards` 重写为 17 项三块 + `7.1/7.2` 子项 + 来源统一写路径；二级面板标题「全局设置」、7 键提示与分组排版、`DIR_INFO_ITEMS` 增 `I`/`A`；新增 `[D]` 诊断子菜单处理器（V/H/T/L 入口聚合）；`_cmd_config_llm_tuning` 增第 7 项入口；`_CONFIG_ENTRY_MAP` 三行改 `[G]` 二级键 |
| `tui/handlers_switch.py` | `[S]` 只渲染 `PANEL_GROUPS["[S]"]` 的组（19 项），不含 LLM 模块块；底部提示指向 `[P]` |
| `core/system_info.py` | 去掉 `doctor_enabled` 判据（自检卡恒显示） |
| `core/logger.py` + `config/_logging.py` + `config/edit_ops.py` | 日志配置读取 / 校验 / 写入与 6 个白名单项（见 logging 设计文档） |
| `web/config_edit.py` | `_BLOCK_DOMAIN` / `_DAILY_BLOCKS` / 声明表 / `_panel_domains` / `_panel_labels` / `_panel_descriptions` / `_panel_defaults`；`_llm_providers_surface` 增策略中文与链序标记；surface 增编排与文案块 |
| `static/web/main.js` | 按 `domains` 分区渲染；删除前端中文表；块渲染支持 `descriptions`/`defaults`/`needs_hint`/`fullKey` |
| `static/web/style.css` | §4.5 四个 class + 暗色配对 |
| `tui/handlers_log.py` / `core/log_reader.py` | 读取 `viewer.default_level` / `tail_lines` 作为查看器初始值 |

不改：`handlers_llm_providers.py`、指数池与匿名化面板本体、全部写路径、CLI 参数名。

### 5.2 数据

`config.json` 的 `default_menu_key` 取值域少 `M`/`I`/`A`、`D`→`G`；出厂 `L` 不受影响。

### 5.3 文档

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-start.md` / `how-to-use-tui-menu.md` | 主菜单块（14 项）+ `[G]` 节（C/F/O/L/I/A/M）+ `[D]` 节（V/H/T/L）+ `[P]` 17 项三块与 `7.1`/`7.2` + `[S]` 19 项三块 |
| `manuals/how-to-config.md` | 配置项索引（线路/指数/匿名化 → `[G]` 二级键）、`default_menu_key` 合法键清单、功能开关表行序 |
| `manuals/how-to-config-llm.md` | `[P]` 的 LLM 章节块与 `7.1`/`7.2` 子项、`[G]`→`[L]` 入口 |
| `manuals/how-to-use-web-mode.md` | 配置面分组表按四域/块重写、「对应 TUI 菜单」列三行 |
| `manuals/how-to-use-cli-mode.md` | `--llm-provider-order` 的 TUI 入口说明、分组措辞 |
| `managements/requirements.md` / `technical.md` | 菜单表（项数与键）、功能开关分组说明 |
| `managements/testplan.md` | 菜单清单与二级键、`[S]` 面板覆盖 |
| `managements/DESIGN.md` | 域标题、说明行、「影响报告」徽标与暗色取值登记 |
| `README.md` | 界面描述与入口说明 |

### 5.4 测试

| 用例 | 断言 |
|:--|:--|
| `test_tui_menu` | 项数 14、配置组 `P/S/G/R`、诊断组 `D`、标签宽度 ≤48 |
| `test_tui_routing` | `G`→`L`/`I`/`A`、`D`→`V`/`H`/`T` 各自可达；`M`/`I`/`A`/`V`/`H`/`T` 顶层键无路由 |
| `test_handlers_config` | 二级提示含 7 键、四个分组标题；`[D]` 诊断子菜单四项（V/H/T/L）可路由；入口地图三行指向 `[G]`；`[P]` 面板 17 项三块 + `7.1/7.2` 子项可切换、智囊团关闭时子项置灰 |
| `test_handlers_llm_providers` | 入口经 `[G]`→`[L]` |
| `config` / `features` | `GROUP_DOMAIN` 键集 = `GROUP_ORDER`、值域 ⊆ `DOMAIN_ORDER`；`PANEL_GROUPS` 覆盖全部组且每组恰属一个面板；`needs_hint` 为布尔；`doctor_check` 不在注册表 |
| `config/test_logging` | 默认值 / 非法值拒绝 / env 覆盖优先级 / 缓存失效 / 轮转参数生效 |
| `web/test_config_edit` | `domains` 覆盖全部组且每块有渲染器；`labels`/`descriptions`/`defaults` 覆盖全部键；匿名化与策略标签来自服务端 |

断言用结构关系（集合相等 / 覆盖 / 序号连续），不写死可增长集合的条数。

---

## 6. 验证计划

1. 单测：§5.4 全部用例。
2. 门禁：`scripts/test-runner.py --mode dev-verify`；提交时由 pre-commit 钩子执行十守护（含 `check-doc-drift` 的分组计数与面板编号）。
3. 人工 TUI：主菜单 14 项；`[G]` 七项、`[D]` 四项可达；`[G]`→`[L]` 第 7 项进入线路面板并返回；`[S]` 编号 1-19 连续、三个组块标题正确；`[P]` 为 17 项三块 + `7.1`/`7.2`。
4. 人工 Web：四域顺序与块内副行说明；章节与模块的「影响报告」徽标、`⚗`、`✻` 三标记同列；线路策略中文；暗色下域标题与徽标可读。

---

## 7. 设计图样

图样按样式分为两组，**互不混排**——同一份文件里要么是目标设计，要么是现有实现。

| 目标设计（建议方案） | 现有实现 |
|:--|:--|
| [`config-panel-mockup/tui.html`](config-panel-mockup/tui.html)：`[P]` 章节总表、`[S]` 报告呈现与增强、`[G]` 全局设置（分组排版）、`[G]`→`[L]` LLM 设置 | [`config-panel-mockup/tui-current.html`](config-panel-mockup/tui-current.html)：四组开关、一级直达的指数池与匿名化、`[D]` 目录信息、`[D]`→`[L]` 调优参数 |
| [`config-panel-mockup/index.html`](config-panel-mockup/index.html)：Web 按业务域编排 | [`config-panel-mockup/web-current.html`](config-panel-mockup/web-current.html)：Web 按存储文件编排 |
| [`config-panel-mockup/llm-config.html`](config-panel-mockup/llm-config.html)：模块纵切结构 + 键位映射 | [`config-panel-mockup/llm-config-current.html`](config-panel-mockup/llm-config-current.html)：扁平结构（参数 × 模块平铺） |

日志配置独立成文件的设计见 [`logging-config-design.md`](logging-config-design.md)。

TUI 两套图样均由真实处理器渲染（等宽字体 + 真实 ANSI 配色），文件选择类屏幕取到列表即中止；设计结构屏按设计项注入后渲染。Web 与配置文件图样的数据取自注册表与真实配置文件，改注册表后可重跑 `tui_capture.py` / `tui_build.py` / `llm_config_mock.py` 刷新。
