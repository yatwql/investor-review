# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.14.2]**（2026-10-22）——已发布版本段随发布移入 [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.14.3-dev] - 开发中（未发布）

### Added

- **`--mode portability`：CI portability job 本地等价复现**：新增非 pytest 探针模式（`scripts/_test_runner/portability.py`），一条命令跑 CI 的阻塞探针——①`PYTHONWARNDEFAULTENCODING=1` 隐式编码严格档（单元套件）；②需求文件 BOM/PEP263 **确定性判定** + `LC_ALL=C` 下 `pip install --dry-run` 烟测（pip ≥25 起默认 UTF-8，输出提示「完整判定需 pip ≤24.x」，确定性判定始终生效）。探针模式无 marker、不进 bench 与三档门禁，计数量按探针项数；配套纪律「本地门禁通过后不逐提交轮询 CI」写入 CLAUDE.md 与 developer-guide。回归 13 例（BOM/cookie 四态、两道探针环境与失败回传、聚合口径、注册表接线）。

- **Social Preview 生成脚本入库**：`scripts/make-social-preview.py` 把 1200×630 品牌预览图的画布模板（猫头鹰「守望」左卡 + 品牌文案右栏 + 夜空渐变）与渲染流程固化进仓库——素材复用 `src/static/owl-mascot.svg`，改文案/换色后重跑即就地刷新入库资产 `src/static/social-preview.jpg`（默认输出，`-o` 可改道临时目录），提交后由人工上传到仓库 Settings。`cairosvg` 为维护期可选依赖（不入 requirements：无 cairo 系统库的环境装不上），缺依赖或素材不可读时打印指引并以退出码 1 结束。回归 12 例（画布尺寸/品牌文案/素材内嵌一致/宽高比/入库资产定位/成品尺寸/栅格化参数/中间 PNG 去留/两条退出码路径）。

### Changed

- **脚本分类重整（七域 + CLI 入口）**：原「诊断」是杂物袋（连通性探针 / 性能基准 / 能力评测 / 渲染检查 / 用户子命令混坐），且同族脚本分落不同域（`llm-hallucination-sampler` 在测试、`factor_zoo_eval` 在诊断，sampler 另有独立章节）。现按**活动类型**重划：拆出「运维观测」（`probe*` / `perf-view` / CLI 的 `check-sources`·`doctor`·`view-logs`·`cassettes`）与「评测与基准」（`perf-test-report` / `llm-hallucination-sampler` / `factor_zoo_eval` / `calibrate-dedup-threshold`）；`check-svg` 归「文档」（检 README 架构图）、`whatif` 归「CLI 子命令」（用户功能，非维护工具）、需求追溯与任务编号四件归「代码与文件质量」（门禁职责）。`scripts-reference.md` 一览/小节/目录与 `developer-guide.md` 按域索引（7→8 行）同步，域行数断言同源更新。

- **README 实景截图全面刷新**：报告三图（首屏品牌标记与目录导航 / 盈亏汇总与市场指数 / 穿透行业分布与 TOP10 持仓交互图表）与 TUI 主菜单、Web 工作台、Web 配置三图按当前版本（v0.14.3-dev）重拍，并新增 **CLI 渠道回显图**（产物路径 / 盈亏汇总 / 模块耗时排行）；样例持仓为虚构两账户 10 只（个股 / ETF / 场外基金 / 债券基金 / 货币 ETF），在隔离目录内生成，真实持仓、缓存与报告目录零接触；README 图说与 folders 目录树/统计行同步（截图 6→7 张）。

- **品牌标记补用（`rf-818`）**：猫头鹰「守望」此前只活在 README 与 Web favicon，报告与 Excel 首页没有标记。现 `DESIGN.md` 契约收窄为「拒绝 hero 大图、装饰性插画」并新增「品牌标记」条款（≤40px 身份识别、Excel ≤48px、不做装饰）+ 护栏 11；报告 favicon 由折线图换猫头鹰头像、页头加 32px 标记（窄屏 26px）、Web 工作台页头 36px、Excel 首页 40px（cairosvg 栅格化，失败静默跳过）；新增 `--brand-mark-ink` token 并登记 Colors 表。回归 5 例。

- **仓库更名 `investor-util` → `investor-review`（`rf-817`）**：`util` 后缀与产品定位（完整工作流的应用，非脚本合集）矛盾，且与中文名「投资复盘助手」语义不对应。同步 14 个文件 47 处引用：README 徽章与 clone 命令、`pyproject.toml` 包名、目录树根名、四份用户手册路径示例、CLI/Web `prog` 显示名、三个 provider 的 HTTP `User-Agent`、通知邮件 `From` 兜底。GitHub 侧旧 URL 永久 301 重定向，外部引用不断。

### Fixed

- **报告域重复实现清理（`rf-821`）**：`report/html_writer_status.py` 里与 `report/html_writer.py` 逐字相同的 `_render_template`/`write_html_report`（约 591 行）与文件内重复定义的状态构建辅助一并删除，模块回归「数据状态装配」单一职责（901 → 134 行）；核心渲染保持 `html_writer.py` 单实现，失效的 re-export/import 与失真导览注释同步清理。
- **文档分类重整遗留漂移清理（`rf-820`）**：`scripts-reference.md` 组标题归位（「测试质量机检」误迁入评测类、「冒烟与采样」剩单条改「冒烟验证」）、质量类条目读序改为「痕迹 → 需求追溯 → 编号/钩子 → 行数/契约/护栏」；`README.md` 去掉会随开发演进的硬编码计数（22 项开关 → 全部开关含实验项、六个 LLM 模块 → 全部模块、10 张图表 → 实测 12 张）；删除 `docs/tmp/github/` 中与入库资产重复的预览图副本。
- **Social Preview 脚本默认输出与装配修正（`rf-819`）**：`_load_render_deps` 仍按旧字段名 `image_cls` 构造 `RenderDeps`，真机执行即 `TypeError`（回归只走注入替身，未覆盖真实导入装配）——改为 `image_module` 并补「真实导入装配」用例；默认输出改为入库资产 `src/static/social-preview.jpg`（受 git 管控，重跑即就地刷新），`-o` 可改道；重跑产物与已提交图片逐字节一致。

- **`publish` 提交前同步统计快照（`rf-816`）**：钩子对含 `src/test` 变更的提交走 `--sync --ci --with-test-count`，而 `publish` 原先不校验，只跑 `--sync` 时 `test-coverage.md` 收集计数陈旧不被发现——本地通过、钩子仍红，v0.14.2 连败两次 publish。现 `publish` 在提交前自动按同源参数同步，失败即中止；补 2 例回归。

- **浮点断言容差化（`rf-815`）**：v0.14.2 的 `test_unequal_lengths_uses_shorter` 用逐位相等比较「对齐到较短者」与「显式截断」两条路径（末位差 1.6e-17，3.13 恰好相等、3.11 不等）→ 改 `pytest.approx(abs=1e-12)`，长度敏感反例改 `> 1e-6`。同时把纪律落进三处文档：根 `CLAUDE.md` 测试纪律、`developer-guide.md` 测试写作规范（正反例）、`testplan.md` 的「浮点比较边界」边界行——判据是「语义等价就带容差，精确可表示值才用 `==`」，容差取「远大于 ulp、远小于真正区分的量级」。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.2（2026-10-21 ~ 2026-10-22）
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
