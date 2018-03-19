from typing import Union

from sdupy import MainWindow

current_main_window = None  # type: MainWindow

windows_by_name = dict()

WindowSpec = Union[str, MainWindow, None]


def window(name: WindowSpec = None):
    """
    Returns window with given name. Create it if doesn't exist. If `name` is `None`, return last window used.
    :param name:
    :return:
    """
    global current_main_window
    if isinstance(name, MainWindow):
        current_main_window = name
        return name
    if name is None:
        if current_main_window is not None:
            return current_main_window
        for i in range(1, 1000000):
            name = "window{}".format(i)
            if name not in windows_by_name:
                break
        persistence_id = None
    else:
        persistence_id = name

    if name in windows_by_name:
        window = windows_by_name[name]
    else:
        window = MainWindow(title=name, persistence_id=persistence_id)
        window.show()

        def window_closed():
            del windows_by_name[name]
            global current_main_window
            if current_main_window == window:
                current_main_window = None

        window.close_callback = window_closed
        windows_by_name[name] = window

    current_main_window = window
    return window
