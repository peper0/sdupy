from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsRectItem
from imageio.v3 import imread

import sdupy
from sdupy import vis, reactive

sdupy.window("sdupy example - image")

img_path = vis.combo('path', choices=['examples/images/flower.jpg', 'examples/images/lena.png'])
image = sdupy.reactive(imread)(img_path)
img_widget = vis.image_pg_adv("image", image, autoLevels=True)

img_row_index = vis.slider("row", min=0, max=image.shape[0] - 1, value=0)
img_row = image[img_row_index]
vis.plot_mpl("selected row", img_row)


@reactive
def mark_row(row, width):
    pen = QPen(QColor(255, 0, 0))
    pen.setCosmetic(True)

    el = QGraphicsRectItem(0, row, width, 1)
    el.setPen(pen)
    return [el]


line = vis.draw_pg("image", "ddd", mark_row(img_row_index, image.shape[1]))

sdupy.run_mainloop()
