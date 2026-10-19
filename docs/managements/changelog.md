# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.7]**（2026-10-19）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.8-dev] - 开发中（未发布）

- **交互契约落地（第一批）**：新建 `docs/managements/DESIGN-TUI.md`（终端交互契约：键分工总表 / 提示四成分模板 / 默认项与取消标注 / 术语对照 / 反馈口径 / 护栏 / 未覆盖面）与结构守卫 `test_design_tui_doc.py`（9 例），使 TUI 改动首次有「唯一判据 + 契约测试」，与 Web 侧 `DESIGN.md` 对称
- **提示语模板化**：新增 `tui/prompt_text.py`（`panel_prompt` / `confirm_prompt` / `keys_help_lines` / `item_detail_lines`），7 处面板提示由手写字面量改为模板产出——「选择 > 」「缓存管理> 」这类连返回键都不说的裸提示消失，提示恒含「动作+示例 · 默认项 · 帮助入口 · 返回键」；机检 `test_prompt_contract.py` 三规则（panel_loop 提示必须来自模板 / 禁止把「回车取消」藏进括注 / input_choice 字面量提示必须声明回车行为）
- **`?` 帮助全面板可用**：帮助入口下沉到 `panel_runtime`（`?` 无参=本面板可用键一览，`?键`=单项详情），面板可经 `on_help` 自处理详情、返回 False 回落通用一览——此前 `?编号` 仅 `[S]` 面板有，其余面板只能猜
- **回车语义收敛**：What-if 文件选择的两处「（直接回车取消）」改为「回车=取消 / 输入编号选择」置句首声明，日志级别筛选补「回车=全部级别 · Esc 取消」默认项标注——回车不再在不同提示处暗示相反后果
- **三渠道用户词对齐（波 3 收尾）**：端点重试状态改由 `core/system_info.circuit_display` 唯一归一（`熔断中`→`暂时失败`，未知文案透传），TUI / CLI 状态表 / Web 工作台健康面板统一显示「自动重试：正常 / 暂时失败」，移除了 TUI 侧本地映射表；日预算超限确认在 TUI / CLI / Web（后端 409 与错误提示 + 前端弹层）统一为「用已有结果继续」；Web 多链线路说明改「按下列顺序作为备用」。契约边界写明：报告/Web 的数据降级口径沿用 `DESIGN.md`，日志/代码注释/FAQ 保留技术词。守卫 `integration/test_channel_vocabulary.py`
- **主菜单按任务分组 + `/` 关键词筛选（波 3）**：主菜单由 19 项平铺改为四组渲染（生成报告 / 数据与查看 / 配置 / 诊断与排查），退出项单列——组标题只降低扫读成本、不改任何按键；新增 `/` 筛选（先比按键再比标签文字，筛选态只渲染命中项、`↑↓` 在命中集内回绕、按到隐藏项给单行反馈、`0` 先清筛选）。机检：分组覆盖全项一次（退出项除外）、筛选命中与筛选内回绕、分组标题与筛选态渲染。**「编号为主入口」经评估未采纳**（键位已在三渠道文档稳定，全量重编号需改约 200 处文档且要放宽菜单块机检，收益低于回归面），理由记入 `DESIGN-TUI` Known Gaps
- **人因门禁落地（波 3）**：三条主路径 E2E 动线（生成完整报告且只强刷指定模块 / 改一个功能开关并确认生效 / 按级别筛日志）同时断言「击键数不增」与「关键用户词上屏」，快照 `tui_flow_contract.json`；击键基线补 `/` 筛选动线并共用一个驱动器 `src/test/_tui_flow.py`。分层：P0 只跑生成主路径 1 条，P2 跑全 3 条
- **按键闸门收敛（波 2）**：`press_any_key()` 从 27 处调用点收敛为 5 处长输出闸门（运行日志详情 / 数据源健康历史 / 系统自检结果 / 报告收尾摘要 / 缓存更新结果摘要），其余 22 处（配置面板收尾、缓存清理、What-if 完成、持仓读取错误、调度层取消与异常）一律直接回菜单——取消与错误反馈不再多按一次键。白名单由 `test_prompt_contract.py::TestPressAnyKeyGateWhitelist` 机检守住；击键数基线同步收紧（`[S]` 只读动线 5→4、`[3]` 缓存面板动线 4→3）
- **术语改写 + 禁用词机检（波 2）**：上屏文案去除工程内部词——「是否强制刷新 LLM？（强刷=重新调模型计费）」→「是否重新生成全部 AI 分析？（f=跳过已有结果重新调用 AI，会产生费用；默认=用已有结果，免费但可能不是最新）」，「降级走缓存」→「用已有结果」，页头「降级源」→「备用源」，`[S]` 页脚「配置漂移」→「与出厂默认不一致」，`[M]` 菜单「降级顺序」→「备用顺序」，LLM 状态面板「熔断」→「自动重试: 正常/暂时失败」；新增机检 `test_prompt_contract.py::TestForbiddenVocabulary`（术语表左列禁上屏：CJK 术语扫全量字面量并剔除 docstring/日志消息，英文术语仅扫展示型调用以免误报程序标识符，内部查表键豁免须校验仍被需要）

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
