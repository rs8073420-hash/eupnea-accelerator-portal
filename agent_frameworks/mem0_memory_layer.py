"""
========================================================================================
MEM0 PERSISTENT AGENT MEMORY LAYER
========================================================================================
Integrates episodic, semantic, and user profile memory for AI agents.
Ensures agents remember user preferences, past errors, solutions, and domain rules
with automatic deduplication and per-agent memory recall.
========================================================================================
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add mem0 repo to sys.path if needed
MEM0_REPO = Path(__file__).resolve().parent / "mem0"
if str(MEM0_REPO) not in sys.path and MEM0_REPO.exists():
    sys.path.insert(0, str(MEM0_REPO))

try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False


class AgentMemoryHub:
    """
    Standardized memory interface for AI agents.
    Supports local JSON persistence fallback with strict deduplication.
    """

    def __init__(self, user_id: str = "commander_aadarsh", agent_id: str = "master_agent"):
        self.user_id = user_id
        self.agent_id = agent_id
        self.local_store_path = Path(__file__).resolve().parent / "memory_cache.json"

        if MEM0_AVAILABLE:
            try:
                self.memory = Memory()
            except Exception:
                self.memory = None
        else:
            self.memory = None

        self._local_cache = self._load_local_cache()

    def _load_local_cache(self) -> Dict[str, Any]:
        if self.local_store_path.exists():
            try:
                with open(self.local_store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("memories"), list):
                        return data
            except Exception:
                pass
        return {"memories": []}

    def _save_local_cache(self):
        with open(self.local_store_path, "w", encoding="utf-8") as f:
            json.dump(self._local_cache, f, indent=2, ensure_ascii=False)

    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Adds a memory observation or fact (deduplicated per user_id + agent_id + content)."""
        clean_content = (content or "").strip()
        if not clean_content:
            return
        meta = dict(metadata or {})
        meta.update({"user_id": self.user_id, "agent_id": self.agent_id})

        # Deduplicate exact memory lines in local cache
        existing = self._local_cache.get("memories", [])
        for item in existing:
            imd = item.get("metadata") or {}
            if (
                (item.get("content") or "").strip() == clean_content
                and imd.get("user_id") == self.user_id
                and imd.get("agent_id") == self.agent_id
            ):
                return

        if self.memory:
            try:
                self.memory.add(clean_content, user_id=self.user_id, metadata=meta)
                return
            except Exception:
                pass

        entry = {"content": clean_content, "metadata": meta}
        self._local_cache.setdefault("memories", []).append(entry)
        self._save_local_cache()

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches memories relevant to the current query."""
        if self.memory:
            try:
                return self.memory.search(query, user_id=self.user_id, limit=limit)
            except Exception:
                pass

        q_words = [w for w in (query or "").lower().split() if len(w) > 2]
        scored = []
        for item in self._local_cache.get("memories", []):
            txt = (item.get("content") or "").lower()
            hits = sum(1 for w in q_words if w in txt) if q_words else 1
            if hits > 0:
                scored.append((hits, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:limit]]

    def get_memories_for_agent(self, agent_id: Optional[str] = None, limit: int = 12) -> List[str]:
        """Returns unique stored memory strings for a given agent_id (or current agent)."""
        target = agent_id or self.agent_id
        seen = set()
        out = []
        for item in self._local_cache.get("memories", []):
            imd = item.get("metadata") or {}
            if imd.get("agent_id") == target:
                c = (item.get("content") or "").strip()
                if c and c not in seen:
                    seen.add(c)
                    out.append(c)
        return out[:limit]

    def get_all_agent_summary(self) -> Dict[str, List[str]]:
        """Groups all unique stored memories across every agent_id."""
        grouped: Dict[str, List[str]] = {}
        seen: Dict[str, set] = {}
        for item in self._local_cache.get("memories", []):
            imd = item.get("metadata") or {}
            aid = imd.get("agent_id") or "shared"
            c = (item.get("content") or "").strip()
            if not c:
                continue
            s = seen.setdefault(aid, set())
            if c not in s:
                s.add(c)
                grouped.setdefault(aid, []).append(c)
        return grouped

    def get_all_context(self) -> str:
        """Formats all unique memories into an LLM system prompt context injection."""
        memories = self._local_cache.get("memories", [])
        if not memories:
            return ""
        seen = set()
        lines = []
        for m in memories:
            c = (m.get("content") or "").strip()
            if c and c not in seen:
                seen.add(c)
                lines.append(f"- {c}")
        return "### AGENT RECALLED MEMORIES & RULES:\n" + "\n".join(lines)
