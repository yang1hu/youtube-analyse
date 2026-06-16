from __future__ import annotations

import argparse
import time

from creator_agent.config import Settings
from creator_agent.services.analysis_audit_logger import AnalysisAuditLogger
from creator_agent.services.monitor_service import MonitorService
from creator_agent.services.redis_task_queue import RedisTaskQueue
from creator_agent.services.task_service import TaskService


def run_worker(*, once: bool = False, idle_sleep_seconds: float = 2.0, monitor: bool = True) -> None:
    settings = Settings()
    queue = RedisTaskQueue(settings)
    service = TaskService(settings)
    monitor_service = MonitorService(settings, task_service=service)
    audit_logger = AnalysisAuditLogger(settings)

    while True:
        task_id = queue.dequeue(timeout_seconds=1)
        if task_id:
            try:
                service.run_task(task_id, from_queue=True)
            except ValueError as exc:
                audit_logger.write("worker_skipped_stale_task", task_id=task_id, error=str(exc))
            except Exception as exc:
                audit_logger.write("worker_task_error", task_id=task_id, error=str(exc))
        elif monitor:
            try:
                monitor_service.run_if_due()
            except Exception as exc:
                audit_logger.write("worker_monitor_error", error=str(exc))
        elif once:
            return
        if once:
            return
        else:
            time.sleep(idle_sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the YouTube Creator Agent Redis task worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one available task, then exit.")
    parser.add_argument("--idle-sleep", type=float, default=2.0, help="Sleep interval when the Redis queue is empty.")
    parser.add_argument("--no-monitor", action="store_true", help="Disable scheduled channel monitoring in this worker.")
    args = parser.parse_args()
    run_worker(once=args.once, idle_sleep_seconds=args.idle_sleep, monitor=not args.no_monitor)


if __name__ == "__main__":
    main()
