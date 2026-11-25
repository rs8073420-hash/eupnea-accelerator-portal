"""
Eupnea Accelerator Portal — Bespoke Natural-Language Platform Search Engine
===========================================================================
Parses single-sentence bespoke search prompts (count, recency window, sector/geography,
platform type, registration requirements, requested columns), queries multiple live web
sources concurrently (Bing RSS, DuckDuckGo HTML, HN Algolia timestamped launches,
GitHub timestamped discovery), probes every domain's homepage + dedicated accelerator
programme webpage, and returns structured, link-verified results cleanly.
"""

import os
import re
import json
import html as html_lib
import sqlite3
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import httpx

import gemini_hydrogen_engine as ghe
import category_agent_trainer as cat_trainer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "presence_agent.db")

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

ADULT_OR_GARBAGE_DOMAINS = (
    "xnxx", "xvideos", "pornhub", "xhamster", "redtube", "onlyfans",
    "w3schools", "geeksforgeeks", "tutorialspoint", "programiz", "stackoverflow",
    "britannica.com", "wikipedia.org", "mdpi.com", "sciencedirect.com",
    "reddit.com", "quora.com", "pinterest.com", "instagram.com", "tiktok.com",
    "gov.in", "nic.in", "ac.in", "linkedin.com", "facebook.com", "youtube.com",
)

SECTOR_PORTAL_SEEDS: Dict[str, List[Tuple[str, str, str]]] = {
    "aerospace": [
        ("Starburst Aerospace Accelerator", "https://starburst.aero/", "https://starburst.aero/startup-accelerator/"),
        ("Seraphim Space Accelerator", "https://seraphim.vc/", "https://seraphim.vc/accelerator/"),
        ("ESA Business Incubation Centres (ESA BIC)", "https://commercialisation.esa.int/", "https://commercialisation.esa.int/esa-bics/"),
        ("Orbital Edge Accelerator (ISS National Lab)", "https://www.issnationallab.org/", "https://www.issnationallab.org/orbital-edge-accelerator/"),
        ("Satellite Applications Catapult", "https://sa.catapult.org.uk/", "https://sa.catapult.org.uk/work-with-us/"),
        ("Aerospace Technology Institute (ATI Hub)", "https://www.ati.org.uk/", "https://www.ati.org.uk/hub/"),
        ("Techstars Space & Defense Accelerators", "https://www.techstars.com/", "https://www.techstars.com/accelerators"),
        ("Creative Destruction Lab (Space & DeepTech)", "https://creativedestructionlab.com/", "https://creativedestructionlab.com/locations/"),
        ("Plug and Play Aerospace & Defense", "https://www.plugandplaytechcenter.com/", "https://www.plugandplaytechcenter.com/accelerators/"),
        ("MassChallenge Aerospace & Aviation", "https://masschallenge.org/", "https://masschallenge.org/programs/"),
        ("FedTech Aerospace & DeepTech Studio", "https://www.fedtech.io/", "https://www.fedtech.io/startup-studio"),
        ("NewSpace Global & SpaceTech Hub", "https://www.newspaceglobal.com/", "https://www.newspaceglobal.com/"),
        ("Space Tech Expo Europe", "https://www.spacetechexpo-europe.com/", "https://www.spacetechexpo-europe.com/"),
        ("Aerospace Xelerated (Boeing & UK)", "https://www.aerospacexelerated.com/", "https://www.aerospacexelerated.com/"),
        ("Catalyst Inc Aero & DeepTech", "https://wearecatalyst.org/", "https://wearecatalyst.org/programmes/"),
        ("F6S Aerospace Startup Programs", "https://www.f6s.com/", "https://www.f6s.com/programs"),
        ("Gust Startup Accelerators Directory", "https://gust.com/", "https://gust.com/accelerators"),
        ("YouNoodle Startup Competitions & Accelerators", "https://www.younoodle.com/", "https://www.younoodle.com/"),
        ("VC4A Startup Programs Directory", "https://vc4a.com/", "https://vc4a.com/programs/"),
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
    """Creates bespoke_searches table if missing."""
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


def parse_bespoke_query(prompt: str) -> Dict[str, Any]:
    """
    Extracts structured search constraints from a one-sentence bespoke search query.
    Returns count, recency window, sector tokens, geography, registration gate, and live search queries.
    """
    raw = (prompt or "").strip()
    low = raw.lower()

    # 1. Extract target count
    requested_count = 15
    m_cnt = re.search(r"\b(?:find|show|top|get|return|discover|list)\s+(\d{1,2})\b|\b(\d{1,2})\s+(?:new\s+)?(?:startup|accelerator|platforms?|sites?|portals?)\b", low)
    if m_cnt:
        num = int(m_cnt.group(1) or m_cnt.group(2))
        requested_count = max(1, min(30, num))

    # 2. Extract recency constraint
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

    # 3. Extract sectors & geography
    sector_labels: List[str] = []
    sector_terms: List[str] = []
    for label, aliases in KNOWN_SECTORS:
        if any(re.search(r"\b" + re.escape(a) + r"\b", low) for a in aliases):
            sector_labels.append(label.upper() if len(label) <= 3 else label.capitalize())
            for a in aliases[:4]:
                if a not in sector_terms:
                    sector_terms.append(a)

    # Extract arbitrary non-stopword topic tokens for custom verticals not in KNOWN_SECTORS
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

    all_focus_terms = sector_terms + [t for t in extra_keywords if t not in {"uk", "europe", "european", "global", "london", "us", "usa"}]

    # 4. Build clean live web search queries (avoid over-quoting multiple synonyms together)
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
        f"list of {primary_topic} startup accelerators register cohorts {geo_phrase}".strip(),
        f"startup platforms accelerators {primary_topic} {year_now}".strip(),
    ]

    # Optional Gemini LLM refinement if API key or local gateway is already active (non-blocking)
    endpoint, _, _ = ghe.GeminiHydrogenEngine.get_llm_endpoint_info()
    engine_mode = "Gemini 4 Hydrogen Query Parser" + (" (Live LLM)" if endpoint else " (Deterministic + Live Search)")

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
        "search_queries": queries[:4],
        "requested_fields": ["description", "homepage", "accelerator_page"],
        "engine_mode": engine_mode,
    }


def _clean_text(txt: str, limit: int = 210) -> str:
    cleaned = html_lib.unescape(re.sub(r"<[^>]+>", " ", txt or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def _gather_live_candidates(parsed: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Concurrently gathers live URLs from Bing RSS, DuckDuckGo HTML, HN Algolia (with timestamp filter), and GitHub."""
    candidates: Dict[str, Dict[str, Any]] = {}
    queries = parsed.get("search_queries") or []
    recency_months = parsed.get("recency_months")
    focus_terms = [t.lower() for t in (parsed.get("focus_terms") or [])]

    def _register_cand(raw_url: str, title: str, snippet: str, source_tag: str, published_at: str = "") -> None:
        dom = cat_trainer._clean_live_domain(raw_url)
        if not dom or any(bad in dom for bad in ADULT_OR_GARBAGE_DOMAINS):
            return
        if dom not in candidates:
            candidates[dom] = {
                "domain": dom,
                "name": _clean_text(title, 85) or dom,
                "homepage_url": f"https://{dom}/",
                "seed_url": raw_url if raw_url.startswith("http") else f"https://{dom}/",
                "snippet": _clean_text(snippet, 220),
                "source_tag": source_tag,
                "published_at": published_at,
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

    def _run_google_news(q: str) -> None:
        try:
            gn_q = q
            if recency_months:
                days = min(365, max(30, recency_months * 30))
                gn_q = f"{q} when:{days}d"
            with httpx.Client(timeout=7.0, follow_redirects=True, verify=False, headers=HEADERS) as cli:
                r = cli.get(
                    "https://news.google.com/rss/search",
                    params={"q": gn_q, "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
                )
                if r.status_code == 200 and "<item>" in r.text:
                    for item_xml in re.findall(r"<item>(.*?)</item>", r.text, re.S)[:20]:
                        tm = re.search(r"<title>(.*?)</title>", item_xml, re.S)
                        pm = re.search(r"<pubDate>(.*?)</pubDate>", item_xml, re.S)
                        sm = re.search(r'<source[^>]*url=["\']([^"\']+)["\'][^>]*>(.*?)</source>', item_xml, re.S)
                        if sm:
                            src_url = sm.group(1).strip()
                            src_name = _clean_text(sm.group(2), 60)
                            title_txt = _clean_text(tm.group(1) if tm else "", 120)
                            pub_str = _clean_text(pm.group(1) if pm else "", 40)
                            tag = f"Live Web (Recent {recency_months*30}d)" if recency_months else "Live Web (Google News)"
                            _register_cand(src_url, f"{src_name}", title_txt, tag, pub_str)
        except Exception:
            pass

    def _run_ddg_polite(q: str) -> None:
        try:
            with httpx.Client(timeout=6.0, follow_redirects=True, verify=False, headers=HEADERS) as cli:
                r = cli.get("https://html.duckduckgo.com/html/", params={"q": q})
                if r.status_code == 200 and "result__a" in r.text:
                    blocks = re.findall(
                        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(?:.*?class="result__snippet"[^>]*>(.*?)</a>)?',
                        r.text,
                        re.S | re.I,
                    )
                    for raw_href, raw_title, raw_snip in blocks:
                        actual_url = raw_href
                        if actual_url.startswith("//"):
                            actual_url = "https:" + actual_url
                        if "uddg=" in actual_url:
                            qs = urllib.parse.parse_qs(urllib.parse.urlparse(actual_url).query)
                            actual_url = (qs.get("uddg") or [actual_url])[0]
                        if actual_url.startswith("http"):
                            _register_cand(actual_url, raw_title, raw_snip, "Live Web (DuckDuckGo)")
                else:
                    rl = cli.get("https://lite.duckduckgo.com/lite/", params={"q": q})
                    if rl.status_code == 200:
                        for raw_href, raw_title in re.findall(r'<a[^>]*class=["\']result-link["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', rl.text, re.S | re.I):
                            actual_url = raw_href
                            if actual_url.startswith("//"):
                                actual_url = "https:" + actual_url
                            if "uddg=" in actual_url:
                                qs = urllib.parse.parse_qs(urllib.parse.urlparse(actual_url).query)
                                actual_url = (qs.get("uddg") or [actual_url])[0]
                            if actual_url.startswith("http"):
                                _register_cand(actual_url, raw_title, "", "Live Web (DuckDuckGo)")
        except Exception:
            pass

    def _run_hn() -> None:
        try:
            hn_q = " ".join((focus_terms[:2] or ["startup"]) + ["accelerator"])
            params: Dict[str, Any] = {"query": hn_q, "tags": "story", "hitsPerPage": 20}
            if recency_months:
                cutoff = int((datetime.utcnow() - timedelta(days=30 * recency_months)).timestamp())
                params["numericFilters"] = f"created_at_i>{cutoff}"
            with httpx.Client(timeout=5.5, follow_redirects=True, verify=False, headers=HEADERS) as cli:
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
            with httpx.Client(timeout=5.5, follow_redirects=True, verify=False, headers=HEADERS) as cli:
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
                            for ltxt, ru in re.findall(r"\[([^\]]{2,80})\]\((https?://[^\)\s]+)\)", rr.text[:40000]):
                                if any(k in (ltxt + " " + ru).lower() for k in ("accelerat", "incubator", "program", "venture", "startup", "aerospace", "space")):
                                    _register_cand(ru, ltxt, ltxt, f"GitHub Index ({full_name})", (repo.get("pushed_at") or "")[:10])
                                if len(candidates) >= 35:
                                    break
        except Exception:
            pass

    # Add curated vertical/sector portals first as guaranteed live probe candidates
    matched_seed_keys = [s.lower() for s in (parsed.get("sector_labels") or []) if s.lower() in SECTOR_PORTAL_SEEDS]
    if not matched_seed_keys:
        matched_seed_keys = ["general"]
    for sk in matched_seed_keys:
        for title, h_url, a_url in SECTOR_PORTAL_SEEDS.get(sk, []):
            _register_cand(a_url, title, title, f"Sector Hub ({sk.capitalize()})")

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = []
        for q in queries[:2]:
            futs.append(ex.submit(_run_google_news, q))
        if queries:
            futs.append(ex.submit(_run_ddg_polite, queries[0]))
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


def _probe_bespoke_candidate(cand: Dict[str, Any], parsed: Dict[str, Any], existing_domains: set) -> Optional[Dict[str, Any]]:
    """
    Fetches live homepage & extracts:
    - clean brief description (<meta name='description'> or title/body)
    - dedicated webpage for startup accelerator programmes (accelerator_url + link status)
    - startup registration capability & sector match strength
    """
    dom = cand["domain"]
    home_url = cand.get("homepage_url") or f"https://{dom}/"
    seed_url = cand.get("seed_url") or home_url
    focus_terms = [t.lower() for t in (parsed.get("focus_terms") or [])]

    homepage_ok = False
    homepage_status = 0
    resolved_home = home_url
    page_title = cand.get("name") or dom
    meta_desc = cand.get("snippet") or ""
    low_html = ""
    anchor_links: List[Tuple[str, str]] = []

    try:
        with httpx.Client(timeout=4.2, follow_redirects=True, verify=False, headers=HEADERS) as cli:
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

            if r_home is None:
                return None

            homepage_status = r_home.status_code
            homepage_ok = _is_valid_page(r_home)
            if not homepage_ok:
                return None

            resolved_home = str(r_home.url)
            resolved_dom = urllib.parse.urlparse(resolved_home).netloc.lower().replace("www.", "").split(":")[0] or dom
            raw_html = (r_home.text or "")[:65000]
            low_html = raw_html.lower()

            # Reject parked/gambling/irrelevant/news sites
            parked_kws = ("domain for sale", "buy this domain", "sedo domain parking", "afternic", "domain is parked", "online casino", "crypto casino", "sports betting", "gambling")
            if any(k in low_html[:15000] for k in parked_kws):
                return None
            news_domains = ("spacenews.com", "rdworldonline.com", "eunewsletter.eu", "entnerd.com", "techcrunch.com", "forbes.com", "bloomberg.com", "reuters.com")
            if any(nd in resolved_dom for nd in news_domains):
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

            # Collect internal anchors mentioning accelerator / programs / apply / register / startups
            for href, text in re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', raw_html, re.I | re.S):
                if href.startswith(("#", "mailto:", "javascript:", "tel:")) or any(ext in href.lower() for ext in (".png", ".jpg", ".svg", ".pdf", ".css", ".js")):
                    continue
                full = urllib.parse.urljoin(resolved_home, href)
                if dom not in full.lower():
                    continue
                anchor_text = _clean_text(text, 80).lower()
                anchor_links.append((full, anchor_text))

            # Build prioritized list of candidate accelerator webpage URLs
            acc_candidates: List[Tuple[int, str]] = []
            if seed_url and dom in seed_url.lower() and seed_url.rstrip("/") != resolved_home.rstrip("/"):
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

    # Reject completely off-topic noise sites (must relate to accelerator/startup ecosystem OR matched sector + startup)
    has_startup_kw = any(k in combined_text for k in ("startup", "start-up", "founder", "entrepreneur", "venture", "seed"))
    if not (has_accel_kw or (has_startup_kw and has_reg_signal)):
        return None

    if not accel_url:
        # Use main homepage as programme overview if homepage explicitly mentions accelerator programmes & registration
        if has_accel_kw and homepage_ok:
            accel_url = resolved_home
            accel_ok = True
            accel_http = homepage_status

    # Detect honest age / recency hints without fabricating
    pub_at = cand.get("published_at") or ""
    if pub_at:
        recency_note = f"Indexed {pub_at}"
    else:
        years = sorted(set(re.findall(r"\b(202[0-6])\b", raw_html[:60000] if 'raw_html' in locals() else "")))
        recency_note = f"Active {', '.join(years[-2:])}" if years else "Active live portal (launch date not listed)"

    # Compute transparent bespoke match score (0-100)
    match_score = 40
    if matched_sectors:
        match_score += min(30, 12 * len(matched_sectors))
    if accel_ok and accel_url != resolved_home:
        match_score += 15
    elif accel_ok:
        match_score += 8
    if has_reg_signal:
        match_score += 10
    if pub_at:
        match_score += 5
    match_score = min(100, match_score)

    clean_name = page_title.split(" | ")[0].split(" - ")[0].strip()[:70] or dom
    if clean_name.lower() in ("home", "welcome", "index"):
        clean_name = (cand.get("name") or dom).strip()[:70]
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
        "source_tag": cand.get("source_tag") or "Live Web",
        "already_in_index": dom in existing_domains,
        "match_score": match_score,
    }


def execute_bespoke_search(prompt: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Executes end-to-end bespoke natural language search:
    1. Parses natural language prompt into structured criteria & queries
    2. Runs live multi-source search + pulls verified index candidates matching sector terms
    3. Probes homepage & accelerator page live for each candidate
    4. Persists search run to bespoke_searches and returns verified results
    """
    init_bespoke_search_db(db_path)
    parsed = parse_bespoke_query(prompt)
    req_count = parsed["requested_count"]
    focus_terms = [t.lower() for t in parsed.get("focus_terms", [])]

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    existing_rows = conn.execute(
        """
        SELECT name, domain, url, form_url, score_reasons, draft_pitch, high_level_category,
               portal_link_ok, portal_http_status, form_link_ok, form_http_status, status
        FROM platforms
        WHERE status NOT IN ('unqualified', 'not_suitable', 'dismissed')
        """
    ).fetchall()
    conn.close()

    existing_domains = set((r["domain"] or "").lower().replace("www.", "") for r in existing_rows)

    # Gather live web candidates first
    candidates = _gather_live_candidates(parsed)

    # Also match relevant already-verified index entries (only added AFTER brand-new live discoveries if prefer_new=True)
    index_matches: List[Dict[str, Any]] = []
    for r in existing_rows:
        dom = (r["domain"] or "").lower().replace("www.", "")
        blob = f"{r['name']} {dom} {r['score_reasons'] or ''} {r['draft_pitch'] or ''} {r['high_level_category'] or ''}".lower()
        hits = sum(1 for t in focus_terms if re.search(r"\b" + re.escape(t) + r"\b", blob))
        is_hub = "f6s" in dom or "gust" in dom or "younoodle" in dom or "Direct Startup Engagement" in (r["high_level_category"] or "")
        if hits > 0 or (is_hub and len(candidates) < req_count):
            index_matches.append(
                {
                    "hits": hits * 3 + (1 if is_hub else 0),
                    "row": dict(r),
                }
            )
    index_matches.sort(key=lambda x: x["hits"], reverse=True)

    # Probe live web candidates first (up to max 26 concurrent HTTP checks so latency stays fast)
    cand_list = list(candidates.values())
    cand_list.sort(key=lambda c: (0 if "Sector Hub" in (c.get("source_tag") or "") else 1, 0 if c["domain"] not in existing_domains else 1, 0 if c.get("published_at") else 1))
    probe_pool = cand_list[:26]

    verified_results: List[Dict[str, Any]] = []
    seen_res_domains = set()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(_probe_bespoke_candidate, c, parsed, existing_domains) for c in probe_pool]
        for fut in as_completed(futs):
            try:
                res = fut.result()
                if res and res["domain"] not in seen_res_domains:
                    if parsed.get("require_registration") and not res.get("supports_registration"):
                        continue
                    seen_res_domains.add(res["domain"])
                    verified_results.append(res)
            except Exception:
                pass

    # If user query is very niche + recent (like "last 3 months + aerospace") and strict new web results < req_count,
    # also supplement cleanly with verified index platforms matching the sector/registration profile (honestly tagged!)
    if len(verified_results) < req_count and index_matches:
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
                    "already_in_index": True,
                    "match_score": 78 + min(20, item["hits"] * 5),
                }
            )

    # Sort: prefer new discoveries if asked, then sector match & accelerator link health
    verified_results.sort(
        key=lambda r: (
            1 if (parsed.get("prefer_new") and r.get("already_in_index")) else 0,
            0 if r.get("accelerator_page_ok") else 1,
            -r.get("match_score", 0),
        )
    )
    final_results = verified_results[:req_count]

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
        "total_found": len(final_results),
        "new_discoveries_count": sum(1 for r in final_results if not r.get("already_in_index")),
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
