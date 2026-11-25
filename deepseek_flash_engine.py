"""
Legacy import bridge kept ONLY for compatibility with historical scripts.
Strictly delegates 100% to GeminiHydrogenEngine (Gemini 4 Hydrogen).
Zero DeepSeek API endpoints or credentials are used anywhere in this codebase.
"""

from gemini_hydrogen_engine import (  # noqa: F401
    ENGINE_VERSION,
    ALGORITHM_SPEC,
    MODEL_PROFILE,
    GEMINI_TIER_1_GROUNDING,
    GEMINI_TIER_2_GROUNDING,
    KNOWN_REGISTRATION_HUB_DOMAINS,
    NON_HUB_SINGLE_ENTITY_DOMAINS,
    WAF_ALIVE_WHITELIST,
    HARD_REJECT_DOMAINS,
    PERK_DOMAINS,
    UNSUITABLE_TITLE_CONTENT_PATTERNS,
    EUPNEA_INTERNAL_TEAM,
    GeminiHydrogenEngine,
    GEMINI_TIER_1_GROUNDING as DEEPSEEK_TIER_1_GROUNDING,
    GEMINI_TIER_2_GROUNDING as DEEPSEEK_TIER_2_GROUNDING,
    HARD_REJECT_DOMAINS as DEEPSEEK_HARD_REJECT_DOMAINS,
    PERK_DOMAINS as DEEPSEEK_PERK_DOMAINS,
    GeminiHydrogenEngine as DeepSeekFlashEngine,
)
