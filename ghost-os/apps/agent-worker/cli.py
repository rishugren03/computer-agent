"""GhostAgent CLI — Command-line interface for setup, control, and monitoring."""

import sys
import os
import json

# Ensure ghost-agent is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_run(args):
    """Start the GhostAgent."""
    from agent import run_agent

    continuous = "--continuous" in args or "-c" in args
    prospects = [a for a in args if a not in ("--continuous", "-c")]

    print("👻 Starting GhostAgent...")
    run_agent(prospects=prospects if prospects else None, continuous=continuous)


def cmd_review(args):
    """Review the approval queue."""
    from approval_queue import ApprovalQueue

    queue = ApprovalQueue()
    pending = queue.get_pending(limit=15)

    if not pending:
        print("✅ No pending items to review!")
        return

    print(f"\n📋 Approval Queue ({len(pending)} items)")
    print("=" * 60)

    for item in pending:
        prospect = item["prospect"]
        name = prospect.get("name", "Unknown")
        headline = prospect.get("headline", "")
        note = item["note"]
        item_id = item["id"]

        print(f"\n👤 {name}")
        if headline:
            print(f"   {headline}")
        print(f"\n   📝 \"{note}\"")
        print(f"\n   [A]pprove  [E]dit  [R]eject  [S]kip  [Q]uit")

        choice = input("   → ").strip().lower()

        if choice == "a":
            queue.approve(item_id)
            print("   ✅ Approved!")
        elif choice == "e":
            new_note = input("   New note: ").strip()
            if new_note:
                queue.edit(item_id, new_note)
                print("   ✏️  Edited & approved!")
        elif choice == "r":
            queue.reject(item_id)
            print("   ❌ Rejected")
        elif choice == "q":
            break
        # 's' = skip (do nothing)

    stats = queue.get_stats()
    print(f"\n📊 Approval rate: {stats['approval_rate']}%")
    print(f"   Auto-Pilot: {'✅ Eligible' if stats['auto_pilot_eligible'] else '❌ Not yet'}")


def cmd_stats(args):
    """Show daily and weekly statistics."""
    from guardrails import Guardrails
    from scheduler import get_schedule_info
    from linkedin.warmup import WarmupSequence
    from approval_queue import ApprovalQueue

    guardrails = Guardrails()
    warmup = WarmupSequence()
    queue = ApprovalQueue()
    schedule = get_schedule_info()

    # Daily stats
    guardrails.print_daily_stats()

    # Schedule
    print(f"\n⏰ Schedule:")
    print(f"   Time: {schedule['current_hour']}:00 ({schedule['timezone']})")
    print(f"   Active: {'✅' if schedule['is_active'] else '❌'}")
    print(f"   Window: {schedule['active_window']}")

    # Warmup
    warmup_info = warmup.get_summary()
    print("\n🔥 Warmup:")
    warmup_status = "✅ Complete" if warmup_info['completed'] else f"⏳ {warmup_info['hours_remaining']:.1f}h remaining"
    print(f"   Status: {warmup_status}")
    print(f"   Sessions: {warmup_info['total_sessions']}")

    # Queue
    queue_stats = queue.get_stats()
    print(f"\n📋 Queue:")
    print(f"   Pending: {queue_stats['pending']}")
    print(f"   Approved (unsent): {queue_stats['approved_unsent']}")
    print(f"   Approval rate: {queue_stats['approval_rate']}%")
    print(f"   Auto-Pilot: {'✅' if queue_stats['auto_pilot_eligible'] else '❌'}")

    # Weekly stats
    weekly = guardrails.get_weekly_stats()
    if weekly:
        print(f"\n📅 Weekly Summary:")
        for date_key, actions in sorted(weekly.items(), reverse=True):
            total = sum(actions.values())
            connections = actions.get("connection", 0)
            views = actions.get("profile_view", 0)
            print(f"   {date_key}: {connections} connects, {views} views, {total} total actions")


def cmd_warmup(args):
    """Manually trigger a warm-up session."""
    from linkedin.warmup import WarmupSequence
    from browser import open_browser, close_browser, wait_for_stable
    from linkedin.auth import ensure_session, wait_for_login, is_logged_in

    warmup = WarmupSequence()

    if warmup.is_complete:
        print("✅ Warm-up already complete! Outreach is unlocked.")
        return

    print(f"🔥 Starting warm-up session ({warmup.hours_remaining:.1f}h remaining)...")

    page, context, playwright = open_browser("https://www.linkedin.com/feed/")
    wait_for_stable(page, timeout=10000)

    try:
        if not is_logged_in(page):
            logged_in = wait_for_login(page)
            if not logged_in:
                print("❌ Could not log in")
                return

        if not ensure_session(page):
            print("❌ Session issue")
            return

        warmup.run_session(page)
        summary = warmup.get_summary()
        print(f"\n✅ Session complete!")
        print(f"   Phase: {summary['phase']}")
        print(f"   Remaining: {summary['hours_remaining']:.1f}h")
        print(f"   Total likes: {summary['total_likes']}")
        print(f"   Total views: {summary['total_profile_views']}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        close_browser(context, playwright)


def cmd_setup(args):
    """Interactive first-time setup."""
    print("👻 GhostAgent First-Time Setup")
    print("=" * 40)

    env_file = os.path.join(os.path.dirname(__file__), ".env")

    config = {}

    print("\n1️⃣  LLM API Keys")
    config["DEEPSEEK_API_KEY"] = input("   DeepSeek API Key: ").strip()
    config["GEMINI_API_KEY"] = input("   Gemini API Key: ").strip()

    print("\n2️⃣  Proxy Settings (leave blank to skip)")
    config["PROXY_HOST"] = input("   Proxy Host: ").strip()
    config["PROXY_PORT"] = input("   Proxy Port: ").strip()
    config["PROXY_USER"] = input("   Proxy Username: ").strip()
    config["PROXY_PASS"] = input("   Proxy Password: ").strip()

    print("\n3️⃣  Location Settings")
    config["USER_TIMEZONE"] = input("   Timezone (e.g. Asia/Kolkata): ").strip() or "Asia/Kolkata"
    config["USER_LAT"] = input("   Latitude: ").strip() or "25.6"
    config["USER_LON"] = input("   Longitude: ").strip() or "84.9"

    # Write .env file
    with open(env_file, "w") as f:
        for key, value in config.items():
            if value:
                f.write(f"{key}={value}\n")

    print(f"\n✅ Config saved to {env_file}")
    print("\n4️⃣  Next step: Run 'python cli.py warmup' to start the 48h warm-up")
    print("    Then 'python cli.py review' to review AI-generated connection notes")
    print("    Finally 'python cli.py run' to start outreach!")


def cmd_test_search(args):
    """Test the search and people tab navigation."""
    from browser import open_browser, close_browser, wait_for_stable
    from linkedin.auth import ensure_session, wait_for_login, is_logged_in
    from navigator import navigate_to_search, _click_people_tab

    if not args:
        print("❌ Please provide a name to search for. Example: python cli.py test_search \"John Doe\"")
        return

    query = " ".join(args)
    print(f"🔍 Testing search functionality for: {query}")

    page, context, playwright = open_browser("https://www.linkedin.com/feed/")
    wait_for_stable(page, timeout=10000)

    try:
        if not is_logged_in(page):
            print("⚠️ Not logged in. Waiting for manual login...")
            logged_in = wait_for_login(page)
            if not logged_in:
                print("❌ Could not log in")
                return

        if not ensure_session(page):
            print("❌ Session issue")
            return

        print("✅ Logged in. Testing search...")
        navigate_to_search(page, query)
        
        print("✅ Search complete. Testing People tab...")
        _click_people_tab(page)
        
        print("🎉 Test complete! Browser will remain open for 15 seconds to inspect.")
        import time
        time.sleep(15)

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleaning up browser...")
        close_browser(context, playwright)


def cmd_test_connect(args):
    """Test connecting to a person after searching them."""
    from browser import open_browser, close_browser, wait_for_stable
    from linkedin.auth import ensure_session, wait_for_login, is_logged_in
    from linkedin.connect import send_connection

    if not args:
        print("❌ Please provide a name to search for. Example: python cli.py test_connect \"John Doe\"")
        return

    query = " ".join(args)
    print(f"🔗 Testing connect functionality for: {query}")

    page, context, playwright = open_browser("https://www.linkedin.com/feed/")
    wait_for_stable(page, timeout=10000)

    try:
        if not is_logged_in(page):
            print("⚠️ Not logged in. Waiting for manual login...")
            logged_in = wait_for_login(page)
            if not logged_in:
                print("❌ Could not log in")
                return

        if not ensure_session(page):
            print("❌ Session issue")
            return

        print("✅ Logged in. Testing connection flow...")
        note = f"Hi {query.split()[0]}, I'd like to join your LinkedIn network. (Test Note)"
        
        # Test the connection flow
        result = send_connection(page, query, note, guardrails=None)
        
        print(f"✅ Connection attempt complete. Result: {result['status']}")
        if result['status'] != 'sent':
            print(f"ℹ️ Reason/Details: {result.get('reason', 'Unknown')}")
            
        print("🎉 Test complete! Browser will remain open for 15 seconds to inspect.")
        import time
        time.sleep(15)

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleaning up browser...")
        close_browser(context, playwright)


def cmd_help(args=None):
    """Print help message."""
    print("""
👻 GhostAgent CLI

Commands:
  python cli.py setup              Interactive first-time setup
  python cli.py run [names...]     Start the agent (optional: prospect names)
  python cli.py run -c             Run in continuous mode (sleep/wake loop)
  python cli.py review             Review pending connection notes
  python cli.py stats              Show daily/weekly statistics
  python cli.py warmup             Manually trigger a warm-up session
  python cli.py test_search "Name" Test the search functionality isolated
  python cli.py test_connect "Name" Test the connection functionality isolated
  python cli.py help               Show this help message

Examples:
  python cli.py setup
  python cli.py warmup
  python cli.py test_search "Utkarsh Kumar Bakhtiyarpur"
  python cli.py test_connect "Utkarsh Kumar Bakhtiyarpur"
  python cli.py run "John Doe" "Jane Smith"
  python cli.py run -c
  python cli.py review
  python cli.py stats
""")


COMMANDS = {
    "run": cmd_run,
    "review": cmd_review,
    "stats": cmd_stats,
    "warmup": cmd_warmup,
    "setup": cmd_setup,
    "test_search": cmd_test_search,
    "test_connect": cmd_test_connect,
    "help": cmd_help,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    if command in COMMANDS:
        COMMANDS[command](args)
    else:
        print(f"Unknown command: {command}")
        cmd_help()
        sys.exit(1)
