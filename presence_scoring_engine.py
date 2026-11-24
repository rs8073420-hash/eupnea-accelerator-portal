"""
Eupnea v2 Presence Agent - Official Scoring & Pre-Qualification Engine
Powered strictly by DeepSeek Flash v4.1 Multi-Layer Verification Engine.
Specification: "Web Presence and Listing Creation AI Agent Brief (October 2026)" + Sree Audit Standards.
"""

from typing import Dict, Any, List
import deepseek_flash_engine as dfe

ENGINE_NAME = dfe.ENGINE_VERSION

TIER_1_BENCHMARKS = {k: (v["score"], v["reasoning"]) for k, v in dfe.DEEPSEEK_TIER_1_GROUNDING.items()}
TIER_2_BENCHMARKS = {k: (v["score"], v["reasoning"]) for k, v in dfe.DEEPSEEK_TIER_2_GROUNDING.items()}
UNSUITABLE_DOMAINS = dfe.DEEPSEEK_HARD_REJECT_DOMAINS
PERK_DOMAINS = dfe.DEEPSEEK_PERK_DOMAINS

POSITIVE_CRITERIA = {
    "real_directory": (30, "Real directory or programme page (+30)"),
    "clear_submit_path": (15, "A clear way to submit or apply (+15)"),
    "target_audience": (15, "The right readers: founders, investors, universities (+15)"),
    "target_geography": (10, "UK, Europe, or global geography (+10)"),
    "structured_fields": (10, "Structured profile fields (+10)"),
    "established_directory": (10, "An established directory prestige (+10)"),
    "tier_1_intake": (15, "Tier 1: Full programme page + built-in application intake (+15)"),
    "tier_2_discovery": (10, "Tier 2: High-authority public visibility and founder discovery (+10)")
}

NEGATIVE_CRITERIA = {
    "unworking_website": (-100, True, "Non-working website / Dead link / Unresolving domain (HARD REJECT, Score 0)"),
    "unverified_org": (-100, True, "Unverifiable organisation / No address / Scam flags (HARD REJECT, Score 0)"),
    "synthetic_domain": (-100, True, "Synthetic pattern / Fake intake domain (HARD REJECT, Score 0)"),
    "unsuitable_platform": (-100, True, "Unsuitable platform type (Job board / SaaS tools / Cloud / Events) (HARD REJECT, Score 0)"),
    "no_programme_intake": (-100, True, "No programme registration or application intake mechanism (HARD REJECT, Score 0)"),
    "blog_news": (-40, True, "Blog or news article (-40, HARD REJECT)"),
    "list_roundup": (-35, True, "List or roundup / 'best platforms' article (-35, HARD REJECT)"),
    "no_way_to_list": (-25, True, "No way to list or submit profile (-25, HARD REJECT)"),
    "software_product": (-25, True, "A software product page, not an accelerator listing (-25, HARD REJECT)"),
    "wrong_geography": (-15, False, "Wrong geography: local directory outside target regions (-15)"),
    "lead_farm": (-15, False, "Thin or lead-farm affiliate page (-15)")
}

def is_synthetic_domain(domain: str) -> bool:
    is_synth, _ = dfe.DeepSeekFlashEngine.detect_synthetic_pattern(domain, domain)
    return is_synth

def validate_prequalification_gates(platform: Dict[str, Any], verify_network: bool = False, use_llm: bool = False) -> Dict[str, Any]:
    return dfe.DeepSeekFlashEngine.evaluate_prequalification_gates(platform, verify_network=verify_network, use_llm=use_llm)

def evaluate_platform_score(criteria: Dict[str, bool]) -> Dict[str, Any]:
    """Evaluates a candidate platform based on exact PDF brief arithmetic & Sree audit standards."""
    score = 0
    reasons: List[str] = []
    hard_rejects_triggered: List[str] = []
    has_hard_reject = False

    for key, (pts, label) in POSITIVE_CRITERIA.items():
        if criteria.get(key, False):
            score += pts
            reasons.append(label)

    for key, (pts, is_hard_reject, label) in NEGATIVE_CRITERIA.items():
        if criteria.get(key, False):
            score += pts
            reasons.append(label)
            if is_hard_reject:
                has_hard_reject = True
                hard_rejects_triggered.append(label)

    if has_hard_reject:
        score = 0
        is_qualified = False
        classification = "rejected_by_rule"
    else:
        score = max(0, min(100, score))
        is_qualified = (score >= 70)
        if score < 50:
            classification = "weak"
        elif score <= 69:
            classification = "borderline"
        else:
            classification = "qualified"

    return {
        "score": score,
        "is_qualified": is_qualified,
        "classification": classification,
        "has_hard_reject": has_hard_reject,
        "hard_rejects": hard_rejects_triggered,
        "reasons": reasons,
        "score_reasons_summary": " | ".join(reasons) if reasons else "No criteria matched baseline."
    }

def score_platform_record(platform: Dict[str, Any], verify_network: bool = False, use_llm: bool = False) -> Dict[str, Any]:
    """Primary platform scoring router strictly backed by DeepSeek Flash v4.1 Engine."""
    return dfe.DeepSeekFlashEngine.score_platform(platform, verify_network=verify_network, use_llm=use_llm)

def generate_eupnea_draft_listing(platform_name: str, domain: str, category: str) -> Dict[str, str]:
    clean_domain = domain.lower().replace(".", "_").replace("-", "_")
    tracking_code = f"https://eupnea.co.uk/?utm_source={clean_domain}&utm_medium=directory&utm_campaign=presence_2026"
    
    title = f"Eupnea UK Accelerator Programme 2026 | {platform_name}"
    pitch = (
        "Eupnea UK Accelerator Cohort 2026: £50k–£250k seed funding, 12-week venture scale program for Enterprise AI, CleanTech, and FinTech ventures."
    )
    full_description = (
        f"Eupnea UK Accelerator Programme 2026 is officially accepting applications from visionary early-stage tech founders.\n\n"
        f"Program Highlights:\n"
        f"• Seed Funding Allocation: £50,000 to £250,000 equity-backed / convertible\n"
        f"• 12-Week Acceleration Sprint: Discover, Design, Deliver, Sustain\n"
        f"• Sector Focus: Enterprise AI, CleanTech, HealthTech, FinTech, and B2B SaaS\n"
        f"• London Ecosystem: 124 City Road, London EC1V 2NX with direct commercial pilot introductions\n\n"
        f"Apply directly via {platform_name} ({category}) or visit official application portal.\n"
        f"Contact: clientservices@eupnea.co.uk | Phone: +44 203 026 1523"
    )
    
    return {
        "title": title,
        "draft_pitch": pitch,
        "draft_full": full_description,
        "tracking_url": tracking_code,
        "banner_note": "Minimalist Oxford Navy & Slate Teal dual-tone banner with Eupnea logo mark"
    }
