# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.1]**（2026-10-14）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.2-dev] - 开发中（未发布）

### Added

- **持仓成本区间位置列（plan-90）**：「持仓明细与分类」页签市值明细与分类汇总两区块末列追加「成本区间位置」两列（近 20 / 260 交易日价格区间百分位，≈1 追涨嫌疑、≈0 低位布局），填补只维护持仓、无流水时「买入时机相对历史区间」的量化空白。纯计算 `analysis/cost_position.py`（clamp/中性值/窗口切片）+ 编排 `report/cost_position.py`（复用既有行情历史链，不新增数据源；长窗口一次取数、短窗口同源切片）；功能开关 `cost_position`（默认开，`GROUP_ANALYSIS`），行情缺失静默隐列不阻断报告；口径脚注随呈现（成本均价近似买入价 + 窗口参数 + 公式）。新增 44 例（纯计算/契约/渲染 + 边缘退化序列/非有限值）。落地设计 `docs/plan/holding-cost-position-design.md`。

### Fixed

- **`scripts/launch.sh` 无参启动崩溃（rf-682）**：`set -euo pipefail` 下裸引用 `$1`/`$VENV_PATH`，无参调用（默认 TUI 路径）或未设 `VENV_PATH` 时直接 `unbound variable` 退出；改 `${1:-}`/`${VENV_PATH:-}` 默认展开，新增 `test_launch_script_regression.py` 回归用例 4 例。

- **shell 契约门禁盲区（rf-683）**：`scripts/` 目录全面核查发现——① `launch.sh` 有 4 处 `set -e` 下的死代码 `$?` 检查（`if [ $? -ne 0 ]` 永不触发，失败时脚本已提前退出，错误处理分支是假安全感）；② 十守护/CI 全为 Python 静态检查，从不执行/解析 shell，`.sh` 的「运行行为」在整个质量体系里零覆盖（rf-682 缺陷穿过全部门禁的根因）。修复：`launch.sh` 4 处死代码改 `if ! cmd; then …` 写法；新增 `test_shell_contract.py` 静态机检，已验证必红，封堵回流。后续精度补丁：裸位置参数检测的 `${N:-}` 守卫豁免集原先全程累积不重置——`launch.sh` 在守卫后紧跟 `shift`，`shift` 后 `$1` 语义变为「下一个可能未设置的参数」，会被早期守卫误豁免（漏报）；遇 `shift` 即清空豁免集，并以「shift 后裸 `$1`」探针验证必红、真实脚本保持全绿。

- **测试冗余检查盲区根治（rf-684）**：`check-test-redundancy.py` 完全重复比对对 62 个用例（self 间接调用无法静态解析）长期跳过——占位面集中在 `test_progress.py`（25）与 `test_market_hours.py`（12）。增强三档绑定解析：① `_class_attr_binding` 新增 setUp/setUpClass 内 `self.<attr> = <值>` 赋值解析（覆盖 self.r/self.fn 类 35 例）；② 无单一 return 的分支型 helper（_run/_call 类 27 例）取方法体 sha1 哈希为绑定；③ 三档均失败才跳过（跳过是保底而非默认）。盲区 62→0，全仓 9675 用例仍零重复；红验证：setUp 同体对 / 分支型 helper 同体对均报重复、不同绑定/不同方法体不误报；契约测试 36→40。缓存逻辑版本随脚本哈希自动失效，无需手动 bump。

### Changed

- **`cost_position` 收盘价提取复用共享单一事实来源（rf-685）**：开发期自审（36 小时实现技术债核对）发现 `analysis/cost_position.py` 自建的 `extract_closes` 与既有共享 `valuation_percentile.extract_closes`（`market_temperature` 同源复用）**同名二份实现且语义不同**——自建只读 `close` 键并过滤 0/负，共享做 `close→nav→price` 字段回退且只滤非有限值；正是「第二份实现即为新增技术债」面。按「复用优先于另写」收敛：删除自建副本，`report/cost_position.py` 改引共享提取并以 `bars or []` 防 `None` bars，区间有效性过滤（0/负/NaN/inf 不入极值）统一收敛到 `compute_window_position`（纯数学层职责）并补锁测试 `test_zero_close_excluded_from_range`（0 夹杂序列区间仍正确）；边缘分片的 extract 层用例改写为 `compute_window_position` 层断言（提取覆盖归 `test_valuation_percentile`）。
- **计划/自审文档去历史复盘痕迹**：`plan.md`（plan-55 预检细节收敛为评测方案引用、plan-70 状态行去掉批次快照叙事）、`review-findings.md`（开发期已修复 5 条收敛为摘要行，完整复盘归 changelog；rf-626 出带叙事收敛为当前行数与策略）、`docs/plan/` 六份在办设计/验证文件（仅保留最新状态内容：决策跨期反思设计去借鉴溯源改为直接设计描述、Jev 评测预检段收敛为设计约束、两份浏览器验证文件去另机/日期/迭代号复盘与红线元叙述）；folders.md 同步（docs/plan 行数/描述、移除已归档的报告对话式追问设计残留描述）

- **文档与实现对齐（TUI 菜单体系，rf-680）**：技术设计文档 §1.6.3 按实际菜单重写（静态 19 项实际排列、补 `[Q]` 报告对话式追问、`[T]`/`[Q]` 双门控 `FEATURE_GATED_ITEMS` 语义、`[S]` 面板四组分块取自 `GROUP_ORDER`/`GROUP_LABELS`、`[A]` 四模式键名、`[R]` 重载范围、页头状态行 `build_status_line` 五项），§1.6.1 模块表补 `handlers_log.py`/`handlers_qa.py`/`status_line.py` 三行；TUI 菜单手册同步：主菜单 `[D]`/`[1]`/`[I]` 标签对齐实际显示、[1] 缓存清单补全（refresh 组 18 模块）、[2] 附带清除 LLM 清单补生成后自检/持仓变动复盘归因/辩论三模块、[A] 名称替换表述改「品种X」。

- **文档与实现对齐（CLI/Web 渠道，rf-681）**：技术设计文档 §1.7.2 补 `report --prefer-source/--exclude-source`；§1.8.4 路由表补 `/api/whatif`、`GET /api/cache`、`POST /api/cache/cleanup`、`POST /api/qa/ask` 四行，§1.8.1/§1.8.8/§1.8.9 同步（handlers 路由清单、配置面板 9 块按 `features.groups` 四组分块、同源校验覆盖四个 POST 写路由）；Web 手册 §5 LLM 分析章节行改现行 7 模块名、§5.1 开关分块与「（影响报告）」标记口径对齐 `report_affecting` 下发、自检卡定位改「机制与诊断」区；CLI 手册 §10.1 改生成类菜单对照并声明无 CLI 等价项。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0（2026-10-13）
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
