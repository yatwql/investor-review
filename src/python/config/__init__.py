"""配置管理模块 — 读写 data/config/config.json。

支持：
- 基础配置（持仓目录/文件名/输出目录等）
- 缓存 TTL 自定义
- LLM 外部配置文件引用（API Key 不直接存储在 config.json 中）
- config.json / llm_settings.json / llm_key.json 支持 ``//`` 单行注释和 ``/* */`` 多行注释
  （自动剥离后解析），方便按业务场景分组管理配置项。

架构：config/ 子包（各子模块职责见 `docs/managements/folders.md` 目录树；本文件只做公开面
re-export，不含实现）。
"""

# 保留子模块引用，供测试和外部直接访问
from src.python.config import _comments as _comments
from src.python.config import _config_defaults as _config_defaults
from src.python.config import _core as _core
from src.python.config import _json_patch as _json_patch
from src.python.config import _llm_settings as _llm_settings
from src.python.config import _llm_settings_defaults as _llm_settings_defaults
from src.python.config import _validation as _validation
from src.python.config._llm_providers import get_llm_providers, write_llm_providers  # noqa: F401
from src.python.config._llm_settings import read_llm_settings_file  # noqa: F401

# ── 日志配置（logger.json）──
from src.python.config._logging import (  # noqa: F401
    LoggerConfigError,
    read_logger_config,
    write_logger_config,
)

# ── JSON 注释剥离 ──
from src.python.config._comments import _strip_json_comments

# ── 默认配置（config.json）──
from src.python.config._config_defaults import (
    _CONFIG_FILE,
    _CONFIG_PATH_OVERRIDE,
    _DEFAULT_CONFIG,
    _get_default_config_template,
    get_config_path,
    set_config_path_override,
)

# ── 配置校验 ──
from src.python.config._validation import (
    _KNOWN_NEWS_SOURCES,
    _KNOWN_PROVIDER_NAMES,
    _KNOWN_PROVIDER_TYPES,
    _STRING_CONFIG_KEYS,
    validate_config,
)

# ── 核心逻辑 ──
from src.python.config._core import (
    _clear_config_cache,
    _config_cache,
    _config_lock,
    _config_mtime,
    _config_size,
    invalidate_config_cache,
    # 配置缓存 & 读写
    get_config,
    init_config,
    # 章节可见性
    is_enable_fund_deep_analysis,
    is_enable_history,
    is_enable_news,
    is_enable_portfolio_evolution,
    is_enable_stock_fundamentals,
    is_enable_action,
    is_enable_data_quality,
    is_enable_candidate_compare,
    is_enable_cost_lots,
    is_enable_datasink,
    datasink_feature_ready,
    is_enable_market_sentiment,
    is_enable_valuation_percentile,
    is_enable_market_temperature,
    is_enable_industry_beta,
    is_enable_fund_purchase_limit,
    is_enable_cost_position,
    get_comparison_candidates,
    set_config,
    del_config,
)

# ── LLM 设置解析（llm_settings.json）──
from src.python.config._llm_settings import (
    _KNOWN_LLM_SETTINGS_KEYS,
    _check_unknown_llm_keys,
    _ensure_llm_settings_file,
    _llm_config_cache,
    _llm_config_lock,
    _llm_config_mtime,
    _llm_config_size,
    invalidate_llm_config_cache,
    # LLM 配置
    default_enabled_llm,
    get_llm_config,
    get_llm_settings_path,
    # 章节可见性
    is_enable_llm,
)

# ── 默认模板（llm_settings.json）──
from src.python.config._llm_settings_defaults import (
    _get_default_llm_settings_template,
)

__all__ = [
    # config 默认配置
    "_DEFAULT_CONFIG",
    "_get_default_config_template",
    "_CONFIG_FILE",
    "_CONFIG_PATH_OVERRIDE",
    "get_config_path",
    # llm 默认模板
    "_get_default_llm_settings_template",
    # 注释剥离
    "_strip_json_comments",
    # 核心逻辑
    "get_config",
    "set_config",
    "del_config",
    "init_config",
    "set_config_path_override",
    "invalidate_config_cache",
    "invalidate_llm_config_cache",
    "_clear_config_cache",
    "_config_cache",
    "_config_mtime",
    "_config_size",
    "_config_lock",
    "validate_config",
    "_KNOWN_NEWS_SOURCES",
    "_KNOWN_PROVIDER_TYPES",
    "_KNOWN_PROVIDER_NAMES",
    "_STRING_CONFIG_KEYS",
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
    # 渠道共享：默认值 / 持仓路径 / 本地状态 / 注释解析（公开 API）
    "get_default",
    "resolve_output_dir",
    "resolve_holdings_path",
    "get_local_flag",
    "strip_json_comments",
    "_KNOWN_LLM_SETTINGS_KEYS",
    "_llm_config_cache",
    "_llm_config_mtime",
    "_llm_config_size",
    "_llm_config_lock",
    "_ensure_llm_settings_file",
    "_check_unknown_llm_keys",
]


# ── 渠道共享 API（默认值 / 持仓与输出路径 / 正式源判定 / 本地状态标记）──
# 实现下沉 `_config_api`（包入口只留 re-export 面）
from src.python.config._config_api import (  # noqa: F401 — 原面 re-export
    get_default,
    get_local_flag,
    is_formal_holdings_source,
    resolve_holdings_path,
    resolve_output_dir,
)


# 评论解析公开别名（原私有名保留供包内既有引用）
strip_json_comments = _strip_json_comments
