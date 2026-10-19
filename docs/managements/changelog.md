# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.7]**（2026-10-19）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.8-dev] - 开发中（未发布）

- **交互契约落地（第一批）**：新建 `docs/managements/DESIGN-TUI.md`（终端交互契约：键分工总表 / 提示四成分模板 / 默认项与取消标注 / 术语对照 / 反馈口径 / 护栏 / 未覆盖面）与结构守卫 `test_design_tui_doc.py`（9 例），使 TUI 改动首次有「唯一判据 + 契约测试」，与 Web 侧 `DESIGN.md` 对称
- **提示语模板化**：新增 `tui/prompt_text.py`（`panel_prompt` / `confirm_prompt` / `keys_help_lines` / `item_detail_lines`），7 处面板提示由手写字面量改为模板产出——「选择 > 」「缓存管理> 」这类连返回键都不说的裸提示消失，提示恒含「动作+示例 · 默认项 · 帮助入口 · 返回键」；机检 `test_prompt_contract.py` 三规则（panel_loop 提示必须来自模板 / 禁止把「回车取消」藏进括注 / input_choice 字面量提示必须声明回车行为）
- **`?` 帮助全面板可用**：帮助入口下沉到 `panel_runtime`（`?` 无参=本面板可用键一览，`?键`=单项详情），面板可经 `on_help` 自处理详情、返回 False 回落通用一览——此前 `?编号` 仅 `[S]` 面板有，其余面板只能猜
- **回车语义收敛**：What-if 文件选择的两处「（直接回车取消）」改为「回车=取消 / 输入编号选择」置句首声明，日志级别筛选补「回车=全部级别 · Esc 取消」默认项标注——回车不再在不同提示处暗示相反后果

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.7（2026-10-13 ~ 2026-10-19）
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
