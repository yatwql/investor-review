# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.15]**（2026-11-01）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.16.16-dev] - 开发中（未发布）

### 变更

- **全仓技术债核查与修复（代码 + 配置）**：按仓内十道守护 + `ruff check`/`ruff format` 全量盘点（全部绿）后，修复六处自查发现的实际欠账：
  - **配置口径不一致**：`pyproject.toml` 的 `[tool.ruff] target-version` 为 `py310`，与 `requires-python = ">=3.11"` 及 CI 矩阵（3.11/3.12/3.13）脱节——改为 `py311`（规则建议重新对齐真实运行环境）。
  - **依赖约束双源头漂移**：`pytest`/`pytest-mock`/`pytest-html` 在 `pyproject` 的 `[test]` extras 是 `>=9.1`/`>=3.15`/`>=4.2`，`requirements.txt` 却停在 `>=8.0`/`>=3.15.1`/`>=4.0`——「启动脚本装环境」与 CI 跑的是两套 pytest 语义；`requirements.txt` 对齐至 extras 同约束（保留 UTF-8 BOM）。补齐缺失的回归契约：`test_dependency_declarations.py` 新增 `test_extras_dependency_specs_match_requirements`（原有契约只覆盖运行时直接依赖，extras 侧无守卫）。
  - **CI 格式扫面与本地基线双口径**：`format` job 只查 `src/python/ scripts/`，而本地基线是整树 `ruff format --check`——`src/test/` 的格式漂移在 CI 上被静默放行（本地红、CI 绿）；纳入 `src/test/`，同步 `developer-guide.md` 门禁说明与「依赖升级流程」契约段落。
  - **格式漂移 3 文件**：`core/provider_registry.py`、`fetcher/industry.py`、`report/fund_style_classify.py` 与声明的「零告警基线」不符，已 `ruff format` 归一。
  - **不可达防御代码**：`web/app.py` 访问日志计算耗时时用 `try/except Exception: pass` 包住 `perf_counter`（该函数不抛异常，`g.get` 自带默认值兜底），删除死分支；同一文件 `app.json.ensure_ascii` 赋值被静态检查判为未知属性（flask 把 `app.json` 标注为基类 `JSONProvider`），改用 `isinstance(..., DefaultJSONProvider)` 缩小类型——行为不变，消掉常驻诊断噪声。
  - **核查结论留档**：无 TODO/FIXME/HACK 残留（生产代码 0 处）、无可变默认参数、无裸 `except:`、无重复长函数体（≥12 行函数体 AST 归一后 0 组重复）、无真死模块（9 个疑似均为包内相对导入/`__main__` 入口的扫描伪信号）、无可删的失效 `noqa`（RUF100 命中 398 处全为未启用规则的有意声明，启用规则集下 0 处）。

- **自审挂账三项清零（决策复盘双路径接线 / 弱证据断言 / 时间炸弹判读）**：
  - **决策跨期反思块在 both 路径补接**：`_generation_both.py` 参照 full 路径接入同一对挂载点——`record_deterministic_decisions`（结算先于登记，入参按挂载点所需键构最小 dict：`today_str` + `holdings_details` 供结算基线）+ `record_llm_decisions_and_review_block`（无 LLM 章节故 `enable_llm=False`，但复盘区块装配与 LLM 无关仍须执行），并把 `decision_review_data` 转发给 `write_html_report`；Excel 端消费 `pipeline_data` 本已就绪，装配后双端同时生效。新增守卫：`test_report_output_spans.py::TestDecisionReviewContractForwarding`（both 路径挂载点顺序 + HTML 转发源码级全覆盖）、`test_orchestrator_generate_report_both.py::TestDecisionReviewWiring`（行为级：入参带日期与持仓基线、复盘区块同时到达 HTML 与 Excel 两个 writer）。
  - **弱证据断言按「用例名承诺了什么」重审**：以 AST 扫描「全部断言均为 `is not None`/`isinstance`/`len == N`/裸真值」的用例 176 例逐条判读——**真需强化 12 文件 30 余处已改**（布尔返回族 `assertTrue/assertFalse(f(x))` → `assertIs(f(x), True/False)` 44 处锁定严格布尔契约；`safe_float(3)`/`finite_or(3)` 补数值断言，原写法放过「类型对值错」；时区断言由「`tzinfo` 非空」改为偏移 `+08:00`；`append_signal` 补回写记录归一键；`token_of` 由 `isinstance` 改为同一实例；`backtest_run_date` 路径断言改精确路径；`check_elements` 补 `missing == []`）。**余下 146 例判读接受**：其形态看似弱实为**精确断言**——负路径 `f(脏值) is None`（返回 None 就是契约本身）、`len(x) == N` 精确计数、内容目录式 `assertTrue(any(
  - **时间炸弹余量全域判读完成（47/47 均为变异伪信号）**：`probe-date-bombs.py --all` 扫出 217 个含绝对日期文件、47 个 rot-suspect，逐一提取失败断言原文（新增 `--detail` 开关：以 `--tb=line` 打印实际/期望两侧原文，判读从「看完整 traceback」降为「看一行」）后归纳为四类伪信号：①**期望被平移、数据在未变异处**（毫秒时间戳 `_MS_2026Q2 = 1782748800000`、cassette JSON 行情快照、模块级 fixture 常量、`2026/7/1` 这类非零填充写法不被 `_STR_DATE` 命中）；②**星期/节假日语义随年份改变**（`datetime(2026, 10, 24)` 是周六、回移三年后变周二，于是「周六 10:00 休市」变「开市」；交易日历/事件窗口/周月分桶/费率周末档同类）；③**生产侧静态历史事实表**（危机区间 2018/2020 固定表 vs 被平移的 bars 窗口，无重叠）；④**时间戳→字符串定值**（`ts_to_str(1782873000) == "2026-07-01 10:30"`）。四类均与「距今远近」无关，墙上时钟走过去不会造成这些用例失败，故结论为**无真实时间炸弹残留**。
  - **探测工具自身的缺陷（连带修复）**：变异筛查跑完还原后，pytest 的断言重写缓存（按 size/mtime 命中）仍指向**变异版字节码**——还原不改变文件大小、mtime 常落在同一分辨率内，于是下一次正常跑测试凭空报出已修好的失败（本次实测污染 3 文件 11 例，清 `__pycache__` 后全绿）。现在子进程一律带 `-B` + `PYTHONDONTWRITEBYTECODE=1`（变异源码不写 `.pyc`），并新增契约用例 `test_probe_file_disables_bytecode_cache` 锁定该不变式；另将进程崩溃丢下的 `core.*`（本次 72MB 转储）纳入 `.gitignore` 并删除存量。

- **R0 结算视界扩展（plan-243）**：决策账本支持 5/20/60 多视界结算——结算事件新增 `target_horizon`（判重键 `(decision_id, 目标视界)`，历史事件无此字段按 5 日归属，旧记录不改写）；`fold_ledger` 新增 `settlements` 全量映射与 `by_horizon` 多视界统计（`settlement`/命中率等口径基准仍为 5 日，既有消费面不变）；报告 seam 随运行推进全部视界；新增 CLI 子命令 `settle-decisions`（结算不依赖报告生成，幂等可重复执行）；doctor 账本概览补多视界已结数。单测覆盖多视界幂等/回补/旧记录兼容。
- **R1 判断依据块骨架（plan-243）**：新增 `report/decision_basis.py`（形态 A 规范空契约，零 LLM、零取数、零参数）；注册功能开关 `decision_basis`（默认开，章节内选项组）与 `pipeline_data["decision_basis_data"]`（附录 H Schema 契约登记）；行动建议章 HTML 嵌入 `#decision-basis` 折叠块（复用折叠组组件）、Excel 页签顶部子块；区块注册表 / §4.22 矩阵（8 区块）/ 语义命名表 / R-OUT-17 同步；骨架期双端空态「数据不可用：<原因>」，R2 起逐节填充（含章标题副行补「判断依据」），`decision_basis.enabled=false` 双端完全隐藏（回滚通道）。
- **R2 信号清单与信号可信度（plan-243）**：`report/decision_basis.py` 接信号账本快照（只读、零取数）——信号清单五类判断类信号（口径/样本/区分度/标注），`basis` 按账本事实判定（估值分位 `detail.pe/pb` 均 null ⇒ 价格代理）；区分度三态如实标注（未回测/样本不足/回测未通过均不进方向轴，`in_direction_axis` 负向用例覆盖）；首批回测结论以模块常量 `BACKTEST_CONCLUSIONS` 登记（估值分位已回测未通过 n=117/ic≈0.04/单调否，因子目录样本不足 n=19，含来源脚本/回测日期/讨论稿 §8.1 指针，不新增配置键）；信号可信度规则仲裁四枚举（`arbitrate_confidence`：no_signal/no_valid_signal/all_proxy/split_direction/insufficient_signals/direction_aligned，首版不产 high）；HTML/Excel 双端渲染信号清单表 + 可信度行（data-status 语义色、数值列 tabular-nums、无效信号标「仅参考」）；空态「暂无信号记录」+「暂不可判」；`enable_llm` 两态输出逐字节一致，CLI/TUI 零引用。

- **投资决策质量讨论稿定稿（plan-242）**：成稿 `docs/archive/v0.16.x/investment-decision-quality/investment-decision-quality.md`（原 `docs/plan/`）——归因结论（建议方向胜率≈随机、组合略弱于基准、纪律建议方向不稳）、7 条结构性事实（无执行回执、结算依赖跑报告频率、3/5 信号零区分度、估值信号丢失口径、纪律规则结构偏空、提示语强制方向且无可信度、无硬性风险约束）、6 项优先级建议与 7 项待验证清单。不实施任何代码/配置/提示语改动。
- **实施任务立项（plan-243）**：`plan.md` 新增 `plan-243` 决策依据章与 LLM 章职责切分（实施），承接 plan-242 讨论稿「章节归属结论」与设计稿 [`investment-decision-basis-design.md`](../plan/investment-decision-basis-design.md) 的 R0~R7 迭代计划；前置为讨论稿 V1/V3 回测；plan-242 保持仅探讨定位，`plan-next` 更新为 244。纯文档变更，无代码/配置/提示语改动。
- **决策质量首批回测（plan-243 前置）**：新增 `scripts/eval-decision-quality.py`（决策视界命中率 / 因子单因子 IC / 估值两口径区分度；判据预注册：视界 5/20/60 交易日、样本门槛 100、|IC| 拒绝线 0.05、三分位单调）+ 单元测试；结论回写讨论稿 §8.1/§8.2——V1/V2 样本不足仅记录不裁决，V3 5 日视界两口径（n=117）均判「叙述性维度」；plan-243 实施前置 V1/V3 完成。
- **迭代设计按首批回测修订（plan-243）**：设计稿 `investment-decision-basis-design.md` 接入回测结论——§2.1 `discrimination` 升为三态契约（未回测 / 样本不足 / 已回测通过·未通过）并更新信号与可信度示例，R0 补 V1 复跑触发与固定/动态视界对拍口径，R2 补回测结论登记机制（模块常量、不新增配置键）与首版渲染态，§5 红线与 §6 风险表同步；`plan.md` plan-243 条目同步（前置改为 V1~V3 同批完成 + 新增「回测接入」行）。
- **plan-243 设计 80 轮复盘**：设计稿新增 §7 复盘记录（33 轮发现 → 18 项整改：confidence 四枚举规则重写〔有效信号定义/short-circuit 仲裁/首版不产 high/unknown→暂不可判〕、配置与文件实名（`rebalance.threshold`、`discipline.*`、`analysis/trade_discipline.py`、`action_section.html`/`action_sheet.py`）、§3 冗余行合并与 `enable_action` 容器联动、R1 Excel 无折叠概念与验收重编号、门禁补十守护/edge/浮点/LLM mock/移动档核验、术语统一「信号可信度」）；plan-243 条目门禁行同步。
- **plan.md 与迭代设计稿去除历史复盘痕迹（plan-243）**：设计稿移除「复盘记录（80 轮）」章节（核对表；18 项整改结论均已固化在正文各节，过程记录不再留存），plan-243 条目同步移除对应指针；其余设计文件的「复盘」字样均为产品功能名（持仓变动复盘 / 行动章复盘块 / 复盘→建议→下期对账闭环），保留；讨论稿 `investment-decision-quality.md` 的逐轮记录属其证据主体（plan-242 验收引用），不在本次梳理范围（其后随 plan-242 归档一并清理，见下条）。
- **plan-242 归档与讨论稿去复盘痕迹**：`plan-242` 整节迁入 [`archived_plan.0.16.x.md`](../archive/v0.16.x/archived_plan.0.16.x.md)，讨论稿迁入 [`docs/archive/v0.16.x/investment-decision-quality/`](../archive/v0.16.x/investment-decision-quality/investment-decision-quality.md)；正文删除逐轮复盘附录与过程叙述（「第 N 轮复盘」标注、「首批／已于某日」类时点表述、优先级表的轮次注记），保留全部结论、证据数字、争议表与待验证清单；回测结论指针同步 `report/decision_basis.py`（`BACKTEST_REF`）、`scripts/eval-decision-quality.py`、设计稿与 `scripts-reference.md`；`folders.md` 目录树与 `plan.md` 在办清单同步（plan-243 直接承接归档讨论稿）。

- **plan-243 设计稿 50 轮复盘整改**：逐轮核对事实与契约后修订 `investment-decision-basis-design.md`——状态行改为迭代实施中（R0/R1/R2 已落地、R3 起待做）；数据契约示例补齐实现字段（`discrimination`/`in_axis`/`*_label`/`enabled`/`title`/`summary`）与单位口径（统一百分数数值，禁用小数比例），区分「`available=false` 故障」与「信号清单为空」两种空态；更正数据通道（`decision_basis_data` 经独立 render 参数传递，不并入 `action_data`）、字段名（`target_horizon`）与路径（`src/python/config/*`、`src/python/analysis/*`）；R8/R9 补语义名（`normalize_discipline_thresholds`/`evaluate_reentry`/`portfolio_constraints`）、配置键与默认值、需求条目 R-DIS-06~09、测试域与 marker、账本 `constrained` 字段兼容口径；补前置未满足时的轮次停留规则、R6/R7 同版本可独立回退口径、§6 四条新增风险、打印态展开与「不新增 CSS（零暗色补丁）」契约。`plan.md` plan-243 门禁行同步。纯文档变更。

- **R3 风险预算块（plan-243）**：`report/decision_basis.py` 新增 `build_risk_budget`——单品种权重 / 行业权重 / 组合回撤三行「上限 vs 现状」，单品种上限取 `rebalance.threshold`（经 `resolve_rebalance_config` 应用 profile 预设）、回撤上限取 `discipline.drawdown_pct`（经 `resolve_discipline_config`），行业上限无配置键即「未配置上限」、回撤缺峰值记「未评估」（不按 0 显示）；超限只标注不改行为，动作仍归「再平衡信号」块（文案互引）；`build_decision_basis_data` 增加确定性入参 `holdings_details`/`total_mv`/`portfolio_peak_mv`（全可缺省、零 LLM），summary 追加超限项数；HTML/Excel 双端渲染风险预算表（状态用既有 `data-status-*` 语义色，不新增 CSS/色值）；full/both 路径在峰值就绪后重装配，basic 路径由 `excel_generator` 就源构建（basic 亦呈现判断依据块）；单测覆盖超限/未配置/未评估/创新高归零/占比并列与双端渲染互引；`technical.md` 语义命名表、`requirements.md` R-OUT-17、TUI 手册说明同步。

- **R4 纪律明细块（plan-243）**：`report/decision_basis.py` 新增 `build_discipline_detail`——只读透传「交易纪律」块已算出的触发条（`action_data["discipline_signals"]`），渲染规则/品种/当前值/距阈值与阶段化执行口径（下跌段对止损/回撤提示「宜确认后执行」，止损与回撤同向时注明避免双重减仓；缺峰值记「未评估」），不重算触发、不写静默状态（触发真值仍在纪律引擎）；`build_decision_basis_data` 新增 `discipline_signals` 入参并接入 summary「纪律触发 N 条（阶段）」；HTML/Excel 双端渲染纪律明细表（与「交易纪律」块文案互引）；编排层/full/both/basic 四处装配均透传纪律触发条；单测覆盖未接入/无触发/字段齐全/阶段判定/双重减仓提示/只读不改原列表与双端渲染；`technical.md` 语义命名表、`requirements.md` R-OUT-17、TUI 手册说明同步。

- **R5 结算摘要块（plan-243）**：`report/decision_basis.py` 新增 `build_settlement_summary`——读 R0 的多视界结算映射（`fold_ledger().decisions[].settlements`，与「历史决策复盘」块同源），按**结算交易日**聚合最近 5 批，每批给 5/20/60 视界的均值收益与均值超额；未到期视界显式「未到期」（`state=pending`、均值恒 null，不按 0 呈现）；着色只给涨跌域变量（`--profit`/`--loss`），与状态域互斥；批次超 5 时指向历史决策复盘块；`build_decision_basis_data` 新增 `settlement_decisions` 入参（缺省读账本）并接入 summary「结算 N 批」；HTML/Excel 双端渲染结算摘要表，判断依据五节齐；单测覆盖空账本/未到期标注/批次上限/收益与超额均值/涨跌域着色/超额缺失回退/双端渲染，并为本模块补决策账本 tmp 隔离；`technical.md` 语义命名表、`requirements.md` R-OUT-17、TUI 手册说明同步。

- **判断依据块双路径 HTML 透传修复（plan-243）**：两条 HTML 生成链都装配了 `decision_basis_data`但都没传给 `write_html_report`——`report/_report_output.py`（full）与 `report/_generation_both.py`（both）均漏传，开关开启时判断依据块在 HTML 端整块不渲染（模板 `{% if _db.get("enabled") %}` 恒假，仅留注释行；Excel 端一直正常）。两处补传并新增回归用例（源码级调用点全覆盖：每条 HTML 调用链必须带该参数，否则新增链忘转发即红）。

- **判断依据块三处实现加固（plan-243）**：① 回测采样日不再写死常量——新增 `decision_basis.backtest_run_date()` 读 `docs/tmp/decision-quality/*.json` 最新产物日期派生，产物缺失才回落 `BACKTEST_DATE_FALLBACK`（归档结论采样日），并在契约新增 `backtest_as_of`、HTML/Excel 双端在信号清单上方显示「回测产物：<日期> 运行」；② 装配补独立 perf 阶段「判断依据块装配」（full/both 双路径），纯内存组装耗时从此可与取数阶段分开定位；③ `decision_basis.py` 781 行过主程序登记线 700，登记进 `review-findings.md` P4 膨胀监控表（拆分方向：信号清单与区分度登记下沉、风险预算/纪律/结算各成一簇）。

- **24 小时变更技术债清理**：① 「回测产物最新日期」此前在 `core/eval_status`（评测提示）与 `report/decision_basis`（判断依据块 `backtest_as_of`）各写一份 glob + mtime 与一份目录常量——口径两处易漂移，现抽出 `eval_status.last_eval_date()` 为唯一实现、`SUMMARY_DIR` 为唯一目录来源，报告侧改为委派调用（新增同源断言用例）；② perf 阶段名 `判断依据块装配` 原在两个生成模块各写一次字面量，收敛为 `decision_basis.PERF_PHASE_ASSEMBLY` 单一常量；③ 清理未使用导入。

- **评测提示命令改用项目虚拟环境解释器**：`core/eval_status.EVAL_COMMAND` 原写裸 `python scripts/eval-decision-quality.py all`，在文档口径下会命中系统解释器（缺 pandas 等依赖）而失败；改为新增 `VENV_PYTHON`（POSIX `.venv/bin/python` / Windows `.venv\Scripts\python.exe`）拼出命令，报告收尾与 `doctor` 的提示行可逐字复制执行，并加断言用例守卫（禁止再出现裸 `python `）。

- **测试用例全量核查（659 文件）**：冗余（`check-test-redundancy` 九类全 0；跨文件同构 5 组经核对均为不同 SUT 的并行覆盖，唯一歧义是同文件两个都叫 `test_empty` 的用例，已按 SUT 改名区分）、无效（AST 解析断言型 helper 后无断言用例 0）、分类（`check-test-markers` 通过，`unit/cache→unit_core` 等 33 处跨域标记属技术设计 §4.23 登记的子集语义）、命名（6 处含 `propagat` 的疑似已核为「置信区间传播/退出码传播/用量传播」，非异常语义）、真实外网（唯一真实网络套件 `src/test/live/` 为 opt-in、默认 skip、不入门禁，其余全走离线桩）、真实 LLM（未 mock 调用 0）——均无违规，仅落地上述命名修正。

- **行业取数会话缓存补齐 + 耗时排行亚秒口径 + README 配图重制**：① 行业取数此前只在**成功**时写会话缓存，取不到的标的（场外基金 005827 等」被上层逐个调用，同一缓存键一轮报告内未命中 16 次并触发「同键未命中」告警；现已让 `fetch_industry_data_cached` 记住失败结论、`batch_fetch_industry_data` 先按会话缓存分流已结案代码（不再进批、不再探文件缓存）、`_push2_extended` 与 `_get_industry_avg_pe` 改走会话缓存变体——同一代码一轮只探一次，告警回归「只报真实重探」；② 模块耗时排行亚秒级此前统一压成 `0.0s`（缓存命中时整表皆 0），改为毫秒口径（`12ms` / `<1ms`），冷热两档差异重新可读；③ 九张 README/手册配图全部按演示工作区重制（两账户 · 6 只公开品种，行情为公开数据，零真实持仓），并修掉 web 工作台配图里泄露的本机绝对路径（`--replace` 归一为 `data/holdings/…`）。

- **交易日历反复探源 + 会话级 single-flight 修复**：① `_get_trading_calendar` 首次装载时多个并发线程各自先读缓存文件（实测同一键一轮记 6 次未命中），现把首次探测也放进取数锁内并二次检查 memo，冷启动只串行一次、其余线程拿锁即命中（`trading_calendar×6` → 0）；② 新增取数失败冷却（`_CAL_FAILURE_COOLDOWN_SECONDS`，默认 300s）：日历与兜底源都不可用时一轮内不再重探，调用方照常回落周度判断；③ `core/data_freshness` 改走 `cached_trading_days()` 统一出口（共享 memo、失败冷却中不读盘），不再各自 `cache.get` 同一键；④ `ProviderRegistry.session_cache_fetch` 提供会话级 single-flight（按 (domain, code) 加锁 + 二次检查 + 失败结论同样缓存），`fetch_industry_data_cached` 改用它，三个报告阶段并行查同一只标的时只探一次（`industry_005827×16` → 3，余 3 次为并行阶段各自首次探测一个确实无数据的标的，非重复取数）。

- **架构约束自查修复（会话级复用 / 双重降级治理 / 单例状态重置）**：① 会话级 single-flight 与失败记忆上线后，`batch_fetch_industry_data` 的批内重试仍走缓存变体 → 首次失败即被记忆，**重试空转**（违反双重降级治理「失败必须真重试」），改为重试专用取数 `_retry_industry_fetch`（绕开会话缓存取数后回写结论），并补「首试失败、重试成功」回归用例；② `fetch_cached_only`（只窥视不取数）的缓存读改 `record_stats=False`，不再计入命中率与「同键未命中」告警（与负缓存探测器同口径），行情核算的窥视不再稀释告警指向；③ `ProviderRegistry.reset()` 补清 `_session_inflight` 在飞锁表（新增持久状态必须可复位，避免跨轮/跨用例残留）；④ 十守护 + 设计护栏 E 级复跑全绿。

- **R6 LLM 章语义增量（plan-243）**：`llm/prompts_action.py` 情景段末尾追加「信息不足以支撑方向判断时明确写『不操作』及所缺数据」（既有强制方向句逐字保留，只加不改；仅在情景段实际出现时追加，条件推理未配置情景与辩论跳过情景均不追加）；`llm/prompts_review.py` 自检清单新增第 4 项「结论是否附条件（失效条件/观察指标）」；`llm/module_fingerprint.py` 把 `PROMPT_SCHEMA_VERSION` 并入自检指纹分段构成（自检清单是静态文案、原内容寻址键不含文本版本，补此缺口后改清单即换键）；本刀不递增版本盐，与 R7 合并为同版本一次重算；单测覆盖三态追加（fallback/条件情景/无情景/辩论跳过）、既有强制句保留、自检第 4 项存在、自检指纹随版本盐变化。

- **R7 提示语替换与解析兜底（plan-243）**：`llm/prompts_action.py` 情景段方向约束改为「条件化动作 + 触发条件，触发条件不满足即写明『不操作』及所缺数据」（默认口径），并保留强制方向口径作为回退常量（`decision_basis` 关闭即回退，回退口径以 `_ms` 缓存后缀换键，两套文本共存一版）；「每个建议必须引用具体品种」开口子（允许「不对具体品种动手 + 理由」）；`llm/rate_caliber.py` 的 `PROMPT_SCHEMA_VERSION` 递增为 `rate-caliber-2`——**本版首轮 LLM 缓存整批重算**（四主模块 + 辩论三段 + 自检；`news_item` 与 `holding_change` 不受影响），R6 的增量与本刀同时生效；`report/decision_llm_capture.py` 解析兜底：缺行/缺方向（含「不操作」行）跳过登记并按原因记 INFO，解析异常不中断报告生成；`requirements.md` 新增 R-LLM-ER-09 并修 R-LLM-ER-05、`testplan.md`/`technical.md` 语义命名表同步；单测覆盖两套口径切换、回退后缀、品种开口子、解析兜底三类跳过与异常兜底。真机采样（基线/新提示词各 5 次、同输入 A/B 各 10 次）挂账待人工执行。

- **V5 止损口径回测（plan-243 R8 前置）**：`scripts/eval-decision-quality.py` 新增 `discipline` 阶段——对比固定止损线（−15%）与波动率归一化止损线（−2.5σ，σ 为报告日前 60 个交易日日收益率总体标准差），触发窗口取报告日后 5 日累计跌幅，效果窗口取第 6~20 日收益；判据预注册（样本 ≥100/组、两组效果均值差 ≥1 个百分点）并固化在脚本常量；纯原语与判定可单测（波幅窗口不足不猜、无前视偏差、样本门槛、三态判定）。实跑读数：决策总数 90，20 日视界成熟样本 2 条、两条口径触发均为 0 → **样本不足，仅记录不裁决**，R8 阈值口径维持默认、前置仍未满足。`scripts-reference.md` 阶段清单同步。

- **R9 集中度/相关性约束标注（plan-243）**：新增 `analysis/portfolio_constraints.py`（判定单品种/行业/相关性三道上限：单品种沿用 `rebalance.threshold` 不另设键、行业与相关性需 `constraints` 段显式配置、相关性样本窗口不足门槛记「未评估」）；新增开关 `portfolio_constraints`（默认关）与 `constraints` 配置段（`industry_max_pct`/`correlation_max`/`correlation_min_window_days`，默认 `null`/`null`/250）；`report/decision_basis.py` 在开关开启时多出 `constraints` 键并在判断依据块渲染「集中度约束」小节（关闭时输出逐字节不变），summary 追加约束标注项数；`core/decision_ledger.append_decision` 新增 `constrained` 参数、`decision_llm_capture` 按 `breached_codes` 标注（只标超限、缺省不写字段），挂载点透传；`requirements.md` 新增 R-DIS-06/07、`testplan.md`/`technical.md` 语义命名表/`how-to-config*.md` 同步；单测覆盖开关门控、单品种 profile 阈值、行业两态、相关性窗口门槛、账本标注与双端渲染，并把 `lessons_cache_suffix` 摘要算法统一为 SHA-256。

- **V7 相关性↔回撤回测（plan-243 R9 前置）**：`scripts/eval-decision-quality.py` 新增 `correlation` 阶段——按滚动窗口（60 日、步长 20 日）计算窗口内平均两两相关系数（复用 `analysis.correlation` 原语，缺口按窗口 60% 取样本门槛）与等权组合最大回撤，对二者做 Spearman IC 与三分位单调性检验；判据预注册（样本期 ≥250 交易日、窗口 ≥100、|IC| ≥0.05、方向须为正）并固化常量；实跑读数：品种 14 个、样本期 146 交易日、窗口 5 个、IC −0.3591（方向与预注册相反且样本不足）→ **样本期不足，仅记录不裁决**，R9 相关性项维持「未评估」。`scripts-reference.md` 阶段清单同步。

- **回测入口提示与 opt-in 随报告执行**：新增 `core/eval_status.py`——按 `docs/tmp/decision-quality/*.json` 最新 mtime 派生「距上次回测 N 天」（无产物给首次运行提示），`doctor`「日志与缓存」组与 CLI 报告收尾同源显示；CLI `report --post-eval` 时在报告成功后以子进程跑零取数阶段（`horizon`/`valuation`，只读账本与缓存），超时/失败只打印提示、不改变退出码，产物仍落 `docs/tmp/`；`requirements.md` R-OUT-18、`testplan.md` 载体、CLI 手册与语义命名表同步；单测覆盖天数派生、提示两态、脚本缺失/超时/成功末几行、CLI 开关解析与 doctor 行。

- **回测脚本拆分（消除文件膨胀豁免）**：`scripts/eval-decision-quality.py` 1016 行超出脚本红线，按 `_eval_factor_zoo` 同形态拆出 `scripts/_eval_decision_quality/`（`primitives` 预注册常量+账本读取+纯原语、`stages` 五阶段、`report` 产物与控制台摘要），入口仅留路径、原面 re-export 与 CLI；`check-file-length` 的临时豁免与 review-findings rf-1024 挂账同步撤销（`rf-next` 回退 1024）；`folders.md` 目录树与 `scripts-reference.md` 同步。顺带消除重复实现：`report/decision_basis.py` 的权重/状态助手改为复用 `analysis/portfolio_constraints.py`（单一实现），报告输出不变。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.15（2026-10-25 ~ 2026-11-01）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
