"""
========================================================================================
BROWSER-USE ENGINE (MANDATORY PER-AGENT BROWSER AUTOMATION PROTOCOL)
========================================================================================
Directive: For ANY and ALL web browser interactions, scraping, DOM extraction,
form verification, and search tasks, 'browser-use' is STRICTLY COMPULSORY.
Every individual agent owns an isolated persistent profile inside agent_browser_profiles/.
========================================================================================
"""

import os
import sys
import json
import asyncio
import time
import urllib.parse
from typing import Optional, Dict, Any, List
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
BROWSER_USE_REPO = WORKSPACE_ROOT / "browser-use"
PROFILES_ROOT = WORKSPACE_ROOT / "agent_browser_profiles"

if str(BROWSER_USE_REPO) not in sys.path and BROWSER_USE_REPO.exists():
    sys.path.insert(0, str(BROWSER_USE_REPO))

try:
    from browser_use import Agent, Browser
    from browser_use.browser.browser import _daemon_cdp
    BROWSER_USE_AVAILABLE = True
except Exception:
    Agent = None
    Browser = None
    _daemon_cdp = None
    BROWSER_USE_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

COMPETITOR_SCANNER_PROFILE_IDS = [f"competitor_{i:02d}" for i in range(1, 11)]

ALL_SPECIALIST_PROFILE_IDS = [
    "bespoke_coordinator",
    "eupnea_v2_presence_browser",
    "competitor_analyst",
    "astra_r01",
    "astra_s01",
    "astra_u01",
    "astra_i01",
    "astra_v01",
    "astra_e01",
    "astra_c01",
] + COMPETITOR_SCANNER_PROFILE_IDS


def get_agent_browser_profile(agent_id: str) -> str:
    """Returns and ensures the dedicated browser-use user_data_dir for an individual agent."""
    safe_id = "".join(ch for ch in (agent_id or "master_profile").lower() if ch.isalnum() or ch in ("_", "-")) or "master_profile"
    pdir = PROFILES_ROOT / safe_id
    pdir.mkdir(parents=True, exist_ok=True)
    return str(pdir)


def ensure_all_agent_browser_profiles() -> Dict[str, str]:
    """Ensures every category, bespoke, orchestrator (110 agents), and competitor agent owns a dedicated browser profile."""
    profile_map = {aid: get_agent_browser_profile(aid) for aid in ALL_SPECIALIST_PROFILE_IDS}
    for i in range(1, 91):
        profile_map[f"agent_{i:02d}"] = get_agent_browser_profile(f"agent_{i:02d}")
    for i in range(1, 11):
        profile_map[f"agent_m{i:02d}"] = get_agent_browser_profile(f"agent_m{i:02d}")
    return profile_map


_CACHED_CHROME_EXE: Optional[str] = ""


def find_chromium_executable() -> Optional[str]:
    """Resolves local Chromium/Chrome executable without spawning blocking loops."""
    global _CACHED_CHROME_EXE
    if _CACHED_CHROME_EXE != "":
        return _CACHED_CHROME_EXE

    if os.environ.get("RENDER") or os.environ.get("SPACE_ID"):
        # Check system paths only; do not force heavy Playwright lookup in slim cloud containers
        for cand in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
            if os.path.exists(cand):
                _CACHED_CHROME_EXE = cand
                return cand
        _CACHED_CHROME_EXE = None
        return None

    if PLAYWRIGHT_AVAILABLE and sync_playwright is not None:
        try:
            with sync_playwright() as p:
                exe = p.chromium.executable_path
                if exe and os.path.exists(exe):
                    _CACHED_CHROME_EXE = exe
                    return exe
        except Exception:
            pass

    for win_cand in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if os.path.exists(win_cand):
            _CACHED_CHROME_EXE = win_cand
            return win_cand

    _CACHED_CHROME_EXE = None
    return None


class BrowserUseEngine:
    """
    Standardized runner for Browser Use 1.0 automation tasks.
    Each agent instantiates its own BrowserUseEngine bound to agent_browser_profiles/{agent_id}/.
    """

    def __init__(
        self,
        agent_id: str = "master_profile",
        llm: Optional[Any] = None,
        headless: bool = True,
        user_data_dir: Optional[str] = None,
        cdp_url: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.llm = llm
        self.headless = headless
        self.user_data_dir = user_data_dir or get_agent_browser_profile(agent_id)
        self.cdp_url = cdp_url
        self.browser: Optional[Any] = None

    @classmethod
    def get_runtime_status(cls, agent_id: str = "master_profile") -> Dict[str, Any]:
        exe = find_chromium_executable()
        live_cdp = bool(BROWSER_USE_AVAILABLE and exe)
        return {
            "agent_id": agent_id,
            "browser_profile_dir": f"agent_browser_profiles/{agent_id}",
            "browser_use_loaded": BROWSER_USE_AVAILABLE,
            "chromium_available": bool(exe),
            "engine_mode": "browser-use 1.0 (Chromium CDP)" if live_cdp else "browser-use 1.0 profile (Cloud HTTP Fallback)",
        }

    def initialize_browser(self) -> Any:
        if not BROWSER_USE_AVAILABLE or Browser is None:
            raise ImportError("browser-use repository could not be imported.")
        exe = find_chromium_executable()
        kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "user_data_dir": os.path.abspath(self.user_data_dir),
        }
        if exe:
            kwargs["executable_path"] = exe
        if self.cdp_url:
            kwargs["cdp_url"] = self.cdp_url
            self.browser = Browser(**kwargs)
        else:
            self.browser = Browser("chromium", **kwargs)
        return self.browser

    async def execute_task(
        self,
        task_instruction: str,
        llm: Optional[Any] = None,
        max_steps: int = 25,
    ) -> Any:
        """Runs a full autonomous browser-use Agent workflow when an LLM model is supplied."""
        if not self.browser:
            self.initialize_browser()
        active_llm = llm or self.llm
        if not active_llm:
            raise ValueError("An LLM must be provided for free-form Agent tasks.")
        agent = Agent(task=task_instruction, llm=active_llm, browser=self.browser)
        return await agent.run(max_steps=max_steps)

    async def inspect_urls_cdp(self, urls: List[str], wait_sec: float = 1.6) -> List[Dict[str, Any]]:
        """
        Opens a persistent Browser('chromium') session under THIS agent's profile directory,
        navigates each candidate URL via native CDP, waits for JS/DOM render, and extracts
        rendered title, meta description, body text snippet, and internal links cleanly.
        """
        if not BROWSER_USE_AVAILABLE or Browser is None or _daemon_cdp is None:
            return []
        exe = find_chromium_executable()
        if not exe:
            return []

        results: List[Dict[str, Any]] = []
        browser = Browser(
            "chromium",
            headless=self.headless,
            user_data_dir=os.path.abspath(self.user_data_dir),
            executable_path=exe,
        )
        js_extract = """
        (() => {
          const title = (document.title || '').trim();
          const descMeta = document.querySelector('meta[name="description"], meta[property="og:description"]');
          const metaDesc = descMeta ? (descMeta.getAttribute('content') || '').trim() : '';
          const bodyText = (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim().slice(0, 4000);
          const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 80).map(a => ({
            href: a.href || '',
            text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80)
          }));
          return JSON.stringify({url: window.location.href, title, metaDesc, bodyText, links});
        })()
        """
        try:
            await asyncio.wait_for(browser.start(), timeout=12.0)
            for target in urls:
                try:
                    _daemon_cdp(browser.name, "Page.navigate", url=target)
                    await asyncio.sleep(wait_sec)
                    ev = _daemon_cdp(browser.name, "Runtime.evaluate", expression=js_extract, returnByValue=True)
                    raw_val = ((ev or {}).get("result") or {}).get("value")
                    if raw_val:
                        parsed = json.loads(raw_val)
                        parsed["ok"] = True
                        parsed["requested_url"] = target
                        parsed["agent_id"] = self.agent_id
                        parsed["browser_profile"] = f"agent_browser_profiles/{self.agent_id}"
                        results.append(parsed)
                except Exception as nav_err:
                    results.append({"ok": False, "requested_url": target, "error": str(nav_err)})
        finally:
            try:
                await asyncio.wait_for(browser.stop(), timeout=6.0)
            except Exception:
                pass
        return results

    def inspect_urls_sync(self, urls: List[str], wait_sec: float = 1.6) -> List[Dict[str, Any]]:
        """Thread-safe synchronous wrapper for BrowserUse CDP page extraction."""
        if not urls:
            return []
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.inspect_urls_cdp(urls, wait_sec=wait_sec))
            finally:
                loop.close()
        except Exception:
            return []

    async def google_search_via_browser(self, query: str, limit: int = 8) -> List[Dict[str, str]]:
        """
        Uses THIS agent's dedicated browser-use Chromium instance to search Google
        and extract non-ad organic startup/accelerator URLs when running locally.
        """
        if not BROWSER_USE_AVAILABLE or Browser is None or _daemon_cdp is None:
            return []
        if not find_chromium_executable():
            return []

        q_enc = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/search?q={q_enc}&hl=en&gl=gb&num=15"
        out: List[Dict[str, str]] = []
        browser = Browser(
            "chromium",
            headless=self.headless,
            user_data_dir=os.path.abspath(self.user_data_dir),
            executable_path=find_chromium_executable(),
        )
        js_serp = """
        (() => {
          const items = [];
          document.querySelectorAll('a h3').forEach(h3 => {
            const a = h3.closest('a');
            if (a && a.href && a.href.startsWith('http') && !a.href.includes('google.com')) {
              items.push({url: a.href, title: (h3.innerText || '').trim()});
            }
          });
          return JSON.stringify(items);
        })()
        """
        try:
            await asyncio.wait_for(browser.start(), timeout=12.0)
            _daemon_cdp(browser.name, "Page.navigate", url=search_url)
            await asyncio.sleep(2.2)
            ev = _daemon_cdp(browser.name, "Runtime.evaluate", expression=js_serp, returnByValue=True)
            raw_val = ((ev or {}).get("result") or {}).get("value")
            if raw_val:
                rows = json.loads(raw_val)
                for row in rows[:limit]:
                    out.append(row)
        except Exception:
            return []
        finally:
            try:
                await asyncio.wait_for(browser.stop(), timeout=6.0)
            except Exception:
                pass
        return out

    async def close(self):
        if self.browser:
            await self.browser.stop()
            self.browser = None


# Ensure all agent browser profile directories exist on import
ensure_all_agent_browser_profiles()
