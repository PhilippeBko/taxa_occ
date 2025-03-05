
###########################################
#imports
import re
import webbrowser

from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QStyledItemDelegate,  QComboBox, QLineEdit, QWidget
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor
from commons import dict_properties
###########################################

##class LinkDelegate to create hyperlink of the QTreeView from Qtreeview_Json
class LinkDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()
        
        # Vérifie si la cellule contient un lien web
        if text and text.startswith("http"):
            # Rend le texte en bleu clair pour indiquer un lien cliquable
            painter.save()
            painter.setPen(QColor(100, 149, 237))  # Bleu clair (Cornflower Blue)
            painter.drawText(option.rect, Qt.AlignLeft, text)
            painter.restore()
        else:
            # Affiche le texte normalement
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        text = index.data()
        
        # Changer le curseur pour une main sur les liens web
        if text and text.startswith("http"):
            if event.type() == event.MouseMove:
                QApplication.setOverrideCursor(QCursor(Qt.PointingHandCursor))
            elif event.type() == event.MouseButtonRelease:
                webbrowser.open(text)
                return True
        else:
            # Restaurer le curseur par défaut si ce n'est pas un lien
            QApplication.restoreOverrideCursor()
        return super().editorEvent(event, model, option, index)


#Class Qtreeview_Json to fill a QTreeView with a json 
class Qtreeview_Json(QWidget):
    """ 
    Fill the Qtreeview with a json_data (a dictionnary of sub-dictionnaries)
    json_data = {'identity': {'name': 'acacia', 'authors': 'Mill.', 'published': 'True'}, 'habit': {'epiphyte': '' ....and so on
    data from sub-dictionnaries could be updated if the key is found in dict_properties (cf. commons.py)
    """
    changed_signal  = pyqtSignal(bool)
    def __init__(self, QTreeView, checkable = False, list_inRows = False):
        super().__init__(QTreeView)
        self.dict_db_properties = {}
        self.trview_identity = QTreeView
        self.id = None
        self.columncount = 2
        self.checkable = checkable
        link_delegate = LinkDelegate()
        self.trview_identity.setItemDelegate(link_delegate)
        self.list_inRows = list_inRows
       
        
    def refresh(self):
        self.setData(self.dict_db_properties)

    def setData(self, json_data):
    #get the data from database to set the treeview widget model values
        if json_data is None : 
            return
        model = QtGui.QStandardItemModel()
        self.trview_identity.setModel(model)
        self.dict_db_properties = json_data
        try:
            #disconnect the changed event to avoid multiple validation processes
            self.trview_identity.model().dataChanged.disconnect(self._validate)
        except Exception:
            pass
        self._set_dict_properties (self.trview_identity.model(), self.dict_db_properties)
        ##validate (and emit signal changed = false in theory !)
        self._validate()
        self.trview_identity.expandAll()
        ## connects at the end of setting data to avoid multiple events !
        self.trview_identity.clicked.connect(self._click)
        for col in range(self.trview_identity.model().columnCount()):
            self.trview_identity.resizeColumnToContents(col)
        self.trview_identity.resizeColumnToContents(0)
        # self.trview_identity.resizeColumnToContents(1)
        # self.trview_identity.resizeColumnToContents(0)
        # self.trview_identity.resizeColumnToContents()
        # current_width = self.trview_identity.columnWidth(0)
        # if model.columnCount() > 2:
        #     max_width = 300
        #     if current_width > max_width:
        #         self.trview_identity.setColumnWidth(0, max_width)

        #self.trview_identity.header().setStretchLastSection(True)
        selection = self.trview_identity.selectionModel()
        selection.currentChanged.connect(self._before_clickitem)
        self.trview_identity.model().dataChanged.connect(self._validate)

    def dict_user_properties(self, item_base = None):
        #get the data from the treeview model
        if item_base is None:
            item_base = self.trview_identity.model()
        tab_value = {}
        for i in range(item_base.rowCount()):
            item = item_base.item(i) ##.data(0)
            if item is None: 
                continue
            key = item.data(0).lower()
            tab_tmp = {}
            for a in range (item.rowCount()):
                _key = item.child(a).data(0).lower()
                _value = item.child(a).index().siblingAtColumn(1).data(0)
                tab_tmp[_key] = _value
            if len(tab_tmp) > 0:
                tab_value[key] = tab_tmp
        #check for autonyms, transform published in False
        # try:
        #     if str(tab_value["identity"]["published"]) == '[Autonym]':
        #         tab_value["identity"]["published"] = 'False'
        # except:
        #     pass
        return (tab_value)

    def _set_dict_properties (self, item_base, _dict_item):
        #set the data into the treeview model
        if _dict_item is None : 
            return
        font = QtGui.QFont()
        font.setBold(True)
        for _key, _value in _dict_item.items():
            #_key = _key.title()
            _key = _key[0].upper() + _key[1:]
            item_key = QtGui.QStandardItem(str(_key))
            item_value = QtGui.QStandardItem(None)
            if type(_value) is dict:
                item_base.appendRow([item_key, item_value],)

                #item_key.setData(font, Qt.FontRole)
                self._set_dict_properties(item_key, _value)
            elif type(_value) is list:
                item_key.setCheckable(self.checkable)
                if self.list_inRows:
                    self.columncount = max(self.columncount, len(_value)+1)
                    ls_items = [item_key]
                    for val in _value:
                        ls_items.append(QtGui.QStandardItem(str(val)))
                    item_base.appendRow(ls_items)
                else:
                    dict_key = {}
                    i = 1
                    for val in _value:
                        item_value = QtGui.QStandardItem(str(val))
                        if _key in dict_key:
                            itemkey = dict_key[_key]
                        else:
                            itemkey = QtGui.QStandardItem(str(_key))
                            item_base.appendRow([itemkey, None],)
                            dict_key[_key] = itemkey
                        itemkey.appendRow([item_value])
                        i += 1
            # elif type(_value) is set:
            #     item_key.setCheckable(self.checkable)
            #     self.columncount = max(self.columncount, len(_value)+1)
            #     ls_items = [item_key]
            #     for val in _value:
            #         ls_items.append(QtGui.QStandardItem(str(val)))
            #     item_base.appendRow(ls_items)
            else:
                item_value = QtGui.QStandardItem(str(_value))
                item_base.appendRow([item_key, item_value],)



    def _validate(self):
        #test and emit a signal of the equality between the db and user tab properties
        _validate = (self.dict_db_properties != self.dict_user_properties())
        self.changed_signal.emit(_validate)
        

    def _label_change(self, _value):
        #set the new text to the column
        if self.trview_identity.currentIndex().column() !=1: 
            return
        item = self.trview_identity.model().itemFromIndex(self.trview_identity.currentIndex())
        item.setText(_value)

    def _combo_click(self, index):
        #set the new Combo text to the column
        if self.trview_identity.currentIndex().column() !=1: 
            return
        try:
            field_table = self.trview_identity.currentIndex().parent().data(0).lower()
            field_name = self.trview_identity.currentIndex().siblingAtColumn(0).data().lower()
            ##field_value = self.trview_identity.currentIndex().siblingAtColumn(1).data()
        except Exception:
            return    

        item = self.trview_identity.model().itemFromIndex(self.trview_identity.currentIndex())
        try:
            _value = dict_properties[field_table][field_name][index]
        except Exception:
            _value =''
        item.setText(_value)


    def _before_clickitem(self, current_index, previous_index):
        #delete the associated add control (lineedit or combobox)
        try:
            column2_index = self.trview_identity.model().itemFromIndex(previous_index).index()
            #column2_index = self.trview_identity.model().index(previous_index.row(), 1)
            self.trview_identity.setIndexWidget(column2_index, None)
        except Exception:
            pass


    def _click(self):

        #activated a edit control (lineedit or combox) to allow aditing of a cell
        if self.trview_identity.currentIndex().column() !=1: 
            return
        try:
            field_table = self.trview_identity.currentIndex().parent().data(0).lower()
            field_name = self.trview_identity.currentIndex().siblingAtColumn(0).data().lower()
            field_value = self.trview_identity.currentIndex().siblingAtColumn(1).data()
        except Exception:
            return
            
        column2_index = self.trview_identity.model().itemFromIndex(self.trview_identity.currentIndex()).index()
        try:
            _properties = dict_properties[field_table][field_name]
        except Exception:
            _properties = None
        if _properties is None : 
            return
        #no modification when a value is in brackets
        #if field_value == '[Autonym]': return
        if re.search(r'\[.*\]',field_value): 
            return

        try: 
            if isinstance(_properties, str)  :
                line_edit = QLineEdit()
                font = QtGui.QFont()
                font.setPointSize(10)
                line_edit.setFont(font)
                line_edit.setFrame(False)
                style_sheet ='' #"QLineEdit QAbstractItemView {background-color: rgb(46, 52, 54)} "
                style_sheet +="QLineEdit {selection-background-color:black; selection-color:yellow; color: rgb(239, 239, 239);background-color: rgb(46, 52, 54); border-radius: 3px}"
                # style_sheet +="QLineEdit::drop-down:button{background-color: rgb(46, 52, 54)} "
                line_edit.setStyleSheet(style_sheet)
                line_edit.setText(field_value)
                #line_edit.selectAll()
                self.trview_identity.setIndexWidget(column2_index, line_edit)
                line_edit.textChanged.connect(self._label_change)
                #line_edit.focusOutEvent.connect(self._validate)
            elif isinstance(_properties, list):
                #try:
                combo_shortcut = QComboBox()
                font = QtGui.QFont()
                font.setPointSize(10)
                combo_shortcut.setFont(font)
                combo_shortcut.setFrame(False)
                #combo_shortcut.setStyleSheet("QComboBox { color: white;background-color: rgb(46, 52, 54);gridline-color:yellow; border-radius: 5px;}") 
                style_sheet ="QComboBox QAbstractItemView {background-color: rgb(46, 52, 54)} "
                #4891b4
                style_sheet +="QComboBox {selection-background-color:black; selection-color:yellow; color: rgb(239, 239, 239);background-color: rgb(46, 52, 54); border-radius: 3px}"
                style_sheet +="QComboBox::drop-down:button{background-color: rgb(46, 52, 54);border-color: #4891b4} "
                combo_shortcut.setStyleSheet(style_sheet)
                #combo_shortcut.setStyleSheet("QComboBox { color: white;background-color: rgb(46, 52, 54)}") 
                combo_shortcut.addItems(_properties)
                combo_shortcut.addItem('Unknown')
                if field_value in ['', 'NULL']:
                    field_value = 'Unknown'
                combo_shortcut.setCurrentText(field_value.title())
                combo_shortcut.currentIndexChanged.connect(self._combo_click)
                self.trview_identity.setIndexWidget(column2_index, combo_shortcut)
        except Exception:
            return
   
