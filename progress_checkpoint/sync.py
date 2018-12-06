from typing import Sequence, Callable, Union, List, Optional

from deprecation import deprecated

ProgressFraction = float  # from to 1
StatusMessage = Union[str, List['str']]
Checkpoint = Callable[[ProgressFraction, Optional[StatusMessage]], None]


def dummy_checkpoint(progress, status=None):
    return


@deprecated("use with_progress()")
def reporting_progress(seq: Sequence, checkpoint: Checkpoint, size=None, status=None, div=1):
    size = size if size is not None else len(seq)
    if checkpoint is not None:
        checkpoint(0, status or '')
    for i, e in enumerate(seq):
        yield e
        if i % div == 0:
            if checkpoint is not None:
                checkpoint((i + 1) / size, status)


def subcheckpoint(checkpoint, start, stop, parent_status=None):
    if checkpoint is None:
        return None

    def new_checkpoint(progress, status):
        if not status:
            st = parent_status
        elif not parent_status:
            st = status
        else:
            st = parent_status + " / " + status
        return checkpoint(progress * (stop-start) + start, st)

    return new_checkpoint


def with_progress(seq: Sequence, checkpoint: Checkpoint, size=None, status=None, with_sub=False,
                  weights: Sequence[float] = None, div=1):
    size = size if size is not None else len(seq)

    if weights is None:
        weights = [1] * size
    total_weight = sum(weights)
    weight_done = 0

    checkpoint(0, status or '')

    for i, (e, w) in enumerate(zip(seq, weights)):
        if with_sub:
            yield e, CheckpointManager(subcheckpoint(checkpoint,
                                                     weight_done / total_weight,
                                                     (weight_done + w) / total_weight))
        else:
            yield e

        weight_done += w

        if i % div == 0:
            checkpoint(weight_done / total_weight, status)


def subcheckpoints(checkpoint, weights=None, size=None):
    if weights is None and size is not None:
        weights = [1] * size
    total_weight = sum(weights)
    weight_done = 0
    result = []
    for w in weights:
        result.append(CheckpointManager(subcheckpoint(checkpoint,
                                                      weight_done / total_weight,
                                                      (weight_done + w) / total_weight)))
        weight_done += w

    return result



@deprecated("use free functions")
class CheckpointManager:
    def __init__(self, checkpoint):
        self.checkpoint = checkpoint or dummy_checkpoint
        self.status = None
        self.frac_used = 0

    def set_status(self, status):
        self.status = status

    def report(self, progress):
        self.frac_used = progress
        return self.checkpoint(progress, self.status)

    def __call__(self, progress, status=None):
        if status is not None:
            self.set_status(status)
        return self.report(progress)

    def sub(self, start=None, stop=None, parent_status=None):
        if start is None:
            start = self.frac_used
        if stop is None:
            stop = 1.0
        self.frac_used = stop
        return CheckpointManager(subcheckpoint(self.checkpoint, start, stop, parent_status))

    def iterate(self, seq, size=None, status=None, make_sub=False, weights: Sequence[float] = None, div=1):
        size = size if size is not None else len(seq)

        if weights is None:
            weights = [1] * size
        total_weight = sum(weights)
        weight_done = 0

        self.checkpoint(0, status or '')

        for i, (e, w) in enumerate(zip(seq, weights)):
            if make_sub:
                yield e, CheckpointManager(subcheckpoint(self.checkpoint,
                                                         weight_done / total_weight,
                                                         (weight_done + w) / total_weight))
            else:
                yield e

            weight_done += w

            if i % div == 0:
                self.checkpoint(weight_done / total_weight, status)

        self.frac_used = 1.0

    def iterate_wc(self, seq, size=None, status=None, weights: Sequence[float] = None):
        return self.iterate(seq, size, status, weights=weights, make_sub=True)

    def divide(self, weights=None, size=None):
        if weights is None and size is not None:
            weights = [1] * size
        total_weight = sum(weights)
        weight_done = 0
        result = []
        for w in weights:
            result.append(CheckpointManager(subcheckpoint(self.checkpoint,
                                                          weight_done / total_weight,
                                                          (weight_done + w) / total_weight)))
            weight_done += w

        return result


def ensure_checkpoint(checkpoint) -> CheckpointManager:
    if isinstance(checkpoint, CheckpointManager):
        return checkpoint
    else:
        return CheckpointManager(checkpoint)
