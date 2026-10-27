# LLM 参考附录

本文件是 [LLM 配置指引](how-to-config-llm.md) 的参考附录：**逐家 provider 的配置示例**与**完整模型定价表**。主篇讲“怎么配、配哪项”，这里查“某家服务商具体怎么写”“某个模型怎么计价”。

## 目录

- [支持的 provider 及配置示例](#支持的-provider-及配置示例)
- [完整模型定价表](#完整模型定价表)

## 支持的 provider 及配置示例

以下示例的**凭据块**写入 `data/config/llm_key.json`，**provider 类型与线路**写入 `data/config/llm_providers.json`（每条线路用 `credentials_ref` 指向凭据块键名），非敏感参数仍在 `llm_settings.json` 中管理。

<details>
<summary><b>Claude（Anthropic 官方）</b></summary>

```json
// llm_key.json
{
  "claude-main": {
    "api_key": "sk-ant-your-key",
    "model": "claude-sonnet-4-20250514",
    "endpoint": "https://api.anthropic.com/v1/messages"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "claude-main",
  "provider": "claude",
  "credentials_ref": "claude-main",
  "priority": 10,
  "timeout": 120
}
```

可用模型：`claude-sonnet-4-20250514`（推荐）、`claude-haiku-4-20250514`（高性价比）、`claude-opus-4-20250514`（强推理）
</details>

<details>
<summary><b>OpenAI</b></summary>

```json
// llm_key.json
{
  "openai-main": {
    "api_key": "sk-your-key",
    "model": "gpt-4o",
    "endpoint": "https://api.openai.com/v1/chat/completions"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "openai-main",
  "provider": "openai",
  "credentials_ref": "openai-main",
  "priority": 10,
  "timeout": 120
}
```

可用模型：`gpt-4o`（推荐）、`gpt-4o-mini`（轻量）、`o3-mini`（推理）
</details>

<details>
<summary><b>DeepSeek（Anthropic 兼容端点 — 推荐）</b></summary>

DeepSeek 官方提供 Anthropic API 兼容端点，`provider` 设为 `"claude"` 即可调用。

```json
// llm_key.json
{
  "claude-main": {
    "api_key": "sk-your-deepseek-key",
    "model": "deepseek-v4-flash",
    "endpoint": "https://api.deepseek.com/anthropic/v1/messages"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "claude-main",
  "provider": "claude",
  "credentials_ref": "claude-main",
  "priority": 10,
  "timeout": 120
}
```

- API Key 使用 DeepSeek 官方 Key（带 `sk-` 前缀）
- 模型：`deepseek-v4-flash`（推荐，**注意全小写**）、`deepseek-flash`（DeepSeek-V4.1-Flash 正式模型名，2026-09-10 发布，与前者同价）
- **已停用模型名**：`deepseek-chat` / `deepseek-reasoner` 曾是 flash 系列非思考 / 思考模式的兼容别名（**不是**独立的 V3 模型），已于 2026-07-24 下线且端点不再接受。本程序对旧名**不再做任何兼容**：不收录价格表（历史报告费用按未知模型显示 `-`）、不收录思考名单，请一律改用 `deepseek-flash`
- **注意**：`deepseek-v4-pro` 官方 2026-09-10 公告继续提供 API 服务（2026-09-14 之后不下线），计费方式不变；`deepseek-v4-flash` 与 `deepseek-v4-flash-vision-exp` 底层模型同样由 V4.1-Flash 接管，价格不变。费用估算以 `core/constants.py` 的 `MODEL_PRICING` 为准
- 官方文档：https://api-docs.deepseek.com/guides/anthropic_api
</details>

<details>
<summary><b>Kimi（月之暗面开放平台，Anthropic 兼容端点）</b></summary>

Kimi 开放平台提供 Anthropic API 兼容端点，`provider` 设为 `"claude"` 即可调用。

```json
// llm_key.json
{
  "claude-main": {
    "api_key": "sk-your-kimi-key",
    "model": "kimi-k2.6",
    "endpoint": "https://api.moonshot.cn/anthropic/v1/messages"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "claude-main",
  "provider": "claude",
  "credentials_ref": "claude-main",
  "priority": 10,
  "timeout": 120
}
```

- API Key 在 [Kimi 开放平台](https://platform.moonshot.cn)控制台创建（按量付费）。注意与 **Kimi Code 订阅的 Key 不通用**——后者仅限编程工具的交互式场景，用于本工具的批量报告生成会触发限流
- 可用模型：`kimi-k2.6`（推荐，256k 上下文，支持思考/非思考模式）、`kimi-k3`（旗舰，1M 上下文）
- Extended Thinking 走 `thinking.budget_tokens`（与 Claude 同机制）；端点默认开思考，模块未开启时本工具会显式发送 `disabled`

> **想改用 Kimi Code 订阅 Key？** 两套系统的端点与模型名不同（Code 为 `api.kimi.com/coding/` + `kimi-for-coding`），
> 直接照抄本段会 401。完整改法见下个折叠块「Kimi Code（订阅会员）」——包含两个文件的改法、`pacing` 推荐值、403 语义与**风险提示**。
</details>

<details>
<summary><b>Kimi Code（订阅会员，Anthropic 兼容端点）</b></summary>

> ⚠️ **先读风险提示**：Kimi Code 官方社区准则明确 **“Don't use Kimi Code for non-interactive automation”**
> （“订阅仅限个人交互式使用；脚本化批量执行、数据标注流水线等非交互用途超出正常使用范围”）。
> 本工具的批量报告生成属于**非交互式自动化**，因此：
> - 用 Kimi Code Key 跑本工具**在合规性上有风险**，`pacing` 只能降低被风控检出的概率，**不能消除风险**；
> - 违规处置可能是 **403 `You've reached your concurrent request limit`**（风控触发，只能申诉）；
> - **长期稳定跑自动化建议用开放平台按量付费 Key**（无此条款）；订阅 Key 更适合留给 Claude Code / CLI 等交互式编码场景。

**与开放平台的关键差异（最容易踩的三个坑）**

| 项 | 开放平台 | **Kimi Code 订阅** |
|---|---|---|
| Base URL | `https://api.moonshot.cn/anthropic/v1/messages` | **`https://api.kimi.com/coding/v1/messages`** |
| Key 来源 | platform.moonshot.cn 控制台 | **Kimi Code 控制台**（kimi.com/code/console） |
| 模型名 | `kimi-k2.6` / `kimi-k3` | **`kimi-for-coding`**（标准）/ `kimi-for-coding-highspeed`（高速）/ `k3` |
| 计费 | 按量付费（token 计费） | 会员订阅额度（**不按 token 计费**） |

两套系统的 **Key 与端点互不通用**——混用会 401 `Invalid Authentication`。
**模型名务必改**：保留 `kimi-k2.6` 去请求 Code 端点会报 `Your model id does not exist, recognized as other:`。

**启用步骤（改两个文件，不改代码）**

**步骤 1** — `data/config/llm_key.json`（本地密钥文件，**不入库**）追加凭据块，保留原有按量付费块便于切回：

```jsonc
{
  // …原有 kimi-main / deepseek-main 保持不变…

  // Kimi Code 订阅（Anthropic 兼容端点；模型名与开放平台不同！）
  "kimi-code": {
    "api_key": "sk-替换为 Kimi Code 控制台新建的 Key",
    "model": "kimi-for-coding",
    "endpoint": "https://api.kimi.com/coding/v1/messages"
  }
}
```

**步骤 2** — `data/config/llm_providers.json`（路由配置，**已入库**，无密钥）把主 Provider 换成 `kimi-code` 并收紧节流：

```jsonc
{
  "strategy": "priority",
  "preferred_providers": {},
  "providers": [
    {
      "name": "kimi-code",
      "provider": "claude",
      "credentials_ref": "kimi-code",
      "priority": 10,
      "timeout": 120,
      // 订阅制端点：低频串行，降低风控风险（见上文「端点级节流」）
      "pacing": { "min_interval": 20, "jitter": 0.2, "max_concurrency": 1 }
    },
    {
      "name": "deepseek-main",
      "provider": "claude",
      "credentials_ref": "deepseek-main",
      "priority": 20,
      "timeout": 120
    }
  ]
}
```

> **备选 Provider 建议保留**：一旦 Code 端点返回 403（配额/风控），程序会自动降级到 `deepseek-main`，报告不会因端点被限流而空白。

**步骤 3** — 验证：

```bash
.venv/bin/python -m src.python.cli doctor --offline      # 配置合法性自检（不发起 LLM 调用）
.venv/bin/python -m src.python.cli report --type full    # 跑一次含 LLM 的报告
.venv/bin/python -m src.python.cli view-logs --level INFO   # 观察 provider 尝试与节流
# 日志应出现：尝试 provider: kimi-code(claude/kimi-for-coding) [https://api.kimi.com/coding/v1/messages]
# 已声明 pacing 时，相邻两次 API 请求的日志时间戳间隔应 ≥ min_interval
```

**`pacing` 推荐值**

| 参数 | 推荐值 | 说明 |
|---|:---:|---|
| `min_interval` | `20` | 两次请求最小间隔（秒）。按「每次报告约 9 次调用」估算，串行 + 20s ≈ 3 分钟额外等待，换来最低频次 |
| `jitter` | `0.2` | 间隔随机抖动 ±20%，避免固定节奏的机器特征 |
| `max_concurrency` | `1` | 该端点**在途**请求上限 1（配合全局 `llm_max_concurrency` 3，只有本端点被串行化） |

**想更保守**：`min_interval` 提到 `30~60`，并把 `llm_settings.json` 的 `llm_max_concurrency` 降到 `1~2`（全局串行）。
**想恢复放开**：删掉 `pacing` 段即可——无 `pacing` 声明的端点零约束（这对按量付费端点也适用，它有明确的分级 RPM/TPM）。

**与「403 配额/风控」的交互**

程序已按订阅端点语义区分状态码：

| 状态码 | 含义 | 程序行为 |
|---|---|---|
| **403** | 配额/风控拒绝（5 小时窗口、并发上限、月度额度） | **不重试**，直接降级下一 Provider；报告显示「LLM 端点配额/风控限制已触发」 |
| **429** | 瞬时限流（配额/风控终态） | **不重试**：首试即长冷却熔断该端点 600s，日志回显两级并发配置并自动降级下一 Provider |
| **503** | 服务端过载 | 按 `max_retries`（默认 2）退避重试 |
| **401** | Key 与 Base URL 不配套 | 认证失败，不重试；核对步骤 1/2 |

> 403 **不重试**是刻意设计：配额窗口按时间滚动（非瞬时故障），重试无益且高频重试会加剧风控画像。429 同归 `quota` 终态（限速即配额/风控信号）：首试即 600s 长冷却熔断、零退避重试，避免无效请求与日志噪音。

**换 Key 后仍会看到的两处「无害提示」**

| 现象 | 原因 | 处理 |
|---|---|---|
| 报告「LLM 用量」页签费用显示 **`-`** | `kimi-for-coding` 不在内置计价表，且订阅制**不按 token 计费**，费用无意义 | 可不处理（`-` 即「未计价」）。若要显示参考值，在 `llm_pricing_ref.json` 的 `models` 中自填等效单价 |
| 请求偶发较慢 | 订阅端点高峰时段（工作日 14:00–17:00）偶发 `429 The engine is currently overloaded`（服务端容量，与账号无关） | 程序首试即熔断该端点 600s 并降级下一 Provider（不退避重试）；避开高峰更稳，或为该条目配置 `pacing.min_interval` 降低请求频率 |
</details>

<details>
<summary><b>DeepSeek（OpenAI 兼容格式）</b></summary>

```json
// llm_key.json
{
  "openai-main": {
    "api_key": "sk-your-deepseek-key",
    "model": "DeepSeek-V4-Flash",
    "endpoint": "https://api.deepseek.com/v1/chat/completions"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "openai-main",
  "provider": "openai",
  "credentials_ref": "openai-main",
  "priority": 10,
  "timeout": 120
}
```
</details>

<details>
<summary><b>火山引擎（豆包）</b></summary>

```json
// llm_key.json
{
  "openai-main": {
    "api_key": "your-volcengine-key",
    "model": "doubao-pro-32k",
    "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "openai-main",
  "provider": "openai",
  "credentials_ref": "openai-main",
  "priority": 10,
  "timeout": 120
}
```

获取方式：火山引擎方舟控制台 → 推理接入点 → 创建接入点。
</details>

<details>
<summary><b>Gemini（Google）</b></summary>

```json
// llm_key.json
{
  "gemini-main": {
    "api_key": "AIzaSyYourGeminiKey",
    "model": "gemini-2.5-flash",
    "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
  }
}
```

```json
// llm_providers.json（providers 数组中的一条）
{
  "name": "gemini-main",
  "provider": "gemini",
  "credentials_ref": "gemini-main",
  "priority": 10,
  "timeout": 120
}
```

- API Key 使用 Google AI Studio 生成的 Gemini API Key
- 可用模型：`gemini-2.5-flash`（推荐，高性价比）、`gemini-2.5-pro`（强推理）
- 认证方式为 `x-goog-api-key` header，非 Bearer token
- 适用于多 Provider 链式服务中作为低成本备选
</details>

---


## 完整模型定价表

代码内置所有支持模型的 Token 定价，**按厂商官方标价币种原样记录**（不做汇率折算）：

| 模型 | 币种 | 输入/M | 输出/M | 缓存命中/M | 说明 |
|------|:----:|:----:|:----:|:--------:|------|
| `claude-sonnet-5-5` | USD | 2.00 | 10.00 | 0.10 | Claude 现役主力（官方 $/M） |
| `claude-opus-5-5` | USD | 4.00 | 20.00 | 0.20 | Claude 现役旗舰推理，适合智囊团等复杂分析 |
| `claude-haiku-5-5` | USD | 0.10 | 0.50 | 0.01 | Claude 现役轻量（单次输入 ≤100K token） |
| `claude-sonnet-5` | USD | 2.00 | 10.00 | 0.20 | 上一代 Sonnet（legacy） |
| `claude-sonnet-4-6` | USD | 3.00 | 15.00 | 0.30 | 上一代 Sonnet（legacy） |
| `claude-opus-4-8` | USD | 5.00 | 25.00 | 0.50 | 上一代 Opus（legacy） |
| `claude-haiku-4-5` | USD | 1.00 | 5.00 | 0.10 | 上一代轻量（legacy） |
| `claude-fable-5-1` | USD | 10.00 | 50.00 | 0.25 | Claude 顶级推理与长程 agent 任务 |
| `claude-fable-5` | USD | 10.00 | 50.00 | 1.00 | 上一代顶级（legacy） |
| `gpt-6.1-sol` | USD | 2.00 | 10.00 | 0.10 | OpenAI 现役主力 |
| `gpt-6-luna` | USD | 0.10 | 0.50 | 0.01 | OpenAI 现役轻量 |
| `gpt-6-astra` | USD | 10.00 | 50.00 | 1.00 | OpenAI 旗舰推理 |
| `gpt-5.6-sol` | USD | 4.00 | 20.00 | 0.40 | 上一代主力 |
| `gpt-4o` | USD | 2.50 | 10.00 | 1.25 | 早期主力（legacy，缓存 50% 折扣） |
| `gpt-4o-mini` | USD | 0.15 | 0.60 | 0.075 | 早期轻量（legacy） |
| `deepseek-v4-flash` | CNY | 1.00 / 2.00 | 4.00 / 8.00 | 0.02 / 0.04 | ⭐ 高性价比推荐，默认模型（峰谷定价，闲时/高峰；2026-09-10 降价） |
| `deepseek-flash` | CNY | 1.00 / 2.00 | 4.00 / 8.00 | 0.02 / 0.04 | DeepSeek-V4.1-Flash 正式模型名（与 v4-flash 同价同底层） |
| `deepseek-v4-pro` | CNY | 4.50 / 9.00 | 13.50 / 27.00 | 0.15 / 0.30 | DeepSeek 增强推理（峰谷定价，闲时/高峰） |
| `gemini-3.8-flash` | USD | 0.75 | 3.75 | 0.075 | Gemini 现役主力（2026-12-31 前优惠价） |
| `gemini-3.1-pro` | USD | 2.00 | 12.00 | 0.20 | Gemini 强推理（preview） |
| `gemini-2.5-flash` | USD | 0.30 | 2.50 | 0.03 | Gemini 上一代主力（legacy） |
| `gemini-2.5-pro` | USD | 1.25 | 10.00 | 0.125 | Gemini 上一代强推理（legacy） |
| `kimi-k3.1-pro` | CNY | 13.00 | 68.00 | 1.30 | Kimi 现役旗舰（1M 上下文） |
| `kimi-k3.1-pro-highspeed` | CNY | 26.00 | 136.00 | 1.30 | Kimi 现役旗舰高速档 |
| `kimi-k3` | CNY | 20.00 | 100.00 | 2.00 | Kimi 上一代旗舰（1M 上下文） |
| `kimi-k2.6` | CNY | 6.50 | 27.00 | 1.10 | Kimi 通用主力（256k 上下文，支持思考模式） |

> **缺省币种（本地主币种）**：`llm_pricing_ref.json` 顶层 `currency`（默认 `CNY`）。语义只有两个——**模型同时提供多币种价时选哪一套**（条目 `alt` 子表提供该币种官方价即命中），以及**日预算以哪个币种判定**。它**不决定条目自身币种**：`MODEL_PRICING` 每条都显式声明了 `currency`，所以把本项改成 `USD` 也不会给人民币标价的模型贴上 `$`。

> **币种与显示口径**：每条定价按**厂商官方标价币种**原样记录（DeepSeek / Kimi 为 CNY，Anthropic / OpenAI / Google 为 USD），**代码里没有任何汇率折算**。
> - 报告、TUI、Web 的金额一律按**该模型生效币种**显示（Claude 出 `$`、DeepSeek 出 `¥`）；
> - 一次报告里混用不同币种模型时，费用**分组并列**显示（如 `¥0.0123 + $0.0045`），从不相加；
> - 若某模型你手上有另一币种的官方价（如国内渠道以人民币计价），可在 `llm_pricing_ref.json` 里用 `alt` 子表或直接把该模型条目改成你配置的币种——**配置币种优先**，模型同时提供多币种价时按你配置的币种显示；
> - 日费用预算 `daily_cost_limit`（一个数字，本地主币种）是唯一使用内部汇率的地方：各币种支出折算后比对，仅用于判定超限，**不改变任何展示金额**。

> 表中为具体模型名；`core/constants.py::MODEL_PRICING` 另有 12 条**模型族前缀兜底价**（`claude-fable-5-` / `claude-opus-5-` / `claude-sonnet-5-` / `claude-haiku-5-` / `claude-sonnet-4-` / `claude-opus-4-` / `claude-haiku-4-` / `gpt-6.1-` / `gpt-5.6-` / `gemini-3.8-` / `gemini-3.1-` / `gemini-2.5-`），供带日期/小版本后缀的未列变体（如 `claude-sonnet-5-5-20260928`）按族价自动计价——表中不单列，也不会覆盖已有的具体模型价。

> **峰谷定价（DeepSeek）**：`deepseek-flash` / `deepseek-v4-*` 采用 DeepSeek 官方峰谷定价（2026-08-17 起生效，2026-08-23 起优化周末规则，2026-09-10 起 flash 系列降价并补充法定节假日规则），表中「闲时/高峰」两列分别为非高峰与高峰时段的每百万 Token 单价。**高峰时段仅在高峰日（周一至周五，不含中国法定节假日）生效**，为**北京时间 09:00–12:00、14:00–18:00**；高峰日其余时间为闲时、**周末（周六/周日）与法定节假日全天一律按闲时价计费**（不区分峰谷，闲时价 = 高峰价的一半）。时段、判定时区与周末/法定节假日规则可在 `llm_pricing_ref.json` 的 `peak_periods` / `idle_periods` / `timezone` / `weekend_always_idle` / `holiday_always_idle` 中覆盖；含 `"peak"` 子段的模型高峰日高峰时段按 `peak` 价计费，其余时段（含周末与法定节假日全天）按 base 价，无 `"peak"` 的模型始终按 base 价计费。
>
> **计算方式**：单次调用费用 = `(输入 token × 输入单价 + 输出 token × 输出单价) / 1,000,000`。例如 DeepSeek-V4-Flash 高峰日闲时/周末/法定节假日：输入 3000 tokens × ¥1.0 + 输出 2000 tokens × ¥4.0 = ¥0.011/次（高峰日高峰时段则 ×2、×8）。缓存命中时输入部分按 `input_cache_hit` 计费。
>
> **覆盖方式**：编辑独立参考文件 `data/config/llm_pricing_ref.json`（JSONC，含中文注释）。`models` 逐模型覆盖，**只写要改的字段**，其余继承内置价；策略字段置顶：
> ```json
> {
>   "version": 1,
>   "currency": "CNY",
>   "timezone": "Asia/Shanghai",
>   "peak_periods": ["09:00-12:00", "14:00-18:00"],
>   "idle_periods": [],
>   "weekend_always_idle": true,
>   "holiday_always_idle": true,
>   "models": {
>     "claude-sonnet-5-5": {"input_price": 2, "output_price": 10},
>     "my-new-model": {"input_price": 5, "output_price": 10, "input_cache_hit": 0.5},
>     "deepseek-v4-flash": {
>       "input_price": 1.0, "output_price": 4.0, "input_cache_hit": 0.02,
>       "peak": {"input_price": 2.0, "output_price": 8.0, "input_cache_hit": 0.04}
>     }
>   }
> }
> ```
> - 文件缺失 → 仅用内置价；`version` 不符 → 拒绝加载并提示删除后重新生成（内置价兜底，报告仍可生成）；单个模型条目非法 → 告警并跳过该条。
> - `weekend_always_idle=false` 时周末恢复按钟点区分峰谷；`holiday_always_idle=false` 同理。
> - 参考数据不进 TUI/Web 配置面板；改价直接编辑本文件。

---


---

**相关手册**：[← LLM 配置指引](how-to-config-llm.md) · [手册总索引](README.md) · [常见问题解答](faq.md)

