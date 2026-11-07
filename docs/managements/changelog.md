# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.3]**（2026-11-06）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.4-dev] - 开发中（未发布）

### 修复

- **新闻关联批量解析失败不再冒充成功**（rf-1055）：响应整体不可解析时解析器返回 `None`，批量骨架按「本批
  失败」收口——不写结果、不写逐条缓存（占位入缓存会被后续轮次当命中复用）、计入 `failed_batches` 并触发
  「部分批次失败」告警，已消耗 token 照常计费；LLM 部分作答仍按正常产出处理（缺失项填默认值）。此前 3 批中
  2 批不可解析时，20/30 条占位被算成「含 LLM 分析」，并连带事件窗极性缺失（91% 事件不可判）。
- **批量用量行显示真实 token**（rf-1056）：归一化协议改按 usage 形状判定，不再把 provider 条目名
  （如 `deepseek-main`）当协议名传进 `_log_token_usage`，消除「输入 0 + 输出 0 = 0 tokens」的假账。
- **逐模块费用改用数值口径**（rf-1057）：不再回读 `estimate_cost` 的展示串（≥0.01 只到 3 位小数），
  消除 0.0646→0.0650 的精度丢失与「逐模块合计 ≠ 页签总计」。
- **HTML 生成阶段拆出子步骤耗时**（rf-1058）：模板渲染 / JS 资产内嵌 / 匿名化 / 落盘四步分别记入阶段细分
  （保留「页面写入」总值供跨版本比对），慢写告警只针对「落盘」段，慢的时候能直接定位到底是渲染、内嵌、
  匿名化还是磁盘 IO（同尺寸产物实测 0.02s / 6.15s / 21.0s 三档）。
- **慢段告警按段分流**（rf-1058）：`warn_slow_write` 支持自定义事件名与排查提示，渲染慢报「HTML 模板渲染 渲染
  偏慢 → 排查模板内逐行循环/过滤器」，落盘慢才报「排查磁盘/挂载与 fsync」；full/both 两条路径均接线。
  实测 0.98MB 产物**落盘仅 0.003s**，此前 6.15s 的「页面写入」实为模板渲染——告警方向原先指错了磁盘。
- **Jinja 模板字节码缓存**（rf-1059）：HTML 生成阶段的耗时实为**模板编译**（18 个模板 0.65s ≈ 97%，渲染仅 ~0.02s、落盘 0.003s），接入字节码缓存到 `<缓存根>/jinja/` 后**冷 0.654s → 热 0.027s（≈24×）**；键含模板源码校验和（改模板自动失效），缓存目录按需解析以尊重测试隔离与 `INVEST_CACHE_DIR`；旧键按 `BYTECODE_CACHE_TTL_DAYS=14` 在写入时回收（改模板换键后不再只增不减）。
- **Excel 产物清扫遇合并单元格整份报告生成失败**（rf-1061）：`mask_workbook_text` 遍历 `ws.iter_rows()` 时未跳过
  `MergedCell`，而被合并吞掉的从属单元格 `value` 只读——清扫命中一处带笔名的合并行即抛 `AttributeError`。
  `full_anonymous` 模式下只要页签里有一条合并单元格（汇总警示行、指数标题行都是），整份 Excel 报告就写不出来。
  现按单元格类型跳过从属单元格（笔名文本存于锚点单元格，锚点仍在遍历集内，不漏清扫），并补「合并区域不抛异常
  + 锚点被改写 + 非合并行照常改写」的回归用例。

### 清理

- **文档与架构约束同步**（rf-1060）：`technical.md` 把 `data/cache/jinja/` 字节码缓存登记为「缓存统一管理」架构约束的
  唯一例外（二进制非 KV、自管保留期）；`requirements` R-PERF-09 / `technical` / `scripts-reference` 的阶段细分名单补齐
  HTML 生成四步；`developer-guide` 补写盘告警按段分流的判读口径；`data-and-backup` 补 `data/cache/jinja` 删除影响。
- **48h 变更技术债清理**（rf-1060）：删 `_first_provider_name` 死函数、`_render_template(self_review_block=...)`
  被架空的死形参、`write_html_report(force_llm=...)` 无调用方的死参数；HTML 阶段收口（总值记录 + 慢段告警）
  抽成 `html_writer.close_html_generation_stage` 由 full/both 共用——此前 both 路径完全没有慢段告警。
- **七组同构副本收口为单一本体**（rf-1062，覆盖 8 个文件、+342/−274）：这些成对的函数原先逐字重复，改一侧
  另一侧不会跟着变，正是口径漂移的温床。各组现共用一个参数化本体，对外签名与输出**逐字不变**：
  - `core/atomic_write.py` —— 文本/二进制写入共享 `_write_atomic`（临时文件→`os.replace`→Windows 占用回退），
    文本仍走 `os.fdopen(fd, "w")` 以保留换行翻译语义（若改成直接写字节，Windows 产物会从 CRLF 变 LF）；
  - `report/excel_writer.py` —— 小计/总计行共享 `_write_summary_row`，差异只剩底色（黄/绿）；
  - `tui/text_layout.py` —— 终端列/行探测共享 `_terminal_dimension`（实时 ioctl → `COLUMNS`/`LINES` → 下限兜底）；
  - `config/_json_patch.py` —— dict/array 值区块共享 `_replace_value_block`，括号字符参数化（`{}`/`[]`）；
  - `report/_report_helpers.py` —— 组合演进/快照差异注入共享 `_inject_optional_section`，构建函数经惰性导入
    包装传入（不做运行时动态 import），失败降级口径仍是「`available=False` + 不阻断报告」；
  - `providers/sina.py` —— A 股/美股指数拉取共享 `_fetch_sina_indices`，仅解析器、日志称谓与
    「格式异常行是否告警」不同（美股链路保留该告警，A 股原先就没有，不借重构改行为）；
  - `report/summary.py` / `fetcher/index.py` —— 指数渲染共享 `_write_index_group`（当日标题
    「本日」/「最新」参数化，保持两个市场的原有文案）、指数取数共享 `_fetch_with_session_cache`。

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.3（2026-11-04 ~ 2026-11-06）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
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
