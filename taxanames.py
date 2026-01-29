# ruff: noqa: E402

#add icon.names in _icons.qrc then
#pyrcc5 _ressources.qrc -o core/ressources.py


import os
import sys

# Standard library
import json
import re
import time

# Third-party
from PyQt5 import QtCore, QtGui, QtWidgets
import core.ressources as ressources  # noqa: F401

# Internal modules
from core import functions
from models.taxa_model import (
    PNTaxa_searchAPI, PNTaxa_TreeModel, PNTaxa, PNTaxa_with_Score, 
    PNTaxa_QTreeView, PNTaxa_add, PNTaxa_edit, PNTaxa_merge,
    PNSynonym, PNSynonym_edit
)
from core.widgets import PN_JsonQTreeView, LinkDelegate, PostgresConfigDialog, load_ui_from_resources, PN_DatabaseStatusWidget, MessageBox
from core.database import DatabaseConnection, PN_dbTaxa

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
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        """ Create the editor (QlineEdit or ComboBox) according to type in the dict_properties         
        """
        if index.column() == 1:
            #get the columns name and value
            try:
                field_table = index.parent().data(0).lower()
                field_name = index.siblingAtColumn(0).data().lower()
                field_value = index.siblingAtColumn(1).data()
                field_def = functions.list_db_properties[field_table][field_name]
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
        r = option.rect
        rect = QtCore.QRect(r.right() - 22, r.top(), 20, r.height())
        self._button_rects[index] = rect

        # 👉 créer une option "comme un item"
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # texte à afficher
        opt.text = "⋮"
        opt.rect = rect
        opt.displayAlignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter

        # pas d’icône / pas de déco
        opt.features &= ~QtWidgets.QStyleOptionViewItem.HasDecoration

        # 👉 laisser QT peindre le texte selon le QSS
        option.widget.style().drawControl(
            QtWidgets.QStyle.CE_ItemViewItem,
            opt,
            painter,
            option.widget
        )

    def editorEvent(self, event, model, option, index):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            rect = self._button_rects.get(index)
            if rect and rect.contains(event.pos()):
                self._current_index = index
                self.menuclipboard.exec_(QtGui.QCursor.pos())
                return True
        return super().editorEvent(event, model, option, index)

    def _triggerClipboard(self, action_text):
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
        # --- Filter Variables (must correspond to self.show_nodes_...)
        self.show_checked_mode = 1  # 1: All, 2: True, 3: False
        self.show_published_mode = 1
        self.show_accepted_mode = 1

    # --- Helper method for match logic (reused from your code) ---
    def match_filter(self, mode, value):
        if mode == 1:
            return True
        if mode == 2:
            return bool(value)
        return not bool(value)
    
    def childCount(self):
    #retourne the number of visible child nodes in the proxy model
        total_child_count = 0
        for row in range(self.rowCount()):
            root_index = self.index(row, 0, QtCore.QModelIndex())
            if root_index.isValid():
                total_child_count += self.rowCount(root_index)
        return total_child_count

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        # set only nodes that are note in the list of hidden nodes (see setFilterConditions)
        index = self.sourceModel().index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        return index.data(QtCore.Qt.UserRole).visible
    
    # --- Method to signal filter change (to be called from your UI) ---
    def setFilterConditions(self, checked_mode, published_mode, accepted_mode, children_only=False):
        #Test the items of the model
        self.show_checked_mode = checked_mode
        self.show_published_mode = published_mode
        self.show_accepted_mode = accepted_mode
        for i in range(self.sourceModel().rowCount()):
            index = self.sourceModel().index(i, 0, QtCore.QModelIndex())
            node_root = index.data(QtCore.Qt.UserRole)
            a = 0
            #test childrens for each root node
            for child_row in range(self.sourceModel().rowCount(index)):
                index_child = self.sourceModel().index(child_row, 0, index)
                # 2. get the nodes infos
                node_child = index_child.data(QtCore.Qt.UserRole)
                taxaname_score = getattr(node_child, 'taxaname_score', None)
                published = getattr(node_child, 'published', False)
                accepted = getattr(node_child, 'accepted', False)
                # 3. Set the filter conditions and Apply the logic of filtering
                filters = [
                    (self.show_checked_mode, taxaname_score),
                    (self.show_published_mode, published),
                    (self.show_accepted_mode, accepted),
                ]
                node_child.visible = all(self.match_filter(mode, value) for mode, value in filters)
                if node_child.visible:
                    a += 1
            #add root node if children_only and no childs
            node_root.visible = not (children_only and a == 0)
        # This forces the Proxy Model to re-execute filterAcceptsRow for all nodes
        self.invalidateFilter()

##The MainWindow load the ui interface to navigate and edit taxaname###
class MainWindow(QtWidgets.QMainWindow):
    
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = load_ui_from_resources("taxanames.ui")
    # setting the main_treeView (list of taxa)
        self.trview_taxonref = self.window.main_treeView
        self.trview_taxonref.setSortingEnabled(True)
        self.trview_taxonref.header().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        #set the proxymodel for filtering and sorting
        self.proxy_model = TaxonomyProxyModel()
        self.proxy_model.setSourceModel(PNTaxa_TreeModel())
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.trview_taxonref.setModel(self.proxy_model)

    # setting the combo_taxa (special filters on taxa)
        self.combo_taxa = self.window.combo_taxa
        self.window.pushButtonMoveChilds.setVisible(False)
        self.window.pushButton.setVisible(False)

    # setting the buttons
        self.button_reset = self.window.buttonBox_metadata
        self.buttonbox_identity = self.window.buttonBox_identity
        button_cancel = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Cancel)
        button_apply = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Apply)
        button_apply_filter = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Apply)
        button_reset_filter = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Reset)
        button_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        button_cancel.setIcon (QtGui.QIcon(":/icons/nok.png"))
        button_cancel.clicked.connect (self.button_identity_cancel_click)
        button_apply.clicked.connect(self.button_identity_apply_click)
        button_apply_filter.clicked.connect(self.trview_taxonref_setData)
        button_reset_filter.clicked.connect(self.button_filter_reset_click)
    
    #setting the filter checkboxes to partially checked
        self.window.checkBox_published.setCheckState(QtCore.Qt.PartiallyChecked)
        self.window.checkBox_accepted.setCheckState(QtCore.Qt.PartiallyChecked)
        self.window.checkBox_withtaxa.setCheckState(QtCore.Qt.PartiallyChecked)
        self.window.checkBox_checked.setCheckState(QtCore.Qt.PartiallyChecked)

    #set the toolbox icon style
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(51))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))

    #add two labels to the statusbar
        #msg for the rank selected
        self.selected_rank_label = QtWidgets.QLabel()
        self.selected_rank_label.setGeometry(100, 40, 30, 25)
        self.selected_rank_label.setVisible(True)
        self.window.statusbar.addWidget(self.selected_rank_label)
        #msg for the selected taxon
        self.selected_taxa_label = QtWidgets.QLabel()
        self.selected_taxa_label.setGeometry(100, 40, 30, 25)
        self.selected_taxa_label.setVisible(True)
        self.window.statusbar.addWidget(self.selected_taxa_label)

    #set the group button (rank selection) and menu (to select the group for displaying the list of taxa)
        button_rankGroup = self.window.button_rankGroup
        menu_button_rankGroup = QtWidgets.QMenu()
        # create an exclusive action group for menu
        self.action_group = QtWidgets.QActionGroup(self)
        self.action_group.setExclusive(True)
        self.actions = []
        # set the list of the available ranks
        menu_items = ['Subregnum','Division', 'Classis', 'Subclassis', 'Order', 'Family', 'Genus']
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            action.setCheckable(True)
            self.action_group.addAction(action)  # Ajouter à l'action group
            self.actions.append(action)
            action.triggered.connect(lambda checked, item=item: self.menu_button_rankGroup_click(item))
            menu_button_rankGroup.addAction(action)
        #set the family as default selected item
        _selected_item = 5
        self.actions[_selected_item].setChecked(True)
        button_rankGroup.setText(menu_items[_selected_item])
        button_rankGroup.setMenu(menu_button_rankGroup)

    #set the theme menu (Diffnes as default)
        button_themes = self.window.button_themes
        button_themes.setText("Diffnes")
        button_themes_menu = QtWidgets.QMenu()
        path_ui = os.path.join(os.path.dirname(__file__), "ui")
        menu_items = [os.path.splitext(f)[0] for f in os.listdir(path_ui) if f.endswith(".qss")]
        
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            #action.setCheckable(True)
            action.triggered.connect(lambda checked, item=item: self.menu_button_themes_click(item))
            button_themes_menu.addAction(action)
        button_themes.setMenu(button_themes_menu)
        self.window.statusbar.addPermanentWidget(button_themes)

    #create the metadata worker (Qthread)
        self.metadata_worker = PNTaxa_searchAPI(self)        
    
    #Create the hierarchical treeview
        self.trView_hierarchy = PNTaxa_QTreeView ()
        self.window.trView_hierarchy_Layout.insertWidget(0,self.trView_hierarchy)
    
    #Create the treeviews for properties (identity, metadata and names)
        self.PN_trview_identity = PN_JsonQTreeView ()
        self.PN_tlview_metadata = PN_JsonQTreeView ()
        self.PN_tlview_names = PN_JsonQTreeView ()
        #insert the treeviews in the three layout
        layout = self.window.toolBox.widget(0).layout()
        layout.insertWidget(0,self.PN_trview_identity)        
        layout = self.window.toolBox.widget(1).layout()
        layout.insertWidget(0,self.PN_tlview_metadata)
        layout = self.window.toolBox.widget(2).layout()
        layout.insertWidget(0,self.PN_tlview_names)
        #set delegate for editing properties of PN_trview_identity
        delegate = EditProperties_Delegate()
        self.PN_trview_identity.setItemDelegate(delegate)
        self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)

    #set the filter treeview
        self.PN_trview_filter = PN_JsonQTreeView ()
        layout = self.window.frame_filter.layout()
        layout.insertWidget(1,self.PN_trview_filter)
        self.PN_trview_filter.setItemDelegate(delegate)
        self.PN_trview_filter.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
        self.window.frame_filter.hide()

        self.authors_delegate = MetadataDelegateWithAuthorCheck()
        self.PN_tlview_metadata.setItemDelegate(self.authors_delegate)
        #self.authors_delegate.menu_action_triggered.connect(self.menu_set_value_click)
    # setting the slots signals
        self.window.button_synonym_add.clicked.connect(self.button_synonym_add_click)
        self.window.button_synonym_edit.clicked.connect(self.button_synonym_edit_click)
        self.window.button_synonym_remove.clicked.connect(self.button_synonym_remove_click)
        self.window.button_reference_add.clicked.connect(self.button_reference_add_click)   
        self.window.button_reference_edit.clicked.connect(self.button_reference_edit_click)
        self.window.button_reference_remove.clicked.connect(self.button_reference_remove_click)
        self.window.button_reference_merge.clicked.connect(self.button_reference_merge_click)
        self.window.button_showFilter.toggled.connect(self.trView_filter_setVisible)    
        self.window.lineEdit_searchtaxon.returnPressed.connect(self.trview_taxonref_setData)
        self.window.checkBox_published.stateChanged.connect(self.trview_taxonref_refreshData)
        self.window.checkBox_accepted.stateChanged.connect(self.trview_taxonref_refreshData)
        self.window.checkBox_withtaxa.stateChanged.connect(self.trview_taxonref_refreshData)
        self.window.checkBox_checked.stateChanged.connect(self.trview_taxonref_refreshData)
        self.window.toolBox.currentChanged.connect(self.toolbox_click)
        self.button_reset.clicked.connect (self.button_metadata_click)
        self.trview_taxonref.selectionModel().selectionChanged.connect(self.trview_taxonref_click)
        self.trview_taxonref.doubleClicked.connect(self.trview_taxonref_dblclick)
        self.trView_hierarchy.doubleClicked.connect(self.trView_hierarchy_dblclick)
        self.trView_hierarchy.selectionModel().selectionChanged.connect(self.trView_hierarchy_click)
        self.PN_tlview_names.selectionModel().selectionChanged.connect(self.buttons_set_enabled)
        self.PN_trview_identity.changed_signal.connect(self.trview_identity_changed)
        self.metadata_worker.Result_Signal.connect(self.trview_metadata_setDataAPI)
    #set the buttons
        self.buttons_set_enabled()
        self.trview_filter_load()


    #     self.PN_database = PN_dbTaxa()
    #     self.window.statusBar().addPermanentWidget(self.PN_database)
    #     self.PN_database.open()      
    #     if not self.PN_database.dbopen:
    #         return
    # #initialize the commons database context
    #     functions.init_context(functions.AppContext(self.PN_database))

    #connect to the database, exit if not open
    #get the config file
        #ok = PostgresConfigDialog.ensure_config("config.ini", self)
        # dlg = PostgresConfigDialog("config.ini", self)
        # result = dlg.exec_()
        self.connected = False
        self.dbwidget_status = PN_DatabaseStatusWidget()
        self.window.statusBar().addPermanentWidget(self.dbwidget_status)
        self.dbwidget_status.clicked.connect(self.onStatusClicked)

    def onStatusClicked(self):
        dlg = PostgresConfigDialog("config.ini", self.window)
        result = dlg.exec_()
        if not result:
            return
        self.load_database()

    def load_database(self):
    #load the connection, load dialog box if not connected
        while True:
            config_file = functions.resource_path("config.ini")
            ok = PostgresConfigDialog.ensure_config(config_file, self)
            dbconn = DatabaseConnection()
            if ok:
                self.connected = dbconn.open_from_config(config_file)
                if self.connected:
                    break
            dlg = PostgresConfigDialog("config.ini", self.window)
            result = dlg.exec_()
            if not result:
                break
        try:
            self.combo_taxa.currentIndexChanged.disconnect()
        except Exception:
            pass    
        #status = PN_DatabaseStatusWidget(dbconn.dbname())
        self.combo_taxa.clear()
        self.combo_taxa.addItem('All names')
        self.combo_taxa.setItemData(0, PNTaxa(0, 'All names', '', 0), role=QtCore.Qt.UserRole)
        

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
        lst = functions.dbtaxa().db_get_apg4_clades()
        for clade in lst:
            self.combo_taxa.addItem(clade)
            self.combo_taxa.setItemData(self.combo_taxa.count() - 1, PNTaxa(0, clade), role=QtCore.Qt.UserRole)
        self.combo_taxa.setCurrentIndex(0)




        self.combo_taxa.currentIndexChanged.connect(self.trview_taxonref_setData)

    #initialize the trview_taxonref (list of taxa)
        self.trview_taxonref_setData()

    def trview_filter_load(self):
        dict_db_properties = {}
        for _key, _value in functions.list_db_properties.items():
            dict_db_properties[_key] = {}.fromkeys(_value,'')
        self.PN_trview_filter.setData(dict_db_properties)

    def trView_filter_setVisible(self, state):
        #set the visibility of the filter treeview
        if not state:
            self.window.frame_filter.hide()
        else:
            self.window.frame_filter.show()

    def menu_button_themes_click(self, item):
        #change the theme
        self.window.button_themes.setText(item)
        try:
            qss_file = functions.resource_path("ui", item + ".qss")
            with open(qss_file, "r") as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            msg = f"Unable to load the style: {e}"
            MessageBox().critical_msgbox("Error", msg)

    def db_get_grouped_PNtaxa(self, dict_filter = None):
        grouped_id_rank = self.button_rankGroup_idrank()
        records = functions.dbtaxa().db_get_json_taxa(grouped_id_rank, dict_filter)
        data = []
        for rec in records:
            item = PNTaxa_with_Score(rec.get("id_taxonref"), rec.get("taxaname"), rec.get("authors"), 
                            rec.get("id_rank"), rec.get("published"), rec.get("accepted"))
            item.id_parent = rec.get("id_parent")
            #set the taxaname_score and api_total
            item.taxaname_score = rec.get("taxaname_score", None)
            item.authors_score = rec.get("authors_score", None)
            data.append(item)
        return data

                    
    def refresh_label_count(self):
        # Display taxa and group count within the self.window.label_count
        #trigger by the refresh_signal from the model
        count_taxa = self.proxy_model.childCount()
        count_parent = self.proxy_model.rowCount()
        #count the number of visible parent rows 
        group_text = self.window.button_rankGroup.text()
        suffix = 'taxa'
        if count_taxa == 1:
            suffix = 'taxon'
        msg = f" {count_taxa} {suffix}, {count_parent} {group_text}(s)"
        self.window.label_count.setText(msg)
    
   
    def database_save_taxa(self, ls_dict_tosave):
        """ 
            common function for update (add_name and edit_name) when apply
            Save a taxon in the database from a list of dictionnaries:   
            if parentname is not present, it will update the taxon with id_parent = (searching the id_parent, in the dbase taxaname = parentname)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "parentname":text, "published":boolean, "accepted":boolean, "id_rank" :integer}
            if idparent is present, it will update the taxon with the id_parent (integer)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "id_parent":integer, "published":boolean, "accepted":boolean, "id_rank" :integer}
        """

        #internal function for saving one taxon in the database


#####main part of the function
        if not isinstance(ls_dict_tosave, list):
            ls_dict_tosave = [ls_dict_tosave]
        ls_item_updated = []
        #save any dict from the list
        for dict_tosave in ls_dict_tosave:
            idtaxonref_torefresh  = functions.dbtaxa().db_save_dict_taxa(dict_tosave)
            if idtaxonref_torefresh:
                ls_item_updated.append(idtaxonref_torefresh)
                #ensure to update the id_taxonref in the dict_tosave
                dict_tosave["id_taxonref"] = idtaxonref_torefresh
            else:
                msg = functions.db().postgres_error()
                MessageBox().critical_msgbox("Error", msg)
        
        #refresh UI if updated (tlview_taxonref and trView_hierarchy)
        if ls_item_updated:
            #reset the id of PN_tlview_names to force refresh (toolbox trigger by self.trView_hierarchy)
            self.PN_tlview_names.id = 0
            self.PN_tlview_metadata.id = 0
            #refresh items in tlview_taxonref
            #get the current values from trView_hierarchy selecteditem
            # idtaxonref = self.trView_hierarchy.selecteditem().idtaxonref
            # idrank = self.trView_hierarchy.selecteditem().id_rank
            #get the current values from the sender (PNTaxa_edit or PNTaxa_add)
            # idtaxonref = self.sender().PNTaxa.idtaxonref
            # idrank = self.sender().PNTaxa.id_rank
            #print (ls_dict_tosave)
            idtaxonref = ls_dict_tosave[0].get("idtaxonref", self.sender().PNTaxa.idtaxonref)
            idrank = max(obj["id_rank"] for obj in ls_dict_tosave)
            #refresh the tlview_taxonref if rank is include into the view (grouped_idrank or higher)
            if idrank >= self.button_rankGroup_idrank():
                self.trview_taxonref_refresh(ls_item_updated)
           
            #get the selecteditem from the trview_taxonref.model
            selecteditem = self.trview_taxonref_selectedItem()
            #if no selection, create a new PNTaxa_with_Score to be sure to get hierarchy of item
            if selecteditem is None:
                selecteditem = PNTaxa_with_Score(idtaxonref)
            #set and select the item in the trView_hierarchy, with idtaxonref as selected item
            if selecteditem:
                #ensure to see the idtaxonref
                self.trView_hierarchy.setdata (selecteditem, idtaxonref)
            
            #efresh the sender PNTaxa_edit or PNTaxa_add
            self.sender().PNTaxa = self.trView_hierarchy.selecteditem()
            self.sender().refresh()


    def combo_taxa_selectedItem(self, selecteditem):
        # select the selecteditem in the combo_taxa or create if not exist
        index = -1
        if selecteditem.id_rank >= 21:
            return
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=QtCore.Qt.UserRole).idtaxonref == selecteditem.idtaxonref:
                index = i
        if index == -1:
            self.combo_taxa.addItem(selecteditem.taxonref)
            index = self.combo_taxa.count() - 1
            self.combo_taxa.setItemData(index, selecteditem, role=QtCore.Qt.UserRole)
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
        
        if index is None:
            index = self.window.toolBox.currentIndex()
        self.window.toolBox.setItemIcon(0, QtGui.QIcon(":/icons/arrow1.png"))
        self.window.toolBox.setItemIcon(1, QtGui.QIcon(":/icons/arrow1.png"))
        self.window.toolBox.setItemIcon(2, QtGui.QIcon(":/icons/arrow1.png"))
        self.window.toolBox.setItemIcon(index, QtGui.QIcon(":/icons/arrow2.png"))
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem:
            new_authors_name = selecteditem.authors
            self.authors_delegate.set_authors_name(new_authors_name)
            if index == 0  and self.PN_trview_identity.id != selecteditem.idtaxonref:
                #print ("set identity data", selecteditem.idtaxonref)
                self.window.buttonBox_identity.setVisible(False)
                if selecteditem.id_rank < 21:
                    identity_data = selecteditem.json_properties_count
                    self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
                    #self.PN_trview_identity.hearder = ["taxa", "count"]
                    self.PN_trview_identity.tab_header = ["Property", "Taxa count"]
                else:
                    identity_data = selecteditem.json_properties
                    self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
                    self.PN_trview_identity.tab_header = ["Property", "Value"]
                    self.window.buttonBox_identity.setVisible(True)
                #set the properties and metadata
                self.PN_trview_identity.setData(identity_data,)
                #conserve the selected idtaxonref 
                self.PN_trview_identity.id = selecteditem.idtaxonref
            elif index == 1  and self.PN_tlview_metadata.id != selecteditem.idtaxonref:
                #print ("set metadata data", selecteditem.idtaxonref)
                #self.PN_tlview_metadata.setData ({})
                dict_metadata = selecteditem.json_metadata
                if dict_metadata is None:
                    #return
                    dict_metadata = {}
                #set the query time stamps
                self.window.label_query_time.setText('')
                if dict_metadata.get("score", None):
                    self.window.label_query_time.setText(dict_metadata["score"].get("query_time", ''))
                # #sort the jsonb according to the list of api (sort and exclude score)
                list_api = self.metadata_worker.list_api
                dict_final = {}
                for key in list_api:
                    if dict_metadata.get(key, None):
                        dict_final[key] = dict_metadata.get(key, 'No results')
                #set the metadata data
                self.PN_tlview_metadata.setData (dict_final)
                self.PN_tlview_metadata.id = selecteditem.idtaxonref
                #self.PN_tlview_metadata.collapseAll()
            elif index == 2  and self.PN_tlview_names.id != selecteditem.idtaxonref:
                #print ("set names data", selecteditem.idtaxonref)
                self.trview_names_setdata(selecteditem)
                self.PN_tlview_names.id = selecteditem.idtaxonref

        self.buttons_set_enabled()


    def set_values_to_none(self, data):
        if isinstance(data, dict):  
            return {key: self.set_values_to_none(value) for key, value in data.items()}
        else:
            return ''
        
    def button_rankGroup_idrank(self):
    #return the id_rank of the selected group (according to button_rankGroup text)
        group_text = self.window.button_rankGroup.text()
        idrankparent = functions.dbtaxa().db_get_rank(group_text, 'id_rank')
        if not idrankparent:
            idrankparent = 14 
        return idrankparent
    
    def menu_button_rankGroup_click(self, menu):
    #event when the menu_button_rankGroup is clicked
        self.window.button_rankGroup.setText(menu)
        self.trview_taxonref_setData()


    def trview_names_setdata(self, selecteditem):
        json_names = functions.dbtaxa().db_get_names(selecteditem.idtaxonref)
        self.PN_tlview_names.setData(json_names)

    def trview_identity_changed(self, changed):
        self.buttonbox_identity.setEnabled(changed)

    def trview_identity_apply(self):
        #return if no change to update
        if not self.PN_trview_identity.changed():
            return
        #get the current id for editing
        id_taxonref = self.PN_trview_identity.id
        #get the dictionnaries (db = input and user = output)
        dict_user_properties = self.PN_trview_identity.dict_user_properties()
        #dict_db_properties = self.PN_trview_identity.dict_db_properties
    
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

        if not functions.dbtaxa().db_update_properties (id_taxonref, _properties):
            msg = functions.db().postgres_error()
            MessageBox().critical_msgbox("Error", msg)

 
 

    def trView_hierarchy_dblclick(self):
    #set the selecteditem to the filter combo_taxa
        selecteditem = self.trView_hierarchy.selecteditem()
        self.combo_taxa_selectedItem(selecteditem)
    
    def trView_hierarchy_click(self):
        #selecteditem = self.trView_hierarchy.selecteditem()
        #print ("trView_hierarchy_click")
        self.toolbox_click()
            #set the rank_msg in the statusbar
        # get the current selectedItem
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem is None:
            return
        
        child_count = self.proxy_model.rowCount(self.trview_taxonref.currentIndex())
        if child_count == 0:
            child_count = ''
        elif child_count == 1:
            child_count = ' (' + str(child_count) + " taxon)"
        else:
            child_count = ' (' + str(child_count) + " taxa)"
        self.selected_taxa_label.setText(f"{selecteditem.taxonref}{child_count}")
        #set the metadata list
        #self.trview_names_setdata(selecteditem)


    def trview_metadata_setDataAPI(self, base, api_json):
        # receive the slot from metaworker - save the json into the database when finish (base = 'END')
        selecteditem = self.trView_hierarchy.selecteditem()
        _selecteditem = self.metadata_worker.PNTaxa_model
        _data_list = None
        if base == "NOTCONNECTED":
            msg = "Error: no connection to the internet"
            MessageBox().critical_msgbox("Connection error", msg)      
            self.button_reset.setEnabled(True)
            return
        elif base == "END":
            self.button_reset.setEnabled(True)
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
                        if functions.dbtaxa().db_add_synonym(_selecteditem.id_taxonref, value, 'Nomenclatural'):
                            new_synonyms += 1
                #refresh the tab names for the current selecteditem if newsynonyms
                if new_synonyms > 0 and selecteditem == _selecteditem:
                    self.trview_names_setdata(selecteditem)             
            #manage and save json medata (including or not synonyms depends of the check line above)

        #if the api_json is empty, do not save it
            # _json_to_save = {}
            # for key, value in api_json.items():
            #     #if the name is not empty, save it
            #     if value.get("name", None):
            #         _json_to_save[key] = value

            _data_list = json.dumps(api_json)
            functions.dbtaxa().db_update_metadata (_selecteditem.id_taxonref, _data_list)

            if "score" in api_json:
                dict_score = api_json["score"]
                trview_item = self.proxy_model.sourceModel().getItem(_selecteditem.idtaxonref)
                if trview_item:
                    trview_item.taxaname_score = dict_score["taxaname_score"]
                    trview_item.authors_score = dict_score["authors_score"]
                self.trview_taxonref.repaint()
        else:
            self.button_reset.setEnabled(False)

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
            self.PN_tlview_metadata.dict_db_properties[base] = api_json
            self.PN_tlview_metadata.refresh()
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
        #self.selected_taxa_label.setText('< no selection >')
        if self.buttonbox_identity.isVisible() and self.buttonbox_identity.isEnabled():
                self.buttonbox_identity.setEnabled(False)
                msg = "Some properties have been changed, save the changes ?"
                result = MessageBox().question_msgbox ("Save properties", msg)
                if result:
                    self.trview_identity_apply()
        
        # get the current selectedItem      
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem is None:
            return
    #set the treetaxonomy hierarchy
        self.trView_hierarchy.setdata (selecteditem)


       
    def trview_taxonref_dblclick(self, current_index):
        # Select or insert the selecteditem into the combo_taxa combobox for shortcut
        #selecteditem = self.trview_taxonref.model().data(current_index, QtCore.Qt.UserRole)
        selecteditem = self.trview_taxonref_selectedItem()
        if selecteditem:
            self.combo_taxa_selectedItem(selecteditem)

    def trview_taxonref_refresh(self, ls_idtaxonref):
    #refresh (update) the trview_taxonref model according to the database for a list of idtaxonref (refresh taxa + childs)
    #return a list of PNTaxa updated (PNTaxa1, PNTaxa2,...)

        if not isinstance(ls_idtaxonref, list):
            ls_idtaxonref = [ls_idtaxonref]
        if not ls_idtaxonref:
            return []
        
        model = self.proxy_model.sourceModel()
        #set the dict_filter
        dict_filter = {"id_taxonref" : self.trView_hierarchy.selecteditem().idtaxonref, "refresh" : True}
        ls_updated_items = self.db_get_grouped_PNtaxa(dict_filter)
        #re-initialise the current index
        self.selected_taxa_label.setText('< no selection >')
        self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
        #if list, refresh model and select the current index or the first updated item if index is not valid
        if ls_updated_items:
            item = ls_updated_items[0]    
            model.refresh(ls_updated_items)
            #search for item index
            index = model.indexItem(item.id_taxonref)
            #search for the id_parent if index not valid
            if not index.isValid():
                index = model.indexItem(item.id_parent)
            #get the index in the proxy model
            index = self.proxy_model.mapFromSource(index)
            #disconnect the signals
            try:
                #disconnect signal to avoid multiple events (except error if not yet connected)
                self.trview_taxonref.selectionModel().selectionChanged.disconnect()
            except Exception:
                pass

            #select parent if valid
            if index.isValid():
                self.trview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
            else: #not found, force loading through combo_taxa with item.id_parent
                self.combo_taxa_selectedItem(PNTaxa_with_Score(item.id_taxonref))
        #reconnect the signal
        self.trview_taxonref.selectionModel().selectionChanged.connect(self.trview_taxonref_click)
        #self.trview_taxonref.repaint()
        return ls_updated_items



    def trview_taxonref_refreshData(self, value = None):
        #refresh the data of the trview_taxonref according to the filtering checkboxes
        #force the checkbox to be Checked or partially Checked
        if self.window.checkBox_withtaxa.checkState() == QtCore.Qt.Unchecked:
            self.window.checkBox_withtaxa.setCheckState(QtCore.Qt.PartiallyChecked) # trigger a recursive signal with validated state
            return
        checked = self.window.checkBox_checked.checkState()
        published = self.window.checkBox_published.checkState()
        accepted = self.window.checkBox_accepted.checkState()
        children_only = self.window.checkBox_withtaxa.checkState() == 2
        self.proxy_model.setFilterConditions(checked, published, accepted, children_only)
        self.refresh_label_count()
        #self.trview_taxonref.repaint()
        #self.trview_taxonref.model().refreshData()

    def trview_taxonref_setData(self):
        self.selected_rank_label.setText(f"Rank {self.window.button_rankGroup.text()}: ")
        # clean the content and selection of trview_taxonref
        self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
        #clear both models first (ensure to empty the lists if the query is empty)
        self.proxy_model.sourceModel().clear()
        self.trView_hierarchy.model().clear()
        
        #create the filter dictionnary for query the database
        clade_sql = None
        if self.combo_taxa.currentIndex() == -1:
            self.combo_taxa.setCurrentIndex(0)
        combo_taxa_index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(combo_taxa_index, role=QtCore.Qt.UserRole).idtaxonref
        if idtaxonref == 0 and combo_taxa_index > 0:
            clade_sql = self.combo_taxa.currentText()
        #if self.combo_taxa.currentText().startswith('AGP IV'):
            #clade_sql = self.combo_taxa.currentText().split(' - ')[1]
        dict_filter = {"id_taxonref" : idtaxonref, 
                       "search_name": self.window.lineEdit_searchtaxon.text(), 
                       "clade": clade_sql, 
                       "properties": self.PN_trview_filter.dict_user_properties()
                      }
        
        #query = self.db.exec(self.db_get_json_taxa())
        data = self.db_get_grouped_PNtaxa(dict_filter)
        
        #set the filter button color
        nb_filter = dict_filter.get("nb_filter", None)
        self.window.button_showFilter.setStyleSheet(
                "color: rgb(0, 55, 217);" if nb_filter else ""
        )

        #refresh all the data of the model with the new list
        self.proxy_model.sourceModel().refreshData(data)
        #refresh the proxy filter (accepted, published, children_only according to checkbox)
        self.trview_taxonref_refreshData()

        #ajust trview_taxonref column width        
        self.trview_taxonref.resizeColumnToContents(0)
        total_width = self.trview_taxonref.viewport().width()
        self.trview_taxonref.setColumnWidth(0, int(total_width * 2 / 3))
        # force expand if a taxa is selected in the combobox_taxa
        if self.trview_taxonref.model().rowCount() == 1:
            self.trview_taxonref.expandAll()
        #select the first row (and activate the signal trview_taxonref_click), row = 0 if no taxa selected
        
        selected_index = self.trview_taxonref.model().index(0,0)
        if selected_index.isValid():
            self.trview_taxonref.selectionModel().setCurrentIndex(
                    selected_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)

   
   
### MANAGE buttons
    def buttons_set_enabled(self):
        #print ("buttons_set_enabled")
        # set any button to enabled = False
        self.window.button_synonym_add.setEnabled(False)
        self.window.button_synonym_edit.setEnabled(False)
        self.window.button_synonym_remove.setEnabled(False)
        self.window.button_reference_merge.setEnabled(False)
        self.window.button_reference_add.setEnabled(False)
        self.window.button_reference_edit.setEnabled(False)
        self.window.button_reference_remove.setEnabled(False)
        self.window.buttonBox_metadata.setEnabled(False)
        self.window.button_rankGroup.setEnabled(False)
        
        # check if a taxon is selected
        selected_taxa = self.trView_hierarchy.selecteditem()
        if selected_taxa is None:
            self.PN_trview_identity.setData()
            self.PN_tlview_metadata.setData()
            self.PN_tlview_names.setData()
            return
        elif not hasattr(selected_taxa, 'idtaxonref'):
            return
        elif selected_taxa.idtaxonref == 0:
            return
        #if a taxon is selected....
        self.window.button_synonym_add.setEnabled(True)
        self.window.buttonBox_metadata.setEnabled(True)
        self.window.button_rankGroup.setEnabled(True)

        # buttons of the names tab: check if a synonym is selected in the names tab, and set enabled buttons to add/remove
        value = False
        try:
            if self.PN_tlview_names.currentIndex().parent().isValid():
                value = self.PN_tlview_names.currentIndex().parent().data() != 'Autonyms'
        except Exception:
            value = False
        self.window.button_synonym_edit.setEnabled(value)
        self.window.button_synonym_remove.setEnabled(value)

        # buttons of the hierarchy: check if a childs item is selected in the hierarchy, and set enabled buttons
        # id_taxonref = None
        # try:
        #     id_taxonref = selected_taxa.idtaxonref

        #     #id_taxonref = int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
        # except Exception:
        #     pass
        #value = id_taxonref is not None
        self.window.button_reference_add.setEnabled(True)
        value = selected_taxa.id_rank >2
        self.window.button_reference_edit.setEnabled(value)
        self.window.button_reference_merge.setEnabled(value)
        self.window.button_reference_remove.setEnabled(value)
        
        

    def button_reference_add_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None: 
            return            
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
        ls_todelete = functions.dbtaxa().db_delete_reference(selecteditem.id_taxonref)
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
                #sql_update = f"CALL taxonomy.pn_taxa_set_synonymy({from_idtaxonref}, {idtaxonref}, '{category}');"
                # sql_update = self.sql_taxa_set_synonyms(from_idtaxonref, idtaxonref, category)
                # result = self.db.exec (sql_update)
                # code_error = result.lastError().nativeErrorCode()
                # if len(code_error) == 0:
                if functions.dbtaxa().db_merge_reference(from_idtaxonref, idtaxonref, category):
                    #reset the id of PN_tlview_names to force refresh (toolbox trigger by self.trView_hierarchy)
                    self.PN_tlview_names.id = 0
                    self.PN_tlview_metadata.id = 0
                    idrank = selecteditem.id_rank
                    # deleted the input taxa
                    self.proxy_model.sourceModel().removeItem(from_idtaxonref)
                    #refresh the tlview_taxonref
                    if idrank >= self.button_rankGroup_idrank():
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
                    msg = functions.db().postgres_error()
                    MessageBox().critical_msgbox("Error", msg)


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
        self.buttonbox_identity.setEnabled(False)
        self.trview_identity_apply()

    def button_identity_cancel_click(self):
    # message to be display first (question, Yes or Not)
        msg = "Are you sure you want to undo all changes and restore from the database ?"
        result = MessageBox().question_msgbox("Cancel properties", msg)
        if not result:
            return
        #cancel is confirmed
        self.PN_trview_identity.refresh()

    def button_filter_reset_click(self):
        self.window.lineEdit_searchtaxon.setText("")
        self.trview_filter_load()
        self.trview_taxonref_setData()
        
    def button_metadata_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        #print (selecteditem.taxaname)
        self.button_reset.setEnabled(False)
        if self.metadata_worker.status == 1:
            self.metadata_worker.kill()
            while self.metadata_worker.isRunning():                
                time.sleep(0.5)
        selecteditem.taxaname_score = 0
        selecteditem.authors_score = 0

        self.window.label_query_time.setText(time.strftime("%Y-%m-%d %H:%M:%S"))
        self.PN_tlview_metadata.dict_db_properties.clear()
        self.PN_tlview_metadata.setData({})
        self.metadata_worker.PNTaxa_model = selecteditem
        self.metadata_worker.start()
        self.trview_taxonref.repaint()


    def button_synonym_add_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if self.PN_tlview_names.currentIndex().parent().isValid():
            category = self.PN_tlview_names.currentIndex().parent().data()
        else:
            category = self.PN_tlview_names.currentIndex().data()
        new_synonym = PNSynonym(None, selecteditem.taxonref, selecteditem.idtaxonref,category)
        class_newname = PNSynonym_edit(new_synonym)
        class_newname.add_signal.connect(self.apply_add_synonym)
        class_newname.show()

    def apply_add_synonym(self, synonym, category):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if functions.dbtaxa().db_add_synonym(selecteditem.idtaxonref,synonym, category, True):
            self.sender().Qline_name.setText('')
            self.trview_names_setdata(selecteditem)
            self.buttons_set_enabled()
        else:
            msg = functions.db().postgres_error()
            MessageBox().critical_msgbox("Error", msg)
        


    def button_synonym_edit_click(self):
        # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        _syno = self.PN_tlview_names.currentIndex().data()
        category = self.PN_tlview_names.currentIndex().parent().data()
        if not _syno or not category:
            return
        edit_synonym = PNSynonym(_syno, selecteditem.taxonref, selecteditem.idtaxonref,category)
        #edit_synonym.id_synonym = 1
        class_newname = PNSynonym_edit(edit_synonym)
        class_newname.edit_signal.connect(self.apply_edit_synonym)

        class_newname.show()
        # self.trview_names_setdata(selecteditem)
        # self.buttons_set_enabled()

    def apply_edit_synonym(self, synonym, category):
                # get the selectedItem
        selecteditem = self.trView_hierarchy.selecteditem()
        _syno = self.PN_tlview_names.currentIndex().data()
        if selecteditem.idtaxonref == 0:
            return
        if functions.dbtaxa().db_edit_synonym(_syno, synonym, category):
            self.sender().close()
            self.trview_names_setdata(selecteditem)
            self.buttons_set_enabled()
        else:
            msg = functions.db().postgres_error()
            MessageBox().critical_msgbox("Error", msg)


    def button_synonym_remove_click(self):
    #delete a synonym from the selected taxon
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if not self.PN_tlview_names.currentIndex().parent().isValid():
            return
        _currentsynonym = self.PN_tlview_names.currentIndex().data()
        if _currentsynonym is None:
            return

        # message to be display first (question, Yes or No)
        msg = f"Are you sure to permanently delete this name {_currentsynonym}?"
        result = MessageBox().question_msgbox("Delete a synonym", msg)
        if not result:
            return
        
        if functions.dbtaxa().db_delete_synonym(_currentsynonym):
            self.trview_names_setdata(selecteditem)
        else:
            msg = functions.db().postgres_error()
            MessageBox().critical_msgbox("Error", msg)
        
        self.buttons_set_enabled()


    def close(self):
        self.window.close()

    def show(self):
        self.menu_button_themes_click ("Diffnes")
        self.window.show()
        self.load_database()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


