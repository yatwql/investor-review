# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.18.6-dev
> **编号源**：`rf-next = 1181`（新增问题提出后更新为 +1；已用最大 rf-1180，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线（主程序 700 / 脚本 600 / 测试 900）即登记。下表为存量监控项（红线：主程序 1000 / 测试 1200，触线必须拆分）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/conftest.py` 1199 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 与装配 |
| `src/python/core/perf.py` 799 行 | 采集器与台账落盘可拆（`perf` 采集 / `perf_history` 读写两文件） |
| `src/python/core/doctor.py` 785 行 | 检查项按域分文件（环境 / 配置 / 数据源 / 报告产物），入口只留编排 |
| `src/python/llm/fact_checker/_numerical.py` 764 行 | 数值校验按规则族拆（金额 / 比率 / 计数），共享解析原语上提包内 `_common` |
| `src/python/tui/handlers_config.py` 743 行 | 配置面板按域拆（内容选项 / 全局设置 / 目录与文件名） |
| `scripts/_doc_drift/_format.py` 742 行 | 格式化规则按文档类型拆（章节 / 表格 / 树 / 统计） |
| `src/python/core/degradation.py` 768 行 | 状态词与事件模型、登记面与持久化可拆两文件 |
| `src/python/report/action_sheet.py` 753 行 | 行动页签内各块（建议表 / 判断依据 / 决策书 / 复盘）拆子模块 |
| `src/python/fetcher/financial_report.py` 719 行 | 按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/python/providers/akshare_extras.py` 718 行 | 按接口族拆（指数 / 行业 / 分红 / 盈利预测） |
| `src/python/core/provider_registry.py` 710 行 | 熔断与会话缓存各自独立文件 |
| `src/python/llm/skeleton.py` 877 行 | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染） |
| `src/python/cli/_handlers.py` 890 行 | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄 |
| `src/python/tui/handlers_holdings.py` 825 行 | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于风险，暂不拆 |
| `src/static/tmpl/report_template.html` 277 行 | 样式已抽到 `partials/_report_styles.html`，各自单一关注点，均未触 1000 行 |
| `src/static/tmpl/whatif_template.html` 543 行 | **不在行数守护域内**（`check-file-length` 只扫 `.py`）；样式已抽到 `partials/_whatif_styles.html` |

## 已解决问题

### 开发期已修复（0.18.6-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| **rf-1178** | `release.py archive` 对同一版本不幂等、且只搬节内**首个**表格块：主台账表格被空行/散文切块后，每轮 `archive` 只搬首块并在归档追加一个 `## 已修复（X.Y.Z）`，余行既滞留主台账、又因 `count_rf_rows` 只看首块被门禁误判「已搬空」；实测 v0.18.5 发布时归档长出两个同名批次节，被 `check-doc-traces`（重复标题）拦下 | ① `apply_rf_archive` 改为节内**逐块全搬**（`_table_blocks` 枚举全部 `|` 块，首块连表头、后续块只取数据行），表外散文按原序留主台账；② `count_rf_rows` 改按节内全量清点（门禁据实测判定）；③ 新增 `_merge_rf_into_archive`：归档已有本版批次节时按 rf 编号去重升序**并入同一节**（同版只留一个批次节）；④ 配 2 条回归用例（多块一次搬全并留散文 / 既有批次节并入且二次运行零改动） |

| **rf-1179** | GitHub CI 三条 job 红：① akshare 1.20.65（CI 依赖解析落点）**就地重命名了四个导出接口**且不留别名（`tool_trade_date_hist_sina`→`calendar_trade_date_hist_sina`、`stock_fund_flow_industry`→`stock_fund_flow_industry_ths`、`news_cctv`→`alternative_news_cctv`、`stock_sector_fund_flow_rank`→`stock_fund_flow_sector_rank_em`），依赖声明是区间 `>=1.16,<2.0` → 新装机器上交易日历/行业资金流/央视新闻三条链路 `AttributeError` 被降级吞掉、数据静默缺失，本机 1.20.42 因旧名仍在而全程未暴露；② `test_v8_call_sites` 的「已知 V8 接口」断言写死旧名，在 CI 假红；③ `ruff format --check` 有 14 个文件早已漂移（CI `format` job 长期红） | ① 新增 `core/akshare_compat.py`（逻辑名→候选链，`resolve()` 取第一个存在的接口；旧名与改名后名字并存时优先走旧名，行为不变），`core/v8_subprocess.py` 子进程按候选链解析、`providers/akshare_news.py`/`providers/akshare_extras.py` 改走 `resolve()`；② 该断言改为按候选链整条判定，另加「合成模块」确定性用例（判定不依赖 akshare 当前实现）；③ 新增 `test_akshare_compat.py`（10 例：候选链/旧名优先/改名回落/不可调用跳过/调用点不得硬引旧名）；④ 14 个漂移文件 `ruff format` 归位，全仓 `format --check` 恢复零告警 |

| **rf-1180** | 全仓核查「旧结构兼容」残留（旧数据结构/旧数据文件/旧缓存结构/旧缓存文件/旧配置/旧配置项/旧内部 API）：运行期仍有三处为旧形态留分支——① `fetcher/index.py` 的 `history_index` 会话缓存对裸列表（旧条目形态）按「窗口未知」放行；② `providers/akshare_extras.py` 的通道失败负缓存把整源单字符串当作「全通道同源失败」；③ `report/_snapshot.capture_snapshot` 的 `**extra` 是无调用方的扩展透传口。其余「兼容」注释均为第三方变体容错（§9.2 形状容错归属）或单据版本拒载护栏，不属跳版本兼容 | ① 会话缓存只认 `(days, bars)` 二元组，其它形态一律当未命中重新取数（写回形态固定）；② 负缓存只认 `{通道: 失败类型}`，非 dict 载荷按空处理；③ 删 `**extra` 与 `pipeline_data.update(extra)`；④ 配 4 条回归用例（裸列表当未命中并回写二元组 / 窗口不足重取 / 窗口足够复用 / 单字符串负缓存按空） |

### 归档档案
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-18）
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-10）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-13 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-13）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-15 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
