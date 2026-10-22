# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.5]**（2026-10-22）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.6-dev] - 开发中（未发布）

### Added

- **CLI `health-history` 子命令（plan-181）**：查看最近 N 次数据源健康记录（`--limit` 默认 10、`--json`），聚合单源 `core.perf.summarize_health_history`（与 TUI `[H]` / Web `/api/health/history` 同字段）；无需 config（配置损坏也能查），无记录为友好空态、读取失败退出码 2。至此 CLI/Web/TUI 的健康历史信息面一致。
- **CLI 收尾打印产物路径（plan-183）**：报告生成后输出「产物目录 + 各产物绝对路径」（定位下沉 `core/artifacts`，与 TUI 同一事实；不做交互，脚本不被阻塞）。
- **Web 产物路径可复制（plan-183）**：结果区每个产物旁显示服务端绝对路径，点击即复制（浏览器与报告不同机，「打开目录」无意义）。
- **LLM 调优参数面板（plan-184）**：`config/edit_ops.LLM_TUNING_SPECS` 声明 6 个可调键（thinking 并发 / 模块并发 / 重试 / 整链重试等待 / 总时间预算 / 日费用上限）及范围与说明；Web 配置面板新增「LLM 调优参数」组、TUI 新增 `[D]→[L]` 子项，保存走同一编辑层（超范围明确拒绝）；此前只能手改 JSON。
- **报告收尾列出产物并支持一键打开**：E/B/L 生成完成后打印报告目录与已生成的 HTML / Excel，问一句「是否打开报告目录与报告？(y/N)」——`y`/`Y` 打开，**默认 N**（其余任何键含 `n`/回车/`Esc`/未知键均按 N），`Esc` 只跳过回菜单、`Ctrl+C` 沿用 TUI 约定退出，非 TTY 只列清单不询问。打开动作平台分派（`startfile`/`open`/`xdg-open`），失败不报错、降级为手动路径提示。取代原「按任意键返回菜单」：同样是按一下回菜单，但键义明确、不多一步（`R-TUI-09`）。

### Fixed

- **近 12h 实施变更技术债核查（rf-831）**：清掉两处重复实现与一处渠道层重复模板——评测工具 `_eval_factor_zoo/metrics.py` 的 `_pearson`/`_ema` 改为直接导入生产 `analysis._factor_formulas`（不再本地留副本遮蔽「同源」导入）；`core/holding_status` 的 `_detail_value`/`_has_effective_quote` 改为复用 `core.data_freshness` 单一实现；`TuiProgressReporter` / `WebProgressReporter` 的 `call_sheet` 上提为 `AnnouncingProgressReporter` 唯一实现（补结构断言两渠道同一函数对象）。另修两处台账/文档漂移：README「HTML 10 图」→ 12 图（与模板实测一致）；恢复被误删的已完成 `plan-181` 节并清掉其孤儿正文。复核：全仓重复函数体 0 组、`check-style-guardrails` E 级与 `check-test-markers` / `check-script-contract` 无新增 finding。
- **TUI 报告追问首字为孤立代理项→整条 provider 链误判失败（rf-830）**（实机复现：按 `Q` 提问返回「服务暂不可用」）：POSIX 下 `sys.stdin` 的 `errors=surrogateescape` 会把终端传入的非法 UTF-8 字节解成 U+D800~U+DFFF，问题首字恰好命中时，httpx 以 `ensure_ascii=False` 序列化请求体在 `.encode("utf-8")` 抛 `UnicodeEncodeError`，又被 `_attempt_api_call` 的 `ValueError` 分支归为「响应解析失败/api_error」——所有 provider 同败，与实际网络/配额无关。新增 `core.text_safety` 统一口径（合法代理对折叠为星平面字符、孤立项→U+FFFD），并在 LLM 请求体（`call_llm_with_retry` 入口递归净化）、LLM 响应正文（`_process_success_response`）与追问问题入口（`qa.session`）三处过关；回归用例锁「带孤立代理项的请求体能正常发出」「响应正文能落 HTML」「问题/历史存净化后文本」。
- **CLI 产物清单不再在失败时误导**：仅在非严重失败（有产物可交付）时打印；`core.artifacts.collect_artifacts` 增加显式 `output_dir` 入参，CLI 不再靠「复制 config 字典改键」传覆盖值（`--output` 语义直连）。
- **异常提示的 JSON 判定改类型判断**：`core.error_hints` 不再用异常类名字符串匹配 JSON 解析错误（类名一改即静默失效），改用 `isinstance(exc, json.JSONDecodeError)`。
- **`gate → publish` 的 verify 复用按构造永不命中**（v0.14.5 发版实测，等于每次白跑约 27s）：`code_fingerprint` 原用 `git diff HEAD` + `git status` 哈希，而 publish 会先提交 prepare 的改动再算指纹——HEAD 一变，同一份代码就得到两个指纹。改为 `CODE_PATHS`（`src` / `scripts` / `pyproject.toml` / `pytest.ini` / `requirements.txt`）下 **tracked + 未忽略未跟踪文件的内容 sha256**，提交前后一致；回归用例锁「提交前后同指纹 / 内容变化变指纹」。
- **单测改写仓库真实发布戳**（v0.14.5 发版期间发现 `logs/release-gate-stamp.json` 被写成夹具版本 `0.13.12`）：`TestGateArchivePrecondition` 沙箱漏隔离 `GATE_STAMP_FILE`，gate 成功用例走完尾部写入真实路径；现该测试模块统一 autouse 重定向「通过戳 / bench 戳 / 耗时台账」，并加回归断言「跑完 gate 成功用例后仓库真实戳字节不变」。
- **`prepare` 归档后「当前迭代」概述行失准**：归档搬走 ✅ 节后该行仍写「在办 15 项…已实施待归档」（doc-drift 不校验这句，每版都要人工改）。`apply_plan_archive` 现按**现存 `#### plan-N` 节**重算在办项数与 P1~P4 分档编号，残留/幻影编号（如已不存在的 `plan-128`）一并纠正；无分层标题时保守不动。
- **渠道层常量/回退链/展示规则单源化（rf-823~828）**：
  - `config.resolve_output_dir(config, override)` 取代 12 处各自为政的 `output_dir` 回退链（含 3 处 `"reports"` 字面量），统一绝对化；
  - `core.num_utils.format_size` 取代 TUI 三处 + CLI 一处的 KB/MB 格式化（此前取整位数已不一致）；
  - `core.error_hints.hint_for` 成为「异常→用户提示」唯一映射：TUI 上屏、CLI 未处理异常行取同一句话（Web 可并入信封），类型判定优先于关键词、内部异常标 `log_detail` 记堆栈；
  - `config.read_llm_settings_file` 成为「原始落盘值」唯一读取入口（TUI 配置面板 / Web 配置面板共用），不再各自 open+strip+parse；
  - doctor 网络检查预算收敛到 `core.doctor`（`NETWORK_TIMEOUT_DEFAULT`/`NETWORK_TIMEOUT_WEB`/`CEILING` + `normalize_network_timeout`），CLI/TUI 用默认档、Web 用 Web 档，渠道不再写数字；CLI 查询串超上限按 15s 截断；
  - TUI 页头「新鲜度」改用 `core.data_freshness.header_freshness`：阈值取 `degradation` 分层最严档（默认 3 天）、偏旧判定取交易日口径（日历只读缓存、不触网），与报告内数据质量同一结论（此前 TUI 自定 `_STALE_DAYS=7` 且用自然日）。

### Changed

- **收益率口径标签 + 提示词文本版本进指纹（plan-185）**：进提示词的数据表统一带口径标签（`持仓收益率（自买入，未年化）` / `组合持仓收益率（成本口径，未年化）` / `区间收益率（窗口内，未年化）`）并附一次口径说明，覆盖持仓行 / TOP3 / 数据槽 / 竞争语境 / 智囊团 / 体检 / 穿透 / 全球政经；新增 `llm/rate_caliber` 单一声明点，`PROMPT_SCHEMA_VERSION` 并入模块指纹，静态文案改动也能让旧口径缓存失效。不改正数与取数链路。
- **`release.py` 逼近红线拆分（rf-829）**：argparse 装配下沉 `scripts/_release/_cli.py`——`build_parser()`（全部子命令与选项）与 `run_cli()`（解析/分派/计时/错误码），`RELEASE_BENCH_MODES` 随之下沉并由入口 re-export；`release.py` 992 → **906 行**（红线 1000，余量 8 → 94）。CLI 面与测试引用面不变（`release.build_parser` / `cmd_*` 仍在入口），`_release` 包说明与目录树同步。
- **文件膨胀处置登记（rf-829）**：`scripts/release.py` 与其余逼近红线文件在 `review-findings` 登记拆分方案与处置方向；release.py 优先项已完成（见上），其余文件继续按登记表逐个处置。
- **测试文件分片**：`test_news_sources.py` 1054 行 → 拆分出 `test_news_dedup.py`（标题判定算法/锚点写入去重/追加写与保留期），两文件均回落到红线以下；同步 folders 目录树。
- **LLM 调优项默认值单源**：`LLM_TUNING_SPECS` 不再各写一份默认值，改为构造时从 `_DEFAULT_LLM_SETTINGS` 取（新增 `config.get_llm_setting_default`）——避免改出厂默认时两处漂移。
- **plan-182 决策不做**：CLI 的「一次命令 + 管道」形态不适合多轮追问，保留 TUI `[Q]` / Web `/api/qa/ask` 两个自然入口；脚本化场景走 Web API。
- **`devbump` 默认推送 `origin dev`**：发布闭环的收尾就是「切版 + 同步远端」两步——上一版（v0.14.5）实测需人工补 `git push origin dev`，漏做会让本地领先远端一个提交。现 `devbump` 默认执行推送，需要本地先复核时用 `--no-push`（`--push` 保留为兼容别名、与省略等效）；推送失败**不回滚**已落盘的切版提交，但会报错并给出重试命令。CLI 默认值由用例锁定（`devbump` ⇒ push=True / `--no-push` ⇒ False）。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.5（2026-10-21 ~ 2026-10-22）
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
