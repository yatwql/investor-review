# TUI 统一交互运行时（panel_runtime）设计

> **关联**：`docs/managements/plan.md` → **plan-155**；用户实测反馈（上下键导航仅首页生效，S 面板弱反馈、P 面板无效）；rf-729/rf-723/rf-725 等一串交互修补是本文的直接动因。
> **目的**：把「读键 → 导航态 → 派发 → 反馈/重绘」的循环控制流从 13 处面板各自手写的实现中抽成**单一运行时**，使架构约束 **C29「分档只改版式不改语义」**从「测试逐处兜底」升级为「构造性成立」。
> **状态**：待评审；本文件不含代码改动。

---

## 1. 背景与问题

### 1.1 现状碎片化的证据

词汇层已单源（`tui_keys.py` 键名标准化 / `text_layout.py` 折行盒线 / `switch_panel.py` S 面板排版），但**控制流层从未抽出**——每个面板自己手写 while 循环，导致：

| 历史缺陷（changelog 可溯） | 根因 |
|---|---|
| Esc 取消缺失，逐处补 14 个提示（plan-151） | 循环控制流无单源，每处自行处理输入 |
| 窄屏反馈两套口径（静默 vs 单行，C29 才统一） | 分档语义靠人肉遵守 |
| 方向键只给了 S 面板，其余面板完全无导航（本次用户反馈） | 导航态是 S 面板内联变量（`cursor`/`cursor_engaged`），不是共享设施 |
| S 面板导航「像没反应」（游标只在临时反馈行，重绘后无行内标记） | 同上，反馈形态各自为政 |
| 方向键拆包误判孤 Esc → 误退出/误触发（rf-723/725/726） | 读键层缺陷叠加各循环对 None/未知键的差异处理 |

`TestTierSemanticParity`（5 例）在**逐面板**断言「窄/宽同语义」——语义没有单源承载，只能靠测试逐处兜底，新增面板天然漏防。

### 1.2 主循环是语义原型而非特例

`tui.py` 主菜单循环实际是**导航语义最完整的实现**（全档 ↑↓/Enter/Esc/直达键/原地重绘/未登记键反馈）。问题不是「首页做了导航而子菜单没做」，而是**这份语义只存在一份、写死在首页**，子菜单无法继承。设计方向：把导航态从主循环**抽出为 NavState**（主循环成为第一个调用方），再让全部列表面板收敛到同一语义。

---

## 2. 现状盘点（全量输入点清单）

### 2.1 列表/选择型（有 N 个候选项 → 迁移目标）

| # | 面板 | 位置 | 现状输入方式 | 特殊语义 |
|---|---|---|---|---|
| 1 | 首页主菜单 | `tui.py::main` | `get_key` 自有循环 | 原地重绘、Esc 双击确认、直达键、busy 锁 |
| 2 | `[S]` 功能开关 | `handlers_config._cmd_config_llm_modules` | `input_choice(arrows=True)` + 内联游标 | 复杂文法：`?3` / `r 3` / `ra` / `x` / `k` / `p` / `键名=on\|off`；窄档反馈行、宽档重绘 |
| 3 | `[P]` 报告章节 | `_cmd_config_report_boards` | `input_choice` 编号 | 无导航（用户反馈核心痛点之一） |
| 4 | `[A]` 匿名化 | `_cmd_config_anonymization_mode` | `input_choice` 编号 | 行首 `►` 当前模式标记 |
| 5 | `[I]` 指数池 | `_cmd_config_comparison_indices` | `input_choice` 字母 A/D/R/0 | 字母派发 |
| 6 | `[I]` 删除指数子流程 | `_remove_comparison_index` | 编号列表 + `input_choice` | 短列表 |
| 7 | `[M]` 多链路优先级 | `_cmd_config_llm_providers` | 「输入两个编号交换」 | **选两次**语义 |
| 8 | `[D]` 目录信息子菜单 | `_cmd_config_dir_info` | `input_choice` 字母 C/F/O/M/B | 字母派发 |
| 9 | `[4]` 缓存管理 | `handlers_cache._cmd_cache_management` | 命令 3/B | 统计首屏后命令循环 |
| 10 | 持仓文件选择 | `tui_handlers.select_holdings_file` | 编号列表 | 一次性列表 |
| 11 | What-if 目标选择 | `handlers_whatif._select_target_file` | 编号列表 | 同上 |
| 12 | What-if 候选路径 | `handlers_whatif._input_candidate_path` | 1/2/回车取消 | 3 选项短菜单 |
| 13 | QA 报告选择 | `handlers_qa._select_report` | 编号列表 | **回车 = 默认最新** |

### 2.2 线性提示型（不迁移）

y/N 确认（`handlers_report` 5 处）、日期/路径/代码录入（`handlers_whatif`/`handlers_config`）、级别筛选（`handlers_log`）、QA 长文本提问（`handlers_qa`）。它们是**单值录入**不是候选列表，方向键对它们无语义——维持 `input_choice`/`input()`，Esc 取消语义不变。

---

## 3. 目标架构

### 3.1 分层位置

```
tui_keys.py（词汇：键名标准化、input_choice 读键）      ← 不动
text_layout.py / switch_panel.py（词汇：排版原语）      ← 不动
─────────────────────────────────────────────
tui/panel_runtime.py（新：控制流单源）                  ← 本次新增
  NavState      导航态状态机（从主循环抽出）
  PanelItem     面板条目声明（键/标签/动作/类型）
  panel_loop    循环运行时（读键→派发→反馈→重绘）
─────────────────────────────────────────────
handlers_*.py（面板 = 声明数据 + render(nav) + 文法钩子）← 变薄
```

### 3.2 API 契约（草案）

```python
# tui/panel_runtime.py

@dataclass(frozen=True)
class PanelItem:
    key: str                       # 派发键（"3" / "A" / "0"…），直达键与导航派发同源
    label: str                     # 显示名（render 自取）
    action: Callable[[], None] | None
    kind: Literal["action", "return", "info"] = "action"

class NavState:
    """列表导航态：从主循环抽出的唯一导航语义实现。

    - ↑/↓ 移动游标（回绕），engaged 置位；
    - engaged 前的空回车**不派发任何项**（各面板原语义由 default_key 承接）；
    - 直达键命中时游标同步到该项（视觉位置与实际派发一致）。
    """
    cursor: int
    engaged: bool
    def move(self, key: str) -> bool          # KEY_UP/KEY_DOWN → 移动并 True
    def marker(self, index: int) -> str       # "▸" if engaged and index == cursor else " "
    def select(self, items: Sequence[PanelItem]) -> str | None
                                              # engaged 空回车 → 选中项 key；否则 None

def panel_loop(
    items: Sequence[PanelItem],
    *,
    render: Callable[[NavState], Iterable[str | None]],   # 面板自绘行（nav.marker 注入行内高亮）
    prompt: str,
    read: Callable[..., str | None],                      # 由面板传入模块级 input_choice（保测试 patch 点）
    repaint: Literal["loop", "feedback"] = "loop",        # "loop"=每轮整屏重绘 / "feedback"=窄档只回反馈行
    on_text: Callable[[str], bool] | None = None,         # 非条目文本回退（S 面板文法钩子）
    default_key: str | None = None,                       # 未导航空回车的默认派发（QA="1" 最新）
    pick: int = 1,                                        # 需按 Enter 收集的次数（[M] 交换 = 2）
    on_picked: Callable[[tuple[str, ...]], None] | None = None,  # pick 完成回调：选中 key 序列交面板（[M] 拿到 (a, b)）
) -> None:
    """循环：读键 → NavState/派发/反馈 → render 重绘。Esc/None → 返回。

    pick=1 时派发选中项的 `item.action`；pick>1 时**不逐项调 action**，
    收满序列后调 `on_picked(tuple)`（缺 on_picked 属编程错误，上抛）。
    """
```

### 3.3 关键设计决策

| 决策 | 理由 |
|---|---|
| **读键经 `read=` 注入而非运行时自 import** | 既有面板测试大量 patch `handlers_config.input_choice`——面板在调用处传模块级名字（函数体内全局名查找在调用时发生），mock 照常生效，迁移不破坏既有测试 patch 点 |
| **`render(nav)` 由面板自绘行，运行时不注入标记** | S 面板有 `format_item` 复杂排版、匿名化面板有 `►` 标记、其余面板行结构各异——运行时只提供 `nav.marker(i)`，行内布局归面板，避免运行时长出排版分支 |
| **NavState 语义以主循环为真值** | 主循环是全档验证过的最完整实现；抽出即锁定，`TestTierSemanticParity` 的断言升级为运行时级 |
| **`on_text` 回退钩子承接复杂文法** | S 面板 `?3`/`r 3`/`键名=on\|off` 等非条目输入走此钩子；运行时对「非键、非空、非方向」输入的唯一职责是转交钩子（无钩子 = 统一「无效选择」反馈） |
| **`pick=2` 原生支持选两次** | `[M]` 面板交换语义 = Enter 选第一项、移动、Enter 选第二项 → `on_picked((a, b))` 回调交面板走既有 reorder 写路径；同时保留直接输入 `3 1` 文本（走 `on_text`） |
| **`default_key` 承接「空回车默认」** | QA「回车 = 最新报告」；无默认的面板传 None，未导航空回车给统一反馈，不误触派发（S 面板既有防误触语义） |
| **`Esc` → 运行时返回**（不抛异常） | 与现有 `input_choice → None → break` 路径同构；嵌套提示的 `PromptCancelledError` 通道不动 |
| **不引入 curses/textual 等全屏框架** | 现有 raw-input 基座已解决拆包/跨平台/手机 SSH 等实际问题，框架替换风险远大于收益 |

### 3.4 C29 的构造性成立

分档差异被压缩到 `repaint` 策略参数 + 面板 `render` 内的 `layout_tier` 分支两处；**导航/派发/Esc/反馈语义只存在于运行时一份**。新增面板写声明即可合规，不可能再出现「这个面板忘了方向键」。

### 3.5 架构约束对照（逐条相关项）

| 约束 | 对照结论 | 本设计主动义务 |
|---|---|---|
| **分档只改版式不改语义** | 无冲突，本设计即其构造性承载 | 导航/派发/反馈语义唯一实现于 `panel_runtime`；分档仅存于 `repaint` 参数与 `render` 内 `layout_tier` 分支 |
| **文件行数红线（主程序 >1000 行）** | **风险点**：`handlers_config.py` 已 982 行逼近红线，S 面板在原文件内改必然破线 | 迭代 5 前置抽壳（switch 面板迁出独立模块，`handlers_config.py` 回落 <800）；`panel_runtime.py` 自设 ≤800 行预算（警戒区即拆分触发线） |
| **渲染期数据不写模块级全局**同理 | NavState 必须是每次 `panel_loop` 调用的**实例态** | 运行时模块内零可变全局；运行时级测试断言无新增模块级可变状态（`tui_keys` 拆包残留标志属读键层既有设计，不在本次范围） |
| **中文报错与单源反馈**（日志与着色） | 交互层反馈不走 logging（无诊断价值且污染控制台） | 运行时不打日志；反馈前缀沿用既有 UI 契约 `[..]/[OK]/[!]`；着色复用 `tui_menu` 色常量，不新建色值 |
| **功能开关唯一事实来源** | 本重构**不新增 feature flag**——内部重构无用户可感知的开关语义，回退 = git revert 单迭代提交；新增开关反而污染注册表 | 决策已定，记录于 §5 风险表；实施阶段不再重议 |
| **薄入口**（渠道架构 1.4 节） | `panel_runtime` 是 TUI 渠道内共享层，不承载业务 | 派发动作、取数、写配置全归面板回调；依赖方向见 §3.7，由 `test_channel_layering` 扩展守护 |

其余架构约束与终端交互层无交集，不适用。

### 3.6 退出与取消语义矩阵（契约硬条款）

每次输入 → 运行时动作，全表如下；运行时**只处理用户取消，永不吞掉 Ctrl+C/EOF/编程错误**（历史上 Esc 逐处补 14 处即因无此单源契约）：

| 输入 | 运行时动作 |
|---|---|
| `KEY_UP` / `KEY_DOWN` | `NavState.move`（游标回绕、engaged 置位），按 `repaint` 策略触发重绘/反馈 |
| Enter + 已导航 | 派发选中项 key；`pick>1` 阶段内不派发，给「已选 x/N」单行反馈 |
| Enter 未导航 | `default_key` 非 None → 派发之（QA 回车=最新）；否则统一单行反馈，**不误触派发**（各档同语义，C29） |
| 单字符命中 `item.key` | 游标同步至该项 + 直达派发（视觉位置与实际派发一致） |
| 其他文本 | 转交 `on_text` 钩子；无钩子 → 统一「无效选择」单行反馈 |
| Esc（`input_choice` → None） | `panel_loop` **返回**（不抛异常）——退出一级 = 回到调用者（`execute_item` → 主循环） |
| Ctrl+C（`KeyboardInterrupt`） | **原样上抛**，运行时永不捕获（与面板既有 except 链衔接） |
| `EOFError` | **原样上抛**（非交互管道环境由面板既有 except 处理） |
| `render`/`on_text`/`action` 内异常 | **原样上抛**（编程错误 fail-fast，不吞） |

取消粒度：`panel_loop` 返回只退一层；嵌套提示（如 `[D]`→`[C]` 录入）的 Esc 取消仍由 `input_choice → None` 承接，运行时不改变层级关系。

### 3.7 依赖方向与渠道边界

- **允许 import**：`tui_keys`、`text_layout`（+ 标准库）。**禁止 import**：`handlers_*`、`config`、`report`、`llm`、`cache`——动作与取数全归面板，运行时保持零业务依赖（薄入口在渠道内的延伸）。守护：`test_channel_layering` 扩展 `panel_runtime` 依赖白名单断言。
- **三渠道边界**：运行时是 TUI 渠道内设施；Web/CLI 无终端导航问题，不在范围。迁移不触碰各面板委托的共享编辑层调用（`apply_config_edit`/`config.features` 等），薄入口不破。

---

## 4. 迭代实施计划（8 迭代，每迭代独立可交付、含可验收标准）

**通用完成定义（每个迭代均适用）**：改动提交时 pre-commit 十守护全过（`check-file-length`/`check-semantic-index`/`check-code-traces`/`check-doc-drift` 等）；收尾 `.venv/bin/python scripts/test-runner.py --mode dev-verify` 全绿；每迭代**一个语义 commit（组）**，回滚粒度 = 迭代边界。

| 迭代 | 内容 | 风险 |
|---|---|---|
| 1 | `panel_runtime.py` 骨架 + 运行时级测试（纯新增） | 低 |
| 2 | 直迁无文法面板：`[P]` `[A]` `[D]` `[4]` 缓存管理 | 低 |
| 3 | 文件/报告选择四处 + 重复表渲染收敛为 `render_entry_table` | 低 |
| 4 | `[I]` 指数池（含删除子流程） | 低 |
| 5 | `[S]` 面板：5a 抽壳（纯移动）→ 5b 迁移（on_text 文法钩子），**两个 commit** | **高** |
| 6 | `[M]` 面板（pick=2 + 直接文本双通道） | 中 |
| 7 | 主循环接入 NavState（机械等价替换，循环结构/Esc 双击/原地重绘/busy 锁不动） | 中 |
| 8 | 治理收尾：文档触点全落地 + 逐面板 parity 用例退役 + rf-730/plan-155 状态更新 | 低 |

### 4.1 逐迭代验收标准（机器可检口径）

**迭代 1（运行时骨架）**
- `.venv/bin/python -m pytest src/test/unit/ui/test_panel_runtime.py -v` 全绿：导航/回绕/防误触/直达同步/Esc 返回/pick 阶段/default_key/两档 parity/「零模块级可变状态」断言（§3.5 实例态义务）；
- `test_channel_layering` 新增 `panel_runtime` 依赖白名单断言通过（§3.7：只许 `tui_keys`/`text_layout`）；
- 全仓无任何既有面板行为变化（`git diff --stat` 仅新增文件）。

**迭代 2（`[P]` `[A]` `[D]` `[4]`）**
- 既有面板测试**零改动**通过（`test_handlers_config.py` 对应类 + `test_handlers_cache.py`）；
- 新增导航用例：每面板 ↑↓ 移动可见 `▸` 行内标记 + Enter 派发选中项；
- 手动冒烟两档：`COLUMNS=100` 与 `COLUMNS=40` 下 ↑↓/Enter/Esc 行为一致（仅版式差）；Esc 即时返回不丢。

**迭代 3（文件/报告选择四处 + 表渲染收敛）**
- 既有测试零改动通过（`test_tui_handlers.py` / `test_handlers_whatif.py` / `test_handlers_qa.py`）；
- grep 断言：三处同构表头格式串收敛后**全仓仅一处定义**（重复渲染消除的机器证据）；
- QA `default_key` 用例：未导航回车 = 最新报告（原语义不变）。

**迭代 4（`[I]` 指数池）**
- 既有指数池用例零改动通过；删除子流程导航用例新增；字母菜单（A/D/R/0）直达 + 导航双通路用例。

**迭代 5a（抽壳，纯移动 commit）**
- `git diff` 仅文件移动 + import 路径行，**零逻辑变更**；
- `handlers_config.py` < 800 行（C28 警戒区下方，原 982）；
- 全部既有 S 面板测试零断言修改通过。

**迭代 5b（S 面板迁移）**
- `test_handlers_config_nav.py` + `test_switch_panel_layout.py` **断言零修改**全绿（只许 import 路径行变更——行为等价由测试厚度背书）；
- S 面板全文法回归清单逐项有用例：`?3`/`r 3`/`ra`/`x`/`k`/`p`/`键名=on|off`/编号切换/键名直取；
- 防误触：未导航裸回车不切换（既有用例保持）。

**迭代 6（`[M]` pick=2）**
- `test_handlers_llm_providers.py` 零改动通过；新增 pick=2 用例（两次 Enter → 触发 reorder 派发）+ 直接输入 `3 1` 文本通道用例。

**迭代 7（主循环）**
- `test_tui_menu.py` 全绿（含 `TestMainLoopExitKeys`/`TestTierSemanticParity`/原地重绘用例）；
- diff 审查：主循环变更仅「内联游标变量 → NavState」等价替换，无分支增删；
- Esc 双击确认/直达键/busy 锁路径人工抽验一轮。

**迭代 8（治理收尾）**
- §8 文档触点清单逐项落地（`check-doc-drift --ci` 过）；
- `plan.md` plan-155 状态更新为完成（含归档迁移：本设计文档随完成态移入版本归档子目录）；`review-findings.md` rf-730 移入已解决区；
- 逐面板 parity 用例退役后 `check-test-redundancy --ci` 干净；
- `testplan.md` 追溯表双向一致（`check-requirement-trace --ci` 过）。

**顺序原则**：风险递增、文法复杂度递增；S 面板（迭代 5）在简单面板全部验证运行时成熟后再动；主循环（迭代 7）只做等价替换，不做行为变更；治理收尾（迭代 8）独立成迭代，避免「顺手改文档」被遗漏。

---

## 5. 风险与回滚

| 风险 | 缓解 | 回滚粒度 |
|---|---|---|
| S 面板文法回归（最厚测试面） | 迭代 5b 验收 = 断言零修改全绿 + 全文法清单逐项用例；5a/5b 分 commit | 5b 单独 revert，5a 抽壳保留（纯移动无风险） |
| 主循环行为漂移（Esc 双击/原地重绘有 rf 历史） | 迭代 7 只做等价替换、diff 审查入验收、`test_tui_menu.py` 全绿为门 | 主循环 commit 单独 revert，不影响已迁面板 |
| 方向键拆包问题在新循环复现 | **读键层（`tui_keys`）不在迁移范围**——拆包防护三件套原样复用；pty 整包方向键既有用例为门 | 不适用（未动） |
| 运行时抽象泄漏（面板绕过运行时直接读键） | 依赖白名单断言 + 「列表面板不得自建 while 输入循环」写入 technical.md 架构约束章节的 TUI 小节 | 逐面板 revert |
| 迭代中途弃坑（只迁一半） | 每迭代独立可交付：已迁面板行为正确、未迁面板维持现状，无中间态缺陷 | 停在任一迭代边界即安全 |

**验收环境矩阵**（迭代 2/5/7 的手动冒烟项）：宽 TTY（`COLUMNS=100`）+ 窄 TTY（`COLUMNS=40`）+ 非 TTY 管道（回退路径）+ pty 子进程方向键时序（既有用例）；Windows 分支由 `test_tui_keys.py` 的 msvcrt mock 用例覆盖，真机验证列发布前人工项（与既有口径一致）。

## 6. 技术债识别与消减（实施中显式偿还，不隐式积累）

| # | 债 | 偿还迭代 | 偿还方式 |
|---|---|---|---|
| 1 | `handlers_config.py` 982 行逼近 C28 红线 | 5a | 抽壳纯移动 commit，回落 <800 |
| 2 | 文件列表表格渲染 3 处重复（持仓选择/What-if 目标/QA 列表同构表头） | 3 | 收敛为 `render_entry_table`（语义名先定），grep 断言全仓单一定义 |
| 3 | 双反馈原语（主循环 `_print_hint` vs 面板各自 print） | 2（随首个面板迁移） | 收编进运行时反馈助手，主循环迭代 7 切换 |
| 4 | `TestTierSemanticParity` 逐面板 parity 用例（语义单源后成冗余） | 8 | 逐面板退役（跟迭代节奏，每迭代只退役已迁面板部分，先建后删）；运行时级 parity 用例取代，`check-test-redundancy` 干净 |
| 5 | `panel_runtime.py` 自身膨胀风险 | 持续 | 自设 ≤800 警戒预算（低于 C28 红线），逼近时拆 NavState/渲染策略子模块 |

## 7. 测试策略

1. **运行时级**（新 `src/test/unit/ui/test_panel_runtime.py`，`unit_ui` marker）：以主循环语义为真值锁 NavState 全契约——键→动作矩阵（§3.6）逐格用例化：导航/回绕/防误触/直达同步/Esc/Ctrl+C 上抛/EOF 上抛/pick 阶段/default_key/两档 parity/零模块级可变状态。这是语义真值的**唯一断言层**。
2. **面板级**：既有测试因 `read=` 注入**patch 点不变**，迁移迭代内零断言修改（只许 import 路径行变更）；各迭代新增「↑↓ 导航 + Enter 派发选中项」正向用例 1~2 例（沿用 `test_handlers_config_nav.py` 模式）。
3. **parity 用例退役纪律**：`TestTierSemanticParity` 逐面板用例的退役**前置条件** = 对应面板已迁入运行时 **且** 运行时级 parity 用例已覆盖同语义（先建后删，每迭代退役本批已迁面板的部分，不一次性删除）。
4. **防回归红线**：迭代 5b（S 面板）不得修改既有断言——行为等价由测试厚度背书；其余迁移迭代同规则。
5. **测试隔离与冗余**：新测试不触持久化文件/不发真实网络（外网 mock 机制天然拦截）；过 `check-test-redundancy`（无死用例/无断言/重复）；条数不断言可增长集合（真值单一来源纪律）。

---

## 8. 文档触点清单（迭代 8 逐项落地）

| 文档 | 改动 |
|---|---|
| `technical.md` | 模块表加 `panel_runtime.py` 行；§1.6 TUI 详细设计补「统一交互运行时」小节；C29 描述从「测试守护」升级为「构造性成立（运行时单源）」；架构目录树同步 |
| `folders.md` | 目录树加 `tui/panel_runtime.py` + `test_panel_runtime.py` |
| `requirements.md` | R-TUI 域补「子菜单列表统一导航」需求行；`testplan.md` §2.1 映射表同步（`check-requirement-trace` 强制双向） |
| `how-to-use-tui-menu.md` | 键位表 ↑↓ 行改为「全部列表面板可用」，删除「仅 S 面板」限定 |
| `changelog.md` | 0.13.7-dev 段记条目（用户反馈驱动的交互统一） |

---

## 9. 非目标

- 不改 Web / CLI 渠道（它们无终端导航问题）；
- 线性提示型输入（y/N、路径、日期、级别、长文本）不加导航；
- 不引入第三方 TUI 框架；
- 不改变任何面板的**派发语义**（编号/字母/默认项含义全部保持）——本次只统一「怎么到达一次派发」，不改「派发什么」。
