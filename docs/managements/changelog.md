# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.17.6]**（2026-11-08）——已发布版本段随发布移入 [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.17.7-dev] - 开发中（未发布）

### 新增

- **TUI 首页最下方显示本机 IP** —— 主菜单帧末新增一行弱化展示（`本机 IP 192.168.1.5`），
  数据取自 `core/logger.get_machine_ip` 单源（优先非回环网卡），与页头状态行共用 45 秒
  TTL 记忆化（首页逐帧重绘，不重复探测）；探测不到时整行降级为 `本机 IP —`，按列宽折行
  且计入原地重绘行数。用途：在手机/另一台机器上访问本机时不必再去系统里查地址。
  契约行见 `DESIGN-TUI.md` 反馈表，手册见 `how-to-use-tui-menu.md`。

### 修复

- **Windows 非交互环境按键读取不再阻塞（rf-1099）** —— `tui_keys._get_key_windows()` 缺 `isatty`
  前置判定（Linux 分支已有），非交互 stdin 下 `msvcrt.getch()` 会一直等键，表现为 `standard`/`unit`
  整档跑到 720s 超时；现判定提到 `import msvcrt` 之前，非 tty 直接返回 `KEY_UNKNOWN`，并补回归用例。

- **并行档位可固定且不再无上限放大（rf-1098）** —— worker 数仍按核数×档位系数计算，但缺省档
  `medium` 封顶 8（实测 16 核上 8 worker 最优、16 反而慢约 17%）；新增 `TEST_RUNNER_PARALLEL`
  环境变量固定档位（优先级 `--parallel` > 环境变量 > 缺省），worker 少于核数时输出提示可提升方式；
  `scripts-reference.md` 补「并行级别怎么选」（含 Windows 上杀软排除建议）。

- **门禁链路提速三层（不降覆盖，rf-1097）** —— `check-types.py` 新增 `--changed`（钩子只查本次变更文件，
  回退规则：变更 >25 个或取不到 git 清单即跑全量；CI guards 与 P2 始终全量）；`dev-verify` 排除
  `real_repo` 标记的真实仓库守护冒烟（钩子已对同一棵树跑过，`verify`/CI 仍全跑）；按计时重新校准
  离线声明。实测 `dev-verify` 45.5s → 33.2s、钩子 13.5s → ≈5s。

- **时间相关缓存用例去钟面依赖（rf-1096）** —— 11 个 LLM 缓存用例断言「同产出第二次命中缓存」，
  却未钉死行情口径桶（盘中档禁止复用价格相关模块），09:00–15:00 跑必红、收盘后转绿；统一注入
  autouse「钉收盘档」fixture，llm 全档 1679 通过。

- **`scripts/` 类型错误清零，类型守护域扩到入口脚本（rf-1093）** —— 顶层脚本 50 处 pyright error
  逐簇清掉（`sys.stdout.reconfigure` 用 `cast` 取具体实现、`ctypes.windll`/`msvcrt` 平台桩走
  `getattr`、动态 target 的 `build_parser` 判空、AST 节点用 `getattr(node, "lineno", 0)`、
  `check-doc-traces` 的分支内赋值先落默认值），`[tool.pyright] include` 与 `check-types` 受检域
  从 `src/python` 扩为 `src/python` + `scripts`。

- **测试归档保留期清理（rf-1095）** —— `test-reports/archives/` 长期无轮转（实测 31 份 ≈ 17G）。
  新增 `scripts/_test_runner/retention.py`：次数闸门（保留最近 N 次，缺省 10）+ 体积闸门
  （总量上限，缺省 2 GiB），两侧均可用 `--keep-runs` / `--archive-cap-mb` 覆盖或关闭；清理在
  `test-runner.py` 启动前静默执行，删除失败只告警且不计入已删，空日期层目录一并回收。

- **类型谓词单源化 + 陈旧离线声明清理（rf-1094）** —— 全仓 5 份「有限真数值」谓词
  （`analysis/holding_change_events`、`analysis/trade_cost_model`、`llm/prompts_signals`、
  `report/chart_data_builder` 各一份 + `core/num_utils.is_finite_number`）收敛为
  `core.num_utils.is_finite_number`（升级 `TypeGuard[int | float]`），各模块只引用不复制；
  同时按「撤声明 → 单跑该文件 → 全绿即陈旧」的试跑法清掉 66 处陈旧
  `offline_external_sources`（保留 61 处确有附带依赖者），恢复「离线桩不得遮盖真实外部访问」。
  另修 `analysis/factor_evaluator` 的 ±inf 语义回归（改用 `value_present` 口径，inf 保留）、
  `core/cassette` 索引的目录竞态兜底。

- **类型检查落地为门禁（rf-1092）** —— `src/python` 的 pyright 错误由 83 处清零（可空值逐点收窄、
  数值归一统一走 `core.num_utils` 的 `safe_num`/`finite_or`、谓词升级 `TypeGuard`、平台桩走
  `getattr` 降级、`PacingGate.__exit__` 改 `-> None`、`cache._store` 用 `builtin_set` 避开同名遮蔽），
  并新增 `scripts/check-types.py`（0 通过 / 1 环境缺失 / 2 有 finding）入 pre-commit 与 CI `guards`；
  规则基线落 `pyproject.toml [tool.pyright]`（受检域 `src/python`，`src/test` 刻意不入域——单测
  mock 噪声远多于缺陷收益，由 pytest 运行时守卫）。`scripts/` 入口脚本残余 52 处另立项（rf-1093）。

- **计价节假日判定只读缓存交易日历（rf-1089）** —— `llm/pricing.py::_is_holiday` 原经
  `trading_calendar._is_trading_day` 判定，日历缓存缺失时会真实取数（akshare）；计价发生在
  每次 LLM 调用收尾，为此拉一次远端日历既慢又与本次调用无关，且无日历缓存的机器 / CI 上
  会把整批 LLM 缓存用例拦成网络守卫硬失败。改为只读 `cached_trading_days()`（不触网），
  无缓存时按「非周末即交易日」降级；补 4 例回归（不触网 / 无缓存降级 / 周末不查日历 / 异常降级）。

- **`cost_first` 策略单价键纠错（rf-1090）** —— `llm/strategy.py::_apply_cost_first` 原读
  `input_price`/`output_price`，而计价表实际键为 `input`/`output`：所有模型得分恒 `inf`，
  `cost_first` 静默退化为「保持原序」（旧用例用同款假键名把错哄住）。改读真实键 + 模型名小写
  归一，缺价/币种子表按未知排末尾；用例改用真实键名，并新增以**真实定价表**为真值的顺序断言。

- **一行静态检查清出的真实隐患（rf-1091）** —— `api_base._attempt` 的 `result` 可能未绑定
  （`PacingGate.__exit__` 声明 `-> bool` 即可被推断为吞异常，现已改 `-> None`）、
  `analysis/scenario.py` 的 CI 区间值可能为 None 仍参与乘法、`analysis/rebalance.py` /
  `trade_discipline.py` 配置段可能为 None 却直接 `dict()` / 下标、`tui_keys` 的 msvcrt 平台桩
  与 `fd` 可空、`holding_change_review` 方向值 `get` 重载不匹配。均为「值判空 + 显式收窄」修复，
  无行为变更。

- **代码类型判定回归中心化（rf-1088）** —— `core/holdings_editor.py::ambiguous_price_kind`
  原内联 `len(raw) == 6 and raw.startswith("00")` 自行判代码形态与 00 重叠区，属架构约束
  「代码类型判定中心化」违规；改用 `code_utils.is_six_digit_code` +
  `is_otc_code_overlap`，与 `price_kind`/`analysis/rebalance.py` 等处口径同一源（消除「代码类型判定中心化」约束下的分散判定）。
  行为不变，补「非 6 位码恒 False」形态用例锁住门槛。

- **主机 IP 展示不再恒为回环** —— 三端（TUI 首页摘要 / CLI 启动日志 / Web 系统信息）
  共用的 `core/logger.py::get_machine_ip` 原为 `gethostbyname(gethostname())`，在
  `/etc/hosts` 把主机名映射到 `127.0.0.1`/`127.0.1.1` 的机器上恒显示回环，对「在哪台
  机器的哪个地址访问」没有信息量。改为按可靠性降序取首个非回环地址：默认出口网卡
  （UDP `connect` 只建路由不发包）→ 主机名解析出的全部 IPv4 → 仅回环可用时仍返回
  回环（离线单机场景它仍是正确地址）→ 全失败 `unknown`。测试网络守卫以
  `BaseException` 子类阻断外部建连，该兜底路径不得让其冒成启动失败。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.6（2026-11-04 ~ 2026-11-08）
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
