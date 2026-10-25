# 定价按官方币种原样计价（不做汇率折算）

## 背景

外币厂商（Anthropic / OpenAI / Google）的 USD 官方价一度按固定汇率折算成人民币写进 `MODEL_PRICING`，理由是「报告里所有费用要能相加」。

问题：汇率是每天变的市场量，写死在代码里必然滞后；而且折算值既不是官方标价也不是账单，用户看到 `¥13.44`（Sonnet 5.5 输入）无法与官方 `$2` 对上，也不知道用了哪天汇率。

## 目标

- 每个模型按**其官方标价币种**计价与展示：DeepSeek / Kimi 显示 `¥`，Claude / OpenAI / Gemini 显示 `$`。
- 代码里**不出现汇率**，不做任何跨币种换算。
- 跨币种金额**不相加**，改为按币种分组并列展示（`¥0.0123 + $0.0045`）。

## 设计

### 1. 定价表

- `MODEL_PRICING` 条目新增可选 `currency` 字段；缺省取 `PRICING_CURRENCY`（默认 `CNY`）。
- 外币厂商条目写官方原值 + `"currency": "USD"`；表内不出现任何汇率常量与折算函数。
- 峰谷 `peak` 子段沿用所属模型的币种（仅 DeepSeek 使用，本币 CNY）。

### 2. 计价与展示（配置币种优先）

- 新增 `pricing.model_currency(model) -> str`：解析「配置币种（若条目用 `alt` 提供该币种价）→ 原生币种」，与 `compute_cost_value` 共用 `_resolve_entry`。
- 条目可用 `alt` 子表提供另一币种官方价（如国内渠道以人民币计价）——**配置币种优先**；只提供原生币种时按原生币种显示。
- `estimate_cost()` 的符号由**模型生效币种**决定（`model_currency` 解析结果）。
- 新增金额聚合原语（同模块内）：`add_cost(costs, currency, amount)` / `merge_costs(a, b)` / `format_costs(costs, digits=4)`。
  - `format_costs({"CNY": 0.0123, "USD": 0.0045})` → `"¥0.0123 + $0.0045"`；单币种时与原格式一致。

### 3. 聚合口径

会话用量 `llm/session.py`：

- `total_cost: float` + `currency: str` 改为 `costs: dict[str, float]`（币种 → 金额）。
- `per_module[module]["cost"]` 旁增 `currency`（该模块模型币种）。
- `format_session_usage()` 输出 `cost_by_currency` 与 `cost_display`（分币种并列）。

下游同步（一律按币种分组，跨币种不相加）：

| 位置 | 变化 |
|------|------|
| `report/summary_llm_usage.py` | 模块明细费用按该模块币种取符号；累计费用读 `cost_display` |
| `report/_generation_shared.py` | perf 上下文的 `total_cost` → `cost_by_currency` + `cost_display` |
| `tui/tui.py`、`tui/tui_handlers.py` | 会话摘要/结束行改为分币种并列展示 |
| `llm/cost_forecast.py` | 预估区间 `low`/`high` → 逐币种 `costs: {币种: {low, high}}`；`currency`/`symbol` 字段改为 `cost_display` |

### 4. 参考文件

`data/config/llm_pricing_ref.json`：

- 顶层 `currency` 语义改为「模型条目未声明 `currency` 时的缺省币种」。
- `models.<model>` 支持 `currency` 覆盖，取值限定在 `CURRENCY_SYMBOLS` 白名单内，非法值告警跳过该条。

### 5. 已确认的口径

- **日费用预算**：**一个数字**，币种即本地主币种；判定超限时用内部汇率表 `FX_TO_CNY` 把各币种支出折算到该币种比对，**折算只参与判定，绝不进入展示金额**；缺汇率的币种列入 `unconvertible` 并点名，不按 0 静默计。
- **币种旋钮收敛为一处**：`currency` 只回答「多币种价选哪套 + 预算币种」；`MODEL_PRICING` 每条显式声明 `currency`（CNY 厂商也写），条目缺 `currency` 时回落常量缺省而非配置值——改配置不会改变条目自身标价币种。
- **历史费用摘要**（`core/perf.module_cost_summary`、`[S]` 面板、`estimate_cached_saving`）：按币种**分组展示**，不同币种历史样本不混算；预估只取「当前模型币种」的样本，跨币种无样本时回落静态单价。

## 影响面

代码：`core/constants.py`、`llm/pricing.py`、`config/_llm_pricing.py`、`llm/session.py`、`llm/cost_forecast.py`、`core/perf.py`、`report/summary_llm_usage.py`、`report/_generation_shared.py`、`report/cli_progress.py`、`tui/tui.py`、`tui/tui_handlers.py`。

文档：`llm-technical.md`（§10 定价、附录 B 增币种列）、`how-to-config-llm.md`（定价表增币种列、覆盖示例）、`datasource*.md` 无涉及、`changelog.md`。

测试：定价币种匹配、`estimate_cost` 符号、`format_costs` 多币种、会话聚合、预估区间、预算与历史摘要口径；全部浮动断言用 `pytest.approx`。

## 验收

- 代码库内 `grep USD_CNY` 无命中；无任何跨币种加法。
- 单模型币种报告与官方标价一一对应（Claude 显示 `$`，DeepSeek 显示 `¥`）。
- 混用模型（如 `global_macro` 用 DeepSeek、`expert_review` 用 Claude）时报告显示两条币种金额，不出现「折算合计」。
