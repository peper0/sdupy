from typing import Union

from sdupy import MainWindow

current_main_window = None  # type: MainWindow

windows_by_name = dict()


def gcw() -> MainWindow:
    """
    Get current main window.
    """
    global current_main_window
    if not current_main_window:
        window()
    return current_main_window


def set_current_window(window):
    global current_main_window
    current_main_window = window


def window(name=None):
    """
    Returns window with given name. Create it if doesn't exist. If `name` is `None`, generate a name automatically.
    :param name:
    :return:
    """
    if name is None:
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
    set_current_window(window)

    return window


WindowSpec = Union[str, MainWindow, None]


def window_for_spec(window_specifier: WindowSpec = None):
    if window_specifier is None:
        return gcw()
    elif isinstance(window_specifier, str):
        return window(window_specifier)
    elif isinstance(window_specifier, MainWindow):
        return MainWindow
