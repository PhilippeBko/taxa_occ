########################################
##imports
import sys
import re
import json
import time

from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QModelIndex

########################################
from models.api_thread import TaxRefThread, API_ENDEMIA
from models.taxa_model import (TableModel, PNTaxa,  PN_add_taxaname, PN_edit_taxaname, PN_move_taxaname, PNSynonym, PN_edit_synonym)
from core.widgets import PN_JsonQTreeView, PN_DatabaseConnect, PN_TaxaQTreeView
from core.functions import (get_dict_from_species, get_str_value, postgres_error, list_db_properties, get_dict_rank_value)
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

    # setting the main_tableView
        model_tableview = TableModel()
        proxyModel = QSortFilterProxyModel()
        proxyModel.setSourceModel(model_tableview)
        self.tlview_taxonref = self.window.main_tableView
        self.tlview_taxonref.setModel(proxyModel)
        self.tlview_taxonref.setSortingEnabled(True)
        self.tlview_taxonref.sortByColumn(0, Qt.AscendingOrder)
        selection = self.tlview_taxonref.selectionModel()
        selection.selectionChanged.connect(self.tlview_taxonref_click)
        self.tlview_taxonref.doubleClicked.connect(self.tlview_taxonref_dblclick)
        selection.currentChanged.connect(self.tlview_taxonref_before_clickitem)
        
    # setting the properties treeview
        self.trView_hierarchy = PN_TaxaQTreeView ()
        self.trView_hierarchy.doubleClicked.connect(self.trView_hierarchy_dblclick)
        self.window.trView_hierarchy_Layout.insertWidget(0,self.trView_hierarchy)

    # setting the combos
        self.combo_taxa = self.window.combo_taxa
        self.combo_taxa.addItem('Any taxa')
        self.combo_taxa.setItemData(0, PNTaxa(0, 'Any taxa', '', 0), role=Qt.UserRole)
        self.combo_taxa.setCurrentIndex(0)

        self.combo_rank = self.window.combo_rank
        rank_filter = ['Any rank', 'Classis', 'Subclassis', 'Order', 'Family', 'Genus','Species', 'Subspecies', 'Variety', 'Hybrid']
        for x in rank_filter:
            self.combo_rank.addItem(x)

        self.combo_status = self.window.combo_status
        self.combo_status.addItem("Any status")
        for x in list_db_properties["new caledonia"]["status"]["items"]:
            self.combo_status.addItem(x)
        self.combo_status.addItem("Unknown")
        
        self.combo_habit = self.window.combo_habit
        self.combo_habit.addItem("Any habit")
        for x in list_db_properties["habit"].keys():
            self.combo_habit.addItem(x.title())
        self.combo_habit.addItem("Unknown")

    # setting the linedit_search
        self.lineEdit_search = self.window.lineEdit_search
    # setting the buttons
        self.button_reset = self.window.buttonBox_metadata.button(QtWidgets.QDialogButtonBox.Reset)
        self.buttonbox_identity = self.window.buttonBox_identity
        button_cancel = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Cancel)
        button_apply = self.buttonbox_identity.button(QtWidgets.QDialogButtonBox.Apply)

    # setting the buttons and linedit slots
        #self.window.pushButtonRefresh.clicked.connect(self.button_metadata_refresh)
        self.window.button_clean.clicked.connect(self.button_clean_click)    
        self.window.pushButtonAdd.clicked.connect(self.button_add_synonym)
        self.window.pushButtonEdit.clicked.connect(self.button_edit_synonym)
        self.window.pushButtonDel.clicked.connect(self.button_delete_synonym)
        self.window.button_addNames.clicked.connect(self.button_addNames_click)   
        self.window.button_editNames.clicked.connect(self.button_editNames_click)
        self.window.button_delNames.clicked.connect(self.button_delNames_click)
        self.window.pushButtonMergeChilds.clicked.connect(self.button_MergeChilds_click)
        self.window.pushButtonMoveChilds.clicked.connect(self.button_MoveChilds_click)
        self.button_reset.clicked.connect (self.button_metadata_refresh)
        button_cancel.clicked.connect (self.button_identity_cancel_click)
        button_apply.clicked.connect(self.button_identity_apply_click)
        self.lineEdit_search.returnPressed.connect(self.tlview_taxonref_setData)
        self.combo_habit.activated.connect(self.tlview_taxonref_setData)
        self.combo_status.activated.connect(self.tlview_taxonref_setData)
        self.combo_rank.activated.connect(self.tlview_taxonref_setData)
        self.combo_taxa.currentIndexChanged.connect(self.tlview_taxonref_setData)
        #self.tab_data = self.window.tab_data
    #set the toolbox icon style
        self.window.toolBox.setItemText(0, "< no selection >")
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(51))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))
        self.window.toolBox.currentChanged.connect(self.toolbox_click)   

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
    #add permanent label       
        self.rank_msg = QtWidgets.QLabel()
        self.rank_msg.setGeometry(100, 40, 30, 25)
        self.rank_msg.setVisible(True)
        self.window.statusbar.addPermanentWidget(self.rank_msg)
    #connect to the database, exit if not open
        connected_indicator = PN_DatabaseConnect()
        self.window.statusBar().addPermanentWidget(connected_indicator)
        connected_indicator.open()      
        if not connected_indicator.dbopen:
            return
        self.db = connected_indicator.db
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
    #connect signals
        self.PN_tlview_names.changed_signal.connect(self.trview_names_changed)
        self.PN_trview_identity.changed_signal.connect(self.trview_identity_changed)        
    #connect the thread
        self.metadata_worker = TaxRefThread(app)
        self.metadata_worker.Result_Signal.connect(self.trview_metadata_setDataAPI)        
    #initialize the tlview_taxonref (list of taxa)
        self.tlview_taxonref_setData()
        self.window.pushButton.clicked.connect(self.test_endemia)

    def theme_menu(self, item):
        self.window.themes_button.setText(item)
        qss_file =  "ui/" + item + ".qss"
        with open(qss_file, "r") as f:
            app.setStyleSheet(f.read())

    def test_endemia(self):
        with open("ui/Combinear.qss", "r") as f:
            #with open("Photoxo.qss", "r") as f:
            _style = f.read()
            app.setStyleSheet(_style)
        return
    

        sql_tmp = "SELECT id_taxonref, taxaname, authors, id_rank FROM taxonomy.taxa_names WHERE id_rank = 21"
        query = self.db.exec(sql_tmp)
        while query.next():
            idtaxonref = query.value("id_taxonref")
            myPNTaxa = PNTaxa(idtaxonref, query.value("taxaname"), query.value("authors"),query.value("id_rank"))
            _classeAPI = API_ENDEMIA(myPNTaxa)
            _response = _classeAPI.get_metadata()
            _id = None
            if _response:
                _id = _response['id']
                sql_update = f"UPDATE taxonomy.taxa_reference SET id_endemia = {_id} WHERE id_taxonref = {idtaxonref}"
            else:
                sql_update = f"UPDATE taxonomy.taxa_reference SET id_endemia = NULL WHERE id_taxonref = {idtaxonref}"
            print (idtaxonref, _id)
            #QtSql.QSqlQuery(sql_update)
            self.db.exec(sql_update)
        print ("end")

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
        separator = " WHERE "
        if self.combo_rank.currentIndex() > 0:
            _idrank = get_dict_rank_value(self.combo_rank.currentText(), 'id_rank')
            sql_where += separator + f"a.id_rank = {_idrank}"
            separator = " AND "
        # sql_where from the self.combo_status
        if self.combo_status.currentIndex() > 0:
            key_status = self.combo_status.currentText()
            if key_status == 'Unknown':
                _prop = "(properties  -> 'new caledonia' ? 'status') IS NULL"
            else:
                _prop = "(properties  @> '{%new caledonia%:{%status%:%Endemic%}}')"
                _prop = _prop.replace('%', chr(34))
                _prop = _prop.replace('Endemic', key_status)
            sql_where += separator + _prop
            separator = " AND "
        # sql_where from the combo_habit
        if self.combo_habit.currentIndex() > 0:
            key_habit = self.combo_habit.currentText().lower()
            if key_habit == 'unknown':
                _prop = "(properties->'habit') IS NULL"
            else:
                _prop = "(properties  @> '{%habit%:{%tree%:%True%}}')"
                _prop = _prop.replace('%', chr(34))
                _prop = _prop.replace('tree', key_habit)
            sql_where += separator + _prop
            separator = " AND "
        # sql_where from the lineEdit_search
        txt_search = self.lineEdit_search.text()
        txt_search = re.sub(r'[\*\%]', '', txt_search)
        if len(txt_search) > 0:
            sql_where = sql_where + separator
            sql_where += f"\na.id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_searchname('%{txt_search}%') GROUP by id_taxonref)"
        
    # add a filter for childs if idtaxonref is not None
        sql_join = ''
        index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(index, role=Qt.UserRole).idtaxonref
        if idtaxonref > 0:
            sql_join = f"\nINNER JOIN taxonomy.pn_taxa_childs ({idtaxonref},True) b ON a.id_taxonref = b.id_taxonref"
    
    #set the final sql_query, including sql_where and sql_join
        sql_query = f"""
                    SELECT
                        a.taxaname::text, 
                        a.authors, 
                        a.id_rank, 
                        a.id_taxonref, 
                        a.published, 
                        score_api
                    FROM 
                        taxonomy.taxa_names a
                    LEFT JOIN 
                        (SELECT 
                            id_taxonref, 
                            count(id_taxonref) as score_api
                         FROM
                            (SELECT 
                                id_taxonref, 
                                jsonb_each(metadata) 
                            FROM 
                                taxonomy.taxa_reference 
                            WHERE 
                                metadata IS NOT NULL
                            ) z
                        GROUP BY 
                            id_taxonref
                        ) c
                    ON a.id_taxonref = c.id_taxonref
                    {sql_join}
                    {sql_where}
                    ORDER BY a.taxaname
                    """
        # return the sql_query
        return sql_query

    def tlviews_clear(self):
        # clear the contents of any tblview
        self.PN_trview_identity.setModel(None) #.model().setRowCount(0)
        self.PN_tlview_metadata.setModel(None)
        self.trView_hierarchy.setModel(None) 
        self.set_enabled_buttons()

    def tlviews_refresh(self, idtaxonref=0):
        # record the current selected row
        currentrow = self.tlview_taxonref.currentIndex().row()
        # refresh the view
        self.tlview_taxonref.model().sourceModel().refresh()
        # get the row (id_taxonref) in data of the sourceModel
        row = self.tlview_taxonref.model().sourceModel().row_idtaxonref(
            idtaxonref)  # item.idtaxonref) ##id_taxonref)
        if row == -1:
            row = currentrow
        row = max(0, min(row, self.tlview_taxonref.model().rowCount() - 1))
        # get the index and obtain the source map index from the model itself
        index = self.tlview_taxonref.model().sourceModel().index(row, 0)
        index = self.tlview_taxonref.model().mapFromSource(index)
        self.tlview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
    
    def combo_taxa_selectedItem(self, selecteditem):
        # select the selecteditem in the combo_taxa or create if not exist
        index = -1
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=Qt.UserRole).idtaxonref == selecteditem.idtaxonref:
                index = i
        if index == -1:
            self.combo_taxa.addItem(selecteditem.taxonref)
            index = self.combo_taxa.count() - 1
            self.combo_taxa.setItemData(index, selecteditem, role=Qt.UserRole)
        self.combo_taxa.setCurrentIndex(index)

    def combo_taxa_deletedItem(self, selecteditem):
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

    def trview_names_changed(self, changed):
        value = False
        try:
            if self.PN_tlview_names.currentIndex().parent().isValid():
                value = self.PN_tlview_names.currentIndex().data() is not None
        except Exception:
            value = False
        self.window.pushButtonEdit.setEnabled(value)
        self.window.pushButtonDel.setEnabled(value)
        self.set_enabled_buttons()

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
        dict_db_properties = self.PN_trview_identity.dict_db_properties
    
    #check that dictionnaries identity are different to proceed to an update in the taxa_reference table
        if dict_db_properties["identity"] != dict_user_properties["identity"]:
            _name = dict_user_properties["identity"]["name"]
            _authors = dict_user_properties["identity"]["authors"]
            _published = dict_user_properties["identity"]["published"]
            #use the internal db function to apply and propage modif to childs
            sql_query =f"""
                        SELECT 
                            id_taxonref, 
                            taxaname, 
                            coalesce(authors,'') as authors, 
                            id_rank
                        FROM 
                            taxonomy.pn_taxa_edit ({id_taxonref}, '{_name}', '{_authors}', NULL, NULL, {_published}, True)"
                       """
            result = self.db.exec (sql_query)
            code_error = result.lastError().nativeErrorCode ()
            if len(code_error) == 0:
                tab_updated_datas =[]
            #refresh the taxa model of the tlview_taxonref tableview
                while result.next():
                    _ispublished = (dict_user_properties["identity"]["published"]== 'True')                
                    item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                    result.value("id_rank"),_ispublished)
                    tab_updated_datas.append(item)
                #emit a signal with tab_updated_datas (= tab of changed PNTaxa's)
                self.tlview_taxonref_refresh(tab_updated_datas)
            else:
                msg = postgres_error(result.lastError())
                QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        
    #create a sub dictionnaries (a copy without the key identity) to compare only json_properties
        sub_dict_db_properties = dict_db_properties.copy()
        del sub_dict_db_properties["identity"]
        sub_dict_user_properties = dict_user_properties.copy()
        del sub_dict_user_properties["identity"]
        #if sub_dictionnaries are different, proceed to update with only non-null values
        if sub_dict_db_properties != sub_dict_user_properties:
            tab_result = {}
            for key, value in sub_dict_user_properties.items():
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
            sql_query += f" WHERE id_taxonref = {id_taxonref}"

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
 
    def tlview_taxonref_before_clickitem(self, current_index, previous_index):
    #check and alert if some properties changed before sected an other item
        if self.buttonbox_identity.isEnabled():
            msg = "Some properties have been changed, save the changes ?"
            result = QtWidgets.QMessageBox.question(None, "Cancel properties", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            self.buttonbox_identity.setEnabled(False)
            if result == QtWidgets.QMessageBox.No:
                self.buttonbox_identity.setEnabled(False)
                return
            else:
                self.trview_identity_apply()
                self.buttonbox_identity.setEnabled(False) #do not move before PN_trview_identity.apply() (see tlview_taxonref_refresh)
        return

    def tlview_taxonref_click(self):
    #set the hierarchy, names, metadata and properties of the selected taxa
        # clear lists
        self.tlviews_clear()
        # get the selectedItem
        selecteditem = self.tlview_taxonref.model().data( self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem is None:
            return
        self.PN_trview_identity.setData(selecteditem.json_properties)
        self.PN_trview_identity.id = selecteditem.idtaxonref
        #self.PN_tlview_metadata.setData (self.trview_metadata_setData(selecteditem))
        self.PN_tlview_metadata.setData (selecteditem.json_metadata)
        self.trview_names_setdata(selecteditem)
        #set the treetaxonomy hierarchy
        if self.trView_hierarchy.model() is None :
            self.trView_hierarchy.setdata (selecteditem)
            self.set_enabled_buttons()
            selection = self.trView_hierarchy.selectionModel()
            selection.selectionChanged.connect(self.set_enabled_buttons)
        #self.tab_data_changed ()
       
    def tlview_taxonref_dblclick(self):
        # Select or insert the selecteditem into the combo_taxa combobox for shortcut
        selecteditem = self.tlview_taxonref.model().data(
            self.tlview_taxonref.currentIndex(), Qt.UserRole)
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
            data.append(item)
            i += 1
        # reset the model to the tableview for refresh
        self.tlview_taxonref.model().sourceModel().resetdata(data)
        self.tlview_taxonref.resizeColumnsToContents()
        # Display row count within the statusbar
        self.window.statusbar.showMessage(str(i) + " row(s)")
        selected_index = self.tlview_taxonref.model().index(row,0)
        self.tlview_taxonref.selectionModel().setCurrentIndex(
                selected_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)

    def tlview_taxonref_refresh(self, tab_items):
        selecteditem = self.tlview_taxonref.model().data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        for item in tab_items:
            self.tlview_taxonref.model().sourceModel().refresh(item)
        self.tlview_taxonref.model().sourceModel().refresh()
        #only refresh tlview_taxon when buttonbox_identity is not enabled (no save in progress, see tlview_taxonref_before_clickitem and button_identity_apply_click)
        if self.buttonbox_identity.isEnabled():
            return
        self.tlviews_refresh(selecteditem.idtaxonref)

    
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
        
        # set buttons to enabled = False
        self.window.pushButtonAdd.setEnabled(False)
        self.window.pushButtonEdit.setEnabled(False)
        self.window.pushButtonDel.setEnabled(False)
        self.window.pushButtonMergeChilds.setEnabled(False)
        self.window.button_addNames.setEnabled(False)
        self.window.button_editNames.setEnabled(False)
        self.window.button_delNames.setEnabled(False)
        self.rank_msg.setText('< no selection >')
        self.window.toolBox.setItemText(0, self.rank_msg.text())
        
        # check if a taxa is selected
        selected_taxa = self.tlview_taxonref.model().data(self.tlview_taxonref.currentIndex(), Qt.UserRole)
        if selected_taxa is None:
            return
        elif selected_taxa.idtaxonref == 0:
            return
        self.rank_msg.setText(selected_taxa.rank_name + " : " + selected_taxa.taxonref)
        self.window.toolBox.setItemText(0, selected_taxa.rank_name)
        self.window.pushButtonAdd.setEnabled(True)
        # check if a synonym is selected
        value = False
        try:
            if self.PN_tlview_names.currentIndex().parent().isValid():
                value = self.PN_tlview_names.currentIndex().parent().data() != 'Autonyms'

        except Exception:
            value = False
        self.window.pushButtonEdit.setEnabled(value)
        self.window.pushButtonDel.setEnabled(value)

        # check if a childs item is selected in the hierarchy
        id_taxonref = None
        try:
            id_taxonref = int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
        except Exception:
            pass
        value = id_taxonref is not None
        self.window.pushButtonMergeChilds.setEnabled(value)
        self.window.button_addNames.setEnabled(value)
        self.window.button_delNames.setEnabled(value)
        self.window.button_editNames.setEnabled(value)

    def button_addNames_click(self):
        selecteditem = self.trView_hierarchy_selecteditem()
        if selecteditem is None: 
            return
            #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
        win = PN_add_taxaname(selecteditem)
        win.apply_signal.connect(self.tlview_taxonref_refresh)
        win.show()

    def button_editNames_click(self):
        try:
            selecteditem = self.trView_hierarchy_selecteditem()
            if selecteditem is None:
                return
                #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
            win = PN_edit_taxaname(selecteditem)
            win.apply_signal.connect(self.tlview_taxonref_refresh)
            win.show()
        except Exception:
            return

    def button_delNames_click(self):
        selecteditem = self.trView_hierarchy_selecteditem()
        if selecteditem is None:
            return
        # message to be display first (question, Yes or Not)

        msg = f"The Taxa: {selecteditem.taxonref}"
        msg += "\nincluding children and synonyms is about to be permanently deleted"
        msg += "\nAre you sure to proceed ?"
        result = QtWidgets.QMessageBox.question(
            None, "Delete a taxa", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
            # execute the suppression
        sql_query = self.sql_taxa_delete_reference(selecteditem.id_taxonref, True)
        result = self.db.exec(sql_query)
        if len(result.lastError().nativeErrorCode()) == 0:
            # refresh the model after deleting the selected taxa and childs in dbase (returns any id_taxonref deleted)
            while result.next():
                self.tlview_taxonref.model().sourceModel().delete(result.value("id_taxonref"))
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
            win = PN_move_taxaname(selecteditem, True)
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
                id_taxonref = win.selecteditem.idtaxonref
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


    def button_MoveChilds_click(self):
        try:
            selecteditem = self.trView_hierarchy_selecteditem()
            win = PN_move_taxaname(selecteditem, False)
            win.show()
            if win.updated:
                # update the sub-taxas properties
                for item in win.updated_datas:
                    self.tlview_taxonref.model().sourceModel().refresh(item)
            # refresh the view
                self.tlviews_refresh(selecteditem.idtaxonref)
        except Exception:
            return


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
        self.combo_taxa.setCurrentIndex(0)
        self.combo_rank.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.combo_habit.setCurrentIndex(0)
        self.lineEdit_search.setText('')
        self.tlview_taxonref_setData()

    def button_metadata_refresh(self):
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