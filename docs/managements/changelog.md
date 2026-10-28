# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.7]**（2026-10-28）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.8-dev] - 开发中（未发布）

### 修复
- **行业资金流向换通道**（plan-234 / rf-955）：主通道东财 `push2` 在本机出口被配额型限流（TLS 层 `RemoteDisconnected`，实测连续 20 次 0 成功、仅罕见短窗口放行），新增**同花顺行业资金流备用通道**（金额亿元→元、净占比由净额/成交额派生），两通道共用同一结构契约与 `sector_flow_failure()` 语义；负缓存改**按通道分别落盘**（主通道限流不得锚死备用）；新增只读探针 `scripts/probe.py sector-flow`（逐通道成功率与判读）。
- **「无回退基准」与「陈旧回退」分开披露**（plan-235）：取数层新增降级三态（正常 / `stale` / `no_baseline`），源不可达且本机无历史载荷时，报告文案与 LLM 数据质量块单独成行标注「无回退基准、区块留空」，不再与「陈旧回退（用上次成功数据）」共用同一句话。
- **缓存清理器吞掉同前缀异构 TTL 键**（plan-237 / rf-955）：清理器按文件名前缀取 TTL，`sector_flow_last_good`（设计 3 天）与 `sector_flow_negative`（设计 30 分钟）被 900s 前缀默认值一并裁掉——3 天陈旧回退基准实际从存活不下来，回退链路形同虚设。注册表新增 `exact_key_ttls` 单源声明 + `get_exact_ttl_map()`，清理器按精确键覆盖；取数侧 TTL 从同一处读，不再两处各写一份。
- **`scripts/probe.py` 子探针 import 失败静默**（rf-956）：入口只把 `scripts/` 加进 `sys.path`，子探针的 `from src.python…` 在直接运行入口时全部 ImportError 并被当作探测失败——`csi` 因此长期输出「无可用代码」。入口补仓库根路径，子探针契约面加 Protocol 类型。
- **去重锚点体积治理三项**（rf-938 / rf-939 / rf-940）：
  - **同源样本 1/50 确定性采样**：`same_src` 样本按标题对 SHA-256 哈希采样（同一对恒定入选），存量 94,706 → 37,913 条（40%），校准样本量仍远超「≥50 条」建议值。
  - **保留期 120 → 30 天**，且保留判定改为 `ts`（发布时间）**或** `written_at`（写入时刻）任一在窗口内即保留——补录/回溯抓到的老新闻 `ts` 很老但刚写入，不再在首次压缩就被裁掉。
  - **体积目标 24 MB**（与 32 MB 告警线分离）：超目标按最旧裁剪到 ≤24 MB，每分支保留最新 50 条（小分支不被整类裁光）；读取前后比对 `(size, mtime)`，期间被并发追加则放弃本次压缩；无行可裁时不重写文件。
- **锚点规则时代口径**（rf-941）：压缩时给无规则指纹的早期行补 `legacy` 标注，校准报告分「当前指纹 / 历史指纹 / 未标注」三桶并列出历史指纹 Top3。
- **文档同步**（rf-942）：developer-guide / technical / requirements R-DATA-09 / scripts-reference / testplan 按三重压缩条件重写，自检提示指向评估脚本并说明会裁到体积目标内。
- **新闻去重锚点按层拆分**（rf-948）：`providers/news_dedup.py` 795 行三簇混装收口——字节动作（分片命名/路径/汇总体积/容错读取/追加/校验后原子替换）下沉 `news_dedup_anchor_store.py`，保留期·体积目标·同源采样·裁剪编排下沉 `news_dedup_anchor_policy.py`，`news_dedup.py` 保留判定主流程并原面 re-export（`compact_anchor_file` 仍是唯一裁剪实现，生产维护与 `eval-dedup-threshold.py` 共用）。
- **负缓存探针收口为单一样板**（rf-949）：新增 `cache/_negative.py::NegativeCache`——四类确定性缺失（标的正文 / 章节清单 / 该文档无该章节 / provider 404 探测）只声明「标签 + 键前缀 + TTL 类型」，锁/命中计数/汇总文案（`nonzero_summaries()`）统一承接；新增一类负缓存不再复制 lock+counter+reset 样板。
- **事实校验自动修正回写缓存**（rf-946）：修正后正文写回该模块缓存（键沿用预检/写侧同源的 `cache_info[mk]["key"]`，不改指纹、不新开键），缓存正文与展示正文口径对齐——此前同一缓存内容每轮都要重做同一批修正（`counters.fact_fix:*` 恒为同一数），且报告展示值与缓存值不一致。校验摘要属当轮元信息，仍在回写之后拼接、不入缓存。
- **章节清单不可得负缓存**（rf-947）：源侧 200 但无可用章节清单时，`/documents/{id}/sections` 每份报告都重探一次（实测 5 篇 × 0.3~1.4s ≈ 5s，全缓存运行的绝对瓶颈）；现按确定性结论记负缓存（`report_sections_miss_`，6h，传输级失败仍不缓存）：覆盖空清单与「非空但不可用」（源侧只解析出封面/目录几项、按清单取正文全空）两种形态，后者先失效清单再重记负缓存；清单失效时正负两键同清。计时同时拆为「财报摘要」「财务指标」两段，`breakdown` 可直接区分逐篇网络探测与单次取数；批量取数评估为不可行（两源均按单标的请求）。
- **生成后自检缓存键去噪**（rf-945）：自检输入剔除 LLM 用量页脚与事实校验摘要段落（后者检查项计数随缓存态变化），报告渲染保持完整正文不变；补未命中时的分段诊断日志。实测强制重算上游模块后，下一次运行自检即命中（此前该场景必多一次 10~15s 调用）。

- **去重锚点按月 gzip 分片**（rf-943）：写入改为 `data/calibration/dedup_anchors-YYYYMM.jsonl.gz`（multi-member gzip 追加，不重写既有压缩块），读取侧 `gzip.open` 透明解压、坏分片只跳过其余内容；压缩按记录月份重新分片并清理整月被裁空的分片，旧版未压缩单文件首次压缩时自动并入并删除。实测存量迁移：34.0 MB / 94,706 行 → 2.7 MB / 62,716 行（2 个分片，0 行解析失败）。

### 性能
- **新浪分类抓取加超时与整源预算**（plan-236）：单请求由 15s 整段超时改为连接 3s / 读取 6s 分档，整源加 20s 预算并按剩余收紧每请求超时；超预算保留已取条目后收尾，单类挂起不再把新闻阶段从 5s 拖到 15s+。
- **历史 K 线挂起不再放大等待**（rf-951）：腾讯 K 线单次超时预算 60s→10s、同源重试 3→2 次且**挂起型不重试**（单次 ≥ 预算一半即判主机不可达）；链级新增 `_HANG_ELAPSED_SECONDS=20s` 判据，挂起不再触发同源重试。实测主机不可达时单标的从 ≈2 分钟（60s+36s+31s）收敛到 10s 内，十余持仓的报告不再被卡二十分钟。
- **章节清单探测加短退避**（rf-952）：`/sections` 传输级失败（挂起/断连）此前不留任何状态，每份报告都为同一篇文档再白等一次超时预算（实测单篇 20.7s）；现记 30min 短退避（`report_sections_backoff`，注册表类型同源），探测成功即清。与「确定性缺失 6h 负缓存」语义分离：一个说源侧没有清单，一个只说这次探测挂起。
- **持仓变动复盘归因并入并行批**（rf-944 ②）：该模块只吃持仓变动契约、不依赖四模块产出，原先串行后置把单次 4–25s 完整叠加在 `expert_review` 之后的关键路径上；现经 `_MODULE_FNS["holding_change"]` 由工作线程调度并复用共享 HTTP 客户端，失败/契约缺席照旧降级为「无归因」。`self_review` 因输入是四模块产出，仍串行后置。
- **逐模块耗时写入 perf**（rf-944）：`perf_history.llm.modules[*]` 新增 `duration_seconds`（缓存命中记 0），作为「关键路径卡在哪个模块」的机器可读证据。
- **实测收益**（4 次完整报告，2026-10-28 19:45~19:49，闲时）：串行尾残差 0.02 / 0.01 / 0.04s（判定阈值 5s）；`expert_review` p50 61.5s（阈值 83.6s）；归因 5.7–6.5s 完全落在并行批内；`LLM+新闻` 88.3 / 74.1 / 61.6s（缓存全命中运行 12.5s、归因 0.0s）。

### 变更
- **LLM 换键归因跨进程可见**（rf-954）：新增 `llm/fingerprint_baseline.py`——编排收尾把「各模块本轮缓存键 + 指纹组件哈希」落盘 `data/state/llm_fingerprint_snapshot.json`，下次预检读取作基线；归因主信号改为「键是否变化」（键变 ⇒ `fingerprint_changed` 并打出变化组件；键未变而读不到内容才是 `ttl_expired`；无基线 ⇒ `cache_miss`）。此前基线只在进程内存，重启后换键只能记成 `ttl_expired`（实测 expert_review 键 `bb5e0593dabe…` → `d86f4195c09f…` 被误归因），且「哪一段输入变了」无据可查。
- **`perf-history` 跨版本键名归一**（rf-950）：`breakdown` 的历史合并段「财报摘要与指标」在读取侧别名为 `财报摘要+财务指标（旧·合并段）` 单列，**不与拆分后的新子项混算**（合并段一次计时覆盖两子项，与逐子项均值量级不等价）；scripts-reference 的阶段细分表标注版本分界。
- 测试隔离补正：锚点路径隔离打在实际持有者 `news_dedup_anchor_store._ANCHOR_PATH` 上（此前打在门面 `news_dedup` 上只换同名变量，测试仍会追写真实 `data/calibration/`）；批内缓冲与「已告警」标记改由 `news_dedup_anchor_policy` 的单例复位，不再改门面副本。
- 压缩实现收口为 `news_dedup.compact_anchor_file` 单一份（生产维护与 `eval-dedup-threshold.py` 共用），工具侧只打印结果，不再自带第二份裁剪逻辑。
- 自检「去重锚点」改按分片汇总体积与行数（`2.6 MB / 62716 行 / 2 个分片`），提示语指向评估脚本的默认压缩。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.7（2026-10-25 ~ 2026-10-28）
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
