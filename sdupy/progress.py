import asyncio
import logging
from typing import Sequence


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


async def reporting_progress(seq: Sequence, progress: Progress, size=None, status=None, div=1):
    size = size if size is not None else len(seq)
    if status is not None and progress is not None:
        progress.set_status(status)
    for i, e in enumerate(seq):
        yield e
        if i % div == 0:
            if progress is not None:
                progress.set_progress((i+1)/size)
                await asyncio.sleep(0.001)