import os
from taskiq_redis import RedisAsyncResultBackend
from taskiq_redis import ListQueueBroker

# Make sure relative imports like "agent.py" work easily in worker
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Setup TaskIQ Broker
broker = ListQueueBroker(redis_url).with_result_backend(RedisAsyncResultBackend(redis_url))

@broker.task(task_name="run_campaign")
def run_campaign_task(prospects: list = None, continuous: bool = False):
    """
    TaskIQ task to run Ghost-OS outreach campaigns.
    Reads from the Redis queue.
    """
    from agent import run_agent
    
    print(f"[Worker] Received run_campaign job! Prospects: {prospects}, Continuous: {continuous}")
    try:
        run_agent(prospects=prospects, continuous=continuous)
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
