# 自审记录归档 — v0.16.x

> 归档时间：2026-10-25（v0.16.0 发布，本系列首批开发期已修复批次并入）；2026-10-25 v0.16.1 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.16.x 开发期已修复项（v0.16.0 → ）（含 v0.16.1）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 开发期已修复（0.16.1-dev）

> 完整复盘见 `changelog.md` 0.16.1-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-25。

| # | 问题 | 修复 |
|---|------|------|
| **rf-882** | `cache/_cleanup._fmt_span` docstring 混入西里尔字母（应为「两」），全文扫描仅此一处非中文外文字符 | 改为「两」，并反向核对希腊字母使用均为公式符号（Σ/σ/Π）属合法 |
| **rf-883** | `config/_config_freshness._keys_of` 解析失败返回空集 → 自检把「文件语法坏」报成「缺全部 40 个新键」，误导修复方向 | 返回 `None` 表示不可比较；`_diff` 增加 `parse_error` 字段；自检单独报「无法解析」并给编码/语法提示；回归 2 例 |
| **rf-884** | 同模块 `check_config_freshness` 只捕 `OSError`，非 UTF-8 配置文件解码失败时冒泡成「对比失败」 | 同时捕 `UnicodeDecodeError`（跳过，由配置加载检查负责报错）；回归 1 例 |
| **rf-885** | 同模块 `import json` 写在函数体内（风格与分层不一致） | 提到模块顶部 |
| **rf-886** | 审计误判：把 `core/costs.add_cost_bucket` 判为「死代码」（只 grep 了 `src/`，漏掉 `scripts/_perf_history` 两处调用），删除后 dev-verify 才暴露 | 已恢复并补 docstring 调用方说明（core / llm / scripts 三方共用）；教训：死代码判定必须扫全仓（含 `scripts/`），且以门禁实跑兜底 |
| **rf-887** | 重算原因（forced/fingerprint_changed/ttl_expired/cache_miss）以字符串字面量散落在预检与骨架两条路径，新增的 `RECOMPUTE_REASONS` 取值域无人使用 | 两处改引用 `observation.RECOMPUTE_*` 常量；`note_recompute_reason` 对域外值告警一次（仍计数，避免静默多出无人认识的统计桶）；回归 3 例 |
| **rf-888** | `_llm_providers_defaults._PROVIDER_NOTES` 与默认线路未配对时静默无注释（新增线路漏写说明不会被发现） | 补对齐回归 2 例：每条默认线路必须有非空说明 + 模板可被注释剥离器解析且订阅制线路保留 `pacing` |
| **rf-889** | 360h 核查：`scripts/_eval_halluc_sampler/llm_call.py` 与 `holdings.py` 有三处逐字重复（`_compute_categories` / `_compute_portfolio_values` / `_load_datasets`），其中一份引用已搬走的 `fact_checker._calc_portfolio_values`，被调即 ImportError | 删除 llm_call 内副本（本模块未使用），唯一实现留在 holdings；模块 docstring 记明原因 |
| **rf-890** | 360h 核查：三家行情源（sina / sina_kline / tencent）各持一份逐字相同的 `_add_prefix`，改一处长度判据或前缀表会让另两处静默取错代码 | 收敛为 `providers/utils.with_exchange_prefix`（规则本体仍在 `core/code_symbols`），三处改为别名；语法断言纯函数行为不变 |
| **rf-891** | 360h 核查：`scripts/_eval_factor_zoo/metrics.py` 内联副本了 `_closes` / `_daily_returns` / `_rolling_beta`（离线评测不依赖 src 私有名，属有意为之），但无任何机制阻止两份公式漂移 | 加同源数值测试：同一段 bars/指数在两侧逐步对比（NaN 位与浮点均带容差）——公式一改即红，而非静默出不同因子值 |
| **rf-892** | 360h 核查：生产代码 6 处 `assert` 承担类型收窄与入参校验职责（LLM 三客户端 `client is not None`、报告两处 checkpoint 类型断言），`python -O` 下会被剥离——真出错时炸点推到更晚且信息更差 | LLM 三处改显式 `if client is None: raise ValueError`；报告 checkpoint 改告警不中断（与同函数内其他校验口径一致）；现全仓生产代码 `assert` 清零 |
