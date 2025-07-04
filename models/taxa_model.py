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
        self.id_parent = None
        self.parent_name = None
        #self.id_rank_parent = None
        self.dict_species = commons.get_dict_from_species(self.taxaname)
        if self.dict_species is None:
            self.dict_species = {}

    def field_dbase(self, fieldname):
        """get a field value from the view taxonomy.taxa_names according to a id_taxonref"""
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
                        a.id_category, a.name
                    """
        query = QtSql.QSqlQuery(sql_query)
        dict_db_names = {'Autonyms': []} #to ensure the first row
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
    def json_properties_count(self):
        if self.id_rank >= 21:
            return None
    #load all the similar names of the taxa to a json dictionnary
        sql_query = f"""
            WITH childs_taxaname AS 
                (
                    SELECT a.id_taxonref, b.properties 
                    FROM 
                    taxonomy.pn_taxa_childs({self.idtaxonref}) a
                    INNER JOIN taxonomy.taxa_names b ON a.id_taxonref = b.id_taxonref
                    WHERE a.id_rank >=21
                    AND b.properties IS NOT NULL 
                )
                SELECT jsonb_object_agg(key, fields) AS json_result
                FROM (
                    SELECT key, jsonb_object_agg(field, values_json) AS fields
                    FROM (
                        SELECT key, field, jsonb_object_agg(
                            replace(value::TEXT, chr(34), '')::TEXT, 
                            occurrence_count
                        ) AS values_json
                        FROM (
                            SELECT 
                                main.key AS key, 
                                sub.key AS field, 
                                sub.value::TEXT AS value, 
                                COUNT(*) AS occurrence_count
                            FROM childs_taxaname,
                            LATERAL jsonb_each(properties) AS main,
                            LATERAL jsonb_each(main.value) AS sub
                            GROUP BY main.key, sub.key, sub.value
                        ) grouped_data
                        GROUP BY key, field
                    ) fields_grouped
                    GROUP BY key
                ) final_json;
                    """
        query = QtSql.QSqlQuery(sql_query)
        query.next()
        json_props = query.value("json_result")
        if json_props:
            json_props = json.loads(json_props)
        else:
            json_props = None
        return json_props

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

        # #fill the identiy of the taxa, exit of error    
        # tab_identity = dict_db_properties["identity"]
        # try:
        #     tab_identity["authors"] =  self.authors
        #     if self.isautonym:
        #         tab_identity["published"] =  '[Autonym]'
        #     else:
        #         tab_identity["published"] =  str(self.published)
        #     tab_identity["name"] =  self.basename     
        # except Exception:
        #     return
        
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
# class TableModel(QtCore.QAbstractTableModel):
#     header_labels = ['Taxa Name', 'Authors', 'Rank'] #, 'ID Taxon']
#     def __init__(self, data = None):
#         super(TableModel, self).__init__()
#         self.PNTaxon = []
#         self.PNTaxon = data if data is not None else []
    
#     def resetdata(self, newdata = None):
#         self.beginResetModel()
#         self.PNTaxon = newdata if newdata is not None else []
#         self.endResetModel()

#     def headerData(self, section, orientation, role=Qt.DisplayRole):
#         if role == Qt.DisplayRole and orientation == Qt.Horizontal:
#             return self.header_labels[section]
#         #return self.headerData(self, section, orientation, role)

#     def delete (self, idtaxonref):
#         ##delete one item in the list, NOT PERSISTENT IN DATABASE)
#         self.PNTaxon = [x for x in self.PNTaxon if x.idtaxonref != idtaxonref]


#     # def add (self, myPNTaxa):
#     #     ##delete one item in the list, NOT PERSISTENT IN DATABASE)
#     #     self.PNTaxon = [x for x in self.PNTaxon if x.idtaxonref != myPNTaxa.idtaxonref]


#     def row_idtaxonref (self, idtaxonref):
#         ##return the row index of the idtaxonref into the _data list
#         for x in range(len(self.PNTaxon)):
#             if self.PNTaxon[x].idtaxonref == idtaxonref:
#                 return x              
#         return -1

#     def refresh (self, myPNTaxa = None):
#         ##By default refresh the entire
#         # look for refresh id_taxonref if exists otherwise append the new row
#         ##not persistent in the database
#         if myPNTaxa is None:
#             self.resetdata(self.PNTaxon)
#         else:
#             found = False
#             for taxa in self.PNTaxon:
#                 if taxa.idtaxonref == myPNTaxa.idtaxonref:
#                     found = True
#                     taxa.taxaname = myPNTaxa.taxaname
#                     taxa.authors = myPNTaxa.authors
#                     taxa.id_rank = myPNTaxa.id_rank
#                     if myPNTaxa.published is not None:
#                         taxa.published = myPNTaxa.published
#             if not found :
#                 self.PNTaxon.append(myPNTaxa)

#     def data(self, index, role):
#         if not index.isValid():
#             return None
#         if 0 <= index.row() < self.rowCount():
#             item = self.PNTaxon[index.row()]
#             col = index.column()        
#             if role == Qt.DisplayRole:
#                 if col == 0:
#                     return item.taxaname
#                 elif col == 1:
#                     #is_published = item.published ##getattr(item, 'published', True)
#                     _authors = str(item.authors)
#                     if item.isautonym:
#                         _authors = '[Autonym]'
#                     elif _authors=='':
#                         _authors = ''
#                     elif not item.published:
#                         _authors += ' ined.'
#                     return _authors.strip()

#                 elif col == 2:
#                     return item.rank_name
#             elif role == Qt.UserRole:
#                 return item
#             elif role == Qt.FontRole:
#                 #is_published = item.published ##getattr(item, 'published', True)
#                 if not item.published:
#                     font = QtGui.QFont()
#                     font.setItalic(True)
#                     return font
#             elif role == Qt.DecorationRole:
#                 if col == 0:
#                     len_json = getattr(item, 'api_score', 0)
#                     col = QtGui.QColor(0,0,0,255)
#                     if 1<= len_json <= 2:
#                         col = QtGui.QColor(255,128,0,255)
#                     elif len_json == 3:
#                         col = QtGui.QColor(255,255,0,255)
#                     elif len_json >= 4:
#                         col = QtGui.QColor(0,255,0,255)
#                     px = QtGui.QPixmap(10,10)
#                     px.fill(QtCore.Qt.transparent)
#                     painter = QtGui.QPainter(px)
#                     painter.setRenderHint(QtGui.QPainter.Antialiasing)
#                     px_size = px.rect().adjusted(2,2,-2,-2)
#                     painter.setBrush(col)

#                     if len_json == 0:
#                         painter.setPen(QtGui.QPen(QtCore.Qt.white, 1,
#                             QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
#                     else:
#                         painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
#                             QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))

#                     # painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
#                     #     QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    

#                     painter.drawEllipse(px_size)
#                     painter.end()

#                     return QtGui.QIcon(px)

#             elif col == 0 and role == Qt.TextAlignmentRole:
#                 if hasattr(item, 'id_rank') and item.id_rank >= 21:
#                     return Qt.AlignRight | Qt.AlignVCenter
#                 else:
#                     return Qt.AlignLeft | Qt.AlignVCenter

#     def rowCount(self, index=QtCore.QModelIndex()):
#         # The length of the outer list.
#         return len(self.PNTaxon)
        
#     def columnCount(self, index=QtCore.QModelIndex()):
#         # The following takes the first sub-list, and returns
#         # the length (only works if all rows are an equal length)
#         try:
#             return 2 #3 #self.PNTaxon[0].columnCount # len(self.PNTaxon[0])
#         except Exception:
#             return 0

#     def additem (self, clrowtable):
#         self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
#         self.PNTaxon.append(clrowtable)
#         self.endInsertRows()
        
#class to add a taxon
class PN_add_taxaname(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa): 
        super().__init__()
        self.myPNTaxa = myPNTaxa
        self.table_taxa = []
        self._taxaname = ''
        self.updated = False
        #set the ui
        self.window = uic.loadUi("ui/pn_addtaxa.ui")
        self.window.publishedComboBox.addItems(['True', 'False'])
        self.rankComboBox_setdata()      

        model = QtGui.QStandardItemModel()
        #model.setHorizontalHeaderLabels(['Rank','Taxon'])        
        #model.itemChanged.connect(self.trview_childs_checked_click)        
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
        #delete some tabs according to ranks and in adequation with the API get_children
        if self.myPNTaxa.id_rank <14:
            self.remove_tab_by_name('ENDEMIA')
        if self.myPNTaxa.id_rank <10:
            self.remove_tab_by_name('POWO')
            self.remove_tab_by_name('FLORICAL')
        if self.myPNTaxa.id_rank <8:
            self.remove_tab_by_name('TAXREF')

        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QDialogButtonBox.Apply)
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        self.taxaLineEdit_setdata()
        #self.alter_category()
    
    def remove_tab_by_name(self, tab_name):
    #delete some tabs according to their name
        tab_widget = self.window.tabWidget_main
        for index in range(tab_widget.count()):
            if tab_widget.tabText(index) == tab_name:
                tab_widget.removeTab(index)
                break

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
            #id_rank = self.data_rank[self.window.rankComboBox.currentIndex()]
            id_rank = self.window.rankComboBox.itemData(self.window.rankComboBox.currentIndex())

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
        dict_rank  = commons.get_dict_rank_value(self.myPNTaxa.id_rank)
        rank_childs = dict_rank["childs"]
        #self.data_rank = []
        index = -1
        for idrank in rank_childs:
            rank_name = commons.get_dict_rank_value(idrank, 'rank_name')
            self.window.rankComboBox.addItem(rank_name, idrank)
            #self.data_rank.append(idrank)
            if idrank == self.myPNTaxa.id_rank:
                index = self.window.rankComboBox.count()-1
        index = max(index, 0)
        try:
            self.window.rankComboBox.setCurrentIndex(index)
        except Exception:
            return        

    def trview_childs_checked_click(self, checked_item):
    #slot to monitor the check state
        state = checked_item.checkState()
        _apply = False
        if state == 2 :
            self.checked_parent(checked_item)
            _apply = True
        elif state == 0:
            self.unchecked_child(checked_item)
            #check to see if at least one item is checked
            for taxa in self.table_taxa:
                try:
                    if taxa.get("item", None) and taxa["item"].checkState() == 2:
                        _apply = True
                        break
                except Exception:
                    continue
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
    #change tabWidget_main item (user search or internet search)
        #index = self.window.comboBox_searchAPI.currentIndex()
        if index == 0 : 
            self.window.label_2.setText("Add taxon")
            self.window.taxaLineEdit_result.setVisible(True)
            self.taxaLineEdit_setdata()
            return
        self.window.taxaLineEdit_result.setVisible(False)
        self.window.label_2.setText("Taxon not found")
        
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)
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
        index = self.window.tabWidget_main.currentIndex()
        _apibase = self.window.tabWidget_main.tabText(index).lower()
                #draw the list in the tree view
        model = self.window.trView_childs.model()
        model.setRowCount(0)
        model.setColumnCount(2)


        item1 = QtGui.QStandardItem(self.myPNTaxa.rank_name)
        item2 = QtGui.QStandardItem(self.myPNTaxa.taxonref)
        item3 = QtGui.QStandardItem(_apibase.upper())
        item4 = QtGui.QStandardItem("Waiting for data...")
        font = QtGui.QFont()
        font.setItalic(True)
        item3.setFont(font)
        item4.setFont(font)
        model.appendRow([item1, item2],)
        item1.appendRow([item3, item4],)
        self.window.trView_childs.expandAll()
        self.window.trView_childs.resizeColumnToContents(0)

        QApplication.processEvents()
        if _apibase == 'taxref':
            _classeAPI = API_TAXREF(self.myPNTaxa)
        elif _apibase == 'endemia':
            _classeAPI = API_ENDEMIA(self.myPNTaxa)
        elif _apibase == 'powo':
            _classeAPI = API_POWO(self.myPNTaxa)
        elif  _apibase == 'florical':
            _classeAPI = API_FLORICAL(self.myPNTaxa)
        _classeAPI.get_children()
        table_taxa = {}
        table_taxa = _classeAPI.children
        if not table_taxa or len(table_taxa) <= 1:
            table_taxa = {}
            #restore original cursor
        #self.window.trView_childs.model().setRowCount(0)
        self.window.trView_childs.repaint()

        # try:
        #     if len(table_taxa) == 0:
        #         table_taxa = {}
        # except Exception:
        #     table_taxa = {}
        # self.window.label_2.setText("No new taxa to add")
        if table_taxa:
            #sort the list (except root = 0) according to taxaname and create self.table_taxa
            item4.setText("Sorting data")
            self.window.trView_childs.repaint()
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

            #ajust the dictionnary, add special fields and construct the query
            _taxaname=''     
            try:
                for taxa in self.table_taxa:
                    _tabtaxa = taxa["taxaname"].split()
                    taxa["id_taxonref"] = 0
                    taxa["id_parent"] = taxa["idparent"]
                    del taxa["idparent"]
                    taxa["basename"] = _tabtaxa[-1]
                    taxa["authors"] = commons.get_str_value(taxa["authors"])
                    taxa["parentname"] = self.get_table_taxa_item(taxa["id_parent"],"taxaname")
                    taxa["id_rank"] =commons.get_dict_rank_value(taxa["rank"], "id_rank")
                    taxa["published"] = len (taxa["authors"]) > 0
                    _taxaname += f",'{taxa['taxaname']}'"
                _taxaname = _taxaname.strip(',')
            except Exception:
                pass
            #check for already existing taxaname and set the id_taxonref if found
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
            #create an index based on the taxaname
            index_taxa = {taxa["taxaname"]: taxa for taxa in self.table_taxa}
            #set the id_taxonref already in the database
            while query.next():
                taxaname = query.value("original_name")
                if taxaname in index_taxa:
                    index_taxa[taxaname]["id_taxonref"] = query.value("id_taxonref")


            model.setRowCount(0)
            self.draw_list ()
            if model.rowCount() ==0:
                model.appendRow([QtGui.QStandardItem("No data   "), QtGui.QStandardItem("< Null Value >")],)
            # self.window.trView_childs.hideColumn(2)
            # self.window.trView_childs.hideColumn(3)
            #model.itemChanged.connect(self.trview_childs_checked_click) 
            self.window.trView_childs.expandAll()
            self.window.trView_childs.resizeColumnToContents(0)
            self.window.trView_childs.resizeColumnToContents(1)
            self.window.trView_childs.sortByColumn(1, Qt.AscendingOrder)
        else:
            #no data found, display a message
            item4.setText("No data found")
            self.window.trView_childs.repaint()
            self.window.label_2.setText("No data found")

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()


    def draw_list(self, id=0):
        model = self.window.trView_childs.model()
        self.checkable = 0

        def draw_list_recursive(id):
            #internal recursive function to build hierarchical tree according to idparent and id
            _search ="id_parent"
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
                    item = taxa2.get("item", None)
                    if item is None:
                        parent_item = self.get_table_taxa_item (id, "item")
                        item = QtGui.QStandardItem(str(taxa2["rank"]))
                        taxaref = str(taxa2["taxaname"]) + ' ' + str(taxa2["authors"])
                        item1 = QtGui.QStandardItem(taxaref.strip())
                        if parent_item:
                            parent_item.appendRow([item, item1],)
                        else:
                            model.appendRow([item, item1],)
                        taxa2["item"] = item
                    _checkable = (taxa2["id_taxonref"] == 0)
                    if _checkable:
                        self.checkable += 1
                        
                    item.setCheckable(False)
                    item.setData(None, Qt.CheckStateRole)
                    item.setCheckable(_checkable)
                    if taxa2["id_parent"] != taxa2["id"]:
                        taxa2["item"] = item
                        draw_list_recursive(taxa2["id"])
        #disconnect the itemChanged signal
        try:
            model.itemChanged.disconnect(self.trview_childs_checked_click)
        except Exception:
            pass
        
        draw_list_recursive(id)
        #add message to the label
        if self.checkable > 0:
            self.window.label_2.setText("Check the taxa to add")
        else:
            self.window.label_2.setText("No new taxa to add")
        #reconnect the itemChanged signal
        model.itemChanged.connect(self.trview_childs_checked_click) 
                    
    def get_table_taxa_item(self,id, key):
    #get a value from a key and id in the table_taxa
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
            if taxa["id_parent"] == id and taxa.get("item", None):
                item = taxa["item"]
                if item.checkState()==2:
                    #taxa["parent"] = taxaname
                    tab_result.append(taxa)
                tab_result += self.get_listcheck(taxa["id"]) #,taxa["taxaname"])
        return tab_result
    def refresh (self):
        self.window.basenameLineEdit.setText('')
        self.window.authorsLineEdit.setText('')
        self.window.publishedComboBox.setCurrentIndex(0)
        index = self.window.tabWidget_main.currentIndex()
        if index == 0:
            return
        # for item_update in ls_updated:
        #     for taxa in self.table_taxa:
        #         if taxa["taxaname"] == item_update.basename:
        #             taxa["id_taxonref"] = item_update.idtaxonref

        # taxa_toAdd = self.get_listcheck()
        # for taxa in taxa_toAdd:
        #     for item_update in ls_updated:
        #         for taxa2 in self.table_taxa:
        #             if taxa2["id"] == taxa["id"]:
        #                 taxa2["id_taxonref"] = item_update.idtaxonref
        self.draw_list()

    def apply(self):
    #apply add taxa
        self.updated = False        
        index = self.window.tabWidget_main.currentIndex()
    #for user table
        if index == 0 :
            newbasename = self.window.basenameLineEdit.text().strip()            
            newpublished = (self.window.publishedComboBox.currentIndex() == 0)
            newauthors = self.window.authorsLineEdit.text().strip()
            newidparent = self.myPNTaxa.idtaxonref
            #newidrank = self.data_rank[self.window.rankComboBox.currentIndex()]
            newidrank = self.window.rankComboBox.itemData(self.window.rankComboBox.currentIndex())
            #create the pn_taxa_edit query function (internal to postgres)
            if len(newauthors) == 0:
                newpublished = False
            dict_tosave = {"id_taxonref":0, "basename":newbasename, "authors":newauthors, "id_parent":newidparent, "published":newpublished, "id_rank":newidrank}
            self.apply_signal.emit(dict_tosave)
            return

    #for API tabs
        #get the dict_tosave for each checked taxa to add
        taxa_toAdd = self.get_listcheck()
        if taxa_toAdd is None:
            return
        if len(taxa_toAdd) == 0:
            return
        #emit the signal to save the taxa
        self.apply_signal.emit(taxa_toAdd)
        return


    def close(self):
        self.window.close()

    def show(self):
        self.window.show()
        self.window.exec_()

#edit a taxa and apply by emit signal 
class PN_edit_taxaname(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa):
        super().__init__()
        self.PNTaxa = myPNTaxa
        self.input_name =''
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
        newbasename = self.window.basenameLineEdit.text().title().strip()
        newauthors = self.window.authorsLineEdit.text()
        parentname = None
        prefix = None
        published = (self.window.publishedComboBox.currentIndex() == 0)
        ined = ''
        if not newauthors:
            ined = ' ined.'
        elif self.window.publishedComboBox.currentIndex() == 1:
            ined = ' ined.'        
        taxa =''
        try:
            id_rank = self.PNTaxa.id_rank
            if id_rank >=21:
                parentname = self.window.parent_comboBox.currentText()
                prefix = commons.get_dict_rank_value(id_rank, 'prefix')
                newbasename = newbasename.lower()
            taxa = " ".join(str(part) for part in [parentname, prefix, newbasename, newauthors, ined] if part)
        except Exception:
            taxa = " ".join([newbasename, newauthors, ined])
        #set the title of the window
        self.window.taxaLineEdit.setText(taxa)
        #if text is different than input text than activated apply button

        if len(self.input_name) == 0 : 
            return
        _apply = (
                (taxa != self.input_name) or 
                (self.parent_name != self.window.parent_comboBox.currentText()) or
                (self.PNTaxa.published != published)
                )        
        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(_apply)

    def close(self):
        self.window.close()
        
    def apply(self):
        # code_error =''
        # msg = ''
        self.updated = False 
        idtaxonref = self.PNTaxa.idtaxonref
        newbasename = self.window.basenameLineEdit.text().strip()
        published = (self.window.publishedComboBox.currentIndex() == 0) 
        newauthors = self.window.authorsLineEdit.text().strip()
        newidparent = self.tab_parent_comboBox[self.window.parent_comboBox.currentIndex()]
        #create the pn_taxa_edit query function (internal to postgres)
        if len(newauthors) == 0:
            published = False
        dict_tosave = {"id_taxonref":idtaxonref, "basename":newbasename, "authors":newauthors, "id_parent":newidparent, "published":published, "id_rank" :None}
        self.apply_signal.emit(dict_tosave)
        return True

    def refresh (self):
        #refresh variables and text info
        self.input_name = self.window.taxaLineEdit.text()
        self.parent_name = self.window.parent_comboBox.currentText()
        self.taxaLineEdit_setdata()
        #self.updated = True

    def show(self):
        self.window.show()
        self.window.exec_()

#merge two taxa and create synonyms
class PN_merge_taxaname(QtWidgets.QMainWindow):
    def __init__(self, myPNTaxa): # move toward a same id_rank if merge
        super().__init__()
        self.PNTaxa = myPNTaxa
        self.updated = False

        self.window = uic.loadUi("ui/pn_movetaxa.ui")
        self.window.setMaximumHeight(1)
        
        self.window.comboBox_category.addItems(['Nomenclatural', 'Taxinomic'])
        self.window.comboBox_category.setCurrentIndex(0)
        self.window.comboBox_category.activated.connect(self.set_newtaxanames)
        
        self.window.comboBox_taxa.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.window.comboBox_taxa.activated.connect(self.set_newtaxanames)
        button_OK = self.window.buttonBox
        button_OK.button(QDialogButtonBox.Apply).clicked.connect (self.accept) 
        button_OK.button(QDialogButtonBox.Close).clicked.connect (self.close)
        
        self.window.taxaLineEdit.setText(self.PNTaxa.taxonref)
        self.comboBox_taxa_setdata()
    @property
    def selected_idtaxonref(self):
        index = self.window.comboBox_taxa.currentIndex()
        return self.window.comboBox_taxa.itemData(index)
    @property
    def selected_category(self):
        return self.window.comboBox_category.currentText()
    
    def set_newtaxanames(self):
    #Display the new names and return the sql query
        # set the resulting label (synonym expression)
        category_synonym = chr(8801)
        if self.window.comboBox_category.currentIndex() > 0:
            category_synonym = chr(61)
        txt_taxa = self.PNTaxa.taxonref +  ' ' + category_synonym + ' ' +self.window.comboBox_taxa.currentText()
        self.window.label_result.setText(txt_taxa)
        self.sql_query_save = ''
        #set the sql query
        str_idtaxonref = str(self.PNTaxa.idtaxonref)
        str_idnewparent = str(self.selected_idtaxonref)
        category = self.window.comboBox_category.currentText()
        sql_query = f"CALL taxonomy.pn_taxa_set_synonymy({str_idtaxonref}, {str_idnewparent}, '{category}');"
        return sql_query

    def comboBox_taxa_setdata(self):
    #fill the combo box with taxa names
        sql_query = "SELECT a.id_taxonref, a.basename, a.id_rank, a.taxaname, a.authors, a.taxonref"
        sql_query += "\nFROM taxonomy.taxa_names a"
        if self.PNTaxa.id_rank < 21:
            sql_query += f"\nWHERE a.id_rank >= {self.PNTaxa.id_rank} AND a.id_rank < {self.PNTaxa.id_rank + 1}"
        else:
            sql_query += "\nWHERE a.id_rank >= 21"
        sql_query += "\nORDER BY taxonref"
        
        #fill the model
        query = QtSql.QSqlQuery (sql_query)
        while query.next():
            self.window.comboBox_taxa.addItem(
                query.value('taxonref'),
                query.value('id_taxonref')
                )
        #set the current taxa
        self.window.comboBox_taxa.setCurrentText(self.PNTaxa.taxonref)
               
    def accept(self):
    #Valid the form, save the data into the dbase and return
    #a list of PNTaxa that have been updated
        code_error =''
        msg = ''
        self.updated = True
        self.close()
        return
        #execute the query to set one name synonym to another one (according to taxonomic rules)
        self.sql_query_save = self.set_newtaxanames()
        if len(self.sql_query_save)>0:
            result = QtSql.QSqlQuery (self.sql_query_save)
            code_error = result.lastError().nativeErrorCode ()
       
        if len(code_error) == 0:
            self.updated_datas = []
            str_idnewparent = self.window.comboBox_taxa.itemData(self.window.comboBox_taxa.currentIndex())
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
    
    
    def close(self):
        self.window.close()
 
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
            sql_query = f"SELECT taxonomy.pn_names_add ('{idtaxonref}','{new_synonym}','{new_category}')"
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

        # self.table = QtWidgets.QTableView()

        # data = [
        #    PNTaxa(123,'Miconia', 'DC.', 14,0),
        #    PNTaxa(124,'Miconia calvescens', 'DC.', 21,1)
        # #  # PNTaxa(1456,'Sapotaceae', 'L.', 10),
        #  ]
        # #self.model = TableModel(data)
        # #self.model = TableModel()
        # #self.model.resetdata(data)
        # #self.table.setModel(self.model)
        # #self.model.additem(PNTaxa(1456,'Sapotaceae', 'L.', 10, 2))
        # #self.model.additem(PNTaxa(1800,'Arecaceae', 'L.', 10, 3))

        # self.setCentralWidget(self.table)





















class TreeItem:
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 2  # Taxa Name, Authors

    def data(self, column):
        if column == 0:
            return self.itemData.taxaname
        elif column == 1:
            _authors = str(self.itemData.authors)
            if self.itemData.isautonym:
                _authors = '[Autonym]'
            elif _authors == '':
                _authors = ''
            elif not self.itemData.published:
                _authors += ' ined.'
            return _authors.strip()
        return None

    def parent(self):
        return self.parentItem

    def row(self):
        try:
            return self.parentItem.childItems.index(self)
        except Exception:
            return 0


class TreeModel(QtCore.QAbstractItemModel):
    header_labels = ['Name', 'Authors']

    def __init__(self, data=None, parent=None):
        super(TreeModel, self).__init__(parent)
        self.rootItem = TreeItem(None)
        self.parent_nodes = {}
        self.sort_column = 0
        self.sort_order = QtCore.Qt.AscendingOrder
        #option to show or not orphelin taxa (not referenced into the grouped node)
        self.show_orphelins = True
        self.items = data if data else []
        self.setupModelData()

    def sortItems(self, column, order=Qt.AscendingOrder, rootItem=None):
    # to sort the model by a column (by default all the model)
        def recursive_sort(item):
            item.childItems.sort(
                key=lambda i: i.data(column).lower() if isinstance(i.data(column), str) else i.data(column),
                reverse=(order == Qt.DescendingOrder)
            )
            for child in item.childItems:
                recursive_sort(child)

        if not rootItem:
            rootItem = self.rootItem
        self.sort_column = column
        self.sort_order = order
        recursive_sort(rootItem)
        self.layoutChanged.emit()

    def indexItem(self, idtaxonref, column=0):
        tree_item = self.getNode (idtaxonref)
        if tree_item is None or tree_item == self.rootItem:
            return QtCore.QModelIndex()

        parent_item = tree_item.parent()
        if parent_item is None:
            return QtCore.QModelIndex()

        row = parent_item.childItems.index(tree_item)
        return self.createIndex(row, column, tree_item)



    def getNode(self, idtaxonref):
    #get the TreeItem from the idtaxonref
        return self.parent_nodes.get(idtaxonref, None)

    def getItem(self, idtaxonref):
        #get the PNTaxa item from the idtaxonref
        TreeItem = self.getNode(idtaxonref)
        #return the item
        return TreeItem.itemData if TreeItem else None
    
    def removeItem(self, id_taxonref):
        def delete_all_children(item):
            for child in item.childItems:
                # recursive call on children
                delete_all_children(child)
                # Remove from the items list
                if child.itemData in self.items:
                    self.items.remove(child.itemData)
                # Remove from the parent_nodes dictionary
                taxon_id = getattr(child.itemData, 'id_taxonref', None)
                if taxon_id in self.parent_nodes:
                    del self.parent_nodes[taxon_id]

        #get the TreeItem from the idtaxonref
        item = self.getNode(id_taxonref)
        if not item:
            return
        #get the parent of the TreeItem
        parent = item.parent()
        if not parent:
            return
        #set the QmodelIndex for the parent
        try:
            parent_index = self.createIndex(parent.row(), 0, parent) if parent != self.rootItem else QtCore.QModelIndex()
        except Exception:
            return
        
        #delete the item and childs from the parent list
        self.beginRemoveRows(parent_index, item.row(), item.row())
        #delete all children recursively
        delete_all_children(item)
        #delete the node itself
        if item in parent.childItems:
            parent.childItems.remove(item)
        self.endRemoveRows()

    def addItem(self, myPNTaxa):
    #add a new item to the model, NOT PERSISTENT IN DATABASE
        self.beginInsertRows(QtCore.QModelIndex(), len(self.items), len(self.items))
        self.items.append(myPNTaxa)
        self.setupModelData(myPNTaxa)
        self.endInsertRows()

    def refresh (self, myPNTaxa = None):
        #Refresh the content of the model, NOT PERSISTENT IN DATABASE
        ##By default refresh the entire model (myPNTaxa = None)
        #look for refresh id_taxonref if exists otherwise append the new row
            #get the PNTaxa Item  
        if myPNTaxa is None:
            self.refreshData()
            return
        
        TreeItem = self.parent_nodes.get(myPNTaxa.id_parent, None)
        if self.getItem (myPNTaxa.idtaxonref): #item already exists
            item = self.getItem(myPNTaxa.idtaxonref)
            #test the id_parent, if different remove and recreate item
            if item.id_parent != myPNTaxa.id_parent: 
                self.removeItem(myPNTaxa.id_taxonref)
                self.addItem(myPNTaxa)
            else: #update the item data
                item.taxaname = myPNTaxa.taxaname
                item.authors = myPNTaxa.authors
                item.id_rank = myPNTaxa.id_rank
                item.published = False
                if myPNTaxa.published is not None:
                    item.published = myPNTaxa.published
        else:
            #if not exists, append the new item
            self.addItem(myPNTaxa)
        self.sortItems(self.sort_column, self.sort_order, TreeItem)

    def refreshData(self, new_PNTaxa_items = None):
    #refresh the entire model with the new items
        if not new_PNTaxa_items:
            new_PNTaxa_items = self.items
        self.items = new_PNTaxa_items
        #reset the model and setup the new data
        self.beginResetModel()
        self.rootItem = TreeItem(None)
        self.setupModelData()
        self.endResetModel()

    def setupModelData(self, item = None):
    #append a list of node to the model, if idparent = None => Root otherwise search for idtaxonref= idparent
    #only append, not remove the previous items
        # and create all the root item
        # if not append:
        #     self.parent_nodes = {}
        #     if self.show_orphelins:
        #         self.parent_nodes = {0: self.rootItem}
        if item:
            items = [item]
        else:
            items = self.items
    # first loop to detect parents (id_parent is None)
        for item in items:
            idparent = getattr(item, 'id_parent', None)
            #if no parent, create a root item
            if idparent is None:
                idtaxonref = item.idtaxonref
                if idtaxonref not in self.parent_nodes:
                    self.parent_nodes[idtaxonref] = TreeItem(item, self.rootItem)
                    self.rootItem.appendChild(self.parent_nodes[idtaxonref])
    # second loop to create the children of the respective parent
        for item in items:
            idparent = getattr(item, 'id_parent', 0)
            if idparent in self.parent_nodes:
                childItem = TreeItem(item, self.parent_nodes[idparent])
                # if item.idtaxonref in self.parent_nodes:
                #     _tmp = self.parent_nodes[item.idtaxonref]
                #     self.parent_nodes[idparent].childItems.remove(_tmp)
                self.parent_nodes[item.idtaxonref] = childItem
                self.parent_nodes[idparent].appendChild(childItem)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 2

    def rowCount(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        return parentItem.childCount()

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem or parentItem is None:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()
        col = index.column()

        if role == Qt.DisplayRole:
            return item.data(col)
        elif role == Qt.UserRole:
            return item.itemData
        elif role == Qt.FontRole:
            if item.itemData and not getattr(item.itemData, 'published', True):
                font = QtGui.QFont()
                font.setItalic(True)
                return font
        elif role == Qt.DecorationRole:
            if item.itemData:
                px = QtGui.QPixmap(26, 12)
                px.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(px)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                if col == 0:
                    len_json = getattr(item.itemData, 'api_score', 0)
                    col = QtGui.QColor(0, 0, 0, 255)
                    if 1 <= len_json <= 2:
                        col = QtGui.QColor(255, 128, 0, 255)
                    elif len_json == 3:
                        col = QtGui.QColor(255, 255, 0, 255)
                    elif len_json >= 4:
                        col = QtGui.QColor(0, 255, 0, 255)           
                    #px_size = px.rect().adjusted(2, 2, -2, -2)
                    r1 = QtCore.QRect(1, 1, 10, 10)   # premier point à gauche

                    painter.setBrush(col)
                    # if len_json == 0:
                    #     painter.setPen(QtGui.QPen(QtCore.Qt.white, 1,
                    #                               QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    # else:
                    #     painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
                    #                               QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    #painter.drawEllipse(px_size)
                    painter.drawEllipse(r1)
                elif col == 1:
                    published =getattr(item.itemData, 'published', True)
                    r2 = QtCore.QRect(15, 1, 10, 10)   # deuxième point à droite
                    if published :
                        col = QtGui.QColor(0, 255, 0, 255)
                        #painter.setPen(QtGui.QPen(QtCore.Qt.white, 1,
                        #                          QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    else:
                        col = QtGui.QColor(255, 0, 0, 255)
                        #painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
                        #                          QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.setBrush(col)
                    painter.drawRects(r2)

                    
                painter.end()

                return QtGui.QIcon(px)

        elif col == 0 and role == Qt.TextAlignmentRole:
            if item.itemData and hasattr(item.itemData, 'id_rank') and item.itemData.id_rank >= 21:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        elif role == Qt.ToolTipRole:
            if col == 0 and item.itemData:
                api_score = getattr(item.itemData, 'api_score', 0)
                published = getattr(item.itemData, 'published', True)

                parts = []
                # Explanation of the API score
                parts.append(f"API Score: {api_score}")
                if api_score == 0:
                    parts.append("→ No API result")
                elif api_score == 1:
                    parts.append("→ Partial match")
                elif api_score == 2:
                    parts.append("→ Moderate match")
                elif api_score == 3:
                    parts.append("→ Good match")
                elif api_score >= 4:
                    parts.append("→ Excellent match")

                # Explanation of the publication status
                parts.append("Published" if published else "Not published")

                return "\n".join(parts)


    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header_labels[section]
        return None












if __name__ == '__main__':
    app=QtWidgets.QApplication(sys.argv)

    window=MainWindow()
    window.show()
    app.exec_()