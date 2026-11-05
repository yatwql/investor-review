# 计划归档 — v0.17.x

> 归档时间：2026-11-04（v0.17.0 发布，本系列首份）；2026-11-05 v0.17.1 本批原表搬运；2026-11-05 v0.17.2 本批原表搬运
> 原始文件：`docs/managements/plan.md`
> 涵盖版本：v0.17.x 开发期完成项（含 v0.17.2）
> 归档内容：已完成任务节经 `release.py prepare` 自动搬入

---

## `plan-244` 「我的建议历史表现」用户可见视图（已完成）

**交付**：判断依据的结算摘要下新增「我的建议历史表现（按视界）」表——5/20/60 日已结算数 / 方向性样本 / 命中数 / 命中率 / 均值超额；命中判定复用 `decision_ledger.classify_direction_outcome`（含 ±1.5% 平盘不判定），命中率仅在方向性样本 ≥ 20 时给结论值，否则「命中/方向性（样本不足）」；只读账本、不受 `decision_reflection` 开关控制；双端同表，数据缺口行计入 gap 不丢样本。

## `plan-245` 依据块默认展开章首摘要三行（已完成）

**交付**：行动建议章首固定三行摘要（有效信号数与可信度档 / 风险预算超限项 / 纪律触发数；无超限/无触发写否定态，三段全不可用压一行空态），明细仍折叠；`build_headline()` 单源产出，HTML 在折叠块之前、Excel 写在块首，两端逐字一致；`headline` 进 `decision_basis_data` 契约，旧契约无该键回落单行 summary。

## `plan-247` 两套样式表公共规则去重（抽 `_base_styles.html`）——已完成

**现状**：`partials/_report_styles.html`（210 条规则）与 `_whatif_styles.html`（73 条）同名 39 条，其中 17 条归一化后逐字相同、另 13 条仅声明顺序/注释不同；真实有意差异 6 条（已登记在白名单）。重复面即「早年复制的基础样式」；一致性已由 `test_report_type_scale.TestSharedStylesheetParity` 守卫（同名规则逐字一致或显式白名单）。
**动作**：抽 `partials/_base_styles.html` 装公共面，两页各 `{% include %}` 引在页面样式之前（级联：基础在前、页面覆盖在后）。
**前置**：报告页缺「样式回归网」（只有调仓页有 `_GOLDEN_*_SHA256`），抽离会改变 CSS 块顺序，需要先有可比对的等价手段——本次以「归一化规则集哈希」补齐（见完成记录），无需截图。
**判据**：抽离后 ① 两页「选择器→声明」多重集与抽离前一致；② whatif golden 差异经确认为纯顺序变化；③ 报告页渲染快照无视觉差异。
**完成记录**：34 条两页逐字相同的规则移入 `partials/_base_styles.html`（87 行），`report_template.html` / `whatif_template.html` 各 `{% include %}` 引在页面样式之前（级联先后为前提）。**验收证据**（三项与改动前完全一致）：① 页内归一化「选择器→声明」多重集哈希（报告 9190e9f1… / 调仓 505214c4…）；② `@media` 块数（报告 13 / 调仓 4）；③ 去样式后正文的空白归一化哈希（报告 5ed41e14… / 调仓 82281384…）。前置②③落地为常驻回归网：新增 `TestReportCssRulesetBaseline`（报告页规则集哈希，搬移不变、增删改必变）与调仓页既有 golden 基线（复核记录写明本次差异仅来自搬移）。抽离脚本由初版「按规则文本替换」改为「按块区间删除」——初版会命中相邻同文本规则的偏移导致误删 `@media` 块，该教训已写进技术说明。另：注释解析须跳过 at-rule 整块（用大括号深度扫描而非正则屏蔽），否则 `@media` 前的缩进会被并入下一条规则的选择器。

## `plan-246` 报告模板内联样式去 Jinja 化（class 驱动）——已完成

**现状**：`src/static/tmpl/` 下多个 partial 把 Jinja 表达式放在 CSS 值位置（`style="order: {{ n }}"`、`style="color: {{ x | profit_color }}"`、`style="… {% if … %}color:…{% endif %}"`）。HTML 语言服务把它当 CSS 扫，单模板稳定报 28 条 `at-rule or selector expected` / `property value expected`（与模板逻辑无关的纯解析误报）。当前已用项目 `.pi-lens.json` 的 `lsp.disabledServers: ["html"]` 把该服务整体关掉止声，代价是 `src/static/web/index.html` 等非模板页也失去 HTML LSP 诊断。
**动作**：把动态样式改成 **class 驱动**——颜色走已有的 `.profit` / `.loss`（`report_template.html` 已有定义，与 `DESIGN.md` 色彩语义角色表一致），数值性样式（`order`、`font-weight`、`text-align`）走工具类：Jinja 只在 `class` 属性里做选择，CSS 值一律静态。逐步覆盖 `partials/` 下有该写法的文件，完成后可从 `.pi-lens.json` 移除 `lsp.disabledServers`（恢复 HTML LSP）。
**风险与验收**：涉及渲染，须逐章比对改动前后 HTML 输出（样式值一致）+ 跑 `src/test/unit/report/` 全绿 + 目测暗色主题与窄屏档（DESIGN.md 断点表）；禁止顺手改视觉（颜色/间距语义变都算越界）。曾试过的两种“小改”已证伪，不要重走：① 用 Jinja `%` 拼整个 `style` 属性（HTML 校验器报特殊字符未转义）；② 条件分支复制开标签（报标签未配对）。
**前置**：无硬门槛；优先级低于任何用户可见缺陷，仅在需要恢复 HTML LSP 或其写法的模板继续增多时启动。
**完成记录**：64 处动态内联样式清零（20 处 `order` 改由 DOM 顺序承载、40 处颜色/字号/字重改语义 class、1 处配置分布条改 SVG 属性宽度）。新增 `profit_class`/`price_type_class` 两个过滤器与 11 个工具类（颜色全部引用既有 token）；`report_template.html` 的 include 顺序对齐 `_REPORT_SECTION_DEFAULT`，`action` 与 `data_source_status` 各归位（渲染顺序与改动前一致）。守卫用例 3 条（模板静态扫描 + 渲染产物断言 + DOM 顺序/编号），报告套件 2827 通过。`.pi-lens.json` 已删除（html 语言服务恢复）。


> 完成态暂存本节，`release.py publish` 前的 archive 步搬入 `archived_plan.*`；不计入上方「在办」计数。
