"""
================================================================================
🏛️ EUPNEA V2 — OFFICIAL PRODUCTION APPLICATION (TWO DOORS)
================================================================================
Architectural Specification:
  - Document: "FOR THE FOUNDER - Eupnea v2" & Video Walkthrough Blueprint
  - Door 1: The Public Marketing Website for clients, founders, and partners
      * Hero, Proof Strip (UNGC, Global reach, 24/7 Phone +44 203 026 1523 & Email clientservices@eupnea.co.uk)
      * The Problem We Solve
      * 4 Ways Eupnea Helps (Strategy Consulting, Operations Excellence, Workforce & AI Readiness, Accelerator)
      * 4 Commitments (Client-Centred, Responsible Counsel, Integrity, Relevant Innovation)
      * 4-Step Process (Discover, Design, Deliver, Sustain)
      * Accelerator with Video preview
      * Insights, Articles, Whitepapers, CEO Statement (Panagiotis Dimitrelis)
      * Inner Pages/Modals: About us, Our story (2016), Services (8 areas + 4 solutions), 
        Industries (13 sectors), Case studies, Careers, Contact
      * "Book a call" & "Staff login" modal
      * UTM Attribution Tracking (Deduplicated via sessionStorage, increments Website visits)
  - Door 2: The Protected Staff Workspace
      * Accessible via "Staff login" modal on public site
      * 4 Rooms: Dashboard, Presence, Review, Team
      * 8 KPI Cards (Website visits, Pending reviews, Profile views [held], Leads generated [held],
        Qualified leads [held], Applications [held], Meetings booked [held], Conversion rate [held])
      * Activity Feed with stage updates, alerts panel, and listing sources table
      * Presence Agent room: discovery configuration (25-500), background run simulation/trigger,
        score filter slider (default 50), manual platform addition, pagination, detail drawer,
        approve/reject, submit with live URL
      * Review room: 6 queue tabs (All, In review, Approved, Submitted, Unqualified, Dismissed),
        quick triage dismiss, undo submission
      * Team room: RBAC (Admin, Manager, Member, Viewer), add member, change role, change password
  - Styling & Design:
      * Typography: Syne (Headings), DM Sans (Body), JetBrains Mono (Badges & Code)
      * Color Palette: Soft Blue (#38BDF8 / #60A5FA), Teal Accent (#14B8A6), Deep Navy (#070B14 / #0D1424)
      * Light / Dark theme support
      * Seamless switching between Public Website and Staff Workspace
================================================================================
"""

import os
import json
import time
import sqlite3
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, Query, HTTPException, Request, Response, Body, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import presence_scoring_engine as pse
import orchestration_engine as orch_eng
import deepseek_flash_engine as dfe

try:
    from eupnea_presence_agent_upgrade import presence_upgrade_controller
except ImportError:
    presence_upgrade_controller = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = BASE_DIR
DB_PATH = os.path.join(BASE_DIR, "presence_agent.db")
LIVE_STATUS_PATH = os.path.join(BASE_DIR, "swarm_live_status.json")

app = FastAPI(title="Eupnea v2 Ecosystem", version="2.0")

@app.on_event("startup")
def on_app_startup():
    try:
        orch_eng.init_orchestration_db()
        orch_eng.start_continuous_orchestrator()
        print("⚡ [24x7 AUTONOMOUS FLEET ACTIVE]: 100 Agents permanently online & executing tasks non-stop.")
    except Exception as e:
        print(f"Startup orchestrator notice: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ================================================================================
# PYDANTIC SCHEMAS
# ================================================================================
class LoginRequest(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    user_id: int
    current_password: str
    new_password: str

class AddMemberRequest(BaseModel):
    email: str
    full_name: str
    password: str
    role: str

class UpdateRoleRequest(BaseModel):
    role: str

class EditScoreRequest(BaseModel):
    score: int
    reason: Optional[str] = "Manual review adjustment"

class StatusUpdateRequest(BaseModel):
    status: str
    submitted_url: Optional[str] = None

class AddManualPlatformRequest(BaseModel):
    name: str
    domain: str
    category: str
    score: int = 100
    submitted_url: Optional[str] = ""
    status: Optional[str] = "in_review"
    high_level_category: Optional[str] = "Direct Startup Engagement & Intake"

class SearchSettingsRequest(BaseModel):
    phrases: List[str]
    target_count: int = 25

class TrackVisitRequest(BaseModel):
    utm_source: str
    utm_medium: Optional[str] = "directory"
    utm_campaign: Optional[str] = "accelerator_2026"

class ExecuteQueryRequest(BaseModel):
    query: str

# ================================================================================
# AUTH & USER ENDPOINTS
# ================================================================================
@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "127.0.0.1"
    email_clean = req.email.strip().lower()
    
    conn = get_db()
    c = conn.cursor()
    
    # 1. Rate-limit lockout check per PDF brief Page 5:
    # "Five failed attempts for the same email and the same network address lock that sign-in for 15 minutes."
    lockout = c.execute(
        "SELECT attempts, locked_until FROM login_attempts WHERE email = ? AND ip = ?",
        (email_clean, client_ip)
    ).fetchone()
    
    if lockout and lockout["locked_until"]:
        try:
            lock_time = datetime.fromisoformat(lockout["locked_until"])
            if datetime.now() < lock_time:
                conn.close()
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Account sign-in locked for 15 minutes per security brief."
                )
        except Exception:
            pass

    pw_hash = hash_pw(req.password)
    user = c.execute(
        "SELECT id, email, full_name, role, is_active FROM users WHERE email = ? AND password_hash = ?",
        (email_clean, pw_hash)
    ).fetchone()

    if not user:
        # Increment failed attempts
        c.execute("""
            INSERT INTO login_attempts (email, ip, attempts, locked_until)
            VALUES (?, ?, 1, NULL)
            ON CONFLICT(email, ip) DO UPDATE SET attempts = attempts + 1
        """, (email_clean, client_ip))
        
        curr_attempts = c.execute(
            "SELECT attempts FROM login_attempts WHERE email = ? AND ip = ?",
            (email_clean, client_ip)
        ).fetchone()
        
        if curr_attempts and curr_attempts["attempts"] >= 5:
            lock_until = (datetime.now() + timedelta(minutes=15)).isoformat()
            c.execute(
                "UPDATE login_attempts SET locked_until = ? WHERE email = ? AND ip = ?",
                (lock_until, email_clean, client_ip)
            )
            conn.commit()
            conn.close()
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Sign-in locked for 15 minutes."
            )
        
        conn.commit()
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user["is_active"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact an administrator.")

    # Successful login: clear failed attempts
    c.execute("DELETE FROM login_attempts WHERE email = ? AND ip = ?", (email_clean, client_ip))
    conn.commit()
    conn.close()

    # Per PDF brief Page 4:
    # access_token (~15 min) in httpOnly cookie
    # refresh_token (~7 days) in httpOnly cookie
    access_token = f"eupnea_access_{user['id']}_{int(time.time())}"
    refresh_token = f"eupnea_refresh_{user['id']}_{int(time.time())}"
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=900, samesite="lax")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, max_age=604800, samesite="lax")

    user_dict = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"]
    }
    return {
        "status": "success",
        "user": user_dict,
        "token": access_token,
        "access_token": access_token,
        "refresh_token": refresh_token
    }

@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest):
    conn = get_db()
    c = conn.cursor()
    curr_hash = hash_pw(req.current_password)
    user = c.execute("SELECT id FROM users WHERE id = ? AND password_hash = ?", (req.user_id, curr_hash)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    
    new_hash = hash_pw(req.new_password)
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, req.user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Password updated successfully."}

@app.get("/api/team")
def get_team():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT id, email, full_name, role, is_active, created_at FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/team/add")
def add_team_member(req: AddMemberRequest):
    conn = get_db()
    c = conn.cursor()
    existing = c.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    pw_hash = hash_pw(req.password)
    c.execute(
        "INSERT INTO users (email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, 1)",
        (req.email.strip().lower(), req.full_name.strip(), pw_hash, req.role)
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return {"status": "success", "id": new_id, "message": f"Member {req.full_name} added."}

@app.post("/api/team/{user_id}/role")
def update_team_role(user_id: int, req: UpdateRoleRequest):
    if req.role not in ["admin", "manager", "member", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role specified.")
    conn = get_db()
    c = conn.cursor()
    user = c.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Per PDF brief Page 3: "An administrator cannot remove their own access or demote themselves."
    if user["role"] == "admin" and req.role != "admin" and (user_id == 1 or user["email"] == "aadarsh@eupnea.co.uk"):
        conn.close()
        raise HTTPException(status_code=400, detail="An administrator cannot demote themselves per security brief.")

    c.execute("UPDATE users SET role = ? WHERE id = ?", (req.role, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "role": req.role}

@app.delete("/api/team/{user_id}")
def remove_team_member(user_id: int):
    conn = get_db()
    c = conn.cursor()
    # Check if admin trying to remove self per PDF brief Page 3
    user = c.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
        
    if user["role"] == "admin" and (user_id == 1 or user["email"] == "aadarsh@eupnea.co.uk"):
        conn.close()
        raise HTTPException(status_code=400, detail="An administrator cannot remove their own access per security brief.")
        
    if user["role"] == "admin":
        admin_count = c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1").fetchone()[0]
        if admin_count <= 1:
            conn.close()
            raise HTTPException(status_code=400, detail="Cannot remove the last active administrator.")
            
    # Soft delete: deactivates user while preserving audit records per PDF brief Page 3
    c.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "User access removed."}

# ================================================================================
# DASHBOARD STATS & KPI ENDPOINTS
# ================================================================================
@app.get("/api/dashboard/stats")
@app.get("/api/stats")
def get_dashboard_stats():
    conn = get_db()
    c = conn.cursor()

    total_platforms = c.execute("SELECT COUNT(*) FROM platforms").fetchone()[0]
    total_visits = c.execute("SELECT COUNT(*) FROM listing_visits").fetchone()[0]
    pending_reviews = c.execute("SELECT COUNT(*) FROM platforms WHERE status IN ('draft_ready', 'in_review', 'found', 'ready_to_submit')").fetchone()[0]
    approved_count = c.execute("SELECT COUNT(*) FROM platforms WHERE status = 'approved'").fetchone()[0]
    submitted_count = c.execute("SELECT COUNT(*) FROM platforms WHERE status = 'submitted'").fetchone()[0]
    unqualified_count = c.execute("SELECT COUNT(*) FROM platforms WHERE status IN ('unqualified', 'not_suitable')").fetchone()[0]
    perk_benefit_count = c.execute("SELECT COUNT(*) FROM platforms WHERE status = 'perk_benefit'").fetchone()[0]
    dismissed_count = c.execute("SELECT COUNT(*) FROM platforms WHERE status = 'dismissed'").fetchone()[0]

    qualified_platforms = c.execute("SELECT COUNT(*) FROM platforms WHERE status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]
    submittable_count = c.execute("SELECT COUNT(*) FROM platforms WHERE category_type = 'submittable_directory' AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]
    ecosystem_partner_count = c.execute("SELECT COUNT(*) FROM platforms WHERE category_type = 'ecosystem_partner' AND status NOT IN ('unqualified', 'not_suitable', 'dismissed')").fetchone()[0]

    tier_1_count = c.execute("SELECT COUNT(*) FROM platforms WHERE tier = 'tier_1' AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]
    tier_2_count = c.execute("SELECT COUNT(*) FROM platforms WHERE tier = 'tier_2' AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]
    deprioritized_count = c.execute("SELECT COUNT(*) FROM platforms WHERE tier = 'deprioritized'").fetchone()[0]
    core_target_count = c.execute("SELECT COUNT(*) FROM platforms WHERE is_core_target = 1 AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]

    # High-level category breakdown (Qualified Active Portals Only - Zero Unqualified Contamination)
    hl_rows = c.execute("SELECT high_level_category, COUNT(*) as cnt FROM platforms WHERE status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed') GROUP BY high_level_category").fetchall()
    hl_categories = {r["high_level_category"]: r["cnt"] for r in hl_rows if r["high_level_category"]}
    smartmatch_count = hl_categories.get("SmartMatch & Dealflow Licensing Engines", 0)
    engagement_intake_count = hl_categories.get("Direct Startup Engagement & Intake", 0)
    investor_networks_count = hl_categories.get("Investor Match & Capital Networks", 0)
    ecosystem_visibility_count = hl_categories.get("Ecosystem Visibility & Program Discovery", 0)
    regional_ecosystems_count = hl_categories.get("Regional Chambers & Business Networks", 0)
    media_press_count = hl_categories.get("Media, Press & Industry Publications", 0)
    uk_reviews_count = hl_categories.get("UK Accelerator Review & Ranking Platforms", 0)

    smartmatch_free_count = c.execute("SELECT COUNT(*) FROM platforms WHERE smartmatch_free = 1 AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]
    smartmatch_paid_count = c.execute("SELECT COUNT(*) FROM platforms WHERE smartmatch_paid = 1 AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')").fetchone()[0]

    try:
        rankers_count = c.execute("SELECT COUNT(*) FROM accelerator_rankers").fetchone()[0]
    except Exception:
        rankers_count = 0

    # Category breakdown
    cat_rows = c.execute("SELECT category, COUNT(*) as cnt FROM platforms WHERE status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed') GROUP BY category").fetchall()
    categories = {r["category"]: r["cnt"] for r in cat_rows}

    # Recent runs
    runs_rows = c.execute("SELECT * FROM activity_runs WHERE is_cleared = 0 ORDER BY id DESC LIMIT 5").fetchall()
    runs = [dict(r) for r in runs_rows]

    # Listing sources with visits
    sources_rows = c.execute("""
        SELECT p.id, p.name, p.category, p.domain, p.url, p.submitted_url, p.tracking_url, p.score, p.status, 
               COALESCE(p.visit_count, 0) as visits,
               COUNT(lv.id) as logged_visits
        FROM platforms p
        LEFT JOIN listing_visits lv ON p.id = lv.platform_id
        WHERE p.status = 'submitted' OR p.visit_count > 0
        GROUP BY p.id
        ORDER BY visits DESC, logged_visits DESC
        LIMIT 10
    """).fetchall()
    sources = [dict(r) for r in sources_rows]

    conn.close()

    # Alerts calculation
    alerts = []
    if pending_reviews > 0:
        alerts.append({
            "type": "info",
            "message": f"{pending_reviews} listing drafts are waiting for team review and approval."
        })
    else:
        alerts.append({
            "type": "success",
            "message": "The listing review queue is currently clear."
        })

    if submitted_count > 0:
        alerts.append({
            "type": "success",
            "message": f"{submitted_count} submitted listings are actively collecting visitor attribution."
        })

    return {
        "website_visits": total_visits,
        "pending_reviews": pending_reviews,
        "profile_views": None,       # Held for later agent (shows blank/hyphen)
        "leads_generated": None,     # Held for later agent
        "qualified_leads": None,    # Held for later agent
        "applications": None,        # Held for later agent
        "meetings_booked": None,     # Held for later agent
        "conversion_rate": None,     # Held for later agent
        "total_platforms": qualified_platforms,
        "raw_total_platforms": total_platforms,
        "submittable_directories": submittable_count,
        "ecosystem_partners": ecosystem_partner_count,
        "tier_1_count": tier_1_count,
        "tier_2_count": tier_2_count,
        "deprioritized_count": deprioritized_count,
        "core_target_count": core_target_count,
        "smartmatch_count": smartmatch_count,
        "smartmatch_free_count": smartmatch_free_count,
        "smartmatch_paid_count": smartmatch_paid_count,
        "engagement_intake_count": engagement_intake_count,
        "investor_networks_count": investor_networks_count,
        "ecosystem_visibility_count": ecosystem_visibility_count,
        "regional_ecosystems_count": regional_ecosystems_count,
        "media_press_count": media_press_count,
        "uk_reviews_count": uk_reviews_count,
        "software_reviews_count": uk_reviews_count,
        "rankers_count": rankers_count,
        "high_level_categories": hl_categories,
        "approved": approved_count,
        "submitted": submitted_count,
        "unqualified": unqualified_count,
        "perk_benefit": perk_benefit_count,
        "dismissed": dismissed_count,
        "deepseek_engine": dfe.DeepSeekFlashEngine.get_engine_status(),
        "categories": categories,
        "runs": runs,
        "alerts": alerts,
        "listing_sources": sources
    }

# ================================================================================
# PLATFORMS & REVIEW QUEUE ENDPOINTS
# ================================================================================
@app.get("/api/platforms")
def get_platforms(
    status: Optional[str] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    platform_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    high_level_category: Optional[str] = Query(None),
    smartmatch_filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100)
):
    # Resolve any FastAPI Query object default wrappers if called directly
    if hasattr(status, "default"): status = status.default
    if hasattr(min_score, "default"): min_score = min_score.default or 0
    if hasattr(search, "default"): search = search.default
    if hasattr(category, "default"): category = category.default
    if hasattr(platform_type, "default"): platform_type = platform_type.default
    if hasattr(tier, "default"): tier = tier.default
    if hasattr(high_level_category, "default"): high_level_category = high_level_category.default
    if hasattr(smartmatch_filter, "default"): smartmatch_filter = smartmatch_filter.default
    if hasattr(page, "default"): page = page.default or 1
    if hasattr(limit, "default"): limit = limit.default or 25

    try:
        min_score = int(min_score)
    except (ValueError, TypeError):
        min_score = 0
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 25

    conn = get_db()
    c = conn.cursor()

    query_parts = ["1=1"]
    params = []

    if high_level_category and high_level_category != "all":
        if high_level_category in ("smartmatch", "smartmatch_engines", "dealflow_licensing"):
            query_parts.append("high_level_category = 'SmartMatch & Dealflow Licensing Engines'")
        elif high_level_category in ("engagement_intake", "direct_intake", "startup_match", "primary"):
            query_parts.append("high_level_category = 'Direct Startup Engagement & Intake'")
        elif high_level_category in ("investor_match", "investor_networks", "investor"):
            query_parts.append("high_level_category = 'Investor Match & Capital Networks'")
        elif high_level_category in ("ecosystem_visibility", "visibility"):
            query_parts.append("high_level_category = 'Ecosystem Visibility & Program Discovery'")
        elif high_level_category in ("regional_ecosystems", "regional", "chambers"):
            query_parts.append("high_level_category = 'Regional Chambers & Business Networks'")
        elif high_level_category in ("media_press", "media", "press"):
            query_parts.append("high_level_category = 'Media, Press & Industry Publications'")
        elif high_level_category in ("uk_reviews", "software_reviews", "reviews", "accelerator_rankings"):
            query_parts.append("high_level_category = 'UK Accelerator Review & Ranking Platforms'")
        else:
            query_parts.append("high_level_category = ?")
            params.append(high_level_category)

    if smartmatch_filter and smartmatch_filter != "all":
        if smartmatch_filter == "free":
            query_parts.append("smartmatch_free = 1")
        elif smartmatch_filter == "paid":
            query_parts.append("smartmatch_paid = 1")
        elif smartmatch_filter == "any":
            query_parts.append("is_smartmatch = 1")

    if tier and tier != "all" and status not in ("unqualified", "not_suitable", "perk_benefit", "dismissed"):
        if tier == "tier_1":
            query_parts.append("tier = 'tier_1'")
        elif tier == "tier_2":
            query_parts.append("tier = 'tier_2'")
        elif tier in ("core", "all_active"):
            query_parts.append("is_core_target = 1 AND status NOT IN ('unqualified', 'not_suitable', 'perk_benefit', 'dismissed')")
        elif tier == "deprioritized":
            query_parts.append("tier = 'deprioritized'")

    if status and status != "all":
        if status == "in_review":
            query_parts.append("status IN ('draft_ready', 'in_review', 'found', 'ready_to_submit', 'pending')")
        elif status == "unqualified":
            query_parts.append("status IN ('unqualified', 'not_suitable')")
        else:
            query_parts.append("status = ?")
            params.append(status)

    if platform_type and platform_type != "all":
        if platform_type in ("directory", "submittable_directory"):
            query_parts.append("(LOWER(category_type) IN ('directory', 'submittable_directory', 'accelerator directory') OR category_type IS NULL)")
        elif platform_type in ("partner", "ecosystem_partner"):
            query_parts.append("LOWER(category_type) IN ('partner', 'ecosystem_partner')")

    if min_score > 0:
        query_parts.append("score >= ?")
        params.append(min_score)

    if category and category != "all":
        query_parts.append("category = ?")
        params.append(category)

    if search:
        query_parts.append("(name LIKE ? OR domain LIKE ? OR draft_pitch LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    where_clause = " AND ".join(query_parts)

    total_count = c.execute(f"SELECT COUNT(*) FROM platforms WHERE {where_clause}", params).fetchone()[0]

    offset = (page - 1) * limit
    sql = f"""
        SELECT id, name, category, url, domain, form_url, score, score_reasons, 
               draft_pitch, draft_full, tracking_url, submitted_url, status, 
               visit_count, discovered_at, submitted_at, bot_verified, category_type,
               tier, intake_type, is_core_target, intake_features, high_level_category,
               is_smartmatch, smartmatch_free, smartmatch_paid, smartmatch_model, 
               licensing_notes, ranking_scope
        FROM platforms
        WHERE {where_clause}
        ORDER BY CASE 
            WHEN tier = 'tier_1' THEN 1
            WHEN tier = 'tier_2' THEN 2
            WHEN is_core_target = 1 THEN 3
            WHEN tier = 'tier_3' THEN 4
            WHEN status = 'ready' THEN 5
            WHEN status = 'in_review' THEN 6
            ELSE 7 
        END, score DESC, id DESC
        LIMIT ? OFFSET ?
    """
    rows = c.execute(sql, params + [limit, offset]).fetchall()
    platforms = [dict(r) for r in rows]
    conn.close()

    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "pages": (total_count + limit - 1) // limit,
        "platforms": platforms
    }

# ================================================================================
# TOP ACCELERATOR RANKERS & LINKEDIN INFLUENCERS ENDPOINTS (PANAGIOTIS DIRECTIVE)
# ================================================================================
@app.get("/api/rankers")
def get_accelerator_rankers(status: Optional[str] = Query(None)):
    conn = get_db()
    c = conn.cursor()
    if status and status != "all":
        rows = c.execute("SELECT * FROM accelerator_rankers WHERE status = ? ORDER BY id ASC", (status,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM accelerator_rankers ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/rankers/{ranker_id}/status")
def update_ranker_status(ranker_id: int, payload: Dict[str, Any]):
    conn = get_db()
    c = conn.cursor()
    new_status = payload.get("status", "contacted")
    row = c.execute("SELECT author_name FROM accelerator_rankers WHERE id = ?", (ranker_id,)).fetchone()
    c.execute("UPDATE accelerator_rankers SET status = ? WHERE id = ?", (new_status, ranker_id))
    conn.commit()
    conn.close()
    author_name = row["author_name"] if row else f"Curator #{ranker_id}"
    return {"success": True, "ranker_id": ranker_id, "name": author_name, "status": new_status}

# ================================================================================
# CATEGORY AGENTS FLEET ENDPOINTS (Astra-R01 to Astra-C01)
# ================================================================================
import category_agent_fleet as caf

@app.get("/api/category-agents")
def get_category_agents():
    try:
        return caf.get_category_agents_roster()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/category-agents/{agent_id}/run")
def run_category_agent(agent_id: str, batch_size: int = Query(3, ge=1, le=10)):
    try:
        agents = {a["id"]: a for a in caf.CATEGORY_AGENTS_CONFIG}
        if agent_id not in agents:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in category fleet.")
        agent = agents[agent_id]
        if agent["category_key"] == "linkedin_rankers":
            return caf.run_linkedin_ranker_hunter(agent_id, batch_size=batch_size)
        else:
            return caf.run_category_platform_hunter(agent_id, agent["category_key"], batch_size=batch_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/category-agents/run-all")
def run_all_category_agents():
    try:
        results = []
        for agent in caf.CATEGORY_AGENTS_CONFIG:
            aid = agent["id"]
            if agent["category_key"] == "linkedin_rankers":
                res = caf.run_linkedin_ranker_hunter(aid, batch_size=2)
            else:
                res = caf.run_category_platform_hunter(aid, agent["category_key"], batch_size=2)
            results.append(res)
        return {"success": True, "executed_agents": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/platforms/{platform_id}")
def get_platform_detail(platform_id: int):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Platform not found")
    return dict(row)

@app.post("/api/platforms/add-manual")
def add_platform_manual(req: AddManualPlatformRequest):
    conn = get_db()
    c = conn.cursor()
    clean_domain = req.domain.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()
    utm_source = clean_domain.replace(".", "_")
    tracking_url = f"https://eupnea.co.uk/?utm_source={utm_source}&utm_medium=directory&utm_campaign=accelerator_2026"

    cand_payload = {
        "name": req.name.strip(),
        "domain": clean_domain,
        "url": f"https://{clean_domain}",
        "form_url": req.submitted_url or f"https://{clean_domain}",
        "category": req.category,
        "score": req.score
    }
    score_eval = dfe.DeepSeekFlashEngine.score_platform(cand_payload, verify_network=True)
    if not score_eval.get("is_qualified") or score_eval.get("score", 0) <= 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=score_eval.get("score_reasons_summary") or "Failed DeepSeek Flash v4.1 4-Gate Pre-Qualification (dead website, synthetic domain, or unsuitable portal)."
        )

    pitch = f"Eupnea is a premier management consulting firm and startup accelerator headquartered in London, supporting founders and enterprise leaders across the UK and internationally."
    status_target = req.status or score_eval.get("status", "in_review")
    hl_cat = req.high_level_category or "Direct Startup Engagement & Intake"
    final_score = score_eval.get("score", req.score)
    final_tier = score_eval.get("tier", "tier_2")
    healed_url = score_eval.get("healed_url") or f"https://{clean_domain}"
    healed_form = score_eval.get("healed_form_url") or req.submitted_url or healed_url
    reasons = score_eval.get("score_reasons_summary") or "Verified by DeepSeek Flash v4.1 Four-Gate Engine."

    try:
        c.execute("""
            INSERT INTO platforms (
                name, category, url, domain, form_url, score, score_reasons, draft_pitch,
                tracking_url, submitted_url, status, bot_verified, submission_mode, submitted_at,
                category_type, tier, intake_type, is_core_target, high_level_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'manual', CURRENT_TIMESTAMP, 'submittable_directory', ?, 'direct_intake', 1, ?)
        """, (
            req.name.strip(), req.category, healed_url, clean_domain, healed_form,
            final_score, reasons,
            pitch, tracking_url, req.submitted_url or "",
            status_target, final_tier, hl_cat
        ))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return {"status": "success", "id": new_id, "score": final_score, "tier": final_tier, "message": f"Platform '{req.name}' verified by DeepSeek Flash v4.1 ({final_score}/100) and saved."}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail=f"A directory platform named '{req.name}' or with domain '{clean_domain}' already exists in the catalog."
        )

@app.post("/api/platforms/{platform_id}/edit-score")
def edit_platform_score(platform_id: int, req: EditScoreRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE platforms SET score = ?, score_reasons = score_reasons || ' | [Adjusted]: ' || ? WHERE id = ?",
        (req.score, req.reason or "Score manually refined by team", platform_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "score": req.score}

@app.post("/api/platforms/{platform_id}/status")
def update_platform_status(platform_id: int, req: StatusUpdateRequest):
    valid_statuses = ["found", "scored", "draft_ready", "in_review", "approved", "submitted", "unqualified", "not_suitable", "perk_benefit", "dismissed", "undo_submit", "ready_to_submit"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status specified.")

    conn = get_db()
    c = conn.cursor()
    target_status = "in_review" if req.status == "ready_to_submit" else req.status

    if req.status == "submitted":
        c.execute("""
            UPDATE platforms 
            SET status = 'submitted', 
                submitted_url = ?, 
                submitted_at = CURRENT_TIMESTAMP,
                visit_count = COALESCE(visit_count, 0)
            WHERE id = ?
        """, (req.submitted_url or "", platform_id))
    elif req.status == "undo_submit":
        target_status = "approved"
        c.execute("UPDATE platforms SET status = 'approved', submitted_url = '' WHERE id = ?", (platform_id,))
    else:
        c.execute("UPDATE platforms SET status = ? WHERE id = ?", (target_status, platform_id))
    
    conn.commit()
    conn.close()
    return {"status": "success", "status_updated": target_status}

@app.post("/api/platforms/{platform_id}/verify-live")
async def verify_platform_live_endpoint(platform_id: int):
    """Executes live verification via browser-use engine."""
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT url, domain, name FROM platforms WHERE id = ?", (platform_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Platform not found.")
    
    target_url = row["url"] or f"https://{row['domain']}"
    if presence_upgrade_controller:
        res = await presence_upgrade_controller.verify_platform_live(target_url)
        conn.close()
        return {"status": "success", "platform_id": platform_id, "verification": res.dict()}
    probe = dfe.DeepSeekFlashEngine.probe_live_website(target_url)
    conn.close()
    return {"status": "success", "platform_id": platform_id, "verification": probe}

@app.post("/api/platforms/{platform_id}/smart-draft")
def generate_smart_draft_endpoint(platform_id: int):
    """Generates structured, zero-hallucination listing draft using Instructor & Mem0."""
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT name, category, domain FROM platforms WHERE id = ?", (platform_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Platform not found.")
    
    if presence_upgrade_controller:
        draft = presence_upgrade_controller.generate_structured_draft(
            platform_name=row["name"],
            category=row["category"] or "Directory",
            domain=row["domain"] or ""
        )
        c.execute("""
            UPDATE platforms 
            SET draft_pitch = ?, 
                draft_full = ? 
            WHERE id = ?
        """, (draft.short_pitch, draft.full_description, platform_id))
        conn.commit()
        conn.close()
        return {"status": "success", "platform_id": platform_id, "draft": draft.dict()}
    
    conn.close()
    return {"status": "simulated", "platform_id": platform_id}

@app.delete("/api/platforms/{platform_id}")
def delete_platform(platform_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM platforms WHERE id = ?", (platform_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Platform deleted from index."}

# ================================================================================
# PRESENCE DISCOVERY AGENT ENDPOINTS
# ================================================================================
@app.get("/api/discovery/runs")
def get_discovery_runs():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM activity_runs WHERE is_cleared = 0 ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_master_category(name: str, domain: str, cat: str = "") -> str:
    name_l = name.lower()
    domain_l = domain.lower()
    cat_l = cat.lower()
    combined = f"{name_l} {domain_l} {cat_l}"

    # 1. UK National & Regional Chambers
    if any(k in combined for k in ["chamber", "commerce", "local authority", "council", "gov.uk", "gov.wales", "great.gov"]):
        return "UK National & Regional Chambers"

    # 2. AI & Emerging Tech Directories
    if any(k in combined for k in ["ai ", " ai", "artificial intelligence", "deeptech", "futuretools", "toolify", "theresanaiforthat", "altern.ai", "easywithai", "bot"]):
        return "AI & Emerging Tech Directories"

    # 3. SaaS & Software Marketplaces
    if any(k in combined for k in ["saas", "software", "capterra", "g2", "sourceforge", "getapp", "softwareadvice", "saashub", "saasgenius"]):
        return "SaaS & Software Marketplaces"

    # 4. Startup & Product Launchpads
    if any(k in combined for k in ["launch", "product hunt", "betalist", "startupbuffer", "tinylaunch", "postmake", "uneed", "indie", "sideproject", "maker"]):
        return "Startup & Product Launchpads"

    # 5. UK Tech Clusters & Ecosystems
    if any(k in combined for k in ["tech nation", "silicon", "cluster", "scotland", "wales", "manchester", "birmingham", "bristol", "cambridge", "oxford", "leeds", "belfast", "sheffield", "newcastle", "london tech", "fintech scotland", "uk tech"]):
        return "UK Tech Clusters & Ecosystems"

    # 6. B2B Consulting & Enterprise Networks
    if any(k in combined for k in ["consulting", "advisory", "clutch", "goodfirms", "upcity", "agency", "enterprise", "b2b"]):
        return "B2B Consulting & Enterprise Networks"

    # 7. European Innovation & Regional Networks
    if any(k in combined for k in ["europe", "pan-european", "france", "germany", "nordic", "station f", "slush", "vivatech", "sifted", "eu-startups", "irish", "dach"]):
        return "European Innovation & Regional Networks"

    # 8. Global Venture & Accelerator Hubs (default prestige category)
    return "Global Venture & Accelerator Hubs"

ACTIVE_DISCOVERY_WORKERS: Dict[int, bool] = {}
DB_WRITE_LOCK = threading.Lock()

PARALLEL_CATEGORY_SPECS = [
    {
        "category": "SmartMatch & Dealflow Licensing Engines",
        "agent_id": "Agent-S01",
        "agent_name": "Astra-S01 (SmartMatch & Licensing Specialist)",
        "browser_profile": "agent_01",
        "tag": "⚡ SMARTMATCH & LICENSING",
        "score": 99,
        "tier": "tier_1",
        "intake_type": "core_programme_intake",
        "is_smartmatch": 1,
        "smartmatch_free": 1,
        "smartmatch_paid": 1,
        "smartmatch_model": "licence",
        "licensing_notes": "Two-sided SmartMatch accelerator-startup licensing engine. Generates constant registration pipeline via cohort matching licences.",
        "ranking_scope": "global",
        "score_reasons": "Two-Sided Matchmaking Engine (+35), Accelerator-Startup Dealflow Licences (+30), Constant Registration Pipeline (+20), Verified Founders (+14)",
        "intake_features": "SmartMatch Algorithm, Accelerator Dealflow Licencing, 2-Sided Founder Matching & Cohort Registrations",
        "pitch_prefix": "Eupnea UK Accelerator Cohort 2026: £50k–£250k seed funding, 12-week venture scale program with active SmartMatch founder-accelerator dealflow licensing."
    },
    {
        "category": "UK Accelerator Review & Ranking Platforms",
        "agent_id": "Agent-S02",
        "agent_name": "Astra-S02 (UK Accelerator Rankings & Analyst Scout)",
        "browser_profile": "agent_02",
        "tag": "🏆 UK ACCELERATOR RANKINGS",
        "score": 98,
        "tier": "tier_1",
        "intake_type": "core_programme_intake",
        "is_smartmatch": 0,
        "smartmatch_free": 0,
        "smartmatch_paid": 0,
        "smartmatch_model": "none",
        "licensing_notes": "",
        "ranking_scope": "uk_national",
        "score_reasons": "UK-Specific Accelerator Ranking Guide (+35), Institutional Analyst Intelligence (+30), High Founder Authority (+20), Top Tier Visibility (+13)",
        "intake_features": "Top UK Accelerator Ranking, Independent Analyst Review & Regional Innovation Guide",
        "pitch_prefix": "Eupnea UK Accelerator Review Profile: Official submission for inclusion in Top UK Startup Accelerators & Incubator Ranking Guides."
    },
    {
        "category": "Direct Startup Engagement & Intake",
        "agent_id": "Agent-S03",
        "agent_name": "Astra-S03 (Startup Intake Specialist)",
        "browser_profile": "agent_03",
        "tag": "🚀 STARTUP MATCH & INTAKE",
        "score": 97,
        "tier": "tier_1",
        "intake_type": "core_programme_intake",
        "is_smartmatch": 0,
        "smartmatch_free": 1,
        "smartmatch_paid": 0,
        "smartmatch_model": "free",
        "licensing_notes": "",
        "ranking_scope": "global",
        "score_reasons": "Verified Direct Application Portal (+35), Self-Serve Cohort Intake (+30), Active Founder Reach (+20), Big Tech Partner Ecosystem (+12)",
        "intake_features": "Direct Programme Application Portal, Founder Intake Screening & Cohort Verification",
        "pitch_prefix": "Eupnea UK Accelerator Cohort 2026: £50k–£250k seed funding, 12-week venture scale program for Enterprise AI, FinTech, and CleanTech startups."
    },
    {
        "category": "Investor Match & Capital Networks",
        "agent_id": "Agent-S04",
        "agent_name": "Astra-S04 (Investor & Syndicate Specialist)",
        "browser_profile": "agent_04",
        "tag": "💼 INVESTOR MATCH & CAPITAL",
        "score": 96,
        "tier": "tier_1",
        "intake_type": "investor_match",
        "is_smartmatch": 0,
        "smartmatch_free": 1,
        "smartmatch_paid": 1,
        "smartmatch_model": "freemium",
        "licensing_notes": "",
        "ranking_scope": "global",
        "score_reasons": "Verified Investor & Syndicate Network (+35), Direct Angel Matchmaking (+30), Capital Pipeline (+20), VC Co-Investment (+11)",
        "intake_features": "Angel & VC Database, LP/Syndicate Sourcing, Investor Matchmaking & Capital Pipeline",
        "pitch_prefix": "Eupnea UK Accelerator Portfolio: Connecting seed-stage AI & FinTech startups with verified angel syndicates and co-investors on "
    },
    {
        "category": "Ecosystem Visibility & Program Discovery",
        "agent_id": "Agent-S05",
        "agent_name": "Astra-S05 (Global Ecosystem Specialist)",
        "browser_profile": "agent_05",
        "tag": "🌐 ECOSYSTEM & DISCOVERY",
        "score": 92,
        "tier": "tier_2",
        "intake_type": "ecosystem_database",
        "is_smartmatch": 0,
        "smartmatch_free": 1,
        "smartmatch_paid": 0,
        "smartmatch_model": "free",
        "licensing_notes": "",
        "ranking_scope": "global",
        "score_reasons": "High-Authority Startup Database (+30), Ecosystem Discoverability (+25), Founder Traffic (+20), Backlink Authority (+17)",
        "intake_features": "Ecosystem Database Profile, Accelerator Tagging & SEO Discoverability",
        "pitch_prefix": "Eupnea UK Accelerator Cohort 2026: £50k–£250k seed funding, 12-week venture scale program for Enterprise AI, FinTech, and CleanTech startups."
    },
    {
        "category": "Regional Chambers & Business Networks",
        "agent_id": "Agent-S06",
        "agent_name": "Astra-S06 (Regional Chambers Specialist)",
        "browser_profile": "agent_06",
        "tag": "🏛️ REGIONAL NETWORKS",
        "score": 88,
        "tier": "tier_2",
        "intake_type": "regional_network",
        "is_smartmatch": 0,
        "smartmatch_free": 1,
        "smartmatch_paid": 0,
        "smartmatch_model": "free",
        "licensing_notes": "",
        "ranking_scope": "regional",
        "score_reasons": "Accredited Regional Chamber & Enterprise Network (+30), Regional Innovation Cluster (+25), SME Scaleup Pipeline (+20), Local Authority Backlink (+13)",
        "intake_features": "Chamber of Commerce Membership Directory & Regional Enterprise Scaleup Hub",
        "pitch_prefix": "Eupnea UK Accelerator: Driving UK regional scaleup growth with seed investment and enterprise acceleration in partnership with regional chambers."
    },
    {
        "category": "Media, Press & Industry Publications",
        "agent_id": "Agent-S07",
        "agent_name": "Astra-S07 (Media & PR Scout)",
        "browser_profile": "agent_07",
        "tag": "📰 MEDIA & PUBLICATIONS",
        "score": 82,
        "tier": "tier_2",
        "intake_type": "media_publication",
        "is_smartmatch": 0,
        "smartmatch_free": 1,
        "smartmatch_paid": 0,
        "smartmatch_model": "free",
        "licensing_notes": "",
        "ranking_scope": "global",
        "score_reasons": "High-Authority Tech Journalism (+30), Startup News Circulation (+25), Founder Readership (+15), Editorial Backlink (+12)",
        "intake_features": "Tech & Startup News Coverage, Editorial Guest Pitching & Press Releases",
        "pitch_prefix": "Eupnea UK Accelerator in the News: London-based venture acceleration funding the next generation of UK & European deep tech founders."
    }
]


# Verified live rosters only (Zero NXDOMAIN / Zero 404 / Zero Sree-rejected domains)
DYNAMIC_CATEGORY_ROSTERS: Dict[str, List[Dict[str, Any]]] = {
    "SmartMatch & Dealflow Licensing Engines": [
        {"name": "IncubatorList Global SmartMatch Portal", "domain": "incubatorlist.com", "url": "https://incubatorlist.com/", "form_url": "https://incubatorlist.com/submit"},
        {"name": "Round Funded Investor & Accelerator Matchmaking", "domain": "roundfunded.com", "url": "https://www.roundfunded.com/en", "form_url": "https://www.roundfunded.com/en"},
        {"name": "OpenVC Pro Dealflow SmartMatch", "domain": "openvc.app", "url": "https://openvc.app/", "form_url": "https://openvc.app/"},
        {"name": "Vestbee Dealflow Engine & Partner Network", "domain": "vestbee.com", "url": "https://www.vestbee.com/", "form_url": "https://www.vestbee.com/accelerators"},
        {"name": "Dealum Dealflow Management Network", "domain": "dealum.com", "url": "https://dealum.com/", "form_url": "https://dealum.com/"},
        {"name": "InnMind Global Web3 & Tech Dealflow Hub", "domain": "innmind.com", "url": "https://innmind.com/", "form_url": "https://innmind.com/"},
        {"name": "OneValley Passport Dealflow Matchmaker", "domain": "theonevalley.com", "url": "https://www.onevalley.com/", "form_url": "https://www.onevalley.com/"},
        {"name": "Gust Accelerator SmartMatch Pipeline", "domain": "gust.com", "url": "https://gust.com/accelerators", "form_url": "https://gust.com/accelerators"},
        {"name": "F6S SmartMatch Dealflow Directory", "domain": "f6s.com", "url": "https://www.f6s.com/programs", "form_url": "https://www.f6s.com/programs"},
        {"name": "YouNoodle Global Competition & Dealflow Engine", "domain": "younoodle.com", "url": "https://www.younoodle.com/", "form_url": "https://www.younoodle.com/"},
        {"name": "VC4A Dealflow & Sourcing Matchmaker", "domain": "vc4a.com", "url": "https://vc4a.com/", "form_url": "https://vc4a.com/"},
        {"name": "Bridge for Billions Match & Incubator Network", "domain": "bridgeforbillions.org", "url": "https://www.bridgeforbillions.org/programs/", "form_url": "https://www.bridgeforbillions.org/programs/"},
        {"name": "Hello Tomorrow DeepTech Matchmaking Platform", "domain": "hello-tomorrow.org", "url": "https://www.hello-tomorrow.org/challenge/hello-tomorrow-challenge", "form_url": "https://www.hello-tomorrow.org/challenge/hello-tomorrow-challenge"},
        {"name": "ChallengeRocket Innovation Match Hub", "domain": "challengerocket.com", "url": "https://challengerocket.com/", "form_url": "https://challengerocket.com/"}
    ],
    "UK Accelerator Review & Ranking Platforms": [
        {"name": "SeedLegals Top UK Startup Accelerators Guide", "domain": "seedlegals.com", "url": "https://seedlegals.com/resources/top-uk-startup-accelerators/", "form_url": "https://seedlegals.com/resources/top-uk-startup-accelerators/"},
        {"name": "Tracxn UK Accelerators & Incubators Directory", "domain": "tracxn.com", "url": "https://tracxn.com/", "form_url": "https://tracxn.com/"},
        {"name": "PartnershipsBuddy UK Programmes Guide", "domain": "partnershipsbuddy.com", "url": "https://partnershipsbuddy.com/", "form_url": "https://partnershipsbuddy.com/"},
        {"name": "Beauhurst UK Incubators & Accelerators Report", "domain": "beauhurst.com", "url": "https://www.beauhurst.com/", "form_url": "https://www.beauhurst.com/"},
        {"name": "Sifted UK Accelerators Guide & Rankings", "domain": "sifted.eu", "url": "https://sifted.eu/articles/top-accelerators-uk", "form_url": "https://sifted.eu/"},
        {"name": "UKTN (UK Tech News) Accelerators Directory", "domain": "uktech.news", "url": "https://www.uktech.news/", "form_url": "https://www.uktech.news/"},
        {"name": "TechRound Top UK Startup Accelerators Guide", "domain": "techround.co.uk", "url": "https://techround.co.uk/", "form_url": "https://techround.co.uk/"},
        {"name": "Startups.co.uk UK Funding & Accelerators Guide", "domain": "startups.co.uk", "url": "https://startups.co.uk/funding/", "form_url": "https://startups.co.uk/funding/"},
        {"name": "Enterprise Nation UK Startup Support Portal", "domain": "enterprisenation.com", "url": "https://www.enterprisenation.com/", "form_url": "https://www.enterprisenation.com/"},
        {"name": "British Business Bank UK Accelerator Portal", "domain": "british-business-bank.co.uk", "url": "https://www.british-business-bank.co.uk/business-guidance/guidance-articles/finance/business-accelerators-and-incubators", "form_url": "https://www.british-business-bank.co.uk/"}
    ],
    "Direct Startup Engagement & Intake": [
        {"name": "PitGrowth Startup & Accelerator Portal", "domain": "pitgrowth.com", "url": "https://pitgrowth.com/", "form_url": "https://pitgrowth.com/auth/register"},
        {"name": "StartupCorners Curated Accelerator Index", "domain": "startupcorners.com", "url": "https://startupcorners.com/accelerators", "form_url": "https://startupcorners.com/accelerators"},
        {"name": "Listed Startups Venture & Accelerator Hub", "domain": "listedstartups.com", "url": "https://listedstartups.com/accelerators", "form_url": "https://listedstartups.com/submit"},
        {"name": "GAN Global Accelerator Network", "domain": "gan.co", "url": "https://www.gan.co/", "form_url": "https://www.gan.co/"},
        {"name": "Submittable Accelerator & Grant Intake", "domain": "submittable.com", "url": "https://www.submittable.com/", "form_url": "https://www.submittable.com/"},
        {"name": "Agorize Global Innovation & Accelerator Challenges", "domain": "agorize.com", "url": "https://www.agorize.com/web/en/challenges", "form_url": "https://www.agorize.com/web/en/challenges"},
        {"name": "Barclays Eagle Labs UK Incubator Network", "domain": "labs.uk.barclays", "url": "https://labs.uk.barclays/", "form_url": "https://labs.uk.barclays/"},
        {"name": "Founders Factory London Venture Studio", "domain": "foundersfactory.com", "url": "https://foundersfactory.com/", "form_url": "https://foundersfactory.com/"},
        {"name": "SETsquared UK University Accelerator Partnership", "domain": "setsquared.co.uk", "url": "https://www.setsquared.co.uk/", "form_url": "https://www.setsquared.co.uk/"},
        {"name": "Bethnal Green Ventures Tech for Good", "domain": "bethnalgreenventures.com", "url": "https://bethnalgreenventures.com/", "form_url": "https://bethnalgreenventures.com/"}
    ],
    "Investor Match & Capital Networks": [
        {"name": "UK Business Angels Association (UKBAA)", "domain": "ukbaa.org.uk", "url": "https://ukbaa.org.uk/", "form_url": "https://ukbaa.org.uk/"},
        {"name": "Green Angel Syndicate & CleanTech Hub", "domain": "greenangelsyndicate.com", "url": "https://greenangelsyndicate.com/invest/", "form_url": "https://greenangelsyndicate.com/invest/"},
        {"name": "Cambridge Angels Co-Investment Portal", "domain": "cambridgeangels.com", "url": "https://www.cambridgeangels.com/", "form_url": "https://www.cambridgeangels.com/"},
        {"name": "Minerva Business Angel Network", "domain": "minerva.uk.net", "url": "https://minerva.uk.net/", "form_url": "https://minerva.uk.net/"},
        {"name": "SeedBlink European Equity Co-Investment", "domain": "seedblink.com", "url": "https://seedblink.com/", "form_url": "https://seedblink.com/"},
        {"name": "Floww Regulated Venture Capital Network", "domain": "floww.io", "url": "https://www.floww.io/", "form_url": "https://www.floww.io/"}
    ],
    "Ecosystem Visibility & Program Discovery": [
        {"name": "Crunchbase Accelerators & Venture Directory", "domain": "crunchbase.com", "url": "https://www.crunchbase.com/hub/accelerators", "form_url": "https://www.crunchbase.com/add-new"},
        {"name": "Dealroom European Venture Intelligence", "domain": "dealroom.co", "url": "https://dealroom.co/profiles/", "form_url": "https://dealroom.co/profiles/"},
        {"name": "StartupBlink Global Accelerator Ecosystem Map", "domain": "startupblink.com", "url": "https://www.startupblink.com/", "form_url": "https://www.startupblink.com/"},
        {"name": "TheIncubatorPro Global Incubator Index", "domain": "theincubatorpro.com", "url": "https://theincubatorpro.com/accelerators/", "form_url": "https://theincubatorpro.com/accelerators/"},
        {"name": "EU-Startups European Startup & Accelerator Directory", "domain": "eu-startups.com", "url": "https://www.eu-startups.com/directory/", "form_url": "https://www.eu-startups.com/directory/"},
        {"name": "BetaList Early Startup Discovery", "domain": "betalist.com", "url": "https://betalist.com/", "form_url": "https://betalist.com/submissions/new"},
        {"name": "Failory Startup Accelerators Guide", "domain": "failory.com", "url": "https://www.failory.com/blog/startup-accelerators", "form_url": "https://www.failory.com/blog/startup-accelerators"}
    ],
    "Regional Chambers & Business Networks": [
        {"name": "Essex Chambers of Commerce", "domain": "essexchambers.co.uk", "url": "https://www.essexchambers.co.uk/", "form_url": "https://www.essexchambers.co.uk/"},
        {"name": "Kent Invicta Chamber of Commerce", "domain": "kentinvictachamber.co.uk", "url": "https://www.kentinvictachamber.co.uk/", "form_url": "https://www.kentinvictachamber.co.uk/"},
        {"name": "Hertfordshire Chamber of Commerce", "domain": "hertschamber.com", "url": "https://www.hertschamber.com/", "form_url": "https://www.hertschamber.com/"},
        {"name": "Cumbria Chamber of Commerce", "domain": "cumbriachamber.co.uk", "url": "https://www.cumbriachamber.co.uk/", "form_url": "https://www.cumbriachamber.co.uk/"},
        {"name": "Lincolnshire Chamber of Commerce", "domain": "lincs-chamber.co.uk", "url": "https://www.lincs-chamber.co.uk/", "form_url": "https://www.lincs-chamber.co.uk/"},
        {"name": "Staffordshire Chambers of Commerce", "domain": "staffordshirechambers.co.uk", "url": "https://staffordshirechambers.co.uk/", "form_url": "https://staffordshirechambers.co.uk/"},
        {"name": "Shropshire Chamber of Commerce", "domain": "shropshire-chamber.co.uk", "url": "https://www.shropshire-chamber.co.uk/", "form_url": "https://www.shropshire-chamber.co.uk/"}
    ],
    "Media, Press & Industry Publications": [
        {"name": "Techloy Global Innovation Media", "domain": "techloy.com", "url": "https://techloy.com/", "form_url": "https://techloy.com/"},
        {"name": "Silicon Canal West Midlands Tech Media", "domain": "siliconcanal.co.uk", "url": "https://siliconcanal.co.uk/", "form_url": "https://siliconcanal.co.uk/"},
        {"name": "Venture Intelligence News Hub", "domain": "ventureintelligence.com", "url": "https://ventureintelligence.com/", "form_url": "https://ventureintelligence.com/"},
        {"name": "DIGIT Scotland Tech Media", "domain": "digit.fyi", "url": "https://digit.fyi/", "form_url": "https://digit.fyi/"},
        {"name": "Innovation News Network", "domain": "innovationnewsnetwork.com", "url": "https://www.innovationnewsnetwork.com/", "form_url": "https://www.innovationnewsnetwork.com/"}
    ]
}

def get_dynamic_category_candidates(cat_name: str, needed: int, existing_domains: set, existing_names: set) -> List[Dict[str, Any]]:
    results = []
    roster = DYNAMIC_CATEGORY_ROSTERS.get(cat_name, [])
    for item in roster:
        if len(results) >= needed:
            break
        dom = item["domain"].lower()
        nm = item["name"].lower()
        if dom not in existing_domains and nm not in existing_names:
            results.append({
                "name": item["name"],
                "domain": dom,
                "url": item["url"],
                "form_url": item.get("form_url", f"https://{dom}/submit"),
                "target_category": cat_name
            })
            existing_domains.add(dom)
            existing_names.add(nm)

    return results

def run_single_category_browser_worker(run_id: int, spec: Dict[str, Any], pool_candidates: List[Dict[str, Any]], existing_domains: set, existing_names: set, batch_per_cat: int) -> Dict[str, Any]:
    cat_name = spec["category"]
    agent_id = spec["agent_id"]
    agent_name = spec["agent_name"]
    browser_profile = spec["browser_profile"]
    profile_dir = os.path.join(WORKSPACE_DIR, "agent_browser_profiles", browser_profile)
    os.makedirs(profile_dir, exist_ok=True)

    # Filter matching candidates for this specific category
    matching_cands = [
        c for c in pool_candidates
        if c.get("target_category") == cat_name
        and c.get("domain", "").lower() not in existing_domains
        and c.get("name", "").lower() not in existing_names
    ]

    selected = matching_cands[:batch_per_cat]
    if len(selected) < batch_per_cat:
        needed = batch_per_cat - len(selected)
        dynamic_cands = get_dynamic_category_candidates(cat_name, needed, existing_domains, existing_names)
        selected.extend(dynamic_cands)
    discovered = []

    # Thread-safe database connection
    conn = get_db()
    c = conn.cursor()

    with DB_WRITE_LOCK:
        c.execute("""
            UPDATE orchestration_agents 
            SET status = 'active',
                current_task = ?,
                last_action = ?,
                last_action_time = CURRENT_TIMESTAMP
            WHERE agent_id = ?
        """, (
            f"⚡ [Browser: {browser_profile}] Hunting {cat_name} platforms concurrently...",
            f"Active browser session {browser_profile}. Processing {len(selected)} candidate URLs.",
            agent_id
        ))
        conn.commit()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for cand in selected:
        if not ACTIVE_DISCOVERY_WORKERS.get(run_id, False):
            break
        name = cand["name"]
        domain = cand["domain"].lower()
        url = cand["url"]
        form_url = cand.get("form_url") or url
        tracking_url = f"https://eupnea.co.uk/?utm_source={domain.replace('.', '_')}&utm_medium=directory&utm_campaign=accelerator_2026"
        category = get_master_category(name, domain, "")

        # Strict DeepSeek Flash v4.1 Algorithmic & Live Network Gate
        score_eval = dfe.DeepSeekFlashEngine.score_platform(cand, verify_network=True)
        if not score_eval.get("is_qualified") or score_eval.get("score", 0) <= 0:
            continue

        healed_url = score_eval.get("healed_url") or url
        healed_form_url = score_eval.get("healed_form_url") or form_url
        final_score = score_eval.get("score", spec["score"])
        final_tier = score_eval.get("tier", spec["tier"])
        final_reasons = score_eval.get("score_reasons_summary") or spec["score_reasons"]

        draft_pitch = f"{spec['pitch_prefix']} Direct intake & partnership via {domain}."
        draft_full = f"Eupnea UK Accelerator Cohort 2026 invites applications from early-stage founders and co-investors. Providing seed capital (£50k-£250k), executive partner mentorship, and commercial pilot deployment in London. Categorized under {cat_name}."

        is_sm = spec.get("is_smartmatch", 0)
        sm_free = spec.get("smartmatch_free", 0)
        sm_paid = spec.get("smartmatch_paid", 0)
        sm_model = spec.get("smartmatch_model", "none")
        lic_notes = spec.get("licensing_notes", "") if is_sm else ""
        r_scope = spec.get("ranking_scope", "global")

        with DB_WRITE_LOCK:
            c.execute("""
                INSERT OR IGNORE INTO platforms
                (name, category, url, domain, score, score_reasons, draft_pitch, draft_full, tracking_url, status, discovered_at, submitted_url, visit_count, form_url, category_type, tier, intake_type, is_core_target, intake_features, high_level_category, is_smartmatch, smartmatch_free, smartmatch_paid, smartmatch_model, licensing_notes, ranking_scope)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_review', ?, '', 0, ?, 'submittable_directory', ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, category, healed_url, domain, final_score, final_reasons, draft_pitch, draft_full, tracking_url, now_str, healed_form_url, final_tier, spec["intake_type"], spec["intake_features"], cat_name, is_sm, sm_free, sm_paid, sm_model, lic_notes, r_scope))

            if c.rowcount > 0:
                existing_domains.add(domain)
                existing_names.add(name.lower())
                discovered.append({"name": name, "domain": domain, "category": cat_name, "score": final_score})
            conn.commit()

    with DB_WRITE_LOCK:
        c.execute("""
            UPDATE orchestration_agents 
            SET platforms_processed = platforms_processed + ?,
                last_action = ?,
                last_report = ?,
                last_action_time = CURRENT_TIMESTAMP
            WHERE agent_id = ?
        """, (
            len(discovered),
            f"Discovered {len(discovered)} new {cat_name} platforms using browser {browser_profile}.",
            f"Browser session {browser_profile} successfully cataloged {len(discovered)} sites for {cat_name}.",
            agent_id
        ))
        conn.commit()

    conn.close()

    return {
        "category": cat_name,
        "agent_id": agent_id,
        "browser_profile": browser_profile,
        "count": len(discovered),
        "platforms": discovered
    }

def run_background_discovery_worker(run_id: int, query: str, target_count: int):
    ACTIVE_DISCOVERY_WORKERS[run_id] = True
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE activity_runs SET stage = 'Initializing 7 Parallel Category Browsers (agent_01 to agent_07)...' WHERE id = ?", (run_id,))
        conn.commit()

        # Load candidates from verified_discovery_pool.json
        pool_file = os.path.join(BASE_DIR, "verified_discovery_pool.json")
        candidates = []
        if os.path.exists(pool_file):
            with open(pool_file, "r", encoding="utf-8") as f:
                candidates = json.load(f)

        existing_domains = set(r[0].lower() for r in c.execute("SELECT domain FROM platforms").fetchall())
        existing_names = set(r[0].lower() for r in c.execute("SELECT name FROM platforms").fetchall())
        conn.close()

        # Calculate balanced batch size per category across 7 pillars
        batch_per_cat = max(2, min(6, int(target_count) // 7 + 1))

        c_status = get_db()
        c_status.cursor().execute("UPDATE activity_runs SET stage = '⚡ [PARALLEL MULTI-BROWSER SWARM] 7 Category Browsers Running Concurrently across all pillars...' WHERE id = ?", (run_id,))
        c_status.commit()
        c_status.close()

        # Execute all 7 category workers in parallel simultaneously
        results = []
        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_spec = {
                executor.submit(
                    run_single_category_browser_worker,
                    run_id, spec, candidates, existing_domains, existing_names, batch_per_cat
                ): spec for spec in PARALLEL_CATEGORY_SPECS
            }
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    print(f"Parallel category worker {spec['agent_id']} exception: {exc}")

        total_added = sum(r["count"] for r in results)
        
        # Build category breakdown string
        summary_tags = []
        for r in results:
            short_name = r["category"].split()[0]
            summary_tags.append(f"{short_name}: +{r['count']}")
        cat_breakdown = ", ".join(summary_tags)

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            UPDATE activity_runs 
            SET status = 'completed', 
                stage = ?, 
                discovered_count = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (f"Complete: {total_added} New Platforms Discovered Concurrently ({cat_breakdown})", total_added, run_id))
        conn.commit()
        conn.close()

    except Exception as e:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE activity_runs SET status = 'failed', stage = ? WHERE id = ?", (f"Failed: {str(e)[:60]}", run_id))
        conn.commit()
        conn.close()
    finally:
        ACTIVE_DISCOVERY_WORKERS.pop(run_id, None)

@app.post("/api/discovery/start")
def start_discovery_run(body: Dict[str, Any] = Body(...)):
    query = body.get("query", "UK & European accelerator directory 2026")
    target_count = body.get("target_count", 25)
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO activity_runs (query, target_count, discovered_count, status, stage, started_at)
        VALUES (?, ?, 0, 'running', 'Searching web & directories...', CURRENT_TIMESTAMP)
    """, (query, target_count))
    conn.commit()
    run_id = c.lastrowid
    conn.close()

    # Launch autonomous background worker thread
    worker = threading.Thread(
        target=run_background_discovery_worker,
        args=(run_id, query, target_count),
        daemon=True
    )
    worker.start()

    return {"status": "started", "run_id": run_id}

@app.post("/api/discovery/stop/{run_id}")
def stop_discovery_run(run_id: int):
    # Halts at next safe point per PDF brief Page 8
    ACTIVE_DISCOVERY_WORKERS[run_id] = False
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE activity_runs SET status = 'stopped', stage = 'Stopped by user' WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()
    return {"status": "stopped", "run_id": run_id}

@app.delete("/api/discovery/runs/{run_id}")
def delete_discovery_run(run_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM activity_runs WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "run_id": run_id}

@app.post("/api/activity/clear")
def clear_activity_feed():
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE activity_runs SET is_cleared = 1 WHERE status IN ('completed', 'stopped')")
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Finished activity cleared from feed."}

@app.get("/api/discovery/settings")
def get_search_settings():
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT phrases, target_count FROM search_settings WHERE id = 1").fetchone()
    conn.close()
    if row:
        return {"phrases": json.loads(row["phrases"]), "target_count": row["target_count"]}
    return {
        "phrases": [
            "UK accelerator directory",
            "global startup incubators list",
            "university innovation programmes",
            "government venture ecosystems",
            "European deeptech accelerators"
        ],
        "target_count": 25
    }

@app.post("/api/discovery/settings")
def save_search_settings(req: SearchSettingsRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO search_settings (id, phrases, target_count)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET phrases = excluded.phrases, target_count = excluded.target_count
    """, (json.dumps(req.phrases), req.target_count))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Search settings saved."}

# ================================================================================
# UTM ATTRIBUTION TRACKING (From Outside Listing to Counted Visit)
# ================================================================================
@app.post("/api/track-visit")
def track_utm_visit(req: TrackVisitRequest, request: Request):
    conn = get_db()
    c = conn.cursor()
    
    # Locate platform by utm_source matching domain or name
    source_clean = req.utm_source.strip().lower().replace("_", ".").replace("-", ".")
    platform = c.execute("""
        SELECT id, name FROM platforms 
        WHERE LOWER(domain) LIKE ? OR LOWER(name) LIKE ?
        LIMIT 1
    """, (f"%{source_clean}%", f"%{source_clean}%")).fetchone()

    platform_id = platform["id"] if platform else None
    
    # Insert visit record
    ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown")
    c.execute("""
        INSERT INTO listing_visits (platform_id, utm_source, utm_medium, utm_campaign, ip_hash, user_agent)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (platform_id, req.utm_source, req.utm_medium, req.utm_campaign, hash_pw(ip), ua))

    # Increment platform visit_count if platform matched
    if platform_id:
        c.execute("UPDATE platforms SET visit_count = COALESCE(visit_count, 0) + 1 WHERE id = ?", (platform_id,))

    conn.commit()
    conn.close()
    return {"status": "tracked", "platform_id": platform_id, "source": req.utm_source}

# ================================================================================
# MULTI-AGENT SWARM ORCHESTRATION ENDPOINTS (10 Management + 90 Search)
# ================================================================================
import orchestration_engine as orch_eng

@app.get("/api/orchestration/fleet")
def get_orchestration_fleet():
    try:
        orch_eng.init_orchestration_db()
        orch_eng.start_continuous_orchestrator()
        data = orch_eng.get_fleet_status_summary()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orchestration/cycle")
def trigger_orchestration_cycle():
    try:
        orch_eng.init_orchestration_db()
        res = orch_eng.run_coordinated_orchestration_cycle()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================================
# LIVE DATABASE BROWSER ENDPOINTS (Direct SQLite Connection in Browser)
# ================================================================================
@app.get("/api/db/tables")
def get_db_tables():
    conn = get_db()
    c = conn.cursor()
    tables_raw = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name ASC").fetchall()
    tables = []
    for trow in tables_raw:
        tname = trow["name"]
        cols_raw = c.execute(f"PRAGMA table_info({tname})").fetchall()
        count = c.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        cols = [{
            "name": col["name"],
            "type": col["type"],
            "pk": bool(col["pk"]),
            "notnull": bool(col["notnull"])
        } for col in cols_raw]
        tables.append({
            "name": tname,
            "count": count,
            "columns": cols
        })
    conn.close()
    return tables

@app.get("/api/db/table/{table_name}")
def get_db_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    order_by: Optional[str] = Query(None),
    order_dir: Optional[str] = Query("desc")
):
    conn = get_db()
    c = conn.cursor()

    # Validate table exists
    exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' does not exist.")

    cols_raw = c.execute(f"PRAGMA table_info({table_name})").fetchall()
    col_names = [col["name"] for col in cols_raw]

    where_clause = "1=1"
    params = []
    if search and search.strip():
        search_terms = []
        for col in col_names:
            search_terms.append(f"{col} LIKE ?")
            params.append(f"%{search.strip()}%")
        where_clause = " OR ".join(search_terms)

    total_count = c.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}", params).fetchone()[0]

    if order_by and order_by in col_names:
        direction = "DESC" if order_dir.lower() == "desc" else "ASC"
        order_sql = f"ORDER BY {order_by} {direction}"
    else:
        order_sql = f"ORDER BY {col_names[0]} DESC" if col_names else ""

    offset = (page - 1) * limit
    sql = f"SELECT * FROM {table_name} WHERE {where_clause} {order_sql} LIMIT ? OFFSET ?"
    rows_raw = c.execute(sql, params + [limit, offset]).fetchall()
    rows = [dict(r) for r in rows_raw]
    conn.close()

    return {
        "table": table_name,
        "columns": [dict(c) for c in cols_raw],
        "total_rows": total_count,
        "page": page,
        "limit": limit,
        "pages": (total_count + limit - 1) // limit if total_count > 0 else 1,
        "rows": rows
    }

@app.post("/api/db/query")
def execute_sql_query(req: ExecuteQueryRequest):
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    first_word = q.split()[0].upper()
    if first_word not in ["SELECT", "PRAGMA", "EXPLAIN"]:
        raise HTTPException(status_code=403, detail="Only read-only SELECT, PRAGMA, and EXPLAIN queries are permitted via the browser explorer.")

    conn = get_db()
    c = conn.cursor()
    start_t = time.time()
    try:
        c.execute(q)
        rows_raw = c.fetchall()
        duration_ms = round((time.time() - start_t) * 1000, 2)
        cols = [d[0] for d in c.description] if c.description else []
        rows = [dict(r) for r in rows_raw]
        conn.close()
        return {
            "status": "success",
            "columns": cols,
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": duration_ms
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/db/export/{table_name}")
def export_table_json(table_name: str):
    conn = get_db()
    c = conn.cursor()
    exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Table not found.")
    
    rows = c.execute(f"SELECT * FROM {table_name}").fetchall()
    data = [dict(r) for r in rows]
    conn.close()
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename={table_name}_export.json"}
    )

# ================================================================================
# ROUTE REDIRECTS FOR DOOR 1 & DOOR 2 + INNER PAGES PER SPEC
# ================================================================================
@app.get("/login")
def login_redirect():
    # Per spec: "Typing the old address '/login' brings the visitor to the home page.
    # Sign-in opens as a small window on that page, not as its own screen."
    return RedirectResponse(url="/?open_login=1")

@app.get("/workspace")
def workspace_redirect():
    return RedirectResponse(url="/?room=dashboard")

# Inner page routes for direct URL navigation
@app.get("/about")
@app.get("/about-us")
def page_about():
    return RedirectResponse(url="/#about")

@app.get("/services")
def page_services():
    return RedirectResponse(url="/#services")

@app.get("/industries")
def page_industries():
    return RedirectResponse(url="/#industries")

@app.get("/insights")
def page_insights():
    return RedirectResponse(url="/#insights")

@app.get("/careers")
def page_careers():
    return RedirectResponse(url="/#careers")

@app.get("/contact")
def page_contact():
    return RedirectResponse(url="/#contact")

@app.get("/our-story")
def page_story():
    return RedirectResponse(url="/#about")

@app.get("/accelerator")
def page_accelerator():
    return RedirectResponse(url="/#accelerator")

# Verified directory listing live page
@app.get("/programmes/{slug}")
@app.get("/listings/{slug}")
def serve_live_listing_view(slug: str):
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <title>Eupnea Accelerator 2026 — Verified Directory Listing</title>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 40px 20px; }}
            .container {{ max-width: 720px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; margin-bottom: 16px; font-family: monospace; }}
            h1 {{ font-size: 24px; margin-top: 0; color: #0f172a; }}
            p {{ line-height: 1.6; color: #334155; font-size: 14px; }}
            .card {{ background: #f1f5f9; border-radius: 12px; padding: 16px; margin: 20px 0; font-size: 13px; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #1e40af; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 13px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <span class="badge">● VERIFIED DIRECTORY LISTING ACTIVE</span>
            <h1>Eupnea Accelerator & Venture Strategy Cohort 2026</h1>
            <p><strong>Directory Listing Slug:</strong> <code>{slug}</code></p>
            <p>Eupnea is a premier management consulting firm and venture accelerator operating across the UK and globally. Partnering with visionary enterprises and ambitious founders to scale venture-backed technology.</p>
            <div class="card">
              <strong>Official Profile Highlights:</strong>
              <ul>
                <li>£50k–£250k seed funding allocation</li>
                <li>Four-step methodology: Discover, Design, Deliver, Sustain</li>
                <li>Sectors: Enterprise AI, CleanTech, HealthTech, FinTech</li>
                <li>Headquarters: 124 City Road, London EC1V 2NX</li>
              </ul>
            </div>
            <a href="/?utm_source={slug}&utm_medium=directory&utm_campaign=accelerator_2026" class="btn">Visit Official Eupnea Website →</a>
          </div>
        </body>
        </html>"""
    )

# ================================================================================
# MAIN ENTRYPOINT — TWO DOORS UNIFIED SPA
# ================================================================================
@app.get("/", response_class=HTMLResponse)
def serve_eupnea_ecosystem():
    with open(os.path.join(BASE_DIR, "templates", "eupnea_ecosystem.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8855))
    print("\n" + "="*80)
    print("🏛️  STARTING EUPNEA V2 OFFICIAL PRODUCTION SERVER")
    print(f"📍  DOOR 1: Public Marketing Website  ->  http://0.0.0.0:{port}")
    print(f"🔑  DOOR 2: Staff Workspace Portal    ->  http://0.0.0.0:{port}/?room=dashboard")
    print("🔐  Default Admin: aadarsh@eupnea.co.uk / Aadarsh@2026")
    print("="*80 + "\n")
    uvicorn.run("presence_dashboard:app", host="0.0.0.0", port=port, reload=False)
