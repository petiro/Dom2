import os
from queue import Queue
from threading import Thread

from core_loop import CoreLoop
from core_services import CoreServices
from ui.desktop_app import run_v6_app


def _start_core(core):
    core.start()


def main():
    queue = Queue()
    core = CoreLoop()
    api_id = int(os.getenv("DOM2_API_ID", "0") or 0)
    api_hash = os.getenv("DOM2_API_HASH", "")
    services = CoreServices(core, queue, api_id=api_id, api_hash=api_hash)

    core_thread = Thread(target=_start_core, args=(core,), daemon=True)
    core_thread.start()

    services_future = core.run_async(services.start_all())

    def _report_startup_failure(future):
        try:
            exc = future.exception()
        except Exception as exc:
            queue.put(("core", f"Service startup error: {exc}"))
            return
        if exc:
            queue.put(("core", f"Service startup error: {exc}"))

    services_future.add_done_callback(_report_startup_failure)

    try:
        return run_v6_app(core, queue)
    finally:
        core.stop()
        core_thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
