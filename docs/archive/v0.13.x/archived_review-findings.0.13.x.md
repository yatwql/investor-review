# 自审记录归档 — v0.13.x

> 归档时间：2026-10-14（v0.13.2 发布，开发期已修复批次迁入）
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.13.x 开发期已修复项（v0.13.1 → v0.13.2）
> 归档内容：由各版本发布时人工迁入

---

## 开发期已修复（0.13.2-dev）

> 完整复盘见 `changelog.md` 0.13.2-dev 段；此处仅摘要行。

- rf-680 已修复（2026-10-14）：technical.md §1.6.3 TUI 菜单体系与实现对齐（含 TUI 手册同步）
- rf-681 已修复（2026-10-14）：technical.md §1.7/§1.8 与 Web/CLI 手册的路由、配置面板、LLM 章节对齐
- rf-682 已修复（2026-10-14）：`scripts/launch.sh` 无参启动 unbound variable 崩溃（默认展开修复 + 4 回归用例）
- rf-683 已修复（2026-10-14）：`launch.sh` 死代码 `$?` 清理 + `test_shell_contract.py` 静态机检，封堵 shell 行为门禁盲区（含豁免集遇 shift 清空的漏报精度补丁）
- rf-684 已修复（2026-10-14）：`check-test-redundancy.py` 完全重复比对三档绑定解析，根治 62 例跳过盲区
- rf-685 已修复（2026-10-14）：`cost_position` 收盘价提取消除同名二次实现——复用 `valuation_percentile.extract_closes` 共享单一事实来源，区间有效性过滤收敛至 `compute_window_position`
