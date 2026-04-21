"""Taskiq worker — spawns agent processes per LinkedIn account."""

import os
import signal
import multiprocessing
import redis
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taskiq_redis import RedisAsyncResultBackend, ListQueueBroker

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
broker = ListQueueBroker(REDIS_URL).with_result_backend(RedisAsyncResultBackend(REDIS_URL))


def _run_agent_process(account_id: str, continuous: bool, skip_warmup: bool = False,
                       task_id: str = None):
    from agent import run_agent
    run_agent(account_id=account_id, continuous=continuous, skip_warmup=skip_warmup,
              task_id=task_id)


def _run_login_process(account_id: str):
    from agent_login import run_login_flow
    run_login_flow(account_id=account_id)


def _run_legacy_agent_process(prospects: list, continuous: bool):
    from agent import run_agent
    run_agent(account_id=None, continuous=continuous, legacy_prospects=prospects)


def _pid_key(account_id: str) -> str:
    return f"ghost_os_pid_{account_id or 'legacy'}"


@broker.task(task_name="run_campaign")
def run_campaign_task(account_id: str = None, continuous: bool = False,
                      legacy_prospects: list = None, skip_warmup: bool = False,
                      task_id: str = None):
    r = redis.Redis.from_url(REDIS_URL)
    print(f"[Worker] run_campaign: account={account_id}, continuous={continuous}, skip_warmup={skip_warmup}, task_id={task_id}")
    try:
        ctx = multiprocessing.get_context("spawn")
        if account_id:
            p = ctx.Process(target=_run_agent_process, args=(account_id, continuous, skip_warmup, task_id))
        else:
            p = ctx.Process(target=_run_legacy_agent_process, args=(legacy_prospects or [], continuous))

        p.start()
        r.set(_pid_key(account_id), p.pid, ex=86400)
        p.join()
        r.delete(_pid_key(account_id))

        if p.exitcode not in (0, -15):
            raise Exception(f"Agent exited with code {p.exitcode}")

        return {"status": "success"}
    except Exception as e:
        print(f"[Worker] Campaign failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        r.close()


@broker.task(task_name="stop_campaign")
def stop_campaign_task(account_id: str = None):
    r = redis.Redis.from_url(REDIS_URL)
    pid_bytes = r.get(_pid_key(account_id))
    if pid_bytes:
        pid = int(pid_bytes)
        try:
            os.kill(pid, signal.SIGTERM)
            r.delete(_pid_key(account_id))
            return {"status": "killed", "pid": pid}
        except ProcessLookupError:
            r.delete(_pid_key(account_id))
    return {"status": "not_running"}


@broker.task(task_name="login")
def login_task(account_id: str):
    """Spawns a visible browser for LinkedIn login flow."""
    r = redis.Redis.from_url(REDIS_URL)
    print(f"[Worker] login: account={account_id}")
    try:
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(target=_run_login_process, args=(account_id,))
        p.start()
        r.set(f"ghost_os_login_pid_{account_id}", p.pid, ex=600)  # 10 min timeout
        p.join(timeout=600)
        if p.is_alive():
            p.terminate()
        r.delete(f"ghost_os_login_pid_{account_id}")
        return {"status": "completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        r.close()
