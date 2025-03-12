###########################################
#imports
import webbrowser
from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QStyledItemDelegate, QTreeView, QHeaderView, QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal
###########################################

##class LinkDelegate to create hyperlink of the QTreeView from Qtreeview_Json
class LinkDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()
        # check for an internet hyperlink
        if text and text.startswith("http"):
            # draw text in blue when its an hyperlink
            painter.save()
            painter.setPen(QtGui.QColor(100, 149, 237))  # (Cornflower Blue)
            painter.drawText(option.rect, Qt.AlignLeft, text)
            painter.restore()
        else:
            # draw text normally
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        text = index.data()
        # change the cursor if cell is an internet hyperlink and open the link if clicked
        if text and text.startswith("http"):
            if event.type() == event.MouseMove:
                QApplication.setOverrideCursor(QtGui.QCursor(Qt.PointingHandCursor))
            elif event.type() == event.MouseButtonRelease:
                webbrowser.open(text)
                return True
        else:
            # Restore the default cursor
            QApplication.restoreOverrideCursor()
        return super().editorEvent(event, model, option, index)

#Class Qtreeview_Json to fill a QTreeView with a json 
class Qtreeview_Json(QTreeView):
    """
    A custom QTreeView widget that displays data from a JSON object.
    ex: json_data = {'identity': {'name': 'acacia', 'authors': 'Mill.', 'published': 'True'}, 'habit': {'epiphyte': '' ....and so on

    Args:
        checkable (bool, optional): Whether the first column is checkable. Defaults to False.
        list_inRows (bool, optional): Whether lists are displayed in rows. Defaults to False.
        header (list, optional): A list of column headers to display. Defaults to None.

    Attributes:
        changed_signal (pyqtSignal): A signal emitted when the data in the tree view is changed.

    Methods:
        refresh(): Refreshes the tree view with the current data.
        setData(json_data): Sets the data in the tree view from a JSON object.
        dict_user_properties(): Retrieves the data from the tree view and returns it as a dictionary.
        _validate(): Compares the original data with the current data in the tree view and emits a signal if they are different.
    """
    changed_signal  = pyqtSignal(bool)
    def __init__(self, checkable = False, list_inRows = False, header = None):
        super().__init__()
        self.tab_header = header
        if header is None:
            self.header().hide()
        self.dict_db_properties = {}
        self.id = None
        self.checkable = checkable
        link_delegate = LinkDelegate()
        self.setItemDelegate(link_delegate)
        self.list_inRows = list_inRows
        self.header().setDefaultAlignment(Qt.AlignCenter)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
               
    def refresh(self):
        self.setData(self.dict_db_properties)

    def setData(self, json_data):
    #set the json_data into the treeview model
        def _set_dict_properties (item_base, _dict_item):
        #internal function to set recursively the data into the treeview model
            if _dict_item is None : 
                return
            for _key, _value in _dict_item.items():
                _key = _key[0].upper() + _key[1:]
                item_key = QtGui.QStandardItem(str(_key))
                item_value = QtGui.QStandardItem(None)
                if type(_value) is dict:
                    item_base.appendRow([item_key, item_value],)
                    _set_dict_properties(item_key, _value)
                elif type(_value) is list:
                    item_key.setCheckable(self.checkable)
                    if self.list_inRows:
                        ls_items = [item_key]
                        for val in _value:
                            item = QtGui.QStandardItem(str(val))
                            item.setTextAlignment(Qt.AlignCenter)
                            ls_items.append(item)
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
                else:
                    item_value = QtGui.QStandardItem(str(_value))
                    item_base.appendRow([item_key, item_value],)


    #get the data from database to set the treeview widget model values
        if json_data is None : 
            return
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        self.dict_db_properties = json_data
        try:
            #disconnect the changed event to avoid multiple validation processes
            self.model().dataChanged.disconnect(self._validate)
        except Exception:
            pass
        _set_dict_properties (self.model(), self.dict_db_properties)
        ##validate (and emit signal changed = false in theory !)
        self._validate()
        self.expandAll()

        #ajust header
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        if self.tab_header:
            model.setHorizontalHeaderLabels(self.tab_header)
            for col in range(1, self.model().columnCount()):
                header.setSectionResizeMode(col, QHeaderView.Stretch)
        self.model().dataChanged.connect(self._validate)

    def dict_user_properties(self, item_base = None):
    #get the json_data from the treeview model
        if item_base is None:
            item_base = self.model()
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
        return (tab_value)

    def changed (self):
    #test the equality between the db and user tab properties
        return (self.dict_db_properties != self.dict_user_properties())

    def _validate(self, index = None):
    #test if changed, underline column 0 for changed value and emit a signal
        if index is not None:
            font = QtGui.QFont()
            _bold = False
            try:
                field_table = index.parent().data(0).lower()
                field_name = index.siblingAtColumn(0).data().lower()
                field_value = index.siblingAtColumn(1).data()
                _bold = (field_value != self.dict_db_properties[field_table][field_name])
            except Exception:
                pass
            font.setUnderline(_bold)
            self.model().setData(index.siblingAtColumn(0), font, Qt.FontRole)
        self.changed_signal.emit(self.changed())