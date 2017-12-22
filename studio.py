import numpy as np
import pandas as pd
import sip
sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

from PyQt5 import QtCore

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QDockWidget, QWidget, QHBoxLayout, QTreeView


class Studio:
    def __init__(self):
        size=10*1
        arr=np.array(np.random.randn(size, 4))
        #arrs=np.array(list(map(tuple, arr.tolist())), dtype=dict(names=['a', 'b', 'c', 'd'], formats=[np.float]*4))
        test_data = pd.DataFrame(arr, columns=['a', 'b', 'c', 'd'])
        self.data = {"test": test_data, "test2": test_data}

    def get_data(self):
        return self.data





class DataTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, studio, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.studio = studio
        self.data = studio.get_data()

    def rowCount(self, parent=None):
        return len(self.data)

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return QtCore.QVariant(str(self.data.keys()[index.row()]))
        return QtCore.QVariant()




        
print("heja3")
