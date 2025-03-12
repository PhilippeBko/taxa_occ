import re
import sys
import json
from PyQt5 import QtCore, QtGui, QtWidgets, QtSql, uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTreeView, QWidget, QLineEdit, QVBoxLayout, QMessageBox, QDialogButtonBox, QGridLayout, QApplication, QCompleter
from api_thread import API_TAXREF, API_ENDEMIA, API_POWO, API_FLORICAL
import commons
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
        """ 
            get a field value from the table taxonomy.taxa_reference according to a id_taxonref
        """
        if fieldname == 'taxonref':
            fieldname = 'CONCAT_WS (' ',taxaname, authors) AS taxonref'
        sql_txt = "SELECT " + fieldname + " FROM taxonomy.taxa_names"
        sql_txt += "\nWHERE id_taxonref = " + str(self.id_taxonref)
        query = QtSql.QSqlQuery(sql_txt)
        query.next()
        return query.value(fieldname)

    @property
    def idtaxonref(self):
        try:
            return int(self.id_taxonref)
        except Exception:
            return 0
    
    @property 
    def authors (self):
        return self._authors
    @authors.setter ##/to suppress Null values from database
    def authors (self, value):
        self._authors = commons.get_str_value(value)

    @property 
    def published (self):
        return self._published        
    @published.setter
    def published (self, value):
        value = commons.get_str_value(value).lower()
        if value == 'false':
            self._published = False
        elif value == 'true':
            self._published = True
        else:
            self._published = None

    @property
    def rank_name (self):
        try :
            txt_rk = commons.get_dict_rank_value(self.id_rank, 'rank_name')
            #txt_rk = PNTaxa.dict_rank[self.id_rank]
        except Exception:
           # txt_rk = PNTaxa.dict_rank[0]
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
        #dict_name = commons.get_dict_from_species (self.taxaname)
        return self.dict_species.get ("autonym", None) #return self.dict_species["autonym"]

    @property
    def basename (self):
        if self.id_rank < 21:
            return self.taxaname.lower()
        #dict_name = commons.get_dict_from_species (self.taxaname)
        return self.dict_species.get ("basename", None) #self.dict_species["basename"]

    @property
    def simple_taxaname (self):
        #_tabname = self.taxaname.split ()
        if self.id_rank < 21:
            #_tabname = self.taxaname.split () #_tabname[0:1]
            return self.taxaname
        #dict_name = commons.get_dict_from_species (self.taxaname)
        return self.dict_species.get ("name", None) #return self.dict_species["name"]
    @property
    def json_properties(self):
        """     
        Return a json (dictionnary of sub-dictionnaries of taxa properties taxa identity + field properties (jsonb)
        from a PNTaxa class
        """
        dict_db_properties = {}
        #selecteditem = myPNTaxa
        # if selecteditem  is None: 
        #     return
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
                            if _value2 !='':
                                _value[_key2] = _value2.title()
                except Exception:
                    continue
        except Exception:
            pass
        return dict_db_properties
    

    # @propertyy
    # def columnCount(self):
    #     return 3

    # @property
    # def api_json (self):
    #     try:
    #         if len(self.json_request) > 0: 
    #             return self.json_request
    #         else:
    #             return None
    #     except:
    #         return None

    # @property
    # def len_json_request(self):
    #     #return the length of the json_request field      
    #     try:
    #         return (len(json.loads(self.json_request)))
    #     except:
    #         return 0

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
# add/update a new synonym to a idtaxonref or search for a idtaxonref (PN_taxa_search_widget) according to a synonym 
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
        self.treeview_searchtaxa = PN_taxa_search_widget()
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
            #add the treeview_searchtaxa = Class PN_taxa_search_widget() (cf. taxa_model.py)
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
        
#class to display a search widget composed of a search text and and treeview result with  matched taxa and score
class PN_taxa_search_widget(QWidget):
    selectionChanged = pyqtSignal(str)
    doubleClicked = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        # load the GUI
        self.lineEdit_search_taxa = QLineEdit(self)
        self.treeview_scoretaxa = QTreeView(self)
        self.lineEdit_search_taxa.setPlaceholderText("search taxa")
        self.treeview_scoretaxa.setEditTriggers(QTreeView.NoEditTriggers)
        #set the model
        self.model = QtGui.QStandardItemModel()
        self.model.setColumnCount(2)
        self.treeview_scoretaxa.setModel(self.model)
        self.treeview_scoretaxa.setHeaderHidden(True)
        #connect slots
        self.treeview_scoretaxa.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.treeview_scoretaxa.doubleClicked.connect(self.on_doubleClicked)
        self.lineEdit_search_taxa.textChanged.connect(self.on_text_changed)
        # set the layout
        layout = QVBoxLayout()
        layout.addWidget(self.lineEdit_search_taxa)
        layout.addWidget(self.treeview_scoretaxa)
        self.setLayout(layout)
    
    def setText(self, newtext):
        self.lineEdit_search_taxa.setText(newtext)

    def currentIndex(self):
        return self.treeview_scoretaxa.currentIndex()
    
    def selectedTaxa(self):
        return self.treeview_scoretaxa.currentIndex().siblingAtColumn(0).data()
    
    def selectedTaxonRef(self):
        parent = self.treeview_scoretaxa.currentIndex().parent()
        if parent.isValid():
            return parent.data()
        else:
            return self.treeview_scoretaxa.currentIndex().data()
        
    def selectedTaxaId(self):
        parent = self.treeview_scoretaxa.currentIndex().parent()
        if parent.isValid():
            return parent.data(Qt.UserRole)
        else:
            return self.treeview_scoretaxa.currentIndex().data(Qt.UserRole)
    
    def selectedScore(self):
        return self.treeview_scoretaxa.currentIndex().siblingAtColumn(1).data()
    
    def on_selection_changed(self, selected):
        index = selected.indexes()[0] if selected.indexes() else None
        if index:
            selected_item = index.data()
            self.selectionChanged.emit(selected_item)  # Emit the slot selected_item
            
    def on_doubleClicked(self, index):
        self.doubleClicked.emit(index)  # Emit the slot selected_item

    def on_text_changed(self):
        #"main" function to search for taxa resolution
        self.model.clear()
        search_txt = self.lineEdit_search_taxa.text()
        _score = 0.4
        #exlude search according to number of characters
        if len(search_txt) < 4:
            return
        if len(search_txt) < 8:
            _score = 0.2
        #create sql query
        sql_query = f"""
            SELECT 
                a.taxonref, a.score, a.id_taxonref, c.name AS synonym
            FROM 
                taxonomy.pn_taxa_searchname('{search_txt}', {_score}::numeric) a 
            INNER JOIN 
                taxonomy.taxa_nameset c 
            ON 
                a.id_taxonref = c.id_taxonref AND c.category <> 1
            ORDER 
                BY score DESC, synonym ASC
        """
        #print (sql_query)
        query = QtSql.QSqlQuery (sql_query)
        dict_nodes = {}
        tab_header = ['taxonref', 'score']
        while query.next():
            id_taxonref = query.value('id_taxonref')
            if id_taxonref in dict_nodes:
                ref_item = dict_nodes[id_taxonref]
            else:
                #create the node if not already existed
                ref_item = [QtGui.QStandardItem(str(query.value(x))) for x in tab_header]
                ref_item[0].setData(id_taxonref, Qt.UserRole)
                ref_item[1].setTextAlignment(Qt.AlignCenter)
                self.model.appendRow(ref_item)
                dict_nodes[id_taxonref] = ref_item
                #set score in red if below 50
                if query.value('score') < 50:
                    _color =  QtGui.QColor(255, 0, 0)
                    ref_item[1].setData(QtGui.QBrush(_color), Qt.ForegroundRole)
            if query.value('synonym'):
                ref_item[0].appendRow ([QtGui.QStandardItem(query.value('synonym'))])
                
        if self.model.rowCount() > 0:
            self.treeview_scoretaxa.resizeColumnToContents(1)
            self.treeview_scoretaxa.setExpanded(self.model.index(0, 0), True)
            self.treeview_scoretaxa.header().setStretchLastSection(False)
            self.treeview_scoretaxa.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.treeview_scoretaxa.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        
# 

#class to add a taxon
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
                taxa["authors"] = commons.get_str_value(taxa["authors"])
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
                msg = commons.postgres_error(result.lastError())
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
        id_rankparent = commons.get_dict_rank_value(self.PNTaxa.id_rank,'id_rankparent')
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
        sql_query += f"\nFROM taxonomy.pn_taxa_edit ({str_idtaxonref}, '{newbasename}', '{newauthors}', {str_newidparent}, NULL, '{str(published)}', TRUE)"
        # sql_query = sql_query.replace ("_idtaxonref", str_idtaxonref)
        # sql_query = sql_query.replace ("_basename", newbasename)
        # sql_query = sql_query.replace ("_authors", newauthors)
        # sql_query = sql_query.replace ("_newidparent", str_newidparent)       
        # # sql_query = sql_query.replace ("_idparent", str_newidparent)
        # # sql_query = sql_query.replace ("_idrank", str_newidrank)
        # sql_query = sql_query.replace ("_published", str(published))
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
            msg = commons.postgres_error(result.lastError())
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
            msg = commons.postgres_error(result.lastError())
        QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)

        return self.updated
        


    def show(self):
        self.window.show()
        self.window.exec_()


#class to display a treeview with hiercharchical taxonomy
# class PN_taxa_hierarchical_widget(QTreeView):
#     def __init__(self):
#         super().__init__()
#         self.setEditTriggers(QAbstractItemView.NoEditTriggers)

#     def setdata(self, myPNTaxa):
# # Get the hierarchy for the selected taxa
#         model = QtGui.QStandardItemModel()
#         model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
#         self.setModel(model)
#         self.setColumnWidth(0, 250)
#         try:
#             if myPNTaxa.idtaxonref * myPNTaxa.id_rank == 0:
#                 return
#         except Exception:
#             return
#         str_idtaxonref = str(myPNTaxa.idtaxonref)
#         # extend to genus where id_rank >= genus (e.g. for species return all sibling species in the genus instead of only the species taxa)
#         if myPNTaxa.id_rank >= 14:
#             str_idtaxonref = "(SELECT * FROM taxonomy.pn_taxa_getparent(" + str_idtaxonref + ",14))"
#         # construct the Query statement, based on the Union betweens parents and childs
#         sql_query = "SELECT id_taxonref, id_rank, id_parent, taxaname,  coalesce(authors,'')::text authors, published FROM"
#         sql_query += "\n(SELECT id_taxonref, id_rank, id_parent, taxaname,  authors, published"
#         sql_query += "\nFROM taxonomy.pn_taxa_parents(" + str_idtaxonref + ", True)"
#         sql_query += "\nUNION SELECT id_taxonref, id_rank, id_parent, taxaname,  authors, published"
#         sql_query += "\nFROM taxonomy.pn_taxa_childs(" + str_idtaxonref + ", False)) a"
        
#         # add a sqlwhere statement according to rank to limit the child deepth avoiding a mega-tree long to load for upper taxonomic rank (class, order,...)
#         if myPNTaxa.id_rank < 10:
#             sql_query += "\nWHERE a.id_rank <=10"
#         #add ordering
#         sql_query += "\nORDER BY a.id_rank, a.taxaname"
#         #print (sql_query)
#         model = self.model()
#         # model.setRowCount(0)
#         model.setColumnCount(4)
#         # execute the Query and fill the treeview standarditemmodel based on search id_parent into the third column containing id_taxonref
#         query = QtSql.QSqlQuery(sql_query)
#         #set the taxon to the hierarchical model rank = taxon
#         while query.next():
#             ls_item_taxonref = []
#             ls_item_taxonref = model.findItems(str(query.value('id_parent')), Qt.MatchRecursive, 2)  # MatchExactly
#             _rankname = commons.get_dict_rank_value(query.value('id_rank'),'rank_name')
#             ##query.value('rank_name'))
#             _taxonref = str(query.value('taxaname'))
#             _authors = str(query.value('authors')).strip()
#             if len(_authors) > 0 and not query.value('published'):
#                 _authors = _authors + ' ined.' 
#             #if not _authors in (['', 'null']):
#             _taxonref = _taxonref.strip() + ' ' + _authors #str(query.value('authors'))
#             _taxonref = _taxonref.strip()

#             item = QtGui.QStandardItem(_rankname)
#             item1 = QtGui.QStandardItem(_taxonref) ##query.value('taxonref'))
#             item2 = QtGui.QStandardItem(str(query.value('id_taxonref')))
#             item4 = QtGui.QStandardItem(str(query.value('taxaname')))

#             if ls_item_taxonref:
#                 # get the first col of the QStandardItem
#                 row = ls_item_taxonref[0].row()
#                 index = ls_item_taxonref[0].index()
#                 index0 = index.sibling(row, 0)
#                 # append a child to the item
#                 model.itemFromIndex(index0).appendRow([item, item1, item2, item4],) #, item3, item4, item5, item6, item7],)
#                 # get a reference to the last append item
#                 key_row = model.itemFromIndex(index0).rowCount()-1
#                 key_item = model.itemFromIndex(index0).child(key_row, 0)
#             else:
#                 # append as a new line if item not found (or first item)
#                 model.appendRow([item, item1, item2, item4],) #, item3, item4, item5, item6, item7],)
#                 key_item = model.item(model.rowCount()-1)
#             # set bold the current id_taxonref line (2 first cells)
#             if not query.value('published'):
#                 font = QtGui.QFont()
#                 font.setItalic(True)
#                 key_index = key_item.index()
#                 key_row = key_item.row()
#                 #model.setData(key_index, font, Qt.FontRole)
#                 key_index = key_index.sibling(key_row, 1)
#                 model.setData(key_index, font, Qt.FontRole)

#             if query.value('id_taxonref') == myPNTaxa.idtaxonref:
#                 font = QtGui.QFont()
#                 font.setBold(True)
#                 key_index = key_item.index()
#                 key_row = key_item.row()
#                 model.setData(key_index, font, Qt.FontRole)
#                 key_index = key_index.sibling(key_row, 1)
#                 model.setData(key_index, font, Qt.FontRole)
#         self.selectionModel().setCurrentIndex(key_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
#         self.setHeaderHidden(True)
#         self.hideColumn(2)
#         self.hideColumn(3)
#         self.expandAll()

#     def selecteditem(self):
#         #return a PNTaxa for the selected item into the hierarchical model
#         try:
#             parentname = self.currentIndex().parent().siblingAtColumn(3).data()
#         except Exception:
#             parentname =''
#         try:
#             id_taxonref = int(self.currentIndex().siblingAtColumn(2).data())
#             sql = f"SELECT id_rank, taxaname, authors, published FROM taxonomy.taxa_names WHERE id_taxonref ={id_taxonref}"

#             query = QtSql.QSqlQuery(sql)
#             query.next()
#             idrank = query.value('id_rank')
#             taxaname = query.value('taxaname')
#             authors = query.value('authors')
#             published = query.value('published')
#             item = PNTaxa(id_taxonref, taxaname, authors, idrank, published)
#             item.parent_name = parentname
#             return item
#         except Exception:
#             return

# class TableSimilarNameModel(QtCore.QAbstractTableModel):
#     #header_labels = ['Name', 'Cleaned Name', 'Reference Name']
#     header_labels = ['Similar Name', 'Category']
#     def __init__(self, data = None):
#         super(TableSimilarNameModel, self).__init__()
#         self._data = []
#         self._data = data if data is not None else []
    
#     def resetdata(self, newdata = None):
#         self.beginResetModel()
#         self._data = newdata if newdata is not None else []
#         self.endResetModel()

#     def headerData(self, section, orientation, role=Qt.DisplayRole):
#         if role == Qt.DisplayRole and orientation == Qt.Horizontal:
#             return self.header_labels[section]

#     def data(self, index, role):
#         if not index.isValid():
#             return None
#         if 0 <= index.row() < self.rowCount():
#             item = self._data[index.row()]
#             col = index.column() 
                   
#             if role == Qt.DisplayRole:
#                 if col==0:
#                     return item.synonym
#                 elif col==1:
#                     return item.category
#             elif role == Qt.UserRole:
#                 return item

#     def rowCount(self, index=QtCore.QModelIndex()):
#         return len(self._data)

#     def columnCount(self, index=QtCore.QModelIndex()):
#         return 2

#     def additem (self, clrowtable):
#         self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
#         self._data.append(clrowtable)
#         self.endInsertRows()


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