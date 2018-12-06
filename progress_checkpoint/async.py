import asyncio
from typing import Sequence


"""
WARNING! copy-pasted from progress_checkpoint.progress!

NOTE! consider using sync_progress instead of this one
"""


async def reporting_progress(seq: Sequence, checkpoint, size=None, status=None, div=1):
    size = size if size is not None else len(seq)
    if checkpoint is not None:
        await checkpoint(0, status or '')
    for i, e in enumerate(seq):
        yield e
        if i % div == 0:
            if checkpoint is not None:
                await checkpoint((i + 1) / size, status)
                await asyncio.sleep(0.000001)
    await checkpoint(1.0, status)


def subcheckpoint(checkpoint, start, stop, parent_status=None):
    if checkpoint is None:
        return None

    async def f(progress, status):
        if not status:
            st = parent_status
        elif not parent_status:
            st = status
        else:
            st = parent_status + " / " + status
        return await checkpoint(progress * (stop-start) + start, st)

    return f


async def dummy_checkpoint(progress, status=None):
    return
