import re

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox, QDialogButtonBox, QGridLayout, QApplication, QCompleter
from PyQt5 import QtGui, QtSql 
from PyQt5.QtCore import pyqtSignal, Qt

from taxa_model import PNTaxa
from api_thread import API_TAXREF, API_ENDEMIA, API_POWO, API_FLORICAL
from commons import postgres_error, get_str_value, get_dict_rank_value

data_prefix = {11:'subfam.', 12:'tr.', 13:'subtr.', 15:'subg.', 16:'sect.', 17:'subsect.',18:'ser.',19:'subser.',21:'',22:'subsp.',23:'var.',25:'f.',28:'cv.',31:'x'}
	


class PN_add_taxaname(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa): # move toward a same id_rank if merge
        super().__init__()
        self.window = uic.loadUi("pn_addtaxa.ui")
        self.myPNTaxa = myPNTaxa
        self.table_taxa = []
        self.data_rank = []
        self._taxaname = ''
        self.updated = False
        # self.window.comboBox_searchAPI.addItems(['TaxRef', 'Endemia', 'Powo', 'Florical'])
        # self.window.comboBox_searchAPI.setCurrentIndex(0)

        #self.window.setWindowTitle("Add Taxa")        
        self.window.publishedComboBox.addItems(['Published', 'Unpublished'])
        self.rankComboBox_setdata()      

        model = QtGui.QStandardItemModel()
        #model.setHorizontalHeaderLabels(['Rank','Taxon'])        
        model.itemChanged.connect(self.trview_childs_checked_click)        
        self.window.trView_childs.setModel(model)
        self.window.trView_childs.setColumnWidth(0,250)
        #self.window.trView_childs.setHeaderHidden(True) 

        # self.window.comboBox_searchAPI.activated.connect(self.alter_category)
        #self.window.buttonGroup.buttonPressed.connect(self.alter_category)
        self.window.tabWidget_main.currentChanged.connect(self.alter_category)
        self.window.basenameLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.authorsLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.rankComboBox.activated.connect(self.taxaLineEdit_setdata)
        self.window.publishedComboBox.activated.connect(self.taxaLineEdit_setdata)

        if self.myPNTaxa.id_rank <14:
            self.window.tabWidget_main.setTabEnabled(4, False)
        if self.myPNTaxa.id_rank <10:
            self.window.tabWidget_main.setTabEnabled(1, False)
            self.window.tabWidget_main.setTabEnabled(3, False)
        if self.myPNTaxa.id_rank <8:
            self.window.tabWidget_main.setTabEnabled(1, False)
        
        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QDialogButtonBox.Apply)
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        self.taxaLineEdit_setdata()
        #self.alter_category()

    def taxaLineEdit_setdata(self):
        newbasename = self.window.basenameLineEdit.text()
        newauthors = self.window.authorsLineEdit.text()
        newbasename = newbasename.lower()
        parentname = self.myPNTaxa.taxaname
        if len(newauthors) == 0:
            ined = ' ined.'
        elif self.window.publishedComboBox.currentIndex() == 0:
            ined = ''
        else:
            ined = ' ined.'
        taxa =''
        try:
            id_rank = self.data_rank[self.window.rankComboBox.currentIndex()]
            prefix = data_prefix[id_rank]
            if len(prefix) > 0:
                prefix = " " + prefix
            taxa = parentname + prefix + " " + newbasename
        except Exception:
            taxa = newbasename.title()
        self._taxaname = taxa
        taxa = taxa + ' ' + newauthors + ined
        taxa = re.sub(' +', ' ', taxa.strip())
        self.window.taxaLineEdit_result.setText(taxa)
        _apply = len(newbasename) > 3
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(_apply)


    def rankComboBox_setdata(self):
        sql_query = f"SELECT id_rank, taxonomy.pn_ranks_name(id_rank) as rank_name FROM taxonomy.pn_ranks_children({self.myPNTaxa.id_rank})"
        # #print (sql_query)
        query2 = QtSql.QSqlQuery (sql_query)
        self.window.rankComboBox.clear()
        self.data_rank = []
        index = -1
        # for _key, rank in commons.RANK_TYPOLOGY.items():
        #     self.window.rankComboBox.addItem(rank["rank_name"])
        #     self.data_rank.append(rank["id_rank"])
        #     if rank["id_rank"] == self.myPNTaxa.id_rank:
        #         index = self.window.rankComboBox.count()-1            
        while query2.next():
            self.window.rankComboBox.addItem(query2.value("rank_name"))
            self.data_rank.append(query2.value("id_rank"))
            if query2.value("id_rank") == self.myPNTaxa.id_rank:
                index = self.window.rankComboBox.count()-1
        index = max(index, 0)
        try:
            self.window.rankComboBox.setCurrentIndex(index)
        except Exception:
            return        

    def trview_childs_checked_click(self,checked_item):
        #slot to monitor the check state
        state = checked_item.checkState()
        if state == 2 :
            self.checked_parent(checked_item)
        elif state == 0:
            self.unchecked_child(checked_item)

        _apply = False
        if len(self.get_listcheck()) > 0:
            _apply = True
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(_apply)


        
    def unchecked_child(self, item):
        #recursive function to uncheck childs
        for row in range(0, item.rowCount()):
            item2 = item.child(row,0)
            if item2.isCheckable():
                item2.setCheckState(0)
            if item2.hasChildren():
                self.unchecked_child(item2)
        return

    def checked_parent(self, item):
        #recursive function to check parents
        try:
            item_parent = item.parent()
            if item_parent.isCheckable():
                item_parent.setCheckState(2)
                self.checked_parent(item_parent)
        except Exception:
            return



    def alter_category(self, index):
        #index = self.window.comboBox_searchAPI.currentIndex()
        if index == 0 : 
            self.window.label_2.setText("Add taxon")
            self.window.taxaLineEdit_result.setVisible(True)
            self.taxaLineEdit_setdata()
            return
        self.window.taxaLineEdit_result.setVisible(False)
        self.window.label_2.setText("Taxon not found")
        
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)
        #self.window.setCursor(Qt.WaitCursor)
        QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        #get data (list of dictionnary) from API class function get_children"
        # a list of childs elements
        #exemple {"id" : '10', "taxaname" : 'Truc bidule', "authors" : 'Not me', "rank" : 'Species', "idparent" : '1'}
        # note that the id_parent of each taxa except the first one must be in the list, if not it will excluded
         #tabwidget.addTab(widget, str(value))
        layout = self.window.tabWidget_main.currentWidget().layout()
        if layout is None:
            layout = QGridLayout()
            self.window.tabWidget_main.currentWidget().setLayout(layout)
        layout.addWidget(self.window.trView_childs)
        #layout.addWidget(self.window.label_3)
        # widget = QLabel()
        # widget.setText('Check the taxa to add')
        # layout.addWidget(widget)

        index = self.window.tabWidget_main.currentIndex()
        #_apibase = index.text().lower()
        _apibase = self.window.tabWidget_main.tabText(index).lower()
        # model = self.window.trView_childs.model()
        # item = QtGui.QStandardItem("Searching")
        # item1 = QtGui.QStandardItem("In base " + _apibase.capitalize())
        # model.appendRow([item, item1],)
        # self.window.trView_childs.update()
        if _apibase == 'taxref':
            _classeAPI = API_TAXREF(self.myPNTaxa)
        elif _apibase == 'endemia':
            _classeAPI = API_ENDEMIA(self.myPNTaxa)
        elif _apibase == 'powo':
            _classeAPI = API_POWO(self.myPNTaxa)
        elif  _apibase == 'florical':
            _classeAPI = API_FLORICAL(self.myPNTaxa)
        _classeAPI.get_children()
        table_taxa = _classeAPI.children
            #restore original cursor
        self.window.trView_childs.model().setRowCount(0)
        self.window.trView_childs.repaint()

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

        try:
            if len(table_taxa) == 0:
                return
        except Exception:
            return
        self.window.label_2.setText("No new taxa to add")
        #sort the list (except root = 0) according to taxaname and create self.table_taxa
        sort_taxa = []
        for taxa in table_taxa[1:]:
            sort_taxa.append(taxa["taxaname"])
        sort_taxa = sorted(sort_taxa)
        #add root first and then the sorted list
        self.table_taxa = []
        self.table_taxa.append(table_taxa[0])
        for taxa in sort_taxa:
            for taxa2 in table_taxa:
                if len(taxa)>0:
                    if taxa == taxa2["taxaname"]:
                        self.table_taxa.append(taxa2)

        #add special fields and construct the query
        _taxaname=''
        _parser=''        
        try:
            for taxa in self.table_taxa:
                _tabtaxa = taxa["taxaname"].split()
                _basename = _tabtaxa[-1]
                taxa["id_taxonref"] = 0
                taxa["basename"] = _basename
                taxa["authors"] = get_str_value(taxa["authors"])
                taxa["parent"] = self.get_table_taxa_item(taxa["idparent"],"taxaname")
                _taxaname += _parser +"'" +taxa["taxaname"] +"'"
                _parser=", "
        except Exception:
            pass
        
         #check the taxaname into the taxa tables, and alters the id_taxonref
        sql_query = "SELECT id_taxonref, original_name FROM taxonomy.pn_taxa_searchnames( array[_taxaname]) WHERE id_taxonref IS NOT NULL"        
        sql_query = sql_query.replace('_taxaname', _taxaname)
        query = QtSql.QSqlQuery (sql_query)
        #set the id_taxonref for taxa already existing into the taxonomy tables
        while query.next():
            for taxa in self.table_taxa:
                if taxa["taxaname"] == query.value("original_name"):
                    taxa["id_taxonref"] = query.value("id_taxonref")
        self.draw_result()

    def draw_result(self):
        model = self.window.trView_childs.model()
        model.setRowCount(0)
        model.setColumnCount(4)
        self.draw_list ()
        if model.rowCount() ==0:
            model.appendRow([QtGui.QStandardItem("No data   "), QtGui.QStandardItem("< Null Value >")],)
        self.window.trView_childs.hideColumn(2)
        self.window.trView_childs.hideColumn(3)
        self.window.trView_childs.expandAll()
        self.window.trView_childs.resizeColumnToContents(0)
        self.window.trView_childs.resizeColumnToContents(1)
        self.window.trView_childs.sortByColumn(1, Qt.AscendingOrder)

    def draw_list(self, id=0):
        #recursive function to build hierarchical tree according to idparent and id
        model = self.window.trView_childs.model()
        _search ="idparent"
        if id==0:
            #search for the input taxon as root
            #id = self.table_taxa[0]["id"]
            for taxa in self.table_taxa:
                if taxa["taxaname"] == self.myPNTaxa.taxaname:
                    id = taxa["id"]
                    break
            _search ="id"
        if id == 0 : 
            return
        
        for taxa2 in self.table_taxa:
            if taxa2[_search] == id:
                item = QtGui.QStandardItem(str(taxa2["rank"]))
                taxa2["item"] = item
                taxaref = str(taxa2["taxaname"]) + ' ' + str(taxa2["authors"])
                item1 = QtGui.QStandardItem(taxaref.strip())
                item2 = QtGui.QStandardItem(str(taxa2["id"]))
                item.setCheckable(False)
                ls_item_taxonref = []
                try:
                    ls_item_taxonref = model.findItems(str(id),Qt.MatchRecursive,2) #MatchExactly
                except Exception:
                    ls_item_taxonref = None

                if ls_item_taxonref:
                    _checkable = (taxa2["id_taxonref"] == 0)
                    if _checkable:
                        self.window.label_2.setText("Check taxa to add")
                    item.setCheckable(_checkable)
                    row = ls_item_taxonref[0].row()
                    index = ls_item_taxonref[0].index()
                    index0 = index.sibling(row,0)
                    #append a child to the item
                    model.itemFromIndex(index0).appendRow([item, item1, item2],)
                else:
                    model.appendRow([item, item1, item2],)
                    #to avoid infinite loop
                if taxa2["idparent"] != taxa2["id"]:
                    self.draw_list(taxa2["id"])
        # print (nb_toadd)
        # if nb_toadd > 0:
        #     self.window.label_2.setText("Check taxa to add")
        # else:
        #     self.window.label_2.setText("No new taxa to add")
    def get_table_taxa_item(self,id, key):
        try:
            for taxa in self.table_taxa:
                if taxa["id"] == id:
                    return taxa[key]
        except Exception:
            return ''
    def get_listcheck(self, id=0):
        #recursive function to build hierarchical tree according to idparent and id
        if id == 0:
            id = self.table_taxa[0]["id"]
        tab_result=[]
        for taxa in self.table_taxa:
            if taxa["idparent"] == id:
                item = taxa["item"]
                if item.checkState()==2:
                    #taxa["parent"] = taxaname
                    tab_result.append(taxa)
                tab_result += self.get_listcheck(taxa["id"],taxa["taxaname"])
        return tab_result

    def apply(self):
        code_error =''
        msg = ''
        self.updated = False        
        index = self.window.tabWidget_main.currentIndex()
        if index == 0 :
            newbasename = self.window.basenameLineEdit.text().strip()
            newauthors = self.window.authorsLineEdit.text().strip()            
            newpublished = self.window.publishedComboBox.currentText() == 'Published'
            if len(newauthors) == 0:
                newpublished = False
            str_newidrank = str(self.data_rank[self.window.rankComboBox.currentIndex()])
            str_newidparent = str(self.myPNTaxa.idtaxonref)

            sql_query = "SELECT id_taxonref, taxaname, coalesce(authors,'') as authors, id_rank"
            sql_query += "\nFROM taxonomy.pn_taxa_edit (0, '_basename', '_authors', '_idparent', '_idrank', _published, TRUE)"
            sql_query = sql_query.replace ("_basename", newbasename)
            sql_query = sql_query.replace ("_authors", newauthors)
            sql_query = sql_query.replace ("_published", str(newpublished))            
            sql_query = sql_query.replace ("_idparent", str_newidparent)
            sql_query = sql_query.replace ("_idrank", str_newidrank)
 
            result = QtSql.QSqlQuery (sql_query)
            code_error = result.lastError().nativeErrorCode ()
            if len(code_error) == 0:
                result.next()
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                              result.value("id_rank"), newpublished)
                self.apply_signal.emit([item])
                self.window.basenameLineEdit.setText('')
                self.window.authorsLineEdit.setText('')
                return
            else:
                msg = postgres_error(result.lastError())
                QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)
            
            return

        #for other tabs
        taxa_toAdd = self.get_listcheck()
        if taxa_toAdd is None:
            return
        if len(taxa_toAdd) == 0:
            return
        sql_text = "SELECT (taxonomy.pn_taxa_edit (0, taxa.basename, taxa.authors, taxa.id_parent, taxa.id_rank, TRUE, TRUE)).* FROM"
        sql_text += "\n(SELECT '_basename' AS basename, '_authors' AS authors, b.id_rank, a.id_taxonref AS id_parent"
        sql_text += "\nFROM taxonomy.taxa_reference a, taxonomy.taxa_rank b WHERE lower(a.taxaname) = '_parentname' AND lower(b.rank_name) ='_rankname') taxa"
        self.updated_datas = []
        for taxa in taxa_toAdd:
            sql_query = sql_text.replace('_basename', taxa["basename"])
            sql_query = sql_query.replace('_authors', taxa["authors"])
            sql_query = sql_query.replace('_parentname', taxa["parent"].lower())
            sql_query = sql_query.replace('_rankname', taxa["rank"].lower())
            #use the basename if parent has only one word
            if len(taxa["parent"].split()) == 1:
                sql_query = sql_query.replace('lower(a.taxaname)', 'lower(a.basename)')
            #print (sql_query)
            result = QtSql.QSqlQuery (sql_query)
            code_error = result.lastError().nativeErrorCode ()
            if len(code_error) == 0:
                result.next()
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                              result.value("id_rank"), 'True')
                self.updated_datas.append(item)
                
                # self.window.basenameLineEdit.setText('')
                # self.window.authorsLineEdit.setText('')
                for taxa2 in self.table_taxa:
                    if taxa2["id"] == taxa["id"]:
                        taxa2["id_taxonref"]=1000 #set to an abitrary number to exclude from new taxa
        self.apply_signal.emit(self.updated_datas)
        self.draw_result()
        self.updated = True

    def close(self):
        self.window.close()

    def show(self):
        self.window.show()
        self.window.exec_()

#edit a taxa and apply by emit signal 
class PN_edit_taxaname(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa): #mode_edit = 0 (edition), mode_edit = 1 (add), mode_edit = 2 (move)
        super().__init__()
        self.PNTaxa = myPNTaxa
        self.input_name =''
        self._taxaname = ''
        self.tab_parent_comboBox =[]
        self.parent_name = self.PNTaxa.parent_name
        self.window = uic.loadUi("pn_edittaxa.ui")
        self.window.setWindowTitle("Edit reference")        
        self.window.publishedComboBox.addItems(['True', 'False'])
        self.window.basenameLineEdit.setText(self.PNTaxa.basename)
        self.window.authorsLineEdit.setText(self.PNTaxa.authors)
        self.window.publishedComboBox.setCurrentText (str(self.PNTaxa.published))          
        
        self.window.basenameLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.authorsLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.publishedComboBox.activated.connect(self.taxaLineEdit_setdata)
        self.window.parent_comboBox.activated.connect(self.taxaLineEdit_setdata)
        
        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QDialogButtonBox.Apply)
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)


        
   
        #set the nomenclature statut
        # field_value = 'Unpublished'
        # if self.PNTaxa.published:
        #     field_value = 'Published'
        #field_value = str(self.PNTaxa.published)
        
        self.fill_parent_comboBox()
        self.taxaLineEdit_setdata()
        self.input_name = self.window.taxaLineEdit.text()
        #self.save_input_state()

    def fill_parent_comboBox(self):
        self.tab_parent_comboBox =[]
        id_rankparent = get_dict_rank_value(self.PNTaxa.id_rank,'id_rankparent')
        sql_query = "SELECT id_taxonref, taxaname, coalesce(authors,'')::text authors FROM taxonomy.taxa_names"
        sql_query += "\nWHERE id_rank >=" + str(id_rankparent)
        sql_query += "\nAND id_rank <" + str(self.PNTaxa.id_rank)
        sql_query += "\n ORDER BY taxaname"
        query = QtSql.QSqlQuery(sql_query)
        i = 0
        index = -1
        while query.next():
            self.window.parent_comboBox.addItem (query.value("taxaname"))
            self.tab_parent_comboBox.append(query.value("id_taxonref"))
            if query.value("taxaname") == self.PNTaxa.parent_name:
                index = i
            i +=1
        self.window.parent_comboBox.setCurrentIndex(index)
        


    def taxaLineEdit_setdata(self):
        #newparent = self.window.parent_comboBox.currentText()
        newbasename = self.window.basenameLineEdit.text()
        newauthors = self.window.authorsLineEdit.text()
        newbasename = newbasename.lower()
        parentname = self.window.parent_comboBox.currentText() ##self.PNTaxa.parent_name
        ined = ''
        if len(newauthors) > 0 and self.window.publishedComboBox.currentIndex() == 1:
            ined = ' ined.'        
        taxa =''
        try:
            id_rank = self.PNTaxa.id_rank
            prefix = data_prefix[id_rank]
            if len(prefix) > 0:
                prefix = " " + prefix
            taxa = parentname + prefix + " " + newbasename
        except Exception:
            taxa = newbasename.title()
        self._taxaname = taxa
        taxa = taxa + ' ' + newauthors + ined
        taxa = re.sub(' +', ' ', taxa.strip())
        self.window.taxaLineEdit.setText(taxa)
        #if text is different than input text than activated apply button

        if len(self.input_name) == 0 : 
            return
        _apply = ((taxa != self.input_name) or 
                (self.parent_name !=self.window.parent_comboBox.currentText()))        
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(_apply)
        

    # def save_input_state(self):
    #     self.tab_input = []
    #     # self.tab_input.append(self.window.parentComboBox.currentText())
    #     self.tab_input.append(self.window.parent_comboBox.currentText())
    #     self.tab_input.append(self.window.basenameLineEdit.text())
    #     self.tab_input.append(self.window.authorsLineEdit.text())
    #     self.tab_input.append(self.window.publishedComboBox.currentText())

    def str_query_value(self, query_value):
        if query_value is None:
            return ''
        else:
            return str(query_value)

    def close(self):
        self.window.close()
        
    def apply(self):
        code_error =''
        msg = ''
        self.updated = False
        newbasename = self.window.basenameLineEdit.text().strip()
        published = (self.window.publishedComboBox.currentIndex() == 0)  
        str_idtaxonref = str(self.PNTaxa.idtaxonref)
        newauthors = self.window.authorsLineEdit.text().strip()
        str_newidparent = str(self.tab_parent_comboBox[self.window.parent_comboBox.currentIndex()])
        # str_newidrank = str(self.data_rank[self.window.rankComboBox.currentIndex()])
        
        sql_query = "SELECT id_taxonref, taxaname, coalesce(authors,'') as authors, id_rank"
        sql_query += "\nFROM taxonomy.pn_taxa_edit (_idtaxonref, '_basename', '_authors', _newidparent, NULL, '_published', TRUE)"
        sql_query = sql_query.replace ("_idtaxonref", str_idtaxonref)
        sql_query = sql_query.replace ("_basename", newbasename)
        sql_query = sql_query.replace ("_authors", newauthors)
        sql_query = sql_query.replace ("_newidparent", str_newidparent)       
        # sql_query = sql_query.replace ("_idparent", str_newidparent)
        # sql_query = sql_query.replace ("_idrank", str_newidrank)
        sql_query = sql_query.replace ("_published", str(published))
        #print (sql_query)
        result = QtSql.QSqlQuery (sql_query)
        code_error = result.lastError().nativeErrorCode ()
        if len(code_error) == 0:

        #fill tlview with query result
            self.updated_datas = []
            #i = 0
            while result.next():
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                              result.value("id_rank"), published)
                self.updated_datas.append(item)
                #i +=1
            self.input_name = self.window.taxaLineEdit.text()
            self.parent_name = self.window.parent_comboBox.currentText()
            self.apply_signal.emit(self.updated_datas)
            self.taxaLineEdit_setdata()
            self.updated = True
            return True
        # elif code_error == '23505':
        #     msg = "Error: Duplicate key value violates unique constraint"
        #     msg +="\n\nThe name: " + self._taxaname + " already exist in the taxonomic namespace"
        else:
            msg = postgres_error(result.lastError())
            #msg += "\n\n" + result.lastError().text()
        QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)
        
        return self.updated

    def show(self):
        self.window.show()
        self.window.exec_()

class PN_move_taxaname(QtWidgets.QMainWindow):
    def __init__(self, myPNTaxa, merge = False): # move toward a same id_rank if merge
        super().__init__()
        self.PNTaxa = myPNTaxa
        self.merge = merge
        self.window = uic.loadUi("pn_movetaxa.ui")
        model = QtGui.QStandardItemModel()
        #tab_header = []
        #tab_header.append('Current Taxa name')
        #tab_header.append('Category')
        # tab_header.append('New Taxa name')
        # model.setHorizontalHeaderLabels(tab_header)
        # self.window.tableView_newtaxa.setModel(model)
        # self.window.tableView_newtaxa.horizontalHeader().setStretchLastSection(True)
        self.window.comboBox_category.addItems(['Nomenclatural', 'Taxinomic'])
        self.window.comboBox_category.setCurrentIndex(0)
        self.window.comboBox_taxa.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.window.comboBox_taxa.activated.connect(self.set_newtaxanames)

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['Rank','Taxon'])
        # self.window.trView_childs.setModel(model)
        # self.window.trView_childs.setColumnWidth(0,250)
        # self.window.trView_childs.setHeaderHidden(True)  

        button_OK = self.window.buttonBox
        button_OK.button(QDialogButtonBox.Apply).clicked.connect (self.accept) 
        button_OK.button(QDialogButtonBox.Close).clicked.connect (self.close) #button_OK.accepted.connect (self.accept) 
        #button_OK.rejected.connect (self.close)

        #initialize list and dictionnary
        self.comboBox_taxa_query = None
        self.updated = False
        self.parent = self.PNTaxa.parent_name
        self.window.categoryLabel.setVisible(self.merge)
        self.window.comboBox_category.setVisible(self.merge)

        #check for mode
        if self.merge:

            
            self.idrankmin = self.PNTaxa.id_rank
            self.idrankmax = self.PNTaxa.id_rank + 1
            self.parent = self.PNTaxa.taxaname
            #self.window.comboBox_category.activated.connect(self.alter_category)
            self.window.setWindowTitle("Merge reference")
            self.window.taxaLineEdit.setText(self.PNTaxa.taxonref)
            self.window.taxaLabel.setText("Merge")
            self.window.toLabel.setText("With")
            self.comboBox_taxa_setdata()
        else: #Move

            self.idrankmin = self.PNTaxa.id_rankparent
            self.idrankmax = self.PNTaxa.id_rank
            self.window.setWindowTitle("Move reference")
            self.window.taxaLabel.setText("Move")
            self.window.toLabel.setText("To")
            self.window.taxaLineEdit.setText(self.PNTaxa.taxonref)
            #self.window.comboBox_taxa.activated.connect(self.set_newtaxanames) 
            self.comboBox_taxa_setdata()

    @property
    def selecteditem(self):
        index = self.window.comboBox_taxa.currentIndex()
        self.comboBox_taxa_query.seek(index)
        return PNTaxa (self.comboBox_taxa_query.value("id_taxonref"), 
                        self.comboBox_taxa_query.value("taxaname"),
                        self.comboBox_taxa_query.value("authors"),
                        self.comboBox_taxa_query.value("id_rank"),
                        )

    #alter the sign of merge taxa
    # def alter_category(self):
    #     model = self.window.trView_childs.model()
    #     if model.rowCount() == 0:
    #         return
    #     txt_value = model.item(0,1).data(0)
    #     if self.window.comboBox_category.currentIndex() == 0:
    #         txt_value = txt_value.replace(chr(61), chr(8801))
    #     else:
    #         txt_value = txt_value.replace(chr(8801), chr(61))
    #     model.item(0,1).setText(txt_value)
        
    #return a str value (change None in '')
    def str_query_value(self, query_value):
        if str(query_value).lower() in ['','null']:
            return ''
        else:
            return str(query_value)

    def set_newtaxanames(self):
        index = self.window.comboBox_taxa.currentIndex()
        self.comboBox_taxa_query.seek(index)
        str_idtaxonref = str(self.PNTaxa.idtaxonref)
        str_idnewparent = str(self.selecteditem.idtaxonref)
        # model = self.window.trView_childs.model()
        # model.setRowCount(0)
        # model.setColumnCount(4)
        _rankname = self.selecteditem.rank_name #commons.get_dict_rank_value(self.selecteditem.idtaxonref.id_rank,'rank_name')
        # item =  QtGui.QStandardItem(_rankname)
        # item1 = QtGui.QStandardItem(self.selecteditem.taxonref)
        # item2 = QtGui.QStandardItem(str_idnewparent)
        # item3 = QtGui.QStandardItem(str(self.selecteditem.rank_name))
        txt_taxa = 'Move Taxon to new ' + self.selecteditem.rank_name
        self.sql_query_save = ''
        # sql_function = "taxonomy.pn_taxa_move"
        if self.merge:
            category_synonym = chr(8801)
            if self.window.comboBox_category.currentIndex() > 0:
                category_synonym = chr(61)
            txt_taxa = self.PNTaxa.taxonref +  ' ' + category_synonym + ' ' +self.selecteditem.taxonref
            # item1 = QtGui.QStandardItem(txt_taxa)
            # item2 = QtGui.QStandardItem(str_idtaxonref)
            # sql_function = "taxonomy.pn_taxa_merge"
        self.window.label_result.setText(txt_taxa)

        #model.appendRow([item, item1, item2, item3],)
        category = self.window.comboBox_category.currentText()
        
        # sql_function += "(" + str_idtaxonref +"," + str_idnewparent + ",$$" + category + "$$," + "FALSE" + ") a"
        # self.sql_query_save = "SELECT a.id_taxonref, a.taxaname, a.authors, a.id_rank FROM " + sql_function

        # sql_query = "SELECT a.id_taxonref, a.taxaname, a.authors, a.id_rank, a.id_parent, CONCAT_WS (' ',a.taxaname, a.authors) AS new_taxonref,"
        # sql_query += "(b.taxaname IS NULL) AS isvalid FROM "
        # sql_query += sql_function #+ "(" + str_idtaxonref +"," + str_idnewparent + ",$$" + category + "$$," + "FALSE" + ") a"
        # sql_query += "\nLEFT JOIN taxonomy.taxa_reference b ON a.taxaname = b.taxaname"
        # sql_query += " ORDER BY id_rank, a.taxaname"
        if self.merge:
            sql_query = f"CALL taxonomy.pn_taxa_set_synonymy({str_idtaxonref}, {str_idnewparent}, '{category}');"
            
        else:
            sql_query = "UPDATE taxonomy.taxa_reference SET id_parent = " + str_idnewparent + " WHERE id_taxonref = " + str_idtaxonref
        #print  (sql_query)
        # self.window.trView_childs.hideColumn(2)
        # self.window.trView_childs.hideColumn(3)
        # self.window.trView_childs.expandAll()
        # self.window.trView_childs.resizeColumnToContents(0)

        #query = QtSql.QSqlQuery (sql_query)
        #self.sql_query_save = sql_query
        return sql_query

        

    def comboBox_taxa_setdata(self):
        str_minidrank = str(self.idrankmin)
        str_maxidrank = str(self.idrankmax)
        sql_query = "SELECT a.id_taxonref, a.basename, a.id_rank, a.taxaname, a.authors, a.taxonref"
        sql_query += "\nFROM taxonomy.taxa_names a"
        #sql_query += "\nLEFT JOIN taxonomy.taxa_rank b ON b.id_rank = a.id_rank"
        #sql_query += "\nWHERE a.id_rank >=" + str_minidrank 
        if self.idrankmin < 21:
            sql_query += "\nWHERE a.id_rank >=" + str_minidrank +" AND a.id_rank < " + str_maxidrank
        else:
            sql_query += "\nWHERE a.id_rank >=21"
        sql_query += "\nORDER BY taxonref"
        #print (sql_query)
        index = -1
        self.comboBox_taxa_query = QtSql.QSqlQuery (sql_query)
        while self.comboBox_taxa_query.next():
            self.window.comboBox_taxa.addItem(str(self.comboBox_taxa_query.value('taxonref')))
            if self.comboBox_taxa_query.value('taxaname') == self.parent:
                index = self.window.comboBox_taxa.count()-1
        self.window.comboBox_taxa.setCurrentIndex(index)

    def close(self):
        self.window.close()
        
    def accept(self):
        code_error =''
        msg = ''
        self.updated = False
        self.sql_query_save = self.set_newtaxanames()
        if len(self.sql_query_save)>0:
            sql_query = self.sql_query_save #.replace("FALSE","TRUE")
            result = QtSql.QSqlQuery (sql_query)
            code_error = result.lastError().nativeErrorCode ()
       
        if len(code_error) == 0:
            self.updated_datas = []
            str_idnewparent = str(self.comboBox_taxa_query.value("id_taxonref"))
            sql_query = f"SELECT * FROM taxonomy.pn_taxa_childs({str_idnewparent}, FALSE)"
            result = QtSql.QSqlQuery (sql_query)
            while result.next():
                self.updated_datas.append(PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                                 result.value("id_rank")))
            self.updated = True
            self.close() 
            return True
        else:
            msg = postgres_error(result.lastError())
        QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)

        return self.updated
        


    def show(self):
        self.window.show()
        self.window.exec_()




 
# def createConnection(db):
#     db.setHostName("localhost")
#     db.setDatabaseName("amapiac")
#     db.setUserName("postgres")
#     db.setPassword("postgres")
#     #app2 = QApplication([])
#     if not db.open():
#         QMessageBox.critical(None, "Cannot open database", "Unable to open database, check for connection parameters", QMessageBox.Cancel)
#         return False
#     return True

# if __name__ == '__main__':
#     app=QtWidgets.QApplication(sys.argv)
    
   
# #connection to the database
#     db = QtSql.QSqlDatabase.addDatabase("QPSQL")
#     if not createConnection(db):
#         sys.exit("error")     
    
#     win = PN_edit_taxaname(QtSql, 1062,True)
#     win2 = PN_move_taxaname(QtSql, 6314, True)
#     win.show()
#     win2.show()
    
#    # app.exec_()
#     sys.exit(app.exec_())

       
    # def set_treeView_parent(self):
    #     #str_idtaxonref = str(self.idtaxonref)
        
    #     str_minidrank = str(self.id_requiredrankparent)
    #     str_maxidrank = str(self.idrank)
    #     sql_where = "\nWHERE id_rank >=" + str_minidrank + " AND id_rank < " + str_maxidrank

    #    # sql_where = "\nWHERE id_rank >=" + str(self.idrank)+ " AND id_rank < " + str(self.idrank+1)
        
    #    # sql_where = "\nWHERE id_rank =" + str(self.idrank) #+ "AND id_rank < " + str_maxidrank
    # #construct the Query statement, based on the Union betweens parents and childs 

    #     sql_query = "SELECT a.id_taxonref,  taxonomy.pn_taxa_rankname(a.id_rank) AS rank_name, a.taxonref, a.id_parent FROM"
    #     sql_query += "\n(SELECT id_taxonref, id_rank, id_parent, CONCAT_WS (' ',taxaname, authors) AS taxonref"    
    #     sql_query += "\nFROM taxonomy.taxa_reference) a "
    #     sql_query += sql_where
    #     sql_query += "\nORDER BY a.id_rank, a.taxonref"
    #     model = QtGui.QStandardItemModel()
    #     model.setHorizontalHeaderLabels(['Rank','Taxon'])
    #     self.window.treeView_parent.setModel(model)
    #     self.window.treeView_parent.header().setDefaultAlignment(QtCore.Qt.AlignCenter)
        
    #     model = self.window.treeView_parent.model()
    #     model.setRowCount(0)
    #     model.setColumnCount(2)
    #     self.window.treeView_parent.setColumnWidth(0,150)
    #     font = QtGui.QFont()
    #     font.setBold(True)
    #     key_index = None
    #     query = QtSql.QSqlQuery (sql_query)
    #     while query.next():
    #         ls_item_taxonref = []
    #         ls_item_taxonref = model.findItems(str(query.value('id_parent')),Qt.MatchRecursive,1) #MatchExactly
    #        # item = QtGui.QStandardItem(query.value('rank_name'))
    #         item1 = QtGui.QStandardItem(query.value('taxonref'))
    #         item2 = QtGui.QStandardItem(str(query.value('id_taxonref')))

    #         if ls_item_taxonref:
    #             #get the first col of the QStandardItem
    #             row = ls_item_taxonref[0].row()
    #             index = ls_item_taxonref[0].index()
    #             index0 = index.sibling(row,0)
    #             #append a child to the item
    #             model.itemFromIndex(index0).appendRow([item1, item2],)
    #             #get a reference to the last append item
    #             key_row = model.itemFromIndex(index0).rowCount()-1
    #             key_item = model.itemFromIndex(index0).child(key_row,0)
    #         else:
    #             #append as a new line if item not found (or first item)
    #             model.appendRow([item1, item2],)
    #             key_item = model.item(model.rowCount()-1)
    #         #set bold the current id_taxonref line (2 first cells)
    #         if query.value('id_taxonref') == self.idparent:
    #             key_index = key_item.index()
    #             key_row = key_item.row()
    #             model.setData(key_index, font, Qt.FontRole)
    #             key_index = key_index.sibling(key_row,1)
    #             model.setData(key_index, font, Qt.FontRole)
    #     self.window.treeView_parent.setCurrentIndex (key_index)
    #     self.window.treeView_parent.hideColumn(1)
    #     self.window.treeView_parent.expandAll()
