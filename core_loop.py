import asyncio
import threading


class CoreLoop:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.tasks = []
        self._task_lock = threading.Lock()

    def start(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self.loop.close()

    def stop(self):
        def _stop():
            with self._task_lock:
                tasks = list(self.tasks)
            for task in tasks:
                task.cancel()
            self.loop.stop()

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(_stop)
        else:
            _stop()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def add_task(self, coro):
        def _create():
            task = self.loop.create_task(coro)
            task.add_done_callback(self._remove_task)
            with self._task_lock:
                self.tasks.append(task)
            if task.done():
                self._remove_task(task)

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(_create)
        else:
            _create()

    def _remove_task(self, task):
        with self._task_lock:
            if task in self.tasks:
                self.tasks.remove(task)
