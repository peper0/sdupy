from progressbar import ProgressBar, widgets as pbwidgets


def status_string(status, size=50):
    status += " " * (size - len(status))
    if len(status) > size:
        status = "..." + status[-size + 3:]
    return status


class ProgressbarCheckpoint:
    def __init__(self):
        self.status_label = pbwidgets.FormatLabel(status_string(""))
        self.pb = ProgressBar(1.0, widgets=[self.status_label,
                                            pbwidgets.Percentage(), ' ', pbwidgets.Bar(),
                                            pbwidgets.FormatLabel(" %(elapsed)s "),
                                            pbwidgets.AdaptiveETA(),
                                            ])
        self.last_status = None
        self.pb.start()

    def __call__(self, progress, status=None):
        if status != self.last_status:
            if status:
                self.status_label.format_string = status_string(status)
                print(status)
            self.last_status = status
        if progress >= 1.0:
            self.pb.finish()
        else:
            self.pb.update(progress)


class ProgressbarCheckpointAsync:
    def __init__(self):
        self.sync = ProgressbarCheckpoint()

    async def __call__(self, *args, **kwargs):
        return self.sync(*args, **kwargs)
