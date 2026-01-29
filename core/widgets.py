# Standard library
# import json
# import os
# import re
# import subprocess
import webbrowser

# Third-party
from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QFile

import os
import configparser

#from PyQt5 import QtWidgets, QtCore
from PyQt5.QtSql import QSqlDatabase



# Internal
#from core import functions, icons_rc


def load_ui_from_resources(ui_name):
    """
    load an ui file from ressources Qt.
    """
    file = QFile(f":/ui/{ui_name}")
    if not file.exists():
        raise FileNotFoundError(f"UI resource not found: {ui_name}")
    file.open(QFile.ReadOnly)
    ui = uic.loadUi(file)
    file.close()
    return ui






##class LinkDelegate to create hyperlink of the QTreeView from Qtreeview_Json
class LinkDelegate(QtWidgets.QStyledItemDelegate):
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
                QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.PointingHandCursor))
            elif event.type() == event.MouseButtonRelease:
                webbrowser.open(text)
                return True
            elif event.type() == QEvent.Leave:
                QtWidgets.QApplication.restoreOverrideCursor()
        else:
            # Restore the default cursor
            QtWidgets.QApplication.restoreOverrideCursor()
        return super().editorEvent(event, model, option, index)

#Class Qtreeview_Json to fill a QTreeView with a json 
class PN_JsonQTreeView(QtWidgets.QTreeView):
    """
    A custom QTreeView widget that displays data from a JSON object.
    ex: json_data = {'identity': {'name': 'acacia', 'authors': 'Mill.', 'published': 'True', 'accepted': 'True'}, 'habit': {'epiphyte': '' ....and so on

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
        dict_db_properties(): A dictionary containing the original json_data receive in the setdata() methods.
        _validate(): Compares the original data with the current data in the tree view and emits a signal if they are different.
    """
    changed_signal  = pyqtSignal(bool)
    def __init__(self, checkable = False, list_inRows = False, header = None):
        super().__init__()
        self.tab_header = header
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        # if header is None:
        #     self.header().hide()
        self.dict_db_properties = {}
        self.id = None
        self.checkable = checkable
        link_delegate = LinkDelegate()
        self.setItemDelegate(link_delegate)
        self.list_inRows = list_inRows
        self.header().setDefaultAlignment(Qt.AlignCenter)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    # def clear (self):
    #     model = QtGui.QStandardItemModel()
    #     self.setModel(model)

    def refresh(self):
        self.setData(self.dict_db_properties)

    def setData(self, json_data = None):
    #set the json_data into the treeview model
        def _set_dict_properties (item_base, _dict_item):
        #internal function to set recursively add the data into the treeview model
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


    #main part of the function
    # set the treeview widget model values
        self.model().clear()
        if not json_data: 
            return
        try:
            #disconnect the changed event to avoid multiple validation processes
            self.model().dataChanged.disconnect(self._validate)
        except Exception:
            pass
        #add nodes to treeview from dict_db_properties
        _set_dict_properties (self.model(), json_data)
        self.dict_db_properties = json_data
    #ajust header
        header = self.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        if self.tab_header:
            self.header().show()
            self.model().setHorizontalHeaderLabels(self.tab_header)
            for col in range(1, self.model().columnCount()):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        else:
            self.header().hide()
    ##validate and expand the treeview
        self._validate()
        self.expandAll()
    ##connect the changed event to validate the data
        self.model().dataChanged.connect(self._validate)

    def dict_user_properties(self, item_base = None):
    #get the json_data from the treeview model (with changed values)
        tab_value = {}
        if item_base is None:
            item_base = self.model()
        if item_base is None:
            return tab_value
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



class PN_DatabaseStatusWidget(QtWidgets.QWidget):
    clicked = pyqtSignal()
    def __init__(self, dbname = None):
        super().__init__()
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("background-color: transparent;")
        self.statusIndicator = QtWidgets.QWidget(frame)
        self.statusConnection = QtWidgets.QLabel(None, frame)
        self.statusIndicator.setFixedSize(10, 10)
        self.statusConnection.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        frame_layout = QtWidgets.QHBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        frame_layout.addWidget(self.statusIndicator)
        frame_layout.addWidget(self.statusConnection)
        self.load_status(dbname)
        self.setLayout(frame_layout)        
        self._installClickFilter(self)

    def _installClickFilter(self, widget):
        widget.installEventFilter(self)
        for child in widget.findChildren(QtWidgets.QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.clicked.emit()
                return True   # on consomme l'événement

        return super().eventFilter(obj, event)

    def load_status (self, dbname = None):
        if dbname:
            self.statusIndicator.setStyleSheet("background-color: rgb(0, 255, 0); border-radius: 5px;")
            self.statusConnection.setText("Connected : "+ dbname)
        else:
            self.statusIndicator.setStyleSheet("background-color: rgb(255, 0, 0); border-radius: 5px;")
            self.statusConnection.setText("Not Connected")
    
class MessageBox(QtWidgets.QMessageBox):
    def __init__(self, parent = None):
        super().__init__(parent)

    def custom_msgbox(self, title, text,
                      icon=QtWidgets.QMessageBox.Icon.Information,
                      buttons=QtWidgets.QMessageBox.StandardButton.Ok):
        
        msg = QtWidgets.QMessageBox(self.parent())
        msg.setWindowTitle(title)
        msg.setText(text)

        msg.setWindowFlags(
        Qt.WindowType.Dialog |
        Qt.WindowType.CustomizeWindowHint |
        Qt.WindowType.WindowCloseButtonHint
        )


        # Icône centrale
        main_icons = {
            QtWidgets.QMessageBox.Icon.Information: QtGui.QIcon(":/icons/info.png"),
            QtWidgets.QMessageBox.Icon.Warning: QtGui.QIcon(":/icons/warning.png"),
            QtWidgets.QMessageBox.Icon.Critical: QtGui.QIcon(":/icons/critical.png"),
            QtWidgets.QMessageBox.Icon.Question: QtGui.QIcon(":/icons/question.png"),
        }

        if icon in main_icons:
            msg.setIconPixmap(main_icons[icon].pixmap(36, 36))
        else:
            msg.setIcon(icon)

        # Boutons
        msg.setStandardButtons(buttons)

        # Icônes des boutons
        button_icons = {
            QtWidgets.QMessageBox.StandardButton.Ok: QtGui.QIcon(":/icons/ok.png"),
            QtWidgets.QMessageBox.StandardButton.Cancel: QtGui.QIcon(":/icons/cancel.png"),
            QtWidgets.QMessageBox.StandardButton.Yes: QtGui.QIcon(":/icons/ok.png"),
            QtWidgets.QMessageBox.StandardButton.No: QtGui.QIcon(":/icons/nok.png"),
        }

        for std_button, icon_btn in button_icons.items():
            btn = msg.button(std_button)
            if btn is not None:
                btn.setIcon(icon_btn)

        return msg.exec()

    def critical_msgbox (self, title, msg):
        self.custom_msgbox(
                title,
                msg,
                icon=QtWidgets.QMessageBox.Icon.Critical,
                buttons=QtWidgets.QMessageBox.StandardButton.Ok
            )
        
    def question_msgbox (self, title, msg, warning = False):
        _icon=QtWidgets.QMessageBox.Icon.Question
        if warning:
            _icon=QtWidgets.QMessageBox.Icon.Warning
        return  self.custom_msgbox(
                    title,
                    msg,
                    icon = _icon,
                    buttons=QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                ) == QtWidgets.QMessageBox.StandardButton.Yes
        





class PostgresConfigDialog(QtWidgets.QDialog):
    def __init__(self, config_path="config.ini", parent=None):
        super().__init__(parent)

        self.setWindowTitle("PostgreSQL configuration")
        self.setModal(True)
        self.config_path = config_path
        self.validated = False

        # --- UI ---
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()

        self.ed_host = QtWidgets.QLineEdit()
        self.ed_user = QtWidgets.QLineEdit()
        self.ed_password = QtWidgets.QLineEdit()
        self.ed_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.ed_database = QtWidgets.QLineEdit()

        form.addWidget(QtWidgets.QLabel("Host"), 0, 0)
        form.addWidget(self.ed_host, 0, 1)

        form.addWidget(QtWidgets.QLabel("User"), 1, 0)
        form.addWidget(self.ed_user, 1, 1)

        form.addWidget(QtWidgets.QLabel("Password"), 2, 0)
        form.addWidget(self.ed_password, 2, 1)

        form.addWidget(QtWidgets.QLabel("Database"), 3, 0)
        form.addWidget(self.ed_database, 3, 1)

        layout.addLayout(form)

        # --- Buttons ---
        btn_layout = QtWidgets.QHBoxLayout()

        self.btn_test = QtWidgets.QPushButton("Test")
        self.btn_ok = QtWidgets.QPushButton("OK")
        self.btn_cancel = QtWidgets.QPushButton("Close")
        self.btn_ok.setIcon(QtGui.QIcon(":/icons/ok.png"))
        self.btn_cancel.setIcon(QtGui.QIcon(":/icons/nok.png"))
        self.btn_test.setIcon(QtGui.QIcon(":/icons/test.png"))

        self.btn_ok.setEnabled(False)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_test)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        # --- Signals ---
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_ok.clicked.connect(self.accept_and_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.adjustSize()
        self.setFixedSize(400, self.height())
        # preload if exists
        self.load_existing_config()

    # --------------------------------------------------

    def load_existing_config(self):
        """Load existing values if file exists and section present."""
        if not os.path.exists(self.config_path):
            return

        config = configparser.ConfigParser()
        config.read(self.config_path)

        if "postgresql" not in config:
            return

        pg = config["postgresql"]

        self.ed_host.setText(pg.get("host", ""))
        self.ed_user.setText(pg.get("user", ""))
        self.ed_password.setText(pg.get("password", ""))
        self.ed_database.setText(pg.get("database", ""))

    # --------------------------------------------------

    def test_connection(self):
        host = self.ed_host.text().strip()
        user = self.ed_user.text().strip()
        password = self.ed_password.text()
        database = self.ed_database.text().strip()

        if not all([host, user, database]):
            QtWidgets.QMessageBox.warning(
                self,
                "Missing fields",
                "Host, user and database are required."
            )
            return

        # create temporary connection
        conn_name = "test_connection"

        db = QSqlDatabase.database(conn_name, open=False)
        if db.isValid():
            db.close()
            del db
            QSqlDatabase.removeDatabase(conn_name)

        db = QSqlDatabase.addDatabase("QPSQL", conn_name)
        db.setHostName(host)
        db.setUserName(user)
        db.setPassword(password)
        db.setDatabaseName(database)

        if not db.open():
            QtWidgets.QMessageBox.critical(
                self,
                "Connection failed",
                db.lastError().text()
            )
            self.btn_ok.setEnabled(False)
            return

        db.close()
        # if QSqlDatabase.contains(conn_name):
        #     QSqlDatabase.removeDatabase(conn_name)

        QtWidgets.QMessageBox.information(
            self,
            "Connection OK",
            "Connection successful."
        )

        self.validated = True
        self.btn_ok.setEnabled(True)

    # --------------------------------------------------

    def accept_and_save(self):
        if not self.validated:
            QtWidgets.QMessageBox.warning(
                self,
                "Not validated",
                "Please test the connection before saving."
            )
            return

        config = configparser.ConfigParser()
        config["postgresql"] = {
            "host": self.ed_host.text().strip(),
            "user": self.ed_user.text().strip(),
            "password": self.ed_password.text(),
            "database": self.ed_database.text().strip()
        }

        try:
            with open(self.config_path, "w") as f:
                config.write(f)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Write error",
                f"Cannot write config file:\n{e}"
            )
            return

        self.accept()

    # --------------------------------------------------

    @staticmethod
    def ensure_config(config_path="config.ini", parent=None):
        """
        Returns True if a valid config exists or was created successfully.
        Returns False if user cancelled.
        """
        config = configparser.ConfigParser()

        if os.path.exists(config_path):
            config.read(config_path)

            if "postgresql" in config:
                pg = config["postgresql"]
                keys = {"host", "user", "password", "database"}

                if keys.issubset(pg.keys()):
                    return True
        return False
        # # config missing or invalid → open dialog
        # dlg = PostgresConfigDialog(config_path, parent)
        # result = dlg.exec_()

        # return result == QtWidgets.QDialog.Accepted









