from typing import Union, List, Callable, Optional, Sequence, Awaitable, Coroutine

ProgressFraction = float  # from to 1
StatusMessage = Union[str, List['str']]
Checkpoint = Callable[[ProgressFraction, Optional[StatusMessage]], None]
AsyncCheckpoint = Callable[[ProgressFraction, Optional[StatusMessage]], Coroutine]


def subcheckpoint(checkpoint, start, stop, parent_status=None):
    if checkpoint is None:
        return None

    def new_checkpoint(progress, status=None):
        if not status:
            st = parent_status
        elif not parent_status:
            st = status
        else:
            st = parent_status + " / " + status
        return checkpoint(progress * (stop - start) + start, st)

    return new_checkpoint


def subcheckpoints(checkpoint, weights=None, statuses=None, status_pattern=None, size=None):
    if size is None:
        if isinstance(weights, Sequence):
            size = len(weights)
        else:
            weights = list(weights)
            size = len(weights)

    if isinstance(weights, Sequence):
        assert (len(weights) == size)

    if isinstance(statuses, Sequence):
        assert (len(statuses) == size)

    if weights is None and size is not None:
        weights = [1] * size

    if statuses is None:
        statuses = [None] * size

    total_weight = sum(weights)
    weight_done = 0

    for i, w, status in zip(range(size), weights, statuses):
        if status_pattern:
            status = status_pattern.format(i=i + 1, size=size, weight_done=weight_done, total_weight=total_weight)
        yield subcheckpoint(checkpoint,
                            weight_done / total_weight,
                            (weight_done + w) / total_weight,
                            status)
        weight_done += w