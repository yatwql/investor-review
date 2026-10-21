# LLM 调用费用优化分析（通用 + DeepSeek 专项）

> 版本：0.13.6 ｜ 日期：2026-10-18 ｜ 归档：2026-10-20（v0.13.9-dev）｜ 状态：分析完成；行动清单闭环——② 已随 v0.13.6 完成，① 用户已采纳闲时调度，③ 已核实无需改配置，④ 机制已具备（待质量评估试用）
> 依据：实测日志 `logs/app.log`（2026-10-17 22:37 一次完整报告，9 次 LLM 调用）+ 配置 `llm_key.json` / `llm_providers.json` / `llm_settings.json`
> 关联自审：rf-701 / rf-702 / rf-703（分析过程发现的计量缺陷，均已随 v0.13.6 修复，摘要见 `docs/archive/v0.13.x/archived_review-findings.0.13.x.md`）

---

## 1. 现状：链路配置

| 项 | 值 | 来源 |
|---|---|---|
| 主 provider | `deepseek-main`（协议 claude，优先级 20，超时 120s） | llm_providers.json |
| 实际模型 | `deepseek-v4-flash`，端点 `https://api.deepseek.com/anthropic/v1/messages` | llm_key.json |
| 备 provider | `opencode-go`（GLM-5.3-Flash，优先级 30，pacing 限速） | llm_providers.json |
| 其他凭据 | `kimi-k2.6`（moonshot）、`kimi-for-coding`（未在 providers 启用） | llm_key.json |
| thinking | expert_review/health_check 开（medium/low），其余关 | llm_settings.json |
| max_tokens | expert 36000 / health 24000 / penetration 12288 / news 3000 | llm_settings.json |

关键点：**用户实际计费模型是 DeepSeek flash（非 Claude）**，`deepseek-v4-flash` 定价 1.0/4.0/0.02（闲时），峰谷子段 2.0/8.0/0.04。费用按北京时间峰谷：周末与法定节假日全天闲时。

## 2. 实测缓存命中率（推翻"前缀不稳"假设）

9 次调用中 6 次有缓存命中。全局：命中 3,840 ｜ 未命中 21,496 ｜ 输出 18,527，**整体命中率 ≈ 15%**。

| 输入(日志) | 输出 | 命中 | 命中率 |
|---:|---:|---:|---:|
| 634 | 128 | 384 | 38% |
| 180 | 357 | 1,792 | 91% |
| 1,350 | 393 | 512 | 27% |
| 5,325 | 10,838 | 256 | 5% |
| 4,686 | 4,207 | 512 | 10% |
| 1,870 | 628 | 384 | 17% |

**纠偏**：此前猜测"前缀不稳定导致缓存失效"不成立——前缀布局已天然友好（system 在前、新闻关联持仓块在前、无时间戳前缀），DeepSeek 也确实在命中。命中率低的真实原因是**输出远大于输入**（输出 18,527 vs 输入 25,336），费用大头在输出而非输入，缓存优化的边际收益远小于预期。

## 3. 发现的计量缺陷（已随 v0.13.6 修复，补 5 个回归用例）

1. **rf-702 负费用**：DeepSeek Anthropic 兼容端点 `input_tokens`=仅未命中（实测 180，而 `cache_read_input_tokens`=1792），`estimate_cost` 按 `cache_miss = input − hit = 180−1792 = −1612` 算出 `¥−0.0001`。仅显示失真，不影响真实扣费。
2. **rf-703 会话费用虚高约 3×**：`session.track_session_usage` 按 Claude 协议 + 未命中口径累计，但 DeepSeek 返回的 `input_tokens` 单位已是 flash 计费单位（DeepSeek 自报"命中 6,400 节省 ¥0.019"反推基准 ≈1.18 元/百万，即 flash 量级非 Claude 的 3.0）。
3. **rf-701 原生端点计量缺失**：DeepSeek 原生 OpenAI 协议端点 `prompt_cache_hit_tokens` 未被解析（当前主链路走 claude 协议不受影响）。

## 4. 行动清单（按「收益 × 零质量损失」排序）

| 优先级 | 动作 | 成本 | 预期收益 | 状态 |
|---|---|---|---|---|
| ① | 非紧急报告挪到闲时/周末跑 | 零（行为） | 输入侧费用 **−50%** | ✅ 用户已采纳（自行闲时调度） |
| ② | 修复 rf-702/703 计费口径 | 一次小改 + 回归 | 费用显示准确 | ✅ 已完成（v0.13.6） |
| ③ | 核实端点模型映射（必要时改 `deepseek-flash` 模型名） | 一次核实 | 解锁正确峰谷价 | ✅ 已核实：`deepseek-v4-flash` 为官方 API 模型 ID，账单已按 DeepSeek-V4.1 计费（控制台名 DeepSeek-V4.1-Flash-1017），无需改名 |
| ④ | 评估 output 瘦身（output_brief / 降 thinking on expert） | 需质量评估 | 输出侧 −30~50% | 机制已具备（`output_brief_*` 精简模式开关，默认关）；质量评估待试用 |

## 5. 不建议做（质量或收益不划算）

- ❌ 合并多模块为单次调用：提示词膨胀 + 注意力稀释
- ❌ 批量 API：DeepSeek 无 batch 折扣，Anthropic/OpenAI 的 50% 折扣不适用主链路
- ❌ 降 max_tokens「省钱」：它是上限不是消耗，只换来截断重试（`AUTO_INCREASE_FACTOR=1.5`，截断重发完整请求，反而双倍输入费）

## 6. 结论

**输出 token 才是费用大头**（输出单价 4× 输入，且输出量与输入同量级），因此最高性价比杠杆是 **① 闲时调度（输入 −50%）** 与 **④ 输出侧瘦身**，而非缓存/前缀优化（命中率已正常但对总费用影响有限）。计费口径缺陷（rf-702/703）不影响真实扣费，仅影响费用构成显示——已随 v0.13.6 完成口径统一，费用显示可直接支撑后续优化决策。
