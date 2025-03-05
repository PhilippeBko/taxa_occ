import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
#from pn_treeview import *

class rowtable(object):
    dict_rang =  {0 : 'Unknown', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'Subspecies', 23 : 'Variety'}
    def __init__(self, idtaxonref, taxaname, authors, idrang, taxascore = 0):
        self.authors = authors
        self.taxa_name = taxaname
        self.id_rang = idrang
        self.id_taxon_ref = idtaxonref
        self.taxa_score = taxascore

    @property
    def rank_txt (self):
        try :
            txt_rk = rowtable.dict_rang[self.id_rang]
        except :
            txt_rk = rowtable.dict_rang[0]   
        return txt_rk
        
    @property
    def columnCount(self):
        return 4
    @property
    def status(self):
        if self.taxa_score > 0 and self.taxa_score < 1:
            return 2
        else:
            return self.taxa_score



class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data = None):
        super(TableModel, self).__init__()
        self._data = []
        self._data = data if data != None else []

    def clear(self):
        self._data = []
        self.reset()

    def data(self, index, role):
        if not index.isValid():
            return None
        if 0 <= index.row() < self.rowCount():
            item = self._data[index.row()]
            col = index.column()        
            if role == Qt.DisplayRole:
                if col==0:
                    return item.taxa_name
                elif col==1:
                    return item.authors
                elif col==2:
                    return item.rank_txt
            elif role == QtCore.Qt.DecorationRole:
                if col == 0:
                    status = getattr(item, 'status', 0)

                    col = QtGui.QColor(255,0,0,255)
                    if status == 1:
                        col = QtGui.QColor(255,128,0,255)
                    elif status == 2:
                        col = QtGui.QColor(255,255,0,255)

                    px = QtGui.QPixmap(50,50)
                    px.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(px)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    px_size = px.rect().adjusted(5,5,-5,-5)
                    painter.setBrush(col)
                    painter.setPen(QtGui.QPen(QtCore.Qt.black, 4,
                        QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.drawEllipse(px_size)
                    painter.end()

                    return QtGui.QIcon(px)

    def rowCount(self, index=QtCore.QModelIndex()):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index=QtCore.QModelIndex()):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        try:
            return self._data[0].columnCount # len(self._data[0])
        except:
            return 0

    def additem (self, clrowtable):
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(clrowtable)
        self.endInsertRows()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.table = QtWidgets.QTableView()

        data = [
           rowtable(123,'Miconia', 'DC.', 14),
           rowtable(124,'Miconia calvescens', 'DC.', 21)
        #  # rowtable(1456,'Sapotaceae', 'L.', 10),
         ]
        self.model = TableModel(data)

        #self.model = TableModel()
        self.table.setModel(self.model)
        self.model.additem(rowtable(1456,'Sapotaceae', 'L.', 10, 2))

        self.setCentralWidget(self.table)

if __name__ == '__main__':
    app=QtWidgets.QApplication(sys.argv)

    window=MainWindow()
    window.show()
    app.exec_()