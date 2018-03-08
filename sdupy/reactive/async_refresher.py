import asyncio
import logging
from contextlib import suppress
from typing import Any, Callable, NamedTuple

logger = logging.getLogger('refresher')


class QueueItem(NamedTuple):
    priority: int
    id: Any
    func: Callable

    def __lt__(self, other):
        return self.priority < other.priority


class AsyncRefresher:
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self.task = None  # type: asyncio.Task

    def maybe_start_task(self):
        if not self.task or self.task.done():
            self.task = asyncio.ensure_future(self.run())  # type: asyncio.Task
            self.task.add_done_callback(self._handle_done)

    @staticmethod
    def _handle_done(f):
        if f.cancelled():
            logger.warning('refresh task was cancelled')
            return
        e = f.exception()
        if e:
            logger.exception('refresh task finished with exception, rethrowing')
            raise e

    def schedule_call(self, hash, func: Callable):
        t = QueueItem(1, hash, func)
        self.queue.put_nowait(t)
        self.maybe_start_task()

    async def run(self):
        update_next = None

        with suppress(asyncio.QueueEmpty):  # it's ok - if the queue is empty we just exit
            while True:
                update = update_next if update_next else self.queue.get_nowait()  # type: QueueItem
                try:
                    update_next = self.queue.get_nowait()
                    if update_next.id == update.id:  # skip update if is same as next
                        continue
                except asyncio.QueueEmpty:
                    update_next = None

                try:
                    f = update.func
                    if asyncio.iscoroutinefunction(f):
                        await f()
                    elif hasattr(f, '__call__'):
                        f()
                except Exception as e:
                    logger.exception('exception when notifying observer (ignoring)')
