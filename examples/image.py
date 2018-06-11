import cv2

import sdupy
from sdupy import vis

sdupy.window("test")

path = vis.var_in_table('vars', 'path', sdupy.var('sdupy_repo/examples/lena.png'))
image = sdupy.reactive(cv2.imread)(path)
ii=vis.image_mpl('ttt', image)





path @= 'LARGE_elevation.jpg'


image_shown = [sdupy.axes('ble').imshow(image, extent=(0, 1, i, i + 1)) for i in range(1)]
