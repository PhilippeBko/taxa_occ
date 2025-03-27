import re
import sys
import json

from PyQt5 import QtCore, QtGui, QtWidgets, QtSql, uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialogButtonBox, QGridLayout, QApplication, QCompleter

########################################
from models.api_thread import API_TAXREF, API_ENDEMIA, API_POWO, API_FLORICAL
from core.widgets import PN_TaxaSearch
from core import functions as commons
########################################
#data_prefix = {11:'subfam.', 12:'tr.', 13:'subtr.', 15:'subg.', 16:'sect.', 17:'subsect.',18:'ser.',19:'subser.',21:'',22:'subsp.',23:'var.',25:'f.',28:'cv.',31:'x'}

# Main classe to store a taxaname with some properties
class PNTaxa(object):
    def __init__(self, idtaxonref, taxaname, authors, idrank, published = None):
        self.authors = authors
        self.taxaname = taxaname
        self.id_rank = idrank
        self.id_taxonref = idtaxonref
        self.published = published
        self.api_score = 0
        self.parent_name = None
        self.dict_species = commons.get_dict_from_species(self.taxaname)
        if self.dict_species is None:
            self.dict_species = {}

    def field_dbase(self, fieldname):
        """get a field value from the table taxonomy.taxa_reference according to a id_taxonref"""
        sql_query = f"""
                    SELECT 
                        {fieldname} 
                    FROM
                        taxonomy.taxa_names
                    WHERE
                        id_taxonref = {self.id_taxonref}
                   """
        query = QtSql.QSqlQuery(sql_query)
        query.next()
        return query.value(fieldname)

    @property
    def idtaxonref(self):
        try:
            return int(self.id_taxonref)
        except Exception:
            return 0
    
    # @property 
    # def authors (self):
    #     return self._authors
    # @authors.setter ##/to suppress Null values from database
    # def authors (self, value):
    #     self._authors = commons.get_str_value(value)

    # @property 
    # def published (self):
    #     return self._published        
    # @published.setter
    # def published (self, value):
    #     value = commons.get_str_value(value).lower()
    #     if value == 'false':
    #         self._published = False
    #     elif value == 'true':
    #         self._published = True
    #     else:
    #         self._published = None



    @property
    def rank_name (self):
        try :
            txt_rk = commons.get_dict_rank_value(self.id_rank, 'rank_name')
        except Exception:
            txt_rk = 'Unknown'
        return txt_rk

    @property
    def id_rankparent (self):
        try :
            id_rp = commons.get_dict_rank_value(self.id_rank, 'id_rankparent')
        except Exception:
            id_rp = None
        return id_rp

    @property
    def taxonref(self):
        try :
            return " ".join([self.taxaname,self.authors]).strip()
        except Exception:
            return self.taxaname

    @property
    def isautonym (self):
        if self.id_rank not in [22,23]:
            return False
        return self.dict_species.get ("autonym", None)

    @property
    def basename (self):
        if self.id_rank < 21:
            return self.taxaname.lower()
        return self.dict_species.get ("basename", None)

    @property
    def simple_taxaname (self):
        if self.id_rank < 21:
            return self.taxaname
        return self.dict_species.get ("name", None)
    

    @property 
    def json_metadata (self):
    #load metadata json from database
        json_data = self.field_dbase("metadata")
        if not json_data:
            return
        json_data = json.loads(json_data)
        #sorted the result, assure to set web links and query time ending the dict
        for key, metadata in json_data.items():
            _links = {'_links': None, 'url':None, 'webpage':None, 'query time': None}
            _fields = {}
            for _key, _value in metadata.items():
                if _key.lower() in _links:
                    _links[_key] = _value
                else:
                    _fields[_key] = _value
            for _link, _url in _links.items():
                 if _url:
                    _fields[_link] = _url
            json_data[key] = _fields
        return json_data


    @property
    def json_names(self):
    #load all the similar names of the taxa to a json dictionnary 
        sql_query = f"""
                    SELECT 
                        a.name, 
                        a.category, 
                        a.id_category 
                    FROM 
                        taxonomy.pn_names_items({self.idtaxonref}) a 
                    ORDER BY 
                        a.name
                    """
        query = QtSql.QSqlQuery(sql_query)
        dict_db_names = {}
        while query.next():
            if query.value("id_category") < 5:
                _category = 'Autonyms'
            else:
                _category = query.value("category")
            if _category not in dict_db_names:
                dict_db_names[_category] = []
            dict_db_names[_category].append(query.value("name"))
        return dict_db_names

    @property
    def json_properties(self):
        """     
        Return a json (dictionnary of sub-dictionnaries of taxa properties taxa identity + field properties (jsonb)
        from a PNTaxa class
        """
        dict_db_properties = {}
        #create a copy of dict_properties with empty values
        for _key, _value in commons.list_db_properties.copy().items():
            dict_db_properties[_key] = {}.fromkeys(_value,'')

        #fill the identiy of the taxa, exit of error    
        tab_identity = dict_db_properties["identity"]
        try:
            tab_identity["authors"] =  self.authors
            if self.isautonym:
                tab_identity["published"] =  '[Autonym]'
            else:
                tab_identity["published"] =  str(self.published)
            tab_identity["name"] =  self.basename     
        except Exception:
            return
        
        #fill the properties from the json field properties annexed to the taxa        
        try:
            json_props = self.field_dbase("properties")
            json_props = json.loads(json_props)
            for _key, _value in dict_db_properties.items():
                try:
                    tab_inbase = json_props[_key]
                    if tab_inbase is not None:
                        for _key2, _value2 in tab_inbase.items():
                            _value2 = commons.get_str_value(_value2)
                            if _value2:
                                _value[_key2] = _value2.title()
                except Exception:
                    continue
        except Exception:
            pass
        return dict_db_properties


#class to generate a model (QAbstractTableModel) for QtableView widget to display taxa (PNTaxa) with red/green dot according to api_score (PNTaxa)
class TableModel(QtCore.QAbstractTableModel):
    header_labels = ['Taxa Name', 'Authors', 'Rank'] #, 'ID Taxon']
    def __init__(self, data = None):
        super(TableModel, self).__init__()
        self.PNTaxon = []
        self.PNTaxon = data if data is not None else []
    
    def resetdata(self, newdata = None):
        self.beginResetModel()
        self.PNTaxon = newdata if newdata is not None else []
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.header_labels[section]
        #return self.headerData(self, section, orientation, role)

    def delete (self, idtaxonref):
        ##delete one item in the list, NOT PERSISTENT IN DATABASE)
        self.PNTaxon = [x for x in self.PNTaxon if x.idtaxonref != idtaxonref]


    # def add (self, myPNTaxa):
    #     ##delete one item in the list, NOT PERSISTENT IN DATABASE)
    #     self.PNTaxon = [x for x in self.PNTaxon if x.idtaxonref != myPNTaxa.idtaxonref]


    def row_idtaxonref (self, idtaxonref):
        ##return the row index of the idtaxonref into the _data list
        for x in range(len(self.PNTaxon)):
            if self.PNTaxon[x].idtaxonref == idtaxonref:
                return x              
        return -1

    def refresh (self, myPNTaxa = None):
        ##By default refresh the entire
        # look for refresh id_taxonref if exists otherwise append the new row
        ##not persistent in the database
        if myPNTaxa is None:
            self.resetdata(self.PNTaxon)
        else:
            found = False
            for taxa in self.PNTaxon:
                if taxa.idtaxonref == myPNTaxa.idtaxonref:
                    found = True
                    taxa.taxaname = myPNTaxa.taxaname
                    taxa.authors = myPNTaxa.authors
                    taxa.id_rank = myPNTaxa.id_rank
                    if myPNTaxa.published is not None:
                        taxa.published = myPNTaxa.published
            if not found :
                self.PNTaxon.append(myPNTaxa)

    def data(self, index, role):
        if not index.isValid():
            return None
        if 0 <= index.row() < self.rowCount():
            item = self.PNTaxon[index.row()]
            col = index.column()        
            if role == Qt.DisplayRole:
                if col == 0:
                    return item.taxaname
                elif col == 1:
                    #is_published = item.published ##getattr(item, 'published', True)
                    _authors = str(item.authors)
                    if item.isautonym:
                        _authors = '[Autonym]'
                    elif _authors=='':
                        _authors = ''
                    elif not item.published:
                        _authors += ' ined.'
                    return _authors.strip()

                elif col == 2:
                    return item.rank_name
            elif role == Qt.UserRole:
                return item
            elif role == Qt.FontRole:
                #is_published = item.published ##getattr(item, 'published', True)
                if not item.published:
                    font = QtGui.QFont()
                    font.setItalic(True)
                    return font
            elif role == Qt.DecorationRole:
                if col == 0:
                    len_json = getattr(item, 'api_score', 0)
                    col = QtGui.QColor(255,0,0,0)
                    if 1<= len_json <= 2:
                        col = QtGui.QColor(255,128,0,255)
                    elif len_json == 3:
                        col = QtGui.QColor(255,255,0,255)
                    elif len_json >= 4:
                        col = QtGui.QColor(0,255,0,255)
                    px = QtGui.QPixmap(10,10)
                    px.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(px)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    px_size = px.rect().adjusted(2,2,-2,-2)
                    painter.setBrush(col)
                    painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
                        QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.drawEllipse(px_size)
                    painter.end()

                    return QtGui.QIcon(px)

    def rowCount(self, index=QtCore.QModelIndex()):
        # The length of the outer list.
        return len(self.PNTaxon)
        
    def columnCount(self, index=QtCore.QModelIndex()):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        try:
            return 2 #3 #self.PNTaxon[0].columnCount # len(self.PNTaxon[0])
        except Exception:
            return 0

    def additem (self, clrowtable):
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self.PNTaxon.append(clrowtable)
        self.endInsertRows()
        
#class to add a taxon
class PN_add_taxaname(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa): # move toward a same id_rank if merge
        super().__init__()
        self.myPNTaxa = myPNTaxa
        self.table_taxa = []
        self.data_rank = []
        self._taxaname = ''
        self.updated = False
        #set the ui
        self.window = uic.loadUi("ui/pn_addtaxa.ui")
        self.window.publishedComboBox.addItems(['True', 'False'])
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
            prefix = commons.get_dict_rank_value(id_rank, 'prefix')  ##data_prefix[id_rank]
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
        sql_query = f"""
                        SELECT 
                            id_rank, 
                            taxonomy.pn_ranks_name(id_rank) as rank_name 
                        FROM 
                            taxonomy.pn_ranks_children({self.myPNTaxa.id_rank})
                    """
        # #print (sql_query)
        query2 = QtSql.QSqlQuery (sql_query)
        self.window.rankComboBox.clear()
        self.data_rank = []
        index = -1
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
                taxa["authors"] = commons.get_str_value(taxa["authors"])
                taxa["parent"] = self.get_table_taxa_item(taxa["idparent"],"taxaname")
                _taxaname += _parser +"'" +taxa["taxaname"] +"'"
                _parser=", "
        except Exception:
            pass
        
         #check the taxaname into the taxa tables, and alters the id_taxonref
        sql_query = f"""
                        SELECT 
                            id_taxonref, 
                            original_name 
                        FROM 
                            taxonomy.pn_taxa_searchnames( array[{_taxaname}]) 
                        WHERE 
                            id_taxonref IS NOT NULL
                    """
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
                tab_result += self.get_listcheck(taxa["id"]) #,taxa["taxaname"])
        return tab_result

    def apply(self):
        code_error =''
        msg = ''
        self.updated = False        
        index = self.window.tabWidget_main.currentIndex()
        if index == 0 :
            newbasename = self.window.basenameLineEdit.text().strip()            
            newpublished = (self.window.publishedComboBox.currentIndex() == 0)
            newauthors = self.window.authorsLineEdit.text().strip()
            newidparent = self.myPNTaxa.idtaxonref
            newidrank = self.data_rank[self.window.rankComboBox.currentIndex()]
            #create the pn_taxa_edit query function (internal to postgres)
            if len(newauthors) == 0:
                newpublished = False
            sql_query = f"""
                            SELECT 
                                id_taxonref, 
                                taxaname, 
                                coalesce(authors,'') as authors, 
                                id_rank
                            FROM taxonomy.pn_taxa_edit (0, '{newbasename}', '{newauthors}', {newidparent}, {newidrank}, {newpublished}, TRUE)
                        """
            result = QtSql.QSqlQuery (sql_query)
            code_error = result.lastError().nativeErrorCode ()
            if len(code_error) == 0:
                self.updated_datas = []
                while result.next():
                    item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                result.value("id_rank"), newpublished)
                    self.updated_datas.append(item)

                self.apply_signal.emit(self.updated_datas)
                self.window.basenameLineEdit.setText('')
                self.window.authorsLineEdit.setText('')
                return
            else:
                msg = commons.postgres_error(result.lastError())
                QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)
            return

        #for other tabs
        taxa_toAdd = self.get_listcheck()
        if taxa_toAdd is None:
            return
        if len(taxa_toAdd) == 0:
            return
        sql_text = """SELECT 
                        (taxonomy.pn_taxa_edit (0, taxa.basename, taxa.authors, taxa.id_parent, taxa.id_rank, TRUE, TRUE)).* 
                       FROM
                        (
                            SELECT 
                                '_basename' AS basename, 
                                '_authors' AS authors, 
                                _idrank as id_rank, 
                                a.id_taxonref AS id_parent
                            FROM
                                taxonomy.taxa_names a
                            WHERE 
                                lower(a.taxaname) = '_parentname'
                    """

        # sql_text = "SELECT (taxonomy.pn_taxa_edit (0, taxa.basename, taxa.authors, taxa.id_parent, taxa.id_rank, TRUE, TRUE)).* FROM"
        # sql_text += "\n(SELECT '_basename' AS basename, '_authors' AS authors, b.id_rank, a.id_taxonref AS id_parent"
        # sql_text += "\nFROM taxonomy.taxa_reference a, taxonomy.taxa_rank b WHERE lower(a.taxaname) = '_parentname' AND lower(b.rank_name) ='_rankname') taxa"


        self.updated_datas = []
        for taxa in taxa_toAdd:
            sql_query = sql_text.replace('_basename', taxa["basename"])
            sql_query = sql_query.replace('_authors', taxa["authors"])
            sql_query = sql_query.replace('_parentname', taxa["parent"].lower())
            sql_query = sql_query.replace('_idrank', str(commons.get_dict_rank_value(taxa["rank"], "id_rank")))

            #sql_query = sql_query.replace('_rankname', taxa["rank"].lower())
            #use the basename if parent has only one word
            # if len(taxa["parent"].split()) == 1:
            #     sql_query = sql_query.replace('lower(a.taxaname)', 'lower(a.basename)')
            
            #print (sql_query)
            result = QtSql.QSqlQuery (sql_query)
            code_error = result.lastError().nativeErrorCode ()
            if len(code_error) == 0:
                result.next()
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                              result.value("id_rank"), 'True')
                self.updated_datas.append(item)
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
        #set the ui 
        self.window = uic.loadUi("ui/pn_edittaxa.ui")
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
        self.fill_parent_comboBox()
        self.taxaLineEdit_setdata()
        self.input_name = self.window.taxaLineEdit.text()

    def fill_parent_comboBox(self):
        self.tab_parent_comboBox =[]
        id_rankparent = commons.get_dict_rank_value(self.PNTaxa.id_rank,'id_rankparent')
        sql_query = f"""SELECT 
                            id_taxonref, 
                            taxaname, 
                            coalesce(authors,'')::text authors 
                        FROM 
                            taxonomy.taxa_names
                        WHERE 
                            id_rank >= {id_rankparent}
                        AND
                            id_rank < {self.PNTaxa.id_rank}
                        ORDER 
                            BY taxaname
                    """
        # sql_query = "SELECT id_taxonref, taxaname, coalesce(authors,'')::text authors FROM taxonomy.taxa_names"
        # sql_query += "\nWHERE id_rank >=" + str(id_rankparent)
        # sql_query += "\nAND id_rank <" + str(self.PNTaxa.id_rank)
        # sql_query += "\n ORDER BY taxaname"
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
            prefix = commons.get_dict_rank_value(id_rank, 'prefix') #data_prefix[id_rank]
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
        
    def close(self):
        self.window.close()
        
    def apply(self):
        code_error =''
        msg = ''
        self.updated = False 
        idtaxonref = self.PNTaxa.idtaxonref
        newbasename = self.window.basenameLineEdit.text().strip()
        published = (self.window.publishedComboBox.currentIndex() == 0) 
        newauthors = self.window.authorsLineEdit.text().strip()
        newidparent = self.tab_parent_comboBox[self.window.parent_comboBox.currentIndex()]
        #create the pn_taxa_edit query function (internal to postgres)
        if len(newauthors) == 0:
            published = False
        sql_query = f"""
                    SELECT 
                        id_taxonref, 
                        taxaname, 
                        coalesce(authors,'') as authors, 
                        id_rank
                    FROM 
                        taxonomy.pn_taxa_edit ({idtaxonref}, '{newbasename}', '{newauthors}', {newidparent}, NULL, {published}, TRUE)       
        """
        #print (sql_query)
        result = QtSql.QSqlQuery (sql_query)
        code_error = result.lastError().nativeErrorCode ()
        if len(code_error) == 0:
            self.updated_datas = []
            while result.next():
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                              result.value("id_rank"), published)
                self.updated_datas.append(item)
            self.apply_signal.emit(self.updated_datas)
            
            self.input_name = self.window.taxaLineEdit.text()
            self.parent_name = self.window.parent_comboBox.currentText()
            self.taxaLineEdit_setdata()
            self.updated = True
            return True
        else:
            msg = commons.postgres_error(result.lastError())
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
        self.window = uic.loadUi("ui/pn_movetaxa.ui")
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
        self.window.setMaximumHeight(1)
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
    # def str_query_value(self, query_value):
    #     if str(query_value).lower() in ['','null']:
    #         return ''
    #     else:
    #         return str(query_value)

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
        if self.idrankmin < 21:
            sql_query += f"\nWHERE a.id_rank >= {str_minidrank} AND a.id_rank < {str_maxidrank}"
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
            msg = commons.postgres_error(result.lastError())
        QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)

        return self.updated

    def show(self):
        self.window.show()
        self.window.exec_()

class PNSynonym(object):
    def __init__(self, synonym = None, taxonref = None, idtaxonref = 0, category = 'Orthographic'):
        self.synonym = synonym
        self.category = category
        self.taxon_ref = taxonref
        self.id_taxonref = idtaxonref
        #self.keyname =''

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

####################
# Class to edit(New or update) synonym
# add/update a new synonym to a idtaxonref or search for a idtaxonref (PN_TaxaSearch) according to a synonym 
class PN_edit_synonym (QtWidgets.QWidget):
    button_click = pyqtSignal(object, int)
    def __init__(self, myPNSynonym):
        super().__init__()
        self.ui_addname = uic.loadUi("ui/pn_editname.ui")
        self.Qline_name = self.ui_addname.name_linedit
        self.Qline_ref = self.ui_addname.taxaLineEdit
        self.Qcombobox = self.ui_addname.comboBox
        buttonbox = self.ui_addname.buttonBox
        self.button_cancel = buttonbox.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_ok = buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        self.myPNSynonym = myPNSynonym
        self.treeview_searchtaxa = PN_TaxaSearch()
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
            #add the treeview_searchtaxa = Class PN_TaxaSearch() (cf. taxa_model.py)
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
            msg = commons.postgres_error(result.lastError())
        QtWidgets.QMessageBox.critical(self.ui_addname, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return False

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.table = QtWidgets.QTableView()

        data = [
           PNTaxa(123,'Miconia', 'DC.', 14,0),
           PNTaxa(124,'Miconia calvescens', 'DC.', 21,1)
        #  # PNTaxa(1456,'Sapotaceae', 'L.', 10),
         ]
        #self.model = TableModel(data)
        self.model = TableModel()
        self.model.resetdata(data)
        self.table.setModel(self.model)
        #self.model.additem(PNTaxa(1456,'Sapotaceae', 'L.', 10, 2))
        #self.model.additem(PNTaxa(1800,'Arecaceae', 'L.', 10, 3))

        self.setCentralWidget(self.table)

if __name__ == '__main__':
    app=QtWidgets.QApplication(sys.argv)

    window=MainWindow()
    window.show()
    app.exec_()