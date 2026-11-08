# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.5]**（2026-11-08）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.6-dev] - 开发中（未发布）

### 变更

- **死代码与重复实现收口**（净 −546 行，删掉的符号均已无生产/测试引用）：LLM 重算归因里那张「模块 → 依赖组件」派生表（判据已收口为「只看模块键是否变化」）、财报负缓存的 `hit` 读取器、eastmoney 行业的两个便捷接口、`report/orchestrator` 的章节开关助手、`tui/handlers_qa` 的 what-if 前缀常量、`market_sentiment` 的行字段契约常量、`fetcher/index` 的腾讯美股代码表；指数裸码的市场号判定改由 `core/code_symbols.index_exchange_of` 单点决定，不再由 provider 自建段前缀表。同时收口两处同构实现：新闻源标签统一走 `news_sources.get_source_label`，开关取值解析复用 `config/features.parse_switch_value`。

### 修复

- **并发用例改事件/屏障判定，消除墙钟抖动**（rf-1087）：`test_slow_jjcc_hedges_to_zqcc`（jjcc `sleep(2.0)` 后断言 `<1.9s`，余量 0.4s）与 `test_categories_fetch_concurrently`（0.05s×3 断言 `<0.12s`，余量 0.03s）在慢 runner 上偶发失败（实测 CI 3.13 红两次）。改为 jjcc 阻塞在事件上、主线程校验「zqcc 起跳时 jjcc 未返回」；新浪分类改三路屏障（串行即超时失败），断言并发语义而非调度运气。
- **配图与面板不再显示本机绝对路径**（rf-1086）：演示工作区配置改为相对项目根（`data/holdings` / `reports`），并新增展示原语 `core/system_info.display_path()`（项目根之下 → 相对形式，越出根目录或跨盘符保持绝对）——系统状态卡与 Web 配置面路径输入框统一走它。此前 Web 工作台「正式更新」提示会把 `/home/<user>/…` 这类本机目录印在面板与 README 配图上。README / 手册全套配图按演示工作区重出（虚构账户 A/B、6 只公开品种）。
- **Web 配置面随 `[S]`/`[C]` 收口同步**（rf-1085）：载荷里那个永远为空的「关联产物」块（`artifact` 分位已无条目）整体删除（域/标题/载荷/前端渲染器），功能开关改为只下发 `[S]` 面板上屏项、经 `panel_switches` 单点取数（不再内联一份上屏判定、不再下发 `[C]` 专属组）；补三条契约用例锁「Web 上屏集合 = TUI `[S]` 面板、`[C]` 项经章节块/子项覆盖、隐藏项不下发」。手册的 Web 域块清单与机制组条目、TUI 面板提示语同步。
- **面板分块与编号全量对齐**（rf-1084）：`whatif_trade_cost` 迁入 `[S]` 后，8 份文档仍按旧口径（`[C]` 四块含关联产物、`[S]` 旧编号、`--chapter` 可覆盖关联产物、R-WIF-13 分组）。文档统一为：`[C]` 三块（顶层 / LLM / 整章，`artifact` 分块位保留但空块跳过）、`[S]` 编号 1-18（机制组内置常开项不占编号）、关联产物入口一律指向 `[S]` 持仓与交易组。

- **归因判据收口后的文档与回归收口**（rf-1083）：未命中归因已改为只看「模块键是否变化」，`llm-technical.md` 仍在描述已不存在的「模块→组件映射表」，且拆分归因用例时丢了 `TestSkeletonPathAttribution` 类头（骨架路径归因的来由注释），`_cache_fixtures.degradation_events` 构造器随之无人调用。文档改为「唯一判据是键变化，组件哈希只服务诊断」；恢复类头并补一条回归：降级事件变化只让 `health_check` 归因为 `fingerprint_changed`（数据质量变了不能当「只是到点」）。
- **初始化铺出的可编辑配置文件补覆盖与写盘防护**（rf-1082）：`init_config` 新增「缺失即按模板铺出 `logger.json` / `llm_pricing_ref.json`」，但无用例锁定该行为；且 `test_init_template_writes_relative_paths` 只屏蔽了原有的两处写盘入口，新增两处在临时还原真实路径的分支里会写进仓库 `data/config/`。补两条用例（缺失即铺出、已存在不改写），并把四处写盘入口一并屏蔽。
- **面板开关清单跨渠道单源 + 两处清理**（rf-1081）：`panel_visible=False` 的开关此前只在 TUI 隐藏，Web 配置面仍全量下发；现统一经新增的 `panel_switches(panel)` 取数（含可见性过滤），`panel_option_numbers` 复用同一入口。顺带删除 `tui/handlers_holdings` 里零引用的单笔回显函数，并把「行情口径桶」测试桩收口到 `src/test/_market_clock.py`（档位 key/label 单源）。
- **成本流水近似分支的数值防护**（rf-1080）：无流水时（开关开）`_build_flow_data` 把明细 `price` 原样收进`current_prices`，非数值会让下游 `final_value > 0` 抛 `TypeError`，异常冒泡导致整份 HTML 报告失败。改为只收正数值市价；并补两条真实现回归（近似分支跑通、非数值市价被过滤）。
- **`[S]` / `[C]` 面板按语义收口**（rf-1079）：判断依据与 LLM 输出评级不再占面板编号（默认常开、日常无需调，仍可用 `features.json` 覆写）；候选基金比较改**自动项**（配置了候选池即生效，不上面板）；首页执行摘要卡转正默认开；市场情绪与资金热点标记「需凭据」。`What-if 交易成本对比` 由 `[C]`「关联产物」迁入 `[S]` 持仓与交易（它只给既有调仓页签加成本层、不新增章节），`[C]` 回归纯章节面板。守护脚本与用例夹具补「空块」容忍。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.5（2026-11-04 ~ 2026-11-08）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
