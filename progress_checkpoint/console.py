from progressbar import ProgressBar, widgets as pbwidgets


class ProgressbarCheckpointAsync:
    def __init__(self):
        self.pb = ProgressBar(1.0, widgets=[pbwidgets.Percentage(), ' ', pbwidgets.Bar(),
                                            pbwidgets.FormatLabel(" %(elapsed)s "),
                                            pbwidgets.AdaptiveETA(),
                                            ])
        self.last_status = None
        self.pb.start()

    async def __call__(self, progress, status=None):
        if status != self.last_status:
            if status:
                print(status)
            self.last_status = status
        self.pb.update(progress)
        if progress >= 1.0:
            self.pb.finish()


class ProgressbarCheckpoint:
    def __init__(self):
        self.pb = ProgressBar(1.0, widgets=[pbwidgets.Percentage(), ' ', pbwidgets.Bar(),
                                            pbwidgets.FormatLabel(" %(elapsed)s "),
                                            pbwidgets.AdaptiveETA(),
                                            ])
        self.last_status = None
        self.pb.start()

    def __call__(self, progress, status=None):
        if status != self.last_status:
            if status:
                print(status)
            self.last_status = status
        self.pb.update(progress)
        if progress >= 1.0:
            self.pb.finish()