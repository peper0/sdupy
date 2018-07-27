import asyncio
from typing import Sequence
import logging


class Progress:
    def __init__(self):
        self.logger = logging.getLogger()
        self._progress = 0
        self._current_status = ""
        self.set_progress_cbk = lambda: None

    def set_progress(self, val):
        self._progress = val

    def set_status(self, status):
        self._current_status = status

    async def set_status_and_show(self, status):
        self._current_status = status
        await asyncio.sleep(0.001)

    async def checkpoint(self, progress, status=None):
        self.set_progress(progress)
        if status is not None:
            self.set_status(status)
        await asyncio.sleep(0.001)


async def reporting_progress(seq: Sequence, checkpoint, size=None, status=None, div=1):
    size = size if size is not None else len(seq)
    if checkpoint is not None:
        await checkpoint(0, status or '')
    for i, e in enumerate(seq):
        yield e
        if i % div == 0:
            if checkpoint is not None:
                await checkpoint((i + 1) / size, status)
                await asyncio.sleep(0.001)


def subcheckpoint(checkpoint, start, stop, parent_status):
    if checkpoint is None:
        return None

    async def f(progress, status):
        if not status:
            st = parent_status
        elif not parent_status:
            st = status
        else:
            st = parent_status + " / " + status
        return await checkpoint(progress / (stop-start) + start, st)

    return f


async def dummy_checkpoint(progress, status):
    return
