"""Postgres DB layer for GhostAgent SaaS.

All state that was previously stored in SQLite/JSON (guardrails, approval queue,
warmup state) is now stored here. Uses psycopg2 with a thread-safe connection pool.
"""

import os
import json
import threading
import psycopg2
import psycopg2.pool
from datetime import datetime, timezone

_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                db_url = os.getenv("DATABASE_URL")
                if not db_url:
                    raise RuntimeError("DATABASE_URL env var not set")
                _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, db_url)
    return _pool

def get_conn():
    return _get_pool().getconn()

def release_conn(conn):
    _get_pool().putconn(conn)

def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─── Users ───────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: str = None) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "User" ("id", "email", "passwordHash", "name", "createdAt", "updatedAt")
            VALUES (gen_random_uuid()::text, %s, %s, %s, NOW(), NOW())
            RETURNING "id", "email", "name", "createdAt"
        """, (email, password_hash, name))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "email": row[1], "name": row[2], "createdAt": str(row[3])}
    finally:
        cur.close()
        release_conn(conn)

def get_user_by_email(email: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "email", "name", "passwordHash", "createdAt"
            FROM "User" WHERE "email" = %s
        """, (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "name": row[2], "passwordHash": row[3], "createdAt": str(row[4])}
    finally:
        cur.close()
        release_conn(conn)

def get_user_by_id(user_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "email", "name", "createdAt"
            FROM "User" WHERE "id" = %s
        """, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "name": row[2], "createdAt": str(row[3])}
    finally:
        cur.close()
        release_conn(conn)


# ─── LinkedIn Accounts ───────────────────────────────────────────────────────

def get_accounts_for_user(user_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "userId", "sessionStatus", "linkedInName", "linkedInUrl",
                   "linkedInHeadline", "warmupStatus", "agentStatus", "lastSessionAt", "createdAt"
            FROM "LinkedInAccount" WHERE "userId" = %s ORDER BY "createdAt" DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "userId": r[1], "sessionStatus": r[2],
                "linkedInName": r[3], "linkedInUrl": r[4],
                "linkedInHeadline": r[5], "warmupStatus": r[6],
                "agentStatus": r[7],
                "lastSessionAt": str(r[8]) if r[8] else None,
                "createdAt": str(r[9])
            }
            for r in rows
        ]
    finally:
        cur.close()
        release_conn(conn)

def create_account(user_id: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "LinkedInAccount" ("id", "userId", "createdAt", "updatedAt")
            VALUES (gen_random_uuid()::text, %s, NOW(), NOW())
            RETURNING "id", "userId", "sessionStatus", "warmupStatus", "agentStatus"
        """, (user_id,))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "userId": row[1], "sessionStatus": row[2],
                "warmupStatus": row[3], "agentStatus": row[4]}
    finally:
        cur.close()
        release_conn(conn)

def get_account(account_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "userId", "liAt", "jsessionId", "sessionStatus",
                   "linkedInName", "linkedInUrl", "linkedInHeadline",
                   "warmupStatus", "warmupStartedAt", "warmupCompletedAt",
                   "warmupSessions", "warmupLikes", "warmupProfileViews",
                   "agentStatus", "lastSessionAt"
            FROM "LinkedInAccount" WHERE "id" = %s
        """, (account_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "userId": row[1], "liAt": row[2], "jsessionId": row[3],
            "sessionStatus": row[4], "linkedInName": row[5], "linkedInUrl": row[6],
            "linkedInHeadline": row[7], "warmupStatus": row[8],
            "warmupStartedAt": str(row[9]) if row[9] else None,
            "warmupCompletedAt": str(row[10]) if row[10] else None,
            "warmupSessions": row[11], "warmupLikes": row[12],
            "warmupProfileViews": row[13], "agentStatus": row[14],
            "lastSessionAt": str(row[15]) if row[15] else None,
        }
    finally:
        cur.close()
        release_conn(conn)

def get_account_cookies(account_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "liAt", "jsessionId" FROM "LinkedInAccount" WHERE "id" = %s
        """, (account_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        return {"li_at": row[0], "JSESSIONID": row[1]}
    finally:
        cur.close()
        release_conn(conn)

def update_account_session(account_id: str, li_at: str, jsessionid: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "LinkedInAccount"
            SET "liAt" = %s, "jsessionId" = %s, "sessionStatus" = 'CONNECTED', "updatedAt" = NOW()
            WHERE "id" = %s
        """, (li_at, jsessionid, account_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def update_account_status(account_id: str, status: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "LinkedInAccount"
            SET "agentStatus" = %s, "lastSessionAt" = NOW(), "updatedAt" = NOW()
            WHERE "id" = %s
        """, (status, account_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def update_warmup_state(account_id: str, warmup_status: str,
                        sessions_delta: int = 0, likes_delta: int = 0, views_delta: int = 0):
    conn = get_conn()
    try:
        cur = conn.cursor()
        extras = []
        params = []

        if warmup_status == "DAY_1" or warmup_status == "NOT_STARTED":
            pass
        if warmup_status == "DAY_1":
            extras.append('"warmupStartedAt" = NOW()')
        if warmup_status == "COMPLETED":
            extras.append('"warmupCompletedAt" = NOW()')

        set_clause = ', '.join([
            '"warmupStatus" = %s',
            '"warmupSessions" = "warmupSessions" + %s',
            '"warmupLikes" = "warmupLikes" + %s',
            '"warmupProfileViews" = "warmupProfileViews" + %s',
            '"updatedAt" = NOW()',
        ] + extras)

        cur.execute(f"""
            UPDATE "LinkedInAccount"
            SET {set_clause}
            WHERE "id" = %s
        """, (warmup_status, sessions_delta, likes_delta, views_delta, account_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def update_account_profile(account_id: str, name: str = None, url: str = None, headline: str = None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "LinkedInAccount"
            SET "linkedInName" = COALESCE(%s, "linkedInName"),
                "linkedInUrl" = COALESCE(%s, "linkedInUrl"),
                "linkedInHeadline" = COALESCE(%s, "linkedInHeadline"),
                "updatedAt" = NOW()
            WHERE "id" = %s
        """, (name, url, headline, account_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)


# ─── Guardrails (atomic check-and-increment) ─────────────────────────────────

def guardrail_check_and_increment(account_id: str, column: str, limit: int) -> bool:
    """Atomically checks if action is under limit and increments if so.

    Uses FOR UPDATE row locking so concurrent workers cannot race past the limit.
    Returns True if action is allowed (was under limit and was incremented).
    """
    today = _today()
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Ensure the row exists
        cur.execute("""
            INSERT INTO "Guardrail" ("id", "linkedInAccountId", "date")
            VALUES (gen_random_uuid()::text, %s, %s)
            ON CONFLICT ("linkedInAccountId", "date") DO NOTHING
        """, (account_id, today))
        conn.commit()

        # Lock row and atomically check + increment
        cur.execute(f"""
            SELECT "{column}" FROM "Guardrail"
            WHERE "linkedInAccountId" = %s AND "date" = %s
            FOR UPDATE
        """, (account_id, today))
        row = cur.fetchone()

        if row is None or row[0] >= limit:
            conn.rollback()
            return False

        cur.execute(f"""
            UPDATE "Guardrail"
            SET "{column}" = "{column}" + 1
            WHERE "linkedInAccountId" = %s AND "date" = %s
        """, (account_id, today))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        release_conn(conn)

def get_guardrail_counts(account_id: str) -> dict:
    today = _today()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "connectionsCount", "profileViewsCount", "likesCount",
                   "commentsCount", "messagesCount"
            FROM "Guardrail" WHERE "linkedInAccountId" = %s AND "date" = %s
        """, (account_id, today))
        row = cur.fetchone()
        if not row:
            return {"connections": 0, "profileViews": 0, "likes": 0, "comments": 0, "messages": 0}
        return {
            "connections": row[0], "profileViews": row[1], "likes": row[2],
            "comments": row[3], "messages": row[4], "date": today
        }
    finally:
        cur.close()
        release_conn(conn)


# ─── Campaigns ───────────────────────────────────────────────────────────────

def create_campaign(user_id: str, account_id: str, name: str, goal: str, **kwargs) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "Campaign" (
                "id", "userId", "linkedInAccountId", "name", "goal",
                "dailyConnectionLimit", "dailyMessageLimit", "activeHoursStart",
                "activeHoursEnd", "timezone", "autoApprove", "personaTone",
                "personaSample", "createdAt", "updatedAt"
            )
            VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING "id", "name", "goal", "status"
        """, (
            user_id, account_id, name, goal,
            kwargs.get("dailyConnectionLimit", 15),
            kwargs.get("dailyMessageLimit", 30),
            kwargs.get("activeHoursStart", 9),
            kwargs.get("activeHoursEnd", 18),
            kwargs.get("timezone", "Asia/Kolkata"),
            kwargs.get("autoApprove", False),
            kwargs.get("personaTone", "professional"),
            kwargs.get("personaSample"),
        ))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "name": row[1], "goal": row[2], "status": row[3]}
    finally:
        cur.close()
        release_conn(conn)

def get_campaigns_for_user(user_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT c."id", c."name", c."goal", c."status", c."linkedInAccountId",
                   c."dailyConnectionLimit", c."autoApprove", c."createdAt",
                   COUNT(DISTINCT p."id") as prospect_count,
                   SUM(CASE WHEN p."status" = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                   SUM(CASE WHEN p."status" = 'REQUESTED' THEN 1 ELSE 0 END) as requested_count,
                   SUM(CASE WHEN p."status" = 'REPLIED' THEN 1 ELSE 0 END) as replied_count
            FROM "Campaign" c
            LEFT JOIN "Prospect" p ON p."campaignId" = c."id"
            WHERE c."userId" = %s
            GROUP BY c."id"
            ORDER BY c."createdAt" DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "name": r[1], "goal": r[2], "status": r[3],
                "linkedInAccountId": r[4], "dailyConnectionLimit": r[5],
                "autoApprove": r[6], "createdAt": str(r[7]),
                "prospectCount": r[8], "pendingCount": r[9],
                "requestedCount": r[10], "repliedCount": r[11]
            }
            for r in rows
        ]
    finally:
        cur.close()
        release_conn(conn)

def get_campaign(campaign_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "userId", "linkedInAccountId", "name", "goal", "status",
                   "dailyConnectionLimit", "dailyMessageLimit", "activeHoursStart",
                   "activeHoursEnd", "timezone", "autoApprove", "personaTone",
                   "personaSample", "createdAt"
            FROM "Campaign" WHERE "id" = %s
        """, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        keys = ["id", "userId", "linkedInAccountId", "name", "goal", "status",
                "dailyConnectionLimit", "dailyMessageLimit", "activeHoursStart",
                "activeHoursEnd", "timezone", "autoApprove", "personaTone",
                "personaSample", "createdAt"]
        return dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in row]))
    finally:
        cur.close()
        release_conn(conn)

def update_campaign_status(campaign_id: str, status: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "Campaign" SET "status" = %s, "updatedAt" = NOW() WHERE "id" = %s
        """, (status, campaign_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def delete_campaign(campaign_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Cascade: delete messages, then prospects, then campaign
        cur.execute("""
            DELETE FROM "OutreachMessage"
            WHERE "prospectId" IN (
                SELECT "id" FROM "Prospect" WHERE "campaignId" = %s
            )
        """, (campaign_id,))
        cur.execute("""DELETE FROM "Prospect" WHERE "campaignId" = %s""", (campaign_id,))
        cur.execute("""DELETE FROM "Campaign" WHERE "id" = %s""", (campaign_id,))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def get_active_campaigns(account_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "name", "goal", "dailyConnectionLimit", "autoApprove",
                   "personaTone", "personaSample", "timezone"
            FROM "Campaign"
            WHERE "linkedInAccountId" = %s AND "status" = 'ACTIVE'
        """, (account_id,))
        rows = cur.fetchall()
        keys = ["id", "name", "goal", "dailyConnectionLimit", "autoApprove",
                "personaTone", "personaSample", "timezone"]
        return [dict(zip(keys, r)) for r in rows]
    finally:
        cur.close()
        release_conn(conn)


# ─── Prospects ───────────────────────────────────────────────────────────────

def create_prospect(campaign_id: str, linkedin_url: str,
                    name: str = None, headline: str = None,
                    company: str = None, notes: str = None) -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "Prospect" (
                "id", "campaignId", "linkedInUrl", "name", "headline",
                "company", "notes", "createdAt", "updatedAt"
            )
            VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT DO NOTHING
            RETURNING "id"
        """, (campaign_id, linkedin_url, name, headline, company, notes))
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        cur.close()
        release_conn(conn)

def bulk_create_prospects(campaign_id: str, prospects: list[dict]) -> int:
    if not prospects:
        return 0
    conn = get_conn()
    try:
        cur = conn.cursor()
        count = 0
        for p in prospects:
            cur.execute("""
                INSERT INTO "Prospect" (
                    "id", "campaignId", "linkedInUrl", "name", "headline",
                    "company", "notes", "createdAt", "updatedAt"
                )
                VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """, (
                campaign_id, p.get("linkedInUrl", ""), p.get("name"),
                p.get("headline"), p.get("company"), p.get("notes")
            ))
            count += cur.rowcount
        conn.commit()
        return count
    finally:
        cur.close()
        release_conn(conn)

def get_prospects_for_campaign(campaign_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "linkedInUrl", "name", "headline", "company", "status",
                   "requestedAt", "connectedAt", "messagedAt", "repliedAt", "createdAt"
            FROM "Prospect"
            WHERE "campaignId" = %s
            ORDER BY "createdAt" DESC
            LIMIT %s OFFSET %s
        """, (campaign_id, limit, offset))
        rows = cur.fetchall()
        keys = ["id", "linkedInUrl", "name", "headline", "company", "status",
                "requestedAt", "connectedAt", "messagedAt", "repliedAt", "createdAt"]
        return [dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in r])) for r in rows]
    finally:
        cur.close()
        release_conn(conn)

def get_next_prospects(campaign_ids: list[str], limit: int = 5) -> list[dict]:
    """Get next PENDING prospects across given campaigns, ordered oldest first."""
    if not campaign_ids:
        return []
    conn = get_conn()
    try:
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(campaign_ids))
        cur.execute(f"""
            SELECT "id", "campaignId", "linkedInUrl", "name", "headline", "company", "notes"
            FROM "Prospect"
            WHERE "campaignId" IN ({placeholders}) AND "status" = 'PENDING'
            ORDER BY "createdAt" ASC
            LIMIT %s
        """, campaign_ids + [limit])
        rows = cur.fetchall()
        keys = ["id", "campaignId", "linkedInUrl", "name", "headline", "company", "notes"]
        return [dict(zip(keys, r)) for r in rows]
    finally:
        cur.close()
        release_conn(conn)

def update_prospect_status(prospect_id: str, status: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        timestamp_fields = {
            "REQUESTED": '"requestedAt" = NOW(),',
            "CONNECTED": '"connectedAt" = NOW(),',
            "MESSAGED": '"messagedAt" = NOW(),',
            "REPLIED": '"repliedAt" = NOW(),',
        }
        extra = timestamp_fields.get(status, "")
        cur.execute(f"""
            UPDATE "Prospect"
            SET "status" = %s, {extra} "updatedAt" = NOW()
            WHERE "id" = %s
        """, (status, prospect_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def save_prospect_profile_data(prospect_id: str, profile_data: dict):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "Prospect"
            SET "profileData" = %s, "status" = 'PROFILE_VIEWED', "updatedAt" = NOW()
            WHERE "id" = %s AND "status" = 'PENDING'
        """, (json.dumps(profile_data), prospect_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def get_pipeline_stats(account_id: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p."status", COUNT(*) as count
            FROM "Prospect" p
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s
            GROUP BY p."status"
        """, (account_id,))
        rows = cur.fetchall()
        stats = {r[0]: r[1] for r in rows}
        return stats
    finally:
        cur.close()
        release_conn(conn)

def get_pipeline_prospects(account_id: str, limit: int = 100) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p."id", p."name", p."headline", p."company", p."linkedInUrl",
                   p."status", p."requestedAt", p."connectedAt", p."messagedAt",
                   p."repliedAt", c."name" as campaign_name
            FROM "Prospect" p
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s
            ORDER BY p."updatedAt" DESC
            LIMIT %s
        """, (account_id, limit))
        rows = cur.fetchall()
        keys = ["id", "name", "headline", "company", "linkedInUrl", "status",
                "requestedAt", "connectedAt", "messagedAt", "repliedAt", "campaignName"]
        return [
            dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in r]))
            for r in rows
        ]
    finally:
        cur.close()
        release_conn(conn)


# ─── Outreach Messages (Approval Queue) ──────────────────────────────────────

def create_outreach_message(prospect_id: str, msg_type: str, content: str) -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "OutreachMessage" (
                "id", "prospectId", "type", "content", "createdAt", "updatedAt"
            )
            VALUES (gen_random_uuid()::text, %s, %s, %s, NOW(), NOW())
            RETURNING "id"
        """, (prospect_id, msg_type, content))
        row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        cur.close()
        release_conn(conn)

def get_pending_messages(account_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT m."id", m."type", m."content", m."status", m."createdAt",
                   p."id" as prospect_id, p."name", p."headline", p."company",
                   p."linkedInUrl", c."name" as campaign_name, c."goal"
            FROM "OutreachMessage" m
            JOIN "Prospect" p ON p."id" = m."prospectId"
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s AND m."status" = 'PENDING_REVIEW'
            ORDER BY m."createdAt" ASC
            LIMIT %s
        """, (account_id, limit))
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "type": r[1], "content": r[2], "status": r[3],
                "createdAt": str(r[4]),
                "prospect": {
                    "id": r[5], "name": r[6], "headline": r[7],
                    "company": r[8], "linkedInUrl": r[9],
                },
                "campaignName": r[10], "campaignGoal": r[11]
            }
            for r in rows
        ]
    finally:
        cur.close()
        release_conn(conn)

def get_approved_messages(account_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT m."id", m."type", m."content", m."editedContent",
                   p."id" as prospect_id, p."name", p."linkedInUrl", p."headline", p."company"
            FROM "OutreachMessage" m
            JOIN "Prospect" p ON p."id" = m."prospectId"
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s AND m."status" = 'APPROVED'
            ORDER BY m."reviewedAt" ASC
        """, (account_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "type": r[1],
                "content": r[3] if r[3] else r[2],  # use edited content if present
                "prospect": {
                    "id": r[4], "name": r[5], "linkedInUrl": r[6],
                    "headline": r[7], "company": r[8]
                }
            }
            for r in rows
        ]
    finally:
        cur.close()
        release_conn(conn)

def approve_message(message_id: str, edited_content: str = None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "OutreachMessage"
            SET "status" = 'APPROVED',
                "editedContent" = %s,
                "reviewedAt" = NOW(),
                "updatedAt" = NOW()
            WHERE "id" = %s AND "status" = 'PENDING_REVIEW'
        """, (edited_content, message_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def reject_message(message_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "OutreachMessage"
            SET "status" = 'REJECTED', "reviewedAt" = NOW(), "updatedAt" = NOW()
            WHERE "id" = %s AND "status" = 'PENDING_REVIEW'
        """, (message_id,))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def bulk_update_messages(account_id: str, action: str) -> int:
    """action: 'approve' or 'reject'"""
    status = "APPROVED" if action == "approve" else "REJECTED"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "OutreachMessage" m
            SET "status" = %s, "reviewedAt" = NOW(), "updatedAt" = NOW()
            FROM "Prospect" p
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE m."prospectId" = p."id"
              AND c."linkedInAccountId" = %s
              AND m."status" = 'PENDING_REVIEW'
        """, (status, account_id))
        count = cur.rowcount
        conn.commit()
        return count
    finally:
        cur.close()
        release_conn(conn)

def mark_message_sent(message_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "OutreachMessage"
            SET "status" = 'SENT', "sentAt" = NOW(), "updatedAt" = NOW()
            WHERE "id" = %s
        """, (message_id,))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def mark_message_failed(message_id: str, reason: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "OutreachMessage"
            SET "status" = 'FAILED', "failureReason" = %s, "updatedAt" = NOW()
            WHERE "id" = %s
        """, (reason, message_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def get_queue_stats(account_id: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT m."status", COUNT(*)
            FROM "OutreachMessage" m
            JOIN "Prospect" p ON p."id" = m."prospectId"
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s
            GROUP BY m."status"
        """, (account_id,))
        rows = cur.fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        cur.close()
        release_conn(conn)


# ─── Agent Sessions ───────────────────────────────────────────────────────────

def create_agent_session(account_id: str) -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "AgentSession" ("id", "linkedInAccountId", "createdAt")
            VALUES (gen_random_uuid()::text, %s, NOW())
            RETURNING "id"
        """, (account_id,))
        row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        cur.close()
        release_conn(conn)

def end_agent_session(session_id: str, status: str, stats: dict):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE "AgentSession"
            SET "status" = %s, "endedAt" = NOW(),
                "connectionsAttempted" = %s, "connectionsSent" = %s,
                "likes" = %s, "comments" = %s,
                "messagesGenerated" = %s, "profilesViewed" = %s,
                "errorMessage" = %s
            WHERE "id" = %s
        """, (
            status,
            stats.get("connectionsAttempted", 0),
            stats.get("connectionsSent", 0),
            stats.get("likes", 0),
            stats.get("comments", 0),
            stats.get("messagesGenerated", 0),
            stats.get("profilesViewed", 0),
            stats.get("errorMessage"),
            session_id
        ))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def log_action(session_id: str, action: str, target: str, status: str, metadata: dict = None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "ActionLog" ("id", "sessionId", "action", "target", "status", "metadata", "createdAt")
            VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, NOW())
        """, (session_id, action, target, status, json.dumps(metadata) if metadata else None))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def get_recent_sessions(account_id: str, limit: int = 10) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "status", "startedAt", "endedAt",
                   "connectionsSent", "likes", "comments", "messagesGenerated", "profilesViewed"
            FROM "AgentSession"
            WHERE "linkedInAccountId" = %s
            ORDER BY "startedAt" DESC
            LIMIT %s
        """, (account_id, limit))
        rows = cur.fetchall()
        keys = ["id", "status", "startedAt", "endedAt", "connectionsSent",
                "likes", "comments", "messagesGenerated", "profilesViewed"]
        return [dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in r])) for r in rows]
    finally:
        cur.close()
        release_conn(conn)

# ─── Agent Tasks ─────────────────────────────────────────────────────────────

def create_agent_task(user_id: str, account_id: str, title: str, instruction: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO "AgentTask" ("id", "userId", "linkedInAccountId", "title", "instruction", "createdAt", "updatedAt")
            VALUES (gen_random_uuid()::text, %s, %s, %s, %s, NOW(), NOW())
            RETURNING "id", "title", "instruction", "status", "createdAt"
        """, (user_id, account_id, title, instruction))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "title": row[1], "instruction": row[2], "status": row[3], "createdAt": str(row[4])}
    finally:
        cur.close()
        release_conn(conn)

def get_tasks_for_user(user_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "userId", "linkedInAccountId", "title", "instruction", "status",
                   "result", "errorMessage", "startedAt", "completedAt", "createdAt"
            FROM "AgentTask" WHERE "userId" = %s ORDER BY "createdAt" DESC
        """, (user_id,))
        rows = cur.fetchall()
        keys = ["id", "userId", "linkedInAccountId", "title", "instruction", "status",
                "result", "errorMessage", "startedAt", "completedAt", "createdAt"]
        return [dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in r])) for r in rows]
    finally:
        cur.close()
        release_conn(conn)

def get_agent_task(task_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "id", "userId", "linkedInAccountId", "title", "instruction", "status",
                   "result", "errorMessage", "steps", "startedAt", "completedAt", "createdAt"
            FROM "AgentTask" WHERE "id" = %s
        """, (task_id,))
        row = cur.fetchone()
        if not row:
            return None
        keys = ["id", "userId", "linkedInAccountId", "title", "instruction", "status",
                "result", "errorMessage", "steps", "startedAt", "completedAt", "createdAt"]
        return dict(zip(keys, [str(v) if isinstance(v, datetime) else v for v in row]))
    finally:
        cur.close()
        release_conn(conn)

def update_agent_task_status(task_id: str, status: str, result: str = None,
                              error: str = None, steps: list = None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        started_at_clause = ', "startedAt" = NOW()' if status == "RUNNING" else ""
        completed_at_clause = ', "completedAt" = NOW()' if status in ("COMPLETED", "FAILED", "CANCELLED") else ""
        cur.execute(f"""
            UPDATE "AgentTask"
            SET "status" = %s, "result" = %s, "errorMessage" = %s,
                "steps" = %s, "updatedAt" = NOW()
                {started_at_clause}{completed_at_clause}
            WHERE "id" = %s
        """, (status, result, error, json.dumps(steps) if steps else None, task_id))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)

def delete_agent_task(task_id: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM "AgentTask" WHERE "id" = %s', (task_id,))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)


def get_daily_stats(account_id: str) -> dict:
    conn = get_conn()
    try:
        today = _today()
        cur = conn.cursor()
        # Guardrail counts (actions taken today)
        cur.execute("""
            SELECT "connectionsCount", "profileViewsCount", "likesCount",
                   "commentsCount", "messagesCount"
            FROM "Guardrail"
            WHERE "linkedInAccountId" = %s AND "date" = %s
        """, (account_id, today))
        g = cur.fetchone() or (0, 0, 0, 0, 0)

        # Pipeline counts
        cur.execute("""
            SELECT p."status", COUNT(*)
            FROM "Prospect" p
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s
            GROUP BY p."status"
        """, (account_id,))
        pipeline = {r[0]: r[1] for r in cur.fetchall()}

        # Queue counts
        cur.execute("""
            SELECT m."status", COUNT(*)
            FROM "OutreachMessage" m
            JOIN "Prospect" p ON p."id" = m."prospectId"
            JOIN "Campaign" c ON c."id" = p."campaignId"
            WHERE c."linkedInAccountId" = %s
            GROUP BY m."status"
        """, (account_id,))
        queue = {r[0]: r[1] for r in cur.fetchall()}

        return {
            "today": {
                "connections": g[0], "profileViews": g[1],
                "likes": g[2], "comments": g[3], "messages": g[4]
            },
            "pipeline": pipeline,
            "queue": queue,
            "date": today
        }
    finally:
        cur.close()
        release_conn(conn)
