# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.7]**（2026-11-09）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.8-dev] - 开发中（未发布）

### 修复

- 名称前缀缩写的主体归因（rf-1112）：LLM 省掉产品类型尾缀时（「嘉实全球产业升级」⊂「嘉实全球产业升级股票(QDII)A」）四种主体来源都解析不出，数值落进「无主体」分支被跳过——`017730` 那处 `8.5%` 因此长期留在正文。现补第五来源 `_match_name_prefix`（前缀 ≥4 字且**唯一**指向一只持仓才生效），并给「名称包含」判据加两道闸（过短 / 命中多只持仓 → 视为不可知，宁漏改不误改）；修正明细的方向标注改取该品种自身盈亏（不再把亏损品种标成「盈利」）
- 离线评测 dry-run 不再对提示词做事实校验（rf-1112）：此前把「LLM 输出」（其实是提示词）当正文校验，产出 9 项检查 / 22% 的假幻觉率；报告新增 dry-run 说明行
- 生成后自检上屏口径（rf-1110）：自检清单原样透传内部模块键（`global_macro` / `penetration_deep`），报告读者看不懂——提示词改按中文模块名投喂并明令禁止输出内部键，模型仍照抄时由代码确定性替换；另对自检引用的百分比做语料核对，查不到原值的追加上「无法核实」注记（该清单属模型复核，此前会把模块里的错值原样转述）
- 增量历史缓存键改为注册表形状（rf-1108）：旧实现拼成 `history_history_{chain}_{code}`，既不命中 `history_stock_` / `history_index_` / `history_fund_otc_` 前缀也不命中精确键，落进 default 日档（24h）被清理——K 线文件每日全量重取，且 `_correction_streak` 计数每日重置，「连续检出→跳过全量刷新」冷却永远到不了阈值；现由唯一构造器 `chain_incremental.history_cache_key()`（`{chain_name}_{code}`）供 `index.py` / `clear_incremental_cache` 共用
- `market_hours`（官方开闭市探测）由未登记改为 `calendar` 模块精确键（清理 14 天 ≥ 读侧 7 天盘后口径）
- 移除 `{cache_key}_correction_flag` 死写（只写不读）
- 新增缓存键形状 ↔ 注册表覆盖契约测试（`test_cache_key_registry_contract.py`）：任何键构造器产出的键都必须命中注册表类型，不得落 default；跟踪基线必须有独立精确键 TTL
- 跨报告对比基线（`fund_manager_snapshot` / `fund_concentration_snapshot` / `fund_style_snapshot`）改为近永久 TTL（`CACHE_NEAR_PERMANENT`，1 年）并在注册表登记精确键 TTL（rf-1107）：此前落入上报域日档（`fund_manager_` → 24h），而报告生成入口每次先跑 `auto_cleanup_expired()`，两次报告相隔超过一天即把基线当过期文件删掉，报告恒定显示「此为首次运行，基金经理变更自下次报告起跟踪」
- 「刷新基础缓存」保留跟踪基线（rf-1107）：`clear_by_group` / `clear_by_prefix` 新增 `exclude_keys`，刷新流程点名保留三个快照键——该流程只清不重建快照，清掉即让下一次报告退化成「首检」

### 变更

- 生成后自检降级为**实验能力（出厂默认关）**（rf-1111）：它是单份报告里输入最大的一遍调用（全部模块正文），产出只是尾部清单；要衡量它是否值得开，改用离线抽样 `scripts/eval-llm-hallucination.py --self-review`，产物为「中文名（内部键）」双写的 Markdown——中文给人读、内部键给解析脚本读，人机共读
- 自检提示词改为双写投喂（`### 模块：全球政经局势（global_macro）`）；报告上屏仍只留中文名（`localize_for_display`），离线产物保留双写（`module_dual_form`）
- 新增**确定性**跨模块一致性检查（`fact_checker/_cross_module.py`，零 LLM 调用）：同一实体在不同模块被赋予不同收益率（实测 017730 一处亏损 8.5%、两处 -5.06%）时，在复核区块最前给出冲突行与两处原值；英文符号/「亏损」措辞按语境补齐方向，容差 0.5 个百分点
- 复核区块不再依赖 LLM 开关：确定性核对段恒在，模型层自检（若开启）跟在事实之后

### 重构

- 本机 IP 探测归位（rf-1109）：`get_machine_ip` / `_is_loopback` 由 `core/logger.py` 迁到 `core/system_info.py`（后者本就是「机器信息 / 展示原语」的单源），顺带清掉 logger 里一段失去绑定的孤立函数文档；`web` 状态卡、TUI 状态行、页脚与启动边界日志改为同一入口
- `scripts/_test_runner/pytest_env.py` 四处可选插件探针（html/timeout/cov/xdist）收敛为 `_has_plugin()` 单点（只查 `find_spec` 不导入，避免插件注册副作用）
（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.7（2026-11-04 ~ 2026-11-09）
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
