import sip

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

# import public
from .main_window import MainWindow, gcmw, main_window
from .mainloop.auto import install as install_mainloop

# fixme: ability to disable this
install_mainloop()
