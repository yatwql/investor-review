# 功能开关面板分组重构（feature_switch 分组作用域化）迭代设计方案与实施计划

> 关联任务：plan-120（`docs/managements/plan.md` P2 预期实施）
> 版本：v0.12.12-dev · 状态：设计定稿
> 语义命名：本设计围绕既有注册表 `config/features.py::feature_switch_registry`（功能开关注册表唯一事实来源约束）；新增分组常量与字段以 `scope`/`GROUP_*` 语义命名。本文所有代码标识符以此为准，禁用任务编号命名（语义命名纪律）。

---

## 1. 背景与问题

### 1.1 现状

TUI `[S]` 面板与 Web 配置面板的功能开关由 `config/features.py::feature_switch_registry`（功能开关注册表唯一事实来源）驱动，当前 31 项开关分三组（`GROUP_ORDER`）：

| 组常量 | 组标签 | 项数 | 判据 |
|:---|:---|:---|:---|
| `GROUP_EXPERIMENTAL` | ⚗ 实验性功能（默认关闭） | 2 | 待真实数据验证后择机转正，出厂默认关 |
| `GROUP_STANDARD` | 常规开关（默认开启） | 9 | 常驻能力，出厂默认开、用户可关 |
| `GROUP_REPORT` | 报告章节与增强（默认多数关闭） | 20 | 逐章/逐区块，默认多数关 |

### 1.2 三个真问题

**问题 1：单块 20 项，认知重灾区。** `GROUP_REPORT` 占全面板 65%（20/31），编号 19-38 横跨 20 个数字。用户想找「市场温度」需在 20 行里扫。且这 20 项性质混杂——14 项是「在既有章节里加一列/一块/一行」（估值分位列、市场温度刻度、申购状态列），仅 6 项是真·独立章或回放（财报摘要、财务指标、持仓变动复盘、调仓回放、What-if 对比、危机双层回放）。

**问题 2：`GROUP_STANDARD` 是杂物抽屉。** 9 项里混着三种性质：真·读侧增强（`metrics_enabled`/`enable_interactive_charts`）、诊断/信号类（`deterministic_signal`/`module_quality_gate`/`datasource_credential_ready`/`doctor_check`）、接缝/契约类（`decision_header_parse`/`datasource_adapter`）。「量化指标显示」与「数据源适配契约」并列令用户困惑。

**问题 3：命名与产物形态不符。** 「报告章节与增强」暗示会新增独立页签，但 14/20 实为既有章内追加。用户开「市场情绪」以为多一页，实际是行动建议章内多一个块。

### 1.3 换轴洞察

用户在 `[S]` 面板决策时的心智问题是「**我开这个开关，报告会长出什么东西？**」（作用域），而非「这个功能处于什么生命周期」。当前分组把「生命周期」当主分类轴（见 `features.py` 顶部注释：分组表达生命周期当前状态）。本设计将**作用域升为主轴、生命周期降为组内标注**。

---

## 2. 目标与明确不做

### 2.1 目标

- 把「报告章节与增强」20 项按**产物作用域**拆成两组，消除单块扫描负担；
- 把 `GROUP_STANDARD` 的「诊断/接缝类」与「实验类」合并为「机制与诊断」组，让低频内部开关聚拢、诚实表达；
- 保持功能开关注册表唯一事实来源：`feature_switch_registry` 仍是唯一事实来源，分组只改**表达**，不新增第二清单；
- 保持「转正 = 生命周期迁移」语义可表达，且不破坏 `--experiment` 取值域与产物自述机制。

### 2.2 明确不做

- **不改任何开关的 `default` 与 `affects_report`**（零行为变化，产物逐字节不变）；
- **不新增/删除/重命名任何开关 key**（31 项 key 恒定）；
- **不动 `enabled_llm`/`news_sources`/`enable_history`/匿名化**等非 features.json 开关；
- **不引入全屏/新交互范式**（仅分组与标签调整）；
- **不做分组的用户自定义拖拽/排序**（超出本次范围）。

---

## 3. 架构约束逐条对照（先自检再设计）

| 约束 | 本设计的遵从方式 |
|:---|:---|
| **功能开关注册表唯一事实来源** | 分组只改 `FeatureSwitchDef.group` 取值与 `GROUP_*` 常量集合，`feature_switch_registry` 仍是唯一清单；渠道层（TUI/Web/CLI）零本地筛选。守护 `test_features.py` 与 `check-semantic-index` 照常 |
| **语义命名纪律** | 新组常量用语义名（见 §4.1），禁止 `plan-`/`rf-`；由 `check-code-traces` 强制 |
| **文档与实现一致性（check-doc-drift）** | 本设计的最大改造面。守护脚本 `scripts/_doc_drift/_format.py` 把三组硬编码进正则与 `check_panel_numbering`，必须**先改守护脚本适配四组**，再改注册表（详见 §6 迭代 1 与 §7 风险 R1） |
| **文件长度红线** | 本设计涉及 `features.py`/`_format.py`/手册，均需在改动后确认 `check-file-length` 通过；`_format.py` 已较长，新增四组逻辑须警惕逼近脚本 1000 行红线 |
| **转正语义（features.py 顶部注释）** | 「转正 = 移出实验组」在四组下重新定义为「生命周期迁移」，见 §4.3 |

**关键耦合点（调研实证）：**
1. `scripts/_doc_drift/_format.py`：`_group_counts()`（硬编码三组）、`_TRIPLE_COUNT` 正则（`⚗实验N/常规N/报告章节与增强N`）、`_GROUP_NAME_TO_KIND`、`_GROUPED_COUNT`、`_REPORT_BLOCK_COUNT`、`check_panel_numbering`（硬编码实验/常规/报告三段边界）。
2. `features.py::is_experimental_switch` = `d.group == GROUP_EXPERIMENTAL`（`--experiment` 取值域）——若实验性降为独立属性，此判定必须改。
3. `features.py::enabled_experimental_features`（`--experiment` 日志 + 页脚实验自述 `experimental_notice.py`）同源于 `d.group == GROUP_EXPERIMENTAL`。
4. TUI `handlers_config.py::_cmd_config_llm_modules`（分块渲染 + `experiment_flags` ⚗ 逐行标记）。
5. 手册 `how-to-use-tui-menu.md`（`[S]` 面板编号表 `_PANEL_SECTION_*`）+ `how-to-config.md`（开关表）+ `technical.md`（features.json 表、面板图）+ `testplan.md`。

---

## 4. 架构方案

### 4.1 分组模型：作用域主轴 + 生命周期独立字段

**核心决策：不把「实验」做成第四/第五个组，而是把「是否实验项」从 `group` 拆成独立布尔字段 `experimental`，分组只承载「作用域」。**

理由：当前 `group` 一个字段同时表达两件事（作用域 + 生命周期），这是 `GROUP_STANDARD` 成为杂物抽屉的根因——诊断类（作用域=机制）和读侧增强类（作用域=呈现）因为「都已转正、默认开」被塞进同一组。拆开后，作用域归分组、生命周期归 `experimental` 字段，两轴正交。

**四分组（作用域主轴，`GROUP_ORDER` 新序）：**

| 组常量 | 组标签 | 收编来源 | 项数 | 语义 |
|:---|:---|:---|:---|:---|
| `GROUP_PRESENTATION` | 📊 呈现与体验（默认开启） | `metrics_enabled`、`enable_interactive_charts` | 2 | 改报告「怎么看」，不新增分析内容 |
| `GROUP_ANALYSIS` | 🔍 分析增强·既有章内追加 | `GROUP_REPORT` 中的块/列/子表类 14 项 | 14 | 在既有章节里追加分析块/列/子表 |
| `GROUP_STANDALONE` | 📑 独立章节与回放 | `GROUP_REPORT` 中的整章/回放类 6 项 | 6 | 新增整页签/整章/多期回放 |
| `GROUP_MECHANISM` | ⚙ 机制与诊断（含实验） | 原 `GROUP_EXPERIMENTAL` 2 项 + `GROUP_STANDARD` 的诊断/接缝类 7 项 | 9 | 内部机制、诊断接缝、待验证实验 |

**项数恒等校验：2 + 14 + 6 + 9 = 31 ✓**（已用 venv 实测：覆盖全集、零重叠、零缺失）

**`GROUP_ORDER` 新序（需显式定义，面板编号与块序均由此派生）**：

```python
GROUP_ORDER = (GROUP_PRESENTATION, GROUP_ANALYSIS, GROUP_STANDALONE, GROUP_MECHANISM)
```

排序依据（**默认开启在前、默认关闭在后、实验收尾**，延续现面板「常规 9-17 默认开在前、报告 18-38 默认关在后、实验置首/机制收尾」的可读性原则）：

| 序 | 组 | 项数 | 默认态 | 置前/置后理由 |
|:---|:---|:---|:---|:---|
| 1 | `GROUP_PRESENTATION` | 2 | 全默认开 | 常驻、用户高频扫过，置最前 |
| 2 | `GROUP_ANALYSIS` | 14 | 4 开 / 10 关 | 主体内容、多为按需开，居中靠前 |
| 3 | `GROUP_STANDALONE` | 6 | 全默认关 | 新增整页签（重动作），置后 |
| 4 | `GROUP_MECHANISM` | 9 | 7 开 / 2 关 | 低频内部机制 + 实验项，收尾（实验项带 ⚗ 逐行标记，位置显但不抢占首屏） |

**默认态摘要（迭代 2 验收对照，`default` 恒等不变）**：全 31 项中默认开 = 呈现 2 + 分析 4（`llm_debate_conditional`/`data_quality`/`market_temperature`/`fund_purchase_limit`）+ 机制 7 = **13 项**；默认关 = 分析 10 + 独立 6 + 机制实验 2 = **18 项**。

**`GROUP_PRESENTATION`（2 项）：**
- `metrics_enabled`（量化指标显示）
- `enable_interactive_charts`（报告图表交互）

**`GROUP_ANALYSIS`（14 项，原 report 组的块/列/子表类）：**
`llm_debate_procon`、`llm_debate_conditional`、`factor_catalog`、`event_window_impact`、`data_quality`、`industry_beta`、`candidate_compare`、`cost_lots`、`valuation_percentile`、`market_temperature`、`market_sentiment`、`fund_purchase_limit`、`risk_adjusted_excess`、`summary_highlights`

**`GROUP_STANDALONE`（6 项，原 report 组的整章/回放类）：**
`financial_report_digest`（财报摘要章）、`financial_indicator`（财务指标章）、`holding_change_review`（持仓变动复盘章）、`rebalance_schedule_replay`（调仓回放章）、`whatif_trade_cost`（What-if 对比）、`crisis_replay`（危机双层回放）

**`GROUP_MECHANISM`（9 项）：**
- 实验类（`experimental=True`）：`decision_reflection`、`report_qa`
- 诊断/接缝类（`experimental=False`）：`deterministic_signal`、`prosperity_framework`、`module_quality_gate`、`decision_header_parse`、`datasource_credential_ready`、`doctor_check`、`datasource_adapter`

### 4.2 FeatureSwitchDef 字段扩展

```python
@dataclass(frozen=True)
class FeatureSwitchDef:
    label: str
    desc: str
    group: str          # 语义作用域：GROUP_PRESENTATION / GROUP_ANALYSIS / GROUP_STANDALONE / GROUP_MECHANISM
    default: bool
    affects_report: bool
    experimental: bool = False   # 生命周期：是否实验项（--experiment 取值域 = 此字段，不再看 group）
```

- `@dataclass(frozen=True)` 下新增带默认值字段必须排在无默认值字段**之后**，故 `experimental: bool = False` 置于末位。
- **实测事实**：31 项声明**全部为位置参数构造**（`label, desc, group, default, affects_report`，`group` 为第 3 个位置参数），故新增末位默认字段不破坏任何既有调用。但**重映射需逐项修改第 3 个位置参数**（`GROUP_*` 常量取值），共 31 处，不能只改常量名。
- 31 项声明中仅 `decision_reflection`/`report_qa` 两处需显式 `experimental=True`，其余 29 项依赖末位默认 `False`（省略）。验证：`set(k for k,d in registry.items() if d.experimental) == {"decision_reflection", "report_qa"}`。

### 4.3 生命周期判定解耦（`--experiment` 取值域与页脚自述）

**已核实：`features.py` 内恰有 4 处 `switches_in_group(GROUP_EXPERIMENTAL)` 消费，字段化后须全部改判 `d.experimental`（否则 `--experiment` 报错/取值错）**：

| 函数 | 现行 | 字段化改法 | 消费方 |
|:---|:---|:---|:---|
| `is_experimental_switch(flag)` | `d.group == GROUP_EXPERIMENTAL` | `bool(d and d.experimental)` | 内部判定 |
| `resolve_experiment_flags` | `all` 分支 `switches_in_group(GROUP_EXPERIMENTAL)` | `{k for k,d in registry.items() if d.experimental}` | CLI `--experiment all` |
| `describe_experiment_flags` | `switches_in_group(GROUP_EXPERIMENTAL)` | 同上字段推导 | CLI 帮助/报错提示 |
| `enabled_experimental_features` | `switches_in_group(GROUP_EXPERIMENTAL)` | 同上 + `is_feature_enabled(k)` | `--experiment` 日志 + 页脚自述 |

```python
def is_experimental_switch(flag: str) -> bool:
    """实验项判定 = 独立 experimental 字段（--experiment 取值域）。"""
    d = feature_switch_registry.get(flag)
    return bool(d and d.experimental)

# 同理 resolve_experiment_flags 的 `all` 分支、describe_experiment_flags、
# enabled_experimental_features 三处 switches_in_group(GROUP_EXPERIMENTAL)
# 一律改为 {k for k, d in feature_switch_registry.items() if d.experimental}
```

- `--experiment` 取值域 = `experimental=True` 的项（现为 `decision_reflection`/`report_qa` 2 项），**取值域集合不变**，只是判定来源从 `group==GROUP_EXPERIMENTAL` 改为 `d.experimental`。
- 页脚实验自述 `experimental_notice.py` 走 `enabled_experimental_features()`，**自述清单不变**。
- **转正语义更新**（写回 `features.py` 顶部注释）：四组下「转正」= 把 `experimental` 置 `False`（移出实验身份）；若作用域也变（如从机制类转为章节类）则同时改 `group`。转正不再必然伴随「离开实验块、落进常规块」的跨块位移，因为实验身份与作用域解耦。

### 4.4 TUI 面板渲染（`handlers_config.py`）

- 分块：`switch_blocks` 按 `GROUP_ORDER`（四组）派生，标题取 `GROUP_LABELS`；`next_serial` 连续派发逻辑不变（已核实 `handlers_config.py` 编号由分组循环派生、非硬编码，四组自动适配）；
- ⚗ 逐行标记：改为 `flag in experiment_flags`，其中 `experiment_flags = {k for k,d in registry.items() if d.experimental}`（与 group 无关）——只有 `decision_reflection`/`report_qa` 带 ⚗，落在「机制与诊断」块内；
- **面板标题**：`render_panel("配置 LLM 报告章节与功能开关", ...)` 需同步为与四组语义一致的标题（如「配置 LLM 报告章节与功能开关（四分组）」或保持现名但确认其仍准确——见迭代 2 验收）；
- **底部硬编码说明文案**：`handlers_config.py` 第 251-253 行硬编码三行（「常规开关默认开启…」「报告章节与增强默认多数关闭…」），四组后必须改写为四行或按 `GROUP_LABELS` 派生；
- 编号派生逻辑（`next_serial` 连续派发）不变，仅块数从 3 → 4。

### 4.5 Web 面板（`config_edit.py`）

**已核实硬编码**：`config_edit.py` 直接 import `GROUP_EXPERIMENTAL/STANDARD/REPORT`，并在下发 dict 中硬编码 `"experimental"`/`"standard"`/`"report"` 三个键（第 90-92 行），另第 71 行单独构造 `report_switches = {flag: ... for flag,_d in switches_in_group(GROUP_REPORT)}`。四组后：
- 下发 dict 键改为四组（`presentation`/`analysis`/`standalone`/`mechanism`），或改为按 `GROUP_ORDER` 动态派生（推荐，避免下次再硬编码）；
- `report_switches` 若前端依赖需同步（读 web/static 相关 JS 确认消费键后同步）；
- 前端模板/JS 的分组渲染若硬编码三组标题，需同步（迭代 2 验收覆盖 Web 面板走查）。

下发逻辑（显示名与 `affects_report`）不变。

### 4.6 GROUP_LABELS 新文案（组描述建议）

```python
GROUP_LABELS = {
    GROUP_PRESENTATION: "📊 呈现与体验（默认开启 · 只改呈现不改内容）",
    GROUP_ANALYSIS:     "🔍 分析增强·既有章内追加（默认关闭 · 在既有章节内追加分析块/列/子表）",
    GROUP_STANDALONE:   "📑 独立章节与回放（默认关闭 · 新增整页签或多期回放）",
    GROUP_MECHANISM:    "⚙ 机制与诊断（内部机制 / 诊断接缝 / 待验证实验）",
}
```

> 注：`GROUP_MECHANISM` 内 7 项机制/诊断类 `default=True`、2 项实验类 `default=False`，组内默认态混合，故标签不写死「默认关闭」，用中性表述。

---

## 5. 文档与文案触点清单

> **已核实完整受检域 = 20 份**（`check-doc-drift -v`）：10 手册 + 10 管理文档（changelog/review-findings 为历史记录类，不参与计数扫描，但 changelog 需追加 Added 条目）。三组措辞命中分布：`requirements.md`（19 处：R-WEB-08/R-DIAG-07/R-OUT-15/R-WIF-13/R-SR-05/R-FCT-05/R-EW-04/R-QA-01 + features.json 节两块）/`developer-guide.md`（9 处：新增开关指南四处「转正/分组/默认值」段 + 语义索引正向校验条目 + 分组计数断言条目）/`test-coverage.md`（3 处 unit 标记描述）/`how-to-use-tui-menu.md`（面板编号表）/`how-to-config.md`（开关表）/`technical.md`（features 表 + 面板图 + 语义命名表）/`testplan.md`/`llm-technical.md`/`how-to-use-cli-mode.md`（3）/`reports-instruction.md`（2）/`how-to-start.md`/`faq.md`/`how-to-config-llm.md`/`how-to-use-web-mode.md`。**迭代 3 必须逐文件扫过这 16 个命中文件**，不得只改 §5 首列示例。

| 触点 | 改动 |
|:---|:---|
| `config/features.py` | 组常量 4 个、`GROUP_LABELS`/`GROUP_ORDER`、`FeatureSwitchDef.experimental` 字段、31 项 group 重映射、`is_experimental_switch`/`enabled_experimental_features` 改判定、顶部注释转正语义 |
| `scripts/_doc_drift/_format.py` | `_group_counts`（四组）、`_TRIPLE_COUNT`→四组连写正则、`_GROUP_NAME_TO_KIND`（新增四组中文名）、`_GROUPED_COUNT`/`_REPORT_BLOCK_COUNT` 适配、`check_panel_numbering` 四段边界 |
| `src/python/tui/handlers_config.py` | 分块四组、`experiment_flags` 改 `d.experimental`、**面板标题 `render_panel(...)` 同步**、**底部三行硬编码说明改四组派生（迭代 2 必改）** |
| `src/python/web/config_edit.py` | **已核实硬编码三组**：import 三组常量 + 下发 dict 硬编码 `"experimental"/"standard"/"report"` 键（第 90-92）+ `report_switches`（第 71）；改为按 `GROUP_ORDER` 动态派生四组键 + 前端 JS/模板分组标题同步 |
| `docs/manuals/how-to-use-tui-menu.md` | `[S]` 面板编号表 `_PANEL_SECTION_*` 区段 → 四组边界；面板图；三组/31 项措辞 |
| `docs/manuals/how-to-config.md` | 开关表分组表头与计数措辞 |
| `docs/managements/technical.md` | features.json 表「实验组 2 + 常规组 9 + 报告组 20」→ 四组计数；`[S]` 面板图；语义命名表新增 `GROUP_PRESENTATION/ANALYSIS/STANDALONE/MECHANISM` slug |
| `docs/managements/testplan.md` | 面板编号表、用例计数（若增测试） |
| `docs/managements/developer-guide.md` | **HIGH：新增开关指南会教错**——「定分组与默认值」「覆盖三面」「实验性准入与转正判据」「内部接缝类开关转正」四段均基于两轴耦合旧模型（把作用域 + 生命周期耦合在单个 group 字段），四组后需重写为「先定作用域 group + 生命周期 experimental 两独立轴」；另语义索引正向校验条目 + 分组计数断言条目措辞同步 |
| `docs/managements/requirements.md` | **19 处三组措辞**：R-WEB-08（Web 三块 → 四块）/ R-DIAG-07 + R-OUT-15 + R-WIF-13 + R-SR-05 + R-FCT-05 + R-EW-04（「报告章节与增强组」→ 分析/独立两组，按 §4.1 归组逐条改）/ R-QA-01 + 报告对话式追问节（`report_qa`「实验组」→ 机制组+experimental）/ features.json 配置文件节（三块计数重写为四组）/ 配置键表 doctor_check 行 + 报告增强开关键表行 |
| `docs/managements/test-coverage.md` | 3 处 unit 标记描述（unit_config「分组默认值遵循生命周期/取值域仍为实验组」/ unit_cli / unit_web「实验组与常规组」）——迭代 4 若改对应测试描述需同步 |
| `docs/managements/changelog.md` | Added：分组重构条目（迭代 3 收尾补） |
| `src/test/unit/config/test_features.py` | **HIGH：`_experimental_flags()` 辅助（第 50-52）= `switches_in_group(GROUP_EXPERIMENTAL)`，被 ~6 用例引用（93/109/116/128/134/135）**——`GROUP_EXPERIMENTAL` 消失后必改写为 `{k for k,d in feature_switch_registry.items() if d.experimental}`；另第 25/28 行 import `GROUP_EXPERIMENTAL/STANDARD` 需改新常量。迭代 2 同步改（否则 `pytest src/test/unit/config` 直接 ImportError/误红） |
| `src/python/config/_core.py` | **约 10 处 docstring 提及 `GROUP_REPORT`**（`is_data_quality_enabled` 等访问器注释「登记于注册表 GROUP_REPORT 分组」）→ 改为 `GROUP_ANALYSIS`/`GROUP_STANDALONE` 按项归组（纯注释，不影响逻辑，属 doc-traces 一致性） |

**语义命名表澄清**：`GROUP_PRESENTATION/ANALYSIS/STANDALONE/MECHANISM` 作为**代码常量 slug 登记**（迭代 3）；`GROUP_LABELS`/`GROUP_ORDER` 不新增 slug（既有三组已未单独立 slug，仅常量重命名 + 新值，`check-semantic-index` 反向校验靠 `handlers_config.py`/`config_edit.py` 真实引用满足）。`features.py` 既有 `GROUP_EXPERIMENTAL/STANDARD/REPORT` 常量将被重命名，需同步清理其在 technical.md 正文的残留引用（写入分派「三组同一路径」措辞等）。注：`core/doctor.py` 亦有一处本地 `GROUP_ORDER`（自检七分类「环境/配置/…」），与本功能开关 `GROUP_ORDER` **无关、不冲突**，勿误改。

**语义命名表新增 4 slug（technical.md「功能语义命名表」章节）：**

| slug | 描述 | 类别 | config 键 |
|:---|:---|:---|:---|
| `GROUP_PRESENTATION` | 呈现与体验分组（改呈现不改内容） | 功能开关分组 | 无 |
| `GROUP_ANALYSIS` | 分析增强·既有章内追加分组 | 功能开关分组 | 无 |
| `GROUP_STANDALONE` | 独立章节与回放分组 | 功能开关分组 | 无 |
| `GROUP_MECHANISM` | 机制与诊断分组（含实验/诊断/接缝） | 功能开关分组 | 无 |

---

## 6. 分阶段实施计划（多迭代，每迭代含可验收标准）

> 顺序依赖：**迭代 1（守护脚本适配）必须先于迭代 2（注册表重映射）**。否则注册表一改，`check-doc-drift` 立即红。这是本次重构与历次改动最大的不同——守护脚本与实现必须原子协同，故拆为「先扩守护（兼容三/四组）→ 再切注册表 → 再刷文档」。

### 迭代 1：守护脚本适配四组（兼容三/四组双态）

- 交付：`scripts/_doc_drift/_format.py` 四组支撑；`_group_counts()` 返回四组；正则与 `check_panel_numbering` 支持四段；**在注册表仍为三组时，脚本不得误报**（向后兼容或按注册表实际组数动态适配）。
- **验收标准**：
  - [ ] `check-doc-drift.py --ci` 在注册表三组态下仍全绿（无回归）；
  - [ ] `_group_counts()` 键集 = 注册表 `GROUP_ORDER` 实际值（动态派生，不硬编码组名）；
  - [ ] `check_panel_numbering` 按注册表 `GROUP_ORDER` 组数动态分段（3 或 4 组均正确）；
  - [ ] `check-file-length.py --ci` 通过（`_format.py` 未破脚本红线）；
  - [ ] 无任务编号入标识符/注释（`check-code-traces` 干净）。

### 迭代 2：注册表重映射 + 生命周期字段

- 交付：`features.py` 四组常量、`FeatureSwitchDef.experimental` 字段、31 项 group/experimental 重映射、`is_experimental_switch`/`enabled_experimental_features` 改判定、顶部注释转正语义更新、`handlers_config.py`/`config_edit.py` 适配、**`test_features.py` 辅助 `_experimental_flags()` 字段化改写 + `GROUP_EXPERIMENTAL/STANDARD` import 改新常量**、`_core.py` docstring 归组注释。
- **验收标准**：
  - [ ] 31 项 key 集合**逐字节不变**（`set(registry.keys())` 前后相等断言）；
  - [ ] 每项 `default`/`affects_report` **前后逐项相等**（回归测试：新旧对照，或断言恒等表）；
  - [ ] 四组计数 2/14/6/9，总和 31（`assert sum == len(registry)`）；
  - [ ] `experimental=True` 恰为 `{decision_reflection, report_qa}`（`--experiment` 取值域不变）；
  - [ ] `is_feature_enabled` 全 31 项默认值前后不变（`get_feature_defaults()` 对照）；
  - [ ] 既有 `test_features.py` 全绿（注册表活性约束 `TestRegistryLiveness` 等）；**`test_features.py` 已改写 `_experimental_flags()` 为字段驱动，无 `GROUP_EXPERIMENTAL`/`GROUP_STANDARD` 残留 import（`pytest src/test/unit/config -q` 全绿、无 ImportError）**；
  - [ ] **全仓 `grep -rn "GROUP_EXPERIMENTAL\|GROUP_STANDARD\|GROUP_REPORT" src/ scripts/` 清零（旧三组常量名无残留，`_core.py` docstring 一并清）**；
  - [ ] TUI 面板四块渲染冒烟（`experiment_flags` 落在机制块内，仅 2 项带 ⚗）；**面板标题与底部说明文案已同步四组（无旧三组文案残留）**；
  - [ ] **Web `config_edit.py` 下发四组键 + 前端分组渲染正确，无三组硬编码残留**；
  - [ ] `pytest src/test/unit -q` 全绿。

### 迭代 3：文档触点刷新 + 语义命名登记

- 交付：§5 **20 份受检文档中 16 份命中文件逐一刷新**（重点 `requirements.md` 19 处 / `developer-guide.md` 9 处 / `test-coverage.md` 3 处）；technical.md 语义命名表 +4 slug；`testplan.md` 面板编号表；`changelog.md` Added。
- **验收标准**：
  - [ ] `check-doc-drift.py --ci` 全绿（四组计数、面板编号四段、目录树）；
  - [ ] **`developer-guide.md` 新增开关指南已重写为两轴模型（group 作用域 + experimental 生命周期），四段（定分组与默认值/覆盖三面/实验性准入与转正判据/内部接缝类开关转正）无旧三组模型残留**；
  - [ ] **`requirements.md` 19 处三组措辞全部按本文（feature-switch-grouping-redesign.md）§4.1 归组改毕（R-WEB-08 四块 + features.json 节四组计数）**；
  - [ ] `check-semantic-index.py --ci` 全绿（4 新 slug 正反向一致）；
  - [ ] `check-doc-links.py --ci` + `check-version-consistency.py --ci` + `check-requirement-trace.py --ci` 全绿；
  - [ ] 手册 `how-to-use-tui-menu.md` `[S]` 编号表四段边界与注册表一致。

### 迭代 4：端到端回归 + 场景门禁

- 交付：mock LLM 下 TUI `[S]` 面板完整走查 + Web 配置面板走查 + 转正迁移演练（临时把某项 `experimental` 置 True/False 验证取值域与自述联动，测后还原）。
- **验收标准**：
  - [ ] `pytest src/test/unit -q` 全绿；
  - [ ] TUI `[S]`：四块标题正确、编号连续无缺、⚗ 仅 2 项、开关联动 `features.json` 落盘；
  - [ ] Web 配置面板：四分组下发、标签一致；
  - [ ] `--experiment report_qa` / `--experiment decision_reflection` 解析成功，`--experiment <机制类>` 被拒（取值域正确）；
  - [ ] 页脚实验自述（`experimental_notice`）仅列 2 实验项；
  - [ ] `scripts/check-code-traces.py --ci` + `check-doc-traces.py --ci` + `check-task-numbering.py --ci` + `check-semantic-index.py --ci` + `check-doc-drift.py --ci` + `check-test-redundancy.py --ci` + `check-requirement-trace.py --ci` + `check-version-consistency.py --ci` + `check-doc-links.py --ci` + `check-file-length.py --ci` 十守护全绿。

---

## 7. 风险管理

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| **R1 守护脚本与注册表改不同步** | 迭代 2 一改注册表，`check-doc-drift` 立即红，提交被钩子中止 | 强制顺序：迭代 1 先让脚本兼容四组（且三组态不误报），迭代 2 再切注册表；两迭代间不得提交半成品 |
| **R2 `--experiment` 取值域意外扩大 / 漏改调用点** | 若把 7 机制类也标 `experimental=True`，`--experiment` 多出 7 个合法令牌；若漏改 4 处 `switches_in_group(GROUP_EXPERIMENTAL)` 之一（`resolve_experiment_flags` 的 `all` 分支 / `describe_experiment_flags` / `is_experimental_switch` / `enabled_experimental_features`），该处 `GROUP_EXPERIMENTAL` 名消失后直接 AttributeError 或取值错 | `experimental` 字段显式只给 2 项；迭代 2 验收断言取值域集合不变；**grep 全仓 `GROUP_EXPERIMENTAL` 清零（无残留 import）**；`--experiment all` / `--experiment <机制类>`（应拒）双验 |
| **R3 页脚实验自述意外变化** | 报告产物字节变化，违反「零行为变化」 | `enabled_experimental_features` 改判定后，断言自述清单 = 2 项；关态产物逐字节不变 |
| **R4 `default`/`affects_report` 误动** | 产物行为变化 | 迭代 2 验收逐项恒等断言 + 回归测试 |
| **R5 手册编号表大面积重排** | 老用户肌肉记忆作废、文档触点多 | 保持编号连续派生逻辑不变，仅块边界变；手册用脚本派生编号而非手写 |
| **R6 `GROUP_MECHANISM` 标签默认值表述** | 该组内 7 开 2 关，写「默认关闭」不准确 | 标签用中性表述，不写死默认值 |
| **R7 `_format.py` 逼近脚本红线** | 触发文件长度红线 finding | 迭代 1/3 均跑 `check-file-length`；必要时把面板检查逻辑拆到 `scripts/_doc_drift/` 子模块 |
| **R8 转正语义文档与实现漂移** | `features.py` 顶部注释仍讲旧三组转正 | 迭代 2 同步更新顶部注释 + technical.md 转正说明 |
| **R9 Web `config_edit.py` 硬编码三组** | 下发 dict 硬编码三组键 + import 三组常量 + `report_switches`，漏改则 Web 面板分组错位或 KeyError | 迭代 2 明确改 `config_edit.py` 为按 `GROUP_ORDER` 动态派生；读 web/static JS/模板确认分组渲染消费键；迭代 4 验收含 Web 面板走查 |
| **R10 developer-guide 新增开关指南教错模型** | 「定分组与默认值」「覆盖三面」「实验性准入与转正判据」「内部接缝类开关转正」四段把「作用域 + 生命周期」耦合在单个 group 字段，四组后开发者照旧指南加开关会落错组、漏标 experimental | 迭代 3 重写为两轴模型（group 定作用域、experimental 定生命周期），四段逐段改；验收 grep 无「实验组 + False」耦合措辞 |
| **R11 既有测试断言依赖三组划分** | `test_features.py::test_experiment_group_excludes_standard_switches` 等若断言「组名 ↔ 实验性」耦合关系，移组后误红 | 迭代 2 跑 `pytest src/test/unit/config -v` 逐条核对；断言改为基于 `experimental` 字段而非 group 名（`is_experimental_switch` 已改字段驱动，该用例应自然存活） |

---

## 8. 交付物清单总览

| 迭代 | 代码 | 测试 | 文档 |
|:---|:---|:---|:---|
| 1 | `scripts/_doc_drift/_format.py`（四组适配） | `src/test/unit/scripts/` drift 相关用例（三/四组双态） | — |
| 2 | `config/features.py` + `tui/handlers_config.py` + `web/config_edit.py` + `config/_core.py`（docstring） | `src/test/unit/config/test_features.py`（key/default/取值域恒等 + 四组计数 + `_experimental_flags()` 字段化改写 + `GROUP_EXPERIMENTAL` import 清零） | `features.py` 顶部注释 |
| 3 | — | — | **16 份命中文档**（requirements 19 处 + developer-guide 9 处 + test-coverage 3 处 + 手册 + technical.md + testplan + llm-technical）+ changelog Added |
| 4 | 转正迁移演练（临时改、测后还原） | TUI/Web 冒烟 + 十守护 | — |
