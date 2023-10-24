import numpy as np

import sdupy
from sdupy import vis, reactive

sdupy.window("sdupy example - sine")

x = np.arange(0, 1, 0.001) * np.pi * 2
freq = vis.slider("frequency", min=0.1, max=10, value=2, step=0.1)
amp = vis.slider("amplitude", min=0.1, max=10, value=2, step=0.1)
vis.plot_mpl("sine", x, amp * reactive(np.sin)(freq * x))

sdupy.run_mainloop()
