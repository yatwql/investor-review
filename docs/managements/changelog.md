# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.5]**（2026-11-08）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.6-dev] - 开发中（未发布）

### 修复

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
