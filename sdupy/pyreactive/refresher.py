import asyncio
import gc
import logging
from contextlib import suppress
from typing import Any, Callable, NamedTuple

from sdupy.pyreactive.common import NotifyFunc

logger = logging.getLogger('refresher')


class QueueItem(NamedTuple):
    priority: int
    id: Any  # FIXME: remove id (callable MUST be hashable, we use wrapper if it isn't)
    func: Callable
    stats: dict

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

    def schedule_call(self, func: NotifyFunc, id, priority, stats):
        if priority is None:
            priority = 999999
        t = QueueItem(priority, id, func, stats)
        self.queue.put_nowait(t)
        self.maybe_start_task()

    async def run(self):
        gc.collect()
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
                    update.stats['calls'] = update.stats.get('calls', 0) + 1
                    f = update.func
                    res = f()
                    if asyncio.iscoroutine(res):
                        await res
                    update.stats['exception'] = None
                except Exception as e:
                    logger.exception('ignoring exception when in notifying observer {}'.format(update.func))
                    update.stats['exception'] = e
        gc.collect()


refresher = None


def get_default_refresher():
    global refresher
    if not refresher:
        refresher = AsyncRefresher()

    return refresher


async def wait_for_var(var=None):
    # fixme: waiting only for certain level (if var is not None)
    task = get_default_refresher().task
    if task:
        await task
