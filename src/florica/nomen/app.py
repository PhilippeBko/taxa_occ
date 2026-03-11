# ruff: noqa: E402

#add icon.names in _icons.qrc then
#pyrcc5 _ressources.qrc -o src/florica/core/ressources.py


import os
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"

import sys

# Standard library
import json
import re
import time
# Third-party
from PyQt5 import QtCore, QtGui, QtWidgets
#print("Répertoire de travail actuel :", os.getcwd())
from florica.core import ressources  # noqa: F401
#import taxa_occ.core.ressources

# Internal modules
from florica.core import functions

from florica.models.taxa_model import (
    PNTaxa_searchAPI, PNTaxa_TreeModel, PNTaxa, PNTaxa_with_Score, 
    PNTaxa_QTreeView, PNTaxa_add, PNTaxa_edit, PNTaxa_merge,
    PNSynonym, PNSynonym_edit
)
from florica.core.widgets import PN_JsonQTreeView, LinkDelegate, PostgresConfigDialog, load_ui_from_resources, PN_DatabaseStatusWidget, MessageBox, ConfigManager
from florica.core.database import DatabaseConnection, PN_dbTaxa

#generic function to access to the dbases classes
#access to the postgresql connexion
def db_postgres():
    return functions.db()
#access to a postgres connexion with specific procedures for taxa management
def db_taxa():
    return functions.dbtaxa()

#Class EditProperties_Delegate is used by the MainWindow class to edit the properties of the PN_JsonQTreeView
class EditProperties_Delegate(QtWidgets.QStyledItemDelegate):
    """
    A custom delegate class for editing properties in a PN_JsonQTreeView.

    This class is responsible for creating editors for specific columns in the tree view,
    based on the type of data in the dict_properties dictionary (for the moment qlinedit and combobox)

    Attributes:
        None

    Methods:
        createEditor: Creates an editor (QLineEdit or QComboBox) for a specific column.
        setEditorData: Sets the data for the editor.
        setModelData: Saves the data from the editor into the model.
    """
    def __init__(self, dict_properties, parent=None):
        super().__init__(parent)
        self.db_properties = dict_properties

    def createEditor(self, parent, option, index):
        """ Create the editor (QlineEdit or ComboBox) according to type in the dict_properties         
        """
        if index.column() == 1:
            #get the columns name and value
            try:
                field_table = index.parent().data(0).lower()
                field_name = index.siblingAtColumn(0).data().lower()
                field_value = index.siblingAtColumn(1).data()
                field_def = self.db_properties[field_table][field_name]
            except Exception:
                field_def = None
                return
            if field_def is None : 
                return
            #do not edit value with brackets (convention)
            if re.search(r'\[.*\]',field_value): 
                return
            _type = field_def.get("type", 'text')
            _lsitems = field_def.get("items", None)
            if _type == 'text' and _lsitems is None :
                editor = QtWidgets.QLineEdit(parent)
            else:
                editor = QtWidgets.QComboBox(parent)
                if _lsitems:
                    editor.addItems(_lsitems)
                elif _type == 'boolean':
                    editor.addItems(['True', 'False'])
                editor.addItems(['Unknown'])
            return editor        
        return

    def setEditorData(self, editor, index):
        """ fill the editor with the model value"""
        if index.column() == 1:
            data = index.model().data(index, QtCore.Qt.DisplayRole)
            if isinstance(editor, QtWidgets.QLineEdit):
                editor.setText(str(data))
            elif isinstance(editor, QtWidgets.QComboBox):
                if not data:
                    data = 'Unknown'
                editor.setCurrentText(str(data))

    def setModelData(self, editor, model, index):
        """ Save the value into the model """

        if index.column() == 1:
            if isinstance(editor, QtWidgets.QLineEdit):
                _value = editor.text()
            elif isinstance(editor, QtWidgets.QComboBox):
                _value = editor.currentText()
                if _value == 'Unknown':
                    _value = ''
            # if model.data(index) != _value:
            #     model.setData(index.siblingAtColumn(0), font, QtCore.Qt.FontRole)
            model.setData(index, _value)

#class MetadataDelegateWithAuthorCheck is used to highlight the authors name in red if it does not match the current authors name
#surcharging the LinkDelegate used to highlight the hyperlinks in the metadata treeview
class MetadataDelegateWithAuthorCheck(LinkDelegate):
    menu_action_triggered = QtCore.pyqtSignal(str, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._authors_name = None
        self._button_rects = {}
        self.menuclipboard = QtWidgets.QMenu(parent)
        font = QtGui.QFont()
        font.setPointSize(10)
        self.menuclipboard.setFont(font)
        #actions list
        actions = ["Copy Value", "Copy Key-Value"]
        for i, text in enumerate(actions):
            act = self.menuclipboard.addAction(text)
            act.setData(i)  # stocke l'index de l'action
            act.triggered.connect(lambda checked=False, a=act.text(): self._triggerClipboard(a))
        self._current_index = 0
        # resize menu
        fm = QtGui.QFontMetrics(font)
        max_width = fm.horizontalAdvance("Copy Key-Value") + 60  # marge
        self.menuclipboard.setFixedWidth(max_width)

    def set_authors_name(self, name):
        self._authors_name = name

    def paint(self, painter, option, index):
        # Apply the superclass's paint method (web links)
        super().paint(painter, option, index)

        # Additional logic for column 1 and key
        if index.column() == 1:
            key = index.sibling(index.row(), 0).data(QtCore.Qt.DisplayRole)
            value = index.data(QtCore.Qt.DisplayRole)
            if key == "Authors" and value != self._authors_name:
                # paint foreground in red if authors are different
                option.palette.setColor(option.palette.Text, QtGui.QColor("red"))
                super().paint(painter, option, index)  # repaint in red
            elif value == 'No results':
                # paint foreground in red if authors are different
                option.palette.setColor(option.palette.Text, QtGui.QColor("red"))
                super().paint(painter, option, index)  # repaint in red

            if (
                    (option.state & QtWidgets.QStyle.State_Selected)
                    and index.parent().isValid()
                ):
                    self.drawButton(painter, option, index)

    def drawButton(self, painter, option, index):
    # create a button for edition
        r = option.rect
        rect = QtCore.QRect(r.right() - 22, r.top(), 20, r.height())
        self._button_rects[index] = rect

        # create a button for edition
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)        
        opt.text = "⋮"
        opt.rect = rect
        opt.displayAlignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter

        # no icon, no decoration, only two points
        opt.features &= ~QtWidgets.QStyleOptionViewItem.HasDecoration
        option.widget.style().drawControl(
            QtWidgets.QStyle.CE_ItemViewItem,
            opt,
            painter,
            option.widget
        )

    def editorEvent(self, event, model, option, index):
    #manage the mouse clic to produce an event
        if event.type() == QtCore.QEvent.MouseButtonPress:
            rect = self._button_rects.get(index)
            if rect and rect.contains(event.pos()):
                self._current_index = index
                self.menuclipboard.exec_(QtGui.QCursor.pos())
                return True
        return super().editorEvent(event, model, option, index)

    def _triggerClipboard(self, action_text):
    #copy option into the clipboard
        index = self._current_index
        if index is None:
            return
        clipboard = QtWidgets.QApplication.clipboard()
        key = index.sibling(index.row(), 0).data(QtCore.Qt.DisplayRole)
        value = index.sibling(index.row(), 1).data(QtCore.Qt.DisplayRole)
        if action_text == "Copy Value":
            clipboard.setText(str(value))
        elif action_text == "Copy Key-Value":
            clipboard.setText(f"{key} - {value}")

#class TaxonomyProxyModel is used for filtering the Taxonomy TreeView according to the checkboxes
class TaxonomyProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # --- Filter parameters
        self.show_checked_mode = 1  # 1: All, 2: True, 3: False
        self.show_published_mode = 1
        self.show_accepted_mode = 1
        self.children_only = False

    def match_filter(self, mode, value):
    # Method for match logic
        if mode == 1:
            return True
        if mode == 2:
            return bool(value)
        return not bool(value)
    
    def childCount(self):
    # the number of visible child nodes in the proxy model (populated root nodes)
        total_child_count = 0
        for row in range(self.rowCount()):
            root_index = self.index(row, 0, QtCore.QModelIndex())
            if root_index.isValid():
                total_child_count += self.rowCount(root_index)
        return total_child_count
    
    def nodeMatchesFilters(self, node):
    #return true/false according to the filters
        return all([
            self.match_filter(self.show_checked_mode, getattr(node, 'taxaname_score', None)),
            self.match_filter(self.show_published_mode, getattr(node, 'published', False)),
            self.match_filter(self.show_accepted_mode, getattr(node, 'accepted', False)),
        ])

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
    # filter node visibility, return True/False according to filters
        index = self.sourceModel().index(source_row, 0, source_parent)
        if not index.isValid():
            return False        
        node = index.data(QtCore.Qt.UserRole)
        if index.parent().isValid():
            return self.nodeMatchesFilters (node)
        # if not children_only root node is visible
        if not self.children_only:
            return True        
        return self.hasAcceptedChildren(index)

    def hasAcceptedChildren(self, parent_index):
    #return True if a child node of parent_index is visible according to filters
        model = self.sourceModel()
        for row in range(model.rowCount(parent_index)):
            child_index = model.index(row, 0, parent_index)
            if not child_index.isValid():
                continue
            node = child_index.data(QtCore.Qt.UserRole)
            if self.nodeMatchesFilters (node):
                return True
        return False


##The MainWindow load the ui interface to navigate and edit taxaname###
class MainWindow(QtWidgets.QMainWindow):
    """
    The main window of the application.
    This class represents the main window of the application and is responsible for managing the user interface.
    It inherits from `QtWidgets.QMainWindow` and provides methods to interact with the UI elements.
    """

    toolbox_click = QtCore.pyqtSignal(int)
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = load_ui_from_resources("taxanames.ui")

    # setting the widgets links to ui
        self.trview_taxonref = self.window.main_treeView
        self.button_metadata_refresh = self.window.button_metadata_refresh
        self.buttonbox_filter = self.window.buttonBox_filter
        self.buttonbox_filter_apply = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Apply)
        self.buttonbox_filter_reset = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Reset)

        self.button_properties = self.window.buttonBox_identity
        self.button_properties_apply = self.button_properties.button(QtWidgets.QDialogButtonBox.Apply)
        self.button_properties_cancel = self.button_properties.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_reference_add = self.window.button_reference_add
        self.button_reference_edit = self.window.button_reference_edit
        self.button_reference_remove = self.window.button_reference_remove
        self.button_reference_merge = self.window.button_reference_merge
        self.button_synonym_add = self.window.button_synonym_add
        self.button_synonym_edit = self.window.button_synonym_edit
        self.button_synonym_remove = self.window.button_synonym_remove
        self.button_rankgroup = self.window.button_rankGroup
        self.button_themes = self.window.button_themes
        self.button_showFilter = self.window.button_showFilter

        self.checkBox_published = self.window.checkBox_published
        self.checkBox_accepted = self.window.checkBox_accepted
        self.checkBox_children = self.window.checkBox_withtaxa
        self.checkBox_checked = self.window.checkBox_checked
        self.searchtaxon = self.window.lineEdit_searchtaxon
        self.toolBox = self.window.toolBox
        self.combo_taxa = self.window.combo_taxa

    #setting the filter checkboxes to partially checked
        self.checkBox_published.setCheckState(QtCore.Qt.PartiallyChecked)
        self.checkBox_accepted.setCheckState(QtCore.Qt.PartiallyChecked)
        self.checkBox_children.setCheckState(QtCore.Qt.PartiallyChecked)
        self.checkBox_checked.setCheckState(QtCore.Qt.PartiallyChecked)

    #set the buttons icons
        self.buttonbox_filter_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        self.buttonbox_filter_reset.setIcon (QtGui.QIcon(":/icons/refresh.png"))
        self.button_properties_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        self.button_properties_cancel.setIcon (QtGui.QIcon(":/icons/nok.png"))

    #set the toolbox icon style
        index = self.toolBox.currentIndex()
        self.on_toolbox_click(index)
    
    #add two labels to displayed msg in the statusbar
        self.selected_rank_label = QtWidgets.QLabel()
        self.selected_taxa_label = QtWidgets.QLabel()
        self.window.statusbar.addWidget(self.selected_rank_label)
        self.window.statusbar.addWidget(self.selected_taxa_label)
        self.window.statusBar().addPermanentWidget(self.button_themes)
        self.toolBox.currentChanged.connect(self.on_toolbox_click)

    def on_toolbox_click(self, index):
        #set the icons to the toolbox and emit a signal
        self.toolBox.setItemIcon(index, QtGui.QIcon(":/icons/arrow2.png"))
        for i in range(3):
            if i != index:
                self.toolBox.setItemIcon(i, QtGui.QIcon(":/icons/arrow1.png"))
        self.toolbox_click.emit(index)
    
    def set_ui_enabled(self, enabled: bool):
        #set the enabled state of the ui
        self.button_synonym_add.setEnabled(enabled)
        self.button_synonym_edit.setEnabled(enabled)
        self.button_synonym_remove.setEnabled(enabled)
        self.button_reference_merge.setEnabled(enabled)
        self.button_reference_edit.setEnabled(enabled)
        self.button_reference_remove.setEnabled(enabled)
        self.button_metadata_refresh.setEnabled(enabled)
        #major buttons
        self.button_showFilter.setEnabled(enabled)
        self.button_rankgroup.setEnabled(enabled)
        self.combo_taxa.setEnabled(enabled)
        self.checkBox_published.setEnabled(enabled)
        self.checkBox_accepted.setEnabled(enabled)
        self.checkBox_checked.setEnabled(enabled)
        self.checkBox_children.setEnabled(enabled)
        self.button_reference_add.setEnabled(enabled)

    def set_taxa_label(self, text: str):
        #set the label taxa
        self.selected_taxa_label.setText(text)
    
    def set_rank_label(self, text: str):
        #set the label rank
        self.selected_rank_label.setText(text)

    def set_filter_visible(self, visible: bool):
        #set the visibility of the filter Frame
        self.window.frame_filter.setVisible(visible)

    def set_theme_text(self, text: str):
       #set the text of the button themes
       self.window.button_themes.setText(text or "Default Style")
    
    def set_rankgroup_text(self, text: str):
       #set the text of the button rank_group
       self.button_rankgroup.setText(text)    

    @property
    ##get and set text from label_count
    def label_count (self):
        return self.window.label_count.text()
    @label_count.setter
    def label_count (self, text: str):
        self.window.label_count.setText(text)

    @property
    ##get and set text from label_query_time
    def label_time (self):
        return self.window.label_query_time.text()
    @label_time.setter
    def label_time (self, text: str):
        self.window.label_query_time.setText(text)

    @property
    ##get and set text from search_taxon
    def search_taxon(self):
        return self.searchtaxon.text()
    @search_taxon.setter    
    def search_taxon(self, text: str):
        self.searchtaxon.setText(text)

    @property
    ##get and set text from the button rank_group
    def rank_group(self):
        return self.button_rankgroup.text()
    @rank_group.setter
    def rank_group(self, text: str):
        self.button_rankgroup.setText(text) 

class MainWindowController:
    """
        The controller class of the MainWindow class
        Initializes the MainWindowController object given a view object.
        It sets the view, window, connected status, db properties, authors delegate,
        config manager, and loads widgets from and to the view.
        It sets the filtering and sorting on the proxy model for trview_taxonref,
        creates the metadata worker (Qthread) and sets the slots signals.
    """    
#the main controller of the application
    def __init__(self, view):
        self.view = view
        self.window = self.view.window
        self.connected = False
        self.db_properties = None
        self.view.set_filter_visible(False)
        self.authors_delegate = MetadataDelegateWithAuthorCheck()
        config_file = functions.resource_path("config.ini")
        self.config_manager = ConfigManager(config_file)

        #load widgets from the view
        self.trview_taxonref = view.trview_taxonref
        
        #load widgets to the view
        self.dbwidget_status = PN_DatabaseStatusWidget()
        self.window.statusBar().addPermanentWidget(self.dbwidget_status)

        self.trview_properties =  PN_JsonQTreeView ()
        layout = self.window.toolBox.widget(2).layout()
        layout.insertWidget(0,self.trview_properties) 

        self.trview_metadata = PN_JsonQTreeView ()
        layout = self.window.toolBox.widget(1).layout()
        layout.insertWidget(0,self.trview_metadata)

        self.trview_names = PN_JsonQTreeView ()
        layout = self.window.toolBox.widget(0).layout()
        layout.insertWidget(0,self.trview_names)

        self.trview_filter = PN_JsonQTreeView ()
        layout = self.window.frame_filter.layout()
        layout.insertWidget(1,self.trview_filter)

        self.trView_hierarchy = PNTaxa_QTreeView ()
        layout = self.window.trView_hierarchy_Layout
        layout.insertWidget(0,self.trView_hierarchy)
        
        self.combo_taxa = view.combo_taxa

         #set filtering and sorting on the proxymodel for trview_taxonref
        self.trview_taxonref.setSortingEnabled(True)
        self.trview_taxonref.header().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.proxy_model = TaxonomyProxyModel()
        self.proxy_model.setSourceModel(PNTaxa_TreeModel())
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.trview_taxonref.setModel(self.proxy_model)
        
        #create the metadata worker (Qthread)
        self.metadata_worker = PNTaxa_searchAPI(view)

        self.trview_metadata.setItemDelegate(self.authors_delegate)

    #setting the slots signals
        #signals from menus clicked (theme and rank group)
        self.view.toolbox_click.connect(self.toolbox_click)
        #signals from buttons
        self.view.button_showFilter.toggled.connect(self.on_filter_toggled)  
        self.view.button_synonym_add.clicked.connect(self.button_synonym_add_click)
        self.view.button_synonym_edit.clicked.connect(self.button_synonym_edit_click)
        self.view.button_synonym_remove.clicked.connect(self.button_synonym_remove_click)
        self.view.button_reference_add.clicked.connect(self.button_reference_add_click)   
        self.view.button_reference_edit.clicked.connect(self.button_reference_edit_click)
        self.view.button_reference_remove.clicked.connect(self.button_reference_remove_click)
        self.view.button_reference_merge.clicked.connect(self.button_reference_merge_click)
        self.view.button_metadata_refresh.clicked.connect (self.button_metadata_click)
        self.view.button_properties_apply.clicked.connect(self.button_identity_apply_click)
        self.view.button_properties_cancel.clicked.connect(self.button_identity_cancel_click)
        #signals from searchTaxon enter
        self.view.searchtaxon.returnPressed.connect(self.trview_taxonref_setData)
        #signals from checkboxes
        self.view.checkBox_published.stateChanged.connect(self.trview_taxonref_refreshData)
        self.view.checkBox_accepted.stateChanged.connect(self.trview_taxonref_refreshData)
        self.view.checkBox_children.stateChanged.connect(self.trview_taxonref_refreshData)
        self.view.checkBox_checked.stateChanged.connect(self.trview_taxonref_refreshData)
        #signals from trviews    
        self.trview_taxonref.selectionModel().selectionChanged.connect(self.trview_taxonref_click)
        self.trview_taxonref.doubleClicked.connect(self.trview_taxonref_dblclick)
        self.trView_hierarchy.selectionModel().selectionChanged.connect(self.trView_hierarchy_click)
        self.trView_hierarchy.doubleClicked.connect(self.trView_hierarchy_dblclick)
        self.trview_names.selectionModel().selectionChanged.connect(self.refresh_ui_trview_hierarchy)
        self.trview_properties.changed_signal.connect(self.trview_identity_changed)
        
        self.metadata_worker.Result_Signal.connect(self.trview_metadata_setDataAPI)
        #self.combo_taxa.currentIndexChanged.connect(self.trview_taxonref_setData)
        self.dbwidget_status.clicked.connect(self.on_status_clicked)

        self.view.buttonbox_filter_apply.clicked.connect(self.trview_taxonref_setData)
        self.view.buttonbox_filter_reset.clicked.connect(self.button_filter_reset_click)
   #load themes menu
        button_themes_menu = QtWidgets.QMenu()
        menu_items = ["Adaptic", "Combinear", "Diffnes", "Geoo", "Lightstyle", "Obit"]

        for item in menu_items:
            action = QtWidgets.QAction(item, self.view)
            action.triggered.connect(lambda checked, item=item: self.on_menu_theme_click(item))
            button_themes_menu.addAction(action)
        self.view.button_themes.setMenu(button_themes_menu)
    #load the grouped ranks menu
        menu_button_rankGroup = QtWidgets.QMenu()
        # create an exclusive action group for menu
        action_group = QtWidgets.QActionGroup(self.view)
        action_group.setExclusive(True)
        actions = []
        # set the list of the available ranks
        menu_items = ['Subregnum','Division', 'Classis', 'Subclassis', 'Order', 'Family', 'Genus']
        for item in menu_items:
            action = QtWidgets.QAction(item, self.view)
            action.setCheckable(True)
            action_group.addAction(action)
            actions.append(action)
            action.triggered.connect(lambda checked, item=item: self.on_rankGroup_selected(item))
            menu_button_rankGroup.addAction(action)
        #set the family as default selected item
        self.view.button_rankgroup.setMenu(menu_button_rankGroup)
        _selected_item = 5
        actions[_selected_item].setChecked(True)
        self.view.set_rankgroup_text(menu_items[_selected_item])

    def on_filter_toggled(self, state: bool):
        #hide/show filter Frame
        self.view.set_filter_visible(state)

    def on_rankGroup_selected(self, rank):
        #clic on a rankGroup Menu item
        self.view.set_rankgroup_text(rank)
        self.trview_taxonref_setData()

    def on_menu_theme_click(self, item):
        if item is None:
            item = "Diffnes"
    #to change the theme        
        try:
            qss_path = f":/ui/{item}.qss"
            file = QtCore.QFile(qss_path)
            if not file.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
                raise RuntimeError(file.errorString())
            stream = QtCore.QTextStream(file)
            stylesheet = stream.readAll()
            file.close()
            QtWidgets.qApp.setStyleSheet(stylesheet)
            # qss_file = functions.resource_path("ui", item + ".qss")
            # with open(qss_file, "r", encoding="utf-8") as f:
            #     QtWidgets.qApp.setStyleSheet(f.read())
            # save the theme in the config.ini via ConfigManager
            self.config_manager.theme = item
        except Exception as e:
            # if item:
            #     msg = f"Unable to load the style: {item}"
            #     MessageBox().critical_msgbox("Error", msg)
            item = None
        #set the theme to the theme button
        self.view.set_theme_text(item)        

    def on_status_clicked(self):
    #load the database dialogBox to change database parameters
        dlg = PostgresConfigDialog(self.config_manager, self.window)
        #dlg = PostgresConfigDialog("config.ini", self.window)
        result = dlg.exec_()
        if not result:
            return
        self.load_database()

    def load_database(self):
        #set the ui disabled
        self.view.set_ui_enabled(False)
    #disconnect signal and set the default value for combo_taxa        
        self.combo_taxa_signal_connected(False)
        self.combo_taxa.clear()
        self.combo_taxa.addItem('All names')
        self.combo_taxa.setItemData(0, PNTaxa(0, 'All names', '', 0), role=QtCore.Qt.UserRole) 
    #load the connection, load dialog box if not connected
        dbconn = DatabaseConnection()
        while True:
            pg = self.config_manager.postgresql
            if pg:
                self.connected = dbconn.open(pg)                
                if self.connected:
                    break
            #dlg = PostgresConfigDialog(config_file, self.window)
            dlg = PostgresConfigDialog(self.config_manager, self.window)
            result = dlg.exec_()
            if not result:
                break
        #set the widget with status (connected or Not)
        self.dbwidget_status.load_status(dbconn.dbname())

    #return if not connected (or loop ??)
        if not self.connected:
            return
    #load the specific taxa database functions
        taxa = PN_dbTaxa(dbconn)
    #initialize the registry database services
        functions._registry = None
        functions.init_registry(functions.ServiceRegistry(dbconn, taxa=taxa))
    #set the APG options into self.combo_taxa
        lst = db_taxa().db_get_apg4_clades()
        for clade in lst:
            self.combo_taxa.addItem(clade)
            self.combo_taxa.setItemData(self.combo_taxa.count() - 1, PNTaxa(0, clade), role=QtCore.Qt.UserRole)
        self.combo_taxa.setCurrentIndex(0)
        #set delegate for editing properties of PN_trview_identity & PN_trview_filter
        self.db_properties = taxa.db_dic_properties
        delegate = EditProperties_Delegate(self.db_properties)
        self.trview_properties.setItemDelegate(delegate)
        self.trview_filter.setItemDelegate(delegate)
        self.trview_properties.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
        self.trview_filter.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
        
        #set the delegate and slots signals
    #reconnect the signal to combo_taxa
        self.combo_taxa_signal_connected(True)
        #self.combo_taxa.currentIndexChanged.connect(self.trview_taxonref_setData)
    #set the ui enabled for the general widgets 
        self.refresh_ui_trview_taxonref(True)
    #initialize the trview_taxonref (list of taxa)
        self.trview_filter_load()
        self.trview_taxonref_setData()


    def combo_taxa_signal_connected (self, connected = True):
        try:
            self.combo_taxa.currentIndexChanged.disconnect()
        except Exception:
            pass
        if connected:
            self.combo_taxa.currentIndexChanged.connect(self.trview_taxonref_setData)

    def get_list_PNTaxa(self, _idtaxonref = None, refresh = False):
    #return a list of PNTaxal objets fill from the database according to a dict_filter
        # ex: dict_filter = {"id_taxonref" : idtaxonref, 
        #             "search_name": self.view.search_taxon, 
        #             "clade": clade_sql, 
        #             "properties": self.trview_filter.dict_user_properties()
        #             }
    
        #create the filter dictionnary for query the database
        clade_sql = None
        if self.combo_taxa.currentIndex() == -1:
            self.combo_taxa.setCurrentIndex(0)
        combo_taxa_index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(combo_taxa_index, role=QtCore.Qt.UserRole).idtaxonref
        ls_idtaxonref = []            
        if _idtaxonref:
            ls_idtaxonref = [_idtaxonref]

        if idtaxonref == 0:
            idtaxonref = None
            if combo_taxa_index > 0:
                clade_sql = self.combo_taxa.currentText()
        else: #
            ls_idtaxonref += [idtaxonref]

        dict_filter = {"id_taxonref" : ls_idtaxonref, 
                       "search_name": self.view.search_taxon, 
                       "clade": clade_sql, 
                       "properties": self.trview_filter.dict_user_properties()
                      }
        

        grouped_id_rank = self.get_idrankGroup()
        records = db_taxa().db_get_json_taxa(grouped_id_rank, dict_filter, refresh)
        data = []
        for rec in records:
            item = PNTaxa_with_Score(rec.get("id_taxonref"), rec.get("taxaname"), rec.get("authors"), 
                            rec.get("id_rank"), rec.get("published"), rec.get("accepted"))
            item.id_parent = rec.get("id_parent")
            #set the taxaname_score and api_total
            item.taxaname_score = rec.get("taxaname_score", None)
            item.authors_score = rec.get("authors_score", None)
            data.append(item)
        #set the filter button color
        nb_filter = dict_filter.get("nb_filter", None)
        self.view.button_showFilter.setStyleSheet(
                "color: rgb(0, 55, 217);" if nb_filter else ""
        )
        return data
    
            
    def get_idrankGroup(self):
    #return the id_rank of the selected group (according to button_rankGroup text)
        group_text = self.view.rank_group
        idrankparent = db_taxa().db_get_rank(group_text, 'id_rank')
        if not idrankparent:
            idrankparent = 14 
        return idrankparent
    
   
    def database_save_taxa(self, ls_dict_tosave):
        #internal function for saving one taxon in the database
        """ 
            common function for update (add_name and edit_name) when apply
            Save a taxon in the database from a list of dictionnaries:   
            if parentname is not present, it will update the taxon with id_parent = (searching the id_parent, in the dbase taxaname = parentname)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "parentname":text, "published":boolean, "accepted":boolean, "id_rank" :integer}
            if idparent is present, it will update the taxon with the id_parent (integer)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "id_parent":integer, "published":boolean, "accepted":boolean, "id_rank" :integer}
        """
        #####main part of the function
        if not isinstance(ls_dict_tosave, list):
            ls_dict_tosave = [ls_dict_tosave]
        ls_item_updated = []
        #save any dict from the list
        for dict_tosave in ls_dict_tosave:
            idtaxonref_torefresh  = db_taxa().db_save_dict_taxa(dict_tosave)
            _idrank = dict_tosave.get("id_rank", 0)
            if idtaxonref_torefresh : #and _idrank >= self.get_idrankGroup():
                ls_item_updated.append(idtaxonref_torefresh)
                #ensure to update the id_taxonref in the dict_tosave
                dict_tosave["id_taxonref"] = idtaxonref_torefresh
            else:
                msg = db_postgres().postgres_error()
                MessageBox().information_msgbox("Error", msg, True)
        
        #refresh UI if updated (tlview_taxonref and trView_hierarchy)
        #if ls_item_updated:
            #reset the id of PN_trview_names to force refresh (toolbox trigger by self.trView_hierarchy)
            # self.trview_names.id = 0
            # self.trview_metadata.id = 0
            #idrank = max(obj["id_rank"] for obj in ls_dict_tosave)
            #refresh the tlview_taxonref if rank is include into the view (grouped_idrank or higher)
            #if idrank >= self.get_idrankGroup():

        #refresh nodes in the treeview model
        self.trview_taxonref_refresh(ls_dict_tosave)
        #get the selecteditem from the trview_taxonref.model
        selecteditem = self.trview_taxonref_selectedItem()
           
        idtaxonref = ls_dict_tosave[0].get("id_taxonref", self.window.sender().PNTaxa.idtaxonref)
        #if no selection, create a new PNTaxa_with_Score to be sure to get hierarchy of item
        if selecteditem is None:
            selecteditem = PNTaxa_with_Score(idtaxonref)
        #set and select the item in the trView_hierarchy, with idtaxonref as selected item
        if selecteditem:
            #ensure to see the idtaxonref
            self.trView_hierarchy.setdata (selecteditem, idtaxonref)
            
        #efresh the sender PNTaxa_edit or PNTaxa_add
        self.window.sender().PNTaxa = self.trView_hierarchy.selecteditem()
        self.window.sender().refresh()


    def combo_taxa_selectedItem(self, selecteditem):
        # select the selecteditem in the combo_taxa or create if not exist
        index = -1

        self.combo_taxa_signal_connected(False)
    
        self.combo_taxa.setCurrentIndex(index)
        if selecteditem.id_rank >= 21:
            return
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=QtCore.Qt.UserRole).idtaxonref == selecteditem.idtaxonref:
                index = i
        if index == -1:
            self.combo_taxa.addItem(selecteditem.taxonref)
            index = self.combo_taxa.count() - 1
            self.combo_taxa.setItemData(index, selecteditem, role=QtCore.Qt.UserRole)
        self.combo_taxa_signal_connected(True)
        self.combo_taxa.setCurrentIndex(index)

    def combo_taxa_deletedItem(self, idtaxonref):
    #delete the selecteditem from the combo_taxa
        index = -1
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=QtCore.Qt.UserRole).idtaxonref == idtaxonref:
                index = i
                break
        if index != -1:
            self.combo_taxa.removeItem(index)

    def toolbox_click(self, index = None):
        #by default the currentindex
        if index is None:
            index = self.view.toolBox.currentIndex()
        #get the current selected item
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        #set the authors name to the delegate
        new_authors_name = selecteditem.authors
        self.authors_delegate.set_authors_name(new_authors_name)
        if index == 2  and self.trview_properties.id != selecteditem.idtaxonref:
            #print ("set identity data", selecteditem.idtaxonref)
            self.view.button_properties.setVisible(False)
            if selecteditem.id_rank < 21:
                identity_data = selecteditem.json_properties_count
                self.trview_properties.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
                #self.trview_properties.hearder = ["taxa", "count"]
                self.trview_properties.tab_header = ["Property", "Taxa count"]
            else:
                identity_data = selecteditem.json_properties
                self.trview_properties.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
                self.trview_properties.tab_header = ["Property", "Value"]
                self.view.button_properties.setVisible(True)
            #set the properties and metadata
            self.trview_properties.setData(identity_data)
            #conserve the selected idtaxonref 
            self.trview_properties.id = selecteditem.idtaxonref
        elif index == 1  and self.trview_metadata.id != selecteditem.idtaxonref:
            #print ("set metadata data", selecteditem.idtaxonref)
            #self.trview_metadata.setData ({})
            dict_metadata = selecteditem.json_metadata
            if dict_metadata is None:
                #return
                dict_metadata = {}
            #set the query time stamps
            self.view.label_time = ''
            if dict_metadata.get("score", None):
                self.view.label_time = str(dict_metadata["score"].get("query_time", ''))
            # #sort the jsonb according to the list of api (sort and exclude score)
            list_api = self.metadata_worker.list_api
            dict_final = {}
            for key in list_api:
                if dict_metadata.get(key, None):
                    dict_final[key] = dict_metadata.get(key, 'No results')
            #set the metadata data
            self.trview_metadata.setData (dict_final)
            self.trview_metadata.id = selecteditem.idtaxonref
            #self.trview_metadata.collapseAll()
        elif index == 0 : # and self.trview_names.id != selecteditem.idtaxonref:
            #print ("set names data", selecteditem.idtaxonref)
            self.trview_names_setdata(selecteditem)
            self.trview_names.id = selecteditem.idtaxonref

#functions for the trview
    def trview_filter_load(self):
        dict_db_properties = {}
        for _key, _value in self.db_properties.items():
            dict_db_properties[_key] = {}.fromkeys(_value,'')
        self.trview_filter.setData(dict_db_properties)



    def trview_names_setdata(self, selecteditem):
        json_names = db_taxa().db_get_names(selecteditem.idtaxonref)
        self.trview_names.setData(json_names)



    def trview_identity_changed(self, changed):
        self.view.button_properties.setEnabled(changed)

    def trview_identity_apply(self):
        #return if no change to update
        if not self.trview_properties.changed():
            return
        #get the current id for editing
        id_taxonref = self.trview_properties.id
        #get the dictionnaries (db = input and user = output)
        dict_user_properties = self.trview_properties.dict_user_properties()
        #dict_db_properties = self.trview_properties.dict_db_properties
    
        tab_result = {}
        for key, value in dict_user_properties.items():
            tab_tmp = {}
            for _key, _value in value.items():
                if _value !='':
                    tab_tmp[_key]= _value
            if len(tab_tmp) > 0:
                tab_result[key] = tab_tmp
        #query according to the len of the result (= Null if zero length)
        _properties = None
        if tab_result:
            _properties = json.dumps(tab_result)

        if not db_taxa().db_update_properties (id_taxonref, _properties):
            msg = db_postgres().postgres_error()
            MessageBox().information_msgbox("Error", msg, True)



    def trView_hierarchy_click(self):  
        #set the current view
        self.toolbox_click()
        self.refresh_ui_trview_hierarchy()

    def trView_hierarchy_dblclick(self):
    #set the selecteditem to the filter combo_taxa
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        self.combo_taxa_selectedItem(selecteditem)


        
    def trview_metadata_setDataAPI(self, base, api_json):
        # receive the slot from metaworker - save the json into the database when finish (base = 'END')
        selecteditem = self.trView_hierarchy.selecteditem()
        _selecteditem = self.metadata_worker.PNTaxa_model
        _data_list = None
        if base == "NOTCONNECTED":
            msg = "Error: no connection to the internet"
            MessageBox().information_msgbox("Connection error", msg, True)  
            self.view.button_metadata_refresh.setEnabled(True)
            return
        elif base == "END":
            self.view.button_metadata_refresh.setEnabled(True)
            #metadata_worker.PNTaxa_model.json_request = None
            if api_json is None:
                return
            tab_synonyms =[]
            #decompose synonyms and metadata
            for taxa in api_json: 
                try:
                    tab_synonyms += api_json[taxa]["synonyms"]
                #to suppress synonyms from json before saving (do we save or not ? NOT)
                    #api_json[taxa].pop("synonyms")
                except Exception:
                    continue
            #add new synonyms into the dbase to the id_taxonref
            if tab_synonyms:
                new_synonyms = 0
                tab_synonyms = [taxa.strip() for taxa in tab_synonyms]
                unique_set = set(tab_synonyms)
                #add new synonyms names according to the previous query
                for taxa in unique_set: #new_unique_taxa:
                    dict_taxa = functions.get_dict_from_species(taxa)
                    if dict_taxa is None:
                        dict_taxa = {}
                        dict_taxa["names"] = [taxa]
                    for value in dict_taxa["names"]:
                        if db_taxa().db_add_synonym(_selecteditem.id_taxonref, value, 'Homotypic'):
                            new_synonyms += 1
                #refresh the tab names for the current selecteditem if newsynonyms
                if new_synonyms > 0 and selecteditem == _selecteditem:
                    self.trview_names_setdata(selecteditem)             
            #manage and save json medata (including or not synonyms depends of the check line above)

        #update metadata
            _data_list = json.dumps(api_json)
            db_taxa().db_update_metadata (_selecteditem.id_taxonref, _data_list)

            if "score" in api_json:
                dict_score = api_json["score"]
                trview_item = self.proxy_model.sourceModel().getItem(_selecteditem.idtaxonref)
                if trview_item:
                    trview_item.taxaname_score = dict_score["taxaname_score"]
                    trview_item.authors_score = dict_score["authors_score"]
                self.trview_taxonref.repaint()
        else:
            self.view.button_metadata_refresh.setEnabled(False)

            #manage json in live ! coming from the metadata_worker api_thread, one by one
            if selecteditem != _selecteditem:
                return        
            if self.metadata_worker.status == 0:
                return
            if "score" in api_json:
                dict_score = api_json["score"]
                trview_item = self.proxy_model.sourceModel().getItem(_selecteditem.idtaxonref)
                if trview_item:
                    trview_item.taxaname_score = dict_score["taxaname_score"]
                    trview_item.authors_score = dict_score["authors_score"]
                del api_json["score"]
             #fill the treeview with the dictionnary json
            self.trview_taxonref.repaint()
            self.trview_metadata.dict_db_properties[base] = api_json
            self.trview_metadata.refresh()
        return



    def trview_taxonref_selectedItem(self):
        #transform the current index from proxy model to source model and return the selecteditem
        proxy_index = self.trview_taxonref.currentIndex()
        source_index = self.proxy_model.mapToSource(proxy_index)
        return self.proxy_model.sourceModel().data(source_index, QtCore.Qt.UserRole)

    def trview_taxonref_click(self):
    #set the hierarchy, names, metadata and properties of the selected taxa
        #check if a previous changed has not be saved
        # check if the buttonbox_identity is enabled (if properties have been changed)
        if self.view.button_properties.isVisible() and self.view.button_properties.isEnabled():
                self.view.button_properties.setEnabled(False)
                msg = "Some properties have been changed, save the changes ?"
                result = MessageBox().question_msgbox ("Save properties", msg)
                if result:
                    self.trview_identity_apply()
        
        # get the current selectedItem      
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem is None:
            return
        #selecteditem.id_taxonref = 166666666
    #set the treetaxonomy hierarchy
        #if selecteditem.id_taxonref !=self.trView_hierarchy.selecteditem().id_taxonref:
        self.trView_hierarchy.setdata (selecteditem)




    def trview_taxonref_dblclick(self, current_index):
        # Select or insert the selecteditem into the combo_taxa combobox for shortcut
        #selecteditem = self.trview_taxonref.model().data(current_index, QtCore.Qt.UserRole)
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem:
            self.combo_taxa_selectedItem(selecteditem)

    def trview_taxonref_refresh(self, dict_torefresh):
    #refresh (update) the trview_taxonref model according to the database for a list of idtaxonref (refresh taxa + childs)
   
        model = self.proxy_model.sourceModel()
        self.view.set_taxa_label('< no selection >')
        print ('longueur du dict_torefresh, ',len(dict_torefresh))
        #filter dict_torefresh to conserve only taxa to refresh (include in the view area [grouped_idrank or higher] and with id_taxonref)
        #conserve only one item in a hierarchical dict_torefresh
        dict_parent = {item["id_taxonref"]: item for item in dict_torefresh}
        ls_idtaxonref = []
        for item in dict_torefresh:
            _idrank = item.get("id_rank", None)
            _idtaxonref = item.get("id_taxonref", None)
            _idparent = item.get("id_parent", None)
            #only concerned if _idrank is >= grouped_idrank and with id_taxonref
            if _idtaxonref and _idrank and _idrank >= self.get_idrankGroup():
                #only add if no parent in the list to refresh (to avoid to refresh multiple times the same branch in the treeview)
                if _idparent and dict_parent.get(_idparent, None) is None:
                    ls_idtaxonref.append(_idtaxonref)
        if not ls_idtaxonref:
            return []
               
        #create list to update and to remove in the model
        items_to_update = []
        items_toremove = []
        for id_taxonref in ls_idtaxonref:
            _lsitems = self.get_list_PNTaxa(id_taxonref, True)
            if _lsitems:
                items_to_update.extend(_lsitems)
            else:
                items_toremove.append(id_taxonref)
        print ('longueur de la liste à rafraichir, ',len(items_to_update))
        print ('longueur de la liste à remove, ',len(items_toremove))
        #get the id_taxonref childs from the  to remove in the model
        items_toremove = db_taxa().db_get_childs(items_toremove)
        #remove nodes in the model
        for item in items_toremove:
            model.removeItem(item)
        #disconnect the signals
        try:
            #disconnect signal to avoid multiple events (except error if not yet connected)
            self.trview_taxonref.selectionModel().selectionChanged.disconnect()
        except Exception:
            pass
        #select null parent
        self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())

    #edit/add nodes in the model
        if items_to_update:   
            model.refresh(items_to_update)
            item = items_to_update[0]
            # _idtaxonref = item.id_taxonref
            # index = model.indexItem(_idtaxonref)
            # # #search for item index
            # # index = model.indexItem(item.id_taxonref)
            # # #search for the id_parent if index not valid
            # if not index.isValid():
            index = model.indexItem(item.id_taxonref)
            if not index.isValid():
                index = model.indexItem(item.id_parent)
            #get the index in the proxy model
            index = self.proxy_model.mapFromSource(index)
            if index.isValid():
                self.trview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)


        #reconnect the signal
        self.trview_taxonref.selectionModel().selectionChanged.connect(self.trview_taxonref_click)
        self.trview_taxonref.repaint()
        return items_to_update

    def trview_taxonref_refreshData(self, value = None):
        #refresh the data of the trview_taxonref according to the filtering checkboxes
        #force the checkbox to be Checked or partially Checked
        if self.view.checkBox_children.checkState() == QtCore.Qt.Unchecked:
            self.view.checkBox_children.setCheckState(QtCore.Qt.PartiallyChecked) # trigger a recursive signal with validated state
            return
        #get the check states
        checked = self.view.checkBox_checked.checkState()
        published = self.view.checkBox_published.checkState()
        accepted = self.view.checkBox_accepted.checkState()
        children_only = self.view.checkBox_children.checkState() == 2
        self.proxy_model.show_checked_mode = checked
        self.proxy_model.show_published_mode = published
        self.proxy_model.show_accepted_mode = accepted
        self.proxy_model.children_only = children_only
        self.proxy_model.invalidateFilter()
        self.trview_taxonref.repaint()
        #reset the current index
        self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
        selected_index = self.trview_taxonref.model().index(0,0)
        #select if valid
        if selected_index.isValid():
            self.trview_taxonref.selectionModel().setCurrentIndex(
                    selected_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
            self.trview_taxonref.expand(selected_index)
        else:
            self.trView_hierarchy.model().clear()
            self.trview_properties.model().clear()
            self.trview_metadata.model().clear()
            self.trview_names.model().clear()
        self.refresh_ui_trview_hierarchy()

    def trview_taxonref_setData(self):
        self.view.set_rank_label(f"Rank {self.view.rank_group}: ")
        # clean the content and selection of trview_taxonref
        self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
        self.proxy_model.sourceModel().clear()
        
        # #create the filter dictionnary for query the database
        # clade_sql = None
        # if self.combo_taxa.currentIndex() == -1:
        #     self.combo_taxa.setCurrentIndex(0)
        # combo_taxa_index = self.combo_taxa.currentIndex()
        # idtaxonref = self.combo_taxa.itemData(combo_taxa_index, role=QtCore.Qt.UserRole).idtaxonref
        # if idtaxonref == 0 and combo_taxa_index > 0:
        #     clade_sql = self.combo_taxa.currentText()
        # #if self.combo_taxa.currentText().startswith('AGP IV'):
        #     #clade_sql = self.combo_taxa.currentText().split(' - ')[1]
        # dict_filter = {"id_taxonref" : idtaxonref, 
        #                "search_name": self.view.search_taxon, 
        #                "clade": clade_sql, 
        #                "properties": self.trview_filter.dict_user_properties()
        #               }
        
        #query = self.db.exec(self.db_get_json_taxa())
        data = self.get_list_PNTaxa()

        #refresh all the data of the model with the new list
        self.proxy_model.sourceModel().refreshData(data)
        #refresh the visibility of items according to the proxy filter (accepted, published, children_only according to checkbox)
        self.trview_taxonref_refreshData()
        #ajust trview_taxonref column width        
        self.trview_taxonref.resizeColumnToContents(0)
        total_width = self.trview_taxonref.viewport().width()
        self.trview_taxonref.setColumnWidth(0, int(total_width * 2 / 3))




### MANAGE buttons   

    def button_reference_add_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            selecteditem = PNTaxa(1, 'Plantae',None,1, published=True, accepted=True) 
            #return            
        win = PNTaxa_add(selecteditem)
        win.apply_signal.connect(self.database_save_taxa)
        win.show()

    def button_reference_edit_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        win = PNTaxa_edit(selecteditem)
        win.apply_signal.connect(self.database_save_taxa)
        win.show()

    def button_reference_remove_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        # message to be display first (question, Yes or No)
        msg = f"""Are you sure you want to delete \"{selecteditem.taxonref}\"?
        The children and all associated names will be permanently deleted"""
        result = MessageBox().question_msgbox("Delete a taxon", msg, True)
        if not result :
            return

        #delete is confirmed
        ls_todelete = db_taxa().db_delete_reference(selecteditem.id_taxonref)
        if ls_todelete: #not result.lastError().isValid():
            #refresh the model and combo_taxa
            try:
                #disconnect signal to avoid multiple events (except error if not yet connected)
                self.trview_taxonref.selectionModel().selectionChanged.disconnect()
            except Exception:
                pass
            # Remove the selected taxa and childs in model and combo_taxa
            for idtaxonref in ls_todelete:
                # remove the item from the model
                self.proxy_model.sourceModel().removeItem(idtaxonref)
                self.combo_taxa_deletedItem(idtaxonref)
                
            index = self.trview_taxonref.currentIndex()
            if not index.isValid():
                index = self.proxy_model.index(0,0)
            self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
            self.trview_taxonref.selectionModel().selectionChanged.connect(self.trview_taxonref_click)
            self.trview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)

    def button_reference_merge_click(self):
        # get the selectedItem
        try:
            selecteditem = self.trView_hierarchy.selecteditem()
            win = PNTaxa_merge(selecteditem)
            win.show()
            #refresh the trview_taxonref (win.main_tableView)
            if win.updated:
                idtaxonref = win.selected_idtaxonref
                category = win.selected_category
                from_idtaxonref = selecteditem.idtaxonref
                if idtaxonref == from_idtaxonref:
                    return
                # execute the merge into the database
                if db_taxa().db_merge_reference(from_idtaxonref, idtaxonref, category):
                    #reset the id of PN_trview_names to force refresh (toolbox trigger by self.trView_hierarchy)
                    self.trview_names.id = 0
                    self.trview_metadata.id = 0
                    idrank = selecteditem.id_rank
                    # deleted the input taxa
                    self.proxy_model.sourceModel().removeItem(from_idtaxonref)
                    #refresh the tlview_taxonref
                    if idrank >= self.get_idrankGroup():
                        self.trview_taxonref_refresh([idtaxonref])
                    
                    #get the selecteditem from the trview_taxonref.model
                    selecteditem = self.trview_taxonref_selectedItem()
                    #if not found, create a new PNTaxa_with_Score
                    if selecteditem is None:
                        selecteditem = PNTaxa_with_Score(idtaxonref) #, False, False)
                    #set and select the merged item in the trView_hierarchy
                    if selecteditem:
                #ensure to see the idtaxonref, by switching the idrank temporarily
                        save_idrank = selecteditem.id_rank
                        selecteditem.id_rank = idrank
                        self.trView_hierarchy.setdata (selecteditem, idtaxonref)
                        selecteditem.id_rank = save_idrank
                else:
                    msg = db_postgres().postgres_error()
                    MessageBox().information_msgbox("Error", msg, True)


                # dict_tosave = {"id_taxonref":from_idtaxonref, "id_merge":idmerge, "category":category}
                # #get the id_taxonref from the database (should be the same as idmerge)
                # to_idtaxonref = self.database_save_taxon(dict_tosave)
                # if to_idtaxonref:
                #     # deleted the input taxa
                #     self.trview_taxonref.model().removeItem(from_idtaxonref)
                #     #refresh the destination taxa
                #     self.trview_taxonref_refresh(to_idtaxonref)
                    #win.close()
        except Exception:
            return

    def button_identity_apply_click(self):
        self.view.button_properties.setEnabled(False)
        self.trview_identity_apply()

    def button_identity_cancel_click(self):
    # message to be display first (question, Yes or Not)
        msg = "Are you sure you want to undo all changes and restore from the database ?"
        result = MessageBox().question_msgbox("Cancel properties", msg)
        if not result:
            return
        #cancel is confirmed
        self.trview_properties.refresh()

    def button_filter_reset_click(self):
        self.view.search_taxon =""
        self.trview_filter_load()
        self.trview_taxonref_setData()
        
    def button_metadata_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        #print (selecteditem.taxaname)
        self.view.button_metadata_refresh.setEnabled(False)
        if self.metadata_worker.status == 1:
            self.metadata_worker.kill()
            while self.metadata_worker.isRunning():                
                time.sleep(0.5)
        selecteditem.taxaname_score = 0
        selecteditem.authors_score = 0

        self.view.label_time = str(time.strftime("%Y-%m-%d %H:%M:%S"))
        self.trview_metadata.dict_db_properties.clear()
        self.trview_metadata.setData({})
        self.metadata_worker.PNTaxa_model = selecteditem
        self.metadata_worker.start()
        self.trview_taxonref.repaint()


    def button_synonym_add_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if self.trview_names.currentIndex().parent().isValid():
            category = self.trview_names.currentIndex().parent().data()
        else:
            category = self.trview_names.currentIndex().data()
        new_synonym = PNSynonym(None, selecteditem.taxonref, selecteditem.idtaxonref,category)
        class_newname = PNSynonym_edit(new_synonym)
        class_newname.add_signal.connect(self.apply_add_synonym)
        class_newname.show()

    def button_synonym_edit_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        _syno = self.trview_names.currentIndex().data()
        category = self.trview_names.currentIndex().parent().data()
        if not _syno or not category:
            return
        edit_synonym = PNSynonym(_syno, selecteditem.taxonref, selecteditem.idtaxonref,category)
        #edit_synonym.id_synonym = 1
        class_newname = PNSynonym_edit(edit_synonym)
        class_newname.edit_signal.connect(self.apply_edit_synonym)
        class_newname.show()

    def button_synonym_remove_click(self):
    #delete a synonym from the selected taxon
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if not self.trview_names.currentIndex().parent().isValid():
            return
        _currentsynonym = self.trview_names.currentIndex().data()
        if _currentsynonym is None:
            return

        # message to be display first (question, Yes or No)
        msg = f"Are you sure to permanently delete this name {_currentsynonym}?"
        result = MessageBox().question_msgbox("Delete a synonym", msg)
        if not result:
            return
        
        if db_taxa().db_delete_synonym(_currentsynonym):
            self.trview_names_setdata(selecteditem)
        else:
            msg = db_postgres().postgres_error()
            MessageBox().information_msgbox("Error", msg, True)
        
        self.refresh_ui_button_names()


    def apply_add_synonym(self, synonym, category):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if db_taxa().db_add_synonym(selecteditem.idtaxonref,synonym, category, True):
            self.window.sender().Qline_name.setText('')
            self.trview_names_setdata(selecteditem)
            self.refresh_ui_button_names()
        else:
            msg = db_postgres().postgres_error()
            MessageBox().information_msgbox("Error", msg, True)
        
    def apply_edit_synonym(self, synonym, category):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        _syno = self.trview_names.currentIndex().data()
        if selecteditem.idtaxonref == 0:
            return
        if db_taxa().db_edit_synonym(_syno, synonym, category):
            self.window.sender().close()
            self.trview_names_setdata(selecteditem)
            self.refresh_ui_button_names()
        else:
            msg = db_postgres().postgres_error()
            MessageBox().information_msgbox("Error", msg, True)




#refresh ui
    def refresh_ui_trview_taxonref(self, enabled: bool):
        self.view.button_showFilter.setEnabled(enabled)
        self.view.button_rankgroup.setEnabled(enabled)
        self.view.combo_taxa.setEnabled(enabled)
        self.view.checkBox_published.setEnabled(enabled)
        self.view.checkBox_accepted.setEnabled(enabled)
        self.view.checkBox_checked.setEnabled(enabled)
        self.view.checkBox_children.setEnabled(enabled)
        self.view.button_reference_add.setEnabled(enabled)

    def refresh_ui_trview_hierarchy(self):
    # refresh buttons, labels in the main UI (mainwindow)
        self.view.button_synonym_add.setEnabled(False)
        self.view.button_metadata_refresh.setEnabled(False)
        self.view.button_reference_edit.setEnabled(False)
        self.view.button_reference_merge.setEnabled(False)
        self.view.button_reference_remove.setEnabled(False)
        self.view.label_count = "< No Selection >"
        
        self.refresh_ui_label_count()
        self.refresh_ui_label_taxa()
        self.refresh_ui_button_names()
        # check if a taxon is selected
        selected_taxa = self.trView_hierarchy.selecteditem()
        if selected_taxa is None:
            self.trview_properties.setData()
            self.trview_metadata.setData()
            self.trview_names.setData()
            return
        elif not hasattr(selected_taxa, 'idtaxonref'):
            return
        elif selected_taxa.idtaxonref == 0:
            return
        
        #if a taxon is selected....
        self.view.button_synonym_add.setEnabled(True)
        self.view.button_metadata_refresh.setEnabled(True)
        #self.view.button_rankgroup.setEnabled(True)

        # buttons references visibility
        #self.view.button_reference_add.setEnabled(True)
        value = selected_taxa.id_rank >2
        self.view.button_reference_edit.setEnabled(value)
        self.view.button_reference_merge.setEnabled(value)
        self.view.button_reference_remove.setEnabled(value)

    def refresh_ui_button_names(self):
    # refresh buttons names enabled state according to trview_name.selectedItem
        value = False
        try:
            if self.trview_names.currentIndex().parent().isValid():
                value = self.trview_names.currentIndex().parent().data() != 'Autonyms'
        except Exception:
            value = False
        self.view.button_synonym_edit.setEnabled(value)
        self.view.button_synonym_remove.setEnabled(value)

    def refresh_ui_label_count(self):
    # Refresh taxa and group count with the model values
        count_taxa = self.proxy_model.childCount()
        count_parent = self.proxy_model.rowCount()
        #set the count parent, taxa
        group_text = self.view.rank_group
        _suffix = 'taxon'
        if count_taxa > 1:
            _suffix = 'taxa'
        msg = f" {count_taxa} {_suffix}, {count_parent} {group_text}(s)"
        self.view.label_count = msg
    
    def refresh_ui_label_taxa(self):
    #Refresh the taxa label with the current trview_taxonref selected item
        self.view.set_taxa_label("< No Selection >")
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem is None:
            return
        child_count = self.proxy_model.rowCount(self.trview_taxonref.currentIndex())
        _suffix = 'taxon'
        if child_count > 1:
            _suffix = 'taxa'
        self.view.set_taxa_label(f"{selecteditem.taxonref} ({child_count} {_suffix})")
    
    def close(self):
        self.window.close()

    def show(self):
        self.on_menu_theme_click (self.config_manager.theme)
        self.window.show()
        self.load_database()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    controller = MainWindowController(window)
    controller.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     window = MainWindow()
#     controller = MainWindowController(window)
#     controller.show()
#     sys.exit(app.exec())


