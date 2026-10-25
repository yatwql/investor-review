# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.6]**（2026-10-25）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.7-dev] - 开发中（未发布）

- **架构约束整改（重试/节流原语、Provider Chain 边界、代码判定中心化）**：① LLM 全链失败重试改走 `core.retry.retry_transient`（不再分支内 `time.sleep` 自建重试）；② 新增 `core.throttle.wait_interval` 作为「429/限速窗口一次性等待」唯一原语，cninfo/datasink 的 `interval_delay + sleep` 改经该原语；③ 行业资金流向失败状态访问器下沉 `fetcher/akshare.py`，report/cache 层不再直连 `providers`；④ A 股指数交易所判定收敛为 `code_symbols.index_exchange_of`，同花顺 provider 内自建的 399/932 判定删除。

- **删除旧结构与旧接口的兼容层**（不保留向后兼容）：① `get_ttl` 去掉历史 `key` 参数（30 处调用点同步）；② 删除历史序列的「载荷语义版本戳」闸门（`_payload_ver` / `write_stale_with_version` / `payload_version_current`）；③ **缓存键版本 `v3`→`v4`**，整体作废旧缓存，替代逐载荷 `rank_schema`/`hold_schema`/`purchase_schema`/`fee_schema` 字段与 `rank_payload_is_current` 判据（排名/持仓归一化不再盖版本字段）；申购/费率的读侧**形状**准准入（防截断载荷）保留；④ 功能开关注册表旧名别名 `GROUP_ANALYSIS` 统一为 `GROUP_FUND_STYLE`；⑤ 删除 `fetcher/batch` 对旧 registry 对象的 duck-typing 守卫；⑥ 清理 `code_symbols`/`datasink` 注释中「`code_utils` 仍转出派生符号」的过期兼容声明。

- **新闻去重比较成本下降**（rf-872）：比较串与字符多重集按标题缓存，并先用字符多重集上界跳过不可能命中的标题对（不再为每个远低门槛的对构造两个 `SequenceMatcher`）；判定结果不变，基准语料约 1.17×。

- **行业资金流向降级收敛**（rf-871）：失败后 5 分钟内不再重试（akshare 内部本已重试 2 次），后续报告直接按「不可用」降级并只留一条告警；备用源评估结论为「免 key 场景无可靠第二源」，故保留显式不可用、不引入过期缓存。

- **事实校验口径**（plan-185）：口径标签与提示词版本号已生效，最近多轮 `fact_fix_total` 稳定为 1（目标 ≤3），收益率指标口径错挂问题收敛。

- **报告内容可复现**：历史走势的并发取数改为「并发抓、按输入持仓顺序汇总」。此前按 `as_completed` 完成顺序追加，导致同数据两次报告的「已纳入走势计算」清单顺序抖动、逐日市值浮点累加顺序漂移（极端时影响四舍五入后的展示值）。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.6（2026-10-24 ~ 2026-10-25）
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
