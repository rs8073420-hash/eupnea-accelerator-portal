"""
Comprehensive End-to-End Verification Suite for Eupnea Portal:
1. Gemini 4 Hydrogen Sovereign Engine (zero DeepSeek)
2. Panagiotis Point System (21 criteria, editable weights & reset) + Quality Summary
3. F6S/Gust Multi-Programme Registration Hubs Spotlight & Top-Hubs Filtering (115 verified hubs)
4. 7-Agent Category Fleet + 100-Agent Swarm Integration (temp-DB isolated where mutating)
"""

import json
import os
import shutil
import sqlite3
import tempfile
from fastapi.testclient import TestClient

import gemini_hydrogen_engine as ghe
import presence_scoring_engine as pse
import presence_dashboard as pdash
import category_agent_fleet as caf
import category_agent_trainer as cat_trainer
import orchestration_engine as orch


def run_suite():
    print("=== EUPNEA GEMINI 4 HYDROGEN + F6S/GUST HUBS E2E VERIFICATION ===")
    client = TestClient(pdash.app)

    # 1. Health & HTML UI Assertions
    r_health = client.get("/health")
    assert r_health.status_code == 200, r_health.text
    hjson = r_health.json()
    assert hjson.get("engine") == "Gemini-4-Hydrogen-Sovereign", hjson
    assert hjson.get("model") == "gemini-4-hydrogen", hjson
    assert hjson.get("deepseek_disabled") is True, hjson

    r_html = client.get("/")
    assert r_html.status_code == 200
    html = r_html.text
    assert "Gemini 4 Hydrogen" in html
    assert "F6S/Gust Hubs" in html
    assert "q-reg-hubs-count" in html
    assert "trainAllCategoryAgents" in html
    assert "Train All 7 Agents" in html
    assert "DeepSeek v4.1" not in html
    assert "DEEPSEEK V4.1" not in html
    print("1. HTML UI & Health checks passed.")

    # 2. Dashboard Stats & Engine Telemetry
    r_stats = client.get("/api/dashboard/stats")
    assert r_stats.status_code == 200, r_stats.text
    stats = r_stats.json()
    eng = stats.get("gemini_hydrogen_engine") or {}
    assert eng.get("engine_version") == "Gemini-4-Hydrogen-Sovereign", eng
    assert eng.get("active_model") == "gemini-4-hydrogen", eng
    assert eng.get("deepseek_disabled") is True, eng
    assert "deepseek_engine" not in stats, "Legacy deepseek_engine key still present"
    assert stats["raw_total_platforms"] == 1172, stats["raw_total_platforms"]
    assert stats["total_platforms"] == 408, stats["total_platforms"]
    assert stats["tier_1_count"] == 65, stats["tier_1_count"]
    assert stats["tier_2_count"] == 343, stats["tier_2_count"]
    assert stats["registration_hubs_count"] == 115, stats["registration_hubs_count"]
    qs = stats["quality_summary"]
    assert qs["registration_hubs_count"] == 115
    assert qs["active_portal_accuracy_pct"] > 90
    print(f"2. Dashboard Stats passed (hubs={stats['registration_hubs_count']}, tier1={stats['tier_1_count']}, qualified={stats['total_platforms']}).")

    # 3. F6S/Gust Top Hubs API Filtering (must return exact 115 without campus labs or CRMs)
    r_h1 = client.get("/api/platforms?top_hubs_only=true&limit=100&page=1")
    r_h2 = client.get("/api/platforms?top_hubs_only=true&limit=100&page=2")
    assert r_h1.status_code == 200 and r_h2.status_code == 200
    h1 = r_h1.json()
    h2 = r_h2.json()
    assert h1["total"] == 115, h1["total"]
    all_hubs = h1["platforms"] + h2["platforms"]
    assert len(all_hubs) == 115
    assert all(p.get("is_registration_hub") is True for p in all_hubs)
    hub_domains = {p["domain"].lower() for p in all_hubs}
    for must_have in [
        "f6s.com", "gust.com", "findukaccelerator.co.uk", "mentornity.com",
        "startersss.com", "venturelist.app", "freestartupfunding.com", "superscout.co",
        "seed-db.com", "startupnation.com", "opengrants.io", "startupstash.com",
        "crunchbase.com", "dealroom.co", "vestbee.com",
    ]:
        assert must_have in hub_domains, f"Missing expected hub: {must_have}"
    for must_exclude in [
        "founderssuite.com", "gla.ac.uk", "shefftechparks.co.uk", "setsquared-bristol.co.uk"
    ]:
        assert must_exclude not in hub_domains, f"Unexpected non-hub leaked into top_hubs_only: {must_exclude}"
    print("3. Top F6S/Gust Hubs API filter passed (115/115 pure hubs).")

    # 4. Point System Criteria & Isolated Temp DB Weight-Recalculation Guard
    r_crit = client.get("/api/scoring/criteria")
    assert r_crit.status_code == 200
    crit = r_crit.json()
    assert len(crit["criteria"]) == 21, len(crit["criteria"])

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = os.path.join(tmpdir, "presence_agent.db")
        shutil.copyfile("presence_agent.db", tmp_db)
        res_upd = pse.update_criteria_weights({"tier_1_intake": 20}, db_path=tmp_db, recalculate=True)
        assert res_upd["recalculated"] > 0
        tconn = sqlite3.connect(tmp_db)
        try:
            t1_non_hub = tconn.execute(
                "SELECT COUNT(*) FROM platforms WHERE tier = 'tier_1' AND COALESCE(is_registration_hub, 0) = 0 AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')"
            ).fetchone()[0]
            assert t1_non_hub == 0, f"Single-entity non-hub leaked into tier_1 after recalc: {t1_non_hub}"
        finally:
            tconn.close()
        pse.reset_criteria_weights(db_path=tmp_db, recalculate=True)
    print("4. Editable 21-Criteria Point System & Single-Entity Tier-1 Guard passed.")

    # 5. Category Fleet Training Profiles, Strict Category Gate & Rankers
    r_rank = client.get("/api/rankers")
    assert r_rank.status_code == 200
    rankers = r_rank.json()
    assert len(rankers) >= 53, len(rankers)

    r_train_all = client.post("/api/category-agents/train-all")
    assert r_train_all.status_code == 200, r_train_all.text
    train_res = r_train_all.json()
    assert train_res["trained_agents"] == 7
    assert train_res["avg_validation_accuracy"] == 100.0, train_res

    r_agents = client.get("/api/category-agents")
    assert r_agents.status_code == 200
    roster = r_agents.json()
    assert len(roster) == 7
    for ag in roster:
        assert ag.get("trained") is True, ag
        assert ag.get("accuracy_score") == 100.0, ag

    r_prof = client.get("/api/category-agents/astra_i01/training-profile")
    assert r_prof.status_code == 200
    prof = r_prof.json()
    assert len(prof.get("positive_examples", [])) > 0
    assert len(prof.get("search_queries", [])) > 0

    astra_i = next(a for a in roster if a["id"] == "astra_i01")
    assert "F6S/Gust" in astra_i["name"], astra_i["name"]
    assert "Gemini 4 Hydrogen" in astra_i["specialization"], astra_i["specialization"]
    assert not any("ox.ac.uk" in x["domain"] or "jbs.cam.ac.uk" in x["domain"] for x in caf.INTAKE_EXPANSION_POOL)

    # Strict Category Alignment Gate Assertions (Zero cross-category leaks)
    assert cat_trainer.classify_candidate_for_category(
        {"name": "University of Glasgow Incubator", "domain": "gla.ac.uk"}, "engagement_intake"
    )["match"] is False
    assert cat_trainer.classify_candidate_for_category(
        {"name": "Greater Manchester Chamber of Commerce", "domain": "gmchamber.co.uk"}, "engagement_intake"
    )["match"] is False
    assert cat_trainer.classify_candidate_for_category(
        {"name": "Greater Manchester Chamber of Commerce", "domain": "gmchamber.co.uk"}, "regional_chambers"
    )["match"] is True
    assert cat_trainer.classify_candidate_for_category(
        {"name": "SeedLegals Top UK Accelerators", "domain": "seedlegals.com"}, "uk_reviews"
    )["match"] is True
    assert cat_trainer.classify_candidate_for_category(
        {"name": "US Local Tech News Blog", "domain": "exampleus.com"}, "uk_reviews"
    )["match"] is False
    print(f"5. Trained Category Fleet (7/7 @ 100.0% Acc) & Strict Category Gate verified (rankers={len(rankers)}).")

    # 6. Check orchestration fleet endpoints (read-only + live agent metadata)
    r_fleet = client.get("/api/orchestration/fleet")
    assert r_fleet.status_code == 200
    fleet = r_fleet.json()
    assert fleet["total_agents"] == 100
    print(f"6. 100-Agent Swarm Orchestration Fleet verified (total_agents={fleet['total_agents']}).")

    print("\nALL GEMINI 4 HYDROGEN E2E ASSERTIONS PASSED WITH 0 FAILURES!")


if __name__ == "__main__":
    run_suite()
