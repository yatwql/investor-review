# 配置文件设计（八份文件边界 / 演进策略 / 写入约定）

> **关联**：[`llm-settings-nesting-design.md`](llm-settings-nesting-design.md)（`llm_settings.json` 纵切结构）、[`logging-config-design.md`](logging-config-design.md)（`logger.json` 键表与加载优先级）、[`config-tui-design.md`](config-tui-design.md)/[`config-web-design.md`](config-web-design.md)（两个渠道的面板呈现）。
> **范围**：配置文件与密钥文件的职责边界、演进策略（不做旧版兼容）、`config.json` 的内部取舍、书写与读取约定（中文注释、统一剥离器、原子写）。**不含**面板层级与浏览器分区。
> **单一事实位**：键位与默认值的真值在代码注册表（`config/_config_defaults.py`、`_llm_settings_defaults.py`、`_llm_pricing.py`、`_logging.py`、`_feature_registry.py`、`chapter_registry.py`），本文只记录边界与约定。

---

## 1. 配置文件全景与边界

### 1.1 演进策略（不做任何旧版兼容）

配置与持久化数据的结构变更，**一律不为旧版本留兼容**。适用范围与处理方式：

| 对象 | 处理 |
|:--|:--|
| **其他结构的配置文件**（config / features / llm_settings / llm_providers / logger 等） | 结构版本不符即拒绝加载并提示重新生成；不提供结构转换脚本、不保留双读分支 |
| **不在当前结构内的配置项 / 键名** | 不解析、不映射、不静默忽略；文档只保留键位对照供重新生成时人工参考 |
| **非当前格式的缓存数据**（`data/cache/` 各前缀 JSON） | 不读取其他格式；缓存可再生，直接清理（`clear_by_group` / 删除目录），由程序按当前结构重建 |
| **其他结构的数据文件**（快照、账本、实验统计、持久化中间产物） | 不做字段兼容与补全；结构不符即忽略该文件或重建，不做隐式转换 |

配套四条硬约束：

1. **重新生成**：文件缺失或结构版本不符，由默认配置生成器产出新文件；用户值不随重建携带，按文档自行重设。
2. **生成器同批更新**：任何结构变更必须同步修改默认生成器（模板、注释、默认项），否则视为改动未完成。
3. **版本字段只做拒绝校验**：缺失或不匹配即报错并给出重建指引，不做升级解释。
4. **代码不写兼容分支**：不保留 `if old_version` / 字段别名映射 / 静默兜底；兼容代码本身即缺陷来源。

### 1.2 八份文件的职责边界（六份配置 + 两份密钥）

| 文件 | 内容 | 归属 | 结论 |
|:--|:--|:--|:--|
| `config.json` | 路径、章节开关、数据源、缓存、调度、通知、基准等 42 键 | 用户可编辑 | 保留，内部整理见 7.2 |
| `features.json` | 功能开关的覆写层（22 项覆写 / 26 项注册） | 面板写入 | 保留：覆写层语义清晰，缺键即出厂默认 |
| `llm_settings.json` | LLM 模块参数与运行约束 | 面板写入 | 保留；结构按 [`llm-settings-nesting-design.md`](llm-settings-nesting-design.md) 纵切 |
| `llm_providers.json` | 多链线路清单与优先级 | 面板/CLI 写入 | 保留：多链是独立子系统 |
| `llm_key.json` / `data_key.json` | 模型与数据源凭据（两份） | 仅手填 | 保留且**永不合并**：密钥与配置分离是安全边界（git 忽略） |
| `logger.json` | 日志级别、轮转、查看器默认项 | 面板写入 | 新增：运行诊断域独立，且需环境变量临时覆盖 |
| `llm_pricing_ref.json` | LLM 计价参考：币种/时区/峰谷规则 + 各模型单价 | 仅手填 | 新增：参考数据（随供应商调价更新），非用户调优项；不进面板 |

原则：**一份文件对应一个用户可理解的域**；密钥单独；**参考数据（如计价表）单独成文件**；不按"代码模块"拆分。

### 1.3 `config.json` 的三处内部问题（取舍结论）

| 问题 | 事实 | 判定 |
|:--|:--|:--|
| 同一组配置分布在扁平键与嵌套段两处 | `market_hour_aware` / `market_hour_ttl` 与 `market_hours` 平级混放（各 7 处引用）；`batch` 与 `batch_rate_limit` 两个平行段（18 处引用） | **暂不合并**：收益仅是形式统一，需重新生成 + 生成器模板 + 文档与测试同步；留待进入「域即文件」阶段统一处理 |
| 四个内部文件指针混在用户配置里 | `llm_key_file` / `llm_settings_file` / `llm_providers_file` / `data_key_file`（5~21 处引用） | **保持结构**：它们是路径覆盖能力而非日常配置；在文档中标为「高级/内部」即可 |
| 空字典段易被误认为"可配" | `preferred_provider` / `redemption_limits` / `fund_fee_fallback` / `user_fund_benchmarks` 默认为 `{}` | **记录为模板质量事项**：给示例值或注明"留空即用内置默认"；不与结构重建同批 |

同理保持不动：`news_top_count` 与 `news_sources` 分离（38 处引用）、`comparison_indices` / `comparison_candidates` / `whatif_benchmark_index` 三处分离（语义不同：基准池 / 候选池 / What-if 基准）。

### 1.3.1 候选整理清单（备查，非排期）

下表把 7.2 的三类问题列为可选动作，仅作将来评审的输入——**无实施动作、无排期**；任一项启动前需单独评审（结构变更按 7.0：不做旧版兼容，直接重新生成）。

| 候选动作 | 引用量 | 重建成本 | 收益 | 触发条件 |
|:--|--:|:--|:--|:--|
| `market_hour_aware` / `market_hour_ttl` 合并为 `market_hours.{aware,ttl}` | 14 处（7+7） | 中：生成器模板 + 文档/测试 | 同类项在一处，扁平键减 2 | 进入「域即文件」阶段 |
| `batch_rate_limit` 合并为 `batch.rate_limit` | 18 处 | 中：同上 | 两个平行段合一 | 同上 |
| 四个文件指针收进 `paths.*` | 5~21 处/键 | 低：生成器模板 + 键名映射 | 用户配置区与内部 plumbing 分开 | 文档标注「高级/内部」后仍被误改 |
| 四个空段补示例或注释 | 0 处代码引用 | 低：仅模板文案 | 消除"看起来可配但为空"的误读 | 随时（作为模板质量项） |
| `news_top_count` 合入 `news.sources`；三处基准键并段 | 38 + 41 处 | 高：面广、语义差异需保留 | 形式统一 | 不作为候选：收益低于成本 |

### 1.4 明确不做的四件事

| 不做 | 理由 |
|:--|:--|
| 合并成单一 `settings.json` | 重建覆盖全部 loader、面板、测试与文档，收益仅"少一个文件"；面板已按域抽象，用户不感知文件名 |
| 按"代码模块"继续拆文件（`scheduler.json`、`datasource.json` 等） | 会让"改一个设置该开哪个文件"更难答；只有**业务域独立**（运行诊断）或**数据类型不同**（参考数据）才单独成文件 |
| 密钥并回主配置 | 安全边界：凭据必须与配置分离且不入库 |
| 给 `config.json` 加 `version` | 仅在结构重建时需要；与该次重建同批加入 |

### 1.5 触发重估的条件

只有出现下列之一才重估本文结构：① 进入「域即文件」阶段（一份文件 = 一个业务域）；② 新增第 7 份用户可编辑文件的需求；③ 扁平键与嵌套段的不一致导致实际误配（有事故/工单）。

### 1.6 配置书写与读取约定（中文注释）

**约束：默认配置生成器一律输出带中文注释的配置文件；所有读取路径一律支持带注释的文件。**

| 角色 | 要求 |
|:--|:--|
| 默认配置生成器（`config.json` / `features.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 及后续新增） | 输出 JSONC 风格（`//` 行注释）：**分类标题 + 每个配置项一句中文说明**；注释不改变数据语义，不允许把值写进注释 |
| 所有读取路径（配置包、`core/logger.py`、`llm/pricing.py`、脚本与 Web） | 必须经统一注释剥离器解析；**禁止**对配置文件直接 `json.loads` 原始文本 |
| 注释剥离器 | 以叶子模块 `core/json_comments.py`（新增，仅标准库）承载，`config/_comments.py` 再导出；日志与计价等 core 级读取因此不必导入 config 包，避免循环依赖 |
| 写入保真 | 写回时保留既有注释（读—改—写链路不得抹掉分类说明与项说明） |
| 校验 | 模板生成测试断言产出含中文注释；读取测试使用带注释样本；新增生成器未带注释视为未完成 |

适用边界：注释只用于解释；机器状态文件（缓存、账本、快照）**不加注释**，仍为纯 JSON。

---

## 2. 架构约束遵从（`technical.md`「架构设计约束」）

下表按语义名称列出与本设计相关的约束及遵从方式（编号与完整表述见 `technical.md`）：

| 约束 | 本设计的遵从方式 |
|:--|:--|
| 缓存统一管理 | 「不做旧版兼容」策略下清理缓存经 `cache/` 子包接口（`clear_by_group`），不直接删文件 |
| 原子写 | 配置写入统一经 `edit_ops` → `atomic_write`；新增的 `logger.json` / `llm_pricing_ref.json` 写入同源，不另建写盘路径 |
| 章节注册表驱动 | `[C]` 的章节清单来自章节注册表与 LLM 模块注册表，面板不硬编码名称 |
| 日志统一 | 日志配置只改 handler 参数；日志器仍为 `logging.getLogger("invest")`，不用 `print` 输出诊断 |
| LLM 模块注册 | `enabled_llm` 位于 `modules.<m>.enabled`，模块函数表与数据模块注册表保持独立 |
| 测试三纪律（标记 / 边缘隔离 / 敏感路径隔离） | 新增测试标注 marker、edge 用例入 `*_edge.py`、敏感路径经 conftest 隔离 |
| 控制台着色 | `console.color` 与既有规则一致：`NO_COLOR` 或非 TTY 自动降级 |
| 路径绝对化 | `logger.file.path`、配置文件路径在配置层一律输出绝对路径 |
| 指纹唯一事实来源 | 「生成参数摘要」由 `llm/module_fingerprint.py` 提供，预检侧与写侧共享同一函数 |
| 开关注册表唯一来源 | 开关集合（`doctor_check` 不入选）、分组归属（含 `crisis_replay` 归 `analysis`）与新组声明全部落在 `feature_switch_registry`；面板不持清单 |
| 凭据不入日志与产物 | 新增的日志与计价文件不含凭据；密钥仍只在 `llm_key.json` / `data_key.json` |
| 文件行数红线 | `[D]`（诊断）与 `[D]`→`[L]`（日志设置）的处理器落在 `handlers_log.py` 或独立模块，`handlers_config.py` 行数保持在红线内 |
| 分档只改版式 | 新面板使用 `layout_tier` 与 `wrap_hanging`，40 列不超宽；分档不改变键义 |

不适用（本设计不触及）：代码类型判定、会话缓存、HTTP 客户端、Provider Chain、新闻召回、渲染期全局变量、pipeline_data Schema、图表说明、实验挂载点、交易日计数、重试原语、间隔节流。

---

## 3. 影响面与验证

**代码**：`config/_config_defaults.py`（config.json 模板与路径解析）、`config/_llm_settings.py` + `_llm_schema.py`（v2 嵌套与展平契约）、`config/_llm_pricing.py`（计价参考独立文件）、`config/_logging.py`（logger.json 读取/校验/写入）、`config/_feature_registry.py` + `chapter_registry.py`（开关与章节注册表）、`config/edit_ops.py`（白名单 + 校验 + 写入分派，三渠道唯一通道）、`core/json_comments.py`（注释剥离叶子模块）、`core/atomic_write.py`（原子写）。

**文档同步点**：`how-to-config.md`（配置项表与注释说明）、`how-to-config-llm.md`（LLM 配置结构、计价参考、参数范围）、`requirements.md` §11（配置项清单）、`technical.md` 配置矩阵（解析协调者 / 注释剥离 / 委托依赖）、`folders.md` 目录树。

**自动验证**：`test_json_comments_contract`（五份配置注释样本 + 读改写保注释）、`test_llm_settings_v2`（版本拒绝 / 三层缺省 / 展平契约）、`test_llm_pricing`（缺失回退 / 部分覆盖 / 非法跳过 / 版本拒绝）、`test_logging_config`（默认 / 回落 / 保存拒绝 / 环境变量优先）、`test_llm_param_validation`（范围表驱动）、`test_config_atomic`（原子写与崩溃恢复）、`test_edit_ops`（白名单结构 / 值规则 / 写入与备份）。

**人工验证**：删除任一配置文件 → 生成器重建后启动正常（`llm_settings.json` / `logger.json` / `llm_pricing_ref.json` 逐一验证）；把配置置为非当前结构 → 明确拒绝并给出重建指引（不静默回落）。

---

## 4. 关联设计

- 面板入口与层级：[`config-tui-design.md`](config-tui-design.md)（终端）· [`config-web-design.md`](config-web-design.md)（浏览器）
- 结构纵切：[`llm-settings-nesting-design.md`](llm-settings-nesting-design.md) · [`logging-config-design.md`](logging-config-design.md)
- 设计图样：[`config-panel-mockup/`](config-panel-mockup/)（TUI / Web / LLM 纵切三套）
