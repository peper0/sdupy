ipython = None

try:
    ipython = get_ipython()
except Exception:
    pass

if ipython is None:
    print("no ipython/jupyter environment detected, call 'run_loop()' after initialization of the application")
    from .standalone import run_mainloop

    unused = run_mainloop


    def install():
        print("no ipython/jupyter environment detected, call 'run_loop()' after initialization of the application")
else:
    if ipython.__class__.__name__ == 'PyDevTerminalInteractiveShell':
        print("pydev_ipython detected")
        from .pydev_ipython import install
    elif ipython.__class__.__name__ == 'ZMQInteractiveShell':
        print("jupyter python kernel detected")
        from .jupyter import install

unused = install  # just ensure IDE that it is used
