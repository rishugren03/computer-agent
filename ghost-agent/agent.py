"""GhostAgent — Main Orchestrator Loop.

The brain that ties everything together:
1. Check schedule (active hours?)
2. Launch browser with stealth settings
3. Verify session / handle login
4. Check warmup status → run warmup if needed
5. If warmup complete → run outreach session:
   a. Organic feed engagement (2-3 interactions)
   b. Process approval queue (send approved connections)
   c. Check inbox (auto-reply, flag leads)
   d. Find new prospects → generate notes → queue for review
6. Respect guardrails on every action
7. Random breaks → repeat until session ends
8. Sleep until next active window
"""

import os
import sys
import time
import random

from config import SCREENSHOT_DIR, DATA_DIR
from browser import open_browser, take_screenshot, wait_for_stable, close_browser
from human import random_delay, apply_interaction_jitter
from scheduler import (
    is_active_hours,
    wait_for_active_hours,
    random_session_duration,
    should_take_break,
    get_break_duration,
    get_schedule_info,
)
from guardrails import Guardrails
from linkedin.auth import ensure_session, wait_for_login, is_logged_in, check_session_or_relogin
from linkedin.warmup import WarmupSequence
from linkedin.connect import send_connection
from linkedin.interact import organic_feed_engagement, pre_connection_engagement
from linkedin.inbox import process_inbox
from navigator import navigate_to_feed, random_detour
from persona import load_persona
from ghostwriter import generate_connection_note, generate_comment, generate_reply
from approval_queue import ApprovalQueue
from diversity import DiversityEngine
from vision import describe_page
from linkedin.kill_switch import start_monitor
import linkedin.kill_switch as ks


def run_agent(prospects=None, continuous=False):
    """Run the GhostAgent.

    Args:
        prospects: Optional list of prospect names to connect with.
        continuous: If True, runs in a loop (sleep/wake cycle).
    """
    print("=" * 60)
    print("  👻 GhostAgent — LinkedIn Digital Twin")
    print("=" * 60)

    # ─── Initialize Components ───────────────────────────────────────

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    guardrails = Guardrails()
    warmup = WarmupSequence()
    persona = load_persona()
    queue = ApprovalQueue()
    diversity = DiversityEngine()

    # Print current status
    guardrails.print_daily_stats()
    schedule = get_schedule_info()
    print(f"\n⏰ Time: {schedule['current_hour']}:00 ({schedule['timezone']})")
    print(f"   Active: {'✅' if schedule['is_active'] else '❌'}")
    print(f"   Warmup: {'✅ Complete' if warmup.is_complete else f'⏳ {warmup.hours_remaining:.1f}h remaining'}")
    print(f"   Queue: {len(queue.get_pending())} pending, {len(queue.get_approved())} approved")
    print(f"   Auto-Pilot: {'✅ Enabled' if queue.auto_pilot_eligible else f'❌ ({queue.approval_rate:.0f}% approval rate)'}")

    while True:
        # ─── Check Schedule ──────────────────────────────────────────

        # TEMP: Disabling active hours check for testing
        # if not is_active_hours():
        #     print("\n[Agent] 😴 Outside active hours")
        #     if continuous:
        #         wait_for_active_hours()
        #     else:
        #         print("[Agent] Not in continuous mode. Exiting.")
        #         return

        # ─── Launch Browser ──────────────────────────────────────────

        print("\n[Agent] 🚀 Starting new session...")
        page, context, playwright = open_browser("https://www.linkedin.com/feed/")
        wait_for_stable(page, timeout=10000)
        
        # Apply initial jitter to establish human footprint
        apply_interaction_jitter(page)

        # Live View will now be handled inside human.py's random_delay function safely.

        try:
            # ─── Verify Session ──────────────────────────────────────

            if not is_logged_in(page):
                print("[Agent] ⚠️  Not logged in")
                logged_in = wait_for_login(page)
                if not logged_in:
                    print("[Agent] ❌ Could not log in. Exiting session.")
                    close_browser(context, playwright)
                    if continuous:
                        time.sleep(300)  # Wait 5 min before retrying
                        continue
                    return

            session_ok = ensure_session(page)
            if not session_ok:
                print("[Agent] ⚠️  Session issue detected. Please resolve manually.")
                close_browser(context, playwright)
                if continuous:
                    time.sleep(600)
                    continue
                return

            print("[Agent] ✅ Session verified")

            # ─── Initialize Ghost Inbox Monitor (Kill Switch) ────────
            ks.ABORT_AUTOMATION = False
            monitor_thread = start_monitor(context)

            # ─── Check Warmup ────────────────────────────────────────

            if not warmup.is_complete:
                print("[Agent] 🔥 Running warm-up session...")
                warmup.run_session(page)
                summary = warmup.get_summary()
                print(f"[Agent] Warmup: {summary['hours_remaining']:.1f}h remaining | "
                      f"{summary['total_likes']} likes | {summary['total_profile_views']} views")

                if not warmup.is_complete:
                    close_browser(context, playwright)
                    if continuous:
                        # Wait 2-4 hours before next warmup session
                        sleep_hours = random.uniform(2, 4)
                        print(f"[Agent] Next warmup session in {sleep_hours:.1f}h")
                        time.sleep(int(sleep_hours * 3600))
                        continue
                    return

                print("[Agent] 🎉 Warm-up complete! Outreach unlocked.")

            # ─── Main Session Loop ───────────────────────────────────

            session_duration = random_session_duration()
            session_start = time.time()
            print(f"[Agent] Session duration: {session_duration // 60}min")

            # Step 1: Organic feed engagement (already on feed from open_browser)
            if ks.ABORT_AUTOMATION:
                print("[Agent] 🚨 KILL SWITCH ACTIVATED — Aborting Session")
                close_browser(context, playwright)
                return
            print("\n[Agent] 📱 Organic feed engagement...")
            organic_feed_engagement(
                page,
                max_likes=random.randint(2, 4),
                max_comments=random.randint(1, 2),
                comment_generator=lambda post_data: generate_comment(
                    post_data.get("body", post_data) if isinstance(post_data, dict) else post_data,
                    persona,
                    author_name=post_data.get("author") if isinstance(post_data, dict) else None,
                    author_headline=post_data.get("author_headline") if isinstance(post_data, dict) else None,
                ),
                guardrails=guardrails,
            )

            # Check if session time exhausted
            if _session_expired(session_start, session_duration):
                print("[Agent] ⏰ Session time up")
                close_browser(context, playwright)
                if continuous:
                    _inter_session_break()
                    continue
                return

            # Step 2: Process approval queue (send approved connections)
            if ks.ABORT_AUTOMATION:
                print("[Agent] 🚨 KILL SWITCH ACTIVATED — Aborting Session")
                close_browser(context, playwright)
                return
            approved = queue.get_approved()
            if approved:
                if not check_session_or_relogin(page):
                    print("[Agent] ❌ Session lost before sending connections — aborting session")
                    close_browser(context, playwright)
                    continue

                print(f"\n[Agent] 📨 Sending {len(approved)} approved connections...")
                for item in approved:
                    if not check_session_or_relogin(page):
                        print("[Agent] ❌ Session lost while sending connections — aborting loop")
                        break

                    if _session_expired(session_start, session_duration):
                        break
                    if not guardrails.can_connect():
                        break

                    # Maybe do a random detour first (natural behavior)
                    if random.random() < 0.3:
                        random_detour(page)

                    name = item["prospect"].get("name", "")
                    note = item["note"]

                    # Ensure message uniqueness
                    note = diversity.ensure_unique(
                        note,
                        regenerate_fn=lambda: generate_connection_note(item["prospect"], persona)
                    )

                    result = send_connection(page, name, note, guardrails)
                    print(f"  → {name}: {result['status']}")

                    if result["status"] == "sent":
                        diversity.record_sent(note)
                        queue.mark_sent(item["id"])

                    random_delay(2.0, 5.0)

                    # Random micro-break
                    if should_take_break():
                        _take_break()
                    else:
                        # Otherwise, just some micro-jitter
                        apply_interaction_jitter(page)

            # Step 3: Process inbox
            if not _session_expired(session_start, session_duration):
                if not check_session_or_relogin(page):
                    print("[Agent] ❌ Session lost before checking inbox — aborting session")
                    close_browser(context, playwright)
                    continue

                print("\n[Agent] 📬 Checking inbox...")
                if ks.ABORT_AUTOMATION:
                    print("[Agent] 🚨 KILL SWITCH ACTIVATED — Aborting Session")
                    close_browser(context, playwright)
                    return
                inbox_summary = process_inbox(
                    page,
                    reply_generator=lambda name, msg, intent: generate_reply(name, msg, intent, persona),
                    guardrails=guardrails,
                )
                if inbox_summary["flagged_leads"]:
                    print(f"[Agent] 🎯 {len(inbox_summary['flagged_leads'])} leads flagged!")

            # Step 4: Generate new prospect notes (if we have prospects)
            if prospects and not _session_expired(session_start, session_duration):
                if not check_session_or_relogin(page):
                    print("[Agent] ❌ Session lost before prospecting — aborting session")
                    close_browser(context, playwright)
                    continue

                print(f"\n[Agent] 🔍 Processing {len(prospects)} prospects...")
                for prospect_name in prospects[:5]:  # Max 5 per session
                    if not check_session_or_relogin(page):
                        print("[Agent] ❌ Session lost during prospecting — aborting loop")
                        break

                    if _session_expired(session_start, session_duration):
                        break

                    # Navigate to profile and extract data
                    from navigator import navigate_to_profile
                    navigate_to_profile(page, prospect_name)
                    wait_for_stable(page, timeout=8000)

                    from linkedin.profile import extract_profile_data
                    profile_data = extract_profile_data(page)

                    # Generate personalized note
                    note = generate_connection_note(profile_data, persona)
                    note = diversity.ensure_unique(
                        note,
                        regenerate_fn=lambda: generate_connection_note(profile_data, persona)
                    )

                    if queue.auto_pilot_eligible:
                        # Auto-pilot: send directly
                        result = send_connection(page, prospect_name, note, guardrails)
                        print(f"  [AUTO] {prospect_name}: {result['status']}")
                        if result["status"] == "sent":
                            diversity.record_sent(note)
                    else:
                        # Queue for review
                        queue.add(profile_data, note)
                        print(f"  [QUEUE] {prospect_name}: Added to approval queue")

                    random_delay(2.0, 5.0)

            # ─── Session Complete ────────────────────────────────────

            print("\n[Agent] ✅ Session complete!")
            guardrails.print_daily_stats()

        except Exception as e:
            print(f"\n[Agent] ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            stream_active = False
            close_browser(context, playwright)

        if not continuous:
            break

        # Inter-session break
        _inter_session_break()


def _session_expired(start_time, duration):
    """Check if the current session has exceeded its duration."""
    return (time.time() - start_time) > duration


def _take_break():
    """Take a micro-break (2-5 minutes)."""
    break_duration = get_break_duration()
    print(f"[Agent] ☕ Taking a {break_duration // 60}min break...")
    time.sleep(break_duration)


def _inter_session_break():
    """Take a longer break between sessions (30-90 minutes)."""
    break_minutes = random.uniform(30, 90)
    print(f"[Agent] 💤 Next session in {break_minutes:.0f}min...")
    time.sleep(int(break_minutes * 60))


if __name__ == "__main__":
    # Parse CLI arguments
    prospects_list = []
    continuous_mode = "--continuous" in sys.argv or "-c" in sys.argv

    # Remaining args are prospect names
    for arg in sys.argv[1:]:
        if arg not in ("--continuous", "-c"):
            prospects_list.append(arg)

    run_agent(prospects=prospects_list if prospects_list else None, continuous=continuous_mode)
