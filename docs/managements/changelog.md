# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.3]**（2026-10-26）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.4-dev] - 开发中（未发布）

### 变更

- **README/手册配图按当前界面重生成**（自造演示持仓，不涉真实数据）：TUI 主菜单（新状态行：数据源失败 0 / 动作提示）、Web 生成页与配置页、HTML 报告首屏 / 盈亏汇总 / 穿透图表 / CLI 生成输出共 6 张（新增 `cli` 子命令：伪终端采集，含进度、耗时排行与产物路径；CLI 手册新增该图），另重生成 GitHub 社交预览图；文件名保持不变，README 与手册链接无需改动（已逐条校验可达）

- **新增离线评测脚本 `eval-llm-budget.py`**（`plan-229` 阶段 1）：冻结持仓样本 × 4 档预算 × 4 种模式，测量墙钟/输出 tokens/分段字数/要素机检/操作建议行数，输出判定与报告到 `docs/tmp/llm-budget/`；`freeze` 离线建样本、`run --dry-run` 零费用自检；实现拆在 `scripts/_eval_llm_budget/` 包（预算文案/提示词替换/样本/度量/编排/报告/CLI），22 例单测

- **`plan-229` LLM 关键路径时延治理（表达预算）：评估后不采纳并归档**（未改生产代码）：离线评测 12 只持仓样本，4000 字档 p50 64.5s→45.0s（−30%）、输出 tokens −41%，但正文篇幅减半且纯提示词约束下 **8/8 次丢失「操作建议」表**（补写接缝可 9/9 补齐，+2~6.5s）；同期评估的 TTL 提升（理论 51%→63%、实际命中恒为 8%）与指纹瘦身（可至 36%，但最多陈旧 3.7h 且违反指纹契约）均不采纳。设计与量化数据归档至 `docs/archive/v0.16.x/llm-expression-budget/`；评测器 `scripts/eval-llm-budget.py` 保留为度量资产。立项时记录（背景）：：`expert_review` 40 个生成样本均值 65.3s / p50 64.5s / p90 85.5s，恒为报告关键路径，而时延与输出 token 数线性相关（156~163 tok/s）、提示词全篇无篇幅上界（对照 `global_macro` 有「500字内」）。设计文档 [`llm-critical-path-design.md`](../archive/v0.16.x/llm-expression-budget/llm-critical-path-design.md) 给出归因模型、四方案取舍（选定「分节表达预算」，拒绝并行拆分与模块合并，thinking 默认不动）、四阶段实施计划、质量守门与回滚口径；**本文档阶段不实施**

- **用户文档与配图同步状态行新形态**（rf-922）：`how-to-use-tui-menu.md` 新增「页头状态行读法」（四项常驻 + `缓存过期 N` 仅 >0 出现 + 第二行动作提示；`数据源失败` 明确标注「与 LLM 多链无关」），并纠正「菜单分组」段落的组成员（原写 `P/S/M/I/A/D/R`、`V/H/T` 等已不存在的归属，改为与 `MENU_GROUPS` 一致）；`README.md` 界面描述、`folders.md` 目录树描述、`developer-guide.md` 菜单触点行（「页脚指引」→ `ACTION_TEMPLATES` 动作短语）、`test-coverage.md` TUI 域用例清单同步；`requirements.md` 补 `R-TUI-10`（页头状态行此前无需求行，只有零散提及）+ `testplan.md` 追溯行；README/手册配图 `src/static/tui-menu.png` 按当前界面重生成

- **页头不再常驻「缓存过期 0」**：启动已自动清理过期缓存，常态的 0 反而引人追问「是不是没清理」——该段改为**仅 N>0 时上屏**（取数失败同样静默，改由 `[3]` 缓存管理查看），出现即意味着本轮运行期间确实积了过期文件
- **页头状态行：静态「详情」括注 → 异常态动作提示**：`〔详情 [3][D][S]〕` 是 5 个指标配 3 个键的目录式指路（用户需自行猜「哪个键对应哪一项」），且它自己承认最不重要（窄终端第一时间丢弃）；改为状态驱动——异常段自带一句带键的动作短语（`[3] 清理过期缓存` / `[2] 更新行情缓存` / `[D]→V 看数据源记录` / `[G]→L 配置 LLM`），汇总为第二行 `└ …` 缩进提示并按列宽折行；全部正常时行尾干净、无第二行。短语单源 `status_line.ACTION_TEMPLATES`，首键受主菜单子集守护（`TestActionHintKeys`），DESIGN-TUI 页头状态行契约同步重写；「备用源」段改名「数据源失败」（它数的是取数源失败个数，紧挨 `LLM ●` 时被误读成 LLM 备用线路数）

### 修复

- **截图脚本的演示报告会污染真实运行状态**（rf-926）：`make-screenshots.py report` 跑真实生成流程，会向 `data/state/perf_history.jsonl`、`datasource_health.jsonl` 与 `data/calibration/dedup_anchors.jsonl` 追加演示数据，与「真实 data/ 零接触」承诺不符（实测污染了 1 条 perf 记录与 1 条健康记录，已清理）。改为跑前快照、跑后原样还原两个目录（含删除运行期新增文件），并补 2 例回归

- **主源正文的确定性空结果不再每轮重复请求**（rf-925）：实测 5 只 A 股在 DataSinking 侧均无「管理层讨论与分析」章节，每份报告逐只重走链路约 10s，而结论是确定性的。改为按 `(doc_id, 章节)` 记 **1 天负缓存** `report_datasink_doc_miss_`（判定依据：各槽原因均为确定性拒绝——「该文档无」或「异源候选拒服务」；任一槽为传输级失败则不写），登记进「财报索引」缓存类型随 TTL 清理；命中次数按轮计数，报告级打**一行 INFO 汇总**（「正文空结果命中负缓存 N 次」），无需 DEBUG 即可确认生效。回归 5 例（命中 / 传输失败不缓存 / 章节隔离 / 计数与重置 / 汇总日志）

- **cninfo orgId 反查挂 40.2s 拖慢报告**（rf-924）：该路径原用 20s 预算，而 httpx 的 timeout 按阶段计、read 又度量「相邻两次收数据间隔」，实测单请求挂到 **40.2s** 才判主机不可达——orgId 只是财报备源的元数据前置，卡在报告主路径上。改为**端到端墙钟 8s**（`post_with_deadline` 支持表单编码后复用）+ 失败入 **1h 负缓存** `report_cninfo_orgid_miss_`（区分「连接失败」与「源侧无该代码档案」；此前失败不留痕，同一网络条件下每次重跑都重付一遍）。实测影响：该轮报告 167.7s → 预计回到 ~130s 量级。回归 3 例（墙钟生效 / 负缓存命中不再发请求 / 两种失败原因分开记）

- **截图配图的配色段前留大段空白**（rf-923）：`scripts/_screenshots/tui_frame.py` 逐段绘制时用「字号 × 0.62」估算步进，而等宽 CJK 字体里拉丁与全角的实际步进与估算不一致，偏差随段落长度累积（页头状态行长行最明显）；改为 `ImageDraw.textlength` 按字体实测推进、画布宽同口径取实测宽度。回归 1 例断言彩色末段起点与实测偏移 ≤4px

- **页头状态行「详情」指引对齐主菜单**（rf-919）：指引键写死为 `[4][H][S]`，而缓存管理已收为 `[3]`、持仓信息目录下沉为 `[G]` 子项，`[4]` 与顶层 `[H]` 均已不存在；改由 `DETAIL_HINT_KEYS = ("3", "D", "S")` 单源派生，并加「指引键 ⊆ 主菜单」守护（菜单改键即红），DESIGN-TUI 页头状态行契约同步写明出处
- **页头「新鲜度」自首版起恒为「—」**（rf-920）：两处叠加——① 从缓存文件名反推键时未剥 `_{版本}` 戳，`get()` 拼出 `{key}_v4_v4.json` 必然未命中；② `cache.get` 的 `max_age_seconds` 未传，TypeError 被兜底 `except` 吞掉只剩「—」。反推口径收为 `cache.cache_key_from_file_name` 单源（清理侧同步改用它），读档改传 `inf`（要报的就是「数据偏旧」）；回归 1 例不 patch `get` 走真实读档
- **缓存包启动清理在异常路径抛 NameError**（rf-921）：`del _logger, _cleaned` 在 `try` 外，`clean_sensitive` 抛异常时 `_cleaned` 未绑定即删，导入期崩；另一处 `os.listdir` 无容错，目录不可读同样中断。改为初值 0 + `_cache_file_names()` 容错列举（清理是尽力而为，不得影响主流程）

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.3（2026-10-25 ~ 2026-10-26）
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
