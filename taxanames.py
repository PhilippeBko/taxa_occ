########################################
##imports
import sys
import re
import json
import time
########################################
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import Qt, QModelIndex   #, QSortFilterProxyModel
########################################
from models.api_thread import TaxRefThread #, API_ENDEMIA
from models.taxa_model import (TreeModel, PNTaxa,  PN_add_taxaname, PN_edit_taxaname, PN_merge_taxaname, PNSynonym, PN_edit_synonym)
from core.widgets import PN_JsonQTreeView, PN_DatabaseConnect, PN_TaxaQTreeView
from core.functions import (list_db_properties, get_dict_from_species, get_str_value, postgres_error, get_dict_rank_value)
########################################



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
                field_def = list_db_properties[field_table][field_name]
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
            data = index.model().data(index, Qt.DisplayRole)
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
            #     model.setData(index.siblingAtColumn(0), font, Qt.FontRole)
            model.setData(index, _value)

##The MainWindow load the ui interface to navigate and edit taxaname###
class MainWindow(QtWidgets.QMainWindow):
    # dict_rank = {'Any rank': 0, 'Classis' : 6, 'Subclassis' : 7, 'Order': 8, 'Family': 10, 'Genus': 14,
    #         'Species': 21, 'Subspecies': 22, 'Variety': 23, 'Hybrid': 31}
    
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = uic.loadUi("ui/taxanames.ui")
        #self.current_selected_item = None

    # setting the main_tableView)
        self.tlview_taxonref = self.window.main_tableView
        self.tlview_taxonref.header().setSortIndicator(0, Qt.AscendingOrder)
        # connect the signal to the slot
        self.tlview_taxonref.header().sortIndicatorChanged.connect(self.on_header_clicked) #self.tlview_taxonref.model().sort)
        self.tlview_taxonref.setModel(TreeModel())

    # setting the combos
        self.combo_taxa = self.window.combo_taxa
        self.combo_taxa.addItem('Any taxon')
        self.combo_taxa.setItemData(0, PNTaxa(0, 'Any taxon', '', 0), role=Qt.UserRole)
        self.combo_taxa.setCurrentIndex(0)
    # setting the buttons
        self.window.pushButtonMoveChilds.setVisible(False)
        self.window.pushButton.setVisible(False)
        self.button_reset = self.window.buttonBox_metadata.button(QtWidgets.QDialogButtonBox.Reset)
        self.buttonbox_identity = self.window.buttonBox_identity
        button_cancel = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Cancel)
        button_apply = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Apply)
        button_apply_filter = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Apply)
        button_reset_filter = self.window.buttonBox_filter.button(QtWidgets.QDialogButtonBox.Reset)
        button_apply_filter.clicked.connect(self.tlview_taxonref_setData)
        button_reset_filter.clicked.connect(self.button_clean_click)    
    # setting the buttons and linedit slots
        self.window.pushButtonAdd.clicked.connect(self.button_add_synonym)
        self.window.pushButtonEdit.clicked.connect(self.button_edit_synonym)
        self.window.pushButtonDel.clicked.connect(self.button_delete_synonym)
        self.window.button_addNames.clicked.connect(self.button_addNames_click)   
        self.window.button_editNames.clicked.connect(self.button_editNames_click)
        self.window.button_delNames.clicked.connect(self.button_delNames_click)
        self.window.pushButtonMergeChilds.clicked.connect(self.button_MergeChilds_click)
        self.window.toolButton.toggled.connect(self.trView_filter_setVisible)
        self.window.splitter.setSizes([0, 1])

        self.button_reset.clicked.connect (self.button_metadata_refresh)
        button_cancel.clicked.connect (self.button_identity_cancel_click)
        button_apply.clicked.connect(self.button_identity_apply_click)
        self.window.lineEdit_searchtaxon.returnPressed.connect(self.tlview_taxonref_setData)
        self.combo_taxa.currentIndexChanged.connect(self.tlview_taxonref_setData)
    #set the toolbox icon style
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(51))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))
        self.window.toolBox.currentChanged.connect(self.toolbox_click)   
    #add two labels to the statusbar
        #msg for the total number of taxa
        self.rows_msg = QtWidgets.QLabel()
        self.rows_msg.setGeometry(100, 40, 30, 25)
        self.rows_msg.setStyleSheet("color: black;")
        self.rows_msg.setVisible(True)
        self.window.statusbar.addWidget(self.rows_msg)
        #msg for the selected taxon
        self.rank_msg = QtWidgets.QLabel()
        self.rank_msg.setGeometry(100, 40, 30, 25)
        self.rank_msg.setVisible(True)
        self.window.statusbar.addWidget(self.rank_msg)
    #set the group button (to select the group for displaying the list of taxa)
        group_button = self.window.group_button
        group_button.setText("Division")
        group_menu = QtWidgets.QMenu()
        # create an exclusive action group for menu
        self.action_group = QtWidgets.QActionGroup(self)
        self.action_group.setExclusive(True)
        self.actions = []
        # set the list of items
        menu_items = ['Division', 'Classis', 'Order', 'Family', 'Genus', 'Species']
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            action.setCheckable(True)
            self.action_group.addAction(action)  # Ajouter à l'action group
            self.actions.append(action)
            action.triggered.connect(lambda checked, item=item: self.group_menu_click(item))
            group_menu.addAction(action)
        self.actions[0].setChecked(True)
        group_button.setMenu(group_menu)

    #set the theme menu
        theme_button = self.window.themes_button
        theme_button.setText("Diffnes")
        theme_menu = QtWidgets.QMenu()
        menu_items = ["Adaptic", "Combinear", "Diffnes",  "Lightstyle", "Obit", "SpyBot", "Geoo"]
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            action.triggered.connect(lambda checked, item=item: self.theme_menu(item))
            theme_menu.addAction(action)
        theme_button.setMenu(theme_menu)
        self.window.statusbar.addPermanentWidget(theme_button)
        
    #setting the hierarchical treeview
        self.trView_hierarchy = PN_TaxaQTreeView ()
        self.trView_hierarchy.doubleClicked.connect(self.trView_hierarchy_dblclick)
        self.window.trView_hierarchy_Layout.insertWidget(0,self.trView_hierarchy)
    #connect the treeviews for properties (identity, metadata and names)
        self.PN_trview_identity = PN_JsonQTreeView ()
        self.PN_tlview_metadata = PN_JsonQTreeView ()
        self.PN_tlview_names = PN_JsonQTreeView ()
    #insert the treeview in the three layout
        layout = self.window.toolBox.widget(0).layout()
        layout.insertWidget(0,self.PN_trview_identity)        
        layout = self.window.toolBox.widget(1).layout()
        layout.insertWidget(0,self.PN_tlview_metadata)
        layout = self.window.toolBox.widget(2).layout()
        layout.insertWidget(0,self.PN_tlview_names)
    #set delegate for editing properties of PN_trview_identity
        self.delegate = EditProperties_Delegate()
        self.PN_trview_identity.setItemDelegate(self.delegate)
        self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
    #set the filter treeview
        self.PN_trview_filter = PN_JsonQTreeView ()
        layout = self.window.frame_filter.layout()
        layout.insertWidget(1,self.PN_trview_filter)
        self.PN_trview_filter.setItemDelegate(self.delegate)
        self.PN_trview_filter.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
    #set the buttons
        self.set_enabled_buttons()

    #connect to the database, exit if not open
        connected_indicator = PN_DatabaseConnect()
        self.window.statusBar().addPermanentWidget(connected_indicator)
        connected_indicator.open()      
        if not connected_indicator.dbopen:
            return
        self.db = connected_indicator.db
    #connect signals
        self.PN_trview_identity.changed_signal.connect(self.trview_identity_changed)        
    #connect the thread
        self.metadata_worker = TaxRefThread(app)
        self.metadata_worker.Result_Signal.connect(self.trview_metadata_setDataAPI)        
    #initialize the tlview_taxonref (list of taxa)
        self.tlview_taxonref_setData()

    def on_header_clicked(self, column):
    #event when the header is clicked to sort the tlview_taxonref
        rootItem = None
        model = self.tlview_taxonref.model()
        order = self.tlview_taxonref.header().sortIndicatorOrder()
        if not model:
            return
        #get the parent Node
        selecteditem = model.data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem:
            rootItem = model.getNode(selecteditem.id_parent)
        model.sortItems(column, order, rootItem)

    def trView_filter_setVisible(self, state):
        #set the visibility of the filter treeview
        if not state:
            self.window.splitter.setSizes([0, 1])
        else:
            self.window.splitter.setSizes([300, 200])

    def theme_menu(self, item):
        #change the theme
        self.window.themes_button.setText(item)
        qss_file =  "ui/" + item + ".qss"
        with open(qss_file, "r") as f:
            app.setStyleSheet(f.read())

    # def test_endemia(self):
    #     with open("ui/Combinear.qss", "r") as f:
    #         #with open("Photoxo.qss", "r") as f:
    #         _style = f.read()
    #         app.setStyleSheet(_style)
    #     #return
    

    #     sql_tmp = "SELECT id_taxonref, taxaname, authors, id_rank FROM taxonomy.taxa_names WHERE id_rank = 21"
    #     query = self.db.exec(sql_tmp)
    #     while query.next():
    #         idtaxonref = query.value("id_taxonref")
    #         myPNTaxa = PNTaxa(idtaxonref, query.value("taxaname"), query.value("authors"),query.value("id_rank"))
    #         _classeAPI = API_ENDEMIA(myPNTaxa)
    #         _response = _classeAPI.get_metadata()
    #         _id = None
    #         if _response:
    #             _id = _response['id']
    #             sql_update = f"UPDATE taxonomy.taxa_reference SET id_endemia = {_id} WHERE id_taxonref = {idtaxonref}"
    #         else:
    #             sql_update = f"UPDATE taxonomy.taxa_reference SET id_endemia = NULL WHERE id_taxonref = {idtaxonref}"
    #         print (idtaxonref, _id)
    #         #QtSql.QSqlQuery(sql_update)
    #         self.db.exec(sql_update)
    #     print ("end")

    def close(self):
        self.window.close()

    def show(self):
        self.window.show()

    def sql_taxa_delete_synonym(self, synonym):
        #return a sql statement for deleting a synonym
        return f"SELECT taxonomy.pn_names_delete ('{synonym}')"

    def sql_taxa_delete_reference(self, id_taxonref, do_update=False):
        #return a sql statement for deleting a reference name
        return f"SELECT * FROM taxonomy.pn_taxa_delete ({id_taxonref}, {do_update})"

    def sql_taxa_get_names(self):
    #create a filter on taxa according to combo state and others filters (names)
        sql_where = ''
        tab_sql = []
        nb_filter = 0
        #get the grouped id_rank
        idrankparent = self.group_idrank()
        #get the dict_user properties
        tab_filter = self.PN_trview_filter.dict_user_properties().copy()
        #sql_where from the lineEdit_search
        txt_search = self.window.lineEdit_searchtaxon.text()
        txt_search = re.sub(r'[\*\%]', '', txt_search)
        if len(txt_search) > 0:
            sql_where = f"\na.id_taxonref IN (SELECT (taxonomy.pn_taxa_childs(id_taxonref, true)).id_taxonref id_taxonref FROM taxonomy.pn_taxa_searchname('%{txt_search}%') GROUP by id_taxonref)"
            tab_sql.append(sql_where)
            nb_filter = 1
        ## sql for the filter (dict_user properties de self.PN_trview_filter)
        for key, value in tab_filter.items():
            for key2, value2 in value.items():
                if value2:
                    _prop = "(a.properties  @> '{%key%:{%key2%:%value%}}')"
                    _prop = _prop.replace('%', chr(34))
                    _prop = _prop.replace('key2', key2)
                    _prop = _prop.replace('key', key)
                    _prop = _prop.replace('value', value2)
                    tab_sql.append(_prop)
                    nb_filter += 1
        #only species and infra species will be displayed
        sql_where =" WHERE a.id_rank >= 21"
        #add queries
        if tab_sql:
            sql_props = ' AND ' + (' AND '.join(tab_sql))
            sql_where += sql_props
        #set color to button filter
        if nb_filter > 0:
            self.window.toolButton.setStyleSheet("color: rgb(0, 55, 217);")
        else:
            self.window.toolButton.setStyleSheet("")
    # add a filter for childs if idtaxonref is not None
        sql_join = ''
        index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(index, role=Qt.UserRole).idtaxonref
        if idtaxonref > 0:
            sql_join = f"\nINNER JOIN taxonomy.pn_taxa_childs ({idtaxonref},True) b ON a.id_taxonref = b.id_taxonref"
    
    #set the final sql_query, including sql_where and sql_join
        sql_query = f"""
                    WITH taxon AS (
                        SELECT a.id_taxonref, a.taxaname, a.authors, a.published, a.metadata,
                            taxonomy.pn_taxa_getparent(a.id_parent, {idrankparent}) AS id_parent,
                            a.id_rank
                        FROM taxonomy.taxa_names a
                        {sql_join}
                        {sql_where}
                    ),
                    parents AS (
                        SELECT id_taxonref, taxaname, authors, published, metadata,
                            -1::integer AS id_parent, {idrankparent}::integer as id_rank
                        FROM taxonomy.taxa_names
                        WHERE id_taxonref IN (SELECT DISTINCT id_parent FROM taxon)
                    ),
                    all_taxa AS (
                        SELECT * FROM parents
                        UNION ALL
                        SELECT * FROM taxon
                    )
                    SELECT a.id_taxonref, a.taxaname, a.authors, a.published, c.score_api, 
                           a.id_parent, a.id_rank
                    FROM all_taxa a
                    LEFT JOIN (
                        SELECT id_taxonref, COUNT(*) AS score_api
                        FROM (
                            SELECT id_taxonref, jsonb_each(metadata) 
                            FROM all_taxa
                            WHERE metadata IS NOT NULL
                        ) z
                        GROUP BY id_taxonref
                    ) c
                    ON a.id_taxonref = c.id_taxonref
                    ORDER BY a.taxaname;
                """
        
        # return the sql_query
        return sql_query

    def tlviews_clear(self):
        # clear the contents of any tblview
        self.PN_trview_identity.setModel(None)
        self.PN_tlview_metadata.setModel(None)
        self.trView_hierarchy.setModel(None) 
        self.set_enabled_buttons()

    def tlviews_refresh(self, idtaxonref=0):
        # save the current selected row
        currentrow = self.tlview_taxonref.currentIndex().row()
        # refresh the view
        self.tlview_taxonref.repaint()
        #return
        # get the row (id_taxonref) in data of the sourceModel
        row = -1 #self.tlview_taxonref.model().sourceModel().row_idtaxonref(idtaxonref)  # item.idtaxonref) ##id_taxonref)
        if row == -1:
            row = currentrow
        row = max(0, min(row, self.tlview_taxonref.model().rowCount() - 1))
        #item = self.tlview_taxonref.model().getItem(idtaxonref)
        # get the index and obtain the source map index from the model itself
        index = self.tlview_taxonref.model().index(row, 0)
        index = self.tlview_taxonref.currentIndex()
        self.tlview_taxonref.setCurrentIndex(QModelIndex())
        #index = item.index()
        #index = self.tlview_taxonref.model().mapFromSource(index)
        self.tlview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
    
    def combo_taxa_selectedItem(self, selecteditem):
        # select the selecteditem in the combo_taxa or create if not exist
        index = -1
        if selecteditem.id_rank >= 21:
            return
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=Qt.UserRole).idtaxonref == selecteditem.idtaxonref:
                index = i
        if index == -1:
            self.combo_taxa.addItem(selecteditem.taxonref)
            index = self.combo_taxa.count() - 1
            self.combo_taxa.setItemData(index, selecteditem, role=Qt.UserRole)
        self.combo_taxa.setCurrentIndex(index)
        self.tlview_taxonref.expandAll()

    def combo_taxa_deletedItem(self, selecteditem):
    #delete the selecteditem from the combo_taxa
        index = -1
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=Qt.UserRole).idtaxonref == selecteditem.idtaxonref:
                index = i
                break
        if index != -1:
            self.combo_taxa.removeItem(index)
    
    def trview_names_setdata(self, selecteditem):
        #self.PN_tlview_names.setData(self.get_similar_names(selecteditem.idtaxonref))
        self.PN_tlview_names.setData(selecteditem.json_names)
        selection = self.PN_tlview_names.selectionModel()
        selection.selectionChanged.connect(self.set_enabled_buttons)

    # def trview_names_changed(self, changed):
    #     value = False
    #     try:
    #         if self.PN_tlview_names.currentIndex().parent().isValid():
    #             value = self.PN_tlview_names.currentIndex().data() is not None
    #     except Exception:
    #         value = False
    #     self.window.pushButtonEdit.setEnabled(value)
    #     self.window.pushButtonDel.setEnabled(value)
    #     self.set_enabled_buttons()

    def toolbox_click(self, index):
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(index, self.window.style().standardIcon(51))

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
    
    #create a sub dictionnaries (a copy without the key identity) to compare only json_properties
        #sub_dict_db_properties = dict_db_properties.copy()
        #del sub_dict_db_properties["identity"]
        #sub_dict_user_properties = dict_user_properties.copy()
        #del sub_dict_user_properties["identity"]
        #if sub_dictionnaries are different, proceed to update with only non-null values
        #if self.PN_trview_identity.changed():
        #if sub_dict_db_properties != sub_dict_user_properties:
        tab_result = {}
        for key, value in dict_user_properties.items():
            tab_tmp = {}
            for _key, _value in value.items():
                if _value !='':
                    tab_tmp[_key]= _value
            if len(tab_tmp) > 0:
                tab_result[key] = tab_tmp
        #query according to the len of the result (= Null if zero length)
        if tab_result:
            _data_list = json.dumps(tab_result)
            sql_query = f"UPDATE taxonomy.taxa_reference SET properties = '{_data_list}'"
        else:
            sql_query = "UPDATE taxonomy.taxa_reference SET properties = NULL"
        sql_query += f" WHERE id_taxonref = {id_taxonref} AND id_rank >= 21"

        result = self.db.exec (sql_query)
        code_error = result.lastError().nativeErrorCode ()
        if len(code_error) != 0:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
       
    def trView_hierarchy_selecteditem(self):
    #transform the dict_item from the hierarchical selecteditem to a PNTaxa object
        dict_item = self.trView_hierarchy.selecteditem()
        if dict_item is None:
            return
        item = PNTaxa(dict_item["idtaxonref"], dict_item["taxaname"], dict_item["authors"], 
                      dict_item["idrank"], dict_item["published"])
        item.parent_name = dict_item["parent"]
        return item

    def trView_hierarchy_dblclick(self):
    #set the selecteditem to the filter combo_taxa
        selecteditem = self.trView_hierarchy_selecteditem()
        self.combo_taxa_selectedItem(selecteditem)
     
    def set_values_to_none(self, data):
        if isinstance(data, dict):  
            return {key: self.set_values_to_none(value) for key, value in data.items()}
        else:
            return ''
        
    def group_idrank(self):
    #return the id_rank of the selected group (according to group_button text)
        group_text = self.window.group_button.text()
        idrankparent = get_dict_rank_value(group_text, 'id_rank')
        if not idrankparent:
            idrankparent = 14 
        return idrankparent
    
    def group_menu_click(self, menu):
    #event when the group_menu is clicked
        self.window.group_button.setText(menu)
        self.tlview_taxonref_setData()

    def tlview_taxonref_click(self):
    #set the hierarchy, names, metadata and properties of the selected taxa
        #check if a previous changed has not be saved
        # check if the buttonbox_identity is enabled (if properties have been changed)
        if self.buttonbox_identity.isVisible() and self.buttonbox_identity.isEnabled():
                msg = "Some properties have been changed, save the changes ?"
                result = QtWidgets.QMessageBox.question(None, "Cancel properties", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
                self.buttonbox_identity.setEnabled(False)
                if result == QtWidgets.QMessageBox.Yes:
                    self.trview_identity_apply()
                   #self.buttonbox_identity.setEnabled(False)
        # clear lists
        self.tlviews_clear()
        
        # get the current selectedItem
        selecteditem = self.tlview_taxonref.model().data( self.tlview_taxonref.currentIndex(), Qt.UserRole)
        #self.current_selected_item = selecteditem
        if selecteditem is None:
            return
        #set the filter to None
        if self.PN_trview_filter.model() is None:
            filter_data = selecteditem.json_properties.copy()
            self.PN_trview_filter.setData(self.set_values_to_none(filter_data))
        
        #get the properties according to the id_rank
        if selecteditem.id_rank < 21:
            identity_data = selecteditem.json_properties_count
            self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.window.buttonBox_identity.setVisible(False)
        else:
            identity_data = selecteditem.json_properties
            self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.CurrentChanged)
            self.window.buttonBox_identity.setVisible(True)
        #set the properties and metadata
        self.PN_trview_identity.setData(identity_data)
        #conserve the selected idtaxonref 
        self.PN_trview_identity.id = selecteditem.idtaxonref
        self.PN_tlview_metadata.setData (selecteditem.json_metadata)
        self.trview_names_setdata(selecteditem)
        #set the treetaxonomy hierarchy
        if self.trView_hierarchy.model() is None :
            self.trView_hierarchy.setdata (selecteditem)
            self.set_enabled_buttons()
            selection = self.trView_hierarchy.selectionModel()
            selection.selectionChanged.connect(self.set_enabled_buttons)
       
    def tlview_taxonref_dblclick(self, current_index):
        # Select or insert the selecteditem into the combo_taxa combobox for shortcut
        selecteditem = self.tlview_taxonref.model().data(current_index, Qt.UserRole)
        if selecteditem:
            self.combo_taxa_selectedItem(selecteditem)

    def tlview_taxonref_setData(self):
        # Fill the main tlview_taxonref with the concacenate sql (cf.sql_reference_names)
        # clean the content and selection of tlview_taxonref
        self.tlview_taxonref.setCurrentIndex(QModelIndex())
        #tlview_similar.model().sourceModel().resetdata(None)
        self.tlviews_clear()
        # search for a selected taxonref in combo_taxa
        index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(index, role=Qt.UserRole).idtaxonref        
        # fill tlview with query result
        data = []
        query = self.db.exec(self.sql_taxa_get_names())
        i = 0
        row = 0
        while query.next():
            #select the row 
            if query.value("id_taxonref") == idtaxonref:
                row = i
            item = PNTaxa(query.value("id_taxonref"), query.value("taxaname"), query.value("authors"), 
                        query.value("id_rank"), query.value("published"))
            item.api_score = query.value("score_api")
            item.id_parent = query.value("id_parent")
            if item.id_parent == -1:
                item.id_parent = None
            else:
                i += 1 
            data.append(item)
            
        # reset the model to the tableview for refresh
        model_tableview = TreeModel(data)
        self.tlview_taxonref.setModel(model_tableview)
        #self.tlview_taxonref.expandAll()
        #self.tlview_taxonref.selectionModel().selectionChanged.connect(self.tlview_taxonref_before_clickitem)
        self.tlview_taxonref.selectionModel().selectionChanged.connect(self.tlview_taxonref_click)
        self.tlview_taxonref.doubleClicked.connect(self.tlview_taxonref_dblclick)

        # self.tlview_taxonref.model().sourceModel().resetdata(data)
        self.tlview_taxonref.resizeColumnToContents(0)
        total_width = self.tlview_taxonref.viewport().width()  # ou treeview.width()
        self.tlview_taxonref.setColumnWidth(0, int(total_width * 2 / 3))
        self.tlview_taxonref.hideColumn (2)

        # Display row count within the statusbar
        msg = str(i) + " taxa"
        if i <= 1:
            msg = str(i) + " taxon"
        self.rows_msg.setText(msg)

        #select the first row
        selected_index = self.tlview_taxonref.model().index(row,0)
        self.tlview_taxonref.selectionModel().setCurrentIndex(
                selected_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)



    
    def trview_metadata_setDataAPI(self, base, api_json):
        # receive the slot from metaworker - save the json into the database when finish (base = 'END')
        selecteditem = self.tlview_taxonref.model().data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        _selecteditem = self.metadata_worker.PNTaxa_model
        sql_query =''
        _data_list = None

        if base == "NOTCONNECTED":
            msg = "Error : no connection to the internet"
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            self.button_reset.setEnabled(True)
            return
        elif base == "END":
            self.button_reset.setEnabled(True)
            #metadata_worker.PNTaxa_model.json_request = None
            if api_json is None: # when a kill
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
            #manage synonyms, search for duplicate
            _taxaname=''
            _parser=''
            for taxa in tab_synonyms:
                taxa = taxa.strip()
                _taxaname += _parser +"'" +taxa.strip() +"'"
                _parser=", "
            #get the new names that are not in the taxa namespace (id_taxonref IS NULL)
            sql_query = f"""
                        SELECT 
                            original_name 
                        FROM 
                            taxonomy.pn_taxa_searchnames( array[{_taxaname}]) 
                        WHERE 
                            id_taxonref IS NULL
                        """
            #sql_query = sql_query.replace('_taxaname', _taxaname)
            query = self.db.exec (sql_query)
            new_unique_taxa = []
            while query.next():
                new_unique_taxa.append (query.value("original_name"))

            #add new synonyms names according to the previous query            
            sql_insert = f"""
                            SELECT 
                                taxonomy.pn_names_add ('_synonymstr','Nomenclatural',{selecteditem.id_taxonref})
                        """
            for taxa in new_unique_taxa:
                dict_taxa = get_dict_from_species(taxa)
                if dict_taxa is None:
                    dict_taxa = {}
                    dict_taxa["names"] = [taxa]
                for value in dict_taxa["names"]:
                    sql_query = sql_insert.replace('_synonymstr', str(value))
                    try:
                        #query = QtSql.QSqlQuery()
                        self.db.exec(sql_query)
                        #delete current model to ensure refresh of similar names
                        #self.tlview_similar.setModel(None)
                    except Exception:
                        continue
            #manage and save json medata (including or not synonyms depends of the check line above)
            if api_json:
                _data_list = json.dumps(api_json)
                sql_query = f"UPDATE taxonomy.taxa_reference SET metadata = '{_data_list}'"
            # else:
            #     sql_query = "UPDATE taxonomy.taxa_reference SET metadata = NULL"
                sql_query += f" WHERE id_taxonref = {_selecteditem.id_taxonref}"
                self.db.exec(sql_query)
                #update the value metadata from the selecteditem
                _selecteditem.api_score = len(api_json)   
                self.tlview_taxonref.repaint()         
        else:
            self.button_reset.setEnabled(False)
            #manage json in live ! coming from the metadata_worker api_thread, one by one
            if selecteditem != _selecteditem:
                return        
            if self.metadata_worker.status == 0:
                return
            #fill the treeview with the dictionnary json
            self.PN_tlview_metadata.dict_db_properties[base] = api_json
            self.PN_tlview_metadata.refresh()
            if get_str_value(api_json["name"]) != '':
                _selecteditem.api_score +=1
            self.tlview_taxonref.repaint()
        return
    

        
### MANAGE buttons
    def set_enabled_buttons(self):
        
        # set any button to enabled = False
        self.window.pushButtonAdd.setEnabled(False)
        self.window.pushButtonEdit.setEnabled(False)
        self.window.pushButtonDel.setEnabled(False)
        self.window.pushButtonMergeChilds.setEnabled(False)
        self.window.button_addNames.setEnabled(False)
        self.window.button_editNames.setEnabled(False)
        self.window.button_delNames.setEnabled(False)
        self.window.buttonBox_metadata.setEnabled(False)
        self.window.group_button.setEnabled(False)
        self.rank_msg.setText('< no selection >')
        
        # check if a taxon is selected
        selected_taxa = self.tlview_taxonref.model().data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selected_taxa is None:
            return
        elif not hasattr(selected_taxa, 'idtaxonref'):
            return
        elif selected_taxa.idtaxonref == 0:
            return
        #if a taxon is selected....
        self.window.pushButtonAdd.setEnabled(True)
        self.window.buttonBox_metadata.setEnabled(True)
        self.window.group_button.setEnabled(True)

        #count childs (if exist) and set message for selected taxon
        child_count = self.tlview_taxonref.model().rowCount(self.tlview_taxonref.currentIndex())
        if child_count == 0:
            child_count = ''
        elif child_count == 1:
            child_count = ' (' + str(child_count) + " taxon)"
        else:
            child_count = ' (' + str(child_count) + " taxa)"
        self.rank_msg.setText("Selected: " + selected_taxa.rank_name + " : " + selected_taxa.taxonref + child_count)

        # check if a synonym is selected in the names tab, and set enabled buttons to add/remove
        value = False
        try:
            if self.PN_tlview_names.currentIndex().parent().isValid():
                value = self.PN_tlview_names.currentIndex().parent().data() != 'Autonyms'
        except Exception:
            value = False
        self.window.pushButtonEdit.setEnabled(value)
        self.window.pushButtonDel.setEnabled(value)

        # check if a childs item is selected in the hierarchy, and set enabled buttons
        id_taxonref = None
        try:
            id_taxonref = self.trView_hierarchy_selecteditem().idtaxonref

            #id_taxonref = int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
        except Exception:
            pass
        value = id_taxonref is not None
        self.window.pushButtonMergeChilds.setEnabled(value)
        self.window.button_addNames.setEnabled(value)
        self.window.button_delNames.setEnabled(value)
        self.window.button_editNames.setEnabled(value)

    def button_addNames_click(self):
        selecteditem = self.trView_hierarchy_selecteditem()
        #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem is None: 
            return
            
        win = PN_add_taxaname(selecteditem, self.group_idrank())
        win.apply_signal.connect(self.apply_edit)
        win.show()

    def button_editNames_click(self):
        selecteditem = self.trView_hierarchy_selecteditem()
        #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem is None:
            return
        win = PN_edit_taxaname(selecteditem, self.group_idrank())
        win.apply_signal.connect(self.apply_edit)
        win.show()
    
    def apply_edit(self, ls_dict_tosave):
    #call by the PN_add_taxaname or PN_edit_taxaname windows events when an update/add was done
        if not isinstance(ls_dict_tosave, list):
            ls_dict_tosave = [ls_dict_tosave]
        ls_item_updated = []
        for dict_tosave in ls_dict_tosave:
            ls_item_updated += self.database_save_taxon(dict_tosave)

        if ls_item_updated:
            self.sender().refresh(ls_item_updated)
            self.tlview_taxonref_refresh(ls_item_updated)

    def tlview_taxonref_refresh(self, tab_items):
        grouped_idrank = self.group_idrank()
        model = self.tlview_taxonref.model()
        #set the id_parent to grouped_idrank and refresh only visible items
        first_item = None
        for item in tab_items:
            if item.id_rank == grouped_idrank:
                item.id_parent = None
            elif item.id_rank < 21:
                continue
            model.refresh(item)
            if not first_item: #save the first item for selection
                first_item = item
        #re-initialise the current index to None to fire the event
        self.tlview_taxonref.setCurrentIndex(QModelIndex())
        #get the index of the first updated item
        item = model.getNode (first_item.idtaxonref)
        index = model.indexFromTreeItem(item)
        self.tlview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
        #repaint the tlview_taxonref
        self.tlview_taxonref.repaint()


    def database_save_taxon(self, dict_tosave):
        #save a taxon in the database from a dictionnary :
        #dict_tosave = {"idtaxonref":integer, "basename":text, "authors":text, "idparent":integer, "published":boolean, "idrank" :integer}
        #and return a list of PNTaxa updated (PNTaxa1, PNTaxa2,...) with id_parent = self.group_idrank()
        code_error =''
        msg = ''
        idtaxonref = dict_tosave["idtaxonref"]
        basename = dict_tosave["basename"].strip().lower()
        published = dict_tosave["published"]
        authors = dict_tosave["authors"].strip()
        idrank = dict_tosave["idrank"]
        if not idrank:
            idrank = 'NULL'
        _parentname = dict_tosave.get("parentname", None)
        _idparent = dict_tosave.get("idparent", None)
        #create the from_query depending if parentname/id_parent are present into the dictionnayr dict_tosave
        if _parentname is not None:# get the id_parent from the parentname (to add taxon)
            _parentname = _parentname.strip().lower()
            sql_from = f"""(SELECT 
                                (taxonomy.pn_taxa_edit ({idtaxonref}, taxa.basename, taxa.authors, taxa.id_parent, taxa.id_rank, TRUE)).* 
                            FROM
                                (
                                    SELECT 
                                        '{basename}' AS basename, 
                                        '{authors}' AS authors, 
                                        {idrank} as id_rank, 
                                        a.id_taxonref AS id_parent
                                    FROM
                                        taxonomy.taxa_reference a
                                    WHERE 
                                        a.basename ='{_parentname}'
                                ) taxa
                            ) as result
                        """
        elif _idparent:
            sql_from = f"""taxonomy.pn_taxa_edit ({idtaxonref}, '{basename}', '{authors}', {_idparent}, {idrank}, {published})"""
        else:
            return
        #manage the id_parent field
        #field_idparent = f", taxonomy.pn_taxa_getparent(id_parent, {self.group_idrank()}) AS id_parent"
        #create the final query
        sql_query = f"""
                    SELECT 
                        id_taxonref, 
                        taxaname,
                        coalesce(authors,'') as authors, 
                        id_rank,
                        taxonomy.pn_taxa_getparent(id_parent, {self.group_idrank()}) AS id_parent
                    FROM
                        {sql_from}   
        """
    
        #print (sql_query)
        #execute query
        result = self.db.exec (sql_query)
        code_error = result.lastError().nativeErrorCode ()
        if len(code_error) == 0:#add a PNTaxa if save without errors
            updated_datas = []
            while result.next():
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                result.value("id_rank"), published)
                item.id_parent = result.value("id_parent")
                updated_datas.append(item)
            return updated_datas
        else:
            msg = postgres_error(result.lastError())
        QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return []


    def button_delNames_click(self):
        selecteditem = self.trView_hierarchy_selecteditem()
        if selecteditem is None:
            return
        # message to be display first (question, Yes or Not)
        msg = f"The Taxon: {selecteditem.taxonref}"
        msg += "\nincluding children and synonyms is about to be permanently deleted"
        msg += "\nAre you sure to proceed ?"
        result = QtWidgets.QMessageBox.question(
            None, "Delete a taxon", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
            # execute the suppression
        sql_query = self.sql_taxa_delete_reference(selecteditem.id_taxonref, True)
        result = self.db.exec(sql_query)
        if len(result.lastError().nativeErrorCode()) == 0:
            # refresh the model after deleting the selected taxa and childs in dbase (returns any id_taxonref deleted)
            while result.next():
                #self.tlview_taxonref.model().sourceModel().delete(result.value("id_taxonref"))
                item = self.tlview_taxonref.model().getItem(result.value("id_taxonref"))
                if item:
                    self.tlview_taxonref.model().removeItem(item)
            self.tlviews_refresh(selecteditem.id_taxonref)
            self.combo_taxa_deletedItem(selecteditem)
        else:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return

    def button_MergeChilds_click(self):
        # get the selectedItem
        try:
            selecteditem = self.trView_hierarchy_selecteditem()
            win = PN_merge_taxaname(selecteditem)
            win.show()

            #refresh the tlview_taxonref (win.main_tableView)
            if win.updated:
                # deleted the merge taxa
                self.tlview_taxonref.model().sourceModel().delete(selecteditem.idtaxonref)
                # update the sub-taxas properties
                for item in win.updated_datas:
                    self.tlview_taxonref.model().sourceModel().refresh(item)
            # refresh the entire view
                self.tlview_taxonref.model().sourceModel().refresh()
                id_taxonref = win.selected_idtaxonref
                # refresh the view
                self.tlviews_refresh(id_taxonref)
        except Exception:
            return

    def button_identity_apply_click(self):
        self.buttonbox_identity.setEnabled(False)
        self.trview_identity_apply()

    def button_identity_cancel_click(self):
    # message to be display first (question, Yes or Not)
        msg = "Are you sure you want to undo all changes and restore from the database ?"
        result = QtWidgets.QMessageBox.question(
            None, "Cancel properties", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
        self.PN_trview_identity.refresh()

    # def button_MoveChilds_click(self):
    #     try:
    #         selecteditem = self.trView_hierarchy_selecteditem()
    #         win = PN_move_taxaname(selecteditem, False)
    #         win.show()
    #         if win.updated:
    #             # update the sub-taxas properties
    #             for item in win.updated_datas:
    #                 self.tlview_taxonref.model().sourceModel().refresh(item)
    #         # refresh the view
    #             self.tlviews_refresh(selecteditem.idtaxonref)
    #     except Exception:
    #         return


    # def button_addChilds_click(self):
    #     #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
    #     try:
    #         row_index = self.tlview_taxonref.currentIndex()
    #         selecteditem = self.tlview_taxonref.model().data(row_index, Qt.UserRole)
    #         # int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
    #         id_taxonref = selecteditem.idtaxonref
    #         win = PN_edit_taxaname(id_taxonref, 1)
    #         win.show()

    #         if win.updated:
    #             for item in win.updated_datas:
    #                 # refresh the data
    #                 self.tlview_taxonref.model().sourceModel().refresh(item)

    #         # refresh the view
    #             self.tlviews_refresh(id_taxonref)
    #     except Exception:
    #         return

    def button_clean_click(self):
        self.window.lineEdit_searchtaxon.setText("")
        self.PN_trview_filter.setModel(None)
        self.tlview_taxonref_setData()

    def button_metadata_refresh(self):
        # get the selectedItem
        selecteditem = self.tlview_taxonref.model().data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        self.button_reset.setEnabled(False)
        if self.metadata_worker.status == 1:
            self.metadata_worker.kill()
            while self.metadata_worker.isRunning():                
                time.sleep(0.5)
        selecteditem.api_score =0
        self.metadata_worker.PNTaxa_model = selecteditem
        self.PN_tlview_metadata.dict_db_properties = {}
        self.metadata_worker.start()
        self.tlview_taxonref.repaint()


    def button_add_synonym(self):
        # get the selectedItem
        selecteditem = self.tlview_taxonref.model().data(
            self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem.idtaxonref == 0:
            return
        if self.PN_tlview_names.currentIndex().parent().isValid():
            category = self.PN_tlview_names.currentIndex().parent().data()
        else:
            category = self.PN_tlview_names.currentIndex().data()
        new_synonym = PNSynonym(None, selecteditem.taxonref, selecteditem.idtaxonref,category)
        class_newname = PN_edit_synonym(new_synonym)
        class_newname.show()
        self.trview_names_setdata(selecteditem)

    def button_edit_synonym(self):
        # get the selectedItem
        selecteditem = self.tlview_taxonref.model().data(
            self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem.idtaxonref == 0:
            return
        _syno = self.PN_tlview_names.currentIndex().data()
        category = self.PN_tlview_names.currentIndex().parent().data()
        if not _syno or not category:
            return
        edit_synonym = PNSynonym(_syno, selecteditem.taxonref, selecteditem.idtaxonref,category)
        #edit_synonym.id_synonym = 1
        class_newname = PN_edit_synonym(edit_synonym)
        class_newname.show()
        self.trview_names_setdata(selecteditem)


    def button_delete_synonym(self):
        selecteditem = self.tlview_taxonref.model().data(
            self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem.idtaxonref == 0:
            return
        if not self.PN_tlview_names.currentIndex().parent().isValid():
            return
        _currentsynonym = self.PN_tlview_names.currentIndex().data()
        if _currentsynonym is None:
            return
        
        # message to be display first (question, Yes or Not)
        msg = f"Are you sure to permanently delete this synonym {_currentsynonym}?"
        result = QtWidgets.QMessageBox.question(
            None, "Delete a synonym", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
            # execute the suppression
        sql_query = self.sql_taxa_delete_synonym(_currentsynonym)
        result = self.db.exec(sql_query)
        if len(result.lastError().nativeErrorCode()) == 0:
            self.trview_names_setdata(selecteditem)
        else:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    #set the style
    with open("ui/Diffnes.qss", "r") as f:
        #with open("Photoxo.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)

    #open the mainwindow
    window = MainWindow()
    window.show()
    app.exec()