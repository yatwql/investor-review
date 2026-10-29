"""动作短语单源：语义名 → 带菜单键的下一步动作。

为什么要单源：页头状态行的异常提示与 ``[ERR]`` 错误行都要在末尾给「下一步按什么」。
两处各写一份短语，迟早出现「页头说 [3] 清理、错误行说 [1] 更新」这类漂移；而短语
的可执行性又依赖菜单键，键位一改就得两处同时改。本模块是唯一写入点。

约束：
  - 短语首个方括号内必须是**主菜单顶层键**（``[G]→L`` 这类二级入口只校验首键），
    由 ``test_tui_menu_status`` 对主菜单键做子集校验——菜单改键即红；
  - 短语保持 6 字上下，超长会被页头折行、错误行换行，破坏单行可读性。
"""

from __future__ import annotations

#: 异常态动作提示（键 = 语义名，值 = 上屏短语）
ACTION_TEMPLATES: dict[str, str] = {
    # 报告
    "report_missing": "[B] 生成标准报告",
    "report_interrupted": "[B] 重新生成",
    "report": "[B] 重新生成",
    # 缓存与数据新鲜度
    "cache_expired": "[3] 清理过期缓存",
    "freshness": "[2] 更新行情缓存",
    "cache": "[1] 更新基础类缓存",
    # 诊断
    "degraded_sources": "[D]→V 看数据源记录",
    "logs": "[D]→L 看运行日志",
    # 配置
    "config": "[G] 检查全局设置",
    "llm_unconfigured": "[G]→L 配置 LLM",
}


def action_phrase(action_key: str | None) -> str:
    """取动作短语（未知键返回空串：调用方据此省略箭头，不在运行时抛错）。"""
    if not action_key:
        return ""
    return ACTION_TEMPLATES.get(action_key, "")
