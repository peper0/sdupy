import logging
import sys

from .integration.auto import install as install_mainloop  # it must be before the others, since it removes some hacks
from .integration.auto import run_mainloop
from .main_window import MainWindow
# from .widgets.helpers import input_value_from_list, vis.slider, display_image, vis.var_in_table, axes, \
#    imshow, \
#    var_from_table
from .pyreactive import var, const, reactive, reactive_finalizable, unwrap
from .windows import window, window_as_current
from .pyreactive import settings





# fixme: move it somewhere or disable conditionally
# stderr_logger_handler = logging.StreamHandler(stream=sys.stderr)
# logging.getLogger().addHandler(stderr_logger_handler)
# stderr_logger_handler.setLevel(logging.INFO)

__all__ = [
    'MainWindow',
    'window',
    'window_as_current',
    'var',
    'const',
    'reactive',
    'reactive_finalizable',
    'unwrap',
    'settings',
    'install_mainloop',
    'run_mainloop',
]
