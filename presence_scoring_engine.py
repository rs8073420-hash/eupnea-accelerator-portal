"""
Eupnea v2 Presence Agent - Official Scoring & Pre-Qualification Engine
Powered strictly by Gemini 4 Hydrogen Multi-Layer Verification Engine.
Specification: "Web Presence and Listing Creation AI Agent Brief (October 2026)" + Sree Audit Standards
+ Panagiotis Editable Point System, Quality Telemetry & F6S/Gust Hub Classification.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import gemini_hydrogen_engine as ghe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "presence_agent.db")

ENGINE_NAME = ghe.ENGINE_VERSION

TIER_1_BENCHMARKS = {k: (v["score"], v["reasoning"]) for k, v in ghe.GEMINI_TIER_1_GROUNDING.items()}
TIER_2_BENCHMARKS = {k: (v["score"], v["reasoning"]) for k, v in ghe.GEMINI_TIER_2_GROUNDING.items()}
UNSUITABLE_DOMAINS = ghe.HARD_REJECT_DOMAINS
PERK_DOMAINS = ghe.PERK_DOMAINS

POSITIVE_CRITERIA = {
    "real_directory": (30, "Real directory or programme page (+30)"),
    "clear_submit_path": (15, "A clear way to submit or apply (+15)"),
    "target_audience": (15, "The right readers: founders, investors, universities (+15)"),
    "target_geography": (10, "UK, Europe, or global geography (+10)"),
    "structured_fields": (10, "Structured profile fields (+10)"),
    "established_directory": (10, "An established directory prestige (+10)"),
    "tier_1_intake": (15, "Tier 1: Full programme page + built-in application intake (+15)"),
    "tier_2_discovery": (10, "Tier 2: High-authority public visibility and founder discovery (+10)"),
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
    "lead_farm": (-15, False, "Thin or lead-farm affiliate page (-15)"),
    "broken_form_penalty": (-10, False, "Broken/404 Form URL while Portal root loads (-10)"),
    "regional_chamber_penalty": (-30, False, "Generic Regional Chamber / Civic Network (-30)"),
}

CRITERIA_CATALOG: List[Dict[str, Any]] = [
    {
        "key": "real_directory",
        "label": "Real Directory or Programme Page",
        "criterion_type": "positive",
        "category_group": "Core Relevance",
        "default_points": 30,
        "is_hard_reject": 0,
        "description": "Dedicated accelerator directory, incubator hub, or programme showcase.",
        "display_order": 1,
    },
    {
        "key": "clear_submit_path",
        "label": "Clear Submission / Application Path",
        "criterion_type": "positive",
        "category_group": "Intake & Usability",
        "default_points": 15,
        "is_hard_reject": 0,
        "description": "Verified working registration, submit-programme, or founder intake URL (HTTP 200).",
        "display_order": 2,
    },
    {
        "key": "target_audience",
        "label": "Founder / Investor / University Audience",
        "criterion_type": "positive",
        "category_group": "Audience Fit",
        "default_points": 15,
        "is_hard_reject": 0,
        "description": "Attracts early-stage founders, angel syndicates, VCs, or research spinouts.",
        "display_order": 3,
    },
    {
        "key": "target_geography",
        "label": "UK, European, or Global Reach",
        "criterion_type": "positive",
        "category_group": "Geography",
        "default_points": 10,
        "is_hard_reject": 0,
        "description": "Explicit UK, European, or international cohort discovery remit.",
        "display_order": 4,
    },
    {
        "key": "structured_fields",
        "label": "Structured Profile & Intake Fields",
        "criterion_type": "positive",
        "category_group": "Data Depth",
        "default_points": 10,
        "is_hard_reject": 0,
        "description": "Supports structured programme criteria (equity terms, deadlines, sector tags, SmartMatch).",
        "display_order": 5,
    },
    {
        "key": "established_directory",
        "label": "Established Authority & Visibility",
        "criterion_type": "positive",
        "category_group": "Authority",
        "default_points": 10,
        "is_hard_reject": 0,
        "description": "Verified active organisation with recognisable domain presence and SEO visibility.",
        "display_order": 6,
    },
    {
        "key": "tier_1_intake",
        "label": "Tier 1 Full Programme + Direct Intake",
        "criterion_type": "positive",
        "category_group": "Strategic Tier",
        "default_points": 15,
        "is_hard_reject": 0,
        "description": "Hosts full programme page AND direct founder application pipeline (F6S, Gust, OneValley, SmartMatch).",
        "display_order": 7,
    },
    {
        "key": "tier_2_discovery",
        "label": "Tier 2 Public Ecosystem Visibility",
        "criterion_type": "positive",
        "category_group": "Strategic Tier",
        "default_points": 10,
        "is_hard_reject": 0,
        "description": "Public venture intelligence database or UK ranking index providing high founder discovery.",
        "display_order": 8,
    },
    {
        "key": "unworking_website",
        "label": "Non-Working Website / Dead Link",
        "criterion_type": "negative",
        "category_group": "Gate 1 · Health",
        "default_points": -100,
        "is_hard_reject": 1,
        "description": "Domain fails DNS lookup, returns 404/5xx, or redirects to a parked/gambling page.",
        "display_order": 9,
    },
    {
        "key": "unverified_org",
        "label": "Unverifiable Organisation / Scam Flag",
        "criterion_type": "negative",
        "category_group": "Gate 2 · Trust",
        "default_points": -100,
        "is_hard_reject": 1,
        "description": "Lacks verifiable address, team, or organisational identity.",
        "display_order": 10,
    },
    {
        "key": "synthetic_domain",
        "label": "Synthetic / Placeholder Intake Pattern",
        "criterion_type": "negative",
        "category_group": "Gate 2 · Anti-Fake",
        "default_points": -100,
        "is_hard_reject": 1,
        "description": "Matches mass-generated domain patterns such as *-intake-* or sequential IDs.",
        "display_order": 11,
    },
    {
        "key": "unsuitable_platform",
        "label": "Unsuitable Platform Type (Tools / Events / Jobs)",
        "criterion_type": "negative",
        "category_group": "Gate 3 · Fit",
        "default_points": -100,
        "is_hard_reject": 1,
        "description": "Job board, AI tools marketplace, extension store, SaaS review site, or event-only community.",
        "display_order": 12,
    },
    {
        "key": "no_programme_intake",
        "label": "No Registration or Application Mechanism",
        "criterion_type": "negative",
        "category_group": "Gate 3 · Intake",
        "default_points": -100,
        "is_hard_reject": 1,
        "description": "Provides no mechanism to register Eupnea UK Accelerator or receive founder applications.",
        "display_order": 13,
    },
    {
        "key": "blog_news",
        "label": "Blog or News Article Only",
        "criterion_type": "negative",
        "category_group": "Editorial Filter",
        "default_points": -40,
        "is_hard_reject": 1,
        "description": "One-off editorial blog post or press article rather than a permanent directory.",
        "display_order": 14,
    },
    {
        "key": "list_roundup",
        "label": "Listicle / Roundup Article",
        "criterion_type": "negative",
        "category_group": "Editorial Filter",
        "default_points": -35,
        "is_hard_reject": 1,
        "description": "Static 'Top 10 Accelerators' roundup post with no self-listing intake.",
        "display_order": 15,
    },
    {
        "key": "no_way_to_list",
        "label": "No Public Way to List Profile",
        "criterion_type": "negative",
        "category_group": "Gate 4 · Visibility",
        "default_points": -25,
        "is_hard_reject": 1,
        "description": "Private club or invite-only registry with zero public programme pages.",
        "display_order": 16,
    },
    {
        "key": "software_product",
        "label": "Software / Plugin Product Page",
        "criterion_type": "negative",
        "category_group": "Editorial Filter",
        "default_points": -25,
        "is_hard_reject": 1,
        "description": "Single software product page or developer marketplace.",
        "display_order": 17,
    },
    {
        "key": "regional_chamber_penalty",
        "label": "Generic Regional Chamber / Civic Network",
        "criterion_type": "negative",
        "category_group": "Soft Penalty",
        "default_points": -30,
        "is_hard_reject": 0,
        "description": "Regional chamber or council hub lacking dedicated startup accelerator intake.",
        "display_order": 18,
    },
    {
        "key": "broken_form_penalty",
        "label": "Broken Form URL (404 / Error Page)",
        "criterion_type": "negative",
        "category_group": "Soft Penalty · Link Health",
        "default_points": -10,
        "is_hard_reject": 0,
        "description": "Portal homepage resolves live, but the direct Form link returns HTTP 404/error (clickable Form button is automatically disabled).",
        "display_order": 19,
    },
    {
        "key": "wrong_geography",
        "label": "Outside UK / Europe / Global Scope",
        "criterion_type": "negative",
        "category_group": "Soft Penalty",
        "default_points": -15,
        "is_hard_reject": 0,
        "description": "Narrow regional ecosystem strictly outside target UK/European founder footprint.",
        "display_order": 20,
    },
    {
        "key": "lead_farm",
        "label": "Thin / Affiliate Lead-Farm Page",
        "criterion_type": "negative",
        "category_group": "Soft Penalty",
        "default_points": -15,
        "is_hard_reject": 0,
        "description": "Thin affiliate wrapper without organic founder prospecting traffic.",
        "display_order": 21,
    },
]

QUALITY_SCORE_DEFINITIONS: List[Dict[str, str]] = [
    {
        "metric": "Platform Prestige Score (0-100)",
        "formula": "Clamp(0, 100, Sum(Matched Positive Criteria Weights) + Sum(Soft Penalties)); 0 if any Hard-Reject Gate fails",
        "purpose": "Ranks platforms from highest strategic value (Tier 1: 93-100, Tier 2: 80-92, Tier 3: 70-79) down to Deprioritized (<70) and Rejected (0).",
    },
    {
        "metric": "Average Score by Status & Calibration Health",
        "formula": "Mean(score) grouped by Approved, Submitted, In Review, Cohort Perks, and Unqualified / Rejected",
        "purpose": "Validates scoring calibration: Approved/Submitted average scores should significantly exceed In Review and Unqualified averages. Any inversion signals criteria weightings need adjustment.",
    },
    {
        "metric": "Form Link Accuracy (%)",
        "formula": "(Platforms with form_link_ok = 1 / Total Platforms in Scope or Tab) * 100",
        "purpose": "Measures % of platforms whose direct Form URL loads HTTP < 400 (or valid WAF protection) with zero '404', 'error', or 'page not found' responses. Broken forms have clickability disabled.",
    },
    {
        "metric": "Portal Link Accuracy (%)",
        "formula": "(Platforms with portal_link_ok = 1 / Total Platforms in Scope or Tab) * 100",
        "purpose": "Measures % of platforms whose primary homepage Portal URL resolves live without DNS failure, timeout, parked redirect, or HTTP error.",
    },
    {
        "metric": "Dual-Link Integrity (%)",
        "formula": "(Active Platforms with BOTH portal_link_ok = 1 AND form_link_ok = 1 / Active Qualified Platforms) * 100",
        "purpose": "Measures % of active targets ready for immediate end-to-end listing with zero broken Portal or Form links.",
    },
    {
        "metric": "Direct Intake Readiness (%)",
        "formula": "(Tier 1 + Direct Startup Intake + SmartMatch + UK Rankings / Active Qualified Platforms) * 100",
        "purpose": "Tracks how much of the qualified index offers direct application intake, two-sided SmartMatch dealflow, or UK ranking visibility.",
    },
    {
        "metric": "Latest Search Yield & Recency",
        "formula": "Count(platforms where last_search_run_id = latest_run_id); tagged 'Latest Search' + relative Date Added",
        "purpose": "Highlights exact platforms added by the most recent discovery run so reviewers can sort by Date Added and triage newly discovered entries immediately.",
    },
    {
        "metric": "Gate-Pass Yield (%)",
        "formula": "(Qualified Active Platforms / Total Audited Index Rows) * 100",
        "purpose": "Measures overall pipeline signal-to-noise precision after filtering synthetic domains, dead links, SaaS/plugin directories, and isolated cohort perks.",
    },
]


def init_scoring_criteria_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Creates and seeds the scoring_criteria table with default weights if not present."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scoring_criteria (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            criterion_type TEXT NOT NULL,
            category_group TEXT NOT NULL,
            default_points INTEGER NOT NULL,
            current_points INTEGER NOT NULL,
            is_hard_reject INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            display_order INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in CRITERIA_CATALOG:
        c.execute("""
            INSERT INTO scoring_criteria (
                key, label, criterion_type, category_group,
                default_points, current_points, is_hard_reject,
                description, display_order, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                label = excluded.label,
                criterion_type = excluded.criterion_type,
                category_group = excluded.category_group,
                default_points = excluded.default_points,
                is_hard_reject = excluded.is_hard_reject,
                description = excluded.description,
                display_order = excluded.display_order
        """, (
            item["key"], item["label"], item["criterion_type"], item["category_group"],
            item["default_points"], item["default_points"], item["is_hard_reject"],
            item["description"], item["display_order"], now_str,
        ))
    conn.commit()
    conn.close()


def get_scoring_criteria(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Returns all editable scoring criteria (defaults vs current weightings) and quality definitions."""
    rows = []
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scoring_criteria'").fetchone()
        if exists:
            rows = conn.execute("SELECT * FROM scoring_criteria ORDER BY display_order ASC").fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        init_scoring_criteria_db(db_path)
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM scoring_criteria ORDER BY display_order ASC").fetchall()
        conn.close()
    criteria = [dict(r) for r in rows]
    modified_count = sum(1 for item in criteria if item["current_points"] != item["default_points"])
    return {
        "engine_version": ENGINE_NAME,
        "criteria": criteria,
        "positive_criteria": [c for c in criteria if c["criterion_type"] == "positive"],
        "negative_criteria": [c for c in criteria if c["criterion_type"] == "negative"],
        "modified_count": modified_count,
        "thresholds": {
            "tier_1_min": 93,
            "tier_2_min": 80,
            "qualified_min": 70,
        },
        "quality_definitions": QUALITY_SCORE_DEFINITIONS,
    }


def get_active_criteria_weights(db_path: str = DEFAULT_DB_PATH) -> Dict[str, int]:
    """Returns mapping of criterion_key -> current_points."""
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scoring_criteria'").fetchone()
        if not exists:
            conn.close()
            return {c["key"]: c["default_points"] for c in CRITERIA_CATALOG}
        rows = conn.execute("SELECT key, current_points FROM scoring_criteria").fetchall()
        conn.close()
        weights = {c["key"]: c["default_points"] for c in CRITERIA_CATALOG}
        for k, pts in rows:
            weights[k] = int(pts)
        return weights
    except Exception:
        return {c["key"]: c["default_points"] for c in CRITERIA_CATALOG}


def extract_platform_criteria_flags(platform: Dict[str, Any]) -> Dict[str, bool]:
    """Determines active selection criteria booleans from a platform record cleanly."""
    hl = (platform.get("high_level_category") or "").lower()
    tier = (platform.get("tier") or "").lower()
    status = (platform.get("status") or "").lower()
    dom = (platform.get("domain") or "").lower().strip()
    cat = (platform.get("category") or "").lower()
    features = (platform.get("intake_features") or "").lower()
    form_url = (platform.get("form_url") or "").strip()
    form_ok = platform.get("form_link_ok", 1)
    portal_ok = platform.get("portal_link_ok", 1)
    is_sm = bool(platform.get("is_smartmatch"))
    score = int(platform.get("score") or 0)

    if status in ("perk_benefit",):
        return {"unsuitable_platform": True}
    if status in ("unqualified", "not_suitable") and tier == "rejected":
        return {"no_programme_intake": True}

    is_chamber = ("chamber" in hl or "chamber" in cat) and tier == "deprioritized"
    is_single = ghe.GeminiHydrogenEngine.is_single_entity_domain(dom)
    is_reg_hub = bool(platform.get("is_registration_hub")) and not is_single
    flags: Dict[str, bool] = {
        "real_directory": not is_chamber,
        "clear_submit_path": bool(form_url) and bool(form_ok) and (
            is_reg_hub or tier == "tier_1" or is_sm or "direct startup" in hl or "investor" in hl or "uk accelerator" in hl or "submit" in form_url.lower() or "apply" in form_url.lower() or "program" in form_url.lower() or "add" in form_url.lower()
        ),
        "target_audience": (not is_chamber) or ("startup" in features),
        "target_geography": True,
        "structured_fields": bool(features) or is_sm or tier in ("tier_1", "tier_2") or dom in ghe.GEMINI_TIER_1_GROUNDING or dom in ghe.GEMINI_TIER_2_GROUNDING,
        "established_directory": bool(portal_ok) and not is_chamber,
        "tier_1_intake": (not is_single) and (is_reg_hub and (tier == "tier_1" or is_sm or ("direct startup" in hl and score >= 93) or dom in ghe.GEMINI_TIER_1_GROUNDING)),
        "tier_2_discovery": is_single or (tier == "tier_2") or ("uk accelerator" in hl) or ("investor" in hl) or ("ecosystem" in hl) or dom in ghe.GEMINI_TIER_2_GROUNDING,
        "broken_form_penalty": bool(portal_ok) and (form_ok == 0),
        "regional_chamber_penalty": is_chamber,
    }
    return flags


def is_synthetic_domain(domain: str) -> bool:
    is_synth, _ = ghe.GeminiHydrogenEngine.detect_synthetic_pattern(domain, domain)
    return is_synth


def validate_prequalification_gates(platform: Dict[str, Any], verify_network: bool = False, use_llm: bool = False) -> Dict[str, Any]:
    return ghe.GeminiHydrogenEngine.evaluate_prequalification_gates(platform, verify_network=verify_network, use_llm=use_llm)


def evaluate_platform_score(criteria: Dict[str, bool], weights_override: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Evaluates a candidate platform using editable criteria weightings & hard-reject guards."""
    weights = weights_override or get_active_criteria_weights()
    meta_map = {c["key"]: c for c in CRITERIA_CATALOG}

    score = 0
    reasons: List[str] = []
    hard_rejects_triggered: List[str] = []
    has_hard_reject = False
    breakdown: List[Dict[str, Any]] = []

    for key, (default_pts, label) in POSITIVE_CRITERIA.items():
        pts = int(weights.get(key, default_pts))
        if criteria.get(key, False):
            score += pts
            short_lbl = meta_map.get(key, {}).get("label", label)
            reasons.append(f"{short_lbl} ({'+' if pts >= 0 else ''}{pts})")
            breakdown.append({"key": key, "label": short_lbl, "points": pts, "type": "positive"})

    for key, (default_pts, is_hard_reject_flag, label) in NEGATIVE_CRITERIA.items():
        pts = int(weights.get(key, default_pts))
        if criteria.get(key, False):
            score += pts
            short_lbl = meta_map.get(key, {}).get("label", label)
            reasons.append(f"{short_lbl} ({pts})")
            breakdown.append({"key": key, "label": short_lbl, "points": pts, "type": "negative", "hard_reject": bool(is_hard_reject_flag)})
            if is_hard_reject_flag:
                has_hard_reject = True
                hard_rejects_triggered.append(short_lbl)

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
        "breakdown": breakdown,
        "score_reasons_summary": " | ".join(reasons) if reasons else "No criteria matched baseline.",
    }


def recalculate_all_platform_scores(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Re-scores eligible platforms using active customized criteria weightings from scoring_criteria."""
    weights = get_active_criteria_weights(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute("""
        SELECT id, name, domain, category, url, form_url, score, status, tier,
               high_level_category, is_smartmatch, intake_features,
               portal_link_ok, form_link_ok,
               COALESCE(is_registration_hub, 0) AS is_registration_hub
        FROM platforms
        WHERE status NOT IN ('perk_benefit', 'dismissed')
          AND NOT (status IN ('unqualified', 'not_suitable') AND COALESCE(tier, '') = 'rejected')
    """).fetchall()

    updated = 0
    for r in rows:
        d = dict(r)
        dom = (d.get("domain") or "").lower().strip()
        is_single = ghe.GeminiHydrogenEngine.is_single_entity_domain(dom)
        is_hub = bool(d.get("is_registration_hub")) and not is_single
        flags = extract_platform_criteria_flags(d)
        res = evaluate_platform_score(flags, weights_override=weights)
        new_score = res["score"]
        cur_status = d["status"]
        if (is_single or not is_hub) and new_score >= 93:
            new_score = min(90, new_score)

        computed_tier = "tier_1" if (is_hub and new_score >= 93) else ("tier_2" if new_score >= 80 else ("tier_3" if new_score >= 70 else "deprioritized"))

        if d["tier"] == "deprioritized" and cur_status == "unqualified":
            new_tier = computed_tier
            new_status = "in_review" if new_score >= 70 else "unqualified"
        else:
            # Keep approved/submitted workflow status intact while updating weighted score
            new_status = cur_status
            new_tier = computed_tier

        c.execute("""
            UPDATE platforms
            SET score = ?,
                tier = ?,
                status = ?,
                criteria_breakdown = ?
            WHERE id = ?
        """, (new_score, new_tier, new_status, json.dumps(res["breakdown"]), d["id"]))
        updated += 1

    conn.commit()
    conn.close()
    return {"recalculated": updated, "weights": weights}


def update_criteria_weights(weights_update: Dict[str, int], db_path: str = DEFAULT_DB_PATH, recalculate: bool = True) -> Dict[str, Any]:
    """Persists custom user point weightings and optionally recalculates platform scores."""
    init_scoring_criteria_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_map = {item["key"]: item for item in CRITERIA_CATALOG}

    updated_keys = []
    for key, val in weights_update.items():
        if key not in meta_map:
            continue
        pts = int(val)
        pts = max(-100, min(100, pts))
        c.execute("UPDATE scoring_criteria SET current_points = ?, updated_at = ? WHERE key = ?", (pts, now_str, key))
        updated_keys.append(key)

    conn.commit()
    conn.close()

    recalc_res = None
    if recalculate:
        recalc_res = recalculate_all_platform_scores(db_path)

    return {
        "success": True,
        "updated_keys": updated_keys,
        "recalculated": recalc_res["recalculated"] if recalc_res else 0,
        "criteria_state": get_scoring_criteria(db_path),
    }


def reset_criteria_weights(db_path: str = DEFAULT_DB_PATH, recalculate: bool = False) -> Dict[str, Any]:
    """Resets all scoring criteria weights back to factory defaults."""
    init_scoring_criteria_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE scoring_criteria SET current_points = default_points, updated_at = ?", (now_str,))
    conn.commit()
    conn.close()
    recalc_res = recalculate_all_platform_scores(db_path) if recalculate else None
    return {
        "success": True,
        "recalculated": recalc_res["recalculated"] if recalc_res else 0,
        "criteria_state": get_scoring_criteria(db_path),
    }


def score_platform_record(platform: Dict[str, Any], verify_network: bool = False, use_llm: bool = False) -> Dict[str, Any]:
    """Primary platform scoring router strictly backed by Gemini 4 Hydrogen Engine."""
    return ghe.GeminiHydrogenEngine.score_platform(platform, verify_network=verify_network, use_llm=use_llm)


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
        "banner_note": "Minimalist Oxford Navy & Slate Teal dual-tone banner with Eupnea logo mark",
    }
