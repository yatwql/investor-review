# 自审记录归档 — v0.17.x

> 归档时间：2026-11-04（v0.17.0 发布，本系列首批已修复批次并入）；2026-11-04 v0.17.0 本批原表搬运；2026-11-05 v0.17.1 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.17.x 已修复项（按发布版号批次，v0.17.0 → ）（含 v0.17.1）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 已修复（0.17.0）

> 完整复盘见 `changelog.md` 0.17.0 段；此处为台账原表搬运（无损），本批发布日 2026-11-04。

| # | 问题 | 处置 |
| --- | --- | --- |
| **rf-1036** | 财报源挂起型超时预算偏长（单次 23~25s，7 日 26 次） | `providers/datasink.py` 预算分档：正文档 20s / 章节清单探测 8s，预算经 `_request`/`_get_with_transient_retry` 透传（+3 用例） |
| **rf-1037** | 美股指数行情无会话级复用（同键一轮记 3~4 次未命中并重复请求上游） | `fetcher/index.py` 的 `fetch_indices`/`fetch_us_indices` 增加 `index_quote` 会话缓存包装；陈旧兜底读改 `record_stats=False`，未命中只记一次（+6 用例） |
| **rf-1038** | 流水页签日期为 Excel 原生日期单元格时整行被判无效静默丢弃（`2026-11-04 00:00:00` 过不了 `_DATE_RE`，该笔卖出在 XIRR/成本分档/分红里消失） | `core/reader.py` 新增 `_coerce_flow_date`（`date`/`datetime` → `YYYY-MM-DD`，文本补零 ISO），交易/分红两处解析改用它；`_valid_date` 补日历校验（拒 `2026-13-01`/`2026-02-30`）；+5 用例 |
| **rf-1039** | 基金经理主页失败无负缓存：同一轮穿透/基金经理分析/菜单预热各调一次都重走 HTTP 并各记一次未命中（实测 `fund_manager_017730×4`） | `fetcher/fund_manager.py` 增两级 `NegativeCache`：确定性解析不出 12h（`fund_manager_miss_`）/ 不可达 1h 短退避（`fund_manager_backoff_`），命中即跳过取数且不计缓存未命中；注册表与三份文档表格同步；+4 用例 |

## 已修复（0.17.1）

> 完整复盘见 `changelog.md` 0.17.1 段；此处为台账原表搬运（无损），本批发布日 2026-11-05。

| # | 问题 | 修复 |
|---|------|------|
| **rf-1041** | both 路径把 `config` 当持仓明细传给 `build_purchase_status_data`：开启「基金申购限购」（默认开）且取数成功时，`build_purchase_constraint_block` 迭代 config 得到键名（str）→ `h.get("code")` 抛 `AttributeError`，HTML+Excel 双产物整条中断 | 改传持仓明细最小形态 `[{"name": d.name, "code": d.code} for d in details]`（与 full 路径 `_orchestrator_data.compute_purchase_status_data` 同源同形）；补回归用例锁定「传 list 而非 dict」 |
| **rf-1040** | LLM 四模块缓存 TTL 4h/24h 形同虚设：连续两轮「持仓与市值完全相同」仍 4/4 全 miss（预检归因 `fingerprint_changed`，非 `ttl_expired`）——指纹把行情派生量（总市值/盈亏、指数、竞争语境、量化指标、风险信号、穿透市值占比）与时效数据（事件窗分歧例块、调仓纪律回放块，新闻 15 分钟刷新且含浮点）全数锁进键 | 指纹改为「**只锁结构与口径**」：入键仅持仓成本、分类结构（`extract_stable_categories`，无市值/盈亏）、穿透品种集与行业、版本盐、生成参数、口径类附录块；行情/时效类只进提示词、时效由 TTL 兜底。`global_macro` 另按 `_APPENDIX_EXCLUDED_SECTIONS` 不注入事件窗分歧例块（口径不符 + 省 token），自检/辩论键同步剔除时效块。同步改 requirements（R-HCR-05/R-SR-04/R-EW-06）、technical §3.4 分界说明与七份单测（含新增 `test_market_derived_inputs_do_not_change_fingerprint` / `test_structural_inputs_change_fingerprint`） |
