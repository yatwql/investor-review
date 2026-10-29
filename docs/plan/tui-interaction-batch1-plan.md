# TUI 第一批改进实施方案

> **关联议题**：[`tui-interaction-design.md`](tui-interaction-design.md) 3.1 / 3.3 / 3.4 / 3.7 节。
> **本批范围**：长任务状态条与中止、错误尾巴单源、未知键全档单行、`j/k` 导航。共四项。
> **本批不变量**：主路径击键数不变（`tui_keystroke_baseline.json` 不动）、不新增「按任意键」闸门、非 TTY 输出逐字节等价、菜单键位不改。

---

## 1. 先定语义名

按「先定语义名再设计」，本批新增标识符一律用语义名，并登记 `technical.md`「功能语义命名表」：

| 语义 slug | 中文名 | 归属 |
|:--|:--|:--|
| `live_status` | 长任务状态条（单行原地刷新的当前阶段/耗时/ETA/中止提示） | `src/python/tui/live_status.py` |
| `CancelToken` / `StageCancelled` | 协作式取消令牌 / 阶段边界取消信号 | `src/python/report/progress.py` |
| `action_hints` | 动作短语单源（语义名 → 带菜单键的下一步短语） | `src/python/tui/action_hints.py` |
| `error_tail` | 错误尾巴（`[ERR]` 统一输出「原因 → 下一步」） | `src/python/tui/error_tail.py` |
| `nav_keys` | 面板循环的方向键别名开关（`j/k` 是否等义 ↑↓） | `panel_runtime.panel_loop` 形参 |

---

## 2. 议题 3.4 未知键全档单行（先做，最小）

**改点**：`src/python/tui/tui.py` 内层按键循环末段。当前窄档走 `_print_hint("未识别按键")` 并 `continue`，宽/中档 `break` 触发整帧重绘。改为**全档统一** `_print_hint(f"「{key.upper()}」未登记（? 看键位）")` + `continue`，删除按档位分叉的 `break`。

**连带**：`?` 在首页尚不存在（议题 3.6 第二项），本批不给首页 `?`，因此提示词只指菜单本身：`「X」未登记（键位见上方菜单）`——与窄档现有文案逐字一致，避免新增无用指路。

**用例**：

| 文件 | 断言要点 |
|:--|:--|
| `src/test/unit/ui/test_tui_menu_loop.py` | 宽档/中档按未登记键：帧不重绘（`_render_menu_frame` 调用次数不增）、多出一行 hint、循环继续；连续两次未知键各出一行 |
| 同上 | 窄档行为不变（既有断言保留，改为全档同语义断言） |

**风险**：宽屏 hint 行会压住页脚一行（与既有 `已清除筛选` 提示同位，视觉位置一致）。

---

## 3. 议题 3.3 错误尾巴单源

**现状**：`core/error_hints.py::hint_for` 已提供 `message + advice`，但 `advice` 全是自然语言（无菜单键路径）；且 TUI 有约 20 处 `[ERR]` 完全不经过它。

**设计**：

1. 新增 `src/python/tui/action_hints.py`：把 `status_line.ACTION_TEMPLATES` 迁入（键：语义名；值：带菜单键短语），并补本批需要的条目——`logs: "[D]→L 看运行日志"`、`config: "[G] 检查配置"`、`cache: "[1]/[2] 更新缓存"`、`llm: "[G]→L 配置 LLM"`、`report: "[B] 重新生成"`。`status_line` 改为 `from .action_hints import ACTION_TEMPLATES`（保留同名 re-export，`test_tui_menu_status` 的 patch 点与首键子集校验不变）。
2. 新增 `src/python/tui/error_tail.py`：`emit_error(message, action_key=None, *, advice=None, echo=print)` → 输出 `  [ERR] {message} → {短语}`（`advice` 非空时缩进续一行）。无 `action_key` 时按调用方给的兜底键，**禁止**输出裸「详见日志」。
3. 站点改造（只改「真错误」，输入校验类不动）：

| 文件 | 行位（`[ERR]` 站点） | 动作键 |
|:--|:--|:--|
| `handlers_log.py` | 读取运行日志失败 / 读取数据源健康历史失败 / 系统自检执行失败 | `logs` |
| `handlers_cache.py` | 缓存操作异常 | `cache` |
| `handlers_config.py` | 配置写入失败 / 无法读取 `llm_settings.json` | `config` |
| `handlers_whatif.py` | 基准文件缺失 / 持仓目录不可用 / 复制失败 / 读取失败 / 调仓对比不可用 | `report` 或 `config` |
| `tui_handlers.py` | 目录下未找到 xlsx | `config` |
| `handlers_holdings.py` | 持仓写入 / 文件被外部修改 / 文件不可访问 | `config` |

**不改**：`应为数字 / 必须大于 0 / 无效编号 / 账户名不能包含路径分隔符` 这类**就地纠正**输入校验——用户下一步动作就是「在同一条提示里重输」，加键路径反而干扰。

**机检**：`src/test/unit/ui/test_prompt_contract.py` 新增 `TestErrorTailHasAction`——AST 扫描 `src/python/tui/*.py` 中字符串含 `[ERR]` 的输出调用，要求该行含 `→`，或以豁免词起头（`应为`/`必须`/`不能`/`无效`/`不能包含`）。新增站点漏改即红。

**风险**：文案改动面 20 处，全部是输出字符串，无控制流影响；`test_handlers_log` / `test_handlers_holdings` 若有逐字断言需同步更新（改断言，不改语义）。

---

## 4. 议题 3.7 `j/k` 导航

**改点**：

| 文件 | 改动 |
|:--|:--|
| `tui.py` | 读键后归一：`j → KEY_DOWN`、`k → KEY_UP`（放在 Esc/字母分派**之前**，避免 `j`/`k` 被当成未登记字母） |
| `panel_runtime.py` | `panel_loop(..., nav_keys: bool = True)`；为 True 时把 `j/k` 归一为 ↑/↓；为 False 时原样交给 `on_text` |
| `handlers_switch.py` | `[S]` 面板传 `nav_keys=False`（该面板 `k` 已用于「窄档显示键名列」、`p` 用于重绘，冲突不可消解且不值得改名） |

**用例**：

| 文件 | 断言要点 |
|:--|:--|
| `test_tui_menu_loop.py` | `j`/`k` 在主菜单移动游标，与 ↑/↓ 等价（选中态与 Enter 派发目标一致） |
| `test_panel_runtime.py` | `nav_keys=True` 时 `j/k` 移动游标；`nav_keys=False` 时 `k` 落到 `on_text`（`[S]` 切换行为仍生效） |
| `test_keystroke_baseline.py` | 不更新基线（`j/k` 是**替代**路径，不是新增步骤） |

**契约批复**：`DESIGN-TUI.md` Keys 表 ↑/↓ 行补一行注记——`j/k` 全档等义，`[S]` 面板除外（`k` 另有职责）。

---

## 5. 议题 3.1 长任务状态条与中止（改动最深，最后做）

### 5.1 现状与可复用面（决定了成本比预估低）

| 已有件 | 位置 | 可复用点 |
|:--|:--|:--|
| 阶段计时 + 阶段开始广播 | `core/perf.py::PerfCollector.start/stop/_announce_stage`，经 `stage_announcer=reporter.stage_progress` 接到 TUI | **阶段边界天然是 `perf.start()`**，取消只需在这一个点检查，不必改 30 处编排 |
| 阶段状态 + ETA | `perf.stage_status()`、`estimate_stage_eta()`、`format_stage_status()` | 状态条文案单源，三渠道共用 |
| 中断收口 | `report/run_integrity.py::handle_interruption`（清临时文件 → 落 `status=interrupted` 运行记录 → 打印已写盘明细） | Ctrl+C 路径已走此函数，取消复用同一收口 |
| 运行守卫 | `orchestrator` 的 `@guard_run` | 取消信号在顶层捕获即可 |

**因此「中止」不是新能力，而是把已有的 Ctrl+C 收口换成一个不退出程序的入口。**

### 5.2 设计

1. **`CancelToken`**（`report/progress.py`，约 25 行）：`threading.Event` 包装 + `cancel()` / `cancelled` / `reason`。挂在 `PerfCollector` 上（构造参数可选，默认 None = 永不取消 → CLI / Web 行为零变化）。
2. **取消生效点**：`PerfCollector.start()` 在 `_announce_stage()` 之后检查 token，置位则抛 `StageCancelled(Exception)`。语义是「**在阶段边界停**」——不硬切线程、不打断网络请求，已完成阶段产物与缓存全部保留。
3. **`live_status`**（`tui/live_status.py`，约 150 行）：单行状态条。
   - `supported()`：`os.name == "posix"` + `sys.stdout.isatty()` + 未设 `TUI_PLAIN`；不满足则整套不启用（退回当前逐行 `[..]` 输出，**逐字节等价**）。
   - `enter()/update(text)/suspend()/close()`：`update` 用 `\r` + 行尾 `\x1b[K` 覆写；`suspend` 供所有 reporter 落地行（`info/ok/warn/error`）在 `print` 前清掉状态条、`print` 后重画。
   - 内容：`[..] 「LLM+新闻」· 已耗时 12s · 预计剩余 ~40s · q 中止`（阶段名/已耗时/ETA 取 `format_stage_status`，尾部再加中止提示）。
   - 刷新时机：阶段切换（`_announce_stage`）+ 后台 daemon 线程每 5s 一次心跳（只在 TTY 启动；`close()` 必定 join）。**不做**每 100ms 动画。
4. **按键检**：心跳线程内非阻塞轮询 stdin——POSIX 用 `select.select([sys.stdin], [], [], 0)`，Windows 用 `msvcrt.kbhit()`；命中 `q` 则 `token.cancel()`。检不到键的环境（管道/无 termios）自动退化为「只显示，不提供 q」，状态条尾部改显示 `Ctrl+C 中断`。
5. **收口**：`orchestrator` 顶层新增 `except StageCancelled:` → `run_integrity.handle_interruption(reporter)`（清临时产物 + 落 `interrupted` 记录 + 打印已写盘明细）→ 返回「本次中止」结果（**不抛、不退程序**）。TUI 侧打印 `[!] 已中止（完成 3/7 项，缓存已保留）→ [B] 重跑只补缺失`，随后照常打印耗时排行。
6. **Ctrl+C 保持现状**：仍由 `guard_run` 收口并退出程序（用户明确要退）。

### 5.3 触点汇总

| 文件 | 改动量 | 内容 |
|:--|:--|:--|
| `report/progress.py` | +45 | `CancelToken`、`StageCancelled`、`snapshot()`、`TuiProgressReporter` 的生命周期钩子（enter/suspend/resume/close） |
| `core/perf.py` | +15 | 构造收 `cancel_token`；`start()` 后检查并抛 |
| `report/orchestrator.py` | +10 | 顶层 `except StageCancelled` → 走收口、返回中止态 |
| `report/run_integrity.py` | ±5 | `handle_interruption` 增 `reason` 参数（`interrupted` 记录里区分「用户取消」与「Ctrl+C」） |
| `tui/live_status.py` | 新增 ~150 | 状态条渲染 + 心跳 + 键检 |
| `tui/tui_handlers.py` | +15 | 报告收尾：中止态文案 |
| `tui/handlers_report.py` | +10 | 创建 `CancelToken` 并交给 reporter/perf |

单文件行数红线：`perf.py` 706 → ~721，`progress.py` 218 → ~263，均在限内；新文件均 <200 行。

### 5.4 用例

| 文件 | marker | 断言要点 |
|:--|:--|:--|
| `src/test/unit/report/test_stage_cancel.py` | `unit_report` | token 置位 → 下一次 `perf.start()` 抛 `StageCancelled`；未置位时零影响（既有编排用例同时兜底） |
| 同上 | 同上 | 中止后已写产物仍在、临时文件被清、`perf_history` 落 `status=interrupted` 且 reason 可辨 |
| `src/test/unit/ui/test_live_status.py` | `unit_ui` | `supported()` 判据矩阵（TTY/非 TTY/`TUI_PLAIN`/Windows）；`update` 输出 `\r` + 清行；`suspend → print → resume` 序列正确；`close` 后输出静默 |
| 同上 | 同上 | 非 TTY：状态条完全不输出，reporter 输出与 `format_stage_status` 逐行一致（无 `\r`） |
| `src/test/unit/ui/test_live_status_edge.py` | `edge` | 极窄列（40）截断、心跳线程在 `close` 后退出（无残留线程） |
| `src/test/unit/ui/test_handlers_report.py` | `unit_ui` | 中止态收尾文案（`[!] 已中止（完成 N/M 项…）→ [B] 重跑只补缺失`） |

### 5.5 契约批复（`DESIGN-TUI.md`）

1. `Feedback` 表新增「长任务」行：状态条单行、四段式（动作/阶段/耗时/中止键），落地行打印前必先清状态条；非 TTY 退回逐行。
2. `Feedback` 表「错误」行补一句：下一步动作经 `action_hints` 单源，形如 `→ [D]→L 看运行日志`。
3. `Do's` 补一条：状态条只承载「正在做什么」，已完成的动作仍走落地行（`[OK]`），不把历史流水塞进状态条。
4. 闸门白名单**不变**（本批不新增闸门）。

---

## 6. 落地顺序与验收

**顺序**（互不阻塞，从便宜到深入）：议题 3.4 → 议题 3.3 → 议题 3.7 → 议题 3.1。每一步：先补失败用例 → 实现 → `pytest src/test/unit/ui src/test/unit/report -q`；四项全绿后跑一次 `test-runner.py --mode dev-verify`。

**验收口径**（可观察，不看代码）：

1. 完整报告生成过程中，末行常驻单行状态条，阶段切换即变；按 `q` 在下一个阶段边界停下并**回到菜单**，已完成产物与缓存保留，`perf_history` 记 `interrupted`。
2. `investor-review --tui > out.txt` 的输出与改进前逐字节等价（无 `\r`、无状态条）。
3. 宽屏按未登记键只多一行提示，菜单帧保持不动。
4. 任意 `[ERR]` 行都带 `→ 键路径`（输入校验类除外）。
5. 主菜单 `j/k` 与 ↑/↓ 行为一致；`[S]` 面板 `k` 切键名列仍生效。
6. `tui_keystroke_baseline.json` 无变更。

## 7. 文档与门禁同步清单

| 文档 | 同步内容 |
|:--|:--|
| `docs/managements/DESIGN-TUI.md` | 上述四项契约批复（Keys / Feedback / Do's） |
| `docs/manuals/how-to-use-tui-menu.md` | 键位段补 `j/k`；新增「长任务与中止」小节（状态条、`q`、非 TTY 行为） |
| `docs/managements/technical.md` | 6.7 功能语义命名表登记 5 个 slug |
| `docs/managements/folders.md` | 目录树 +3 文件（`live_status.py` / `action_hints.py` / `error_tail.py`），统计表随之刷新 |
| `docs/managements/test-coverage.md` | `test-collect-coverage.py --update-docs` 回写计数 |
| `src/test/data/fixtures/tui_keystroke_baseline.json` | **不动**（本批零新增击键） |

## 8. 风险与回滚

| 风险 | 缓解 |
|:--|:--|
| 状态条与 reporter 打印交错出鬼影行 | 只在 reporter 类内部走 `suspend/resume` 单点封装；用例钉住「print 前清、print 后重画」序列 |
| `StageCancelled` 被中途某个 `except Exception` 吞掉 | 协作式取消天然可延迟到下一阶段边界；方案明示「最迟下一阶段生效」，不走线程强杀 |
| 心跳线程泄漏 | 仅 TTY 且仅报告生成期启动；`close()` 内 `join(timeout)`；`live_status` 用例断言线程数复原 |
| 取消语义被误用成「强制中断」 | 契约写明：取消只在阶段边界判定，进行中的网络请求与写盘不打断 |
| 20 处错误文案改动牵动既有逐字断言 | 逐站点改断言（不改语义），改动集中在 `unit/ui` 与 `unit/handlers` 两个目录 |

## 9. 明确不做（本批）

- 不做「中止后续跑」（只给「重跑只补缺失」的建议，编排不改）。
- 不做阶段内百分比（阶段内无细分粒度，硬造会误导）。
- 不做首页 `?` 与 `/` 筛选通用化（属第二批）。
- 不做分页查看器（属第二批）。
