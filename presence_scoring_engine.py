"""
Eupnea v2 Presence Agent - Official Scoring Arithmetic Engine
Strict implementation according to 'Web Presence and Listing Creation AI Agent Brief (October 2026)', Pages 7-8.

Rules:
1. A site starts at 0 points.
2. The total is kept strictly between 0 and 100.
3. Positive additions:
   - Real directory or programme page: +30
   - A clear way to submit or apply: +15
   - The right readers (founders, investors, universities, public bodies): +15
   - UK, Europe, or global geography: +10
   - Structured profile fields (name, description, location, sector): +10
   - An established directory (known accelerator, university, gov): +10
4. Negative points & Hard rejects:
   - Blog or news article: -40 (HARD REJECT)
   - List or roundup ('7 best platforms'): -35 (HARD REJECT)
   - No way to list / submit: -25 (HARD REJECT)
   - A software product page: -25 (HARD REJECT)
   - The wrong geography: -15
   - Thin or lead-farm page: -15
5. Qualification rule:
   - "A hard reject cannot be outweighed by other points. A well-written blog post is still rejected."
   - A site qualifies ONLY when total score is 70 or higher AND none of the hard rejects apply.
6. Display classification:
   - Under 50: Weak
   - 50 to 69: Borderline
   - 70 or above: Qualified
"""

from typing import Dict, Any, List, Tuple

POSITIVE_CRITERIA = {
    "real_directory": (30, "Real directory or programme page (+30)"),
    "clear_submit_path": (15, "A clear way to submit or apply (+15)"),
    "target_audience": (15, "The right readers: founders, investors, universities (+15)"),
    "target_geography": (10, "UK, Europe, or global geography (+10)"),
    "structured_fields": (10, "Structured profile fields (+10)"),
    "established_directory": (10, "An established directory prestige (+10)")
}

NEGATIVE_CRITERIA = {
    "blog_news": (-40, True, "Blog or news article (-40, HARD REJECT)"),
    "list_roundup": (-35, True, "List or roundup / 'best platforms' article (-35, HARD REJECT)"),
    "no_way_to_list": (-25, True, "No way to list or submit profile (-25, HARD REJECT)"),
    "software_product": (-25, True, "A software product page, not a listing (-25, HARD REJECT)"),
    "wrong_geography": (-15, False, "Wrong geography: local directory Eupnea cannot join (-15)"),
    "lead_farm": (-15, False, "Thin or lead-farm affiliate page (-15)")
}

def evaluate_platform_score(criteria: Dict[str, bool]) -> Dict[str, Any]:
    """
    Evaluates a candidate platform based on exact PDF brief arithmetic.
    """
    score = 0
    reasons: List[str] = []
    hard_rejects_triggered: List[str] = []
    has_hard_reject = False

    # 1. Positive points
    for key, (pts, label) in POSITIVE_CRITERIA.items():
        if criteria.get(key, False):
            score += pts
            reasons.append(label)

    # 2. Negative deductions & Hard rejects
    for key, (pts, is_hard_reject, label) in NEGATIVE_CRITERIA.items():
        if criteria.get(key, False):
            score += pts  # pts is negative
            reasons.append(label)
            if is_hard_reject:
                has_hard_reject = True
                hard_rejects_triggered.append(label)

    # 3. Clamp between 0 and 100
    score = max(0, min(100, score))

    # 4. Qualification logic per PDF brief
    # "A site qualifies only when the total is 70 or higher, and only when none of the hard rejects apply."
    is_qualified = (score >= 70) and (not has_hard_reject)

    # 5. Display classification
    if score < 50:
        classification = "weak"
    elif score <= 69:
        classification = "borderline"
    else:
        classification = "qualified" if not has_hard_reject else "rejected_by_rule"

    return {
        "score": score,
        "is_qualified": is_qualified,
        "classification": classification,
        "has_hard_reject": has_hard_reject,
        "hard_rejects": hard_rejects_triggered,
        "reasons": reasons,
        "score_reasons_summary": " | ".join(reasons) if reasons else "No criteria matched baseline."
    }

def generate_eupnea_draft_listing(platform_name: str, domain: str, category: str) -> Dict[str, str]:
    """
    Generates standardized listing copy and UTM link per PDF brief Page 7 & 8:
    - Written from stored description of Eupnea
    - Consistent first draft
    - One-line note for a future image banner
    - Unique UTM tracking code
    """
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
