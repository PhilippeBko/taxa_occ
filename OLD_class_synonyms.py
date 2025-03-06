from PyQt5 import uic, QtWidgets, QtSql
from PyQt5.QtCore import pyqtSignal

#import commons
from commons import postgres_error

from taxa_model import QTreeViewSearch


class PNSynonym(object):
    def __init__(self, synonym = None, taxonref = None, idtaxonref = 0, category = 'Orthographic'):
        self.synonym = synonym
        self.category = category
        self.taxon_ref = taxonref
        self.id_taxonref = idtaxonref
        self.keyname =''

    @property
    def idtaxonref(self):
        try:
            return int(self.id_taxonref)
        except Exception:
            return 0

    @property
    def resolved(self):
        #return True if idtaxonref>0 
        return self.idtaxonref > 0  

    # @property
    # def cleaned_name(self):
    #     if len(self.keyname) == 0:
    #         sql_query = "SELECT taxonomy.pn_taxa_keyname('__taxaname__') AS keyname"
    #         sql_query = sql_query.replace("__taxaname__", self.taxon_ref)
    #         query = QtSql.QSqlQuery (sql_query)
    #         if query.next():
    #             self.keyname = query.value('keyname')
    #     return self.keyname

#####################
#Class to edit(New or update) synonym
# add/update a new synonym to a idtaxonref or search for a idtaxonref (QTreeViewSearch) according to a synonym 
class PN_edit_synonym (QtWidgets.QWidget):
    button_click = pyqtSignal(object, int)
    def __init__(self, myPNSynonym):

        super().__init__()
        self.ui_addname = uic.loadUi("edit_name.ui")
        self.Qline_name = self.ui_addname.name_linedit
        self.Qline_ref = self.ui_addname.taxaLineEdit
        self.Qcombobox = self.ui_addname.comboBox
        buttonbox = self.ui_addname.buttonBox
        self.button_cancel = buttonbox.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_ok = buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        self.myPNSynonym = myPNSynonym
        self.treeview_searchtaxa = QTreeViewSearch()
        self.is_new = (self.myPNSynonym.synonym is None or self.myPNSynonym.idtaxonref == 0)


    def setting_ui(self):
        self.updated = False
        self.Qline_name.setReadOnly(not self.myPNSynonym.resolved)
        self.Qline_name.setText('') 
        self.ui_addname.setMaximumHeight(500)
        self.ui_addname.resize(500,500)
        self.Qcombobox.setCurrentText(str(self.myPNSynonym.category))
        self.Qline_name.setText(self.myPNSynonym.synonym)
        #resolved depends if idtaxonref is Null
        if not self.myPNSynonym.resolved:
            self.ui_addname.label_tip.setText('Select Reference...')
            #add the treeview_searchtaxa = Class QTreeViewSearch() (cf. taxa_model.py)
            layout = self.ui_addname.QTreeViewSearch_layout
            layout.addWidget(self.treeview_searchtaxa)
            self.treeview_searchtaxa.setText(self.myPNSynonym.synonym)
            self.treeview_searchtaxa.selectionChanged.connect(self.valid_newname)
        else: #idtaxonref is not Null
            if self.is_new:
                self.ui_addname.label_tip.setText('New Synonym...')
            else:
                self.ui_addname.label_tip.setText('Edit Synonym...')
            self.Qline_ref.setText(self.myPNSynonym.taxon_ref)
            self.ui_addname.setMaximumHeight(1)
            self.Qline_name.setFocus()
        self.Qline_name.textChanged.connect (self.valid_newname)
        self.Qcombobox.activated.connect(self.valid_newname)
        self.button_ok.clicked.connect (self.accept) 
        self.button_cancel.clicked.connect (self.close)
        self.valid_newname()

    def show(self):
        self.setting_ui()
        self.ui_addname.show()
        self.ui_addname.exec()
        
    def close(self):
        self.ui_addname.close()

    def valid_newname(self):
        txt_item = self.Qline_name.text().strip()
        txt_category = self.Qcombobox.currentText().strip()         
        flag = False
        if len(txt_item)>3:
            if self.myPNSynonym.resolved:
                flag = not (self.myPNSynonym.synonym == txt_item and self.myPNSynonym.category == txt_category)
            else:
                new_taxonref = self.treeview_searchtaxa.selectedTaxonRef()
                flag = new_taxonref is not None
                self.Qline_ref.setText(new_taxonref)
        self.button_ok.setEnabled(flag)

    def accept(self):
        self.updated = False
        new_synonym = self.Qline_name.text().strip()
        new_category = self.Qcombobox.currentText()
        new_taxonref = self.Qline_ref.text().strip()
        #is_new = True
        if self.myPNSynonym.resolved:
            idtaxonref = self.myPNSynonym.idtaxonref
            #is_new = (self.myPNSynonym.synonym is None)
        else:
            try :
                idtaxonref = int(self.treeview_searchtaxa.selectedTaxaId())
            except Exception:
                idtaxonref = 0
        if idtaxonref == 0:
            return
        if self.is_new:
            #add mode
            sql_query = f"SELECT taxonomy.pn_names_add ('{new_synonym}','{new_category}', '{idtaxonref}')"
        else:
            #edit mode
            #return if nothing has changed
            if new_synonym == self.myPNSynonym.synonym and new_category == self.myPNSynonym.category:
                self.ui_addname.close()
                return True
            sql_query = f"SELECT taxonomy.pn_names_update ('{self.myPNSynonym.synonym}','{new_synonym}', '{new_category}')"
        #execute query
        result = QtSql.QSqlQuery (sql_query)
        #check for errors code (cf. postgresql function taxonomy.pn_taxa_edit_synonym)
        code_error = result.lastError().nativeErrorCode ()
        msg = ''
        if len(code_error) == 0:
            self.myPNSynonym.synonym = new_synonym
            self.myPNSynonym.category = new_category
            self.myPNSynonym.taxon_ref = new_taxonref                                    
            self.myPNSynonym.id_taxonref = idtaxonref
            self.ui_addname.close()
            self.updated = True
            return True
        else:
            msg = postgres_error(result.lastError())
        QtWidgets.QMessageBox.critical(self.ui_addname, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return False



# class PN_add_synonym (QtWidgets.QWidget):
#     button_click = pyqtSignal(object, int)
#     def __init__(self, myPNTaxa):

#         super().__init__()
#         self.window = uic.loadUi("pn_addsynonym.ui")
#         self.myPNTaxa = myPNTaxa
#         self.table_taxa = []
#         self.data_rank = []
#         self.updated = False

#         #self.window.setWindowTitle("Add Taxa")          

#         model = QtGui.QStandardItemModel()
#         #model.setHorizontalHeaderLabels(['Rank','Taxon'])        
#         model.setHorizontalHeaderLabels(['Taxa', 'Category'])          
#        # model.itemChanged.connect(self.tblview_api_click)
        

#         self.window.tblview_api.setModel(model)
#         selection = self.window.tblview_api.selectionModel()
#         selection.currentChanged.connect(self.tblview_api_before_clickitem)
#         self.window.tblview_api.clicked.connect(self.tblview_api_click)

#         self.window.tblview_api.setColumnWidth(0,250)
#         self.window.tabWidget_main.currentChanged.connect(self.alter_category)
#         self.Qbutton_OK = self.window.buttonBox
#         self.Qbutton_OK.rejected.connect (self.close)
#         #button = self.window.buttonBox.button(QDialogButtonBox.Apply)
#         self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(False)
#         #button.clicked.connect(self.apply)


#     def close(self):
#         self.window.close()
#     def show(self):
#         self.window.show()
#         self.window.exec_()       


#     def tblview_api_before_clickitem(self, current_index, previous_index):
#         try:
#             column2_index = self.window.tblview_api.model().itemFromIndex(previous_index).index()
#             self.window.tblview_api.setIndexWidget(column2_index, None)
#         except Exception:
#             pass

#     def tblview_api_click(self):
#             #tlview_identity_get_dict_properties(tlview_identity.model())
#         if self.window.tblview_api.currentIndex().column() != 1:
#             return
#         # item = self.window.tblview_api.model().itemFromIndex(self.window.tblview_api.currentIndex())
#         # if not item.isCheckable():
#         #     return

#         try:
#             #field_name = self.window.tblview_api.currentIndex().siblingAtColumn(0).data()
#             field_value = self.window.tblview_api.currentIndex().siblingAtColumn(1).data()
#         except Exception:
#             return
#         #try:
#         column2_index = self.window.tblview_api.model().itemFromIndex(self.window.tblview_api.currentIndex()).index()

#         combo_shortcut = QtWidgets.QComboBox()
#         font = QtGui.QFont()
#         font.setPointSize(10)
#         combo_shortcut.setFont(font)
#         combo_shortcut.setFrame(False)
#         #combo_shortcut.setStyleSheet("QComboBox { color: white;background-color: rgb(46, 52, 54);gridline-color:yellow; border-radius: 5px;}") 
#         style_sheet ="QComboBox QAbstractItemView {background-color: rgb(46, 52, 54)} "
#         style_sheet +="QComboBox {selection-background-color:black; selection-color:yellow; color: rgb(239, 239, 239);background-color: rgb(46, 52, 54); border-radius: 3px}"
#         style_sheet +="QComboBox::drop-down:button{background-color: rgb(46, 52, 54)} "
#         combo_shortcut.setStyleSheet(style_sheet)
#         #combo_shortcut.setStyleSheet("QComboBox { color: white;background-color: rgb(46, 52, 54)}")
#         _properties =['Orthographic', 'Nomenclatural', 'Taxinomic', 'Vernacular']
#         combo_shortcut.addItems(_properties)
#         combo_shortcut.setCurrentText(field_value.title())
#         combo_shortcut.currentIndexChanged.connect(self.tblview_api_combo_click)
        
#         self.window.tblview_api.setIndexWidget(column2_index, combo_shortcut)

#     def tblview_api_combo_click(self, index):
#         if self.window.tblview_api.currentIndex().column() !=1: 
#             return
#         _properties =['Orthographic', 'Nomenclatural', 'Taxinomic', 'Vernacular']
#         _value =_properties[index]
#         item = self.window.tblview_api.model().itemFromIndex(self.window.tblview_api.currentIndex())
#         item.setText(_value)

#     def alter_category(self, index):
#         #index = self.window.comboBox_searchAPI.currentIndex()
#         if index == 0 : 
#             #self.taxaLineEdit_setdata()
#             return
#         self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(False)
#         #self.window.setCursor(Qt.WaitCursor)
#         QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
#         layout = self.window.tabWidget_main.currentWidget().layout()
#         widget = None
#         if layout is None:
#             layout = QtWidgets.QGridLayout()
#             self.window.tabWidget_main.currentWidget().setLayout(layout)
#             layout.addWidget(self.window.tblview_api)
#             widget = QtWidgets.QLabel()
#             widget.setText('Check the taxa to add')
#             layout.addWidget(widget)
#         else:            
#             layout.addWidget(self.window.tblview_api)
#         index = self.window.tabWidget_main.currentIndex()
#         #_apibase = index.text().lower()
#         _apibase = self.window.tabWidget_main.tabText(index).lower()
#         if _apibase == 'taxref':
#             table_taxa = API_TAXREF(self.myPNTaxa).get_synonyms()
#         elif _apibase == 'endemia':
#             table_taxa = API_ENDEMIA(self.myPNTaxa).get_synonyms()
#         # elif _apibase == 'powo':
#         #     table_taxa = API_POWO(self.myPNTaxa).get_synonyms()
#         elif  _apibase == 'florical':
#             table_taxa = API_FLORICAL(self.myPNTaxa).get_synonyms()
#             #restore original cursor
#         self.window.tblview_api.model().setRowCount(0)
#         self.window.tblview_api.repaint()

#         while QtWidgets.QApplication.overrideCursor() is not None:
#             QtWidgets.QApplication.restoreOverrideCursor()
#         #self.window.setCursor(Qt.ArrowCursor)
#         try:
#             if len(table_taxa) == 0:
#                 return
#         except Exception:
#             return

#         #sort the list
#         self.table_taxa = []
#         sort_taxa = []
#         for taxa in table_taxa:
#             if taxa not in sort_taxa: #eliminate duplicate
#                 sort_taxa.append(taxa.strip())
                
#         sort_taxa = sorted(sort_taxa)

#         #add special fields and construct the query
#         _taxaname=''
#         _parser=''        
#         try:
#             for taxa in sort_taxa:
#                 _taxaname += _parser +"'" +taxa +"'"
#                 _parser=", "
#         except Exception:
#             pass
        
#          #check the taxaname into the taxa tables, and alters the id_taxonref
#         sql_query = "SELECT COALESCE(id_taxonref,0) AS id_taxonref, original_name FROM taxonomy.pn_taxa_searchnames( array[_taxaname]) ORDER BY original_name"        
#         sql_query = sql_query.replace('_taxaname', _taxaname)
#         query = QtSql.QSqlQuery (sql_query)
#         #set the id_taxonref for taxa already existing into the taxonomy tables
#         model = self.window.tblview_api.model()
#         model.setRowCount(0)
#         model.setColumnCount(2)
#         for taxa in sort_taxa:
#             table_taxa = get_dict_from_species(taxa)
#             table_taxa["id_taxonref"] = 0
#             self.table_taxa.append(table_taxa)

#         while query.next():
#             taxa = query.value("original_name")
#             item = QtGui.QStandardItem(taxa)
#             item.setCheckable(query.value("id_taxonref")==0)
#             self.window.tblview_api.model().appendRow([item, QtGui.QStandardItem("Taxinomic"), ])

#         self.window.tblview_api.resizeColumnToContents(0)
#         self.window.tblview_api.horizontalHeader().setStretchLastSection(True)
#        # print (self.table_taxa)
#         #self.draw_result()


#     def draw_result(self):
#         model = self.window.tblview_api.model()
#         model.setRowCount(0)
#         model.setColumnCount(4)
#         #self.draw_list ()
#         if model.rowCount() ==0:
#             model.appendRow([QtGui.QStandardItem("No data   "), QtGui.QStandardItem("< Null Value >")],)
#         # self.window.trView_childs.hideColumn(2)
#         # self.window.trView_childs.hideColumn(3)
#         # self.window.trView_childs.expandAll()
#         # self.window.trView_childs.resizeColumnToContents(0)
#         # self.window.trView_childs.resizeColumnToContents(1)
#         # self.window.trView_childs.sortByColumn(1, Qt.AscendingOrder)
