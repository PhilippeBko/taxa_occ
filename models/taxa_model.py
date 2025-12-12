#from pydoc import text
#from operator import index
import re
#import sys
import json
import time
import requests


from PyQt5 import QtCore, QtGui, QtWidgets, QtSql, uic
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import QMessageBox, QDialogButtonBox, QGridLayout, QApplication, QCompleter

########################################
#from models.api_thread import API_Taxonomy  #, API_TAXREF, API_ENDEMIA, API_POWO, API_FLORICAL, API_TROPICOS, API_IPNI, API_INATURALIST, API_GBIF, TaxonData
from core.widgets import PN_TaxaSearch
from core import functions as commons
from models.api_taxonomy import API_Taxonomy
########################################
APIkey_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"


# Main classe to store a taxaname with some properties
class PNTaxa(object):
    def __init__(self, idtaxonref, taxaname = None, authors = None, idrank= None, published = None, accepted = None):
        self.id_taxonref = idtaxonref
        if taxaname:
            self.taxaname = taxaname
            self.authors = authors
            self.id_rank = idrank
            self.published = published
            self.accepted = accepted
            self.id_parent = None
        else:
            self.fill_from_dbase()
        self.dict_species = commons.get_dict_from_species(self.taxaname)
        if self.dict_species is None:
            self.dict_species = {}

    def fill_from_dbase(self):
        """fill the class with values from the database according to a id_taxonref"""
        sql_query = f"""
                    SELECT 
                        taxaname, authors, id_rank, published, accepted, id_parent 
                    FROM
                        taxonomy.taxa_names
                    WHERE
                        id_taxonref = {self.id_taxonref}
                   """
        query = QtSql.QSqlQuery(sql_query)
        query.next()
        self.taxaname = query.value("taxaname")
        self.authors = query.value("authors")
        self.id_rank = query.value("id_rank")
        self.published = query.value("published")
        self.accepted = query.value("accepted")
        self.id_parent = query.value("id_parent")
       
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
        # if not self.taxaname:
        #     self.taxaname = self.field_dbase("taxaname")
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
    def list_hierarchy(self):
        # Get the hierarchy for the selected taxa
        try:
            if self.idtaxonref * self.id_rank == 0:
                return
        except Exception:
            return
        str_idtaxonref = str(self.idtaxonref)
        sql_where = ''
        # extend to all taxa included in the genus when id_rank > genus (e.g. for species return all sibling species within the genus)
        #or in other words, set to the genus rank when id_rank > genus
        if self.id_rank > 14: #get the genus rank at minimum
            str_idtaxonref = f"""(SELECT * FROM taxonomy.pn_taxa_getparent({str_idtaxonref},14))"""
        if self.id_rank < 10: #limit the deepth to the families level
            sql_where = "\nWHERE a.id_rank <=10"
        # create the SQL query to get the hierarchy of taxa
        sql_query = f"""SELECT 
                            id_taxonref, id_rank, id_parent, taxaname,  coalesce(authors,'')::text authors, published, accepted 
                        FROM
                            (SELECT 
                                id_taxonref, id_rank, id_parent, taxaname,  authors, published, accepted
                            FROM    
                                taxonomy.pn_taxa_parents({str_idtaxonref}, True)
                            UNION 
                            SELECT 
                                id_taxonref, id_rank, id_parent, taxaname,  authors, published, accepted
                            FROM 
                                taxonomy.pn_taxa_childs({str_idtaxonref}, False)
                            ) a
                            {sql_where}
                        ORDER BY 
                            a.id_rank, a.taxaname
                    """
        # execute the Query and fill the list_hierarchy of dictionnary
        query = QtSql.QSqlQuery(sql_query)
        #set the taxon to the hierarchical model rank = taxon
        #ls_hierarchy = []
        ls_hierarchy2 = []
        #ls_hierarchy2.add(self)
        #print (self.idtaxonref, self.id_parent)
        while query.next():
            id_taxonref = query.value('id_taxonref')
            idrank = query.value('id_rank')
            taxaname = query.value('taxaname').strip()
            authors = query.value('authors').strip()
            published = query.value('published')
            accepted = query.value('accepted')
            idparent = query.value('id_parent')
            item = PNTaxa(id_taxonref, taxaname, authors, idrank, published, accepted)
            item.id_parent = idparent
            ls_hierarchy2.append(item)
            #print (id_taxonref, idparent)

            #create the items
            #dict_item = {'idtaxonref': id_taxonref, 'taxaname': taxaname, 'authors': authors, 'published': published, 'accepted': accepted, 'idrank': idrank, 'idparent': idparent}
            #ls_hierarchy.append (dict_item)
            #ls_hierarchy[_rankname] = dict_item
        return ls_hierarchy2

    @property 
    def json_metadata (self):
    #load metadata json from database
        json_data = self.field_dbase("metadata")
        if not json_data:
            return None
        json_data = json.loads(json_data)
        #sorted the result, assure to set web links and query time ending the dict
        for key, metadata in json_data.items():
            _links = {'url':None, 'webpage':None} #, 'query time': None}
            if key.lower() =="score":
                _links = {}
            _fields = {}
            for _key, _value in metadata.items():
                if _key.lower() in _links:
                    _links[_key] = _value
                else:
                    _fields[_key] = _value
            #add the links to the fields
            #_fields = _fields | _links
            for _key, _value in _links.items():
                 if _value:
                    _fields[_key] = _value
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

#class to represent taxa with scoring information
class PNTaxa_with_Score(PNTaxa):
    """Subclass of PNTaxa with additional properties for scoring."""
    def __init__(self, idtaxonref, taxaname = None, authors = None, idrank= None, published = None, accepted = None):
        super().__init__(idtaxonref, taxaname, authors, idrank, published, accepted)
        self.taxaname_score = None
        self.authors_score = None
        self.api_total = 0

    @property
    def taxaname_percent(self):
        if self.taxaname_score is not None:
            # if self.taxaname_score == 0:
            #     return "Not Found"
            return str(round(100 * self.taxaname_score, 1)) + "%"
        else: 
            return None
    @property
    def authors_percent(self):
        if self.authors_score is not None:
            # if self.authors_score == 0:
            #     return "Not Found"
            return str(round(100 * self.authors_score, 1)) + "%"
        else: 
            return None

#class to search taxa through API
class PNTaxa_searchAPI (QThread):
    """
    Worker thread to query multiple biodiversity APIs asynchronously.

    Emits:
        Result_Signal (str, object): Signal emitted with API name and data dictionary
            or special status strings like "END" or "NOTCONNECTED".
    Args:
        parent (QObject): Parent QObject for the thread.
        myPNTaxa (object, optional): Model or taxon object to query. Defaults to None.
        filter (str, optional): Limits queries to a single API from the supported list. Defaults to None.
    Attributes:
        PNTaxa_model (object): The taxon model to query.
        status (int): Thread status flag, 1 for running, 0 for stopped.
        list_api (list): List of API names to query.
    """
    
    Result_Signal = pyqtSignal(str, object)
    
    def __init__(self, parent, myPNTaxa = None, filter = None):
        """
        Initialize the thread with taxon model and optional API filter.
        """
        QThread.__init__(self, parent)
        self.PNTaxa_model = myPNTaxa
        self.api_Taxonomy = API_Taxonomy()
        self.list_api = list(self.api_Taxonomy.api_classes.keys())
        self.status = 0
        #apikey_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
        #self.list_api =  ["POWO","TAXREF","IPNI","TROPICOS","ENDEMIA","FLORICAL", "INATURALIST", "GBIF"]
        # test for a _filter (= one of the valid base (IPNI, POWO, TAXREF, TROPICOS))
        try:
            if filter in self.list_api:
                self.list_api = [filter]
        except Exception:
            pass
        
    def kill(self):
        """
        Signal to stop the thread's operation and emit an "END" signal.
        """
        try:
            self.Result_Signal.emit("END", None)
        finally :
            self.status = 0

    def run(self):
        """
        Main thread loop that queries each API in the list sequentially.

        Steps:
            - Checks for internet connectivity.
            - Iterates over the APIs to query metadata and synonyms.
            - Emits results through Result_Signal.
            - Stops if status is set to 0.
        """        
        _list_api = {}
        
        #test for a effective connection
        try:
            requests.get("https://www.google.com", timeout=2)
        except Exception:
            self.Result_Signal.emit("NOTCONNECTED", None)
            return
        
        if self.PNTaxa_model is None:
            self.Result_Signal.emit("END", None)
            return
        #set the variables
        _name = self.PNTaxa_model.simple_taxaname
        _rank = self.PNTaxa_model.rank_name
        #_key_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
        #self.list_api = ["GBIF"]

        #add only classes accepted id_rank for searching
        list_api_tosearch = []
        for key, value in self.api_Taxonomy.api_classes.items():
            _children = value.get("search", 0)
            if self.PNTaxa_model.id_rank >= _children:
                list_api_tosearch.append(key)
        #set variables for scoring
        self.status = 1
        total_checked = 0
        total_fullname = 0
        total_authors  = 0
        total_match = 0
        _score = {"authors_score": 0, "taxaname_score": 0, "query_time": time.strftime("%Y-%m-%d %H:%M:%S")}

        for api_name in list_api_tosearch:
            _json = None
            #check for status
            if self.status == 0: 
                return
            #set the key (if tropicos)
            _key = None
            if api_name == "TROPICOS":
                _key = APIkey_tropicos
            #search the taxon in the API            
            result = self.api_Taxonomy.get_APIclass(api_name, _name, _rank, _key)
            if not result.API_url:
                continue
            if result.API_error:
                if result.API_error.startswith("Connection error"):
                    continue
            total_checked += 1

            if result is None :
                continue
        #get the metadata
            _json = result.get_metadata()
            #delete None values
            if _json:
                if "query time" in _json:
                    del _json["query time"] #delete query time for each json, use a common query_time in _score dictionnary
                _json = {k: v for k, v in _json.items() if v is not None}
            
            #add synonyms if exists and emit intermediate signal
            if _json:
                total_match +=1
                t_synonyms = result.get_synonyms()
                if t_synonyms:
                    _json["synonyms"] = t_synonyms

            #check if the author name is the same considering only alphanumeric characters
                if _json.get ("authors", None):
                    total_authors += 1
                    _json_authors = re.sub(r'[^A-Za-z]', '', _json["authors"]).lower()
                    _pn_authors = re.sub(r'[^A-Za-z]', '', self.PNTaxa_model.authors).lower()
                    if _json_authors == _pn_authors:
                        total_fullname += 1                    
                self.status += 1
                _list_api[api_name] = _json
            #create intermediate _json (score and _json error will not be included in the _list_api final !)
            if not _json:
                _json = {"error": "No results", "url":result.API_url}
            _json = _json.copy()
            #create score dictionnary
            _score["taxaname_score"] = total_match / total_checked if total_checked > 0 else 0
            _score["authors_score"] = total_fullname / total_authors if total_authors > 0 else 0
            #emit intermediate signal
            _json["score"] = _score
            self.Result_Signal.emit(str(api_name), _json)

            
            if self.status == 0 : 
                return
            time.sleep(0.2)
        #emit final signal
        #create score dictionnary
        _score["taxaname_score"] = total_match / total_checked if total_checked > 0 else 0
        _score["authors_score"] = total_fullname / total_authors if total_authors > 0 else 0
        _list_api["score"] = _score
        self.Result_Signal.emit("END", _list_api)

            


    @property 
    def total_api_calls(self):
        return (self.status-1)
        _total_api_servers = len(self.list_api)
        if _total_api_servers > 0:
            return int(100 * (self.status-1) / _total_api_servers)

#class to display a treeview with hiercharchical taxonomy
class PNTaxa_QTreeView(QtWidgets.QTreeView):
    """
    The PNTaxa_QTreeView class is a custom class that inherits from QtWidgets.QTreeView.
    It is designed to display a hierarchical taxonomic structure.
    The class takes a PNTaxa object as input to define the taxonomic hierarchy.

    Attributes:
        None

    Methods:
        __init__ : Initializes the tree view window, disabling editing capabilities.
        setdata : Defines the taxonomic hierarchy based on a PNTaxa object. It creates a SQL query to retrieve the hierarchy, executes the query, and populates the tree view with the results.
        selecteditem : Returns a PNTaxa object corresponding to the selected item in the tree view.

    Notes:
        The setdata method is the primary method of the class, as it retrieves and populates the taxonomic hierarchy from a PNTaxa object.
        The selecteditem method is a convenience function to retrieve the data of the selected item as a PNTaxa object.
    """
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        model = QtGui.QStandardItemModel()
        #model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
        self.setModel(model)   
    
    def setdata(self, myPNTaxa, currentIdtaxonref = None):
# Get the hierarchy for the selected taxa
        # model = QtGui.QStandardItemModel()
        # #model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
        # self.setModel(model)
        model = self.model()

        model.clear()
        
        ls_hierarchy = myPNTaxa.list_hierarchy
        if not ls_hierarchy:
            return

        dict_idtaxonref = {}
        for item in ls_hierarchy:
            _itemrank = item.rank_name
            if not item.published and item.id_rank >=3:
                _itemrank += " (ined.)"
            dict_idtaxonref[item.idtaxonref] = [QtGui.QStandardItem(_itemrank), QtGui.QStandardItem(item.taxonref)]

        for item in ls_hierarchy:
            #search for a parent_item in the dictionnary of item index on id_taxonref
            item_parent = dict_idtaxonref.get(item.id_parent, None)
            item_taxon = dict_idtaxonref.get(item.idtaxonref, None)
            #append as child or root
            if item_parent:
                item_parent[0].appendRow(item_taxon)
            else:
                # append as a new line if item not found (or first item)
                model.appendRow(item_taxon)
            #if item_rank:
            item_taxon[0].setData(item, Qt.UserRole)
            # set italic if not published
            if not item.published:
                font = QtGui.QFont()
                font.setItalic(True)
                model.setData(item_taxon[0].index(), font, Qt.FontRole)
            if not item.accepted:
                model.setData(item_taxon[0].index(), QtGui.QColor(255, 0, 0), Qt.ForegroundRole)

        #get the selection
        current_item = None
        #item_selected = self.currentIndex().siblingAtColumn(0).data(Qt.UserRole)
        if currentIdtaxonref is not None:
            current_item = dict_idtaxonref.get(currentIdtaxonref, None)

        if current_item is None:
            current_item = dict_idtaxonref.get(myPNTaxa.idtaxonref, None)         

        # set bold the current id_taxonref line (2 first cells) and italized authors if not published
            
        key_index = None
        if current_item:
            # font = QtGui.QFont()
            # font.setBold(True)
            key_index = current_item[0].index()
        if key_index:
            #select and ensure visible the key_index (automatic scroll)
            self.selectionModel().setCurrentIndex(key_index, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
            self.scrollTo(key_index,QtWidgets.QAbstractItemView.PositionAtCenter)  # PositionAtTop/EnsureVisible
            
        self.setHeaderHidden(True)
        self.setColumnWidth(0, 300)
        self.expandAll()

    def selecteditem(self):
        #return a PNTaxa for the selected item into the hierarchical model
        return self.currentIndex().siblingAtColumn(0).data(Qt.UserRole)

#class to add a taxon
class PNTaxa_add(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa): 
        super().__init__()
        self.PNTaxa = myPNTaxa
        self.table_taxa = []
        self._taxaname = ''
        self.updated = False
        #set the ui
        self.window = uic.loadUi("ui/pn_addtaxa.ui")
        # self.window.publishedComboBox.addItems(['True', 'False'])
        # self.window.acceptedComboBox.addItems(['True', 'False'])
        self.window.trView_childs.setVisible(False)
        self.rankComboBox_setdata()      

        model = QtGui.QStandardItemModel()
        self.window.trView_childs.setModel(model)
        self.window.trView_childs.setColumnWidth(0,250)
        
        #delete some tabs according to ranks and in adequation with the API get_children

        #create tabs acccording to the list of api available to search for children

        self.taxonomy_api = API_Taxonomy()
        # rank = self.PNTaxa.rank_name
        # rank = rank.lower()
        _idrank = self.PNTaxa.id_rank
        api_class_toadd = {}
        #add only classes with a get_children function
        for key, value in self.taxonomy_api.api_classes.items():
            _children = value.get("children", None)
            if _children and _idrank >=_children:
                api_class_toadd[key] = value

        #api_class_toadd = self.taxonomy_api.api_classes_children(self.PNTaxa.rank_name)
        for api_class in api_class_toadd.keys():
            self.window.tabWidget_main.addTab(QtWidgets.QWidget(), api_class.title())


        self.window.tabWidget_main.currentChanged.connect(self.alter_category)
        self.window.basenameLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.authorsLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.rankComboBox.activated.connect(self.taxaLineEdit_setdata)
        # self.window.publishedComboBox.activated.connect(self.taxaLineEdit_setdata)
        # self.window.acceptedComboBox.activated.connect(self.taxaLineEdit_setdata)
        self.window.checkBox_published.toggled.connect(self.taxaLineEdit_setdata)
        self.window.checkBox_accepted.toggled.connect(self.taxaLineEdit_setdata)

        # if self.PNTaxa.id_rank <14:
        #     self.remove_tab_by_name('ENDEMIA')
        #     self.remove_tab_by_name('TROPICOS')
        # if self.PNTaxa.id_rank <10:
        #     self.remove_tab_by_name('POWO')
        #     self.remove_tab_by_name('FLORICAL')
        # if self.PNTaxa.id_rank <8:
        #     self.remove_tab_by_name('TAXREF')

        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QDialogButtonBox.Apply)
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        self.taxaLineEdit_setdata()
        #self.alter_category()
    
    # def remove_tab_by_name(self, tab_name):
    # #delete some tabs according to their name
    #     tab_widget = self.window.tabWidget_main
    #     for index in range(tab_widget.count()):
    #         if tab_widget.tabText(index) == tab_name:
    #             tab_widget.removeTab(index)
    #             break

    def taxaLineEdit_setdata(self):
        newbasename = self.window.basenameLineEdit.text()
        newauthors = self.window.authorsLineEdit.text()
        newbasename = newbasename.lower()
        parentname = self.PNTaxa.taxaname
        published = self.window.checkBox_published.isChecked()
        #accepted = self.window.checkBox_accepted.isChecked()
        if len(newauthors) == 0:
            ined = ' ined.'
        elif published:
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
        dict_rank  = commons.get_dict_rank_value(self.PNTaxa.id_rank)
        rank_childs = dict_rank["childs"]
        #self.data_rank = []
        index = -1
        for idrank in rank_childs:
            rank_name = commons.get_dict_rank_value(idrank, 'rank_name')
            self.window.rankComboBox.addItem(rank_name, idrank)
            #self.data_rank.append(idrank)
            if idrank == self.PNTaxa.id_rank:
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
        self.window.trView_childs.setVisible(False)

        if index == 0 : 
            self.window.label_2.setText("Add taxon")
            self.window.taxaLineEdit_result.setVisible(True)
            self.taxaLineEdit_setdata()
            return
        #index = self.window.tabWidget_main.currentIndex()
        _apibase = self.window.tabWidget_main.tabText(index)
        self.window.taxaLineEdit_result.setVisible(False)
        self.window.label_2.setText(f"Search for taxon to add from {_apibase.title()}...")

        self.window.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)
        QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        #get data (list of dictionnary) from API class function get_children"
        # a list of childs elements
        #exemple {"id" : '10', "taxaname" : 'Genus species', "authors" : 'Not me', "rank" : 'Species', "idparent" : '1'}
        # note that the id_parent of each taxa except the first one must be in the list, if not it will excluded
         #tabwidget.addTab(widget, str(value))
        layout = self.window.tabWidget_main.currentWidget().layout()
        if layout is None:
            layout = QGridLayout()
            self.window.tabWidget_main.currentWidget().setLayout(layout)
        layout.addWidget(self.window.trView_childs)
        self.window.trView_childs.setVisible(True)

        #draw the list in the tree view
        model = self.window.trView_childs.model()
        model.setRowCount(0)
        model.setColumnCount(2)


        item1 = QtGui.QStandardItem(self.PNTaxa.rank_name)
        item2 = QtGui.QStandardItem(self.PNTaxa.taxonref)
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

        _apibase = _apibase.upper()
        QApplication.processEvents()
        _name = self.PNTaxa.simple_taxaname
        _rank = self.PNTaxa.rank_name
        #set the key (if tropicos)
        _key = None
        if _apibase == "TROPICOS":
            _key = APIkey_tropicos
        #get the class
        result = self.taxonomy_api.get_APIclass(_apibase, _name, _rank, _key)
        #get children
        table_taxa = result.get_children()
        if not table_taxa or len(table_taxa) <= 1:
            table_taxa = {}

        if table_taxa:
            #sort the list (except root = 0) according to taxaname and create self.table_taxa
            item4.setText("Sorting data")
            self.window.trView_childs.repaint()
            #create a sorted list of unique item
            sort_taxa = set()
            for taxa in table_taxa[1:]:
                sort_taxa.add(taxa["taxaname"])
            sort_taxa = list(sort_taxa)
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
            _SQL_taxaname=''     
            #try:
            for taxa in self.table_taxa:                
                _tabtaxa = taxa["taxaname"].split()
                taxa["id_taxonref"] = 0
                taxa["basename"] = _tabtaxa[-1]
                taxa["authors"] = commons.get_str_value(taxa["authors"])
                taxa["parentname"] = self.get_table_taxa_item(taxa["id_parent"],"taxaname")
                taxa["id_rank"] =commons.get_dict_rank_value(taxa["rank"], "id_rank")
                taxa["published"] = len (taxa["authors"]) > 0
                taxa["accepted"] = True
                taxa["autonym"] = False
                if taxa["id_rank"] > 21 and len(_tabtaxa) >= 4:
                    taxa["autonym"] = (_tabtaxa[1] == taxa["basename"])
                _SQL_taxaname += f",'{taxa['taxaname']}'"
            _SQL_taxaname = _SQL_taxaname.strip(',')


            #check for already existing taxaname and set the id_taxonref if found
            sql_query = f"""
                            SELECT 
                                id_taxonref, 
                                original_name 
                            FROM 
                                taxonomy.pn_taxa_searchnames( array[{_SQL_taxaname}]) 
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
            _msg = self.taxonomy_api._api_class.API_error or "No sub-Taxon found"
            item4.setText(_msg)
            self.window.trView_childs.repaint()
            self.window.label_2.setText("No data found")

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()


    def draw_list(self, id=0):
        
        if self.window.tabWidget_main.currentIndex() == 0:
            return
        model = self.window.trView_childs.model()
        self.checkable = 0

        def draw_list_recursive(id):
            #internal recursive function to build hierarchical tree according to idparent and id
            _search ="id_parent"
            if id==0:
                #search for the input taxon as root
                #id = self.table_taxa[0]["id"]
                for taxa in self.table_taxa:
                    if taxa["taxaname"] == self.PNTaxa.taxaname:
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
                    _checkable = (taxa2["id_taxonref"] == 0 and not taxa2["autonym"]  )
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
        index = self.window.tabWidget_main.currentIndex()
        _api_name = self.window.tabWidget_main.tabText(index).title()
        if self.checkable > 0:
            self.window.label_2.setText("Check the taxa to add from " + _api_name)
        else:
            self.window.label_2.setText("No new taxa to add from " + _api_name)
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
        self.window.checkBox_published.setChecked(False)
        self.window.checkBox_accepted.setChecked(False)

        self.draw_list()

    def apply(self):
    #apply add taxa
        self.updated = False        
        index = self.window.tabWidget_main.currentIndex()
    #for user table
        if index == 0 :
            newbasename = self.window.basenameLineEdit.text().strip()            
            newpublished = self.window.checkBox_published.isChecked()
            newaccepted = self.window.checkBox_accepted.isChecked()
            newauthors = self.window.authorsLineEdit.text().strip()
            newidparent = self.PNTaxa.idtaxonref
            #newidrank = self.data_rank[self.window.rankComboBox.currentIndex()]
            newidrank = self.window.rankComboBox.itemData(self.window.rankComboBox.currentIndex())
            #create the pn_taxa_edit query function (internal to postgres)
            if len(newauthors) == 0:
                newpublished = False
            dict_tosave = {"id_taxonref":0, "basename":newbasename, "authors":newauthors, "id_parent":newidparent, "published":newpublished, "accepted":newaccepted, "id_rank":newidrank}
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
class PNTaxa_edit(QtWidgets.QMainWindow):
    apply_signal  = pyqtSignal(object)
    def __init__(self, myPNTaxa):
        super().__init__()
        self.PNTaxa = myPNTaxa
        #set the ui 
        self.window = uic.loadUi("ui/pn_edittaxa.ui")
        self.window.setWindowTitle("Edit reference")        
        #self.window.publishedComboBox.addItems(['True', 'False'])
        #self.window.acceptedComboBox.addItems(['True', 'False'])
        self.window.basenameLineEdit.setText(self.PNTaxa.basename)
        self.window.authorsLineEdit.setText(self.PNTaxa.authors)
        self.window.checkBox_published.setChecked(self.PNTaxa.published)
        self.window.checkBox_accepted.setChecked(self.PNTaxa.accepted)

        _style = """
            QCheckBox::indicator:checked {
                background-color: rgb(0, 255, 0);
                border: 1px solid darkgreen;
            }
            QCheckBox::indicator:unchecked {
                background-color: rgb(255, 0, 0);
                border: 1px solid darkred;
            }
            QCheckBox::indicator:indeterminate {
                background-color: white;
                border: 1px solid #555;
    }
        """
        self.window.checkBox_published.setStyleSheet(_style)
        self.window.checkBox_accepted.setStyleSheet(_style)


        #self.window.publishedComboBox.setCurrentText (str(self.PNTaxa.published))
        self.window.basenameLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.authorsLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        #self.window.publishedComboBox.activated.connect(self.taxaLineEdit_setdata)

        self.window.checkBox_published.toggled.connect(self.taxaLineEdit_setdata)
        self.window.checkBox_accepted.toggled.connect(self.taxaLineEdit_setdata)

        self.window.parent_comboBox.activated.connect(self.taxaLineEdit_setdata)
        #self.window.acceptedComboBox.activated.connect(self.taxaLineEdit_setdata)
        #self.window.acceptedComboBox.setCurrentText (str(self.PNTaxa.accepted))

        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QDialogButtonBox.Apply)
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        self.fill_parent_comboBox()
        self.taxaLineEdit_setdata()
        #self.input_name = self.window.taxaLineEdit.text()

    def fill_parent_comboBox(self):
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
        query = QtSql.QSqlQuery(sql_query)
        i = 0
        index = -1
        while query.next():
            idtaxonref = query.value("id_taxonref")
            self.window.parent_comboBox.addItem (query.value("taxaname"), idtaxonref)
            if idtaxonref == self.PNTaxa.id_parent:
                index = i
            i +=1
        self.window.parent_comboBox.setCurrentIndex(index)


    def taxaLineEdit_setdata(self):
        #newparent = self.window.parent_comboBox.currentText()
        newbasename = self.window.basenameLineEdit.text().title().strip()
        newauthors = self.window.authorsLineEdit.text()
        parentname = None
        prefix = None
        published = (self.window.checkBox_published.isChecked())
        accepted = (self.window.checkBox_accepted.isChecked())
        ined = ''
        if not newauthors:
            ined = ' ined.'
        elif not published:
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

        if len(self.PNTaxa.basename) == 0 : 
            return
        _idparent = self.window.parent_comboBox.itemData(self.window.parent_comboBox.currentIndex(), Qt.UserRole)
        _apply = (
                (self.PNTaxa.basename != newbasename.lower()) or
                (self.PNTaxa.authors != newauthors) or
                (self.PNTaxa.id_parent != _idparent) or
                (self.PNTaxa.published != published) or 
                (self.PNTaxa.accepted != accepted)
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
        published = (self.window.checkBox_published.isChecked())
        accepted = (self.window.checkBox_accepted.isChecked())
        newauthors = self.window.authorsLineEdit.text().strip()
        newidparent = self.window.parent_comboBox.itemData(self.window.parent_comboBox.currentIndex(), Qt.UserRole)
        #create the pn_taxa_edit query function (internal to postgres)
        # if len(newauthors) == 0:
        #     published = False
        dict_tosave = {"id_taxonref":idtaxonref, "basename":newbasename, "authors":newauthors, "id_parent":newidparent, "published":published, "accepted":accepted, "id_rank" :None}
        self.apply_signal.emit(dict_tosave)
        return True

    def refresh (self):
        #refresh variables and text info
        self.window.basenameLineEdit.setText(self.PNTaxa.basename)
        self.window.authorsLineEdit.setText(self.PNTaxa.authors)
        self.window.checkBox_published.setChecked(self.PNTaxa.published)
        self.window.checkBox_accepted.setChecked(self.PNTaxa.accepted)
        index = self.window.parent_comboBox.findData(self.PNTaxa.id_parent)
        self.window.parent_comboBox.setCurrentIndex(index)
        self.taxaLineEdit_setdata()
        

    def show(self):
        self.window.show()
        self.window.exec_()

#merge two taxa and create synonyms
class PNTaxa_merge(QtWidgets.QMainWindow):
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
            #sql_query += f"\nWHERE a.id_rank >= {self.PNTaxa.id_rank} AND a.id_rank < {self.PNTaxa.id_rank + 1}"
            sql_query += f"\nWHERE a.id_rank = {self.PNTaxa.id_rank}"
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

#classes (PNTaxa_TreeModel containing PNTaxa_treeItem) to create an abstract model to display taxon with parent
class PNTaxa_treeItem:
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

class PNTaxa_TreeModel(QtCore.QAbstractItemModel):
    header_labels = ['Name', 'Authors']
    refresh_signal = pyqtSignal()

    def __init__(self, data=None, parent=None):
        super(PNTaxa_TreeModel, self).__init__(parent)
        self.rootItem = PNTaxa_treeItem(None)
        self.parent_nodes = {}
        self.sort_column = 0
        self.show_nodes_with_children_only = 0 #2 = root nodes with children only (no others options)
        self.show_nodes_published = 1  #0=all, 1=published only, 2=unpublished only
        self.show_nodes_accepted = 1  #0=all, 1=accepted only, 2=unaccepted only
        # self.filter_published = None
        # self.filter_accepted = None
        self.sort_order = QtCore.Qt.AscendingOrder
        #option to show or not orphelin taxa (not referenced into the grouped node)
        self.show_orphelins = True
        self.items = data if data else []
        #self.items = set(data) if data else set()
        #self.setupModelData()



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
        def delete_all_children(node):
            # Remove the PNTaxa_with_score from the items list
            if node.itemData in self.items:
                self.items.remove(node.itemData)
            # Remove from the parent_nodes dictionary
            taxon_id = getattr(node.itemData, 'id_taxonref', None)
            if taxon_id in self.parent_nodes:
                del self.parent_nodes[taxon_id]
            for child in node.childItems:
                # recursive call on children
                delete_all_children(child)

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
        row = item.row()
        #delete the item and childs from the parent list
        self.beginRemoveRows(parent_index, row, row)
        #delete all children recursively
        delete_all_children(item)
        #delete the node itself
        if item in parent.childItems:
            parent.childItems.remove(item)
        self.endRemoveRows()

    # def addItem(self, myPNTaxa):
    # #add a new item to the model, NOT PERSISTENT IN DATABASE
    # #add only id_rank >=21 with a node parent existing
    #     #if myPNTaxa.id_rank < 21 or 
    #     if self.getItem(myPNTaxa.id_parent) is None:
    #         return
    #     self.items.append(myPNTaxa)
    #     self.setupModelData(myPNTaxa)

    def refresh (self, myPNTaxas = None):
        #Refresh the content of the model, NOT PERSISTENT IN DATABASE
        ##By default refresh the entire model (myPNTaxa = None)
        #look for refresh id_taxonref if exists otherwise append the new row
        #refresh the entire model if myPNTaxa is None
        if myPNTaxas is None:
            self.refreshData()
            return
        #ensure the myPNTaxas is a list
        if not isinstance(myPNTaxas, list):
            ls_myPNTaxas = [myPNTaxas]
        else:
            ls_myPNTaxas = myPNTaxas
        #browse the list and refresh or add the items
        node_parent = None
        for myPNTaxa in ls_myPNTaxas:
            node_parent = self.getNode(myPNTaxa.id_parent)
            node_item = self.getNode(myPNTaxa.idtaxonref)
            if node_item: #item already exists
                #do not move root items
                if node_item.parentItem is not self.rootItem:
                    #delete if node_parent is NULL
                    if node_parent is None:
                        self.removeItem(myPNTaxa.idtaxonref)
                        continue
                    #if parent different, move the node to the new parent
                    elif node_item.parentItem != node_parent:
                        #delete the item from the old parent
                        if node_item in node_item.parentItem.childItems:
                            node_item.parentItem.childItems.remove(node_item)
                        #set the new parent
                        node_item.parentItem = node_parent
                        node_parent.appendChild (node_item)
                #swap the existing itemData with the new one in self.items and node_item
                item = node_item.itemData
                i = self.items.index(item)
                self.items[i] = myPNTaxa
                #finally change the itemData of the node_item
                node_item.itemData = myPNTaxa
            elif node_parent: #new item on an existingn parent
                self.items.append(myPNTaxa)
                self.setupModelData(myPNTaxa)
        #sort the model
        self.sortItems(self.sort_column, self.sort_order, node_parent)


    def clear(self):
        #clear the model
        self.beginResetModel()
        self.rootItem = PNTaxa_treeItem(None)
        self.parent_nodes = {}
        self.items = []
        self.endResetModel()

    def refreshData(self, new_PNTaxa_items = None):
    #refresh the entire model with the new items
        #save the items before clear
        if not new_PNTaxa_items:
            new_PNTaxa_items = self.items
        self.clear()
        #set the items list
        self.items = new_PNTaxa_items

        #reset the model and setup the new data
        self.beginResetModel()
        # self.rootItem = PNTaxa_treeItem(None)
        # self.parent_nodes = {}
        self.setupModelData()
        self.endResetModel()

    def setupModelData(self, item = None):
    #append a list of node to the model, if idparent = None => Root otherwise search for idtaxonref= idparent
        if item:
            items = [item]
        else:
            items = self.items
        
        # first loop, create a dictionnary for every items
        dict_parent = {item.idtaxonref: item.id_parent for item in self.items}

        # second loop to detect parents node(id_parent is None)
        for item in items:
            node_parent = dict_parent.get(item.id_parent, None)
            if node_parent is None:
                # If no parent is found, create a new root item
                self.parent_nodes[item.idtaxonref] = PNTaxa_treeItem(item, self.rootItem)
                self.rootItem.appendChild(self.parent_nodes[item.idtaxonref])

        # third loop to create the children of the respective parent
        for item in items:
            #only add childs where id_rank >=21
            if getattr(item, 'id_rank', 0) < 21:
                continue
            idparent = getattr(item, 'id_parent', 0)
            if idparent in self.parent_nodes:

                # --- FILTER PUBLISHED ---
                valid_published = (
                    self.show_nodes_published == 1
                    or (self.show_nodes_published == 2 and item.published)
                    or (self.show_nodes_published == 0 and item.published is False)
                )
                # --- FILTER ACCEPTED ---
                valid_accepted = (
                    self.show_nodes_accepted == 1
                    or (self.show_nodes_accepted == 2 and item.accepted)
                    or (self.show_nodes_accepted == 0 and item.accepted is False)
                )
                #add the item only if it passes the two filters
                if valid_published and valid_accepted:
                    childItem = PNTaxa_treeItem(item, self.parent_nodes[idparent])
                    self.parent_nodes[item.idtaxonref] = childItem
                    self.parent_nodes[idparent].appendChild(childItem)
                    
        #delete nodes with no children according to flag show_nodes_with_children_only (= 2, checked state !)
        if self.show_nodes_with_children_only == 2:
            self.rootItem.childItems = [it for it in self.rootItem.childItems if it.childCount() != 0]
        #emit signal after refresh
        self.refresh_signal.emit()

    def taxa_count(self):
        #count the number of taxa (child items) in the model
        return sum(item.childCount() for item in self.parent_nodes.values())

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

        if item.itemData is None:
            return None
        elif role == Qt.DisplayRole:
            return item.data(col)
        elif role == Qt.UserRole:
            return item.itemData
        elif role == Qt.FontRole:
            if item.itemData and not getattr(item.itemData, 'published', True):
                font = QtGui.QFont()
                font.setItalic(True)
                return font
        elif col == 0 :
            if role == Qt.DecorationRole:
                _taxonref_score = item.itemData.authors_score
                _taxaname_score = item.itemData.taxaname_score
                colour1 = 1
                colour2 = 1
                if _taxaname_score is not None:
                    #colour according to taxaname_score
                    if _taxaname_score == 0:
                        colour1 = QtGui.QColor(255, 0, 0)
                    elif _taxaname_score == 1:
                        colour1 = QtGui.QColor(0, 255, 0)
                    else:
                        colour1 = QtGui.QColor(255, 255, 0)
                    #colour according to taxonref_score
                    if _taxonref_score == 0:
                        colour2 = QtGui.QColor(255, 0, 0)
                    elif _taxonref_score == 1:
                        colour2 = QtGui.QColor(0, 255, 0)
                    elif _taxaname_score is not None:
                        colour2 = QtGui.QColor(255, 255, 0)
                #create the mask for both ellipses
                px = QtGui.QPixmap(20, 10)
                px.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(px)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)                        
                #First ellipse for taxaname_score
                r1 = QtCore.QRect(1, 1, 8, 8)
                painter.setBrush(colour1)
                painter.drawEllipse(r1)
                #First ellipse for _taxonref_score
                r1 = QtCore.QRect(12, 1, 8, 8)
                painter.setBrush(colour2)
                painter.drawEllipse(r1)
                painter.end()
                return QtGui.QIcon(px)

            elif role == Qt.TextAlignmentRole:
                if hasattr(item.itemData, 'id_rank') and item.itemData.id_rank >= 21:
                    return Qt.AlignRight | Qt.AlignVCenter
                else:
                    return Qt.AlignLeft | Qt.AlignVCenter
            elif role == Qt.ToolTipRole:
                published = getattr(item.itemData, 'published', False)
                accepted = getattr(item.itemData, 'accepted', False)
                parts = []
                # Explanation of the taxaname score
                parts.append(f"Taxaname: {item.itemData.taxaname_percent}")
                parts.append(f"Authors: {item.itemData.authors_percent}")
                # Explanation of the publication status
                parts.append(f"Published: {published}")
                parts.append(f"Accepted: {accepted}")

                # parts.append("Published" if published else "Not published")
                # parts.append("Accepted" if accepted else "Not accepted")
                return "\n".join(parts)
        elif col == 1  and role == Qt.DecorationRole:
            px = QtGui.QPixmap(26, 12)
            px.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(px)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            #create rectangle for published status
            published = getattr(item.itemData, 'published', False)
            r2 = QtCore.QRect(1, 1, 10, 10)
            colour = QtGui.QColor(0, 255, 0) if published else QtGui.QColor(255, 0, 0)
            painter.setBrush(colour)
            painter.drawRect(r2)
            #create rectangle for accepted status
            accepted = getattr(item.itemData, 'accepted', False)
            r2 = QtCore.QRect(15, 1, 10, 10)
            colour = QtGui.QColor(0, 255, 0) if accepted else QtGui.QColor(255, 0, 0)
            painter.setBrush(colour)
            painter.drawRect(r2)

            painter.end()
            return QtGui.QIcon(px)
        


    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header_labels[section]
        return None


####################

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
class PNSynonym_edit (QtWidgets.QWidget):
# add/update a new synonym to a idtaxonref or search for a idtaxonref (PN_TaxaSearch) according to a synonym 
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




# class PN_move_taxaname(QtWidgets.QMainWindow):
#     def __init__(self, myPNTaxa, merge = False): # move toward a same id_rank if merge
#         super().__init__()
#         self.PNTaxa = myPNTaxa
#         self.merge = merge
#         self.window = uic.loadUi("ui/pn_movetaxa.ui")
#         model = QtGui.QStandardItemModel()
#         #tab_header = []
#         #tab_header.append('Current Taxa name')
#         #tab_header.append('Category')
#         # tab_header.append('New Taxa name')
#         # model.setHorizontalHeaderLabels(tab_header)
#         # self.window.tableView_newtaxa.setModel(model)
#         # self.window.tableView_newtaxa.horizontalHeader().setStretchLastSection(True)
#         self.window.comboBox_category.addItems(['Nomenclatural', 'Taxinomic'])
#         self.window.comboBox_category.setCurrentIndex(0)
#         self.window.comboBox_taxa.completer().setCompletionMode(QCompleter.PopupCompletion)
#         self.window.comboBox_taxa.activated.connect(self.set_newtaxanames)

#         model = QtGui.QStandardItemModel()
#         model.setHorizontalHeaderLabels(['Rank','Taxon'])
#         # self.window.trView_childs.setModel(model)
#         # self.window.trView_childs.setColumnWidth(0,250)
#         # self.window.trView_childs.setHeaderHidden(True)  

#         button_OK = self.window.buttonBox
#         button_OK.button(QDialogButtonBox.Apply).clicked.connect (self.accept) 
#         button_OK.button(QDialogButtonBox.Close).clicked.connect (self.close) #button_OK.accepted.connect (self.accept) 
#         #button_OK.rejected.connect (self.close)

#         #initialize list and dictionnary
#         self.comboBox_taxa_query = None
#         self.updated = False
#         self.parent = self.PNTaxa.parent_name
#         self.window.categoryLabel.setVisible(self.merge)
#         self.window.comboBox_category.setVisible(self.merge)

#         #check for mode
#         if self.merge:
#             self.idrankmin = self.PNTaxa.id_rank
#             self.idrankmax = self.PNTaxa.id_rank + 1
#             self.parent = self.PNTaxa.taxaname
#             #self.window.comboBox_category.activated.connect(self.alter_category)
#             self.window.setWindowTitle("Merge reference")
#             self.window.taxaLineEdit.setText(self.PNTaxa.taxonref)
#             self.window.taxaLabel.setText("Merge")
#             self.window.toLabel.setText("With")
#             self.comboBox_taxa_setdata()
#         else: #Move
#             self.idrankmin = self.PNTaxa.id_rankparent
#             self.idrankmax = self.PNTaxa.id_rank
#             self.window.setWindowTitle("Move reference")
#             self.window.taxaLabel.setText("Move")
#             self.window.toLabel.setText("To")
#             self.window.taxaLineEdit.setText(self.PNTaxa.taxonref)
#             #self.window.comboBox_taxa.activated.connect(self.set_newtaxanames) 
#             self.comboBox_taxa_setdata()
#         self.window.setMaximumHeight(1)
#     @property
#     def selecteditem(self):
#         index = self.window.comboBox_taxa.currentIndex()
#         self.comboBox_taxa_query.seek(index)
#         return PNTaxa (self.comboBox_taxa_query.value("id_taxonref"), 
#                         self.comboBox_taxa_query.value("taxaname"),
#                         self.comboBox_taxa_query.value("authors"),
#                         self.comboBox_taxa_query.value("id_rank"),
#                         )

#     #alter the sign of merge taxa
#     # def alter_category(self):
#     #     model = self.window.trView_childs.model()
#     #     if model.rowCount() == 0:
#     #         return
#     #     txt_value = model.item(0,1).data(0)
#     #     if self.window.comboBox_category.currentIndex() == 0:
#     #         txt_value = txt_value.replace(chr(61), chr(8801))
#     #     else:
#     #         txt_value = txt_value.replace(chr(8801), chr(61))
#     #     model.item(0,1).setText(txt_value)
        
#     #return a str value (change None in '')
#     # def str_query_value(self, query_value):
#     #     if str(query_value).lower() in ['','null']:
#     #         return ''
#     #     else:
#     #         return str(query_value)

#     def set_newtaxanames(self):
#         index = self.window.comboBox_taxa.currentIndex()
#         self.comboBox_taxa_query.seek(index)
#         str_idtaxonref = str(self.PNTaxa.idtaxonref)
#         str_idnewparent = str(self.selecteditem.idtaxonref)
#         # model = self.window.trView_childs.model()
#         # model.setRowCount(0)
#         # model.setColumnCount(4)
#         _rankname = self.selecteditem.rank_name #commons.get_dict_rank_value(self.selecteditem.idtaxonref.id_rank,'rank_name')
#         # item =  QtGui.QStandardItem(_rankname)
#         # item1 = QtGui.QStandardItem(self.selecteditem.taxonref)
#         # item2 = QtGui.QStandardItem(str_idnewparent)
#         # item3 = QtGui.QStandardItem(str(self.selecteditem.rank_name))
#         txt_taxa = 'Move Taxon to new ' + self.selecteditem.rank_name
#         self.sql_query_save = ''
#         # sql_function = "taxonomy.pn_taxa_move"
#         if self.merge:
#             category_synonym = chr(8801)
#             if self.window.comboBox_category.currentIndex() > 0:
#                 category_synonym = chr(61)
#             txt_taxa = self.PNTaxa.taxonref +  ' ' + category_synonym + ' ' +self.selecteditem.taxonref
#             # item1 = QtGui.QStandardItem(txt_taxa)
#             # item2 = QtGui.QStandardItem(str_idtaxonref)
#             # sql_function = "taxonomy.pn_taxa_merge"
#         self.window.label_result.setText(txt_taxa)

#         #model.appendRow([item, item1, item2, item3],)
#         category = self.window.comboBox_category.currentText()
        
#         # sql_function += "(" + str_idtaxonref +"," + str_idnewparent + ",$$" + category + "$$," + "FALSE" + ") a"
#         # self.sql_query_save = "SELECT a.id_taxonref, a.taxaname, a.authors, a.id_rank FROM " + sql_function

#         # sql_query = "SELECT a.id_taxonref, a.taxaname, a.authors, a.id_rank, a.id_parent, CONCAT_WS (' ',a.taxaname, a.authors) AS new_taxonref,"
#         # sql_query += "(b.taxaname IS NULL) AS isvalid FROM "
#         # sql_query += sql_function #+ "(" + str_idtaxonref +"," + str_idnewparent + ",$$" + category + "$$," + "FALSE" + ") a"
#         # sql_query += "\nLEFT JOIN taxonomy.taxa_reference b ON a.taxaname = b.taxaname"
#         # sql_query += " ORDER BY id_rank, a.taxaname"
#         if self.merge:
#             sql_query = f"CALL taxonomy.pn_taxa_set_synonymy({str_idtaxonref}, {str_idnewparent}, '{category}');"
            
#         else:
#             sql_query = "UPDATE taxonomy.taxa_reference SET id_parent = " + str_idnewparent + " WHERE id_taxonref = " + str_idtaxonref
#         #print  (sql_query)
#         # self.window.trView_childs.hideColumn(2)
#         # self.window.trView_childs.hideColumn(3)
#         # self.window.trView_childs.expandAll()
#         # self.window.trView_childs.resizeColumnToContents(0)

#         #query = QtSql.QSqlQuery (sql_query)
#         #self.sql_query_save = sql_query
#         return sql_query

#     def comboBox_taxa_setdata(self):
#         str_minidrank = str(self.idrankmin)
#         str_maxidrank = str(self.idrankmax)
#         sql_query = "SELECT a.id_taxonref, a.basename, a.id_rank, a.taxaname, a.authors, a.taxonref"
#         sql_query += "\nFROM taxonomy.taxa_names a"
#         if self.idrankmin < 21:
#             sql_query += f"\nWHERE a.id_rank >= {str_minidrank} AND a.id_rank < {str_maxidrank}"
#         else:
#             sql_query += "\nWHERE a.id_rank >=21"
#         sql_query += "\nORDER BY taxonref"
#         #print (sql_query)
#         index = -1
#         self.comboBox_taxa_query = QtSql.QSqlQuery (sql_query)
#         while self.comboBox_taxa_query.next():
#             self.window.comboBox_taxa.addItem(str(self.comboBox_taxa_query.value('taxonref')))
#             if self.comboBox_taxa_query.value('taxaname') == self.parent:
#                 index = self.window.comboBox_taxa.count()-1
#         self.window.comboBox_taxa.setCurrentIndex(index)

#     def close(self):
#         self.window.close()
        
#     def accept(self):
#         code_error =''
#         msg = ''
#         self.updated = False
#         self.sql_query_save = self.set_newtaxanames()
#         if len(self.sql_query_save)>0:
#             sql_query = self.sql_query_save #.replace("FALSE","TRUE")
#             result = QtSql.QSqlQuery (sql_query)
#             code_error = result.lastError().nativeErrorCode ()
       
#         if len(code_error) == 0:
#             self.updated_datas = []
#             str_idnewparent = str(self.comboBox_taxa_query.value("id_taxonref"))
#             sql_query = f"SELECT * FROM taxonomy.pn_taxa_childs({str_idnewparent}, FALSE)"
#             result = QtSql.QSqlQuery (sql_query)
#             while result.next():
#                 self.updated_datas.append(PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
#                                                  result.value("id_rank")))
#             self.updated = True
#             self.close() 
#             return True
#         else:
#             msg = commons.postgres_error(result.lastError())
#         QMessageBox.critical(self.window, "Database error", msg, QMessageBox.Ok)

#         return self.updated

#     def show(self):
#         self.window.show()
#         self.window.exec_()















# if __name__ == '__main__':
#     app=QtWidgets.QApplication(sys.argv)

#     window=MainWindow()
#     window.show()
#     app.exec_()