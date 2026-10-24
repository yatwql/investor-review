"""配置管理模块 — 读写 data/config/config.json。

支持：
- 基础配置（持仓目录/文件名/输出目录等）
- 缓存 TTL 自定义
- LLM 外部配置文件引用（API Key 不直接存储在 config.json 中）
- config.json / llm_settings.json / llm_key.json 支持 ``//`` 单行注释和 ``/* */`` 多行注释
  （自动剥离后解析），方便按业务场景分组管理配置项。

架构：config/ 子包；本文件只声明已经文档化的公共 API，不复制实现，也不导出私有名。
"""

# ── JSON 注释剥离（owner：core/json_comments.py）──
from src.python.core.json_comments import strip_json_comments

# ── 默认配置路径（config.json）──
from src.python.config._config_defaults import (
    get_config_path,
    set_config_path_override,
)

# ── 配置校验入口 ──
from src.python.config._validation import validate_config

# ── 核心逻辑 ──
from src.python.config._core import (
    datasink_feature_ready,
    del_config,
    get_comparison_candidates,
    get_config,
    init_config,
    invalidate_config_cache,
    is_enable_action,
    is_enable_candidate_compare,
    is_enable_cost_lots,
    is_enable_cost_position,
    is_enable_data_quality,
    is_enable_datasink,
    is_enable_fund_deep_analysis,
    is_enable_fund_purchase_limit,
    is_enable_history,
    is_enable_industry_beta,
    is_enable_market_sentiment,
    is_enable_market_temperature,
    is_enable_news,
    is_enable_portfolio_evolution,
    is_enable_stock_fundamentals,
    is_enable_valuation_percentile,
    set_config,
)

# ── LLM 设置解析（llm_settings.json）──
from src.python.config._llm_providers import get_llm_providers, write_llm_providers
from src.python.config._llm_settings import (
    default_enabled_llm,
    get_llm_config,
    get_llm_settings_path,
    invalidate_llm_config_cache,
    is_enable_llm,
    read_llm_settings_file,
)

# ── 日志配置（logger.json）──
from src.python.config._logging import (
    LoggerConfigError,
    read_logger_config,
    write_logger_config,
)

# ── 渠道共享 API（默认值 / 持仓与输出路径 / 正式源判定 / 本地状态标记）──
from src.python.config._config_api import (
    get_default,
    get_local_flag,
    is_formal_holdings_source,
    resolve_holdings_path,
    resolve_output_dir,
)

__all__ = [
    # 注释解析
    "strip_json_comments",
    # 配置路径
    "get_config_path",
    "set_config_path_override",
    # 核心读写
    "get_config",
    "set_config",
    "del_config",
    "init_config",
    "invalidate_config_cache",
    "validate_config",
    # 章节可见性
    "is_enable_fund_deep_analysis",
    "is_enable_news",
    "is_enable_history",
    "is_enable_llm",
    "default_enabled_llm",
    "is_enable_portfolio_evolution",
    "is_enable_stock_fundamentals",
    "is_enable_action",
    "is_enable_data_quality",
    "is_enable_candidate_compare",
    "is_enable_cost_lots",
    "is_enable_datasink",
    "datasink_feature_ready",
    "is_enable_market_sentiment",
    "is_enable_valuation_percentile",
    "is_enable_market_temperature",
    "is_enable_industry_beta",
    "is_enable_fund_purchase_limit",
    "is_enable_cost_position",
    "get_comparison_candidates",
    # LLM 配置
    "get_llm_config",
    "get_llm_providers",
    "write_llm_providers",
    "get_llm_settings_path",
    "read_llm_settings_file",
    "invalidate_llm_config_cache",
    # 日志配置
    "LoggerConfigError",
    "read_logger_config",
    "write_logger_config",
    # 渠道共享
    "get_default",
    "resolve_output_dir",
    "resolve_holdings_path",
    "is_formal_holdings_source",
    "get_local_flag",
]
