import sip

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

# import public
from .main_window import MainWindow, gcmw, make_main_window
from .mainloop.auto import install as install_mainloop
from .helpers import input_value_from_list, input_value_from_range, display_image, display_variable

# fixme: ability to disable this
install_mainloop()
