# 配置面板分类与描述重整设计（TUI 主体 → Web 对齐）

> **关联**：[`llm-settings-nesting-design.md`](llm-settings-nesting-design.md)（`llm_settings.json` 纵切）；设计图样 [`config-panel-mockup/index.html`](config-panel-mockup/index.html)（Web）、[`tui.html`](config-panel-mockup/tui.html)（TUI 全层级）。
> **范围**：TUI 菜单与面板层级、Web 配置面编排、两渠道共用的概念与文案来源。**不含**新增可编辑项、改写入语义、改配置文件结构（见纵切设计）。
> **顺序**：TUI 定稿 → Web 按同一套概念对齐。两渠道表现形式不同（终端 vs 浏览器），但**域、组、显示名、标记口径、说明文案同源**。

---

## 1. 目标

1. **一套概念三渠道共用**：域、组、入口名、标记与说明只有一个来源，TUI 与 Web 只是排布不同。
2. **TUI 先说清层级**：主菜单 → 二级 → 三级（→ 线路面板）逐层收敛，高频操作不超过两层。
3. **Web 按业务域编排**：块的顺序、标题、说明、默认值全部由服务端下发，前端不持有中文文案表。
4. **可增长**：新增开关/入口只改注册表与声明表，面板与文档自动跟随。

---

## 2. 共用概念（单一来源）

### 2.1 域（一级分区，Web 用；TUI 以菜单分组体现）

| 域键 | 上屏标题 | 域说明 | 收纳内容 | TUI 对应入口 |
|:--|:--|:--|:--|:--|
| `report_content` | 报告内容 | 改这里会改变报告里出现什么：顶层章节取舍、章内附加块、整章回放 | 顶层章节 + 分析增强组 + 独立章节与回放组 | `[P]`、`[S]`（前两组） |
| `presentation_mechanism` | 呈现与机制 | 只改呈现口径、匿名化与内部机制/诊断接缝：内容主体不变或仅影响入口显隐 | 匿名化 + 呈现与体验组 + 机制与诊断组 | `[G]`→`[A]`、`[S]`（机制组） |
| `data_and_routes` | 数据与线路 | 数据从哪读、跟什么基准比、LLM 走哪条线路 | 目录与文件名 + 对比基准指数 + 多链线路 | `[G]`→`[C]/[F]/[O]`、`[G]`→`[I]`、`[G]`→`[L]`（线路） |
| `llm_run` | LLM 运行 | LLM 章节启停、调用内增强（辩论/情景）与运行参数（并发/重试/预算） | LLM 章节启停 + LLM 分析增强组 + 运行参数 | `[S]`（LLM 章节）、`[G]`→`[L]` |

域与 TUI 菜单**不一一对应**：TUI 按"操作位置"（章节 / 开关 / 全局设置）组织，Web 按"意图域"组织；两者共用同一批**条目名**与**标记口径**，不共用排布。

### 2.2 组（二级，作用域轴）

| 顺序 | 组键 | 上屏标题 | 域 | 项数 |
|:--|:--|:--|:--|--:|
| 1 | `analysis` | 🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表） | 报告内容 | 14 |
| 2 | `standalone` | 📑 独立章节与回放（默认关闭 · 新增整页签或多期回放） | 报告内容 | 5 |
| 3 | `presentation` | 📊 呈现与体验（默认开启 · 只改呈现不改内容） | 呈现与机制 | 1 |
| 4 | `mechanism` | ⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验） | 呈现与机制 | 5 |
| 5 | `llm_enhance` | 🧠 LLM 分析增强（默认关闭 · 在 LLM 章节内追加辩论/情景段，无独立章节） | LLM 运行 | 2 |

组的域归属由 `GROUP_DOMAIN` 一处登记；`GROUP_ORDER` 即两渠道共同的组顺序。

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
| 「已改」 | 当前值 ≠ `defaults` | Web 行尾 `✻`；TUI 行尾 `*`（既有语义，两渠道同源比较对象） |
| 顺序 | 固定为 `⚗ › 影响报告 › 已改` | 行末区右对齐、不随标签长度漂移 |

### 2.5 文案来源

- 组标题、组说明、条目显示名、一句话说明、出厂默认值：**注册表**（`FeatureSwitchDef` 六字段 + `needs_hint`）。
- 域标题与域说明：`DOMAIN_LABELS` / `DOMAIN_HINTS`。
- 路径 / 章节 / 调优项的说明：服务端声明表与 `LLM_TUNING_SPECS.hint`。
- 前端与 TUI 渲染层**不持有**任何中文标签或说明表。

---

## 3. TUI 设计（主体）

### 3.1 主菜单：16 项，四组

```
── 生成报告 ──          [E] [B] [L] [W]
── 数据与查看 ──        [Q] [1] [2] [3]
── 配置 ──              [P] [S] [G] [R]
── 诊断与排查 ──        [V] [H] [T]
                        [X] 退出（0 亦可）
```

配置组四项（标签显示宽均 ≤ 48，80 列不折行）：

```
  [P] 报告章节（顶层章节取舍与顺序）              ← 30
  [S] 分析增强与章节增补（五组 · 含 LLM 章节）    ← 40
  [G] 全局设置（目录 / LLM / 指数 / 匿名化）      ← 38
  [R] 刷新配置
```

定位与边界：

| 项 | 管什么 | 不管什么 |
|:--|:--|:--|
| `[P]` | 顶层章节是否出现与其顺序（`config.json` 的 `enable_*`） | 章内增强块、整章增补（在 `[S]` 的组内） |
| `[S]` | 27 项功能开关：章内增强、整章增补、呈现、机制、LLM 增强；以及 7 个 LLM 章节启停 | 顶层章节取舍（在 `[P]`） |
| `[G]` | 目录与文件名、LLM 设置（运行参数 + 多链线路）、对比基准指数、持仓匿名化、配置入口地图 | 章节与开关 |
| `[R]` | 重读全部配置文件 | — |

`[P]` 面板只列 5 个顶层章节，不含跳转项；面板底部保留一行提示：`章内增强与整章增补见 [S]`。

### 3.2 `[G]` 二级：7 项

```
  ── 全局设置 ──
   [C] 持仓信息目录
   [F] 持仓信息文件名
   [O] 报告输出目录
   [L] LLM 设置（运行参数 / 多链线路）
   [I] 对比基准指数
   [A] 持仓匿名化（代码 / 名称脱敏）
   [M] 配置入口地图（各配置项所在菜单）
   [0] 返回主菜单
```

选择提示、无效输入提示与面板标题（「全局设置」）覆盖全部 7 键。`[I]` `[A]` 的面板本体与写路径（`edit_ops` 的 `comparison_indices` / `anonymization.mode`）保持不变，只改入口层级。

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
   0. 返回
```

1~6 沿用"输入新值"语义（范围校验不变）；7 为**入口**——进入既有线路面板（按链序展示 + 输入两个编号交换），返回后回到本面板。线路面板本体与写路径零改动。行尾摘要给出线路条数与链首，不进第四级即可判断链序。

### 3.4 `[S]` 面板与编号

编号 = LLM 可见模块数（7）+ 按 `GROUP_ORDER` 连续派生，运行时计算：

| 区间 | 内容 | 项数 |
|:--|:--|--:|
| 1-7 | LLM 分析章节 | 7 |
| 8-21 | 分析增强·既有章内追加 | 14 |
| 22-26 | 独立章节与回放 | 5 |
| 27-27 | 呈现与体验 | 1 |
| 28-32 | 机制与诊断 | 5 |
| 33-34 | LLM 分析增强 | 2 |

稳定入口是**键名**：`?` 详情、`?编号` 查询、`键名=on|off` 赋值均以键名为准，编号仅作当前版本的快捷定位。

### 3.5 键位纪律

- 顶层字母是用户肌肉记忆：本次释放 `M`/`I`/`A`，`D`→`G`（Global），其余不动。
- `default_menu_key` 取值域随之更新（出厂 `L` 不受影响）；失效键回落首项 `E`（既有回落逻辑）。
- 二级键在 `[G]` 内唯一（C/F/O/L/I/A/M），与顶层键不冲突。

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

四个域与块的完整对应见 §2.1；域内块顺序：报告内容（章节 → 分析增强 → 独立章节）、呈现与机制（匿名化 → 呈现 → 机制）、数据与线路（目录 → 指数 → 线路）、LLM 运行（LLM 章节 → LLM 分析增强 → 运行参数）。

### 4.2 文案：`labels` / `descriptions` / `defaults`

| 键空间 | 覆盖 | 来源 |
|:--|:--|:--|
| `labels` | 目录 3 项、顶层章节 5 项、功能开关 27 项、`enabled_llm.<模块>` 7 项 | 声明表 + 注册表 `label` + 模块注册表（名称与 §2.3 逐字一致） |
| `descriptions` | 同上全覆盖（调优项说明随 `llm_tuning[].hint` 下发） | 声明表 + 注册表 `desc` + 模块说明模板 |
| `defaults` | 布尔与数值类：开关 27、章节 5、LLM 模块 7、调优 6 | `FeatureSwitchDef.default` / 默认 `true` / `LLM_TUNING_SPECS`；枚举与动作类无默认值 |
| `features.descriptions` / `features.defaults` / `features.needs_hint` | 27 项 | 注册表 |
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
| `config/_feature_registry.py` | 5 个域常量 + `DOMAIN_ORDER/LABELS/HINTS` + `GROUP_DOMAIN`；新增 `GROUP_LLM` 并确定五组顺序；辩论两项归入该组；`FeatureSwitchDef` 新增 `needs_hint` |
| `config/features.py` | 导出面扩展（域常量、`GROUP_DOMAIN`） |
| `tui/tui_menu.py` | `MENU_ITEMS` 移除 `M`/`I`/`A`、`D`→`G`、`P`/`S` 换标签；`MENU_GROUPS` 配置组改 `P/S/G/R` |
| `tui/handlers_config.py` | 二级面板标题「全局设置」、7 键提示、`DIR_INFO_ITEMS` 增 `I`/`A` 并改 `L` 标题、`_cmd_config_llm_tuning` 增第 7 项入口、`_cmd_config_report_boards` 去掉指路牌项、`_CONFIG_ENTRY_MAP` 三行改 `[G]` 二级键 |
| `web/config_edit.py` | `_BLOCK_DOMAIN` / `_DAILY_BLOCKS` / 声明表 / `_panel_domains` / `_panel_labels` / `_panel_descriptions` / `_panel_defaults`；`_llm_providers_surface` 增策略中文与链序标记；surface 增编排与文案块 |
| `static/web/main.js` | 按 `domains` 分区渲染；删除前端中文表；块渲染支持 `descriptions`/`defaults`/`needs_hint`/`fullKey` |
| `static/web/style.css` | §4.5 四个 class + 暗色配对 |

不改：`handlers_llm_providers.py`、指数池与匿名化面板本体、全部写路径、CLI 参数名。

### 5.2 数据

`config.json` 的 `default_menu_key` 取值域少 `M`/`I`/`A`、`D`→`G`；出厂 `L` 不受影响。

### 5.3 文档

| 文件 | 同步点 |
|:--|:--|
| `manuals/how-to-start.md` / `how-to-use-tui-menu.md` | 主菜单块（16 项）+ `[M]`/`[I]`/`[A]` 三节并入 `[G]` 节 + `[S]` 编号表与五个组块标题 |
| `manuals/how-to-config.md` | 配置项索引（线路/指数/匿名化 → `[G]` 二级键）、`default_menu_key` 合法键清单、功能开关表行序 |
| `manuals/how-to-config-llm.md` | `[S]` 分块与编号、辩论两项组名、`[G]`→`[L]` 入口 |
| `manuals/how-to-use-web-mode.md` | 配置面分组表按四域/块重写、「对应 TUI 菜单」列三行 |
| `manuals/how-to-use-cli-mode.md` | `--llm-provider-order` 的 TUI 入口说明、分组措辞 |
| `managements/requirements.md` / `technical.md` | 菜单表（项数与键）、功能开关分组说明 |
| `managements/testplan.md` | 菜单清单与二级键、`[S]` 面板覆盖 |
| `managements/DESIGN.md` | 域标题、说明行、「影响报告」徽标与暗色取值登记 |
| `README.md` | 界面描述与入口说明 |

### 5.4 测试

| 用例 | 断言 |
|:--|:--|
| `test_tui_menu` | 项数 16、配置组 `P/S/G/R`、标签宽度 ≤48 |
| `test_tui_routing` | `G`→`L`/`I`/`A` 各自可达；`M`/`I`/`A` 顶层键无路由 |
| `test_handlers_config` | 二级提示含 7 键；入口地图三行指向 `[G]`；`[P]` 面板无指路牌项 |
| `test_handlers_llm_providers` | 入口经 `[G]`→`[L]` |
| `config` / `features` | `GROUP_DOMAIN` 键集 = `GROUP_ORDER`、值域 ⊆ `DOMAIN_ORDER`；`llm_enhance` 组内为辩论两项；`needs_hint` 为布尔 |
| `web/test_config_edit` | `domains` 覆盖全部组且每块有渲染器；`labels`/`descriptions`/`defaults` 覆盖全部键；匿名化与策略标签来自服务端 |

断言用结构关系（集合相等 / 覆盖 / 序号连续），不写死可增长集合的条数。

---

## 6. 验证计划

1. 单测：§5.4 全部用例。
2. 门禁：`scripts/test-runner.py --mode dev-verify`；提交时由 pre-commit 钩子执行十守护（含 `check-doc-drift` 的分组计数与面板编号）。
3. 人工 TUI：主菜单 16 项；`[G]` 七项可达；`[G]`→`[L]` 第 7 项进入线路面板并返回；`[S]` 编号 8-34 连续、五个组块标题正确；`[P]` 无指路牌项。
4. 人工 Web：四域顺序与块内副行说明；章节与模块的「影响报告」徽标、`⚗`、`✻` 三标记同列；线路策略中文；暗色下域标题与徽标可读。

---

## 7. 设计图样

图样按样式分为两组，**互不混排**——同一份文件里要么是目标设计，要么是现有实现。

| 目标设计（建议方案） | 现有实现 |
|:--|:--|
| [`config-panel-mockup/tui.html`](config-panel-mockup/tui.html)：五组开关、16 项主菜单、`[G]` 七项、`[G]`→`[L]` 七项 | [`config-panel-mockup/tui-current.html`](config-panel-mockup/tui-current.html)：四组开关、19 项主菜单、`[D]` 五项、`[D]`→`[L]` 六项 |
| [`config-panel-mockup/index.html`](config-panel-mockup/index.html)：Web 按业务域编排 | [`config-panel-mockup/web-current.html`](config-panel-mockup/web-current.html)：Web 按存储文件编排 |
| [`config-panel-mockup/llm-config.html`](config-panel-mockup/llm-config.html)：模块纵切结构 + 键位映射 | [`config-panel-mockup/llm-config-current.html`](config-panel-mockup/llm-config-current.html)：扁平结构（参数 × 模块平铺） |

TUI 两套图样均由真实处理器渲染（等宽字体 + 真实 ANSI 配色），文件选择类屏幕取到列表即中止；设计结构屏按设计项注入后渲染。Web 与配置文件图样的数据取自注册表与真实配置文件，改注册表后可重跑 `tui_capture.py` / `tui_build.py` / `llm_config_mock.py` 刷新。
