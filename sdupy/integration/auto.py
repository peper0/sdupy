
try:
    from . import pydev_ipython  # workaround for importing it here fix the problem with matplotlib?
except:
    pass


def get_module():
    global install, run_mainloop
    ipython = None

    try:
        ipython = get_ipython()
    except Exception:
        pass


    #print("ipython", ipython)
    if ipython is not None:
        if ipython.__class__.__name__ == 'PyDevTerminalInteractiveShell':
            print("pydev_ipython detected")
            from . import pydev_ipython
            return pydev_ipython
        elif ipython.__class__.__name__ == 'ZMQInteractiveShell':
            print("jupyter python kernel detected")
            from . import jupyter
            return jupyter
        else:
            print("unknown IPython class: {}".format(ipython.__class__.__name__))

    print("no supported ipython/jupyter environment detected")
    from . import standalone
    return standalone


def install():
    get_module().install()


def run_mainloop():
    get_module().run_mainloop()


__all__ = ['install', 'run_mainloop']

