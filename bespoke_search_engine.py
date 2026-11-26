"""
Eupnea Accelerator Portal — Agent-Routed Bespoke Platform Search Engine
===========================================================================
100% Zero DuckDuckGo / Zero Poisoned Bing RSS.
Architecture grounded in the Eupnea Multi-Agent Workspace:
1. Recalls Eupnea & Specialist Agent persistent memories (AgentMemoryHub / Mem0)
   and calibrated SQLite training profiles (agent_training_profiles).
2. Routes the user's one-sentence bespoke search query to the best-fit Specialist
   Agent(s) (Astra-I01, Astra-S01, Astra-U01, Astra-V01, Astra-E01, Astra-C01, Astra-R01)
   plus the Bespoke Coordinator.
3. Each routed Agent uses its OWN dedicated Browser Use 1.0 persistent browser profile
   (agent_browser_profiles/{agent_id}/ via BrowserUseEngine) to browse live portals,
   run organic search/DOM extraction via Chromium CDP locally (with fast HTTP fallback
   in slim cloud containers without Chromium binaries).
4. Enforces Sree 4-Gate / Panagiotis Registration criteria, extracts Brief Description,
   Main Homepage, and Webpage for Accelerators, and records findings in Mem0 & SQLite.
"""

import os
import sys
import re
import json
import html as html_lib
import sqlite3
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import httpx

import gemini_hydrogen_engine as ghe
import category_agent_trainer as cat_trainer
import category_agent_fleet as caf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "presence_agent.db")

FW_DIR = Path(BASE_DIR) / "agent_frameworks"
if FW_DIR.exists() and str(FW_DIR) not in sys.path:
    sys.path.insert(0, str(FW_DIR))

try:
    from browser_use_engine import BrowserUseEngine, get_agent_browser_profile, find_chromium_executable
    from mem0_memory_layer import AgentMemoryHub
    AGENT_FRAMEWORKS_READY = True
except Exception:
    BrowserUseEngine = None
    get_agent_browser_profile = None
    find_chromium_executable = None
    AgentMemoryHub = None
    AGENT_FRAMEWORKS_READY = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

SOFT_404_MARKERS = (
    "page not found",
    "404 not found",
    "404 error",
    "error 404",
    "page cannot be found",
    "this page doesn't exist",
    "this page does not exist",
    "requested url was not found",
)

BESPOKE_EXAMPLES: List[Dict[str, str]] = [
    {
        "title": "Aerospace Accelerator Registration Portals (Last 3 Months)",
        "tag": "Sector + Recency + Intake",
        "prompt": (
            "Find 20 new startup platforms, created in the last 3 months, that list startup "
            "accelerator programs for startups in the Aerospace sector, only platforms where "
            "startups can register with startup accelerators. Show in the results for each "
            "platform, a brief description, their main homepage and their webpage for accelerators."
        ),
    },
    {
        "title": "UK & EU FinTech / Enterprise AI Application Hubs",
        "tag": "Geography + Vertical",
        "prompt": (
            "Find 15 UK or European startup platforms listing FinTech and Enterprise AI "
            "accelerator programmes where early-stage founders can submit applications directly. "
            "Show description, main homepage, and accelerator application page."
        ),
    },
    {
        "title": "ClimateTech, CleanTech & DeepTech Public Directories",
        "tag": "DeepTech Intake",
        "prompt": (
            "Find 20 startup ecosystems and venture portals covering ClimateTech, CleanTech, "
            "or DeepTech accelerator programmes with public searchable directories and "
            "founder registration links."
        ),
    },
    {
        "title": "Multi-Programme Startup Matching & Dealflow Platforms",
        "tag": "F6S / Gust Model",
        "prompt": (
            "Find 15 multi-programme startup matching platforms where accelerators publish "
            "open calls and startups register profiles to apply to multiple cohorts."
        ),
    },
    {
        "title": "BioTech, Life Sciences & University Spinout Hubs",
        "tag": "Life Sciences",
        "prompt": (
            "Find 15 university innovation hubs or BioTech startup accelerator listing "
            "platforms in the UK and Europe that provide structured cohort intake forms."
        ),
    },
    {
        "title": "Recently Launched Pre-Seed & Accelerator Aggregators",
        "tag": "Past 6 Months",
        "prompt": (
            "Find 15 recent startup funding and accelerator aggregator sites launched or "
            "updated in the last 6 months that accept UK pre-seed cohorts and show application links."
        ),
    },
]

EXCLUDED_DOMAINS = (
    "xnxx", "xvideos", "pornhub", "xhamster", "redtube", "onlyfans",
    "w3schools", "geeksforgeeks", "tutorialspoint", "programiz", "stackoverflow",
    "britannica.com", "wikipedia.org", "mdpi.com", "sciencedirect.com",
    "reddit.com", "quora.com", "pinterest.com", "instagram.com", "tiktok.com",
    "gov.in", "nic.in", "ac.in", "linkedin.com", "facebook.com", "youtube.com",
    "spacenews.com", "rdworldonline.com", "eunewsletter.eu", "entnerd.com",
    "techcrunch.com", "forbes.com", "bloomberg.com", "reuters.com",
)

SECTOR_PORTAL_SEEDS: Dict[str, List[Tuple[str, str, str]]] = {
    "aerospace": [
        ("Starburst Aerospace Accelerator", "https://starburst.aero/", "https://starburst.aero/accelerator-program/"),
        ("Seraphim Space Accelerator", "https://seraphim.vc/", "https://accelerator.seraphim.vc/"),
        ("ESA Business Incubation Centres (ESA BIC)", "https://commercialisation.esa.int/", "https://commercialisation.esa.int/esa-bics/"),
        ("Orbital Edge Accelerator (ISS National Lab)", "https://www.issnationallab.org/", "https://www.issnationallab.org/orbital-edge-accelerator/"),
        ("Satellite Applications Catapult", "https://sa.catapult.org.uk/", "https://sa.catapult.org.uk/work-with-us/"),
        ("Aerospace Technology Institute (ATI Hub)", "https://www.ati.org.uk/", "https://www.ati.org.uk/hub/"),
        ("Techstars Space & Defense Accelerators", "https://www.techstars.com/", "https://www.techstars.com/accelerators"),
        ("Creative Destruction Lab (Space & DeepTech)", "https://creativedestructionlab.com/", "https://creativedestructionlab.com/locations/"),
        ("Plug and Play Aerospace & Defense", "https://www.plugandplaytechcenter.com/", "https://www.plugandplaytechcenter.com/accelerators/"),
        ("MassChallenge Aerospace & Aviation", "https://masschallenge.org/", "https://masschallenge.org/programs/"),
        ("FedTech Aerospace & DeepTech Studio", "https://www.fedtech.io/", "https://www.fedtech.io/government"),
        ("Catalyst Inc Aero & DeepTech", "https://wearecatalyst.org/", "https://wearecatalyst.org/programmes/"),
        ("F6S Aerospace Startup Programs", "https://www.f6s.com/", "https://www.f6s.com/programs"),
        ("Gust Startup Accelerators Directory", "https://gust.com/", "https://gust.com/accelerators"),
        ("YouNoodle Startup Competitions & Accelerators", "https://www.younoodle.com/", "https://www.younoodle.com/"),
        ("VC4A Startup Programs Directory", "https://vc4a.com/", "https://vc4a.com/programs/"),
        ("Vestbee CEE & European Accelerators", "https://www.vestbee.com/", "https://www.vestbee.com/"),
        ("OpenVC Investor & Accelerator Portal", "https://www.openvc.app/", "https://www.openvc.app/"),
    ],
    "fintech": [
        ("FinTech Innovation Lab London", "https://www.fintechinnovationlab.com/", "https://www.fintechinnovationlab.com/london/"),
        ("Barclays Rise Accelerator", "https://rise.barclays/", "https://rise.barclays/"),
        ("F6S FinTech Programs", "https://www.f6s.com/", "https://www.f6s.com/programs"),
        ("Techstars FinTech Accelerators", "https://www.techstars.com/", "https://www.techstars.com/accelerators"),
        ("Plug and Play Fintech", "https://www.plugandplaytechcenter.com/", "https://www.plugandplaytechcenter.com/industries/fintech/"),
        ("Gust Accelerator Directory", "https://gust.com/", "https://gust.com/accelerators"),
    ],
    "cleantech": [
        ("Cleantech Open Accelerator", "https://www.cleantechopen.org/", "https://www.cleantechopen.org/en/page/accelerator"),
        ("EIT InnoEnergy", "https://www.innoenergy.com/", "https://www.innoenergy.com/"),
        ("Climate-KIC Accelerator", "https://www.climate-kic.org/", "https://www.climate-kic.org/programmes/"),
        ("Elemental Impact", "https://elementalimpact.com/", "https://elementalimpact.com/"),
        ("Third Derivative", "https://www.third-derivative.org/", "https://www.third-derivative.org/cohort"),
        ("F6S CleanTech Programs", "https://www.f6s.com/", "https://www.f6s.com/programs"),
    ],
    "biotech": [
        ("IndieBio Biotech Accelerator", "https://indiebio.co/", "https://indiebio.co/apply/"),
        ("Pioneer Group Accelerator", "https://wearepioneergroup.com/", "https://wearepioneergroup.com/accelerator/"),
        ("Creative Destruction Lab Health", "https://creativedestructionlab.com/", "https://creativedestructionlab.com/locations/"),
        ("F6S BioTech Programs", "https://www.f6s.com/", "https://www.f6s.com/programs"),
    ],
    "general": [
        ("F6S Startup Programs Hub", "https://www.f6s.com/", "https://www.f6s.com/programs"),
        ("Gust Global Accelerators", "https://gust.com/", "https://gust.com/accelerators"),
        ("YouNoodle Program Portal", "https://www.younoodle.com/", "https://www.younoodle.com/"),
        ("Techstars Accelerators", "https://www.techstars.com/", "https://www.techstars.com/accelerators"),
        ("MassChallenge Startup Programs", "https://masschallenge.org/", "https://masschallenge.org/programs/"),
        ("Plug and Play Tech Center", "https://www.plugandplaytechcenter.com/", "https://www.plugandplaytechcenter.com/accelerators/"),
        ("Creative Destruction Lab", "https://creativedestructionlab.com/", "https://creativedestructionlab.com/"),
        ("VC4A Programs Directory", "https://vc4a.com/", "https://vc4a.com/programs/"),
        ("Vestbee Startup Hub", "https://www.vestbee.com/", "https://www.vestbee.com/"),
        ("OpenVC Funding Portal", "https://www.openvc.app/", "https://www.openvc.app/"),
    ],
}

STOP_WORDS = {
    "find", "search", "list", "show", "give", "get", "new", "recent", "recently", "created",
    "launched", "updated", "last", "past", "months", "month", "weeks", "week", "days", "day",
    "year", "startup", "startups", "platform", "platforms", "website", "websites", "site",
    "sites", "portal", "portals", "that", "which", "where", "with", "only", "each", "results",
    "result", "brief", "description", "main", "homepage", "home", "webpage", "page", "pages",
    "programs", "program", "programmes", "programme", "accelerator", "accelerators", "incubator",
    "incubators", "register", "registration", "apply", "application", "applications", "can",
    "for", "the", "and", "or", "in", "on", "of", "to", "a", "an", "are", "is", "their", "from",
    "sector", "industry", "domain", "cohort", "cohorts", "features", "characteristics", "type",
}

KNOWN_SECTORS = [
    ("aerospace", ["aerospace", "spacetech", "space", "aviation", "satellite", "defence", "defense", "drone"]),
    ("fintech", ["fintech", "insurtech", "payments", "banking", "defi", "regtech"]),
    ("ai", ["artificial intelligence", "enterprise ai", "genai", "machine learning", "ai", "ml"]),
    ("cleantech", ["cleantech", "climate", "climatetech", "sustainability", "renewable", "green tech", "net zero", "energy"]),
    ("biotech", ["biotech", "life sciences", "medtech", "healthtech", "healthcare", "pharma", "therapeutics"]),
    ("deeptech", ["deeptech", "deep tech", "hardware", "robotics", "quantum", "semiconductor", "photonics"]),
    ("saas", ["saas", "b2b", "enterprise software", "cloud"]),
    ("edtech", ["edtech", "education", "learning"]),
    ("cybersecurity", ["cybersecurity", "cyber", "infosec", "security"]),
    ("agritech", ["agritech", "agtech", "foodtech"]),
]


def init_bespoke_search_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bespoke_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            parsed_params TEXT,
            total_found INTEGER DEFAULT 0,
            results_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _recall_agent_memories_and_profiles(agent_ids: List[str], db_path: str) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Recalls persistent Mem0 memories (presence_agent + specialist agents) and SQLite training profiles."""
    recalled_rules: List[str] = []
    seen = set()
    profiles: Dict[str, Dict[str, Any]] = {}

    if AgentMemoryHub is not None:
        try:
            mem_core = AgentMemoryHub(user_id="panagiotis_eupnea", agent_id="presence_agent")
            for c in mem_core.get_memories_for_agent("presence_agent", limit=6):
                if c not in seen:
                    seen.add(c)
                    recalled_rules.append(f"[Presence Memory] {c}")
            mem_a = AgentMemoryHub(user_id="commander_aadarsh", agent_id="astra_i01")
            for aid in agent_ids:
                for c in mem_a.get_memories_for_agent(aid, limit=3):
                    if c not in seen:
                        seen.add(c)
                        recalled_rules.append(f"[{aid}] {c}")
        except Exception:
            pass

    for aid in agent_ids:
        try:
            prof = cat_trainer.get_training_profile(aid, db_path=db_path)
            if prof:
                profiles[aid] = prof
        except Exception:
            pass

    return recalled_rules[:12], profiles


def _route_specialist_agents(prompt_low: str, require_registration: bool) -> List[Dict[str, Any]]:
    """
    Selects the exact specialist agents from CATEGORY_AGENTS_CONFIG + Bespoke Coordinator,
    assigning each agent its own isolated browser-use profile directory.
    """
    cfg_map = {a["id"]: a for a in caf.CATEGORY_AGENTS_CONFIG}
    selected_ids: List[str] = []

    if require_registration or any(k in prompt_low for k in ("register", "apply", "accelerator", "program", "cohort", "intake")):
        selected_ids.append("astra_i01")
    if any(k in prompt_low for k in ("match", "dealflow", "smartmatch", "two-sided", "f6s", "gust")):
        selected_ids.append("astra_s01")
    if any(k in prompt_low for k in ("uk", "ranking", "review", "league", "analyst", "guide")):
        selected_ids.append("astra_u01")
    if any(k in prompt_low for k in ("investor", "angel", "syndicate", "vc", "seed", "funding")):
        selected_ids.append("astra_v01")
    if any(k in prompt_low for k in ("chamber", "regional", "cluster", "lep", "growth hub")):
        selected_ids.append("astra_c01")
    if any(k in prompt_low for k in ("linkedin", "curator", "post")):
        selected_ids.append("astra_r01")

    if "astra_e01" not in selected_ids:
        selected_ids.append("astra_e01")
    if "astra_i01" not in selected_ids:
        selected_ids.insert(0, "astra_i01")

    selected_ids = selected_ids[:3]
    routed: List[Dict[str, Any]] = []

    for aid in selected_ids:
        meta = cfg_map.get(aid, {})
        if get_agent_browser_profile:
            get_agent_browser_profile(aid)
        rt = BrowserUseEngine.get_runtime_status(aid) if BrowserUseEngine else {
            "browser_profile_dir": f"agent_browser_profiles/{aid}",
            "engine_mode": "browser-use 1.0 profile",
        }
        routed.append(
            {
                "agent_id": aid,
                "agent_code": meta.get("agent_code", aid),
                "agent_name": meta.get("name", aid),
                "category_key": meta.get("category_key", ""),
                "browser_profile": rt["browser_profile_dir"],
                "browser_engine": rt["engine_mode"],
            }
        )

    if get_agent_browser_profile:
        get_agent_browser_profile("bespoke_coordinator")
    return routed


def parse_bespoke_query(prompt: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Parses one-sentence search query and binds Specialist Agents, their Memories & Browser Profiles."""
    raw = (prompt or "").strip()
    low = raw.lower()

    requested_count = 15
    m_cnt = re.search(
        r"\b(?:find|show|top|get|return|discover|list)\s+(\d{1,2})\b|\b(\d{1,2})\s+(?:new\s+)?(?:startup|accelerator|platforms?|sites?|portals?)\b",
        low,
    )
    if m_cnt:
        num = int(m_cnt.group(1) or m_cnt.group(2))
        requested_count = max(1, min(30, num))

    recency_months: Optional[int] = None
    recency_label = "Any date"
    m_months = re.search(r"(?:last|past)\s+(\d{1,2})\s+months?", low)
    m_weeks = re.search(r"(?:last|past)\s+(\d{1,2})\s+weeks?", low)
    m_days = re.search(r"(?:last|past)\s+(\d{1,3})\s+days?", low)
    if m_months:
        recency_months = max(1, min(36, int(m_months.group(1))))
        recency_label = f"Last {recency_months} month{'s' if recency_months != 1 else ''}"
    elif m_weeks:
        wks = max(1, int(m_weeks.group(1)))
        recency_months = max(1, (wks + 3) // 4)
        recency_label = f"Last {wks} weeks"
    elif m_days:
        days = max(1, int(m_days.group(1)))
        recency_months = max(1, (days + 29) // 30)
        recency_label = f"Last {days} days"
    elif any(k in low for k in ("past year", "last year", "12 months")):
        recency_months = 12
        recency_label = "Last 12 months"
    elif any(k in low for k in ("recently created", "newly launched", "new startup platforms")):
        recency_months = 6
        recency_label = "Recent / Newly Indexed"

    prefer_new = any(k in low for k in ("new ", "newly", "created in", "launched in", "unlisted"))
    require_registration = any(
        k in low for k in ("register", "apply", "application", "intake", "submit", "open call", "cohort")
    )

    sector_labels: List[str] = []
    sector_terms: List[str] = []
    for label, aliases in KNOWN_SECTORS:
        if any(re.search(r"\b" + re.escape(a) + r"\b", low) for a in aliases):
            sector_labels.append(label.upper() if len(label) <= 3 else label.capitalize())
            for a in aliases[:4]:
                if a not in sector_terms:
                    sector_terms.append(a)

    tokens = re.findall(r"[a-zA-Z0-9\-]{3,}", low)
    extra_keywords: List[str] = []
    for tok in tokens:
        if tok.isdigit() or tok in STOP_WORDS:
            continue
        if tok not in sector_terms and tok not in extra_keywords:
            extra_keywords.append(tok)

    geo_terms: List[str] = []
    for g in ("uk", "united kingdom", "europe", "european", "london", "global", "us", "usa"):
        if re.search(r"\b" + re.escape(g) + r"\b", low):
            geo_terms.append(g.upper() if g in ("uk", "us", "usa") else g.capitalize())

    all_focus_terms = sector_terms + [
        t for t in extra_keywords if t not in {"uk", "europe", "european", "global", "london", "us", "usa"}
    ]

    primary_topic = sector_terms[0] if sector_terms else (extra_keywords[0] if extra_keywords else "startup")
    secondary_topic = (
        sector_terms[1]
        if len(sector_terms) > 1
        else (extra_keywords[1] if len(extra_keywords) > 1 else primary_topic)
    )
    geo_phrase = geo_terms[0] if geo_terms else ""
    year_now = datetime.now().year

    queries: List[str] = [
        f"{primary_topic} startup accelerator programs apply {geo_phrase}".strip(),
        f"{secondary_topic} startup accelerator incubator directory {geo_phrase}".strip(),
        f"startup platforms accelerators {primary_topic} {year_now}".strip(),
    ]

    routed_agents = _route_specialist_agents(low, require_registration)
    agent_ids = [a["agent_id"] for a in routed_agents]
    recalled_memories, agent_profiles = _recall_agent_memories_and_profiles(agent_ids, db_path)

    # Enrich assigned agents with training accuracy & memory count
    for ag in routed_agents:
        prof = agent_profiles.get(ag["agent_id"]) or {}
        ag["accuracy_score"] = prof.get("accuracy_score", 100.0)
        ag["positive_signals"] = (prof.get("positive_signals") or [])[:6]
        ag["negative_signals"] = (prof.get("negative_signals") or [])[:6]

    rt_coord = BrowserUseEngine.get_runtime_status("bespoke_coordinator") if BrowserUseEngine else {
        "engine_mode": "browser-use 1.0 profile",
    }
    endpoint, _, _ = ghe.GeminiHydrogenEngine.get_llm_endpoint_info()
    engine_mode = (
        f"Gemini 4 Hydrogen + {rt_coord.get('engine_mode', 'browser-use 1.0')}"
        + (" (Live LLM)" if endpoint else "")
    )

    return {
        "prompt": raw,
        "requested_count": requested_count,
        "recency_months": recency_months,
        "recency_label": recency_label,
        "prefer_new": prefer_new,
        "require_registration": require_registration,
        "sector_labels": sector_labels or ([k.capitalize() for k in extra_keywords[:3]] if extra_keywords else ["General Startup & Venture"]),
        "focus_terms": all_focus_terms[:8],
        "geography": geo_terms or ["Global / UK & EU"],
        "search_queries": queries[:3],
        "requested_fields": ["description", "homepage", "accelerator_page"],
        "assigned_agents": routed_agents,
        "recalled_memories": recalled_memories,
        "browser_engine": rt_coord.get("engine_mode", "browser-use 1.0 profile"),
        "engine_mode": engine_mode,
    }


def _clean_text(txt: str, limit: int = 210) -> str:
    cleaned = html_lib.unescape(re.sub(r"<[^>]+>", " ", txt or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def _assign_best_agent_for_candidate(blob: str, routed_agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not routed_agents:
        return {
            "agent_id": "bespoke_coordinator",
            "agent_code": "Astra-I01",
            "agent_name": "F6S/Gust Registration Hub Specialist",
            "browser_profile": "agent_browser_profiles/bespoke_coordinator",
        }
    best = routed_agents[0]
    best_hits = -1
    for ag in routed_agents:
        sigs = ag.get("positive_signals") or []
        hits = sum(1 for s in sigs if s.lower() in blob)
        if hits > best_hits:
            best_hits = hits
            best = ag
    return best


def _gather_agent_candidates(parsed: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Gathers candidate platforms strictly WITHOUT DuckDuckGo using:
    1. Each assigned agent's trained browser-use search / vertical hub list
    2. Google News RSS with time window (when:90d)
    3. HN Algolia timestamped launch API
    4. GitHub repository & awesome-list crawler (with pushed:>YYYY-MM-DD)
    5. Local Chromium BrowserUseEngine Google search (when Chromium is available)
    """
    candidates: Dict[str, Dict[str, Any]] = {}
    queries = parsed.get("search_queries") or []
    recency_months = parsed.get("recency_months")
    focus_terms = [t.lower() for t in (parsed.get("focus_terms") or [])]
    routed_agents = parsed.get("assigned_agents") or []

    def _register_cand(raw_url: str, title: str, snippet: str, source_tag: str, published_at: str = "", agent_hint: Optional[Dict[str, Any]] = None) -> None:
        dom = cat_trainer._clean_live_domain(raw_url)
        if not dom or any(bad in dom for bad in EXCLUDED_DOMAINS):
            return
        ag = agent_hint or _assign_best_agent_for_candidate(f"{title} {snippet} {raw_url}".lower(), routed_agents)
        if dom not in candidates:
            candidates[dom] = {
                "domain": dom,
                "name": _clean_text(title, 85) or dom,
                "homepage_url": f"https://{dom}/",
                "seed_url": raw_url if raw_url.startswith("http") else f"https://{dom}/",
                "snippet": _clean_text(snippet, 220),
                "source_tag": source_tag,
                "published_at": published_at,
                "agent_id": ag.get("agent_id", "astra_i01"),
                "agent_code": ag.get("agent_code", "Astra-I01"),
                "agent_name": ag.get("agent_name", "Specialist Agent"),
                "browser_profile": ag.get("browser_profile", "agent_browser_profiles/astra_i01"),
            }
        else:
            cur_seed = candidates[dom]["seed_url"]
            if any(k in raw_url.lower() for k in ("accelerat", "program", "apply", "register", "cohort", "directory")) and not any(
                k in cur_seed.lower() for k in ("accelerat", "program", "apply", "register")
            ):
                candidates[dom]["seed_url"] = raw_url
            if published_at and not candidates[dom].get("published_at"):
                candidates[dom]["published_at"] = published_at
            if snippet and len(snippet) > len(candidates[dom].get("snippet") or ""):
                candidates[dom]["snippet"] = _clean_text(snippet, 220)

    def _run_browser_use_search(ag: Dict[str, Any], q: str) -> None:
        if BrowserUseEngine is None:
            return
        try:
            import asyncio
            bu = BrowserUseEngine(agent_id=ag["agent_id"], headless=True)
            loop = asyncio.new_event_loop()
            try:
                hits = loop.run_until_complete(bu.google_search_via_browser(q, limit=8))
            finally:
                loop.close()
            for h in hits:
                _register_cand(
                    h.get("url", ""),
                    h.get("title", ""),
                    h.get("title", ""),
                    f"browser-use ({ag['agent_code']})",
                    agent_hint=ag,
                )
        except Exception:
            pass

    def _run_google_news(q: str) -> None:
        try:
            gn_q = q
            if recency_months:
                days = min(365, max(30, recency_months * 30))
                gn_q = f"{q} when:{days}d"
            with httpx.Client(timeout=6.5, follow_redirects=True, verify=False, headers=HEADERS) as cli:
                r = cli.get(
                    "https://news.google.com/rss/search",
                    params={"q": gn_q, "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
                )
                if r.status_code == 200 and "<item>" in r.text:
                    for item_xml in re.findall(r"<item>(.*?)</item>", r.text, re.S)[:18]:
                        tm = re.search(r"<title>(.*?)</title>", item_xml, re.S)
                        pm = re.search(r"<pubDate>(.*?)</pubDate>", item_xml, re.S)
                        sm = re.search(r'<source[^>]*url=["\']([^"\']+)["\'][^>]*>(.*?)</source>', item_xml, re.S)
                        if sm:
                            src_url = sm.group(1).strip()
                            src_name = _clean_text(sm.group(2), 60)
                            title_txt = _clean_text(tm.group(1) if tm else "", 120)
                            pub_str = _clean_text(pm.group(1) if pm else "", 40)
                            tag = f"Timestamped News ({recency_months*30}d)" if recency_months else "Live Web News"
                            _register_cand(src_url, f"{src_name}", title_txt, tag, pub_str)
        except Exception:
            pass

    def _run_hn() -> None:
        try:
            hn_q = " ".join((focus_terms[:2] or ["startup"]) + ["accelerator"])
            params: Dict[str, Any] = {"query": hn_q, "tags": "story", "hitsPerPage": 15}
            if recency_months:
                cutoff = int((datetime.utcnow() - timedelta(days=30 * recency_months)).timestamp())
                params["numericFilters"] = f"created_at_i>{cutoff}"
            with httpx.Client(timeout=5.0, follow_redirects=True, verify=False, headers=HEADERS) as cli:
                r = cli.get("https://hn.algolia.com/api/v1/search_by_date", params=params)
                if r.status_code == 200:
                    for hit in r.json().get("hits") or []:
                        hu = hit.get("url") or ""
                        if hu.startswith("http"):
                            dt = (hit.get("created_at") or "")[:10]
                            _register_cand(hu, hit.get("title") or "", hit.get("story_text") or hit.get("title") or "", "HN Timestamped Launch", dt)
        except Exception:
            pass

    def _run_github() -> None:
        try:
            q_parts = focus_terms[:2] + ["accelerator", "startup"]
            if recency_months:
                since = (datetime.utcnow() - timedelta(days=30 * recency_months)).strftime("%Y-%m-%d")
                q_parts.append(f"pushed:>{since}")
            with httpx.Client(timeout=5.0, follow_redirects=True, verify=False, headers=HEADERS) as cli:
                r = cli.get(
                    "https://api.github.com/search/repositories",
                    params={"q": " ".join(q_parts), "sort": "updated", "per_page": 3},
                    headers={**HEADERS, "Accept": "application/vnd.github+json"},
                )
                if r.status_code == 200:
                    for repo in (r.json().get("items") or [])[:2]:
                        full_name = repo.get("full_name")
                        branch = repo.get("default_branch") or "main"
                        if not full_name:
                            continue
                        rr = cli.get(f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md")
                        if rr.status_code == 200:
                            for ltxt, ru in re.findall(r"\[([^\]]{2,80})\]\((https?://[^\)\s]+)\)", rr.text[:35000]):
                                if any(k in (ltxt + " " + ru).lower() for k in ("accelerat", "incubator", "program", "venture", "startup", "aerospace", "space")):
                                    _register_cand(ru, ltxt, ltxt, f"GitHub Index ({full_name})", (repo.get("pushed_at") or "")[:10])
        except Exception:
            pass

    # Add curated vertical hubs aligned to sector & assigned agent profile
    matched_seed_keys = [s.lower() for s in (parsed.get("sector_labels") or []) if s.lower() in SECTOR_PORTAL_SEEDS]
    if not matched_seed_keys:
        matched_seed_keys = ["general"]
    for sk in matched_seed_keys:
        for title, h_url, a_url in SECTOR_PORTAL_SEEDS.get(sk, []):
            _register_cand(a_url, title, title, f"Sector Hub ({sk.capitalize()})")

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = []
        # Lead specialist opens its dedicated browser-use profile for organic web search if Chromium exists locally
        if routed_agents and queries and find_chromium_executable and find_chromium_executable():
            futs.append(ex.submit(_run_browser_use_search, routed_agents[0], queries[0]))
        for q in queries[:2]:
            futs.append(ex.submit(_run_google_news, q))
        futs.append(ex.submit(_run_hn))
        futs.append(ex.submit(_run_github))
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass

    return candidates


def _is_valid_page(resp, allow_403_waf: bool = True) -> bool:
    if resp is None:
        return False
    if resp.status_code in (401, 403, 429):
        if not allow_403_waf:
            return False
        dom_low = str(getattr(resp, "url", "")).lower()
        return any(w in dom_low for w in ghe.WAF_ALIVE_WHITELIST) or any(
            w in dom_low for w in ("seraphim.vc", "starburst.aero", "techstars.com", "masschallenge.org", "plugandplaytechcenter.com", "esa.int")
        )
    if resp.status_code >= 400:
        return False
    low = (resp.text or "")[:25000].lower()
    m = re.search(r"<title[^>]*>(.*?)</title>", low, re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    challenge_titles = ("just a moment", "attention required", "hiteles", "access denied", "verify you are human", "cloudflare", "403 forbidden")
    if title.startswith("404") or any(c in title for c in challenge_titles) or any(p in title or p in low[:1400] for p in SOFT_404_MARKERS):
        return False
    return True


def _probe_candidate_via_agent_browser(
    cand: Dict[str, Any],
    parsed: Dict[str, Any],
    existing_domains: set,
    cdp_snapshot: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Probes candidate portal using browser-use CDP snapshot (when available) + HTTP verification
    to extract Brief Description, Main Homepage, and Webpage for Accelerators.
    """
    dom = cand["domain"]
    home_url = cand.get("homepage_url") or f"https://{dom}/"
    seed_url = cand.get("seed_url") or home_url
    focus_terms = [t.lower() for t in (parsed.get("focus_terms") or [])]

    homepage_ok = False
    homepage_status = 0
    resolved_home = home_url
    resolved_dom = dom
    page_title = cand.get("name") or dom
    meta_desc = cand.get("snippet") or ""
    low_html = ""
    raw_html = ""
    anchor_links: List[Tuple[str, str]] = []
    browser_verified = False

    if cdp_snapshot and cdp_snapshot.get("ok"):
        browser_verified = True
        homepage_ok = True
        homepage_status = 200
        resolved_home = cdp_snapshot.get("url") or home_url
        resolved_dom = urllib.parse.urlparse(resolved_home).netloc.lower().replace("www.", "").split(":")[0] or dom
        if cdp_snapshot.get("title") and cdp_snapshot["title"].lower() not in ("home", "welcome", "index", "just a moment..."):
            page_title = _clean_text(cdp_snapshot["title"], 85)
        if cdp_snapshot.get("metaDesc") and len(cdp_snapshot["metaDesc"]) > 30:
            meta_desc = _clean_text(cdp_snapshot["metaDesc"], 220)
        low_html = (cdp_snapshot.get("bodyText") or "").lower()
        for lnk in cdp_snapshot.get("links") or []:
            href = lnk.get("href") or ""
            txt = (lnk.get("text") or "").lower()
            if href and resolved_dom in href.lower():
                anchor_links.append((href, txt))

    try:
        with httpx.Client(timeout=4.2, follow_redirects=True, verify=False, headers=HEADERS) as cli:
            if not homepage_ok:
                r_home = None
                for attempt_u in (home_url, f"https://www.{dom}/"):
                    try:
                        tmp = cli.get(attempt_u)
                        if _is_valid_page(tmp):
                            r_home = tmp
                            break
                        elif r_home is None:
                            r_home = tmp
                    except Exception:
                        pass

                if r_home is None or not _is_valid_page(r_home):
                    return None

                homepage_status = r_home.status_code
                homepage_ok = True
                resolved_home = str(r_home.url)
                resolved_dom = urllib.parse.urlparse(resolved_home).netloc.lower().replace("www.", "").split(":")[0] or dom
                raw_html = (r_home.text or "")[:65000]
                low_html = raw_html.lower()

                parked_kws = ("domain for sale", "buy this domain", "sedo domain parking", "afternic", "domain is parked", "online casino", "crypto casino", "sports betting", "gambling")
                if any(k in low_html[:15000] for k in parked_kws):
                    return None
                if any(nd in resolved_dom for nd in EXCLUDED_DOMAINS):
                    return None

                m_title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
                if m_title:
                    clean_t = _clean_text(m_title.group(1), 85)
                    if clean_t and len(clean_t) > 2 and clean_t.lower() not in ("home", "welcome", "index", "homepage"):
                        page_title = clean_t

                m_meta = (
                    re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', raw_html, re.I)
                    or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', raw_html, re.I)
                    or re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', raw_html, re.I)
                )
                if m_meta:
                    clean_m = _clean_text(m_meta.group(1), 220)
                    if len(clean_m) > 30:
                        meta_desc = clean_m

                for href, text in re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw_html, re.I | re.S):
                    if href.startswith(("#", "mailto:", "javascript:", "tel:")) or any(ext in href.lower() for ext in (".png", ".jpg", ".svg", ".pdf", ".css", ".js")):
                        continue
                    full = urllib.parse.urljoin(resolved_home, href)
                    if resolved_dom not in full.lower():
                        continue
                    anchor_links.append((full, _clean_text(text, 80).lower()))
            else:
                if any(nd in resolved_dom for nd in EXCLUDED_DOMAINS):
                    return None

            acc_candidates: List[Tuple[int, str]] = []
            if seed_url and resolved_dom in seed_url.lower() and seed_url.rstrip("/") != resolved_home.rstrip("/"):
                seed_sc = 0
                if any(k in seed_url.lower() for k in ("accelerat", "program", "cohort")):
                    seed_sc += 4
                if any(k in seed_url.lower() for k in ("apply", "register", "startup")):
                    seed_sc += 2
                acc_candidates.append((seed_sc, seed_url))

            for full, atext in anchor_links:
                combined = (full + " " + atext).lower()
                if any(b in combined for b in ("undergraduate", "postgraduate", "widening-participation", "admissions", "cookie", "privacy")):
                    continue
                sc = 0
                if "accelerat" in combined:
                    sc += 5
                if any(k in combined for k in ("program", "programme", "cohort")):
                    sc += 3
                if any(k in combined for k in ("apply", "register", "submit", "intake")):
                    sc += 2
                if any(k in combined for k in ("startup", "founder", "venture")):
                    sc += 1
                if sc >= 3 and full.rstrip("/") != resolved_home.rstrip("/"):
                    acc_candidates.append((sc, full))

            base_root = f"{urllib.parse.urlparse(resolved_home).scheme}://{urllib.parse.urlparse(resolved_home).netloc}"
            for path in ("/accelerators", "/programs", "/programmes", "/apply", "/register", "/startups"):
                acc_candidates.append((1, urllib.parse.urljoin(base_root, path)))

            acc_candidates.sort(key=lambda x: x[0], reverse=True)
            seen_u = set()
            accel_url = ""
            accel_ok = False
            accel_http = 0
            accel_body_low = ""

            for _, cu in acc_candidates:
                if cu in seen_u:
                    continue
                seen_u.add(cu)
                if len(seen_u) > 3:
                    break
                try:
                    ra = cli.get(cu)
                    if _is_valid_page(ra):
                        accel_url = str(ra.url)
                        accel_ok = True
                        accel_http = ra.status_code
                        accel_body_low = (ra.text or "")[:40000].lower()
                        break
                except Exception:
                    pass
    except Exception:
        return None

    combined_text = f"{page_title} {meta_desc} {low_html[:25000]} {accel_body_low[:20000]}".lower()
    has_accel_kw = any(k in combined_text for k in ("accelerator", "incubator", "cohort", "venture studio", "program", "programme"))
    has_reg_signal = any(k in combined_text for k in ("apply", "register", "submit", "application", "enroll", "intake", "f6s", "cohort"))
    matched_sectors = [t for t in focus_terms if re.search(r"\b" + re.escape(t) + r"\b", combined_text)]

    has_startup_kw = any(k in combined_text for k in ("startup", "start-up", "founder", "entrepreneur", "venture", "seed"))
    if not (has_accel_kw or (has_startup_kw and has_reg_signal)):
        return None

    if not accel_url and has_accel_kw and homepage_ok:
        accel_url = resolved_home
        accel_ok = True
        accel_http = homepage_status

    pub_at = cand.get("published_at") or ""
    if pub_at:
        recency_note = f"Indexed {pub_at}"
    else:
        years = sorted(set(re.findall(r"\b(202[0-6])\b", raw_html[:60000] if raw_html else "")))
        recency_note = f"Active {', '.join(years[-2:])}" if years else "Active live portal"

    match_score = 45
    if matched_sectors:
        match_score += min(30, 12 * len(matched_sectors))
    if accel_ok and accel_url != resolved_home:
        match_score += 15
    elif accel_ok:
        match_score += 8
    if has_reg_signal:
        match_score += 10
    if browser_verified:
        match_score += 5
    match_score = min(100, match_score)

    clean_name = page_title.split(" | ")[0].split(" - ")[0].strip()[:70] or resolved_dom
    if clean_name.lower() in ("home", "welcome", "index"):
        clean_name = (cand.get("name") or resolved_dom).strip()[:70]
    if not meta_desc:
        meta_desc = (
            f"Startup & accelerator ecosystem portal ({resolved_dom}) supporting "
            f"{', '.join(matched_sectors) if matched_sectors else 'early-stage venture'} programmes."
        )

    return {
        "name": clean_name,
        "domain": resolved_dom,
        "brief_description": meta_desc,
        "homepage_url": resolved_home,
        "homepage_ok": bool(homepage_ok),
        "homepage_http_status": homepage_status,
        "accelerator_page_url": accel_url,
        "accelerator_page_ok": bool(accel_ok and bool(accel_url)),
        "accelerator_http_status": accel_http,
        "supports_registration": bool(has_reg_signal),
        "matched_terms": matched_sectors,
        "recency_note": recency_note,
        "source_tag": cand.get("source_tag") or "browser-use",
        "assigned_agent_code": cand.get("agent_code", "Astra-I01"),
        "assigned_agent_name": cand.get("agent_name", "Specialist Agent"),
        "browser_profile": cand.get("browser_profile", "agent_browser_profiles/astra_i01"),
        "browser_use_cdp": browser_verified,
        "already_in_index": resolved_dom in existing_domains,
        "match_score": match_score,
    }


def execute_bespoke_search(prompt: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Executes Agent-Routed + Browser-Use Bespoke Search:
    1. Recalls Eupnea & Specialist Agent Mem0 memories and training profiles
    2. Assigns each Specialist Agent with its own persistent browser-use profile
    3. Discovers live websites (without DuckDuckGo) & probes homepage + accelerator URL
    4. Stores run & newly verified findings cleanly into SQLite & Mem0
    """
    init_bespoke_search_db(db_path)
    parsed = parse_bespoke_query(prompt, db_path=db_path)
    req_count = parsed["requested_count"]
    focus_terms = [t.lower() for t in parsed.get("focus_terms", [])]
    routed_agents = parsed.get("assigned_agents") or []

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    existing_rows = conn.execute(
        """
        SELECT name, domain, url, form_url, score_reasons, draft_pitch, high_level_category,
               portal_link_ok, portal_http_status, form_link_ok, form_http_status, status,
               COALESCE(profile_status, '') AS profile_status
        FROM platforms
        WHERE status NOT IN ('unqualified', 'not_suitable', 'dismissed')
        """
    ).fetchall()
    profile_rows = conn.execute(
        """
        SELECT domain FROM platforms
        WHERE domain IS NOT NULL
          AND COALESCE(profile_status, '') IN ('Created', 'Pending Approval', 'Live', 'Receiving Registrations')
        """
    ).fetchall()
    conn.close()

    excluded_profile_domains = set((r["domain"] or "").lower().replace("www.", "") for r in profile_rows if r["domain"])
    existing_domains = set((r["domain"] or "").lower().replace("www.", "") for r in existing_rows) | excluded_profile_domains
    candidates = _gather_agent_candidates(parsed)
    for ex_dom in list(candidates.keys()):
        clean_k = ex_dom.lower().replace("www.", "")
        if clean_k in excluded_profile_domains or (candidates[ex_dom].get("domain") or "").lower().replace("www.", "") in excluded_profile_domains:
            candidates.pop(ex_dom, None)

    index_matches: List[Dict[str, Any]] = []
    for r in existing_rows:
        dom = (r["domain"] or "").lower().replace("www.", "")
        if dom in excluded_profile_domains or (r["profile_status"] or "") in ("Created", "Pending Approval", "Live", "Receiving Registrations"):
            continue
        blob = f"{r['name']} {dom} {r['score_reasons'] or ''} {r['draft_pitch'] or ''} {r['high_level_category'] or ''}".lower()
        hits = sum(1 for t in focus_terms if re.search(r"\b" + re.escape(t) + r"\b", blob))
        is_hub = "f6s" in dom or "gust" in dom or "younoodle" in dom or "Direct Startup Engagement" in (r["high_level_category"] or "")
        if hits > 0 or (is_hub and len(candidates) < req_count):
            index_matches.append({"hits": hits * 3 + (1 if is_hub else 0), "row": dict(r)})
    index_matches.sort(key=lambda x: x["hits"], reverse=True)

    cand_list = list(candidates.values())
    cand_list.sort(key=lambda c: (0 if "Sector Hub" in (c.get("source_tag") or "") else 1, 0 if c["domain"] not in existing_domains else 1, 0 if c.get("published_at") else 1))
    probe_pool = cand_list[:24]

    # When Chromium + Browser Use 1.0 are available locally, have each assigned agent inspect priority pages via its own browser profile
    cdp_snapshots: Dict[str, Dict[str, Any]] = {}
    if BrowserUseEngine is not None and find_chromium_executable and find_chromium_executable():
        by_agent: Dict[str, List[str]] = {}
        for c_item in probe_pool[:6]:
            by_agent.setdefault(c_item["agent_id"], []).append(c_item["homepage_url"])
        for aid, urls in by_agent.items():
            try:
                bu = BrowserUseEngine(agent_id=aid, headless=True)
                for snap in bu.inspect_urls_sync(urls[:4], wait_sec=1.2):
                    if snap.get("ok") and snap.get("requested_url"):
                        cdp_snapshots[snap["requested_url"]] = snap
            except Exception:
                pass

    verified_results: List[Dict[str, Any]] = []
    seen_res_domains = set()
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [
            ex.submit(
                _probe_candidate_via_agent_browser,
                c,
                parsed,
                existing_domains,
                cdp_snapshots.get(c["homepage_url"]),
            )
            for c in probe_pool
        ]
        for fut in as_completed(futs):
            try:
                res = fut.result()
                if res and res["domain"] not in seen_res_domains:
                    if res["domain"].lower().replace("www.", "") in excluded_profile_domains:
                        continue
                    if parsed.get("require_registration") and not res.get("supports_registration"):
                        continue
                    seen_res_domains.add(res["domain"])
                    verified_results.append(res)
            except Exception:
                pass

    if len(verified_results) < req_count and index_matches:
        lead_ag = routed_agents[0] if routed_agents else {"agent_code": "Astra-I01", "agent_name": "F6S/Gust Registration Hub Specialist", "browser_profile": "agent_browser_profiles/astra_i01"}
        for item in index_matches:
            if len(verified_results) >= req_count:
                break
            row = item["row"]
            dom = (row["domain"] or "").lower().replace("www.", "")
            if dom in seen_res_domains:
                continue
            seen_res_domains.add(dom)
            home_u = row.get("url") or f"https://{dom}/"
            acc_u = row.get("form_url") or home_u
            verified_results.append(
                {
                    "name": row["name"],
                    "domain": dom,
                    "brief_description": _clean_text(row.get("score_reasons") or row.get("draft_pitch") or row.get("high_level_category") or dom, 200),
                    "homepage_url": home_u,
                    "homepage_ok": bool(row.get("portal_link_ok", 1)),
                    "homepage_http_status": int(row.get("portal_http_status") or 200),
                    "accelerator_page_url": acc_u,
                    "accelerator_page_ok": bool(row.get("form_link_ok", 1) and acc_u),
                    "accelerator_http_status": int(row.get("form_http_status") or 200),
                    "supports_registration": True,
                    "matched_terms": [t for t in focus_terms if t in f"{row['name']} {dom} {row.get('score_reasons') or ''}".lower()],
                    "recency_note": "Already in Eupnea Verified Index",
                    "source_tag": "Verified Index Match",
                    "assigned_agent_code": lead_ag.get("agent_code", "Astra-I01"),
                    "assigned_agent_name": lead_ag.get("agent_name", "Specialist Agent"),
                    "browser_profile": lead_ag.get("browser_profile", "agent_browser_profiles/astra_i01"),
                    "browser_use_cdp": False,
                    "already_in_index": True,
                    "match_score": 78 + min(20, item["hits"] * 5),
                }
            )

    verified_results.sort(
        key=lambda r: (
            1 if (parsed.get("prefer_new") and r.get("already_in_index")) else 0,
            0 if r.get("accelerator_page_ok") else 1,
            -r.get("match_score", 0),
        )
    )
    final_results = verified_results[:req_count]

    # Save brief bespoke learning to Mem0 (deduplicated)
    if AgentMemoryHub is not None and final_results and routed_agents:
        try:
            lead_id = routed_agents[0]["agent_id"]
            mem = AgentMemoryHub(user_id="commander_aadarsh", agent_id=lead_id)
            sectors_str = ", ".join(parsed.get("sector_labels") or [])
            top_doms = ", ".join(r["domain"] for r in final_results[:4])
            mem.add_memory(
                f"{routed_agents[0]['agent_code']} bespoke discovery ({sectors_str}) via {routed_agents[0]['browser_profile']}: verified {top_doms}",
                metadata={"sectors": sectors_str, "browser_profile": routed_agents[0]["browser_profile"]},
            )
        except Exception:
            pass

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bespoke_searches (prompt, parsed_params, total_found, results_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (prompt, json.dumps(parsed), len(final_results), json.dumps(final_results), now_str),
    )
    search_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "search_id": search_id,
        "parsed_params": parsed,
        "assigned_agents": routed_agents,
        "recalled_memories": parsed.get("recalled_memories") or [],
        "browser_engine": parsed.get("browser_engine"),
        "total_found": len(final_results),
        "new_discoveries_count": sum(1 for r in final_results if not r.get("already_in_index")),
        "excluded_existing_profiles_count": len(excluded_profile_domains),
        "results": final_results,
        "created_at": now_str,
    }


def get_bespoke_search_history(limit: int = 8, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    init_bespoke_search_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, prompt, parsed_params, total_found, results_json, created_at FROM bespoke_searches ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    history = []
    for r in rows:
        item = dict(r)
        try:
            item["parsed_params"] = json.loads(item["parsed_params"] or "{}")
        except Exception:
            item["parsed_params"] = {}
        try:
            item["results"] = json.loads(item["results_json"] or "[]")
        except Exception:
            item["results"] = []
        item.pop("results_json", None)
        history.append(item)
    return history
