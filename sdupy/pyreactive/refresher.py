import asyncio
import gc
import logging
from contextlib import suppress
from typing import Any, NamedTuple

import sys

stderr_logger_handler = logging.StreamHandler(stream=sys.stderr)
stderr_logger_handler.setLevel(logging.DEBUG)
logger = logging.getLogger('notify')
logger.addHandler(stderr_logger_handler)
logger.setLevel(logging.INFO)


class QueueItem(NamedTuple):
    priority: int
    id: Any  # FIXME: remove id (callable MUST be hashable, we use wrapper if it isn't)
    notifier: 'Notifier'
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

    def schedule_call(self, notifier: 'Notifier'):
        logger.debug('  scheduled notification ({}) [{:X}] {}'.format(notifier.priority, id(notifier), notifier.name))
        t = QueueItem(notifier.priority, notifier, notifier, notifier.stats)
        self.queue.put_nowait(t)
        self.maybe_start_task()

    async def run(self):
        gc.collect()
        update_next = None

        notified_notifiers = set()
        with suppress(asyncio.QueueEmpty):  # it's ok - if the queue is empty we just exit
            while True:
                notification = update_next if update_next else self.queue.get_nowait()  # type: QueueItem
                try:
                    update_next = self.queue.get_nowait()
                    if update_next.id == notification.id:  # skip notification if is same as next
                        continue
                except asyncio.QueueEmpty:
                    update_next = None

                try:
                    notification.stats['calls'] = notification.stats.get('calls', 0) + 1
                    notifier = notification.notifier
                    if notifier in notified_notifiers:
                        logger.debug('notifier [{:X}] {} called more than once'.format(id(notifier), notifier.name))
                    notified_notifiers.add(notifier)
                    logger.debug('call notification ({}) [{:X}] {}'.format(notifier.priority, id(notifier),
                                                                           notifier.name))

                    res = notifier.notify()
                    if asyncio.iscoroutine(res):
                        res = await res
                    notification.stats['exception'] = None

                    assert isinstance(res, bool), "res has type {}, should be bool for {}".format(type(res),
                                                                                                  notifier.name)
                    if res:
                        logger.debug(' notification finished with True, notifying observers')
                        notification.notifier.notify_observers()
                        logger.debug(' finished')
                    else:
                        logger.debug(' notification finished with False')

                except Exception as e:
                    logger.exception('ignoring exception when in notifying observer {}'.format(notification.notifier))
                    notification.stats['exception'] = e
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
