import sip

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

# import public
from .integration.auto import install as install_mainloop  # it must be before the others, since it removes some hacks
from .main_window import MainWindow
from .windows import window
from .helpers import input_value_from_list, input_value_from_range, display_image, display_variable, axes, imshow
from .reactive import var, const, reactive, reactive_finalizable, unwrap

# fixme: ability to disable this
install_mainloop()
