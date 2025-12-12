########################################
##imports
import os
import sys
import re
import json
import time
########################################
from PyQt5 import uic, QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QModelIndex   #, QSortFilterProxyModel
########################################
#from models.api_thread import API_Thread #, API_ENDEMIA
from models.taxa_model import (PNTaxa_searchAPI, PNTaxa_TreeModel, PNTaxa,  PNTaxa_with_Score, PNTaxa_QTreeView, PNTaxa_add, PNTaxa_edit, PNTaxa_merge, PNSynonym, PNSynonym_edit)
from core.widgets import PN_JsonQTreeView, PN_DatabaseConnect, LinkDelegate
from core.functions import (list_db_properties, get_dict_from_species, postgres_error, get_dict_rank_value)
########################################, get_str_value



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


#class MetadataDelegateWithAuthorCheck is used to highlight the authors name in red if it does not match the current authors name
#surcharging the LinkDelegate used to highlight the hyperlinks in the metadata treeview
class MetadataDelegateWithAuthorCheck(LinkDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._authors_name = None

    def set_authors_name(self, name):
        self._authors_name = name

    def paint(self, painter, option, index):
        # Apply the superclass's paint method (web links)
        super().paint(painter, option, index)

        # Additional logic for column 1 and key
        if index.column() == 1:
            key = index.sibling(index.row(), 0).data(Qt.DisplayRole)
            value = index.data(Qt.DisplayRole)
            if key == "Authors" and value != self._authors_name:
                # paint foreground in red if authors are different
                option.palette.setColor(option.palette.Text, QtGui.QColor("red"))
                super().paint(painter, option, index)  # repaint in red
            elif value == 'No results':
                # paint foreground in red if authors are different
                option.palette.setColor(option.palette.Text, QtGui.QColor("red"))
                super().paint(painter, option, index)  # repaint in red

##The MainWindow load the ui interface to navigate and edit taxaname###
class MainWindow(QtWidgets.QMainWindow):
    
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = uic.loadUi("ui/taxanames.ui")
        self.window.splitter.setSizes([0, 1])


    # setting the main_treeView
        self.trview_taxonref = self.window.main_treeView
        self.trview_taxonref.header().setSortIndicator(0, Qt.AscendingOrder)
        # connect the signal to the slot
        self.trview_taxonref.header().sortIndicatorChanged.connect(self.on_header_clicked)
        self.trview_taxonref.setModel(PNTaxa_TreeModel())
        self.trview_taxonref.model().refresh_signal.connect(self.refresh_label_count)
        self.trview_taxonref.selectionModel().selectionChanged.connect(self.tlview_taxonref_click)
        self.trview_taxonref.doubleClicked.connect(self.tlview_taxonref_dblclick)

    # setting the combo_taxa
        self.combo_taxa = self.window.combo_taxa
        self.combo_taxa.addItem('All names')
        self.combo_taxa.setItemData(0, PNTaxa(0, 'All names', '', 0), role=Qt.UserRole)
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
        self.window.button_MergeNames.clicked.connect(self.button_MergeChilds_click)
        self.window.button_showFilter.toggled.connect(self.trView_filter_setVisible)
        self.button_reset.clicked.connect (self.button_metadata_refresh)
        button_cancel.clicked.connect (self.button_identity_cancel_click)
        button_apply.clicked.connect(self.button_identity_apply_click)
        self.window.lineEdit_searchtaxon.returnPressed.connect(self.tlview_taxonref_setData)
        self.combo_taxa.currentIndexChanged.connect(self.tlview_taxonref_setData)

        self.window.checkBox_published.setCheckState(Qt.PartiallyChecked)
        self.window.checkBox_accepted.setCheckState(Qt.PartiallyChecked)
        self.window.checkBox_withtaxa.setCheckState(Qt.PartiallyChecked)
        self.window.checkBox_published.stateChanged.connect(self.tlview_taxonref_refreshData)
        self.window.checkBox_accepted.stateChanged.connect(self.tlview_taxonref_refreshData)
        self.window.checkBox_withtaxa.stateChanged.connect(self.tlview_taxonref_refreshData)

    #     #set a special style for the checkboxes Accepted and Published
    #     _style = """
    #         QCheckBox::indicator:checked {
    #             background-color: rgb(0, 255, 0);
    #             border: 1px solid darkgreen;
    #         }
    #         QCheckBox::indicator:unchecked {
    #             background-color: rgb(255, 0, 0);
    #             border: 1px solid darkred;
    #         }
    #         QCheckBox::indicator:indeterminate {
    #             background-color: white;
    #             border: 1px solid #555;
    # }
    #     """
    #     self.window.checkBox_published.setStyleSheet(_style)
    #     self.window.checkBox_accepted.setStyleSheet(_style)          

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
        group_button = self.window.button_rankGroup
        group_menu = QtWidgets.QMenu()
        # create an exclusive action group for menu
        self.action_group = QtWidgets.QActionGroup(self)
        self.action_group.setExclusive(True)
        self.actions = []
        # set the list of items
        menu_items = ['Division', 'Classis', 'Subclassis', 'Order', 'Family', 'Genus']
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            action.setCheckable(True)
            self.action_group.addAction(action)  # Ajouter à l'action group
            self.actions.append(action)
            action.triggered.connect(lambda checked, item=item: self.group_menu_click(item))
            group_menu.addAction(action)
        #set the family as default selected item
        _selected_item = 4
        self.actions[_selected_item].setChecked(True)
        group_button.setText(menu_items[_selected_item])
        group_button.setMenu(group_menu)

    #set the theme menu
        theme_button = self.window.button_themes
        theme_button.setText("Diffnes")
        theme_menu = QtWidgets.QMenu()
        path_ui = os.path.join(os.path.dirname(__file__), "ui")
        menu_items = [os.path.splitext(f)[0] for f in os.listdir(path_ui) if f.endswith(".qss")]
        #menu_items = ["Adaptic", "Combinear", "Diffnes",  "Lightstyle", "Obit", "SpyBot", "Geoo"]
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            #action.setCheckable(True)
            action.triggered.connect(lambda checked, item=item: self.theme_menu(item))
            theme_menu.addAction(action)
        theme_button.setMenu(theme_menu)
        self.window.statusbar.addPermanentWidget(theme_button)
        
    #setting the hierarchical treeview
        self.trView_hierarchy = PNTaxa_QTreeView ()
        self.trView_hierarchy.doubleClicked.connect(self.trView_hierarchy_dblclick)
        selection = self.trView_hierarchy.selectionModel()
        selection.selectionChanged.connect(self.trView_hierarchy_click)
        
#self.trView_hierarchy.clicked.connect(self.tlview_taxonref_click)
        self.window.trView_hierarchy_Layout.insertWidget(0,self.trView_hierarchy)
    #connect the treeviews for properties (identity, metadata and names)
        self.PN_trview_identity = PN_JsonQTreeView ()
        self.PN_tlview_metadata = PN_JsonQTreeView ()
        self.PN_tlview_names = PN_JsonQTreeView ()
        self.PN_tlview_names.selectionModel().selectionChanged.connect(self.set_enabled_buttons)

    #insert the treeview in the three layout
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
                #if self.PN_trview_filter.model() is None:
        self.button_clean_setData()

        self.authors_delegate = MetadataDelegateWithAuthorCheck()
        self.PN_tlview_metadata.setItemDelegate(self.authors_delegate)

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
        self.metadata_worker = PNTaxa_searchAPI(app)
        self.metadata_worker.Result_Signal.connect(self.trview_metadata_setDataAPI)
    #set the APG options into self.combo_taxa
        sql_agp = "SELECT json_agg(DISTINCT a.clade) AS json_list FROM taxonomy.apg4 a WHERE clade IS NOT NULL;"
        query = self.db.exec(sql_agp)
        if query.next():
            result = query.value("json_list")
            lst = json.loads(result)
            for clade in lst:
                self.combo_taxa.addItem(f'AGP IV - {clade}')
                self.combo_taxa.setItemData(self.combo_taxa.count() - 1, PNTaxa(0, f'AGP IV - {clade}', '', 0), role=Qt.UserRole)               
    #initialize the trview_taxonref (list of taxa)
        self.tlview_taxonref_setData()


    def on_header_clicked(self, column):
    #event when the header is clicked to sort the trview_taxonref
        rootItem = None
        model = self.trview_taxonref.model()
        order = self.trview_taxonref.header().sortIndicatorOrder()
        if not model:
            return
        #get the parent Node
        selecteditem = model.data(self.trview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem:
            rootItem = model.getNode(selecteditem.id_parent)
        model.sortItems(column, order, rootItem)

    def trView_filter_setVisible(self, state):
        #set the visibility of the filter treeview
        if not state:
            # handle = self.window.splitter.handle(1)
            # handle.setEnabled(False)
            # handle.setStyleSheet("background: transparent;")
            #self.window.splitter.setVisible(True)
            self.window.splitter.setSizes([0, 1])
        else:
            #self.window.splitter.setVisible(True)
            # handle = self.window.splitter.handle(1)
            # handle.setEnabled(True)
            # handle.setStyleSheet("")
            #.window.splitter.setVisible(True)
            self.window.splitter.setSizes([300, 200])

    def theme_menu(self, item):
        #change the theme
        self.window.button_themes.setText(item)
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

    def sql_taxa_delete_reference(self, id_taxonref):
        #return a sql statement for deleting a reference name
        return f"SELECT taxonomy.pn_taxa_delete ({id_taxonref}) AS id_taxonref"

    def sql_taxa_get_names(self):
    #create a filter on taxa according to combo state and others filters (names)
        sql_where_taxa = ''
        tab_sql = ["a.id_rank >= 21"]
        nb_filter = 0
        #get the grouped id_rank
        idrankparent = self.group_idrank()

       #1) text filter: sql_where_taxa from the lineEdit_search
        txt_search = self.window.lineEdit_searchtaxon.text()
        txt_search = re.sub(r'[\*\%]', '', txt_search)
        if len(txt_search) > 0:
            sql_where_taxa = f"""\na.id_taxonref IN (
                             SELECT 
                                (taxonomy.pn_taxa_childs(id_taxonref, true)).id_taxonref id_taxonref 
                            FROM 
                                taxonomy.pn_taxa_searchname('%{txt_search}%') 
                            GROUP 
                                by id_taxonref)"""
            #will filter only display species and infraspecies
            sql_where_taxa = f"""\na.id_taxonref IN (
                             SELECT id_taxonref 
                            FROM 
                                taxonomy.pn_taxa_searchname('%{txt_search}%'))"""
            tab_sql.append(sql_where_taxa)
            nb_filter = 1
            
        #2) properties filter: sql_where_taxa from the PN_trview_filter (get the dict_user properties=
        tab_filter = self.PN_trview_filter.dict_user_properties()
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


        #3) ComboTaxa filter: add a filter for childs and parentsif idtaxonref is not None
        sql_join_taxa = ''
        clade_sql = ''
        base_taxa = 'all_taxa'
        index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(index, role=Qt.UserRole).idtaxonref
        if idtaxonref >0:
            sql_where_parents = f"WHERE id_taxonref IN (SELECT DISTINCT id_parent FROM taxa) OR id_taxonref = {idtaxonref} "
            sql_join_taxa = f"\nINNER JOIN taxonomy.pn_taxa_childs ({idtaxonref},True) b ON a.id_taxonref = b.id_taxonref"
        else:
            sql_where_parents = f"WHERE id_rank = {idrankparent}"
        
        #4) APG Filter: add a filter for APG clade
        if self.combo_taxa.currentText().startswith('AGP IV'):
            clade_sql = self.combo_taxa.currentText().split(' - ')[1]
            base_taxa = 'apg_taxa'
        
        # button filter style
        self.window.button_showFilter.setStyleSheet(
                "color: rgb(0, 55, 217);" if nb_filter else ""
        )
        #5) create query: set the final sql_query, including sql_where_taxa and sql_join
        sql_where_taxa = " WHERE " + " AND ".join(tab_sql)
        sql_query = f"""
        WITH 
            order_apg AS 
                (SELECT DISTINCT
                    b.id_taxonref AS id_order,
                    taxonomy.pn_taxa_getparent(id_taxonref, {idrankparent}) AS id_parent --to change
                FROM taxonomy.apg4 a
                INNER JOIN taxonomy.taxa_reference b ON lower(a.ordre) = b.basename
                WHERE b.id_rank = 8 
                AND a.clade = '{clade_sql}'
                ),
            taxa AS (
                SELECT 
                    a.id_taxonref, a.id_rank,
                    taxonomy.pn_taxa_getparent(a.id_parent, {idrankparent}) AS id_parent
                FROM taxonomy.taxa_reference a
                {sql_join_taxa}
                {sql_where_taxa}
            ),
            parents AS (
                SELECT 
                    id_taxonref, id_rank, id_parent
                FROM taxonomy.taxa_reference
                {sql_where_parents} 
                ),
            all_taxa AS            
                (SELECT * from parents
                    UNION
                SELECT * from taxa
                ),
            apg_taxa AS
                (SELECT DISTINCT a.id_taxonref, a.id_parent, a.id_rank
                    FROM all_taxa a
                    LEFT JOIN order_apg b ON a.id_taxonref = b.id_parent
                    LEFT JOIN order_apg c ON taxonomy.pn_taxa_getparent(a.id_taxonref, 8) = c.id_order
                    WHERE c.id_order IS NOT NULL OR b.id_parent IS NOT NULL
                ),
            score_taxa AS 
                (SELECT 
                    a.id_taxonref, a.id_rank,
                    a.taxaname, a.authors, a.published, a.accepted,
                    b.id_parent,
                    (a.metadata->'score'->>'taxaname_score')::numeric AS taxaname_score,
                    (a.metadata->'score'->>'authors_score')::numeric AS authors_score
                    FROM {base_taxa} b
                    INNER JOIN taxonomy.taxa_names a ON a.id_taxonref = b.id_taxonref
                    ORDER BY taxaname
                    )
            SELECT * FROM score_taxa;
        """




        # sql_query = f"""
        #             WITH taxa AS (
        #                 SELECT 
        #                     a.id_taxonref, a.id_rank, 
        #                     a.taxaname, a.authors, a.published, a.accepted, a.metadata,
        #                     taxonomy.pn_taxa_getparent(a.id_parent, {idrankparent}) AS id_parent
        #                 FROM taxonomy.taxa_names a
        #                 {sql_join}
        #                 {sql_where_taxa}
        #             ),
        #             parents AS (
        #                 SELECT 
        #                     id_taxonref, id_rank, 
        #                     taxaname, authors, published, accepted, metadata,
        #                     id_parent
        #                 FROM taxonomy.taxa_names
        #                 {sql_where_parents} 
        #             ),
        #             all_taxa AS (
        #                 SELECT * FROM parents
        #                 UNION
        #                 SELECT * FROM taxa WHERE id_parent IS NOT null
        #             )
        #              SELECT a.id_taxonref, a.id_rank,
        #                     a.taxaname, a.authors, a.published, a.accepted,
        #                     a.id_parent,
        #                    (a.metadata->'score'->>'taxaname_score')::numeric AS taxaname_score,
  		#  				   (a.metadata->'score'->>'authors_score')::numeric AS authors_score
        #              FROM all_taxa a
                    
        #             ORDER BY a.taxaname;
        #         """
        


        # sql_query = f"""
        #             WITH taxon AS (
        #                 SELECT a.id_taxonref, a.taxaname, a.authors, a.published, a.metadata,
        #                     taxonomy.pn_taxa_getparent(a.id_parent, {idrankparent}) AS id_parent,
        #                     a.id_rank
        #                 FROM taxonomy.taxa_names a
        #                 {sql_join}
        #                 {sql_where}
        #             ),
        #             parents AS (
        #                 SELECT id_taxonref, taxaname, authors, published, metadata,
        #                     -1::integer AS id_parent, {idrankparent}::integer as id_rank
        #                 FROM taxonomy.taxa_names
        #                 WHERE id_taxonref IN (SELECT DISTINCT id_parent FROM taxon)
        #             ),
        #             all_taxa AS (
        #                 SELECT * FROM parents
        #                 UNION ALL
        #                 SELECT * FROM taxon
        #             )
        #             SELECT a.id_taxonref, a.id_rank,
        #                    a.taxaname, a.authors, a.published, a.accepted,
        #                    a.id_parent,
        #                    (a.metadata->'score'->>'taxaname_score')::numeric AS taxaname_score,
  		# 				   (a.metadata->'score'->>'authors_score')::numeric AS authors_score
        #             FROM all_taxa a
        #             ORDER BY a.taxaname;
        #         """        
        #print(sql_query)
        return sql_query


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

    def combo_taxa_deletedItem(self, idtaxonref):
    #delete the selecteditem from the combo_taxa
        index = -1
        for i in range (self.combo_taxa.count()):
            if self.combo_taxa.itemData(i, role=Qt.UserRole).idtaxonref == idtaxonref:
                index = i
                break
        if index != -1:
            self.combo_taxa.removeItem(index)
    
    def trview_names_setdata(self, selecteditem):
        #print ("set names data", selecteditem.idtaxonref)
        #self.PN_tlview_names.setData(self.get_similar_names(selecteditem.idtaxonref))
        self.PN_tlview_names.setData(selecteditem.json_names)


        #self.PN_tlview_names.selectionModel().selectionChanged.connect(self.set_enabled_buttons)

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

    def toolbox_click(self, index = None):
        
        if index is None:
            index = self.window.toolBox.currentIndex()
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(index, self.window.style().standardIcon(51))
        #selecteditem = self.trview_taxonref.model().data( self.trview_taxonref.currentIndex(), Qt.UserRole)
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem:
            new_authors_name = selecteditem.authors
            self.authors_delegate.set_authors_name(new_authors_name)
            if index == 0  and self.PN_trview_identity.id != selecteditem.idtaxonref:
                print ("set identity data", selecteditem.idtaxonref)
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
                print ("set metadata data", selecteditem.idtaxonref)
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
                print ("set names data", selecteditem.idtaxonref)
                self.trview_names_setdata(selecteditem)
                self.PN_tlview_names.id = selecteditem.idtaxonref

        self.set_enabled_buttons()


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
        _properties = 'NUL'
        if tab_result:
            _properties = "'" + json.dumps(tab_result) + "'"
        

        sql_query = f"""UPDATE 
                            taxonomy.taxa_reference 
                        SET 
                            properties = {_properties}
                        WHERE 
                            id_taxonref = {id_taxonref} 
                        AND 
                            id_rank >= 21
                    """ 
        # else:

        #     sql_query = "UPDATE taxonomy.taxa_reference SET properties = NULL"
        #sql_query += f" WHERE id_taxonref = {id_taxonref} AND id_rank >= 21"

        result = self.db.exec (sql_query)
        code_error = result.lastError().nativeErrorCode()
        if len(code_error) != 0:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
       
    # def trView_hierarchy_selecteditem(self):
    # #transform the dict_item from the hierarchical selecteditem to a PNTaxa object
    #     dict_item = self.trView_hierarchy.selecteditem()
    #     # if dict_item is None:
    #     #     return
    #     # item = PNTaxa(dict_item["idtaxonref"], dict_item["taxaname"], dict_item["authors"], 
    #     #               dict_item["idrank"], dict_item["published"], dict_item["accepted"])
    #     # item.parent_name = dict_item["parent"]
    #     return self.trView_hierarchy.selecteditem()

    def trView_hierarchy_dblclick(self):
    #set the selecteditem to the filter combo_taxa
        selecteditem = self.trView_hierarchy.selecteditem()
        self.combo_taxa_selectedItem(selecteditem)
    
    def trView_hierarchy_click(self):
        #selecteditem = self.trView_hierarchy.selecteditem()
        print ("trView_hierarchy_click")
        self.toolbox_click()
            #set the rank_msg in the statusbar
        # get the current selectedItem
        selecteditem = self.trview_taxonref.model().data( self.trview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem is None:
            return
        child_count = self.trview_taxonref.model().rowCount(self.trview_taxonref.currentIndex())
        if child_count == 0:
            child_count = ''
        elif child_count == 1:
            child_count = ' (' + str(child_count) + " taxon)"
        else:
            child_count = ' (' + str(child_count) + " taxa)"
        self.rank_msg.setText(f"Selected {selecteditem.rank_name} : {selecteditem.taxonref}{child_count}")
        #set the metadata list
        #self.trview_names_setdata(selecteditem)

    def set_values_to_none(self, data):
        if isinstance(data, dict):  
            return {key: self.set_values_to_none(value) for key, value in data.items()}
        else:
            return ''
        
    def group_idrank(self):
    #return the id_rank of the selected group (according to group_button text)
        group_text = self.window.button_rankGroup.text()
        idrankparent = get_dict_rank_value(group_text, 'id_rank')
        if not idrankparent:
            idrankparent = 14 
        return idrankparent
    
    def group_menu_click(self, menu):
    #event when the group_menu is clicked
        self.window.button_rankGroup.setText(menu)
        self.tlview_taxonref_setData()

    def tlview_taxonref_click(self):
    #set the hierarchy, names, metadata and properties of the selected taxa
        #check if a previous changed has not be saved
        # check if the buttonbox_identity is enabled (if properties have been changed)
        #self.rank_msg.setText('< no selection >')
        
        
        if self.buttonbox_identity.isVisible() and self.buttonbox_identity.isEnabled():
                msg = "Some properties have been changed, save the changes ?"
                result = QtWidgets.QMessageBox.question(None, "Cancel properties", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
                self.buttonbox_identity.setEnabled(False)
                if result == QtWidgets.QMessageBox.Yes:
                    self.trview_identity_apply()
                   #self.buttonbox_identity.setEnabled(False)
        # clear lists
        #self.tlviews_clear()
        
        # get the current selectedItem
        selecteditem = self.trview_taxonref.model().data( self.trview_taxonref.currentIndex(), Qt.UserRole)
        if selecteditem is None:
            return


    #set the treetaxonomy hierarchy
        self.trView_hierarchy.setdata (selecteditem)



        #self.PN_tlview_metadata.setData (selecteditem.json_metadata)
    #     self.toolbox_click()
    # #set the metadata list
    #     self.trview_names_setdata(selecteditem)
        #if self.trView_hierarchy.model() is None :
        # selection = self.trView_hierarchy.selectionModel()
        # try:
        #     selection.selectionChanged.disconnect(self.set_enabled_buttons)
        # except Exception:
        #     pass
        # selection.selectionChanged.connect(self.set_enabled_buttons)
        
        #self.set_enabled_buttons()

       
    def tlview_taxonref_dblclick(self, current_index):
        # Select or insert the selecteditem into the combo_taxa combobox for shortcut
        selecteditem = self.trview_taxonref.model().data(current_index, Qt.UserRole)
        if selecteditem:
            self.combo_taxa_selectedItem(selecteditem)

    def tlview_taxonref_refreshData(self, value):
        #refresh the data of the trview_taxonref according to the filtering checkboxes
        #force the checkbox to be Checked or partially Checked
        if self.window.checkBox_withtaxa.checkState() == Qt.Unchecked:
            self.window.checkBox_withtaxa.setCheckState(Qt.PartiallyChecked) # trigger a recursive signal with validated state
            return
        #set the checked satus to the model
        self.trview_taxonref.model().show_nodes_published = self.window.checkBox_published.checkState()
        self.trview_taxonref.model().show_nodes_accepted = self.window.checkBox_accepted.checkState()
        self.trview_taxonref.model().show_nodes_with_children_only = self.window.checkBox_withtaxa.checkState()
        #rrefresh the current data, according to the new filters
        self.trview_taxonref.model().refreshData()
        
    def refresh_label_count(self):
        # Display taxa and group count within the self.window.label_count
        #trigger by the refresh_signal from the model
        count_taxa = self.trview_taxonref.model().taxa_count()
        count_parent =  self.trview_taxonref.model().rowCount()
        group_text = self.window.button_rankGroup.text()
        suffix = 'taxa'
        if count_taxa == 1:
            suffix = 'taxon'
        msg = f"|    {count_taxa} {suffix}, {count_parent} {group_text}(s)"
        self.window.label_count.setText(msg)
    
    def tlview_taxonref_setData(self):
        # clean the content and selection of trview_taxonref
        self.trview_taxonref.setCurrentIndex(QModelIndex())
        #clear both models first (ensure to empty the lists if the query is empty)
        self.trview_taxonref.model().clear()
        self.trView_hierarchy.model().clear()
        

        # search for a selected taxonref in combo_taxa
        combo_taxa_index = self.combo_taxa.currentIndex()
        idtaxonref = self.combo_taxa.itemData(combo_taxa_index, role=Qt.UserRole).idtaxonref

        # set the data from the database
        # fill the list data with PNTaxa_with_Score for any query result
        data = []
        #i = 0
        #row = 0
        query = self.db.exec(self.sql_taxa_get_names())
        while query.next():
            #select the row 
            # if query.value("id_taxonref") == idtaxonref:
            #     row = i
            # if query.value("id_rank") >=21:
            #     i += 1
            item = PNTaxa_with_Score(query.value("id_taxonref"), query.value("taxaname"), query.value("authors"), 
                        query.value("id_rank"), query.value("published"), query.value("accepted"))
            item.id_parent = query.value("id_parent")
            #set the taxaname_score and api_total
            #_total_api = len(self.metadata_worker.list_api)
            #item.api_total = 0
            item.taxaname_score = None
            item.authors_score = None
            #if _total_api > 0:
            if not query.isNull("taxaname_score"):
                item.taxaname_score = query.value("taxaname_score")
                if not query.isNull("authors_score"):
                    item.authors_score = query.value("authors_score")

            #item.authors_score = query.value("authors_score")
            data.append(item)
            
        # reset the model to the tableview for refresh
       #model_tableview = self.trview_taxonref.model() ## PNTaxa_TreeModel(data)
        
        # self.trview_taxonref.setModel(model_tableview)
        # model_tableview.refresh_signal.connect(self.refresh_label_count)

        #refresh the data of the model with the new list
        self.trview_taxonref.model().refreshData(data)

        #ajust trview_taxonref column width        
        self.trview_taxonref.resizeColumnToContents(0)
        total_width = self.trview_taxonref.viewport().width()
        self.trview_taxonref.setColumnWidth(0, int(total_width * 2 / 3))
        # force expand if a taxa is selected in the combobox_taxa
        if idtaxonref > 0:
            self.trview_taxonref.expandAll()   
        #select the first row (and activate the signal tlview_taxonref_click), row = 0 if no taxa selected
        
        selected_index = self.trview_taxonref.model().index(0,0)
        if selected_index.isValid():
            self.trview_taxonref.selectionModel().setCurrentIndex(
                    selected_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
        else:
            self.toolbox_click()
        #self.set_enabled_buttons()
   
    def trview_metadata_setDataAPI(self, base, api_json):
        # receive the slot from metaworker - save the json into the database when finish (base = 'END')
        #selecteditem = self.trview_taxonref.model().data(self.trview_taxonref.currentIndex(), Qt.UserRole)
        selecteditem = self.trView_hierarchy.selecteditem()
        _selecteditem = self.metadata_worker.PNTaxa_model
        sql_query =''
        _data_list = None
        if base == "NOTCONNECTED":
            msg = "Error: no connection to the internet"
            QtWidgets.QMessageBox.critical(None, "Connection error", msg, QtWidgets.QMessageBox.Ok)
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
                sql_insert = f"""
                                SELECT 
                                    taxonomy.pn_names_add ({_selecteditem.id_taxonref},'_synonymstr','Nomenclatural')
                            """
                for taxa in unique_set: #new_unique_taxa:
                    dict_taxa = get_dict_from_species(taxa)
                    if dict_taxa is None:
                        dict_taxa = {}
                        dict_taxa["names"] = [taxa]
                    for value in dict_taxa["names"]:
                        sql_query = sql_insert.replace('_synonymstr', str(value))
                        try:
                            #query = QtSql.QSqlQuery()
                            result = self.db.exec(sql_query)
                            code_error = result.lastError().nativeErrorCode()

                        #if no errors, count new_names
                            if len(code_error) == 0:
                                new_synonyms += 1
                        except Exception:
                            continue
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
            _data_list = _data_list.replace("'","''") #escape single quote for sql
            #_data_list = list(api_json.items())
            sql_query = f"""UPDATE 
                                taxonomy.taxa_reference 
                            SET 
                                metadata = '{_data_list}'
                            WHERE 
                                id_taxonref = {_selecteditem.id_taxonref}
                        """
            self.db.exec(sql_query)
            if "score" in api_json:
                dict_score = api_json["score"]
                trview_item = self.trview_taxonref.model().getItem(_selecteditem.idtaxonref)
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
                trview_item = self.trview_taxonref.model().getItem(_selecteditem.idtaxonref)
                if trview_item:
                    trview_item.taxaname_score = dict_score["taxaname_score"]
                    trview_item.authors_score = dict_score["authors_score"]
                del api_json["score"]
             #fill the treeview with the dictionnary json
            self.trview_taxonref.repaint()
            self.PN_tlview_metadata.dict_db_properties[base] = api_json
            self.PN_tlview_metadata.refresh()
        return

        
### MANAGE buttons
    def set_enabled_buttons(self):
        #print ("set_enabled_buttons")
        # set any button to enabled = False
        self.window.pushButtonAdd.setEnabled(False)
        self.window.pushButtonEdit.setEnabled(False)
        self.window.pushButtonDel.setEnabled(False)
        self.window.button_MergeNames.setEnabled(False)
        self.window.button_addNames.setEnabled(False)
        self.window.button_editNames.setEnabled(False)
        self.window.button_delNames.setEnabled(False)
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
        self.window.pushButtonAdd.setEnabled(True)
        self.window.buttonBox_metadata.setEnabled(True)
        self.window.button_rankGroup.setEnabled(True)

        # buttons of the names tab: check if a synonym is selected in the names tab, and set enabled buttons to add/remove
        value = False
        try:
            if self.PN_tlview_names.currentIndex().parent().isValid():
                value = self.PN_tlview_names.currentIndex().parent().data() != 'Autonyms'
        except Exception:
            value = False
        self.window.pushButtonEdit.setEnabled(value)
        self.window.pushButtonDel.setEnabled(value)

        # buttons of the hierarchy: check if a childs item is selected in the hierarchy, and set enabled buttons
        # id_taxonref = None
        # try:
        #     id_taxonref = selected_taxa.idtaxonref

        #     #id_taxonref = int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
        # except Exception:
        #     pass
        #value = id_taxonref is not None
        value = selected_taxa.id_rank >2
        self.window.button_editNames.setEnabled(value)
        self.window.button_MergeNames.setEnabled(value)
        self.window.button_addNames.setEnabled(value)
        self.window.button_delNames.setEnabled(value)
        
        

    def button_addNames_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None: 
            return
            
        win = PNTaxa_add(selecteditem)
        win.apply_signal.connect(self.update_names)
        win.show()

    def button_editNames_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        win = PNTaxa_edit(selecteditem)
        win.apply_signal.connect(self.update_names)
        win.show()
    
    def update_names(self, ls_dict_tosave):
        """ 
            common function for update (add_name and edit_name) when apply
            Save a taxon in the database from a list of dictionnaries:   
            if parentname is not present, it will update the taxon with id_parent = (searching the id_parent, in the dbase taxaname = parentname)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "parentname":text, "published":boolean, "accepted":boolean, "id_rank" :integer}
            if idparent is present, it will update the taxon with the id_parent (integer)
                dict_tosave = {"id_taxonref":integer, "basename":text, "authors":text, "id_parent":integer, "published":boolean, "accepted":boolean, "id_rank" :integer}
        """

        #internal function for saving one taxon in the database
        def database_save_taxon(dict_tosave):
            #return id_taxonref (new or updated) or None if error

            code_error = ''
            msg = ''
            return_idtaxonref = None
            idtaxonref = dict_tosave.get("id_taxonref", None)
            if idtaxonref is None:
                return None
            
            basename = dict_tosave.get("basename", None)
            if basename:
                basename = basename.strip().lower()
            else:
                return None
            #test for the types of update (according to specific fields)
            _parentname = dict_tosave.get("parentname", None)
            _idparent = dict_tosave.get("id_parent", None)
            published = dict_tosave.get("published", None)
            accepted = dict_tosave.get("accepted", None)
            authors = dict_tosave.get("authors", "").strip()
            authors = authors.replace("'", "''")  # escape single quotes
            idrank = dict_tosave.get("id_rank", None)

        #create the from_query depending if parentname/id_parent are present into the dictionnayr dict_tosave
            if _parentname:# get the id_parent from the parentname (to add taxon, idtaxonref= 0)
                _parentname = _parentname.strip().lower()
                sql_update = f"""(SELECT 
                                    taxonomy.pn_taxa_edit ({idtaxonref}, '{basename}', '{authors}', taxa.id_parent, {idrank}, {published},{accepted}) AS id_taxonref 
                                FROM
                                    (SELECT 
                                        a.id_taxonref AS id_parent
                                    FROM
                                        taxonomy.taxa_names a
                                    WHERE 
                                        lower(a.taxaname) ='{_parentname}'
                                    ) taxa
                                )
                            """
            elif _idparent:
                sql_update = f"""SELECT 
                                    taxonomy.pn_taxa_edit ({idtaxonref}, '{basename}', '{authors}', {_idparent}, {idrank}, {published},{accepted}) AS id_taxonref"""
            else:
                return
            
        #1 - execute the sql_update and get the id_taxonref (update or add), if no error 
            sql_update = sql_update.replace("None", "NULL")
            result = self.db.exec (sql_update)
            code_error = result.lastError().nativeErrorCode()

            #if no errors, set the id_taxonref to the dict_tosave
            if len(code_error) == 0:
                if result.next():
                    return_idtaxonref = result.value("id_taxonref")
                #dict_tosave["id_taxonref"] = return_idtaxonref            
            else:
                msg = postgres_error(result.lastError())
                QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return return_idtaxonref

#####main part of the function
        if not isinstance(ls_dict_tosave, list):
            ls_dict_tosave = [ls_dict_tosave]
        ls_item_updated = []
        #save any dict from the list
        for dict_tosave in ls_dict_tosave:
            idtaxonref_torefresh  = database_save_taxon(dict_tosave)
            if idtaxonref_torefresh:
                ls_item_updated.append(idtaxonref_torefresh)
                #ensure to update the id_taxonref in the dict_tosave
                dict_tosave["id_taxonref"] = idtaxonref_torefresh
        
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
            idtaxonref = self.sender().PNTaxa.idtaxonref
            idrank = self.sender().PNTaxa.id_rank
            #refresh the tlview_taxonref if rank is include into the view (grouped_idrank or higher)
            if idrank >= self.group_idrank():
                self.tlview_taxonref_refresh(ls_item_updated)
           
            #get the selecteditem from the trview_taxonref.model
            selecteditem = self.trview_taxonref.model().data( self.trview_taxonref.currentIndex(), Qt.UserRole)
            #if no selection, create a new PNTaxa_with_Score to be sure to get hierarchy of item
            if selecteditem is None:
                selecteditem = PNTaxa_with_Score(idtaxonref)
            #set and select the item in the trView_hierarchy, with idtaxonref as selected item
            if selecteditem:
                #ensure to see the idtaxonref, by switching the idrank temporarily
                # save_idrank = selecteditem.id_rank
                # selecteditem.id_rank = idrank
                self.trView_hierarchy.setdata (selecteditem, idtaxonref)
                # selecteditem.id_rank = save_idrank

            #efresh the sender PNTaxa_edit or PNTaxa_add
            self.sender().PNTaxa = self.trView_hierarchy.selecteditem()
            self.sender().refresh()



    def tlview_taxonref_refresh(self, ls_idtaxonref):
    #refresh (update) the trview_taxonref model according to the database for a list of idtaxonref (refresh taxa + childs)
    #return a list of PNTaxa updated (PNTaxa1, PNTaxa2,...)

        if not isinstance(ls_idtaxonref, list):
            ls_idtaxonref = [ls_idtaxonref]
        if not ls_idtaxonref:
            return []
        
        model = self.trview_taxonref.model()
        #set the id_parent to grouped_idrank and refresh only visible items
        #first_item = None        
    #2 - create and execute the query to get the childs from the database (only childs linked by name, ex...genus + species)
        # to refresh UI nodes in the model with the id_parent field
        grouped_idrank = self.group_idrank()
        sql_query = f"""
            SELECT 
                DISTINCT
                a.id_taxonref, a.id_rank, 
                a.taxaname, a.authors, a.published, a.accepted,
                coalesce(taxonomy.pn_taxa_getparent(a.id_parent, {grouped_idrank}), a.id_parent) AS id_parent,
                a.authors_score
            FROM
                (SELECT (taxonomy.pn_taxa_childs(id_taxonref, True, True)).*,
                    (metadata->'score'->>'authors_score')::numeric AS authors_score
                    FROM 
                    taxonomy.taxa_reference
                    WHERE
                    id_taxonref IN ({', '.join(map(str, ls_idtaxonref))})
                ) a

        """
            #     WHERE 
            #     a.id_rank = {grouped_idrank}
            # OR
            #     a.id_rank >= 21
        #print (sql_query)
        #execute query and return a list of PNTaxa to update into the model
        result = self.db.exec (sql_query)
        code_error = result.lastError().nativeErrorCode()
        ls_updated_items = []
        if len(code_error) == 0:#add or edit a PNTaxa if save without errors
            try:
                #disconnect signal to avoid multiple events (except error if not yet connected)
                #self.trview_taxonref.selectionModel().selectionChanged.disconnect(self.tlview_taxonref_click)
                self.trview_taxonref.selectionModel().selectionChanged.disconnect()
            except Exception:
                pass
            while result.next():
                #if result.value("id_rank") == grouped_idrank or result.value("id_rank") >= 21:
                    item = PNTaxa_with_Score(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                    result.value("id_rank"), result.value("published"), result.value("accepted"))
                    if not result.isNull("authors_score"):
                        item.authors_score = result.value("authors_score")
                    item.id_parent = result.value("id_parent")
                    ls_updated_items.append(item)
                
            #re-initialise the current index
            index = self.trview_taxonref.currentIndex()
            self.rank_msg.setText('< no selection >')
            #get the current selectioned item
            #selecteditem = self.trview_taxonref.model().data(self.trview_taxonref.currentIndex(), Qt.UserRole)
            #selected index and connect the signal
            self.trview_taxonref.setCurrentIndex(QModelIndex())
            #if list, refresh model and select the current index or the first updated item if index is not valid
            if ls_updated_items:
                model.refresh(ls_updated_items)
                #search for the last founded item.id_parent
                index = model.indexItem(item.id_parent)
                #search for the last item.id_taxonref if parent not found
                if not index.isValid():
                    index = model.indexItem(item.id_taxonref)
                #select parent if valid
                if index.isValid():
                    self.trview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
                else: #not found, force loading through combo_taxa with item.id_parent
                    item = PNTaxa_with_Score(item.id_parent)
                    self.combo_taxa_selectedItem(item)

            #reconnect the signal
            self.trview_taxonref.selectionModel().selectionChanged.connect(self.tlview_taxonref_click)
            #expand & repaint the trview_taxonref
            #self.trview_taxonref.expand(index)
            self.trview_taxonref.repaint()
        else:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return ls_updated_items


    def button_delNames_click(self):
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem is None:
            return
        # message to be display first (question, Yes or Not)
        msg = f"""Are you sure you want to delete \"{selecteditem.taxonref}\"?
                 \nThe children and all associated names will be permanently deleted"""
        result = QtWidgets.QMessageBox.warning(
            None, "Delete a taxon", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
        
        #delete is confirmed
        #get the list of the id_taxonref childs (affected by deleted on cascade)
        sql_query = f"""SELECT 
                            id_taxonref 
                        FROM 
                            taxonomy.pn_taxa_childs({selecteditem.id_taxonref}, True);
                    """
        result = self.db.exec(sql_query)
        ls_todelete = []
        if not result.lastError().isValid():
            while result.next():
                ls_todelete.append(result.value("id_taxonref"))
        if not ls_todelete:
            return
        
        # execute delete into the database
        sql_query = self.sql_taxa_delete_reference(selecteditem.id_taxonref)
        result = self.db.exec(sql_query)
        if not result.lastError().isValid():
            #refresh the model and combo_taxa
            try:
                #disconnect signal to avoid multiple events (except error if not yet connected)
                self.trview_taxonref.selectionModel().selectionChanged.disconnect()
            except Exception:
                pass
            # Remove the selected taxa and childs in model and combo_taxa
            for idtaxonref in ls_todelete:
                # remove the item from the model
                self.trview_taxonref.model().removeItem(idtaxonref)
                self.combo_taxa_deletedItem(idtaxonref)
                
            index = self.trview_taxonref.currentIndex()
            if not index.isValid():
                index = self.trview_taxonref.model().index(0,0)
            self.trview_taxonref.setCurrentIndex(QtCore.QModelIndex())
            self.trview_taxonref.selectionModel().selectionChanged.connect(self.tlview_taxonref_click)
            self.trview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
            #.trview_taxonref.expand(index)
            #repaint the trview_taxonref
            #self.trview_taxonref.repaint()
        else:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return

    def button_MergeChilds_click(self):
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
                sql_update = f"CALL taxonomy.pn_taxa_set_synonymy({from_idtaxonref}, {idtaxonref}, '{category}');"
                result = self.db.exec (sql_update)
                code_error = result.lastError().nativeErrorCode()
                if len(code_error) == 0:            
                    #reset the id of PN_tlview_names to force refresh (toolbox trigger by self.trView_hierarchy)
                    self.PN_tlview_names.id = 0
                    self.PN_tlview_metadata.id = 0
                    idrank = selecteditem.id_rank
                    # deleted the input taxa
                    self.trview_taxonref.model().removeItem(from_idtaxonref)
                    #refresh the tlview_taxonref
                    if idrank >= self.group_idrank():
                        self.tlview_taxonref_refresh([idtaxonref])
                    
                    #get the selecteditem from the trview_taxonref.model
                    selecteditem = self.trview_taxonref.model().data( self.trview_taxonref.currentIndex(), Qt.UserRole)
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
                    msg = postgres_error(result.lastError())
                    QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)



                # dict_tosave = {"id_taxonref":from_idtaxonref, "id_merge":idmerge, "category":category}
                # #get the id_taxonref from the database (should be the same as idmerge)
                # to_idtaxonref = self.database_save_taxon(dict_tosave)
                # if to_idtaxonref:
                #     # deleted the input taxa
                #     self.trview_taxonref.model().removeItem(from_idtaxonref)
                #     #refresh the destination taxa
                #     self.tlview_taxonref_refresh(to_idtaxonref)
                win.close()
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
    #         selecteditem = self.trView_hierarchy.selecteditem()
    #         win = PN_move_taxaname(selecteditem, False)
    #         win.show()
    #         if win.updated:
    #             # update the sub-taxas properties
    #             for item in win.updated_datas:
    #                 self.trview_taxonref.model().sourceModel().refresh(item)
    #         # refresh the view
    #             self.tlviews_refresh(selecteditem.idtaxonref)
    #     except Exception:
    #         return


    # def button_addChilds_click(self):
    #     #selecteditem = trview_taxonref.model().data(trview_taxonref.currentIndex(), Qt.UserRole)
    #     try:
    #         row_index = self.trview_taxonref.currentIndex()
    #         selecteditem = self.trview_taxonref.model().data(row_index, Qt.UserRole)
    #         # int(self.trView_hierarchy.currentIndex().siblingAtColumn(2).data())
    #         id_taxonref = selecteditem.idtaxonref
    #         win = PNTaxa_edit(id_taxonref, 1)
    #         win.show()

    #         if win.updated:
    #             for item in win.updated_datas:
    #                 # refresh the data
    #                 self.trview_taxonref.model().sourceModel().refresh(item)

    #         # refresh the view
    #             self.tlviews_refresh(id_taxonref)
    #     except Exception:
    #         return
    def button_clean_setData(self):
        dict_db_properties = {}
        for _key, _value in list_db_properties.items():
            dict_db_properties[_key] = {}.fromkeys(_value,'')
        self.PN_trview_filter.setData(dict_db_properties)

    def button_clean_click(self):
        self.window.lineEdit_searchtaxon.setText("")
        self.button_clean_setData()
        #self.PN_trview_filter.setModel(None)
        self.tlview_taxonref_setData()

    def button_metadata_refresh(self):
        # get the selectedItem
        #selecteditem = self.trview_taxonref.model().data(self.trview_taxonref.currentIndex(), Qt.UserRole)
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

    def button_add_synonym(self):
        # get the selectedItem
        # selecteditem = self.trview_taxonref.model().data(
        #     self.trview_taxonref.currentIndex(), Qt.UserRole)
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if self.PN_tlview_names.currentIndex().parent().isValid():
            category = self.PN_tlview_names.currentIndex().parent().data()
        else:
            category = self.PN_tlview_names.currentIndex().data()
        new_synonym = PNSynonym(None, selecteditem.taxonref, selecteditem.idtaxonref,category)
        class_newname = PNSynonym_edit(new_synonym)
        class_newname.show()
        self.trview_names_setdata(selecteditem)
        self.set_enabled_buttons()

    def button_edit_synonym(self):
        # get the selectedItem
        # selecteditem = self.trview_taxonref.model().data(
        #     self.trview_taxonref.currentIndex(), Qt.UserRole)
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
        class_newname.show()
        self.trview_names_setdata(selecteditem)
        self.set_enabled_buttons()


    def button_delete_synonym(self):
        # selecteditem = self.trview_taxonref.model().data(
        #     self.trview_taxonref.currentIndex(), Qt.UserRole)
        selecteditem = self.trView_hierarchy.selecteditem()
        if selecteditem.idtaxonref == 0:
            return
        if not self.PN_tlview_names.currentIndex().parent().isValid():
            return
        _currentsynonym = self.PN_tlview_names.currentIndex().data()
        if _currentsynonym is None:
            return
        
        # message to be display first (question, Yes or Not)
        msg = f"Are you sure to permanently delete this name {_currentsynonym}?"
        result = QtWidgets.QMessageBox.question(
            None, "Delete a synonym", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.No:
            return
            # execute the suppression
        sql_query = self.sql_taxa_delete_synonym(_currentsynonym)
        result = self.db.exec(sql_query)
        code_error = result.lastError().nativeErrorCode()
        if len(code_error) == 0:
            self.trview_names_setdata(selecteditem)
        else:
            msg = postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        
        self.set_enabled_buttons()


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