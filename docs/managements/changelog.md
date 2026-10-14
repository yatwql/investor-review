# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.1]**（2026-10-14）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.2-dev] - 开发中（未发布）

### Fixed

- **`scripts/launch.sh` 无参启动崩溃（rf-682）**：`set -euo pipefail` 下裸引用 `$1`/`$VENV_PATH`，无参调用（默认 TUI 路径）或未设 `VENV_PATH` 时直接 `unbound variable` 退出；改 `${1:-}`/`${VENV_PATH:-}` 默认展开，新增 `test_launch_script_regression.py` 回归用例 4 例。

### Changed

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
