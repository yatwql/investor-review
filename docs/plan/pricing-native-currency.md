# 定价按官方币种原样计价（不做汇率折算）

## 目标

- 每个模型按其**官方标价币种**计价与展示：DeepSeek / Kimi 显示 `¥`，Claude / OpenAI / Gemini 显示 `$`。
- 代码里**不出现用于展示的汇率**，不做任何跨币种换算。
- 跨币种金额**不相加**，按币种分组并列展示（`¥0.0123 + $0.0045`）。

## 设计

### 1. 定价表

- `MODEL_PRICING` 每条显式声明 `currency`（含 CNY 厂商）；峰谷 `peak` 子段沿用所属模型币种。
- 条目可用 `alt` 子表提供另一币种官方价（如国内渠道以人民币计价）。

### 2. 计价与展示（配置币种优先）

- `pricing.model_currency(model)`：解析「配置币种（若条目 `alt` 提供）→ 原生币种」，与 `compute_cost_value` 共用 `_resolve_entry`。
- `estimate_cost()` 的符号由**模型生效币种**决定。
- 金额聚合原语：`add_cost` / `merge_costs` / `format_costs`（`format_costs({"CNY": 0.0123, "USD": 0.0045})` → `"¥0.0123 + $0.0045"`）。

### 3. 聚合口径

会话用量 `llm/session.py` 的 `costs: dict[str, float]`（币种 → 金额）；`per_module[module]["costs"]` 同结构；`format_session_usage()` 输出 `cost_by_currency` 与 `cost_display`。

下游按币种分组、跨币种不相加：`report/summary_llm_usage.py`（模块明细按该模块币种）、`report/_generation_shared.py`（perf `cost_by_currency`）、`tui/tui.py` 与 `tui/tui_handlers.py`（分币种并列）、`llm/cost_forecast.py`（预估逐币种 `costs: {币种: {low, high}}`）。

### 4. 参考文件

`data/config/llm_pricing_ref.json`：顶层 `currency` = 缺省币种（默认 CNY）；`models.<model>` 支持 `currency` 覆盖，取值限定白名单，非法值告警跳过该条。

### 5. 已确认的口径

- **日费用预算**：一个数字，币种即本地主币种；判定超限时用内部汇率表 `FX_TO_CNY` 折算比对，**折算只参与判定，不进展示金额**；缺汇率的币种列入 `unconvertible` 并点名，不按 0 静默计。
- **币种旋钮收敛为一处**：`currency` 只回答「多币种价选哪套 + 预算币种」；条目缺 `currency` 时回落常量缺省而非配置值。
- **历史费用摘要**（`core/perf.module_cost_summary`、`[S]` 面板、`estimate_cached_saving`）：按币种分组，不同币种样本不混算；预估只取当前模型币种的样本。

## 验收

- 代码库内无跨币种换算函数、无跨币种加法。
- 单模型币种与官方标价一一对应（Claude `$`、DeepSeek `¥`）。
- 混用模型时报告并列两条币种金额，不出现「折算合计」。
- 契约测试：`test_pricing_currency.py`（原生展示/配置优先/分组聚合/预算折算只判定）、`test_cache_fingerprint_alignment.py` 中的多币种桶用例。
