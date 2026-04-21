"""GhostAgent — Multi-user orchestrator loop.

Flow per session:
  1. Load account + session cookies from DB
  2. Launch stealth browser, inject cookies
  3. Verify LinkedIn session (handle re-login if needed)
  4. Start kill-switch monitor thread
  5. Run warmup OR main outreach:
     a. Organic feed engagement (likes, comments)
     b. Send approved connection requests from DB queue
     c. Check inbox, flag leads
     d. Visit new prospects, generate notes → save to DB for review
  6. Record session stats to DB, update account status
  7. Sleep between sessions (continuous mode)
"""

import os
import sys
import time
import random
import threading
import concurrent.futures

import db
from config import SCREENSHOT_DIR, DATA_DIR
from browser import open_browser, take_screenshot, wait_for_stable, close_browser, start_screen_broadcast
from human import random_delay, apply_interaction_jitter
from scheduler import (
    is_active_hours,
    random_session_duration,
    should_take_break,
    get_break_duration,
)
from guardrails import Guardrails
from linkedin.auth import ensure_session, wait_for_login, is_logged_in, check_session_or_relogin
from linkedin.connect import send_connection
from linkedin.interact import organic_feed_engagement
from linkedin.inbox import process_inbox
from navigator import navigate_to_feed, random_detour, navigate_to_profile
from ghostwriter import generate_connection_note, generate_comment, generate_reply
from diversity import DiversityEngine
import linkedin.kill_switch as ks
from linkedin.kill_switch import start_monitor


_LLM_TIMEOUT_SECS = 30  # Max time for any single LLM call
_CONNECT_VERIFY_WAIT = 2.0  # Seconds to wait before verifying connection was sent


def run_agent(account_id: str = None, continuous: bool = False,
              legacy_prospects: list = None, skip_warmup: bool = False,
              task_id: str = None):
    """Run the GhostAgent for a specific LinkedIn account.

    Args:
        account_id: DB id of the LinkedInAccount record. None = legacy single-user mode.
        continuous: Run in loop with inter-session breaks.
        legacy_prospects: Prospect names for legacy single-user mode.
        task_id: If set, run a specific one-off AgentTask instead of campaign loop.
    """
    print("=" * 60)
    print("  👻 GhostAgent — LinkedIn Digital Twin")
    if account_id:
        print(f"  Account: {account_id}")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # ─── Load account state from DB ─────────────────────────────────
    if account_id:
        account = db.get_account(account_id)
        if not account:
            print(f"[Agent] ❌ Account {account_id} not found in DB")
            return
        db.update_account_status(account_id, "RUNNING")
    else:
        account = None

    guardrails = Guardrails(account_id) if account_id else _legacy_guardrails()
    diversity = DiversityEngine()
    persona = _load_persona(account)

    if account_id:
        guardrails.print_daily_stats()

    session_id = None

    while True:
        # ─── Launch browser ─────────────────────────────────────────

        print("\n[Agent] 🚀 Starting new session...")

        # Get fresh cookies from DB before each session
        cookies = db.get_account_cookies(account_id) if account_id else None
        page, context, playwright = open_browser(
            "https://www.linkedin.com/feed/",
            cookies=cookies,
            account_id=account_id,
        )
        wait_for_stable(page, timeout=10000)
        apply_interaction_jitter(page)

        # Stream live view to dashboard for the duration of this session
        broadcast_stop = start_screen_broadcast(page, account_id=account_id) if account_id else None

        if account_id:
            session_id = db.create_agent_session(account_id)

        session_stats = {
            "connectionsAttempted": 0, "connectionsSent": 0,
            "likes": 0, "comments": 0, "messagesGenerated": 0, "profilesViewed": 0
        }

        try:
            # ─── Verify session ──────────────────────────────────────

            if not is_logged_in(page):
                print("[Agent] ⚠️  Not logged in")
                logged_in = wait_for_login(page, account_id=account_id)
                if not logged_in:
                    print("[Agent] ❌ Could not log in")
                    _end_session(session_id, "ERROR", session_stats,
                                 error="Login failed", account_id=account_id)
                    close_browser(context, playwright)
                    if continuous:
                        time.sleep(300)
                        continue
                    return

                # After login, capture and save fresh cookies
                if account_id:
                    _save_cookies_from_browser(context, account_id)

            session_ok = ensure_session(page)
            if not session_ok:
                print("[Agent] ⚠️  Session challenge detected")
                if account_id:
                    db.update_account_status(account_id, "PAUSED")
                _end_session(session_id, "ABORTED", session_stats,
                             error="Session challenge", account_id=account_id)
                close_browser(context, playwright)
                if continuous:
                    time.sleep(600)
                    continue
                return

            print("[Agent] ✅ Session verified")

            # Refresh cookies after successful session verify
            if account_id:
                _save_cookies_from_browser(context, account_id)

            # ─── Kill switch monitor ─────────────────────────────────

            ks.ABORT_AUTOMATION = False
            kill_event = threading.Event()
            monitor_thread = threading.Thread(
                target=_robust_inbox_monitor,
                args=(context, kill_event),
                daemon=True,
            )
            monitor_thread.start()

            # ─── Warmup check ────────────────────────────────────────

            # Tasks bypass warmup — they're one-off instructions
            effective_skip_warmup = skip_warmup or bool(task_id)
            warmup_done = _check_warmup(account, page, session_stats, account_id,
                                        skip_warmup=effective_skip_warmup)
            if not warmup_done:
                kill_event.set()
                close_browser(context, playwright)
                if account_id:
                    db.update_account_status(account_id, "WARMUP")
                if continuous:
                    sleep_h = random.uniform(2, 4)
                    print(f"[Agent] Next warmup in {sleep_h:.1f}h")
                    time.sleep(int(sleep_h * 3600))
                    continue
                return

            # ─── Task mode (one-off instruction) ─────────────────────

            if task_id:
                _run_task_mode(page, task_id, session_id, account_id)
                kill_event.set()
                _end_session(session_id, "COMPLETED", session_stats, account_id=account_id)
                close_browser(context, playwright)
                if account_id:
                    db.update_account_status(account_id, "IDLE")
                return

            # ─── Main session ────────────────────────────────────────

            session_duration = random_session_duration()
            session_start = time.time()
            print(f"[Agent] Session duration: {session_duration // 60}min")

            # Step 1: Organic feed engagement
            if not ks.ABORT_AUTOMATION:
                print("\n[Agent] 📱 Feed engagement...")
                try:
                    stats = organic_feed_engagement(
                        page,
                        max_likes=random.randint(2, 4),
                        max_comments=random.randint(1, 2),
                        comment_generator=lambda post: _safe_generate_comment(post, persona),
                        guardrails=guardrails,
                    )
                    session_stats["likes"] += stats.get("likes", 0)
                    session_stats["comments"] += stats.get("comments", 0)
                    if session_id:
                        db.log_action(session_id, "feed_engagement", "feed", "success",
                                      {"likes": stats.get("likes", 0), "comments": stats.get("comments", 0)})
                except Exception as e:
                    print(f"[Agent] Feed engagement error: {e}")
                    if session_id:
                        db.log_action(session_id, "feed_engagement", "feed", "failed", {"error": str(e)})

            if _session_expired(session_start, session_duration):
                raise _SessionComplete()

            # Step 2: Send approved connections from DB queue
            if not ks.ABORT_AUTOMATION and account_id:
                approved = db.get_approved_messages(account_id)
                if approved:
                    if not check_session_or_relogin(page):
                        print("[Agent] ❌ Session lost before sending connections")
                    else:
                        print(f"\n[Agent] 📨 Sending {len(approved)} approved connections...")
                        for item in approved:
                            if ks.ABORT_AUTOMATION or _session_expired(session_start, session_duration):
                                break
                            if not guardrails.can_connect():
                                break
                            if not check_session_or_relogin(page):
                                break

                            if random.random() < 0.3:
                                random_detour(page)

                            name = item["prospect"].get("name") or item["prospect"].get("linkedInUrl", "")
                            note = item["content"]
                            note = diversity.ensure_unique(
                                note,
                                regenerate_fn=lambda: _safe_generate_note(item["prospect"], persona)
                            )

                            session_stats["connectionsAttempted"] += 1
                            result = send_connection(page, name, note, guardrails)
                            print(f"  → {name}: {result['status']}")

                            if session_id:
                                db.log_action(session_id, "connect", name, result["status"])

                            if result["status"] == "sent":
                                session_stats["connectionsSent"] += 1
                                diversity.record_sent(note)
                                db.mark_message_sent(item["id"])
                                db.update_prospect_status(item["prospect"]["id"], "REQUESTED")
                            elif result["status"] in ("failed", "error"):
                                db.mark_message_failed(item["id"], result.get("reason", "unknown"))

                            random_delay(2.0, 5.0)
                            if should_take_break():
                                _take_break()
                            else:
                                apply_interaction_jitter(page)

            if _session_expired(session_start, session_duration):
                raise _SessionComplete()

            # Step 3: Process inbox
            if not ks.ABORT_AUTOMATION:
                if check_session_or_relogin(page):
                    print("\n[Agent] 📬 Checking inbox...")
                    try:
                        inbox_summary = process_inbox(
                            page,
                            reply_generator=lambda name, msg, intent: _safe_generate_reply(name, msg, intent, persona),
                            guardrails=guardrails,
                        )
                        if inbox_summary.get("flagged_leads"):
                            print(f"[Agent] 🎯 {len(inbox_summary['flagged_leads'])} leads flagged!")
                            # Mark prospects as leads (if we can match them)
                    except Exception as e:
                        print(f"[Agent] Inbox error: {e}")

            if _session_expired(session_start, session_duration):
                raise _SessionComplete()

            # Step 4: Visit new prospects, generate notes → save to DB for review
            if not ks.ABORT_AUTOMATION and account_id:
                campaigns = db.get_active_campaigns(account_id)
                if campaigns:
                    campaign_ids = [c["id"] for c in campaigns]
                    next_prospects = db.get_next_prospects(campaign_ids, limit=5)

                    if next_prospects:
                        if not check_session_or_relogin(page):
                            print("[Agent] ❌ Session lost before prospecting")
                        else:
                            campaign_map = {c["id"]: c for c in campaigns}
                            print(f"\n[Agent] 🔍 Processing {len(next_prospects)} prospects...")

                            for prospect in next_prospects:
                                if ks.ABORT_AUTOMATION or _session_expired(session_start, session_duration):
                                    break
                                if not check_session_or_relogin(page):
                                    break

                                campaign = campaign_map.get(prospect["campaignId"], {})
                                linkedin_url = prospect.get("linkedInUrl", "")
                                name = prospect.get("name") or linkedin_url

                                try:
                                    # Navigate to profile
                                    navigate_to_profile(page, name, url=linkedin_url)
                                    wait_for_stable(page, timeout=8000)
                                    session_stats["profilesViewed"] += 1

                                    from linkedin.profile import extract_profile_data
                                    profile_data = extract_profile_data(page)
                                    db.save_prospect_profile_data(prospect["id"], profile_data)

                                    if session_id:
                                        db.log_action(session_id, "profile_view", name, "success")

                                    # Generate note
                                    persona_for_campaign = _persona_for_campaign(campaign, persona)
                                    note = _safe_generate_note(profile_data, persona_for_campaign)
                                    note = diversity.ensure_unique(
                                        note,
                                        regenerate_fn=lambda: _safe_generate_note(profile_data, persona_for_campaign)
                                    )

                                    if campaign.get("autoApprove"):
                                        # Auto-send without review
                                        result = send_connection(page, name, note, guardrails)
                                        if result["status"] == "sent":
                                            session_stats["connectionsSent"] += 1
                                            diversity.record_sent(note)
                                            db.update_prospect_status(prospect["id"], "REQUESTED")
                                            msg_id = db.create_outreach_message(
                                                prospect["id"], "CONNECTION_NOTE", note
                                            )
                                            db.mark_message_sent(msg_id)
                                        print(f"  [AUTO] {name}: {result['status']}")
                                    else:
                                        # Queue for review
                                        db.create_outreach_message(prospect["id"], "CONNECTION_NOTE", note)
                                        session_stats["messagesGenerated"] += 1
                                        print(f"  [QUEUE] {name}: Added to approval queue")

                                except Exception as e:
                                    print(f"  [SKIP] {name}: {e}")
                                    db.update_prospect_status(prospect["id"], "SKIPPED")
                                    if session_id:
                                        db.log_action(session_id, "profile_view", name, "failed", {"error": str(e)})

                                random_delay(2.0, 5.0)

            print("\n[Agent] ✅ Session complete!")
            guardrails.print_daily_stats()
            kill_event.set()

        except _SessionComplete:
            print("\n[Agent] ⏰ Session time up")
            kill_event.set()

        except KeyboardInterrupt:
            print("\n[Agent] 🛑 Interrupted")
            kill_event.set()
            _end_session(session_id, "ABORTED", session_stats, account_id=account_id)
            close_browser(context, playwright)
            return

        except Exception as e:
            import traceback
            print(f"\n[Agent] ❌ Error: {e}")
            traceback.print_exc()
            kill_event.set()
            _end_session(session_id, "ERROR", session_stats,
                         error=str(e), account_id=account_id)
            close_browser(context, playwright)
            if continuous:
                time.sleep(120)
                continue
            return

        finally:
            if broadcast_stop:
                broadcast_stop.set()
            close_browser(context, playwright)

        _end_session(session_id, "COMPLETED", session_stats, account_id=account_id)

        if not continuous:
            break

        _inter_session_break()

    if account_id:
        db.update_account_status(account_id, "IDLE")


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _SessionComplete(Exception):
    pass


def _end_session(session_id, status, stats, error=None, account_id=None):
    if session_id:
        if error:
            stats["errorMessage"] = error
        db.end_agent_session(session_id, status, stats)
    if account_id and status in ("ERROR", "ABORTED"):
        db.update_account_status(account_id, "ERROR" if status == "ERROR" else "IDLE")


def _session_expired(start_time: float, duration: float) -> bool:
    return (time.time() - start_time) > duration


def _take_break():
    dur = get_break_duration()
    print(f"[Agent] ☕ Break {dur // 60}min...")
    time.sleep(dur)


def _inter_session_break():
    minutes = random.uniform(30, 90)
    print(f"[Agent] 💤 Next session in {minutes:.0f}min...")
    time.sleep(int(minutes * 60))


def _check_warmup(account, page, session_stats, account_id, skip_warmup: bool = False) -> bool:
    """Returns True if warmup is complete and outreach can begin."""
    if not account_id:
        return True  # Legacy mode: no warmup tracking
    if not account:
        return True
    if skip_warmup:
        return True

    warmup_status = account.get("warmupStatus", "NOT_STARTED")
    if warmup_status == "COMPLETED":
        return True

    print(f"[Agent] 🔥 Warmup status: {warmup_status}")

    from linkedin.warmup import WarmupSequence
    warmup = _DBWarmup(account_id, warmup_status, account)
    warmup.run_session(page)

    session_stats["likes"] += warmup.session_likes
    session_stats["profilesViewed"] += warmup.session_views

    return warmup.is_complete


def _save_cookies_from_browser(context, account_id: str):
    try:
        cookies = context.cookies()
        li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)
        jsessionid = next((c["value"] for c in cookies if c["name"] == "JSESSIONID"), None)
        if li_at:
            db.update_account_session(account_id, li_at, jsessionid or "")
    except Exception as e:
        print(f"[Agent] Cookie save warning: {e}")


def _robust_inbox_monitor(context, stop_event: threading.Event):
    """Kill-switch monitor with full exception handling."""
    from linkedin.kill_switch import ghost_inbox_monitor_loop
    while not stop_event.is_set() and not ks.ABORT_AUTOMATION:
        try:
            ghost_inbox_monitor_loop(context, stop_event)
        except Exception as e:
            print(f"[KillSwitch] Monitor error (restarting): {e}")
            if not stop_event.wait(timeout=15):
                continue
        break


def _safe_generate_comment(post_data, persona) -> str:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(
            generate_comment,
            post_data.get("body", post_data) if isinstance(post_data, dict) else post_data,
            persona,
            author_name=post_data.get("author") if isinstance(post_data, dict) else None,
        )
        try:
            return future.result(timeout=_LLM_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            return ""  # Skip comment on timeout


def _safe_generate_note(profile_data, persona) -> str:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(generate_connection_note, profile_data, persona)
        try:
            return future.result(timeout=_LLM_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            name = profile_data.get("name", "there") if isinstance(profile_data, dict) else "there"
            return f"Hi {name}, I'd love to connect and learn more about your work."


def _safe_generate_reply(name, msg, intent, persona) -> str:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(generate_reply, name, msg, intent, persona)
        try:
            return future.result(timeout=_LLM_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            return ""


def _load_persona(account: dict | None):
    from persona import load_persona
    return load_persona()


def _persona_for_campaign(campaign: dict, default_persona) -> object:
    if not campaign:
        return default_persona
    tone = campaign.get("personaTone", "professional")
    sample = campaign.get("personaSample")
    if sample:
        default_persona.tone = tone
        default_persona.sample = sample
    return default_persona


def _legacy_guardrails():
    """Return guardrails for legacy single-user mode (SQLite-backed)."""
    try:
        from guardrails import Guardrails as LegacyGuardrails
        return LegacyGuardrails(account_id="legacy")
    except Exception:
        from guardrails import Guardrails
        return Guardrails(account_id="legacy")


class _DBWarmup:
    """Thin warmup wrapper that reads/writes warmup state from DB."""

    def __init__(self, account_id: str, status: str, account: dict):
        self.account_id = account_id
        self.status = status
        self.account = account
        self.session_likes = 0
        self.session_views = 0

    @property
    def is_complete(self):
        return self.status == "COMPLETED"

    def run_session(self, page):
        from linkedin.warmup import WarmupSequence
        # Use the existing warmup logic but sync state back to DB
        warmup = WarmupSequence()
        warmup.status = self.status

        # Inject DB state
        warmup._state = {
            "status": self.status,
            "sessions": self.account.get("warmupSessions", 0),
            "total_likes": self.account.get("warmupLikes", 0),
            "total_profile_views": self.account.get("warmupProfileViews", 0),
            "started_at": self.account.get("warmupStartedAt"),
        }

        warmup.run_session(page)

        # Write back
        new_status = warmup.status
        self.status = new_status
        self.session_likes = getattr(warmup, "_session_likes", 0)
        self.session_views = getattr(warmup, "_session_views", 0)

        db.update_warmup_state(
            self.account_id, new_status,
            sessions_delta=1,
            likes_delta=self.session_likes,
            views_delta=self.session_views,
        )


def _run_task_mode(page, task_id: str, session_id: str, account_id: str):
    """Execute a one-off AgentTask using the vision-based task executor."""
    from task_executor import run_task

    task = db.get_agent_task(task_id)
    if not task:
        print(f"[Agent] Task {task_id} not found")
        return

    print(f"\n[Agent] 🎯 Executing task: {task['title']}")
    print(f"[Agent] Instruction: {task['instruction'][:120]}...")

    db.update_agent_task_status(task_id, "RUNNING")

    def on_step(step_num, action, reason):
        print(f"[Task] Step {step_num}: {action} — {reason}")
        if session_id:
            db.log_action(session_id, f"task_step_{action}", reason, "in_progress")

    result = run_task(page, task["instruction"], on_step=on_step)

    final_status = "COMPLETED" if result["status"] == "completed" else "FAILED"
    db.update_agent_task_status(
        task_id,
        final_status,
        result=result.get("result"),
        error=result.get("result") if final_status == "FAILED" else None,
        steps=result.get("steps"),
    )

    print(f"[Agent] Task {final_status}: {result.get('result', '')}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", help="LinkedInAccount DB id")
    parser.add_argument("--continuous", action="store_true")
    args = parser.parse_args()
    run_agent(account_id=args.account_id, continuous=args.continuous)
