import cv2

import sdupy

sdupy.window("test")

path = sdupy.var_from_table('vars', 'path', sdupy.var('./lena.png'))

path @= 'LARGE_elevation.jpg'

image = sdupy.reactive(cv2.imread)(path)

image_shown = [sdupy.axes('ble').imshow(image, extent=(0, 1, i, i + 1)) for i in range(1)]
