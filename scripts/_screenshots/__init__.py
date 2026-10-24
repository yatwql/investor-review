"""演示截图生成实现包（入口 `scripts/make-screenshots.py` 仅留子命令分发）。

三块实现各守一段流水线：

- `demo_workspace.py` — 隔离演示工作区（自造持仓 + 占位凭据）与报告生成
- `tui_frame.py`       — 一帧 TUI 首页文本 → PNG（与终端同源文本与配色）
- `web_shot.py`        — 无头 Chromium CDP 截图封装（实现在 `cdp_shot.mjs`）
"""
