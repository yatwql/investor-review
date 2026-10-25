# 自审记录归档 — v0.15.x

> 归档时间：2026-10-24（v0.15.0 发布，本系列首批开发期已修复批次并入）；2026-10-24 v0.15.0 本批原表搬运；2026-10-24 v0.15.1 本批原表搬运；2026-10-25 v0.15.5 本批原表搬运；2026-10-25 v0.15.7 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.15.x 开发期已修复项（v0.15.0 → ）（含 v0.15.7）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 开发期已修复（0.15.0-dev）

> 完整复盘见 `changelog.md` 0.15.0-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-24。

| # | 问题 | 修复 |
|---|------|------|
| **rf-841** | changelog 指针行跨小版本时指向旧档：`apply_changelog_release` 只重写反引号里的归档文件名，`(../archive/v0.15.x/...)` 的目标路径仍旧——文件存在故死链检查不报，人点进去看的是上一系列归档 | 指针行同时改写链接文本与目标路径（目录按新归档文件名派生）；补回归用例 `test_pointer_line_target_path_follows_minor` |
| **rf-840** | 发布工具链契约不一致：`archive-init` 写出的 changelog 归档索引行是占位形态 `— v0.15.x（date ~ date）`，`prepare` 的改写正则只接受 `vX.Y.Z` → 新小版本首次发布在 prepare 阶段硬失败 | 索引正则接受占位形态并按「首版」语义归一为 `v{release}（date）`；真实仓库契约测试对「刚 init 未发布」的空骨架放宽为「有则同形」；补回归用例 `test_archive_init_placeholder_line_is_accepted` |
| **rf-838** | `test_json_comments` 的叶子模块边界用例用 `subprocess.run(text=True)` 未指定编码——`PYTHONWARNDEFAULTENCODING=1` 下直接告警为错误（`error::EncodingWarning`），`LC_ALL=C` 等非 UTF-8 locale 还会按 cp936/latin-1 解码子进程输出 | 显式 `encoding="utf-8"` + `errors="replace"`；由 portability 隐式编码严格档拦截，无需新增用例 |
| **rf-836** | 事实校验自动修正器产出用户可见畸形数值（`持仓收益率+-9.0%`）：把占比当收益率改写、同句多代码主体归属错、替换不处理原符号 | 三条同修：① 数值前文语义（占比/最大持仓/份额/市值/仓位等局部窗口）→ 不参与收益率修正；② 主体归属改为括号 > 分句 > 全句三级作用域；③ 替换时剥除原符号（新值符号优先，正值且原文有 `+` 时延续）并按 `[+-]{2,}` 做畸形自检，命中整批不写回。回归用例 6 例（`TestNonReturnMetricAndSignNormalization`） |
| **rf-837** | 计价模块懒加载标志与显式重载不一致：显式 `reload_pricing()` 后 `_PRICING_LOADED` 仍为 False，进程内首次计费会再读一次配置文件并覆盖已装载的定价（用例单独执行失败、整文件通过） | `reload_pricing()` 在 `finally` 置 `_PRICING_LOADED = True`；新增回归用例 `test_explicit_reload_is_not_undone_by_lazy_init`（断言显式重载后计费直接使用已装载的定价） |
| **rf-842** | TUI 动线驱动器漏覆盖一类处理器：`_cmd_diagnose_menu` 等函数内 `from tui_keys import input_choice` 局部导入，模块属性 patch 无效；非 TTY 下 `input_choice` 退化为内置 `input()` → 动线跑不动（读真实 stdin）或静默错位。日志动线（`filter_logs_by_level`）场景用例因此长期失效，只在 P2 regression 档暴露 | 驱动器 `_patch_readers` 增补 `builtins.input` 兜底（不 patch 源头，避免跨用例永久绑定）；该动线按键序列按菜单分层更新为 `[D]→[V]→级别→按键→[0]→[X]`（6 键），契约快照同步并说明「加长来自菜单分层而非新增确认屏」 |

## 开发期已修复（0.15.1-dev）

> 完整复盘见 `changelog.md` 0.15.1-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-24。

| # | 问题 | 修复 |
|---|------|------|
| **rf-862** | 发布 prepare 的 changelog 指针行目标路径缺 `v` 前缀：跨小版本发布写出 `../archive/0.15.x/`（应为 `../archive/v0.15.x/`），死链检查在校验阶段拦下，prepare 中途失败；原回归用例只断言整篇文本含正确路径（索引行也含），未隔离指针行，故未拦住 | 指针目录由归档文件名派生并补 `v`；回归用例改为**只取「最近发布」指针行**断言目标路径，并显式排除缺 `v` 形态 |
| **rf-861** | 近 18h 变更的技术债：① `llm_report_unavailable_reason` 与 `is_enable_llm` 两套章节开通判据（可能漂移）；② 锚点「自动压缩」命名/日志/`doctor` 提示与「报告只追加、维护时压缩」新口径不符；③ `_runtime_overrides` 两个只读 API 无消费方；④ 维护体积提示每次 flush 都打印；⑤ `eval` 默认维护压缩失败会推翻已完成的评估输出；⑥ 测试 docstring 仍写「跨轮不重复追加/写失败回滚 key」 | ① 统一复用 `is_enable_llm`；② 改名 `_compact_anchor_file`/维护压缩，同步 doctor、testplan、requirements、folders、scripts-reference 与设计图样；③ 删除死 API；④ 每进程只提示一次（conftest 重置）；⑤ 维护失败只打印提示、保留评估结论；⑥ 改写测试与 eval 文档串 |
| **rf-860** | `report --type full` 在 LLM 全关/未配置时静默等同 `both`：只在 Excel 页脚留「LLM 用量页签无落点」，日志与结束摘要无显式提示 | `core/system_info.llm_report_unavailable_reason()` 统一判定未配置/章节全关；`full` 生成开始时 `reporter.warn` 明确「按不含 LLM 内容生成（full 等同 both）」，三渠道同一提示；补充文案与测试 |
| **rf-859** | `perf_history.breakdown` 仅记录 `LLM+新闻 → 新闻获取`，`数据准备 14.4s` 无子阶段、去重/锚点维护不可见 | `数据准备` 补九项子计时（行情与明细/指数获取/穿透/风格与因子/覆盖与新鲜度/估值与温度/财报摘要与指标/申购与成本位置/明细装配与建议）；`LLM+新闻` 补新闻源抓取/去重与关联/锚点维护/事件窗装配；子项全部沿用既有 `PhaseBreakdownRecorder`，不新增面板 |
| **rf-858** | 去重锚点每轮全量加载/压缩（39 MB，约 18.5s，占管线 42%），而锚点只服务阈值校准 | **采集保持默认开启**（诊断数据不断档；`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关）；写侧改为纯追加：不读旧文件、批内去重，跨轮重复由 `eval-dedup-threshold.py::load_anchors` 按键去重（保留最早一条），诊断结论不受影响；39MB 文件的加载/压缩移出报告路径（压缩只由 `--compact` 或 `INVEST_DEDUP_MAINTENANCE=1` 显式触发），文件超 32MB 仅记体积提示 |
| **rf-857** | 技术设计文档的配置编辑白名单计数陈旧：写「8 组 51 条键 / 功能开关 27」，实际为 9 组 56 条键 / 功能开关 26；`target` / `writer` 枚举漏 `llm_providers` / `logging`，也未记录 `scheduler.*` 走独立写入原语 | 按 `config_edit_whitelist` 实测刷新（9 组 56 条、26 开关、补 logging 与 scheduler 说明）；三处「Web/TUI 唯一/两渠道」表述改为 TUI/Web/CLI |
| **rf-856** | CLI 帮助/手册把 LLM 多链调序指向「TUI 菜单 [M]」，而 [M] 现为「配置入口地图」，实际入口在 `[G]` → `[L]` LLM 设置；CLI 手册 §10.1 又笼统写「配置类菜单暂无 CLI 等价」，与 `--output` / `--feature` 的既有覆盖不符 | 帮助与手册改指 `[G]` → `[L]`；§10.1 改为「一次性 / 持久化」两档覆盖说明，并同步新增的 `--chapter` / `--anonymize` / `config set` 入口 |
| **rf-855** | 启动向导「幂等」用例与「标记后非首次」用例只差一次重复调用，断言完全相同；交易日历用例留着未使用的 `trading_days` 集合并在末尾 `del`，指数链路用例的 `call_count` 计数从未被读取 | 两条启动向导用例合并为一条（重复标记 + 状态不变）；两处死变量删除 |
| **rf-854** | 一批「弱断言」：名称为映射/阈值/警告/命中语义，实际只断言 `is not None`（行业映射、分位最小样本、汇率/夏普警告、参数校验、cassette 命中、凭据缺失、指数全失败） | 按契约补足：映射锁定具体指数代码、分位恰达阈值断言 100、警告断言文案要点、参数校验断言键名与原因、cassette 断言响应体、凭据断言返回声明字段、指数全失败断言空字典 |
| **rf-853** | 配置原子写崩溃用例在收尾阶段 `try/except OSError: pass`——崩溃未抛出时用例照样通过，临时文件清理断言失去前提 | 改为 `with self.assertRaises(OSError)` 明确崩溃契约，再比对 `.tmp` 文件数 |
| **rf-852** | 文件系统边缘 4 例接受双结果（占用文件接受任意异常、超长路径 `except OSError: pass`、空字节 xlsx 允许列表或异常）——两种结局都算过，等于没有契约 | 按 `reader` 实现钉死：PermissionError/OSError 原样抛出、超长路径（mock 后）返回空列表、尾部空字节 xlsx 正常解析出 1 条持仓 |
| **rf-851** | 安全基线 3 例为**自证式**：缓存用例自造 JSON 再扫自己、日志用例自定义脱敏函数再断言它脱敏、HTML 用例用本地正则断言本地样本——均不触生产代码，恒过 | 改为触生产：缓存条目由 `cache.set` 写出后再扫、LLM 源码静态守卫（日志语句不得含 `api_key`）、HTML 模板产物扫绝对路径；对应文档同步 |
| **rf-850** | 「当前迭代」概述行重算与归档完成标记口径不一致：归档只认 ✅/❌/「已完成」，而重算只排除 ✅/❌——台账里写「已完成，待发布归档」的节会被归档搬走，搬走前却仍算进「在办」项数（概述行与实际在办数对不上） | `recompute_current_iteration` 排除集并入「已完成」，与 `plan_completed_sections` 单源；回归 1 例（「已完成」节与 ✅ 同口径） |
| **rf-849** | `[C]` 面板无效编号提示写死「可输入 1-16 或子项 7.1 / 7.2」：章节与子项是注册表派生量，新增一章后提示立刻过期，把用户引到不存在的编号 | 新增 `invalid_number_hint()` 从 `chapter_numbers()` / `sub_item_numbers()` 现取范围；回归 2 例（范围随注册表、注册表缩短时提示同步缩短） |
| **rf-848** | TUI 动线驱动器的打点可能静默失效：处理器函数内 `from tui_keys import input_choice` 绕过模块属性 patch，用例表面在跑、实际读真实 stdin（rf-842 的根因只在 P2 regression 暴露） | `run_flow` 前置「打点矩阵自证」——逐项校验 `builtins.input` 与各消费方 `input_choice` / `get_key` 都指向 feeder，任一未命中即报错；日志动线改标 `scenario_basic` 让 P0 也覆盖；回归 2 例 |
| **rf-847** | 发布台账失败记录只有 `ok=false`：复盘时无法回答「折在哪一步、哪些用例红、报告在哪」，只能去 `test-reports/archives/` 按 mtime 反查（目录名与结束时间对不上） | 失败命令写 `failure`：失败步 / 退出码 / 报告目录 / 失败用例名 / 输出尾部（首次失败保留第一现场）；回归 2 例 |
| **rf-846** | 发布 bench 的 `--fail-fast` 在多档并行时形同虚设：`unit` 等长尾档与场景档同批启动，场景失败仍要等完整 unit 跑完（实测一次白等约 45s） | 发布子集按「快而决定性 → 长尾」排序（regression → integration → unit → dev-verify）；回归 1 例锁顺序 |
| **rf-845** | prepare 的文档手术会在写入前因 changelog 派生失败中止，但该失败发生在 archive-init 与台账操作之后，排查要回退已动文件 | `check` 增加 changelog 派生预演（`apply_changelog_release` 只算不写），派生失败在动文件前中止并给出修复方向 |
| **rf-844** | publish 台账只记「统计快照同步」一步（1.32s），实际提交/合并/tag/推送均未入账；且 gate 后代码有改动时只说「实跑 verify」，读者不知道改了什么、是否白跑 | 提交/合并/tag/推送分段计时入账；gate 戳增存逐文件代码哈希，publish 指纹不一致时点名 gate 后改动的代码文件并说明 verify 为何重跑；回归 2 例 |
| **rf-843** | Web 配置面板的块标题回退成内部块 id：`renderBoolBlock` 用 `labels[blockKey]` 取标题，而 labels 只登记可编辑键；`sections` / `llm` 等块在面板上直接显示英文 id（中文块标题只有 `features.*` 组与少数写死项）。同批发现 `renderTuningGroup` 签名与块标题取源不一致（引用未定义 `surface`）导致整面板渲染失败 | 块标题改为**服务端随面下发**（`block_titles`，单一来源），前端一律取服务端下发的标题（不回退到 id、不写死中文）；`renderTuningGroup` / `renderAnonGroup` 改为接收 `surface`；契约测试补「每块都有中文标题且标题≠块 id」 |
| **rf-839** | `_evaluate_percent_value` 参数蔓延（单函数 22 个参数：7 基础值 + 10 语境开关 + 5 数据映射），新增一种语境要同步改签名/文档/调用点与全部直接用例，语境判定顺序只体现在函数体里 | 收进冻结 dataclass `PercentContext`（22 字段，字段即语义），函数签名单参 `_evaluate_percent(ctx)`；调用点构造上下文，语境优先级仍在函数体内单源维持；`src/test/unit/llm` 1326 例全绿（行为零变化） |

## 开发期已修复（0.15.5-dev）

> 完整复盘见 `changelog.md` 0.15.5-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-25。

| # | 问题 | 结论 |
|---|------|------|
| **rf-873** | 手机远端跑完报告提示「是否打开」(y/N)，按 `y` 后得到「打开失败」并返回主菜单（`DISPLAY` 为 tmux/screen/Catlink 等继承的会话环境变量时被当成有桌面） | 已修：`local_open_supported()` 在 Linux 上额外要求 X socket 真实存在且 `xdg-open` 可执行，并把 Catlink/Xpra 类桥接会话归为无图形会话；`xdg-open` 子进程 stdout/stderr 丢弃（转发器报错不写回终端，不打乱 TUI 版面）；打开失败一次后本会话直接打印路径与 Web/scp 指引；补 6 例回归 |

## 开发期已修复（0.15.7-dev）

> 完整复盘见 `changelog.md` 0.15.7-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-25。

| # | 问题 | 结论 |
|---|------|------|
| **rf-871** | 行业资金流向无备用源/缓存 | 失败负缓存 5 分钟 + 单条聚合告警；备用源评估＝免 key 无可靠第二源，保留显式不可用 |
| **rf-872** | 新闻去重耗时占比高 | 比较串/多重集缓存 + 上界预筛（判定等价），新闻 TTL 不变 |
