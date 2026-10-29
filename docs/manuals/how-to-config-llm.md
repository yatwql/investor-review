# LLM 配置指引

全球政经局势、智囊团深度复盘、持仓体检报告、穿透深度分析、以及可选的财经新闻热点与持仓关联分析均需调用外部 LLM API。

LLM 配置由三个独立文件管理：

| 文件 | 内容 | 用途 |
|------|------|------|
| `data/config/llm_key.json` | `credentials_ref` 命名凭据块（每块含 api_key / model / endpoint） | 密钥与线路明细（不提交仓库） |
| `data/config/llm_providers.json` | Provider 路由配置 | 定义 Provider 的切换顺序、策略，并 `credentials_ref` 引用凭据块 |
| `data/config/llm_settings.json` | 所有非敏感配置 | 参数调优（temperature、timeout、cache、system_prompt 等） |

> **为什么用三个文件？** `llm_key.json` 包含 API Key，可加入 `.gitignore` 避免误提交；
> `llm_providers.json` 和 `llm_settings.json` 不含密钥，可安全纳入版本控制，方便团队共享调优参数。
>
> **不配置会怎样？** `llm_key.json` 缺失或 key 为空时，程序不崩溃，其他功能正常。对应报告页签显示占位提示。不同失败场景的占位文本：
> 
> | 原因 | 占位文本 |
> |------|---------|
> | LLM 未配置 | 本节内容待生成 — LLM 未配置（请配置 data/config/llm_key.json 与 llm_providers.json） |
> | API 调用失败 | 本节内容待生成 — LLM API 调用失败（请检查 API Key 和网络连接后重新生成） |
> | 请求超时 | 本节内容待生成 — LLM API 请求超时（可尝试在 llm_settings.json 中增大 timeout 配置） |
> | 网络连接失败 | 本节内容待生成 — LLM API 网络连接失败（请检查网络后重新生成） |
> | 熔断冷却中 | 本节内容待生成 — LLM API 暂时不可用（熔断冷却中，请稍后重试） |
> | 模块已禁用 | （直接跳过，无占位文本，HTML 章节与 Excel 页签整章不出现，后续章号连续递进） |

## 目录

- [快速配置](#快速配置) · [多 Provider 链式服务（进阶）](#多-provider-链式服务进阶)（[文件分工](#文件分工) · [配置步骤](#配置步骤) · [Provider 条目字段](#provider-条目字段) · [调整多链线路优先级](#调整多链线路优先级) · [端点级节流（`pacing`）](#端点级节流pacing) · [切换策略](#切换策略) · [模块级 Provider 偏好](#模块级-provider-偏好) · [配置检查](#配置检查) · [配置形态](#配置形态)）
- [模块启停](#模块启停) · [缓存机制](#缓存机制)
- [失败降级与占位](#失败降级与占位) · [`system_prompt` 配置覆盖链](#system_prompt-配置覆盖链)
- [配置项总览](#配置项总览)（[模块级配置](#模块级配置) · [事实校验容差配置](#事实校验容差配置)） · [各模块推荐参数值](#各模块推荐参数值) · [参数合法范围](#参数合法范围)
- [Extended Thinking](#extended-thinking)（[配置方式](#配置方式) · [模型差异](#模型差异) · [`thinking_budget` 与 `max_tokens` 的关系](#thinking_budget-与-max_tokens-的关系) · [效果参考](#效果参考)） · [Prompt Caching（Anthropic 专属）](#prompt-cachinganthropic-专属)
- [HTTP 代理配置](#http-代理配置)（[Linux / macOS](#linux--macos) · [Windows PowerShell](#windows-powershell) · [注意事项](#注意事项)）
- [Token 消耗参考](#token-消耗参考) · [Token 用量统计](#token-用量统计)
- [provider 示例与定价表（独立参考）](#provider-示例与定价表独立参考) —— 拆到 [LLM 参考附录](how-to-config-llm-reference.md)

## 快速配置

**Step 1**：在 `data/config/llm_key.json` 写入一个命名凭据块（键名自定义，下文以 `claude-main` 为例）：

```json
{
  "claude-main": {
    "api_key": "sk-ant-xxxxxxxxxxxxx",
    "model": "claude-sonnet-4-20250514",
    "endpoint": "https://api.anthropic.com/v1/messages"
  }
}
```

**Step 2**：在 `data/config/llm_providers.json` 写一条引用该凭据块的线路（只需一条也能正常出报告；多线路自动降级见下文「多 Provider 链式服务」）：

```json
{
  "strategy": "priority",
  "providers": [
    {
      "name": "claude-main",
      "provider": "claude",
      "credentials_ref": "claude-main",
      "priority": 10,
      "timeout": 120
    }
  ]
}
```

> **两条都必填**：`llm_key.json` 只放密钥（`api_key`/`model`/`endpoint`），`llm_providers.json` 只放路由字段并用 `credentials_ref` 指向凭据块的键名——两者键名必须一致。`llm_providers.json` 里写 `api_key` 会被拒绝（凭据分离）。非敏感参数统一在 `llm_settings.json` 中管理。

**Step 3**（可选，使用默认值即可跳过）：编辑 `data/config/llm_settings.json`，根据偏好微调参数。示意结构如下（完整配置项见「配置项总览」章节）：

```json
{
  "max_retries": 2,
  "enabled_llm": {
    "global_macro": true,
    "expert_review": true,
    "health_check": true,
    "penetration_deep": true,
    "news_correlation": false,
    "self_review": true,
    "holding_change": true
  },
  "temperature_global_macro": 0.3,
  "max_tokens_global_macro": 3072,
  "temperature_expert_review": 0.3,
  "max_tokens_expert_review": 36000
}

```

> **注意**：
> - `system_prompt_*` 默认值为 `null`，表示使用代码内置提示词。填入字符串可覆盖。
> - 代码内置提示词定义在 `src/python/llm/prompts_core.py`（主 prompt）、`prompts_tables.py`（数据表格）、`prompts_action.py`（行动建议）中，更新代码时可自动升级。
> - 计价策略与模型单价覆盖在独立参考文件 `llm_pricing_ref.json` 中，详见 [LLM 参考附录 §完整模型定价表](how-to-config-llm-reference.md#完整模型定价表)。

**Step 4**：启动程序，菜单选 **L** 生成包含 LLM 分析的完整版报告。

---

## 多 Provider 链式服务（进阶）

当需要同时配置多个 LLM 服务商（如 DeepSeek 为主、Gemini 为辅），按策略自动切换时，可启用多链模式。

### 文件分工

| 文件 | 内容 | 安全等级 |
|------|------|---------|
| `llm_providers.json` | Provider 路由配置：名称、类型、切换策略、凭据引用 | ✅ 可提交仓库 |
| `llm_key.json` | 凭据块：每个 `credentials_ref` 对应一个包含 api_key / model / endpoint 的命名块 | ❌ 含密钥，不提交 |

### 配置步骤

**Step A** — 编辑 `data/config/llm_providers.json`（首次运行已按此生成：DeepSeek 主行 + OpenCode Go 订阅中转）：

> `opencode-go` 是**订阅制**中转：`pacing` 段对它不是可选优化——删掉就回到不限速高频调用，容易撞风控/超会员额度。出厂值 `min_interval: 5` 是实测可用档，想更保守可写成 `{ "min_interval": 20, "jitter": 0.2, "max_concurrency": 1 }`。

```json
{
  "strategy": "priority",
  "preferred_providers": {},
  "providers": [
    {
      "name": "deepseek-main",
      "provider": "claude",
      "credentials_ref": "deepseek-main",
      "priority": 10,
      "timeout": 120
    },
    {
      "name": "opencode-go",
      "provider": "claude",
      "credentials_ref": "opencode-go",
      "priority": 20,
      "timeout": 120,
      "pacing": { "min_interval": 5, "max_concurrency": 1 }
    }
  ]
}
```

**Step A'** — 另一种常见配法：次选换成 Gemini（`provider` 类型为 `gemini`，端点与模型不同，无需 `pacing`）：

```json
{
  "strategy": "priority",
  "preferred_providers": {},
  "providers": [
    {
      "name": "deepseek-main",
      "provider": "claude",
      "credentials_ref": "deepseek-main",
      "priority": 10,
      "timeout": 120
    },
    {
      "name": "gemini-fallback",
      "provider": "gemini",
      "credentials_ref": "gemini-fb",
      "priority": 20,
      "timeout": 60,
      "proxy_preferred": true
    }
  ]
}
```

**Step B** — 在 `data/config/llm_key.json` 中添加对应凭据块（按上一步采用哪套线路保留对应块）：

```json
{
  "deepseek-main": {
    "api_key": "sk-your-deepseek-key",
    "model": "deepseek-v4-flash",
    "endpoint": "https://api.deepseek.com/anthropic/v1/messages"
  },
  "opencode-go": {
    "api_key": "your-opencode-go-key",
    "model": "deepseek-v4.1-flash",
    "endpoint": "https://your-opencode-go-host.example/anthropic/v1/messages"
  },
  "gemini-fb": {
    "api_key": "AIzaSyYourGeminiKey",
    "model": "gemini-2.5-flash",
    "endpoint": "https://generativelanguage.googleapis.com/v1beta"
  }
}
```

> **注意**：`llm_key.json` 使用多键格式时，顶层 `provider` / `api_key` / `model` / `endpoint` 字段无效，需要为每个 `credentials_ref` 定义独立的命名凭据块。`llm_providers.json` 中的 `credentials_ref` 值必须与 `llm_key.json` 中的键名精确匹配。

### Provider 条目字段

| 字段 | 必填 | 类型 | 说明 |
|------|:----:|:----:|------|
| `name` | ✅ | string | Provider 唯一标识名，用于日志和缓存键 |
| `provider` | ✅ | string | 服务商类型：`claude` / `openai` / `gemini` |
| `credentials_ref` | ✅ | string | 引用 `llm_key.json` 中的凭据块键名 |
| `model` | ❌ | string | 路由字段：覆盖凭据块中的同名模型名；缺省时用凭据块的值 |
| `endpoint` | ❌ | string | 路由字段：覆盖凭据块中的同名端点；缺省时用凭据块的值 |
| `priority` | ❌ | int | 优先级（数值越小越优先），默认 99 |
| `weight` | ❌ | int | 加权随机权重，仅 `weighted` 策略有效，默认 1 |
| `timeout` | ❌ | int | 端到端请求超时秒数（墙钟上限：含服务端排队与传输全程，到点放弃并重试/切换），覆盖全局 timeout，默认 60 |
| `proxy_preferred` | ❌ | bool | `true` 时优先使用代理直连（而非自动路由），默认 `false` |
| `pacing` | ❌ | object | **端点级节流/并发约束**（仅作用于本条目对应的端点）；缺省 = 无额外约束。字段见下方「端点级节流」 |

> **不得内联 `api_key`**：本文件可提交仓库（团队共享调优参数），因此**只放路由字段**——写入 `api_key` 等于把密钥随配置入库。校验器遇到非空内联 `api_key` 会记 WARNING 并**跳过整条 provider**（不是仅告警后放行）。密钥一律写在 `llm_key.json` 的凭据块里，本文件用 `credentials_ref` 引用。`model` / `endpoint` 属非敏感路由字段，可留在本文件按条目覆盖凭据块同名值。

### 调整多链线路优先级

备用顺序的真值是 `providers[].priority`（数值越小越优先，`priority`/`fallback_only` 策略下即实际链序）。各处展示一律按这个链序排列（首页配置块 `[1]/[2]`、页头状态行的链首线路、`[G]` → `[L]` 面板编号、Web 配置面一致），`providers` 数组里条目的物理位置不影响链序。三个入口写同一份文件、走同一校验（order 必须恰好覆盖全部线路名，写前自动 `.bak` 备份、注释保留）：

- **TUI**：主菜单 `G` → `M` —— 面板按当前顺序列出线路，输入两个编号交换位置（如 `3 1`）即写盘
- **Web**：配置面板「LLM 多链线路优先级」块，▲▼ 按钮调序即存
- **CLI**：`python -m src.python.cli --llm-provider-order deepseek-main,opencode-go report --type basic` —— 顺序靠前优先，写盘后退出；`NAME` 须恰好覆盖全部现有线路（少写/多写/重复均拒绝，报错会列出当前名单）

> `weighted` / `cost_first` 策略下实际链序由权重/成本决定，上面顺序仅在 `priority` / `fallback_only` 策略下生效。

写回只动 `providers` 区块：文件原有缩进风格与注释保留；文件头的「主：/备：」这类线路标注会在写盘时中性化为「线路：」（链序以 `priority` 升序为准，标注在换序后即失效，避免注释与字段相互矛盾）。

### 端点级节流（`pacing`）

**为什么需要它**：同一次报告生成的 LLM 调用会落在不同端点上，而各端点背后的服务约束截然不同——

- **订阅制编码端点**（如 OpenCode Go、Kimi Code）：按会员额度计费（按周期刷新而非按量扣费），带滚动频率窗口与风控型并发上限；其服务条款要求**交互式**使用，批量调用应低频串行。**pacing 对它们是必备约束**：出厂默认的 `opencode-go` 条目已带 `pacing`，删掉就回到不限速高频调用。
- **按量付费端点**（如 DeepSeek 开放平台 `api.deepseek.com/anthropic`）：有明确的分级 RPM / TPM 与按量账单，可放心用较高并发，不写 `pacing` 即可。

全局键 `llm_max_concurrency` 无法表达「同一程序、不同端点不同策略」，因此把约束**声明到 provider 条目**上：

```jsonc
"providers": [
  {
    "name": "kimi-code",
    "provider": "claude",
    "credentials_ref": "kimi-code",
    "priority": 10,
    "pacing": { "min_interval": 20, "jitter": 0.2, "max_concurrency": 1 }
  }
]
```

| `pacing` 字段 | 类型 | 默认 | 含义 |
|------|:----:|:----:|------|
| `min_interval` | float | 0 | 同一端点上两次请求的**最小间隔**（秒）；0 = 不限 |
| `jitter` | float | 0 | 在主间隔上叠加的随机抖动**比例**（0~1）；避免固定节奏的机器特征 |
| `max_concurrency` | int | 0 | 该端点**同时在途**请求上限；0 = 不限 |

**关键性质**：

- **缺省即无约束**：不写 `pacing` 的 provider 行为与未引入本机制时**逐字节一致**（零开销直通）。因此同一份配置里，可以把订阅制端点收紧、把按量端点放开。
- **与全局并发叠加**：`llm_max_concurrency` 仍限制总线程数（默认 3）；`pacing.max_concurrency` 是**额外**的每端点上限，两者同时生效。例如全局 3 线程 + 订阅制端点 `max_concurrency: 1` ⇒ 该端点始终串行，其余端点可达 3 路并行。
- **失败分类与重试**：端点返回 **403**（配额/风控拒绝，如 `You've reached your 5-hour usage limit` / `concurrent request limit`）时**不重试**——这类限制按时间窗口滚动、重试无益且会加剧风控画像；报告将显示「LLM 端点配额/风控限制已触发」并降级到下一 provider。**503** 仍按 `max_retries` 重试；**429** 归 `quota` 终态不重试——限速属配额/风控终态，首试即以 600s 长冷却熔断该端点并降级下一 provider（与 403 同路径，记 `FAIL_REASON_QUOTA_EXCEEDED`）。
- **抖动与间隔的线程安全**：同一端点的间隔串行与在途计数均为线程安全（per-端点锁 + 信号量），不同端点互不阻塞。
- **429 诊断回显**：端点返回 429 时日志**先回显两级实际配置再给建议**——`当前配置：全局 llm_max_concurrency=…；provider[条目] pacing.max_concurrency=…、pacing.min_interval=…`（端点约束未声明标「未配置（不限流）」、间隔未声明标「未配置」），再按**生效并发 = min(全局, 端点)** 分支：生效并发 >1 只建议**绑定项**（哪级等于生效并发才建议调哪级，非绑定项注明须低于对方现值才生效）；任一级已到 1（生效并发=1）就不再叫你调低任何并发旋钮——端点已配 1 时调低全局根本不减少该端点在途并发——改推请求间隔 `min_interval`；生效并发与间隔均已到底时会明确提示「429 更可能来自请求速率或配额（RPM/TPM）/风控而非并发」。凡建议调整处均带当前值，不必翻配置找基数。

### 切换策略

`strategy` 字段支持 4 种切换策略：

| 策略 | 值 | 行为 |
|------|:---:|------|
| **优先级排序** | `priority` | 按 `priority` 字段升序尝试，第一个成功返回即停止。这是默认策略 |
| **加权随机** | `weighted` | 按 `weight` 权重随机选取 Provider，失败后重试其他 |
| **价格最低优先** | `cost_first` | 优先使用单价最低的 Provider，失败后按价格升序递补 |
| **仅 Fallback** | `fallback_only` | 始终使用第一个 Provider，仅在其全部失败后尝试下一个 |

> `proxy_preferred` 不是策略类型，而是 provider 条目级别的后处理标记。启用时，该条目的请求将优先通过代理发送（若系统配置了代理），而非直连。

### 模块级 Provider 偏好

当特定 LLM 模块（如智囊团深度复盘）需要使用指定的 provider，而其他模块沿用默认排序时，可通过 `preferred_providers` 字段配置模块级偏好：

```json
{
  "strategy": "priority",
  "preferred_providers": {
    "expert_review": "opencode-go",
    "health_check": "opencode-go"
  },
  "providers": [
    { "name": "deepseek-main", "provider": "claude", "credentials_ref": "deepseek-main", "priority": 10, "timeout": 120 },
    { "name": "opencode-go", "provider": "claude", "credentials_ref": "opencode-go", "priority": 20, "timeout": 120, "pacing": { "min_interval": 5, "max_concurrency": 1 } }
  ]
}
```

上述配置的效果：

| 模块 | module_key | Chain 排序 | 优先尝试 |
|------|-----------|-----------|---------|
| 智囊团深度复盘 | `expert_review` | `[opencode-go, deepseek-main]` | OpenCode Go |
| 持仓体检报告 | `health_check` | `[opencode-go, deepseek-main]` | OpenCode Go |
| 全球政经局势 | `global_macro`（未配置） | `[deepseek-main, opencode-go]` | DeepSeek |
| 穿透深度分析 | `penetration_deep`（未配置） | `[deepseek-main, opencode-go]` | DeepSeek |

> **module_key 规则**：对应 `llm_settings.json` 中 `max_tokens_{module_key}` 的 `{module_key}` 部分。有效值：`global_macro` / `expert_review` / `health_check` / `penetration_deep` / `news_correlation`。
>
> `preferred_providers` 中的 provider 名称必须与 `providers[].name` 精确匹配，否则该条配置会被忽略并记录警告日志。

### 配置检查

TUI 菜单 **[S]** 查看状态时会显示多链模式详情：

```
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
LLM Provider 状态
状态: 已配置 | 策略: 优先级排序 | 多链服务: 2 provider
  [1] deepseek-main (claude)
      模型: deepseek-v4-flash    优先级: 10    自动重试: 正常
  [2] gemini-fallback (gemini)
      模型: gemini-2.5-flash    优先级: 20    自动重试: 正常
  ▶ 模块偏好: 智囊团深度复盘 → gemini-fallback / 持仓体检报告 → gemini-fallback
```

- 首行状态：`状态` 行显示所选策略（优先级排序 / 加权随机 / 价格最低优先 / 仅 Fallback）与 provider 数量
- 每个 provider 单独两行：`[序号] 名称 (backend)` + `模型 / 优先级 / 自动重试` 状态
- `▶ 模块偏好` 行仅在配置了 `preferred_providers` 时显示

### 配置形态

运行期只认「命名凭据块 + provider 条目」这一种形态（`llm_key.json` 为 `{"<块名>": {"api_key": ...}}`，`llm_providers.json` 用 `credentials_ref` 引用块名）。

**密钥摊在顶层的旧形态（`provider` / `api_key` / `model` / `endpoint` 四个顶层字段）已不支持**：不做自动改写、不写 `.bak` 备份，凭据加载直接拒绝并在日志给出改写指引，LLM 章节按「未配置」显示占位。按上文 Step 1 / Step 2 手工改写两个文件即可（把四个顶层字段包进一个命名块，并在 `llm_providers.json` 的对应线路里填 `credentials_ref`）。

---

## 模块启停

通过 `enabled_llm` 嵌套字典控制每个模块的开关。除 `news_correlation`（新闻 LLM 关联分析）默认关闭外，其余默认开启（`self_review` 默认开启）（`holding_change` 持仓变动复盘归因的启停同时受报告章节开关 `holding_change_review` 约束）：

```json
"enabled_llm": {
  "global_macro": true,
  "expert_review": true,
  "health_check": true,
  "penetration_deep": true,
  "news_correlation": false,
  "self_review": true,
  "holding_change": true
}
```

- 关闭的模块在报告中自动跳过，不消耗 Token
- **申购限购约束上下文联动**：已启用的分析章提示词会自动附带「申购限购约束块」（限大额日限额 / 暂停申购，天天基金渠道口径），数据侧受报告功能开关 `fund_purchase_limit` 控制——关闭该开关或限购数据不可用时，各分析章回退无约束上下文（提示词与缓存键同步回退、静默不报错），已启用模块其余内容不受影响
- 可通过菜单 **P** 交互式开关各模块（LLM 章节块，即上方 `enabled_llm` 字典；编号由章节注册表派生，含实验性的「生成后自检」与持仓变动复盘归因）
- **[C] 面板四块**（编号由 `config/chapter_registry.py` 派生）：顶层章节（`config.json`）/ LLM 章节（`llm_settings.json`，智囊团章节下另有生成子项）/ 默认关闭的整章 / 关联产物；**[S] 面板五组**管章内内容（持仓与交易 / 市场与估值 / 基金与风格 / 事件与摘要 / 机制与质量，编号由开关注册表派生）。**章节显隐与章内内容分属两个面板**，无需改配置文件。
- 若 4 个 LLM 报告模块（global_macro / expert_review / health_check / penetration_deep）全部关闭，LLM 分析章节在报告中整体隐藏
- 仅 `news_correlation` 开启时不影响 LLM 分析章节可见性
- `self_review`（生成后自检）不是报告章节模块：它以**附录**形式附在 LLM 分析部分之后，不参与章节编号与目录导航，也不影响 LLM 分析章节的可见性

---

## 缓存机制

LLM 分析结果默认缓存，避免重复调用 API 浪费费用：

- **缓存自动失效** — 持仓数据或指数数据变更时，对应的 LLM 缓存自动失效。无需手动操作
- **缓存有效期** — 各模块独立配置（`cache_ttl` 中的 `llm_{module}` 条目），默认值见[配置指南](how-to-config.md#cache_ttl-可调参数)
- **手动清除** — 菜单 **[2]** 更新行情类缓存 → 所有 LLM 缓存自动清除
- **关闭缓存** — 在 `llm_settings.json` 中将 `cache_enabled_{module}` 设为 `false`，每次生成都重新调用 API

---

## 失败降级与占位

各模块在以下场景下自动降级或重试：

| 场景 | 行为 | 日志 |
|------|------|------|
| `llm_key.json` 缺失或 key 为空 | 显示占位："本节内容待生成 — LLM 未配置" | INFO |
| `enabled_llm.{module}` = false | 直接跳过，不显示占位；对应 LLM 分析章（HTML 章节/Excel 页签）整章隐藏，章号连续递进 | INFO |
| API 调用失败（网络错误/超时） | 显示占位："（本节内容生成失败）" | WARNING |
| 返回空内容（无文本块，如思考耗尽 max_tokens 预算） | 关闭 thinking 同 Provider 重试一次；仍失败才切换下一 Provider | WARNING |
| 返回空字符串（内容被过滤） | 追加安抚指令重试一次，仍失败则切换 Provider | WARNING |
| 输出被截断（含 `... [TRUNCATED] ...`） | 自动增大 `max_tokens` 1.5× 重试一次，仍截断则记录日志提示用户手动调大 | WARNING |

---

## `system_prompt` 配置覆盖链

系统提示词按以下优先级（高 → 低）解析：

1. `llm_settings.json` → `system_prompt_{module}` 的值（非 null）
2. 代码内置提示词（`prompts_core.py` / `prompts_tables.py` / `prompts_action.py` 中定义）

> 设为 `null` 表示回退使用代码内置提示词，升级代码时可自动获取更新。

**示例** — 让智囊团深度复盘输出英文摘要：

```json
{
  "system_prompt_expert_review": "You are an investment expert. Analyze the portfolio data and provide a concise review in English, including risk assessment and rebalancing suggestions. Keep the output within 500 words."
}
```

> 注意：覆盖后不会随代码升级自动更新，移除该字段或设为 `null` 即可恢复内置提示词。

---

## 配置项总览

> 以下为 `llm_settings.json` 的全部配置项。`{module}` 占位符替换为具体的模块后缀（global_macro / expert_review / health_check / penetration_deep / news_correlation / self_review / holding_change）。

配置分为**全局配置**和**模块级配置**两类。全局配置项如下：

- `llm_total_time_budget_sec`（秒，默认 `0`=不启用）：整段 LLM 生成的时间预算；超预算后不再启动新模块（已在跑的模块不打断），日志回显已用时长与预算值，报告按已生成内容呈现。用于兜住「单模块卡住 + 重试叠加」把一次完整报告拖成小时级（实测曾出现 LLM+新闻阶段 6,623s）。
- `max_retries`（int，默认 `2`）：**503**/超时/网络异常最多重试次数（**429/403 归 quota 不重试**——429 首试即 600s 长冷却熔断）
- `llm_full_fail_retry_delay`（int，默认 `30`）：整链全挂后的延迟重试等待秒数（`0`=不等待）——网络/超时/单次 API 错误等**瞬时类**失败在整链失败后等待该秒数重试 1 次；配额（429/403）与熔断终态不重试
- `llm_max_concurrency`（int，默认 `3`）：LLM 模块并发生成的最大线程数。设为 1 时完全串行，设为 4 及以上可提升速度但可能触发 API 限速（429）。建议值 2-3
- `llm_max_thinking_concurrency`（int，默认 `2`；**TUI `[D]→[L]` / Web 配置面板「LLM 调优参数」可改，范围 1~4**）：开启 Extended Thinking 的模块（health_check / expert_review 等 `thinking_enabled_{module}=true`）并发的最大请求数。默认 `2` 让两个 thinking 模块并行——实测串行时「等待并发槽」占单次报告墙钟约 44%（智囊团 68.7s + 体检 28.5s，体检全程排队）。多 thinking 模块同时涌向 DeepSeek 等强制推理端点时偶发返回空 content（HTTP 200 空响应），若日志出现空内容重试（会关闭 thinking 同 provider 重试一次）或内容质量下降，改回 `1` 恢复串行。非 thinking 模块不受此限

> **全局并发 vs 端点级节流**：`llm_max_concurrency` 是**全局**上限（所有模块合起来最多几个线程）；若需对**某个具体端点**单独限速/限并发（例如同一个程序里，订阅制编码端点要低频串行、按量付费端点可以放开），用 `llm_providers.json` 各 provider 条目内的 `pacing` 段——两者叠加生效，见下方「端点级节流」。
- `enabled_llm`（dict，默认除 `news_correlation` 为 `false` 外均为 `true`；`self_review` 默认开启）：各模块独立启停开关。`self_review`（生成后自检）每次报告额外调用一次 LLM，对四个分析模块产出做一致性复核并输出【自检清单】附录（与确定性事实校验分层不重叠，失败不影响主内容）
- `fact_check`（dict，默认 `{tolerance: 1.0}`）：LLM 输出数值一致性检测配置。详见下节「事实校验容差配置」
- **计价策略与模型单价**：不在本文件，见独立参考数据 `data/config/llm_pricing_ref.json`（`version` + 策略 + `models` 逐模型覆盖；缺失时仅用内置价）。详见 [LLM 参考附录 §完整模型定价表](how-to-config-llm-reference.md#完整模型定价表)
- `news_correlation_top_n`（int，默认 `30`）：送 LLM 分析的新闻条数。仅 news_correlation 模块有效，值越大 Token 消耗越高
- `daily_cost_limit`（数值，默认 `0` 不启用）：LLM **日费用预算上限**，单位是**本地主币种**（`llm_pricing_ref.json → currency`，默认 CNY）。判定超限时把各币种今日支出按内部汇率表折算到该币种比对（折算仅参与判定，**不改变任何展示金额**）；某币种缺少内部汇率会被点名「无法折算」，不会静默按 0 计。
- `debate`（dict，可选实验功能）：辩论模式配置。含 procon（三段式正反辩论，`per_call_max_tokens` 限定每阶段输出上限，默认 18432（null 时按代码兜底同值））、conditional（条件情景推理）、concentration_qa（集中度问答阈值，辩论流程内建段落的触发阈值），以及 `max_total_tokens_per_report`（单次报告辩论总 Token 预算上限，默认 72000，覆盖三段式真实成本）和 `per_call_timeout_override`（辩论单次 API 超时覆盖）。**本段仅控制辩论行为的参数，启停由 Feature Flag（`llm_debate_*`）决定，非配置直接启用**；决策跨期反思闭环（`decision_reflection`）同样由 Feature Flag 启停，无独立配置段

### 模块级配置

| 配置键 | 类型 | 默认值（各模块不同） | 说明 |
|--------|:----:|:--------------------:|------|
| `system_prompt_{module}` | string / null | `null` | 系统提示词覆盖，`null`=使用代码内置 prompt |
| `model_{module}` | string / null | `null` | 独立指定本模块使用的模型，`null`=沿用线路默认。**线路条目或凭据块中的 `model` 优先**（模块级值只在两者都缺省时生效） |
| `temperature_{module}` | float | 0.1~0.8（模块差异） | 采样温度，0=确定性最高，1=最大多样性 |
| `max_tokens_{module}` | int | 3072~36000（模块差异） | 输出最大 token 数，超过时内容被截断（触发自动重试）。**DeepSeek 为 thinking + 正文共享预算**（详见下方 DeepSeek V4 说明） |
| `timeout_{module}` | int | 60~120（模块差异） | API 超时秒数 |
| `cache_enabled_{module}` | bool | `true` | 是否启用缓存。关闭后每次生成都重新调用 API |
| `output_brief_{module}` | bool | `false` | 精简模式：`true` 时输出 ≤200 字（global_macro）或 ≤300 字（其余模块）。**批量模式（news_correlation）不支持** |
| `thinking_enabled_{module}` | bool | 模块差异 | 是否开启 Extended Thinking（Claude / DeepSeek / Gemini 2.5） |
| `thinking_budget_{module}` | int | 6000~24000（模块差异） | **Claude / Gemini 2.5** Thinking token 预算。须小于对应 `max_tokens`（思考计入总输出预算，须为正文留余量），非法值代码自动修正 |
| `reasoning_effort_{module}` | string / null | `"low"`（`expert_review` 为 `"medium"`） | **仅 DeepSeek** 推理深度：`"low"` / `"medium"` / `"high"` / `"max"` |

> 各模块默认值差异详见下方「各模块推荐参数值」表。

---

### 事实校验容差配置

`fact_check` 段控制 LLM 生成内容中数值的自动校验和修正逻辑，用于检测并纠正 LLM 在报告中提到的收益率、占比、排名等数值与实际数据的偏差。

```json
"fact_check": {
  // 全局数值偏差容差（百分点），默认 1.0
  "tolerance": 1.0,
  // 按模块覆盖容差（模块名 → 百分点）
  "tolerance_overrides": {
    "expert_review": 2.0,
    "health_check": 1.0,
    "global_macro": 1.0,
    "penetration_deep": 1.0
  }
}
```

| 配置键 | 类型 | 默认值 | 说明 |
|--------|:----:|:------:|------|
| `tolerance` | float | `1.0` | 全局数值偏差容差（百分点）。LLM 输出的百分比数值与真实值偏差在 ±tolerance 百分点内即视为通过校验，超出则被标记为"疑似幻觉"并触发自动修正 |
| `tolerance_overrides` | dict | 见默认值 | 按模块覆盖容差。key 为模块名（`expert_review` / `health_check` / `global_macro` / `penetration_deep`），value 为该模块专用的容差值。未在 override 中列出的模块使用全局 `tolerance` |

**工作原理**：
1. LLM 模块生成报告后，事实校验器扫描 HTML 中的百分比数值
2. 将每个数值与持仓数据的真实值对比（如持仓收益率、组合占比等）
3. 偏差 ≤ `tolerance`（或模块对应的 override 值）→ 标记为绿色 ✅ 通过
4. 偏差 > 容差 → 标记为红色 ❌ 疑似幻觉，并用真实值自动替换错误数值
5. 批量修正后，报告末尾追加一段"事实校验"摘要（显示修正前后的对比）

**内置语境感知（自动跳过，无需配置）**：
- **回撤语境**：「历史最大回撤 19.0%」等回撤数值与实际最大回撤比较，不按收益率校验
- **环比/同比变化率语境**：「总市值变化-96.02%」「较上期+3.21%」等相对上期/上年的变化比例，与收益率（相对成本）维度不同，**自动跳过不校验**——避免被误当成收益率改写为某个品种的收益率（如 96.02% 被修正为 27.6%）
- **占比/仓位/归因/假设/调仓目标等语境**：仓位占比、收益归因贡献度、假设情景（"如果下跌 20%"）、调仓目标（"降至 30%"）、币种敞口等数值同样自动跳过，不与收益率直接比较

**品种存在性校验（穿透 TOP10 代码豁免）**：
- 除数值一致性外，事实校验器还检查 LLM 提到的 6 位品种代码是否真实存在（持仓代码 + 常见指数代码如沪深300 `000300` 视为有效）
- **穿透 TOP10 代码豁免**：智囊团深度复盘 / 持仓体检报告 / 穿透深度分析三模块的提示词均含【穿透 TOP10】数据（如宁德时代 `300750`、阳光电源 `300274`），这些股票**非直接持仓但属组合穿透范围**——LLM 引用它们不算幻觉，不触发"品种代码不在当前持仓中"告警。全球政经局势提示词不含穿透数据，保持严格校验

**推荐配置**：
- **`expert_review`（智囊团深度复盘）= 2.0**：该模块综合判断较多，LLM 可能对收益率进行"约数"表述（如"约 15%"而非精确的 14.7%），给予更宽松容差可减少误报
- **`health_check` / `global_macro` / `penetration_deep` = 1.0**：这些模块数值引用较少，1 个百分点已足够宽松
- 若发现某模块频繁误报"通过"的数值，可适当降低该模块容差；反之频繁误标"疑似幻觉"时可适当提高

> **注意**：容差以百分点为单位，非百分比。例如 `tolerance: 1.0` 表示 LLM 说"15%"而真实值为 14.0%~16.0% 之间均算通过。修正操作仅在偏差超过容差时触发，并自动将错误数值替换为真实值。

---

<details>
<summary><b>📄 llm_settings.json 结构参考（schema v2）</b>（点击展开）</summary>

文件由程序生成（含每个键的中文说明注释），**不要手抄整份**；只需按需改值。结构骨架：

```json
{
  "schema_version": 2,

  // 缺省：所有模块继承；模块内只写差异
  "defaults": {
    "model": null, "temperature": 0.3, "max_tokens": 3072, "timeout": 60,
    "cache": true, "output_brief": false, "system_prompt": null,
    "thinking": { "enabled": false, "budget": null, "effort": null }
  },

  // 模块：一个业务对象一段；enabled 必须显式声明（各模块出厂默认不同）
  "modules": {
    "global_macro":     { "enabled": true },
    "expert_review":    { "enabled": true, "max_tokens": 36000,
                          "thinking": { "enabled": true, "budget": 24000, "effort": "medium" },
                          "debate": { /* procon / conditional / concentration_qa */ } },
    "news_correlation": { "enabled": false, "max_tokens": 3000, "timeout": 90 }
    // …其余模块同理
  },

  // 运行约束（面板「LLM 调优参数」）
  "runtime": {
    "max_concurrency": 3, "thinking_concurrency": 2, "max_retries": 2,
    "full_fail_retry_delay_sec": 30, "time_budget_sec": 0, "daily_cost_limit": 0,
    "debate_limits": { "max_tokens_per_report": 72000, "call_timeout_override_sec": 90 }
  },

  // 高级选项
  "advanced": {
    "fact_check": { "tolerance": 1.0, "tolerance_overrides": { "expert_review": 2.0 } },
    "news_correlation": { "top_n": 10 }
  }
}
```

> - 模块段**只写与 `defaults` 不同的项**；`enabled` 不参与继承，必须逐模块声明。
> - `thinking.budget` / `thinking.effort` 在 `thinking.enabled=false` 时保留（临时关停不丢预算）。
> - 本手册与面板里的 `model_<m>` / `temperature_<m>` / `enabled_llm` / `llm_max_*` / `debate` 等**扁平键仍是读写契约**：读取时展平注入 `get_llm_config()`，写入时反展平回本结构（`llm/` 包无感）。
> - `schema_version` 缺失或不为 2 时**拒绝加载**并提示重新生成——不做旧结构转换，删掉文件后程序按模板重建。
> - 注释只用于解释；写入保留既有注释（值变化走文本 patch）。
</details>

---

## 参数合法范围

| 参数 | 合法范围 | 越界处理 |
|:--|:--|:--|
| `temperature` | 0–2 | 加载时回落 `defaults` / 内置默认并告警；面板写入直接拒绝 |
| `max_tokens` | 1–200000 | 同上 |
| `timeout` | 5–600 秒 | 同上 |
| `thinking.budget` | 1024–100000（`enabled=false` 时保留但校验） | 同上 |
| `thinking.effort` | `low` / `medium` / `high` | 同上 |
| `debate.procon.synthesis_temperature` | 0–2 | 同上 |
| `runtime.debate_limits.max_tokens_per_report` | 1024–500000 | 同上 |
| `runtime.debate_limits.call_timeout_override_sec` | 5–600 秒 | 同上 |

> 报错/告警文案统一含**键名、当前值、合法范围**；面板写入被拒时文件保持原值（不静默裁剪、不落盘半成品）。

## 各模块推荐参数值

> 以下仅列出**有差异的调优参数**。其余参数所有模块统一：`cache_enabled=true`、`output_brief=false`、`system_prompt=null`（使用内置）、`reasoning_effort="low"`（`expert_review` 例外，见下表）。

| 模块 | model | temperature | max_tokens | timeout | thinking_enabled | thinking_budget | reasoning_effort | output_brief_limit |
|------|:-----:|:-----------:|:----------:|:-------:|:----------------:|:---------------:|:----------------:|:------------------:|
| **全球政经局势** | null（使用默认） | **0.3**（低温保事实） | **3072** | **60s** | false | 6000 | low | **200 字** |
| **智囊团深度复盘** | null | **0.3**（低温保事实） | **36000** | **120s** | **true** ⭐ | 24000 | **medium** | 300 字 |
| **持仓体检报告** | null | **0.1**（极低温保数值精确） | **24000** | **120s** | **true** | 18000 | **low** | 300 字 |
| **穿透深度分析** | null | **0.1**（极低温保数值精确） | **12288** | **90s** | false | 12000 | low | 300 字 |
| **财经新闻关联分析** | null（可换轻量模型降成本） | **0.1**（极低温保 JSON） | **3000** | **60s** | false | 6000 | low | 不适用 |
| **生成后自检**（附录，默认开） | null | **0.1** | **4608** | **90s** | false | 6000 | low | 300 字 |
| **持仓变动复盘归因**（章本体另有开关） | null | **0.2** | **2048** | **90s** | false | 6000 | low | 300 字 |

> **补充**：财经新闻关联分析还支持 `news_correlation_top_n` 配置项（默认 `30`），控制送 LLM 分析的新闻条数上限，按关键词匹配数降序选取。增大此值会线性增加 Token 消耗，减小则降低 LLM 关联分析的覆盖率。设为 `0` 可完全禁用 LLM 分析（仅保留关键词匹配）。

> **temperature 项说明**：
> - **低温（≤0.3）**：输出稳定可预测，适合事实性分析和结构化 JSON。**智囊团深度复盘/持仓体检/穿透分析使用 0.1~0.2 极低温以减少数值幻觉**。
> - **中温（0.4~0.6）**：在准确性和判断力之间平衡，适合评分分析。
> - **高温（≥0.7）**：鼓励多样性和创造性输出，适合辩论式分析。**不推荐用于数值引用类模块**。

---

## Extended Thinking

> **Claude**（provider: `"claude"`）：模型 ≥ `claude-sonnet-4` 时生效，用 `thinking.budget_tokens` 控制思考 token 预算。
>
> **DeepSeek**（provider: `"claude"` + endpoint `api.deepseek.com/anthropic`）：模型 `deepseek-flash` / `deepseek-v4-*` 时生效，用 `output_config.effort` 控制思考深度（`"low"` / `"medium"` / `"high"` / `"max"`）。
>
> **Kimi（月之暗面）**（provider: `"claude"` + endpoint `api.moonshot.cn/anthropic`）：模型 `kimi-*`（如 `kimi-k2.6`）时生效，用 `thinking.budget_tokens` 控制思考 token 预算（与 Claude 同机制）。**注意 Kimi 端点默认开思考**：模块未开启 thinking 时本工具会自动显式发送 `disabled`，避免思考 token 白烧 max_tokens 预算。
>
> **Gemini**（provider: `"gemini"`）：模型 `gemini-2.5-*` 时生效，用 `generationConfig.thinkingConfig.thinkingBudget` 控制思考 token 预算。

**[Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)** 让模型在回答前进行深度推理，大幅提升复杂分析的深度和逻辑严谨性。代价是输出 token 大幅增加（约 2~4 倍），费用相应上升。

### 配置方式

在 `llm_settings.json` 中设置（示例为 DeepSeek 全面开启智囊团深度复盘使用 Extended Thinking）：

```json
{
  "thinking_enabled_expert_review": true,
  "reasoning_effort_expert_review": "max"
}
```

或使用 Claude 模型：

```json
{
  "thinking_enabled_expert_review": true,
  "thinking_budget_expert_review": 24000
}
```

### 模型差异

| 维度 | Anthropic Claude | DeepSeek V4+ | Google Gemini 2.5 | Kimi（月之暗面） |
|------|------------------|-------------|-------------------|-------------------|
| 控制参数 | `thinking.budget_tokens`（token 数量预算） | `output_config.effort`（"high"/"max" 定性控制） | `generationConfig.thinkingConfig.thinkingBudget`（token 数量预算） | `thinking.budget_tokens`（token 数量预算，与 Claude 同机制） |
| 与 temperature 关系 | **互斥**（开启后 temperature 参数被忽略） | **互斥**（开启后 temperature 参数被忽略） | **互斥**（开启后 temperature 参数被忽略） | **互斥**（开启后 temperature 参数被忽略） |
| 兼容端点 | `api.anthropic.com` | `api.deepseek.com/anthropic`（Anthropic 兼容端点） | `generativelanguage.googleapis.com` | `api.moonshot.cn/anthropic`（Anthropic 兼容端点） |
| 默认思考行为 | 默认不思考 | **默认开思考**（effort 族） | 默认不思考 | **默认开思考**（未开启时工具自动发 `disabled` 兜底） |
| 推荐场景 | 预算可控，适合所有模型 | 默认 `low`（智囊团 `medium`）；需更深时手动提到 `high` / `max`（`max` 仅推荐智囊团） | 低成本备选，适合轻量推理 | 通用主力（256k 上下文），预算可控 |

### `thinking_budget` 与 `max_tokens` 的关系

**仅在使用 Claude / Gemini / Kimi 模型时 `thinking_budget_{模块}` 有意义**（三者同属 `budget_tokens` 族）。DeepSeek 使用 `reasoning_effort`（`"low"` / `"medium"` / `"high"` / `"max"`，出厂默认 `"low"`）定性控制思考深度，不涉及 token 预算概念。

| 配置项 | 管什么 | expert 默认值 |
|--------|--------|:------------:|
| `max_tokens_expert_review` | **最终输出文本**的最大 token 数（DeepSeek 为 thinking + 正文共享预算） | 36000 |
| `thinking_budget_expert_review` | **内部思考过程**分配的 token 预算 | 24000 |

**API 硬性约束（仅 `budget_tokens` 族：Claude / Gemini / Kimi）：** `thinking_budget_{模块}` 的值**必须小于**对应的 `max_tokens_{模块}`（思考 token 计入 max_tokens 共享预算，须为其后的正文留余量）。代码自动保护：若 `thinking_budget` 缺失或 ≥ `max_tokens`，自动修正为 `max(1024, max_tokens − 2048)`（1024 为 Anthropic `budget_tokens` 的最小值硬限制；`max_tokens − 2048` 保证正文至少留 2048 token 余量）。若配置开启但模型不支持，自动跳过并记录 WARNING。

**一句话总结（Claude / Gemini / Kimi）：** `max_tokens` 管"最终说多少"，`thinking_budget` 管"允许想多久"。
**一句话总结（DeepSeek）：** `reasoning_effort` 管"想多深"，`"max"` 对应深度分析的极致模式。

> **默认开思考的厂商需注意（DeepSeek / Kimi）**：两家端点在不传思考参数时**默认开启思考**（思考 token 计入 `max_tokens` 共享预算）。模块**未**开启 thinking 时，程序会自动显式发送 `disabled` 兜底，避免思考占满预算而正文为空；但若你手动改小 `max_tokens`，仍建议同步核对 `thinking_budget` 与模块开关。

**DeepSeek V4 强制推理说明**：DeepSeek V4 系列为**强制推理模型**，即使 `thinking_enabled` 关闭也会返回 `thinking` block；且 `max_tokens` 是 **thinking + 最终文本的共享预算**（而非仅最终输出）。当思考部分耗尽预算时，响应只含 thinking block、无最终文本（即"返回空内容"场景）。

**思考耗尽自动兜底**：开启 Extended Thinking 时若出现"思考部分耗尽 max_tokens 预算"，程序会**自动关闭 thinking 同 Provider 重试一次**（`call_claude` 层安全网，日志 `关闭 thinking 重试一次，避免模块整体失败`），保证有正文产出；重试仍失败才切换下一 Provider。因此正常情况下不再因思考耗尽直接丢模块内容。

**调参建议**：若日志仍频繁出现 `LLM 输出思考部分耗尽 max_tokens 预算`，请**增大对应模块的 `max_tokens_{module}`**（DeepSeek 为 thinking + 正文共享预算，需 > `thinking_budget` + 正文余量）或**降低 `reasoning_effort_{module}`**。日志会**直接回显具体字段名与当前值**（如 `max_tokens_expert_review=8192`、安全网日志的思考配置现值），照提示的字段调即可，不必自己对应模块。当前默认 expert_review 36000 / health_check 24000（对应 thinking_budget 24000/18000 + 正文余量，DeepSeek V4 输出上限 384K 无 API 拒绝风险；2026-09-16 全模块整体上调 50%），配合自动兜底双重保障。

### 效果参考

| 分析模块 | 关闭 thinking（token 用量） | 开启 thinking（token 用量） | 费用倍率 |
|------|:---------------------------:|:---------------------------:|:--------:|
| 智囊团深度复盘 | 输入 ~3000 / 输出 ~2000 | 输入 ~3000 / 输出 ~8000 | ~2.5× |
| 全球政经局势 | 输入 ~1500 / 输出 ~600 | 输入 ~1500 / 输出 ~2500 | ~3× |

---

## Prompt Caching（Anthropic 专属）

> 仅 `provider: "claude"` 时生效，OpenAI 提供商不适用。

代码在调用 Claude API 时自动启用 Anthropic Messages API 的 [Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) 功能。

- **生效条件**：同一 system prompt 在 **5 分钟内**重复使用
- **场景**：财经新闻热点与持仓关联分析批量处理时最有价值——5 分钟内多次调用共享缓存，**输入 token 扣费减少约 50%**
- **无感使用**：不需要任何配置项，调用 Claude API 时自动启用

---

## provider 示例与定价表（独立参考）

篇幅原因，逐家 provider 的配置示例与完整模型定价表已拆到 [LLM 参考附录](how-to-config-llm-reference.md)：

- [支持的 provider 及配置示例](how-to-config-llm-reference.md#支持的-provider-及配置示例) —— 各服务商的 `credentials_ref` / endpoint / model 写法（DeepSeek、OpenAI、Gemini、Anthropic 兼容端点等）
- [完整模型定价表](how-to-config-llm-reference.md#完整模型定价表) —— 计费口径与逐模型单价（配 `llm_pricing_ref.json` 时对照）

## HTTP 代理配置

程序默认直连 LLM API，如所在网络需要通过 HTTP 代理访问外网（如公司内网、VPN 环境），可通过环境变量配置：

### Linux / macOS

```bash
# 设置 HTTP 代理
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"

# 设置后运行程序即可
.venv/bin/python -m src.python.tui
```

### Windows PowerShell

```powershell
# 设置 HTTP 代理
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"

# 设置后运行程序
.venv/bin/python -m src.python.tui
```

### 注意事项

- 代理配置对所有 LLM Provider（Claude、OpenAI、DeepSeek、Gemini、火山引擎）均生效
- 代理仅影响 LLM API 调用，不影响数据源行情获取（详情数据源暂不支持代理）
- 如仅需部分 Provider 走代理，可在 `llm_providers.json` 中为该 Provider 设置 `"proxy_preferred": true`（多链模式下生效）
- 如代理认证需要用户名密码，使用 `http://user:pass@host:port` 格式
- 设置后可通过日志确认：`logs/app.log` 中搜索 `proxy` 或 `httpx.Proxy` 关键字

---

## Token 消耗参考

以下费用按 **DeepSeek-V4-Flash 闲时价**（¥1.0/M 输入、¥4.0/M 输出，2026-09-10 官方降价后）估算，工作日高峰时段约翻倍、周末与法定节假日全天按闲时价，各模型单价详见 [LLM 参考附录 §完整模型定价表](how-to-config-llm-reference.md#完整模型定价表)。

| 模块 | 输入 token | 输出 token | 单次费用参考 |
|------|-----------|-----------|-------------|
| 全球政经局势 | ~300-800 | ~300-600 | ~¥0.002-0.003 |
| 智囊团深度复盘 | ~800-2500 | ~1500-2500 | ~¥0.007-0.013 |
| 持仓体检报告 | ~500-1500 | ~800-1500 | ~¥0.004-0.008 |
| 穿透深度分析 | ~500-1500 | ~800-1500 | ~¥0.004-0.008 |
| 财经新闻关联分析（可选） | ~2000-4000 | ~600-1200 | ~¥0.004-0.009 |
| **五者合计（菜单 L + 新闻 LLM）** | — | — | **~¥0.02-0.04/次** |

- 仅菜单 **L** 触发 LLM 调用，E / B 不会
- LLM 结果默认缓存，缓存有效期内反复按 L 不会重复扣费
- 持仓或指数数据变更时，关联的 LLM 缓存自动失效；也可通过菜单 **[2]** 更新行情类缓存主动清除所有 LLM 缓存

---

## Token 用量统计

每次菜单 L 完成后，程序会统计本次会话的 LLM Token 消耗明细，展示在多个位置：

| 输出端 | 展示形式 | 说明 |
|:-------|:---------|:-----|
| **Excel 报告** | 独立页签「LLM API 用量」 | 顶部汇总区 + 下方模块明细表，状态列带条件颜色填充 |
| **HTML 报告** | 报告「LLM API 用量」章节（底部） | 与 Excel 格式一致 |
| **TUI 终端** | 一行摘要 | 每次菜单 L 完成时输出 |
| **调试日志** | `logs/app.log` | 每次 API 调用后记录明细 |

主要内容包括：
- **汇总数据**：API 调用次数、模型名称、输入/输出 Token 总数、缓存命中 Token、累计费用
- **模块明细**：每个 LLM 子模块的单独统计（状态、模型、Token 数、费用、是否缓存、是否开启 Thinking）
- **缓存统计**：系统数据缓存命中/未命中/总请求数/命中率

---

**相关手册**：[← 常规配置指引](how-to-config.md) · [报告文件结构 →](reports-instruction.md) · [手册总索引](README.md)
同主题：[常见问题解答](faq.md)
