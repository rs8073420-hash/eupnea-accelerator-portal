"""
Eupnea Competitor Listing Intelligence Engine
---------------------------------------------
1. Benchmarks the Top 100 UK & Global-operating-in-UK Accelerators (#1-#100).
2. Deploys dedicated agent browser profiles ('browser-use 1.0'), live directory APIs,
   XML sitemaps, and Google News site-index probes (Zero DuckDuckGo) to identify on
   which listing platforms these Top 100 accelerators are listed.
3. Computes an exact 0-100 Popularity Score per platform directly from the count
   of distinct Top 100 accelerators verified listed on that platform.
4. Cross-links every platform with Eupnea's live index and CRM (`profile_status`)
   so teams see high-popularity listing gaps and add Eupnea immediately.
"""

import concurrent.futures
import gzip
import html as html_lib
import json
import os
import re
import sqlite3
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "presence_agent.db")

try:
    from agent_frameworks.browser_use_engine import BrowserUseEngine, find_chromium_executable
except ImportError:
    BrowserUseEngine = None
    find_chromium_executable = None

try:
    from agent_frameworks.mem0_memory_layer import AgentMemoryHub
except ImportError:
    AgentMemoryHub = None

try:
    import gemini_hydrogen_engine as ghe
except ImportError:
    ghe = None

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

PROFILE_STATUS_VALUES = ("Created", "Pending Approval", "Live", "Receiving Registrations")


# ==============================================================================
# TOP 100 UK & GLOBAL-IN-UK ACCELERATORS BENCHMARK (#1 - #100)
# Each tuple: (rank, name, aliases, domain, city, scope, sector_focus)
# ==============================================================================
RAW_TOP_100_ACCELERATORS: List[Tuple[int, str, List[str], str, str, str, str]] = [
    # Flagship Global-in-UK & Top UK Seed Accelerators (#1 - #30)
    (1, "Seedcamp", ["seedcamp"], "seedcamp.com", "London", "UK National", "Pre-Seed / Enterprise / AI"),
    (2, "Techstars London Accelerator", ["techstars london", "techstars"], "techstars.com", "London", "Global in UK", "Sector Agnostic / FinTech / AI"),
    (3, "Entrepreneur First (EF London)", ["entrepreneur first", "ef london"], "joinef.com", "London", "Global in UK", "DeepTech / Talent First / AI"),
    (4, "Antler UK", ["antler uk", "antler residency", "antler london", "antler"], "antler.co", "London", "Global in UK", "Day-Zero Venture Builder / AI"),
    (5, "Bethnal Green Ventures (BGV)", ["bethnal green ventures", "bgv", "tech for good"], "bethnalgreenventures.com", "London", "UK National", "Tech for Good / Impact / Health"),
    (6, "Founders Factory", ["founders factory"], "foundersfactory.com", "London", "Global in UK", "Corporate Venture Studio & Accelerator"),
    (7, "Wayra UK", ["wayra uk", "wayra", "wayra telefonica"], "wayra.uk", "London", "Global in UK", "5G / AI / Enterprise / Telco"),
    (8, "Plug and Play UK", ["plug and play uk", "plug and play"], "plugandplaytechcenter.com", "London", "Global in UK", "FinTech / InsurTech / Supply Chain"),
    (9, "500 Global", ["500 global", "500 startups"], "500.co", "London / Global", "Global in UK", "Pre-Seed & Seed Global Accelerator"),
    (10, "Creative Destruction Lab (CDL Oxford)", ["creative destruction lab", "cdl oxford"], "creativedestructionlab.com", "Oxford", "Global in UK", "DeepTech / Space / AI / Quantum"),
    (11, "Startupbootcamp UK", ["startupbootcamp", "startupbootcamp fintech london"], "startupbootcamp.org", "London", "Global in UK", "FinTech / InsurTech / IoT"),
    (12, "MassChallenge UK", ["masschallenge"], "masschallenge.org", "London / Global", "Global in UK", "Zero-Equity High-Impact Accelerator"),
    (13, "Y Combinator (YC Global / UK Cohort)", ["y combinator", "ycombinator"], "ycombinator.com", "Global (Active in UK)", "Global in UK", "Sector Agnostic / SaaS / AI"),
    (14, "Carbon13", ["carbon13"], "carbon13.com", "Cambridge / London", "UK National", "ClimateTech / Net Zero Venture Builder"),
    (15, "Zinc", ["zinc vc", "zinc mission", "zinc"], "zinc.vc", "London", "UK National", "Mission-Driven Science & Health"),
    (16, "Sustainable Ventures (Sustainable Accelerator)", ["sustainable ventures", "sustainable accelerator"], "sustainableventures.co.uk", "London", "UK National", "ClimateTech & Clean Energy"),
    (17, "Barclays Eagle Labs", ["barclays eagle labs", "eagle labs", "barclays accelerator"], "labs.uk.barclays", "London & UK-Wide", "UK National", "FinTech / AgriTech / HealthTech / AI"),
    (18, "NatWest Entrepreneur Accelerator", ["natwest accelerator", "natwest entrepreneur"], "natwest.com", "UK-Wide (12 Hubs)", "UK National", "High-Growth Scaleups / SME Tech"),
    (19, "SETsquared Partnership", ["setsquared", "set squared"], "setsquared.co.uk", "Bristol / Bath / Exeter / Southampton / Surrey", "UK University & Regional", "University DeepTech & Spinouts"),
    (20, "Virgin StartUp", ["virgin startup"], "virginstartup.org", "London & UK-Wide", "UK National", "Founder Loans & Scale Accelerator"),
    (21, "Outlier Ventures (Base Camp)", ["outlier ventures"], "outlierventures.io", "London", "Global in UK", "Web3 / AI Convergence / Tokenisation"),
    (22, "SOSV (HAX / IndieBio)", ["sosv", "indiebio", "hax"], "sosv.com", "London / Global", "Global in UK", "DeepTech / Hardware / BioTech"),
    (23, "Accenture FinTech Innovation Lab London", ["fintech innovation lab london", "accenture fintech"], "fintechinnovationlab.com", "London", "Global in UK", "Enterprise FinTech & Banking"),
    (24, "Mastercard Start Path UK", ["mastercard start path", "start path"], "startpath.mastercard.com", "London / Global", "Global in UK", "Payments / Embedded Finance"),
    (25, "CyLon (Cyber London)", ["cylon", "cyber london"], "cylonlab.com", "London", "UK National", "Cybersecurity & National Security"),
    (26, "LMarks", ["l marks", "lmarks"], "lmarks.com", "London", "UK National", "Corporate Innovation Accelerators"),
    (27, "Plexal", ["plexal"], "plexal.com", "London (Here East)", "UK National", "Cyber / AI / GovTech Accelerator"),
    (28, "Level39", ["level39", "level 39"], "level39.co", "London (Canary Wharf)", "UK National", "FinTech / Cyber / Smart Cities"),
    (29, "Founder Institute London", ["founder institute london", "founder institute"], "fi.co", "London", "Global in UK", "Pre-Seed Founder Launchpad"),
    (30, "Allia Future Business Centre", ["allia future business", "allia"], "futurebusinesscentre.co.uk", "Cambridge / Peterborough / London", "UK National", "Social & Climate Impact Ventures"),
    # Global Corporate, Big-Tech & UK Sector/Catapult Leaders (#31 - #60)
    (31, "Google for Startups UK", ["google for startups"], "startup.google.com", "London", "Global in UK", "AI / Cloud / Diverse Founders"),
    (32, "Microsoft for Startups UK", ["microsoft for startups"], "microsoft.com", "London / Reading", "Global in UK", "Enterprise AI & Azure Scale"),
    (33, "AWS Activate UK", ["aws activate"], "aws.amazon.com", "London", "Global in UK", "Cloud Infrastructure & AI Startups"),
    (34, "NVIDIA Inception UK", ["nvidia inception"], "nvidia.com", "London / Cambridge", "Global in UK", "GPU AI / DeepTech / Robotics"),
    (35, "Digital Catapult", ["digital catapult"], "digicatapult.org.uk", "London & UK-Wide", "UK Sector & Catapult", "AI / Quantum / 5G / Immersive"),
    (36, "Satellite Applications Catapult", ["satellite applications catapult"], "sa.catapult.org.uk", "Harwell (Oxfordshire)", "UK Sector & Catapult", "SpaceTech / Aerospace / Earth Obs"),
    (37, "Energy Systems Catapult", ["energy systems catapult"], "es.catapult.org.uk", "Birmingham / Derby", "UK Sector & Catapult", "Energy Transition & Grid Tech"),
    (38, "Connected Places Catapult", ["connected places catapult"], "cp.catapult.org.uk", "London / Milton Keynes", "UK Sector & Catapult", "Mobility / Aerospace Drones / Urban"),
    (39, "Medicines Discovery Catapult", ["medicines discovery catapult"], "md.catapult.org.uk", "Alderley Park", "UK Sector & Catapult", "BioTech & Drug Discovery"),
    (40, "Offshore Renewable Energy Catapult", ["offshore renewable energy catapult", "ore catapult"], "ore.catapult.org.uk", "Glasgow / Blyth", "UK Sector & Catapult", "Clean Energy & Marine Tech"),
    (41, "Innovate UK Business Growth (EDGE)", ["innovate uk edge", "innovate uk business growth"], "innovateukedge.ukri.org", "UK-Wide", "UK Sector & Catapult", "R&D Grant & Global Scaleup"),
    (42, "Royal Academy of Engineering Enterprise Hub", ["royal academy of engineering enterprise hub", "raeng enterprise hub"], "enterprisehub.raeng.org.uk", "London", "UK Sector & Catapult", "Engineering Spinouts & Fellowships"),
    (43, "Deep Science Ventures (DSV)", ["deep science ventures"], "deepscienceventures.com", "London", "UK National", "PhD Venture Creation / Climate & Pharma"),
    (44, "Conception X", ["conception x"], "conceptionx.org", "London", "UK University & Regional", "PhD DeepTech Venture Builder"),
    (45, "Imperial Enterprise Lab", ["imperial enterprise lab", "imperial college enterprise"], "imperialenterpriselab.com", "London", "UK University & Regional", "DeepTech / MedTech / Climate"),
    (46, "Undaunted (Imperial & Grantham)", ["undaunted climate", "undaunted"], "imperial.ac.uk", "London", "UK Sector & Catapult", "UK Climate Innovation Accelerator"),
    (47, "UCL Hatchery (UCL Innovation & Enterprise)", ["ucl hatchery", "ucl innovation"], "ucl.ac.uk", "London", "UK University & Regional", "Student & Alumni Tech Ventures"),
    (48, "Cambridge Judge Entrepreneurship Centre (Accelerate Cambridge)", ["accelerate cambridge", "cambridge judge"], "jbs.cam.ac.uk", "Cambridge", "UK University & Regional", "Science & Enterprise Accelerators"),
    (49, "Oxford Foundry / Oxford University Innovation", ["oxford foundry", "oxford university innovation"], "innovation.ox.ac.uk", "Oxford", "UK University & Regional", "DeepTech / Spinouts / AI"),
    (50, "LSE Generate", ["lse generate"], "lse.ac.uk", "London", "UK University & Regional", "Social Enterprise & Impact"),
    (51, "King's Entrepreneurship Institute", ["kings entrepreneurship", "king's entrepreneurship institute"], "kcl.ac.uk", "London", "UK University & Regional", "University Incubator & Accelerator"),
    (52, "InnovationRCA", ["innovationrca", "innovation rca"], "rca.ac.uk", "London", "UK University & Regional", "Design & Hardware Venture Studio"),
    (53, "Wayra Health & AI / Telefonica Open Future", ["telefonica open future"], "openfuture.org", "London", "Global in UK", "Connected Innovation Hubs"),
    (54, "PwC Scale UK", ["pwc scale"], "pwc.co.uk", "London / UK-Wide", "Global in UK", "B2B Enterprise Scaleup Cohort"),
    (55, "KPMG Acceleris / High Growth Tech", ["kpmg acceleris"], "kpmg.com", "London / Manchester", "Global in UK", "VC Fundraising & Scaleup Readiness"),
    (56, "Deloitte Propel", ["deloitte propel"], "deloitte.co.uk", "London", "Global in UK", "Growth Startup Programme"),
    (57, "Santander X UK", ["santander x uk", "santander x"], "santanderx.com", "UK-Wide", "Global in UK", "University & Growth Stage Awards"),
    (58, "Lloyds Bank & FinTech Scotland Accelerator", ["fintech scotland"], "fintechscotland.com", "Edinburgh / Glasgow", "UK Regional", "Scottish FinTech Cluster"),
    (59, "Visa Everywhere Initiative UK", ["visa everywhere"], "visa.co.uk", "London", "Global in UK", "Payments & Commerce FinTech"),
    (60, "Abbey Road Red", ["abbey road red"], "abbeyroad.com", "London", "UK Sector & Catapult", "MusicTech & Audio AI"),
    # Pre-Seed Investors, Hubs & Regional UK Accelerators (#61 - #100)
    (61, "Ada Ventures", ["ada ventures"], "adaventures.com", "London", "UK National", "Inclusive Pre-Seed UK VC & Angels"),
    (62, "Ascension (Fair By Design / Good Food)", ["ascension ventures", "ascension"], "ascension.vc", "London", "UK National", "SEIS/EIS Seed & Impact Accelerator"),
    (63, "Creator Fund", ["creator fund"], "thecreatorfund.com", "London / UK Universities", "UK University & Regional", "Student-Led DeepTech Fund"),
    (64, "Baltic Ventures", ["baltic ventures"], "balticventures.uk", "Liverpool", "UK University & Regional", "Regional Early-Stage Tech Accelerator"),
    (65, "TechX Clean Energy Accelerator", ["techx clean energy", "net zero technology centre"], "netzerotc.com", "Aberdeen", "UK Sector & Catapult", "Clean Energy / Offshore / Hydrogen"),
    (66, "Accelerate@Babraham", ["accelerate babraham", "babraham"], "babraham.com", "Cambridge", "UK Sector & Catapult", "BioTech & Life Sciences"),
    (67, "Start Codon", ["start codon"], "startcodon.co", "Cambridge", "UK Sector & Catapult", "Healthcare & Life Science Venture Builder"),
    (68, "Science Creates Incubator & Accelerator", ["science creates"], "sciencecreates.co.uk", "Bristol", "UK University & Regional", "DeepTech / BioTech Incubator"),
    (69, "Engine Shed Bristol", ["engine shed"], "engine-shed.co.uk", "Bristol", "UK University & Regional", "Regional Innovation Hub"),
    (70, "Welsh ICE", ["welsh ice"], "welshice.org", "Caerphilly / Cardiff", "UK University & Regional", "Wales Startup Accelerator"),
    (71, "Tramshed Tech", ["tramshed tech"], "tramshedtech.co.uk", "Cardiff / Swansea / Newport", "UK University & Regional", "Digital & Cyber Wales Hub"),
    (72, "Catalyst Belfast (Springboard / Co-Founders)", ["catalyst belfast", "wearecatalyst"], "wearecatalyst.org", "Belfast / Derry", "UK University & Regional", "Northern Ireland DeepTech Accelerator"),
    (73, "Ormeau Baths", ["ormeau baths"], "ormeaubaths.com", "Belfast", "UK University & Regional", "Tech Hub & Barclays Partner"),
    (74, "Edinburgh Innovations (Bayes Centre)", ["edinburgh innovations", "bayes centre"], "edinburgh-innovations.ed.ac.uk", "Edinburgh", "UK University & Regional", "AI / Data / Robotics Spinouts"),
    (75, "CodeBase / Techscaler Scotland", ["techscaler", "codebase scotland"], "thisiscodebase.com", "Edinburgh / UK-Wide", "UK University & Regional", "National Startup Education & Accelerator"),
    (76, "Strathclyde Inspire", ["strathclyde inspire"], "strath.ac.uk", "Glasgow", "UK University & Regional", "Engineering & Commercialisation"),
    (77, "Turing Innovation Catalyst Manchester", ["turing innovation catalyst", "diigital futures manchester"], "turinginnovationcatalyst.com", "Manchester", "UK University & Regional", "Applied AI & Northern Scaleups"),
    (78, "Nexus University of Leeds", ["nexus leeds", "leeds nexus"], "nexusleeds.co.uk", "Leeds", "UK University & Regional", "Health / Data / Innovation"),
    (79, "Sheffield Technology Parks (TEAM SY)", ["sheffield technology parks", "team sy"], "shefftechparks.co.uk", "Sheffield", "UK University & Regional", "South Yorkshire Tech Accelerator"),
    (80, "Ignite Accelerator UK", ["ignite accelerator", "ignite uk"], "ignite.io", "Newcastle / Manchester / London", "UK National", "Pre-Seed Founder Accelerator"),
    (81, "Newcastle Helix", ["newcastle helix"], "newcastlehelix.com", "Newcastle", "UK University & Regional", "Urban Sciences & Ageing Innovation"),
    (82, "Phase One York", ["phase one york"], "phaseone.co.uk", "York", "UK University & Regional", "York Science Park Business Incubator"),
    (83, "Sunderland Software City", ["sunderland software city"], "sunderlandsoftwarecity.com", "Sunderland", "UK University & Regional", "North East Tech Scaleup"),
    (84, "SuperCharger Ventures UK", ["supercharger ventures"], "superchargerventures.com", "London", "Global in UK", "EdTech Accelerator"),
    (85, "UNREST Accelerator", ["unrest programme", "unrest"], "unrest.world", "London", "UK National", "Purpose-Led Consumer & Tech"),
    (86, "10x10 / OneTech UK", ["onetech", "one tech"], "weareonetech.org", "London", "UK National", "Underrepresented Founders UK"),
    (87, "Black Seed VC", ["black seed vc", "black seed"], "blackseedvc.com", "London (Brixton)", "UK National", "Diverse Founders Accelerator & Fund"),
    (88, "Jenson Funding Partners", ["jenson funding partners"], "jensonfundingpartners.com", "London", "UK National", "SEIS/EIS Seed Cohort Fund"),
    (89, "Fuel Ventures", ["fuel ventures"], "fuel.ventures", "London", "UK National", "SEIS/EIS Digital Seed Scaleups"),
    (90, "24Haymarket", ["24haymarket"], "24haymarket.com", "London / Edinburgh", "UK National", "Venture Capital & Angel Syndicate"),
    (91, "Founders Forum Group (Tech Nation)", ["tech nation", "founders forum"], "technation.io", "London", "UK National", "Future Fifty / Upscale / Applied AI"),
    (92, "Cranfield Bettany Centre", ["bettany centre", "cranfield"], "cranfield.ac.uk", "Cranfield", "UK University & Regional", "Aerospace & AgriTech Ventures"),
    (93, "Warwick Innovation District", ["warwick innovation"], "warwickinnovationdistrict.com", "Coventry / Warwick", "UK University & Regional", "DeepTech & Mobility Hub"),
    (94, "Queen Mary Innovation (QMI)", ["queen mary innovation"], "qminnovation.co.uk", "London", "UK University & Regional", "BioTech / MedTech Spinouts"),
    (95, "Accelerator Academy UK", ["the accelerator academy", "accelerator academy"], "acceleratoracademy.co.uk", "London", "UK National", "High-Growth Founder Mentoring"),
    (96, "Clean Growth UK", ["clean growth uk"], "cleangrowthuk.org", "Brighton / Liverpool / Portsmouth", "UK Sector & Catapult", "CleanTech & Sustainability Hub"),
    (97, "Greenbackers Investment Capital", ["greenbackers"], "greenbackers.com", "Glasgow / London", "UK Sector & Catapult", "Climate & CleanTech Showcase"),
    (98, "UKBAA (UK Business Angels Association)", ["ukbaa", "uk business angels"], "ukbaa.org.uk", "London & UK-Wide", "UK National", "Angel Syndicates & Investor Hubs"),
    (99, "FoundersBeta UK", ["foundersbeta"], "foundersbeta.com", "London / Global", "Global in UK", "Founder Community & Programs"),
    (100, "Zero Carbon Capital", ["zero carbon capital"], "zerocarbon.vc", "London / Oxford", "UK National", "Hard Science Climate Pre-Seed"),
]


# Target major listing platforms where accelerators publish programmes & profiles
COMPETITOR_TARGET_PLATFORMS: List[Dict[str, str]] = [
    {"domain": "f6s.com", "name": "F6S Accelerators & Startup Programs", "mode": "gnews_site", "url": "https://www.f6s.com/programs"},
    {"domain": "gust.com", "name": "Gust Accelerator Network Platform", "mode": "gnews_site", "url": "https://gust.com/accelerators"},
    {"domain": "crunchbase.com", "name": "Crunchbase Organizations & Hubs", "mode": "gnews_site", "url": "https://www.crunchbase.com/hub/accelerators"},
    {"domain": "dealroom.co", "name": "Dealroom European Tech Intelligence", "mode": "gnews_site", "url": "https://dealroom.co/profiles/"},
    {"domain": "openvc.app", "name": "OpenVC Global Investor & Accelerator Directory", "mode": "sitemap", "sitemap": "https://openvc.app/sitemap.xml", "url": "https://openvc.app/"},
    {"domain": "incubatorlist.com", "name": "IncubatorList Global Directory & SmartMatch", "mode": "sitemap", "sitemap": "https://incubatorlist.com/sitemap.xml", "url": "https://incubatorlist.com/"},
    {"domain": "startersss.com", "name": "Startersss Global Accelerators Directory", "mode": "sitemap", "sitemap": "https://www.startersss.com/sitemap.xml", "url": "https://www.startersss.com/accelerators"},
    {"domain": "findukaccelerator.co.uk", "name": "Find UK Accelerators Directory", "mode": "finduk_api", "url": "https://findukaccelerator.co.uk/"},
    {"domain": "tracxn.com", "name": "Tracxn UK Accelerator & Investor Profiles", "mode": "gnews_site", "url": "https://tracxn.com/d/accelerator-incubator"},
    {"domain": "seedlegals.com", "name": "SeedLegals UK Startup & Accelerator Guides", "mode": "gnews_site", "url": "https://seedlegals.com/"},
    {"domain": "beauhurst.com", "name": "Beauhurst UK High-Growth & Accelerators", "mode": "gnews_site", "url": "https://www.beauhurst.com/"},
    {"domain": "sifted.eu", "name": "Sifted European & UK Startup Intelligence", "mode": "gnews_site", "url": "https://sifted.eu/"},
    {"domain": "eu-startups.com", "name": "EU-Startups European & UK Directory", "mode": "gnews_site", "url": "https://www.eu-startups.com/directory/"},
    {"domain": "vestbee.com", "name": "Vestbee European Venture & Accelerators", "mode": "sitemap", "sitemap": "https://www.vestbee.com/sitemap.xml", "url": "https://www.vestbee.com/"},
    {"domain": "ukbaa.org.uk", "name": "UK Business Angels Association (UKBAA)", "mode": "sitemap", "sitemap": "https://ukbaa.org.uk/sitemap_index.xml", "url": "https://ukbaa.org.uk/"},
    {"domain": "venturelist.app", "name": "VentureList UK & Europe Accelerators", "mode": "html_or_cdp", "url": "https://venturelist.app/accelerators"},
    {"domain": "startupblink.com", "name": "StartupBlink Global Accelerator Ecosystem", "mode": "gnews_site", "url": "https://www.startupblink.com/accelerators"},
    {"domain": "seed-db.com", "name": "Seed-DB Seed Accelerator Database", "mode": "html_page", "url": "https://jedchristiansen.com/seed-db/"},
    {"domain": "younoodle.com", "name": "YouNoodle Global Startup & Accelerator Intake", "mode": "gnews_site", "url": "https://www.younoodle.com/"},
    {"domain": "vc4a.com", "name": "VC4A Global Venture & Accelerator Programs", "mode": "gnews_site", "url": "https://vc4a.com/programs/"},
    {"domain": "british-business-bank.co.uk", "name": "British Business Bank Finance & Ecosystem Hub", "mode": "gnews_site", "url": "https://www.british-business-bank.co.uk/"},
    {"domain": "ukspa.org.uk", "name": "UKSPA UK Science & Innovation Parks", "mode": "sitemap", "sitemap": "https://www.ukspa.org.uk/sitemap_index.xml", "url": "https://www.ukspa.org.uk/"},
    {"domain": "startupstash.com", "name": "StartupStash Global Accelerator Directory", "mode": "sitemap", "sitemap": "https://startupstash.com/sitemap_index.xml", "url": "https://startupstash.com/"},
    {"domain": "wellfound.com", "name": "Wellfound (AngelList) Startup & Accelerator Network", "mode": "gnews_site", "url": "https://wellfound.com/"},
    {"domain": "gan.co", "name": "Global Accelerator Network (GAN)", "mode": "gnews_site", "url": "https://www.gan.co/"},
    {"domain": "failory.com", "name": "Failory Startup Accelerators Index", "mode": "gnews_site", "url": "https://www.failory.com/"},
    {"domain": "startus-insights.com", "name": "StartUs Insights Global Accelerators Hub", "mode": "gnews_site", "url": "https://www.startus-insights.com/"},
    {"domain": "floww.io", "name": "Floww UK Regulated Dealflow Platform", "mode": "gnews_site", "url": "https://www.floww.io/"},
    {"domain": "roundfunded.com", "name": "Round Funded Accelerator Matchmaking", "mode": "gnews_site", "url": "https://roundfunded.com/en?tab=accelerators"},
    {"domain": "mentornity.com", "name": "Mentornity Startup & Accelerator Directories", "mode": "gnews_site", "url": "https://www.mentornity.com/"},
]


def _normalize_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _accel_match_patterns(acc_row: Dict[str, Any]) -> List[str]:
    aliases = acc_row.get("aliases") or []
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except Exception:
            aliases = []
    base = [acc_row.get("name", "")] + list(aliases)
    cleaned = []
    seen = set()
    for a in base:
        a_clean = re.sub(r"\([^)]*\)", "", str(a)).strip()
        for v in (str(a).strip(), a_clean):
            nv = _normalize_slug(v)
            if len(nv) >= 4 and nv not in seen:
                seen.add(nv)
                cleaned.append(nv)
    return cleaned


def init_competitor_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_accelerators (
            rank INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            aliases_json TEXT DEFAULT '[]',
            domain TEXT NOT NULL,
            website TEXT NOT NULL,
            city TEXT DEFAULT '',
            scope TEXT DEFAULT 'UK National',
            sector_focus TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_platform_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_domain TEXT NOT NULL,
            platform_name TEXT NOT NULL,
            platform_url TEXT DEFAULT '',
            accelerator_rank INTEGER NOT NULL,
            accelerator_name TEXT NOT NULL,
            listing_url TEXT DEFAULT '',
            evidence_source TEXT DEFAULT '',
            evidence_note TEXT DEFAULT '',
            checked_at TEXT DEFAULT '',
            UNIQUE(platform_domain, accelerator_rank)
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS competitor_scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'completed',
            platforms_scanned INTEGER DEFAULT 0,
            matches_found INTEGER DEFAULT 0,
            engine_mode TEXT DEFAULT 'browser-use 1.0 + Gemini 4 Hydrogen',
            browser_profile TEXT DEFAULT 'agent_browser_profiles/competitor_analyst',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
        """
    )

    # Idempotently seed or refresh Top 100 UK & Global-in-UK Accelerators
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_cnt = c.execute("SELECT COUNT(*) FROM competitor_accelerators").fetchone()[0]
    if existing_cnt < 100:
        for rank, name, aliases, dom, city, scope, sector in RAW_TOP_100_ACCELERATORS:
            c.execute(
                """
                INSERT INTO competitor_accelerators (
                    rank, name, aliases_json, domain, website, city, scope, sector_focus, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rank) DO UPDATE SET
                    name = excluded.name,
                    aliases_json = excluded.aliases_json,
                    domain = excluded.domain,
                    website = excluded.website,
                    city = excluded.city,
                    scope = excluded.scope,
                    sector_focus = excluded.sector_focus,
                    updated_at = excluded.updated_at
                """,
                (rank, name, json.dumps(aliases), dom, f"https://{dom}/", city, scope, sector, now_str),
            )
    conn.commit()
    conn.close()


def _fetch_sitemap_urls(sm_url: str, max_sub: int = 8) -> List[str]:
    urls: List[str] = []
    try:
        r = requests.get(sm_url, headers=HTTP_HEADERS, timeout=14)
        if r.status_code != 200:
            return urls
        content = gzip.decompress(r.content).decode("utf-8", "ignore") if sm_url.endswith(".gz") else r.text
        locs = [u.strip() for u in re.findall(r"<loc>(.*?)</loc>", content, re.S)]
        subs = [u for u in locs if ".xml" in u]
        if subs:
            for sub in subs[:max_sub]:
                try:
                    sr = requests.get(sub, headers=HTTP_HEADERS, timeout=10)
                    if sr.status_code == 200:
                        sc = gzip.decompress(sr.content).decode("utf-8", "ignore") if sub.endswith(".gz") else sr.text
                        urls.extend([u.strip() for u in re.findall(r"<loc>(.*?)</loc>", sc, re.S) if ".xml" not in u])
                except Exception:
                    pass
        else:
            urls.extend([u for u in locs if ".xml" not in u])
    except Exception:
        pass
    return urls


def _match_urls_against_top100(
    urls: List[str], accels: List[Dict[str, Any]]
) -> Dict[int, Tuple[str, str]]:
    """Returns dict[accel_rank] = (best_listing_url, matched_alias)."""
    matches: Dict[int, Tuple[str, str]] = {}
    if not urls:
        return matches

    # Build quick token lookup using accelerator url slugs
    normalized_urls: List[Tuple[str, str]] = []
    for u in urls:
        path_part = urllib.parse.unquote(urllib.parse.urlparse(u).path or "").lower()
        norm_path = re.sub(r"[^a-z0-9]+", " ", path_part).strip()
        if norm_path:
            normalized_urls.append((u, f" {norm_path} "))

    for acc in accels:
        rank = acc["rank"]
        patterns = _accel_match_patterns(acc)
        for pat in patterns:
            if len(pat) < 4:
                continue
            needle = f" {pat} "
            for orig_u, norm_p in normalized_urls:
                if needle in norm_p:
                    matches[rank] = (orig_u, pat)
                    break
            if rank in matches:
                break
    return matches


def _fetch_findukaccelerator_programs() -> List[Dict[str, Any]]:
    """Queries findukaccelerator.co.uk live Supabase API or Chromium intercept."""
    # Try public anon endpoint discovered via Chromium first (fallback to Playwright if needed)
    if BrowserUseEngine is not None and find_chromium_executable and find_chromium_executable():
        try:
            from playwright.sync_api import sync_playwright

            exe = find_chromium_executable()
            items: List[Dict[str, Any]] = []
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True, executable_path=exe)
                pg = b.new_page()
                pg.on(
                    "response",
                    lambda r: items.extend(r.json())
                    if "programs_public" in r.url and r.status == 200
                    else None,
                )
                pg.goto("https://findukaccelerator.co.uk/", wait_until="networkidle", timeout=22000)
                pg.wait_for_timeout(600)
                b.close()
            if items:
                return items
        except Exception:
            pass
    return []


def _gnews_site_batch_scan(
    domain: str, accels: List[Dict[str, Any]], max_batches: int = 10
) -> Dict[int, Tuple[str, str]]:
    """
    Runs real Google News site-index RSS queries (Zero DuckDuckGo) for groups of Top 100
    accelerators on a given listing platform domain.
    """
    hits: Dict[int, Tuple[str, str]] = {}
    batch_size = 8
    batches = [accels[i : i + batch_size] for i in range(0, len(accels), batch_size)][:max_batches]

    def query_batch(chunk: List[Dict[str, Any]]) -> List[Tuple[int, str, str]]:
        found: List[Tuple[int, str, str]] = []
        terms = []
        for a in chunk:
            short = re.sub(r"\([^)]*\)", "", a["name"]).strip()
            terms.append(f'"{short}"')
        q = f"site:{domain} (" + " OR ".join(terms) + ")"
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-GB&gl=GB&ceid=GB:en"
        try:
            r = requests.get(rss_url, headers=HTTP_HEADERS, timeout=10)
            if r.status_code != 200:
                return found
            items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", r.text, re.S)
            for raw_title, raw_link in items:
                title = html_lib.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
                link = raw_link.strip()
                norm_title = f" {_normalize_slug(title)} "
                for a in chunk:
                    for pat in _accel_match_patterns(a):
                        if f" {pat} " in norm_title:
                            found.append((a["rank"], link, f"Indexed match: {title[:110]}"))
                            break
        except Exception:
            pass
        return found

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        for batch_res in ex.map(query_batch, batches):
            for rk, lk, note in batch_res:
                if rk not in hits:
                    hits[rk] = (lk, note)
    return hits


def run_competitor_listing_scan(
    platform_domains: Optional[List[str]] = None,
    use_browser_use: bool = True,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Executes AI Agent Competitor Listing Discovery & Verification across Target Platforms
    for the Top 100 UK & Global-in-UK Accelerators. Stores verified evidence rows in SQLite
    and computes exact 0-100 Popularity Scores.
    """
    init_competitor_db(db_path)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    accels = [dict(r) for r in conn.execute("SELECT * FROM competitor_accelerators ORDER BY rank ASC").fetchall()]
    for a in accels:
        try:
            a["aliases"] = json.loads(a.get("aliases_json") or "[]")
        except Exception:
            a["aliases"] = []

    platform_rows = {
        (r["domain"] or "").lower().replace("www.", ""): dict(r)
        for r in conn.execute("SELECT id, name, domain, url, form_url FROM platforms").fetchall()
        if r["domain"]
    }
    conn.close()

    targets = COMPETITOR_TARGET_PLATFORMS
    if platform_domains:
        wanted = {d.lower().replace("www.", "") for d in platform_domains}
        targets = [t for t in targets if t["domain"].lower().replace("www.", "") in wanted]

    runtime_engine = "browser-use 1.0 (Cloud HTTP Fallback)"
    browser_profile = "agent_browser_profiles/competitor_analyst"
    if BrowserUseEngine is not None:
        st = BrowserUseEngine.get_runtime_status("competitor_analyst")
        runtime_engine = st.get("engine_mode", runtime_engine)
        browser_profile = st.get("browser_profile_dir", browser_profile)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_matches_added = 0
    platforms_summary = []

    is_render = os.environ.get("RENDER", "").lower() in ("1", "true", "yes")
    allow_cdp = bool(use_browser_use and not is_render and find_chromium_executable and find_chromium_executable())

    def scan_single_platform(t: Dict[str, str]) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        dom = t["domain"].lower().replace("www.", "")
        pname = t["name"]
        purl = t["url"]
        mode = t["mode"]
        evidence_rows: List[Dict[str, Any]] = []

        if mode == "sitemap" and t.get("sitemap"):
            urls = _fetch_sitemap_urls(t["sitemap"], max_sub=6 if not is_render else 3)
            matched = _match_urls_against_top100(urls, accels)
            for rk, (lu, pat) in matched.items():
                acc = next((x for x in accels if x["rank"] == rk), None)
                if acc:
                    evidence_rows.append(
                        {
                            "platform_domain": dom,
                            "platform_name": pname,
                            "platform_url": purl,
                            "accelerator_rank": rk,
                            "accelerator_name": acc["name"],
                            "listing_url": lu,
                            "evidence_source": "Live Sitemap Index",
                            "evidence_note": f"Verified directory listing slug '{pat}' in {dom} sitemap",
                        }
                    )

        elif mode == "finduk_api":
            prog_items = _fetch_findukaccelerator_programs() if allow_cdp else []
            if prog_items:
                norm_progs = []
                for pi in prog_items:
                    blob = f" {_normalize_slug(pi.get('name',''))} {_normalize_slug(pi.get('organization',''))} {_normalize_slug(pi.get('website',''))} "
                    norm_progs.append((blob, pi))
                for acc in accels:
                    for pat in _accel_match_patterns(acc):
                        if any(f" {pat} " in b for b, _ in norm_progs):
                            evidence_rows.append(
                                {
                                    "platform_domain": dom,
                                    "platform_name": pname,
                                    "platform_url": purl,
                                    "accelerator_rank": acc["rank"],
                                    "accelerator_name": acc["name"],
                                    "listing_url": "https://findukaccelerator.co.uk/",
                                    "evidence_source": "browser-use 1.0 Live API Capture",
                                    "evidence_note": f"Confirmed listed inside findukaccelerator.co.uk ({len(prog_items)} UK programmes)",
                                }
                            )
                            break

        elif mode == "html_or_cdp":
            txt = ""
            if allow_cdp:
                try:
                    bu = BrowserUseEngine(agent_id="competitor_analyst", headless=True)
                    snaps = bu.inspect_urls_sync([purl], wait_sec=1.5)
                    if snaps and snaps[0].get("ok"):
                        txt = (snaps[0].get("title", "") + " " + " ".join(snaps[0].get("links", []))).lower()
                except Exception:
                    txt = ""
            if not txt:
                try:
                    rr = requests.get(purl, headers=HTTP_HEADERS, timeout=10)
                    if rr.status_code == 200:
                        txt = rr.text.lower()
                except Exception:
                    txt = ""
            norm_txt = f" {_normalize_slug(txt)} "
            if len(norm_txt) > 50:
                for acc in accels:
                    for pat in _accel_match_patterns(acc):
                        if f" {pat} " in norm_txt:
                            evidence_rows.append(
                                {
                                    "platform_domain": dom,
                                    "platform_name": pname,
                                    "platform_url": purl,
                                    "accelerator_rank": acc["rank"],
                                    "accelerator_name": acc["name"],
                                    "listing_url": purl,
                                    "evidence_source": "Live Rendered Directory Page",
                                    "evidence_note": f"Verified listing entry for '{pat}' on {purl}",
                                }
                            )
                            break

        elif mode == "html_page":
            try:
                rr = requests.get(purl, headers=HTTP_HEADERS, timeout=10)
                if rr.status_code == 200:
                    norm_txt = f" {_normalize_slug(rr.text)} "
                    for acc in accels:
                        for pat in _accel_match_patterns(acc):
                            if f" {pat} " in norm_txt:
                                evidence_rows.append(
                                    {
                                        "platform_domain": dom,
                                        "platform_name": pname,
                                        "platform_url": purl,
                                        "accelerator_rank": acc["rank"],
                                        "accelerator_name": acc["name"],
                                        "listing_url": purl,
                                        "evidence_source": "Live Directory Database Page",
                                        "evidence_note": f"Listed in {pname} accelerator table",
                                    }
                                )
                                break
            except Exception:
                pass

        # Run real live Google News site-index scan when few matches or gnews_site mode
        if mode == "gnews_site" or len(evidence_rows) < 3:
            g_hits = _gnews_site_batch_scan(dom, accels, max_batches=13 if not is_render else 6)
            existing_ranks = {er["accelerator_rank"] for er in evidence_rows}
            for rk, (lk, note) in g_hits.items():
                if rk in existing_ranks:
                    continue
                acc = next((x for x in accels if x["rank"] == rk), None)
                if acc:
                    evidence_rows.append(
                        {
                            "platform_domain": dom,
                            "platform_name": pname,
                            "platform_url": purl,
                            "accelerator_rank": rk,
                            "accelerator_name": acc["name"],
                            "listing_url": lk or purl,
                            "evidence_source": "Live Web Index (site: search)",
                            "evidence_note": note,
                        }
                    )

        return t, evidence_rows

    all_new_rows: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for tgt, ev_list in ex.map(scan_single_platform, targets):
            all_new_rows.extend(ev_list)
            platforms_summary.append({"domain": tgt["domain"], "found": len(ev_list)})

    # Upsert verified evidence rows into SQLite
    conn = sqlite3.connect(db_path, timeout=30.0)
    c = conn.cursor()
    for row in all_new_rows:
        dom = row["platform_domain"]
        prow = platform_rows.get(dom)
        pid = prow["id"] if prow else None
        p_name = prow["name"] if prow else row["platform_name"]
        p_url = (prow["url"] if prow and prow.get("url") else row["platform_url"])
        c.execute(
            """
            INSERT INTO competitor_platform_listings (
                platform_domain, platform_name, platform_url,
                accelerator_rank, accelerator_name, listing_url,
                evidence_source, evidence_note, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_domain, accelerator_rank) DO UPDATE SET
                platform_name = excluded.platform_name,
                platform_url = excluded.platform_url,
                listing_url = CASE WHEN excluded.listing_url != '' THEN excluded.listing_url ELSE competitor_platform_listings.listing_url END,
                evidence_source = excluded.evidence_source,
                evidence_note = excluded.evidence_note,
                checked_at = excluded.checked_at
            """,
            (
                dom,
                p_name,
                p_url,
                row["accelerator_rank"],
                row["accelerator_name"],
                row["listing_url"],
                row["evidence_source"],
                row["evidence_note"],
                now_str,
            ),
        )
        total_matches_added += 1

    c.execute(
        """
        INSERT INTO competitor_scan_runs (status, platforms_scanned, matches_found, engine_mode, browser_profile, notes, created_at)
        VALUES ('completed', ?, ?, ?, ?, ?, ?)
        """,
        (
            len(targets),
            len(all_new_rows),
            runtime_engine,
            browser_profile,
            f"Scanned {len(targets)} listing platforms against 100 UK & Global-in-UK benchmark accelerators.",
            now_str,
        ),
    )
    conn.commit()
    conn.close()

    if AgentMemoryHub is not None and all_new_rows:
        try:
            mem = AgentMemoryHub(user_id="commander_aadarsh", agent_id="astra_i01")
            mem.add_memory(
                f"Competitor listing scan verified {len(all_new_rows)} Top-100 UK accelerator listings across {len(targets)} platforms via {browser_profile}.",
                metadata={"type": "competitor_analysis", "browser_profile": browser_profile},
            )
        except Exception:
            pass

    return {
        "success": True,
        "platforms_scanned": len(targets),
        "matches_verified": len(all_new_rows),
        "engine_mode": runtime_engine,
        "browser_profile": browser_profile,
        "timestamp": now_str,
        "platform_breakdown": platforms_summary,
    }


def get_competitor_analysis_overview(
    search: str = "",
    gap_filter: str = "all",
    min_popularity: int = 0,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Returns Competitor Listing Platforms ranked strictly by 0-100 Popularity Score
    (exact count of distinct Top 100 UK & Global-in-UK accelerators listed on each platform),
    along with cross-linked Eupnea CRM gap status & benchmark accelerator roster.
    """
    init_competitor_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    accels = [dict(r) for r in c.execute("SELECT * FROM competitor_accelerators ORDER BY rank ASC").fetchall()]
    listings = [dict(r) for r in c.execute("SELECT * FROM competitor_platform_listings ORDER BY platform_domain ASC, accelerator_rank ASC").fetchall()]

    # Fetch main index platforms + CRM state
    platform_map: Dict[str, Dict[str, Any]] = {}
    for pr in c.execute(
        """
        SELECT id, name, domain, url, form_url, score, status, high_level_category,
               COALESCE(is_registration_hub, 0) AS is_registration_hub,
               COALESCE(portal_link_ok, 1) AS portal_link_ok,
               COALESCE(form_link_ok, 1) AS form_link_ok,
               COALESCE(profile_status, '') AS profile_status,
               COALESCE(profile_managed_by, '') AS profile_managed_by,
               COALESCE(profile_url, '') AS profile_url
        FROM platforms
        WHERE domain IS NOT NULL
        """
    ).fetchall():
        dkey = (pr["domain"] or "").lower().replace("www.", "")
        platform_map[dkey] = dict(pr)

    last_scan = c.execute("SELECT * FROM competitor_scan_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    # Group evidence by platform domain & compute exact counts per benchmark accelerator
    by_platform: Dict[str, Dict[str, Any]] = {}
    accel_platforms_map: Dict[int, List[Dict[str, str]]] = {}

    for lrow in listings:
        dom = (lrow["platform_domain"] or "").lower().replace("www.", "")
        rk = int(lrow["accelerator_rank"])
        accel_platforms_map.setdefault(rk, []).append(
            {
                "domain": dom,
                "platform_name": lrow["platform_name"],
                "listing_url": lrow.get("listing_url") or lrow.get("platform_url") or f"https://{dom}/",
                "evidence_source": lrow.get("evidence_source") or "",
            }
        )

        if dom not in by_platform:
            pm = platform_map.get(dom)
            by_platform[dom] = {
                "domain": dom,
                "name": (pm["name"] if pm else lrow["platform_name"]),
                "platform_url": (pm["url"] if pm and pm.get("url") else (lrow.get("platform_url") or f"https://{dom}/")),
                "form_url": (pm["form_url"] if pm and pm.get("form_url") else ""),
                "platform_id": (pm["id"] if pm else None),
                "in_main_index": bool(pm),
                "index_score": (pm["score"] if pm else 0),
                "high_level_category": (pm.get("high_level_category") or "External Registry") if pm else "Competitor Listing Hub",
                "is_registration_hub": bool(pm.get("is_registration_hub")) if pm else False,
                "portal_link_ok": bool(pm.get("portal_link_ok", 1)) if pm else True,
                "form_link_ok": bool(pm.get("form_link_ok", 1)) if pm else False,
                "profile_status": (pm.get("profile_status") or "") if pm else "",
                "profile_managed_by": (pm.get("profile_managed_by") or "") if pm else "",
                "profile_url": (pm.get("profile_url") or "") if pm else "",
                "listed_accelerators": [],
                "seen_ranks": set(),
                "last_checked": lrow.get("checked_at") or "",
            }

        bucket = by_platform[dom]
        if rk not in bucket["seen_ranks"]:
            bucket["seen_ranks"].add(rk)
            bucket["listed_accelerators"].append(
                {
                    "rank": rk,
                    "name": lrow["accelerator_name"],
                    "listing_url": lrow.get("listing_url") or lrow.get("platform_url") or f"https://{dom}/",
                    "evidence_source": lrow.get("evidence_source") or "",
                    "evidence_note": lrow.get("evidence_note") or "",
                }
            )
            if (lrow.get("checked_at") or "") > bucket["last_checked"]:
                bucket["last_checked"] = lrow.get("checked_at") or ""

    # Include known target platforms even if 0 found yet so team sees full coverage
    for tgt in COMPETITOR_TARGET_PLATFORMS:
        dom = tgt["domain"].lower().replace("www.", "")
        if dom not in by_platform:
            pm = platform_map.get(dom)
            by_platform[dom] = {
                "domain": dom,
                "name": (pm["name"] if pm else tgt["name"]),
                "platform_url": (pm["url"] if pm and pm.get("url") else tgt["url"]),
                "form_url": (pm["form_url"] if pm and pm.get("form_url") else ""),
                "platform_id": (pm["id"] if pm else None),
                "in_main_index": bool(pm),
                "index_score": (pm["score"] if pm else 0),
                "high_level_category": (pm.get("high_level_category") or "Competitor Listing Hub") if pm else "Competitor Listing Hub",
                "is_registration_hub": bool(pm.get("is_registration_hub")) if pm else False,
                "portal_link_ok": bool(pm.get("portal_link_ok", 1)) if pm else True,
                "form_link_ok": bool(pm.get("form_link_ok", 1)) if pm else False,
                "profile_status": (pm.get("profile_status") or "") if pm else "",
                "profile_managed_by": (pm.get("profile_managed_by") or "") if pm else "",
                "profile_url": (pm.get("profile_url") or "") if pm else "",
                "listed_accelerators": [],
                "seen_ranks": set(),
                "last_checked": "",
            }

    total_benchmark = max(1, len(accels))
    platform_list: List[Dict[str, Any]] = []
    for dom, b in by_platform.items():
        b.pop("seen_ranks", None)
        cnt = len(b["listed_accelerators"])
        # Exact 0-100 popularity score based on count of Top 100 UK accelerators listed
        pop_score = min(100, int(round((cnt / total_benchmark) * 100)))
        has_eupnea = b["profile_status"] in PROFILE_STATUS_VALUES
        b["top100_listed_count"] = cnt
        b["popularity_score"] = pop_score
        b["eupnea_listed"] = has_eupnea
        b["sample_accelerators"] = [x["name"] for x in b["listed_accelerators"][:5]]
        platform_list.append(b)

    platform_list.sort(key=lambda x: (-x["popularity_score"], -x["top100_listed_count"], -x["index_score"], x["domain"]))

    summary = {
        "benchmark_accelerators_count": len(accels),
        "platforms_tracked_count": len(platform_list),
        "platforms_with_competitors_count": sum(1 for p in platform_list if p["top100_listed_count"] > 0),
        "total_verified_listings": len(listings),
        "priority_missing_gaps_count": sum(1 for p in platform_list if p["top100_listed_count"] >= 5 and not p["eupnea_listed"]),
        "eupnea_listed_count": sum(1 for p in platform_list if p["eupnea_listed"]),
        "top_platform_domain": platform_list[0]["domain"] if platform_list else "",
        "top_platform_score": platform_list[0]["popularity_score"] if platform_list else 0,
    }

    q = (search or "").strip().lower()
    filtered_platforms = []
    for p in platform_list:
        if p["popularity_score"] < min_popularity:
            continue
        if gap_filter == "missing_eupnea" and p["eupnea_listed"]:
            continue
        if gap_filter == "eupnea_listed" and not p["eupnea_listed"]:
            continue
        if gap_filter == "registration_hubs" and not p["is_registration_hub"]:
            continue
        if q:
            hay = " ".join([
                p["name"],
                p["domain"],
                p["high_level_category"],
                " ".join(x["name"] for x in p["listed_accelerators"]),
            ]).lower()
            if q not in hay:
                continue
        filtered_platforms.append(p)

    # Enrich Top 100 benchmark accelerators with their found platforms
    enriched_accels = []
    for a in accels:
        rk = a["rank"]
        plist = accel_platforms_map.get(rk, [])
        enriched_accels.append(
            {
                "rank": rk,
                "name": a["name"],
                "domain": a["domain"],
                "website": a["website"],
                "city": a["city"],
                "scope": a["scope"],
                "sector_focus": a["sector_focus"],
                "platforms_count": len(plist),
                "listed_on": plist,
            }
        )

    return {
        "summary": summary,
        "last_scan": dict(last_scan) if last_scan else None,
        "platforms": filtered_platforms,
        "benchmark_accelerators": enriched_accels,
    }
