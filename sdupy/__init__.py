import logging
import sip

import sys

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

# import public
from .integration.auto import install as install_mainloop  # it must be before the others, since it removes some hacks
from .main_window import MainWindow
from .windows import window
#from .widgets.helpers import input_value_from_list, vis.slider, display_image, vis.var_in_table, axes, \
#    imshow, \
#    var_from_table
from .pyreactive import var, const, reactive, reactive_finalizable, unwrap

# fixme: ability to disable this
install_mainloop()

# fixme: move it somewhere or disable conditionally
stderr_logger_handler = logging.StreamHandler(stream=sys.stderr)
logging.getLogger().addHandler(stderr_logger_handler)
stderr_logger_handler.setLevel(logging.INFO)
