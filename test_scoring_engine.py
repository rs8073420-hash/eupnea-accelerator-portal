import presence_scoring_engine as pse

print("=== Running Gemini 4 Hydrogen Scoring Engine Verification ===")

# Test 1: Fake Intake Domain
res_fake = pse.score_platform_record({
    "name": "Newcastle Life Sciences Enterprise Scaleup Lab",
    "domain": "newcastle-lifesciences-intake-144.co.uk",
    "url": "https://newcastle-lifesciences-intake-144.co.uk"
})
print("1. Fake Intake Domain:", res_fake["score"], res_fake["tier"], res_fake["status"])
assert res_fake["score"] == 0
assert res_fake["tier"] == "rejected"
assert res_fake["status"] == "unqualified"
assert res_fake["engine"] == "Gemini-4-Hydrogen-Sovereign"

# Test 2: Unsuitable Platform
res_uns = pse.score_platform_record({
    "name": "VentureMatch",
    "domain": "venturematch.tech",
    "url": "https://venturematch.tech"
})
print("2. Unsuitable Platform (VentureMatch):", res_uns["score"], res_uns["tier"], res_uns["status"])
assert res_uns["score"] == 0
assert res_uns["tier"] == "rejected"
assert res_uns["status"] == "unqualified"

# Test 3: Perk Platform
res_perk = pse.score_platform_record({
    "name": "GitHub for Startups Accelerator Partner Program",
    "domain": "github.com",
    "url": "https://github.com",
    "category": "Global Venture & Accelerator Hubs"
})
print("3. Perk Platform (GitHub for Startups):", res_perk["score"], res_perk["tier"], res_perk["status"])
assert res_perk["score"] == 0
assert res_perk["tier"] == "cohort_perk"
assert res_perk["status"] == "perk_benefit"

# Test 4: Tier 1 Hub Benchmark (F6S)
res_f6s = pse.score_platform_record({
    "name": "F6S Accelerators & Startup Programs Directory",
    "domain": "f6s.com",
    "url": "https://www.f6s.com/programs"
})
print("4. Tier 1 Benchmark (F6S):", res_f6s["score"], res_f6s["tier"], res_f6s["status"], "hub=", res_f6s["is_registration_hub"])
assert res_f6s["score"] == 99
assert res_f6s["tier"] == "tier_1"
assert res_f6s["status"] == "in_review"
assert res_f6s["is_registration_hub"] == 1

# Test 5: High-Reach Discovery Hub (Crunchbase)
res_cb = pse.score_platform_record({
    "name": "Crunchbase Organizations & Accelerator Hub",
    "domain": "crunchbase.com",
    "url": "https://www.crunchbase.com/hub/accelerators"
})
print("5. Discovery Hub (Crunchbase):", res_cb["score"], res_cb["tier"], res_cb["status"], "hub=", res_cb["is_registration_hub"])
assert res_cb["score"] >= 90
assert res_cb["is_registration_hub"] == 1

# Test 6: Single-Entity Campus Guard (University .ac.uk cannot inflate into Tier 1 or Registration Hub)
res_uni = pse.score_platform_record({
    "name": "University of Glasgow Entrepreneurship Lab",
    "domain": "gla.ac.uk",
    "url": "https://www.gla.ac.uk/",
    "high_level_category": "Direct Startup Engagement & Intake",
})
print("6. Single-Campus Guard (gla.ac.uk):", res_uni["score"], res_uni["tier"], "hub=", res_uni["is_registration_hub"])
assert res_uni["tier"] != "tier_1"
assert res_uni["is_registration_hub"] == 0

# Test 7: PDF Brief Editable Criteria Compatibility
res_calc = pse.evaluate_platform_score({
    "real_directory": True,
    "clear_submit_path": True,
    "target_audience": True,
    "target_geography": True,
    "structured_fields": True,
    "established_directory": True
})
print("7. Standard Qualified Platform:", res_calc["score"], res_calc["is_qualified"], res_calc["classification"])
assert res_calc["score"] >= 70
assert res_calc["is_qualified"] is True

res_reject = pse.evaluate_platform_score({
    "real_directory": True,
    "blog_news": True
})
print("8. Hard Reject Platform (Blog):", res_reject["score"], res_reject["is_qualified"], res_reject["classification"])
assert res_reject["score"] == 0
assert res_reject["is_qualified"] is False

print("\nALL GEMINI 4 HYDROGEN SCORING ENGINE UNIT TESTS PASSED 100%!")
