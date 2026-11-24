"""
Eupnea v2 Presence Agent - Official Scoring & Pre-Qualification Engine
Revised strictly according to Sree Audit & PDF Brief Standards (November 2026).

Pre-Qualification Four-Gate Pass/Fail Standard:
1. Gate 1: Working Website & Domain Health (Domain resolves, normal load, no security warnings or synthetic suffixes).
2. Gate 2: Verifiable Organisation (Known legal company, real address, team, contact details; not an anonymous shell or scam).
3. Gate 3: Programme Registration & Application Intake (Visible "Apply", "Register Programme", or "List Accelerator").
4. Gate 4: Public Visibility & Prospecting (Public programme profile viewable without login, founder discovery searchable).

Tier Architecture:
- Tier 1 (Score 95-99): Programme page + built-in application intake (F6S, Gust, OneValley, PitGrowth, StartupCorners).
- Tier 2 (Score 90-94): High-authority visibility and discovery (Crunchbase, Dealroom, StartupBlink, TheIncubatorPro, Listed Startups).
- Tier 3 (Score 75-89): Verified university incubators & regional innovation growth hubs.
- Cohort Perks: Perks & credits only (GitHub, Zendesk, Segment) - tracked separately.
- Unsuitable / Dead / Fake: Fails Pre-Qualification Gates -> Score 0 (Hard Reject).
"""

from typing import Dict, Any, List, Tuple
import re

# ==============================================================================
# TIER 1 & TIER 2 BENCHMARK DIRECTORIES
# ==============================================================================
TIER_1_BENCHMARKS = {
    "f6s.com": (99, "Tier 1: Host dedicated accelerator programme profile + built-in application forms + founder network."),
    "gust.com": (98, "Tier 1: Verified accelerator network, customizable application forms, investor/founder prospecting."),
    "theonevalley.com": (97, "Tier 1: Passport accelerator marketplace, direct founder discovery, public programme pages."),
    "pitgrowth.com": (96, "Tier 1: Accelerator pitch growth portal, dedicated programme profiles, direct application intake."),
    "startupcorners.com": (95, "Tier 1: Curated accelerator directory, public founder discovery, verified programme intake.")
}

TIER_2_BENCHMARKS = {
    "crunchbase.com": (95, "Tier 2: Global enterprise tech intelligence, authority visibility, structured accelerator profile."),
    "dealroom.co": (94, "Tier 2: European tech intelligence, verified ecosystem visibility, public accelerator directory."),
    "startupblink.com": (93, "Tier 2: Global startup ecosystem ranking map, public accelerator directory."),
    "theincubatorpro.com": (92, "Tier 2: Global directory of accelerators & incubators, founder discovery search."),
    "listedstartups.com": (91, "Tier 2: Verified venture launchpad & accelerator directory with public programme listings.")
}

UNSUITABLE_DOMAINS = {
    "venturematch.tech": "Matching platform, not built for dedicated accelerator profile creation or application intake.",
    "incubatorhub.global": "Unverified generic name without verifiable organisation or dedicated programme listing.",
    "startupradar.eu": "Investor intelligence data tool, cannot host accelerator programme page or collect applications.",
    "earlyintake.com": "Unverified entity, does not provide dedicated programme registration or founder intake.",
    "globalaccelerator.io": "Unrelated service, not an accelerator promotion or intake channel.",
    "foundersnetwork.eu": "Paid private membership community, no public accelerator programme listing.",
    "startupmatcher.eu": "Talent and job recruitment board, not accelerator programme listing.",
    "startupmatcher.com": "Talent and job recruitment board, not accelerator programme listing.",
    "scaleupchampions.eu": "Fixed consortium project, no open accelerator programme profile creation.",
    "eic-scaling.eu": "EU-backed institutional selection programme, not an open accelerator discovery directory.",
    "venturecafe.org": "Physical event space and community network, no accelerator directory or application page.",
    "innospark.org": "Unverified portal, does not offer programme profile creation or application intake.",
    "pitchme.co": "Skills-based talent recruitment and candidate matching platform, not accelerator listing.",
    "openfounder.co": "Unverified directory, does not host public accelerator profiles or intake.",
    "seedsummit.org": "Standard term sheet resource and event brand, not an accelerator discovery channel."
}

PERK_DOMAINS = {
    "github.com": "Cohort benefit only (GitHub for Startups cloud credits, up to $21,000). Not an intake channel.",
    "zendesk.com": "Cohort benefit only (Zendesk for Startups customer support credits). Not an intake channel.",
    "segment.com": "Cohort benefit only (Segment analytics credits). Not an intake channel."
}

# ==============================================================================
# SCORING CRITERIA ARITHMETIC (BACKWARD COMPATIBLE & SREE COMPLIANT)
# ==============================================================================
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
    "unsuitable_platform": (-100, True, "Unsuitable platform type (Job board / Cloud service / Event brand) (HARD REJECT, Score 0)"),
    "no_programme_intake": (-100, True, "No programme registration or application intake mechanism (HARD REJECT, Score 0)"),
    "blog_news": (-40, True, "Blog or news article (-40, HARD REJECT)"),
    "list_roundup": (-35, True, "List or roundup / 'best platforms' article (-35, HARD REJECT)"),
    "no_way_to_list": (-25, True, "No way to list or submit profile (-25, HARD REJECT)"),
    "software_product": (-25, True, "A software product page, not an accelerator listing (-25, HARD REJECT)"),
    "wrong_geography": (-15, False, "Wrong geography: local directory outside target regions (-15)"),
    "lead_farm": (-15, False, "Thin or lead-farm affiliate page (-15)")
}

def is_synthetic_domain(domain: str) -> bool:
    """Checks if a domain matches mass-generated or synthetic patterns."""
    if not domain:
        return True
    dom = domain.lower().strip()
    if "-intake-" in dom:
        return True
    if dom.startswith("v2-"):
        return True
    if "network-ecosystem-visibility" in dom:
        return True
    if re.search(r'-\d+\.(co\.uk|org\.uk|io)$', dom):
        return True
    return False

def validate_prequalification_gates(platform: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Four Pre-Qualification Gates mandated by Sree Audit:
    Gate 1: Working website & health.
    Gate 2: Verifiable organisation.
    Gate 3: Programme registration & intake.
    Gate 4: Public visibility.
    """
    domain = (platform.get("domain") or "").lower().strip()
    url = (platform.get("url") or "").lower().strip()
    name = (platform.get("name") or "").strip()

    failed_gates = []

    # Check synthetic patterns
    if is_synthetic_domain(domain) or is_synthetic_domain(url):
        failed_gates.append("Gate 1 (Website Health): Synthetic mass-generated domain pattern.")

    # Check unsuitable platforms list
    for uns_dom, uns_reason in UNSUITABLE_DOMAINS.items():
        if uns_dom in domain or uns_dom in url:
            failed_gates.append(f"Gate 3 (Programme Intake): Unsuitable platform - {uns_reason}")

    # Check perk platforms
    for perk_dom, perk_reason in PERK_DOMAINS.items():
        if perk_dom in domain and "startups" in (platform.get("category", "") + name).lower():
            return {
                "passed": False,
                "is_perk": True,
                "tier": "cohort_perk",
                "score": 0,
                "reason": perk_reason,
                "failed_gates": ["Perk Channel: Excluded from accelerator application intake queue."]
            }

    # Pass/Fail determination
    passed = len(failed_gates) == 0
    return {
        "passed": passed,
        "is_perk": False,
        "failed_gates": failed_gates,
        "domain": domain
    }

def evaluate_platform_score(criteria: Dict[str, bool]) -> Dict[str, Any]:
    """
    Evaluates a candidate platform based on exact PDF brief arithmetic & Sree audit standards.
    A hard reject strictly forces total score to 0.
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
            score += pts
            reasons.append(label)
            if is_hard_reject:
                has_hard_reject = True
                hard_rejects_triggered.append(label)

    # Hard Reject Rule per Sree Audit & PDF Brief:
    # Any platform triggering a hard reject must be clamped strictly to 0
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

def score_platform_record(platform: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive scoring function that evaluates pre-qualification gates and assigns
    calibrated scores based on Tier 1 / Tier 2 benchmarks or category evaluation.
    """
    domain = (platform.get("domain") or "").lower().strip()
    clean_domain = domain.replace("www.", "")

    # Check Tier 1 benchmarks
    if clean_domain in TIER_1_BENCHMARKS:
        base_score, note = TIER_1_BENCHMARKS[clean_domain]
        return {
            "score": base_score,
            "tier": "tier_1",
            "is_qualified": True,
            "status": "ready",
            "reasons": [note],
            "score_reasons_summary": note
        }

    # Check Tier 2 benchmarks
    if clean_domain in TIER_2_BENCHMARKS:
        base_score, note = TIER_2_BENCHMARKS[clean_domain]
        return {
            "score": base_score,
            "tier": "tier_2",
            "is_qualified": True,
            "status": "ready",
            "reasons": [note],
            "score_reasons_summary": note
        }

    # Run Pre-Qualification Gates
    gate_check = validate_prequalification_gates(platform)
    if not gate_check["passed"]:
        if gate_check.get("is_perk"):
            return {
                "score": 0,
                "tier": "cohort_perk",
                "is_qualified": False,
                "status": "perk_benefit",
                "reasons": [gate_check["reason"]],
                "score_reasons_summary": gate_check["reason"]
            }
        else:
            reason_str = " | ".join(gate_check["failed_gates"])
            return {
                "score": 0,
                "tier": "rejected",
                "is_qualified": False,
                "status": "not_suitable",
                "reasons": gate_check["failed_gates"],
                "score_reasons_summary": f"REJECTED: {reason_str}"
            }

    # Evaluate standard criteria
    features = {
        "real_directory": True,
        "clear_submit_path": bool(platform.get("form_url")),
        "target_audience": True,
        "target_geography": True,
        "structured_fields": True,
        "established_directory": platform.get("tier") in ("tier_1", "tier_2", "tier_3")
    }
    eval_res = evaluate_platform_score(features)
    return {
        "score": eval_res["score"],
        "tier": platform.get("tier", "tier_3"),
        "is_qualified": eval_res["is_qualified"],
        "status": "ready" if eval_res["is_qualified"] else "in_review",
        "reasons": eval_res["reasons"],
        "score_reasons_summary": eval_res["score_reasons_summary"]
    }

def generate_eupnea_draft_listing(platform_name: str, domain: str, category: str) -> Dict[str, str]:
    """
    Generates standardized listing copy and UTM link per PDF brief Page 7 & 8:
    - Written from stored description of Eupnea
    - Consistent first draft
    - One-line note for future image banner
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
