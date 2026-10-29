# TUI 第三批改进实施方案

> **关联议题**：[`tui-interaction-design.md`](tui-interaction-design.md) 的 3.5 / 3.6 / 3.8 / 3.9 节。
> **本批范围**：`/` 筛选进面板（含 `NavState` 可见集合协议）、配置面板「可试可退」、页头瘦身、`TUI_ASCII` 符号表。
> **不变量**：主菜单键位与分组不变、击键基线不增、非 TTY 输出不变、宽窄两档折行不变。

---

## 1. 语义名

| 语义 slug | 中文名 | 归属 |
|:--|:--|:--|
| `nav_filter` | 面板筛选态（当前屏可见项集合 + 关键词重置口径） | `NavState` 新增 `visible` / `apply_filter` |
| `config_snapshot` | 配置面板会话快照（进入时拍快照，`U` 一键还原） | `handlers_config` |
| `first_run_notices` | 首用未就绪摘要（页头一行 + `?` 富详情） | `status_line` |
| `symbols` | 符号表单源（结构线/游标/实验标记/进度块，可切 ASCII） | `text_layout` |

---

## 2. 协议变更：`NavState.visible`

面板的帧由面板自己 `render(nav)` 逐行打印，运行时无法过滤行。筛选因此靠**可见集合**下放：

| 变更 | 内容 |
|:--|:--|
| `NavState` 新增 | `visible: set[int] \| None`（None = 全部可见）、`is_visible(i)`、`apply_filter(visible)`、`clear_filter()`、`filtered` 属性 |
| 游标移动 | `move()` 的 `navigable` 谓词与可见集合求交（筛选态只在命中项间回绕） |
| 面板渲染 | 渲染循环加一行 `if not nav.is_visible(i): continue`（8 个面板各一处） |
| 分派 | 单字符直达只对可见项生效；按到被隐藏项给一行提示（与首页口径一致） |
| 入口 | `panel_loop(..., filter_reader=None)`：`/` 调行输入取关键词，空回车清除，`Esc` 保持原筛选 |

接入节奏：`[S]`（18 项）与 `[M]`（线路表）已按上式接入；其余面板接一行 `if not nav.is_visible(index): continue` 即可启用，未接入者 `visible=None` 行为与现状一致。 |
| 页脚 | 运行时在帧前打一行筛选状态（`筛选「x」：3/18 项（/ 改词 · 0 清除）`），面板不感知文案 |

兼容口径：`visible=None` 时 `is_visible` 恒真、`move` 行为与现状逐字节一致——未接筛选的面板零改动。

---

## 3. 配置面板「可试可退」

- 进入 `[S]` / `[G]` / `[C]` / `[M]` 面板时拍内存快照（深拷贝当前配置）。
- `u` 撤销上一次单项改动、`U` 还原到进入时快照（一次性写盘 + 清页脚标记）。
- 不做草稿态（改动仍即时生效）：真需求是「别让我记原值」，且即时生效是功能开关裁剪菜单的前提。
- 页脚事实行：`本次改动 3 项（U 可全部还原）`，有改动才出现。

---

## 4. 页头瘦身

- 未就绪检测移出渲染：`status_line.first_run_notices()` 与页头状态行共用 TTL 记忆与 `reset_status_memo` 失效点。
- 页头只留一行：`📋 未就绪：持仓文件 · LLM（[G] 配置 · ? 看指引）`；全部就绪时整行消失。
- 详细引导（原来的两条长 bullet）移到首页 `?` 速查尾部，由同一 `first_run_notices()` 派生，不另写一份文案。

---

## 5. `TUI_ASCII` 符号表

- `text_layout.SYMBOLS`：`rule` / `branch` / `last` / `pipe` / `cursor` / `experiment` / `bar_full` / `bar_empty` / `dot_on` / `dot_off` / `arrow_body`；`TUI_ASCII=1` 时全部换 ASCII（`- | + > * # . O o >`）。
- 取用点集中：`text_layout`（结构线）、`switch_panel`、`panel_runtime.marker`、`status_line`、`handlers_switch`（⚗）、`progress.print_timing_summary`（█░）、`handlers_log`（⤷）。
- 硬约束：**列宽不变**（每个替换符显示宽度相同）——沿用「窄档每行 ≤ 列宽」用例回归。
- 机检：`src/python/tui/*.py` 与 `report/progress.py` 字面量中不得出现裸符号常量（除 `text_layout.SYMBOLS` 定义处）。

---

## 6. 顺序与验收

顺序：页头瘦身 → `TUI_ASCII` 符号表 → 配置面板快照 → `/` 筛选进面板（协议变更放最后，改动最集中）。

验收（可观察）：

1. 首用未就绪时页头只多一行；`?` 里能看到详细引导与菜单键。
2. `TUI_ASCII=1` 下全屏无制表符/方点类符号，每行显示宽度与不设该变量时**完全相同**。
3. 配置面板改 3 项后页脚显示计数，`U` 一键还原到进入时状态（磁盘与内存一致）。
4. 任一列表面板 `/` 可筛选，命中项间 `↑↓`/`j k` 回绕，`0` 先清筛选再返回；未接筛选的面板行为不变。
5. 击键基线不增；主路径（生成/配置/日志三条动线）语义不变。
