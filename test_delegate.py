import sys
from PyQt5.QtWidgets import QApplication, QTableView,  QItemDelegate
from PyQt5.QtGui import QColor
import sys
from commons import *
from PyQt5 import QtCore, QtGui, QtWidgets, QtSql
from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTreeView, QTableView

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
from PyQt5.QtWidgets import QApplication, QTableView, QItemDelegate
from PyQt5.QtGui import QColor

import sys
from PyQt5.QtWidgets import QApplication, QTableView, QItemDelegate
from PyQt5.QtGui import QColor, QPainter, QStandardItemModel, QStandardItem



class ColoredColumnDelegate(QItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() == 0:
            painter.fillRect(option.rect, QColor(255, 0, 0, 100))  # Rouge semi-transparent

class MainWindow(QTableView):
    def __init__(self):
        super().__init__()

        self.model = QStandardItemModel(self)
        self.setItemDelegateForColumn(0, ColoredColumnDelegate())

        self.model.setColumnCount(3)
        self.model.setRowCount(5)

        for row in range(5):
            for col in range(3):
                item = QStandardItem(f"Row {row}, Col {col}")
                self.model.setItem(row, col, item)

        self.setModel(self.model)
        self.setWindowTitle("QTableView avec couleur de fond personnalisée")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())


