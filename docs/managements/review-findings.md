# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.4-dev
> **编号源**：`rf-next = 927`（新增问题提出后更新为 +1；已用最大 rf-926，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。当前无登记项。

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。当前无登记项。

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 5 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 999 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 827 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐） |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/llm/skeleton.py` 739 行（主程序登记线 700） | 骨架模板与占位渲染可分（模板数据 vs 渲染逻辑） |

## 已解决问题

### 开发期已修复（0.16.4-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-919** | 页头状态行的「详情」指引指向已不存在的菜单键：写死 `〔详情 [4][H][S]〕`，而主菜单把缓存管理收到 `[3]`、持仓信息目录下沉为 `[G]` 子项，`[4]` 与顶层 `[H]` 均已不存在——按指引按键只会落空 | 指引键收敛为常量 `status_line.DETAIL_HINT_KEYS = ("3", "D", "S")`（缓存统计 / 数据源与运行日志 / 功能开关与 LLM 模块），渲染由 `_detail_hint()` 单源派生；新增守护用例对主菜单键做子集校验（菜单改键即红），并在 DESIGN-TUI 页头状态行契约写明出处。回归 2 例（指引键 ⊆ 主菜单 / 渲染文本逐键出现） |
| **rf-920** | 页头「新鲜度」自首版起恒为「—」：反推缓存键未剥 `_{版本}` 戳（拼出 `_v4_v4`）且 `cache.get` 的 `max_age_seconds` 未传（TypeError 被兜底吞掉） | 反推口径收为 `cache_key_from_file_name` 单源，`get(key, inf)`（要报的就是偏旧数据）；回归 1 例走真实读档（不 patch `get`） |
| **rf-921** | 缓存包启动清理在异常路径崩：`del _logger, _cleaned` 在 `try` 外，`clean_sensitive` 抛异常时 `_cleaned` 未绑定即删；`os.listdir` 无容错 | 初值 0 + `_cache_file_names()` 容错列举（清理尽力而为，不中断主流程） |

| **rf-922** | 用户文档与配图滞后于页头状态行改动：手册无状态行读法、`README` 仍写「缓存过期/备用源/五项」、目录树描述滞后，且「菜单分组」段落组成员写的是已不存在的键（`P/S/M/I/A/D/R`、`V/H/T`） | 手册补「页头状态行读法」+ 分组归属按 `MENU_GROUPS` 纠偏；README/`folders`/`developer-guide`/`test-coverage` 同步；配图重生成 |
| **rf-923** | 截图工具逐段步进按「字号 × 0.62」估算，等宽 CJK 字体实际步进不符 → 配色段起点累积偏移（README 配图状态行彩色段前一大段空白） | 改 `ImageDraw.textlength` 实测推进 + 画布按实测宽度；回归 1 例断言偏移 ≤4px |
| **rf-924** | cninfo orgId 反查单次挂 40.2s：20s 预算在 httpx 分阶段超时下放大成 2 倍，且失败结果不留痕——同一网络条件下每次重跑都重付一遍（实测报告 167.7s vs 上轮 121.1s，数据准备 52.7s vs 6.5s） | 该路径改端到端墙钟 8s（`post_with_deadline` 加表单编码支持）+ 1h 负缓存并区分「连接失败/源侧无该代码档案」；回归 3 例 |
| **rf-925** | 主源财报正文的「确定性空结果」未缓存：5 只 A 股均无「管理层讨论与分析」章节，每份报告逐只重走链路（合计约 10s），属可避免的重复请求 | 按 `(doc_id, section)` 记 1 天负缓存 `report_datasink_doc_miss_`（各槽原因均为确定性拒绝才写：该文档无/异源候选拒服务；任一传输失败不写）；登记进「财报索引」缓存类型；命中按轮计数并打一行 INFO 汇总（无需 DEBUG）；回归 5 例 |
| **rf-926** | 截图脚本的演示报告污染真实运行状态：`make-screenshots.py report` 会向 `data/state/perf_history.jsonl`、`datasource_health.jsonl`、`data/calibration/dedup_anchors.jsonl` 追加演示数据（实测 1 条 perf + 1 条健康），违背脚本自述的「真实 data/ 零接触」 | 跑前快照 `data/state` 与 `data/calibration`、跑后原样还原（含删除运行期新增文件）；已清理本次污染记录；补 2 例回归 |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-26）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.0 ~ v0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
