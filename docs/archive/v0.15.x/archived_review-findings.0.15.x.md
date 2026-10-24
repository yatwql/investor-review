# 自审记录归档 — v0.15.x

> 归档时间：2026-10-24（v0.15.0 发布，本系列首批开发期已修复批次并入）；2026-10-24 v0.15.0 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.15.x 开发期已修复项（v0.15.0 → ）（含 v0.15.0）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 开发期已修复（0.15.0-dev）

> 完整复盘见 `changelog.md` 0.15.0-dev 段；此处为台账原表搬运（无损），本批发布日 2026-10-24。

| # | 问题 | 修复 |
|---|------|------|
| **rf-841** | changelog 指针行跨小版本时指向旧档：`apply_changelog_release` 只重写反引号里的归档文件名，`(../archive/v0.15.x/...)` 的目标路径仍旧——文件存在故死链检查不报，人点进去看的是上一系列归档 | 指针行同时改写链接文本与目标路径（目录按新归档文件名派生）；补回归用例 `test_pointer_line_target_path_follows_minor` |
| **rf-840** | 发布工具链契约不一致：`archive-init` 写出的 changelog 归档索引行是占位形态 `— v0.15.x（date ~ date）`，`prepare` 的改写正则只接受 `vX.Y.Z` → 新小版本首次发布在 prepare 阶段硬失败 | 索引正则接受占位形态并按「首版」语义归一为 `v{release}（date）`；真实仓库契约测试对「刚 init 未发布」的空骨架放宽为「有则同形」；补回归用例 `test_archive_init_placeholder_line_is_accepted` |
| **rf-838** | `test_json_comments` 的叶子模块边界用例用 `subprocess.run(text=True)` 未指定编码——`PYTHONWARNDEFAULTENCODING=1` 下直接告警为错误（`error::EncodingWarning`），`LC_ALL=C` 等非 UTF-8 locale 还会按 cp936/latin-1 解码子进程输出 | 显式 `encoding="utf-8"` + `errors="replace"`；由 portability 隐式编码严格档拦截，无需新增用例 |
| **rf-836** | 事实校验自动修正器产出用户可见畸形数值（`持仓收益率+-9.0%`）：把占比当收益率改写、同句多代码主体归属错、替换不处理原符号 | 三条同修：① 数值前文语义（占比/最大持仓/份额/市值/仓位等局部窗口）→ 不参与收益率修正；② 主体归属改为括号 > 分句 > 全句三级作用域；③ 替换时剥除原符号（新值符号优先，正值且原文有 `+` 时延续）并按 `[+-]{2,}` 做畸形自检，命中整批不写回。回归用例 6 例（`TestNonReturnMetricAndSignNormalization`） |
| **rf-837** | 计价模块懒加载标志与显式重载不一致：显式 `reload_pricing()` 后 `_PRICING_LOADED` 仍为 False，进程内首次计费会再读一次配置文件并覆盖已装载的定价（用例单独执行失败、整文件通过） | `reload_pricing()` 在 `finally` 置 `_PRICING_LOADED = True`；新增回归用例 `test_explicit_reload_is_not_undone_by_lazy_init`（断言显式重载后计费直接使用已装载的定价） |
| **rf-842** | TUI 动线驱动器漏覆盖一类处理器：`_cmd_diagnose_menu` 等函数内 `from tui_keys import input_choice` 局部导入，模块属性 patch 无效；非 TTY 下 `input_choice` 退化为内置 `input()` → 动线跑不动（读真实 stdin）或静默错位。日志动线（`filter_logs_by_level`）场景用例因此长期失效，只在 P2 regression 档暴露 | 驱动器 `_patch_readers` 增补 `builtins.input` 兜底（不 patch 源头，避免跨用例永久绑定）；该动线按键序列按菜单分层更新为 `[D]→[V]→级别→按键→[0]→[X]`（6 键），契约快照同步并说明「加长来自菜单分层而非新增确认屏」 |
