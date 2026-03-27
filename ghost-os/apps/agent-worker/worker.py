import os
from taskiq_redis import RedisAsyncResultBackend
from taskiq_redis import ListQueueBroker

# Make sure relative imports like "agent.py" work easily in worker
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Setup TaskIQ Broker
broker = ListQueueBroker(redis_url).with_result_backend(RedisAsyncResultBackend(redis_url))

import multiprocessing

def _run_agent_process(prospects, continuous):
    from agent import run_agent
    run_agent(prospects=prospects, continuous=continuous)

import redis
import signal

@broker.task(task_name="stop_campaign")
def stop_campaign_task():
    r = redis.Redis.from_url(redis_url)
    pid_bytes = r.get("ghost_os_active_pid")
    if pid_bytes:
        pid = int(pid_bytes)
        try:
            os.kill(pid, signal.SIGTERM)
            r.delete("ghost_os_active_pid")
            return {"status": "killed", "pid": pid}
        except ProcessLookupError:
            pass
    return {"status": "not_running"}

@broker.task(task_name="run_campaign")
def run_campaign_task(prospects: list = None, continuous: bool = False):
    """
    TaskIQ task to run Ghost-OS outreach campaigns.
    Reads from the Redis queue.
    """
    print(f"[Worker] Received run_campaign job! Prospects: {prospects}, Continuous: {continuous}")
    try:
        # Run agent in a separate process to avoid greenlet/asyncio thread conflicts
        # between TaskIQ's async environment and patchright's sync_api
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(target=_run_agent_process, args=(prospects, continuous))
        p.start()
        
        # Track the active process ID in Redis for the kill switch
        r = redis.Redis.from_url(redis_url)
        r.set("ghost_os_active_pid", p.pid)
        
        p.join()
        
        # Cleanup
        r.delete("ghost_os_active_pid")
        
        if p.exitcode != 0 and p.exitcode != -15:  # -15 is SIGTERM (killed by us)
            raise Exception(f"Agent process exited with code {p.exitcode}")
            
        return {"status": "success", "message": "Campaign completed successfully"}
    except Exception as e:
        print(f"[Worker] Campaign failed: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # If this script is run manually, it acts as a test trigger
    import asyncio
    
    async def trigger():
        await broker.startup()
        if len(sys.argv) > 1 and sys.argv[1] == "trigger":
            print("[Trigger] Firing test campaign job to Redis...")
            prospects = sys.argv[2:] if len(sys.argv) > 2 else ["Test Profile"]
            task = await run_campaign_task.kiq(prospects=prospects, continuous=False)
            print(f"[Trigger] Job dispatched. Task ID: {task.task_id}")
            
            # Wait a little bit for the job execution to be visible
            print("[Trigger] You can monitor the worker logs in Docker.")
        await broker.shutdown()

    asyncio.run(trigger())
