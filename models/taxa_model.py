# Standard library
import re
import time

# Third-party
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QSortFilterProxyModel

# Internal
from core import functions
from core.widgets import load_ui_from_resources
from models.api_taxonomy import API_Taxonomy

########################################
APIkey_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
########################################

# Main classe to store a taxaname with some properties
class PNTaxa(object):
    def __init__(self, idtaxonref, taxaname = None, authors = None, idrank= None, published = None, accepted = None):
        self.id_taxonref = idtaxonref
        self.dict_species = None
        self.id_parent = None
        if taxaname:
            self.taxaname = taxaname
            self.authors = authors
            self.id_rank = idrank
            self.published = published
            self.accepted = accepted
        else:
            self.fill_from_dbase()


    def _part_name(self, fieldname):
        #create the dictionnary of species parts if not yet done
        if self.dict_species is None:
            self.dict_species = functions.get_dict_from_species(self.taxonref)
        if self.dict_species is None:
            self.dict_species = {}
        #search and return the part (ex: basename, name, autonym, authors,...) from the dictionnary
        if fieldname in self.dict_species:
            return self.dict_species[fieldname]
        else:
            return None
        
    def fill_from_dbase(self):
        """fill the class with values from the database according to the id_taxonref"""
        dict_taxa = functions.dbtaxa().db_get_taxon(self.id_taxonref)
        if dict_taxa is not None:
            self.taxaname = dict_taxa.get("taxaname", None)
            self.authors = dict_taxa.get("authors", None)
            self.id_rank = dict_taxa.get("id_rank", None)
            self.published = dict_taxa.get("published", None)
            self.accepted = dict_taxa.get("accepted", None)
            self.id_parent = dict_taxa.get("id_parent", None)

    @property
    def idtaxonref(self):
        try:
            return int(self.id_taxonref)
        except Exception:
            return 0

    @property
    def rank_name (self):
        try :
            txt_rk = functions.dbtaxa().db_get_rank(self.id_rank, 'rank_name')
        except Exception:
            txt_rk = 'Unknown'
        return txt_rk

    @property
    def id_rankparent (self):
        try :
            id_rp = functions.dbtaxa().db_get_rank(self.id_rank, 'id_rankparent')
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
        return self._part_name ("autonym")

    @property
    def basename (self):
        if self.id_rank < 21:
            return self.taxaname.lower()
        return self._part_name ("basename")

    @property
    def simple_taxaname (self):
        if self.id_rank < 21:
            return self.taxaname
        return self._part_name ("name")
    
    @property
    def json_names(self):
        """     
        Return a json (dictionnary of sub-dictionnaries) of the set of names for a id_taxonref
        """
        return functions.dbtaxa().db_get_names(self.idtaxonref)

    @property 
    def json_metadata (self):
        """     
        Return a json (dictionnary of sub-dictionnaries) of for metadata from a id_taxonref
        """              
        return functions.dbtaxa().db_get_metadata(self.idtaxonref)
    
    @property
    def json_properties_count(self):
        """     
        Return a json (dictionnary of sub-dictionnaries) of the count of taxa properties(jsonb) from a id_taxonref = sum (json_properties) of child taxa
        """        
        return functions.dbtaxa().db_get_properties_count(self.idtaxonref)

    @property
    def json_properties(self):
        """     
        Return a json (dictionnary of sub-dictionnaries of a taxon properties(jsonb) for a id_taxonref
        """
        return functions.dbtaxa().db_get_properties(self.idtaxonref)

    @property
    def list_hierarchy(self):
        """     
        Return a json (dictionnary of sub-dictionnaries) of hierarchy (parent + childs) for a id_taxonref
        """
        ls_hierarchy = functions.dbtaxa().db_get_list_hierarchy(self.idtaxonref, self.id_rank)
        return ls_hierarchy






#class to represent taxa with scoring information
class PNTaxa_with_Score(PNTaxa):
    """Subclass of PNTaxa with additional properties for scoring."""
    def __init__(self, idtaxonref, taxaname = None, authors = None, idrank= None, published = None, accepted = None):
        super().__init__(idtaxonref, taxaname, authors, idrank, published, accepted)
        self.taxaname_score = None
        self.authors_score = None
        self.api_total = 0
        self.visible = True

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


class PN_TaxaSearch(QtWidgets.QWidget):
    """
    The PN_TaxaSearch class is a custom class that inherits from QtWidgets.QWidget.
    It is designed to display a search widget composed of a search text and a treeview result with matched taxa and score.

    Attributes:
        lineEdit_search_taxa (QtWidgets.QLineEdit): The search text input field.
        treeview_scoretaxa (QtWidgets.QTreeView): The treeview widget that displays the search results.

    Methods:
        __init__ : Initializes the search widget.
        setText : Sets the text of the search input field.
        selectedTaxa : Returns the selected taxon object.
        selectedTaxonRef : Returns the reference of the selected taxon.
        selectedScore : Returns the score of the selected taxon.
        selectedTaxaId : Returns the ID of the selected taxon.

    Signals:
        selectionChanged (str): Emitted when the selection in the treeview changes.
        doubleClicked (object): Emitted when an item in the treeview is double-clicked.

    """
    selectionChanged = pyqtSignal(str)
    doubleClicked = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        # load the GUI
        self.lineEdit_search_taxa = QtWidgets.QLineEdit(self)
        self.treeview_scoretaxa = QtWidgets.QTreeView(self)
        self.lineEdit_search_taxa.setPlaceholderText("search taxa")
        self.treeview_scoretaxa.setEditTriggers(QtWidgets.QTreeView.NoEditTriggers)
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
        layout = QtWidgets.QVBoxLayout()
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
        #get the list of search names with score
        ls_searchnames = functions.dbtaxa().db_get_fuzzynames(search_txt, 0.4)
        if ls_searchnames is None:
            return
        #set the item into the model
        for name, item in ls_searchnames.items():
            id_taxonref = item['id_taxonref']
            ref_item = [QtGui.QStandardItem(name), QtGui.QStandardItem(item['score'])]
            ref_item[0].setData(id_taxonref, Qt.UserRole)
            ref_item[1].setTextAlignment(Qt.AlignCenter)
            self.model.appendRow(ref_item)
            #set score in red if below 50
            if item['score'] < 50:
                _color =  QtGui.QColor(255, 0, 0)
                ref_item[1].setData(QtGui.QBrush(_color), Qt.ForegroundRole)
            for synonym in item['synonym']:
                ref_item[0].appendRow ([QtGui.QStandardItem(synonym)])
                
        if self.model.rowCount() > 0:
            self.treeview_scoretaxa.resizeColumnToContents(1)
            self.treeview_scoretaxa.setExpanded(self.model.index(0, 0), True)
            self.treeview_scoretaxa.header().setStretchLastSection(False)
            self.treeview_scoretaxa.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.treeview_scoretaxa.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)



#class to search taxa through API
class PNTaxa_searchAPI (QtCore.QThread):
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
        QtCore.QThread.__init__(self, parent)
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
        model = self.model()
        model.clear()
        
        ls_hierarchy = myPNTaxa.list_hierarchy
        if not ls_hierarchy:
            return
        
        ls_pn_taxa = []
        for item in ls_hierarchy:
            id_taxonref = item['id_taxonref']
            idrank = item['id_rank']
            taxaname = item['taxaname'].strip()
            authors = item['authors'].strip()
            published = item['published']
            accepted = item['accepted']
            idparent = item['id_parent']
            pn_item = PNTaxa(id_taxonref, taxaname, authors, idrank, published, accepted)
            pn_item.id_parent = idparent
            ls_pn_taxa.append(pn_item)

        dict_idtaxonref = {}
        for item in ls_pn_taxa:
            _itemrank = item.rank_name
            if not item.published and item.id_rank >=3:
                _itemrank += " (ined.)"
            dict_idtaxonref[item.idtaxonref] = [QtGui.QStandardItem(_itemrank), QtGui.QStandardItem(item.taxonref)]

        for item in ls_pn_taxa:
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
        self.window = load_ui_from_resources("pn_addtaxa.ui")
        self.window.trView_childs.setVisible(False)
        self.window.combo_group.setVisible(False)
        self.window.checkBox_filter_new.setVisible(False)
        button_OK = self.window.buttonBox
        button_OK.rejected.connect (self.close)
        button_apply = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        button_close = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Close)        
        button_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        button_close.setIcon (QtGui.QIcon(":/icons/nok.png"))
        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        #set the model to the treeview_childs
        model = QtGui.QStandardItemModel()
        self.proxy = self.CheckableOnlyProxy()
        self.proxy.setSourceModel(model)
        self.window.trView_childs.setModel(self.proxy)
        self.window.trView_childs.setColumnWidth(0,250)
        #manage the combo_group
        self.window.combo_group.addItem("All names")
        self.window.combo_group.addItem(myPNTaxa.taxaname)
        lst = functions.dbtaxa().db_get_apg4_clades()
        for clade in lst:
            self.window.combo_group.addItem(clade)
        self.window.combo_group.setCurrentIndex(1)
        #Manage the taxonomy_api class
        self.taxonomy_api = API_Taxonomy()
        _idrank = self.PNTaxa.id_rank
        api_class_toadd = {}
        #add Tab only for classes with a get_children function
        if _idrank <10:
            self.window.tabWidget_main.addTab(QtWidgets.QWidget(), 'WFO')       
        for key, value in self.taxonomy_api.api_classes.items():
            _children = value.get("children", None)
            if _children and _idrank >=_children:
                api_class_toadd[key] = value     
        for api_class in api_class_toadd.keys():
            self.window.tabWidget_main.addTab(QtWidgets.QWidget(), api_class.title())

        #manage slot and signals
        self.window.tabWidget_main.currentChanged.connect(self.alter_category)
        self.window.basenameLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.authorsLineEdit.textChanged.connect (self.taxaLineEdit_setdata)
        self.window.rankComboBox.activated.connect(self.taxaLineEdit_setdata)
        self.window.combo_group.activated.connect(self.refresh_category)
        self.window.checkBox_filter_new.toggled.connect(self.click_view_onlyNew)
        self.window.checkBox_published.toggled.connect(self.taxaLineEdit_setdata)
        self.window.checkBox_accepted.toggled.connect(self.taxaLineEdit_setdata)

        #load rankcombo_box
        self.rankComboBox_setdata()      
        self.taxaLineEdit_setdata()


    class CheckableOnlyProxy(QSortFilterProxyModel):
    #class as a proxy model to filter only checkable items
        def __init__(self):
            super().__init__()
            self.only_checkable = False   # ← OFF par défaut

        def setOnlyCheckable(self, enabled: bool):
            self.only_checkable = enabled
            self.invalidateFilter()

        def filterAcceptsRow(self, row, parent):
            # desactivated filter (all rows)
            if not self.only_checkable:
                return True
            model = self.sourceModel()
            index = model.index(row, 0, parent)
            if not index.isValid():
                return False
            # visible if checkable
            if model.flags(index) & Qt.ItemIsUserCheckable:
                return True
            # visible if at least one child is checkable
            for i in range(model.rowCount(index)):
                if self.filterAcceptsRow(i, index):
                    return True
            return False
    
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

            prefix = functions.dbtaxa().db_get_rank(id_rank, 'prefix') 
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
        self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(_apply)


    def rankComboBox_setdata(self):
        rank_childs = functions.dbtaxa().db_get_rank(self.PNTaxa.id_rank, "childs") 
        #self.data_rank = []
        index = -1
        for idrank in rank_childs:
            rank_name = functions.dbtaxa().db_get_rank(idrank, 'rank_name')
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
        ctrl_pressed = QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier
        
        #disconnect the itemChanged signal
        try:
            #model = self.window.trView_childs.model()
            model = self.proxy.sourceModel()
            model.itemChanged.disconnect()
        except Exception:
            pass

        if state == 2 :
            self.checked_parent(checked_item)
            _apply = True
            if ctrl_pressed:
                self.checked_children(checked_item)
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
        #reconnect the itemChanged signalmodel.itemChanged.connect(self.trview_childs_checked_click)
        self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(_apply)
        model.itemChanged.connect(self.trview_childs_checked_click)


    def unchecked_child(self, item):
    #recursive function to uncheck childrens
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
        
    def checked_children(self, item):
    #recursive function to check childrens
        for row in range(item.rowCount()):
            child = item.child(row)
            if child and child.isCheckable():
                child.setCheckState(2)
                self.checked_children(child)
    
    def refresh_category (self):
    #refresh the current category
        index = self.window.tabWidget_main.currentIndex()
        self.alter_category(index)
        
    def click_view_onlyNew (self, value):
        self.proxy.setOnlyCheckable(value)
        self.window.trView_childs.expandAll()
        self.window.trView_childs.resizeColumnToContents(0)
        self.window.trView_childs.resizeColumnToContents(1)

    def alter_category(self, index):
        if index is None:
            index = self.window.tabWidget_main.currentIndex()
    #change tabWidget_main item (user search or internet search)
        self.window.trView_childs.setVisible(False)
        self.window.combo_group.setVisible(False)
        self.window.checkBox_filter_new.setVisible(False)
    #index = 0 --> USER
        if index == 0 : 
            self.window.label_2.setText("Add taxon")
            self.window.taxaLineEdit_result.setVisible(True)
            self.taxaLineEdit_setdata()
            return
    #else --> WFO or API
        _apibase = self.window.tabWidget_main.tabText(index)
        self.window.taxaLineEdit_result.setVisible(False)
        self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        #get data (list of dictionnary) from API class function get_children"
        # a list of childs elements
        #exemple {"id" : '10', "taxaname" : 'Genus species', "authors" : 'Not me', "rank" : 'Species', "idparent" : '1'}
        # note that the id_parent of each taxa except the first one must be in the list, if not it will excluded
        #self.window.frame_filter.setVisible(True)
        self.window.combo_group.setVisible (False)
    #add the widgets to the layout
        layout = self.window.tabWidget_main.currentWidget().layout()
        if layout is None:
            layout = QtWidgets.QGridLayout()
            self.window.tabWidget_main.currentWidget().setLayout(layout)
        #add the widget to the layout
        layout.addWidget(self.window.combo_group)
        layout.addWidget(self.window.trView_childs)
        self.window.trView_childs.setVisible(True)

    #draw the list in the tree view
        self.window.label_2.setText("Searching into " + _apibase + "...")
        model = self.proxy.sourceModel()
        model.setRowCount(0)
        model.setColumnCount(2)
        QtWidgets.QApplication.processEvents()
        msg = "Null Value"
        _apibase = _apibase.upper()
        self.table_taxa = []        
        if _apibase == "WFO": #add taxa from the internal datalist (WFO)
            self.window.combo_group.setVisible(True)
            #_filter the taxasearch with a keyword (None or from combo_clade)
            _filter = None
            if self.window.combo_group.currentIndex() > 0:
                _filter = self.window.combo_group.currentText()
            self.table_taxa = functions.dbtaxa().db_get_taxa_wfo (_filter)
        else: #use seulf.taxonomy_api

            
            _name = self.PNTaxa.simple_taxaname
            _rank = self.PNTaxa.rank_name
            #set the key (if tropicos)
            _key = None
            if _apibase == "TROPICOS":
                _key = APIkey_tropicos
            #get the class and errors
            result = self.taxonomy_api.get_APIclass(_apibase, _name, _rank, _key)
            msg = self.taxonomy_api._api_class.API_error
            #get children
            if result:
                self.table_taxa = result.get_children()
            if self.table_taxa:
                #search for all names into the dbase (return a dictionnary id_taxonref by taxaname)       
                names = [d["taxaname"].strip() for d in self.table_taxa]     
                dict_id_taxonref = functions.dbtaxa().db_get_searchnames(names)
                #add an index dictionnary to search for taxaname from id_taxonref
                dict_parent = {item["id"]: item["taxaname"] for item in self.table_taxa}
                #ajust the dictionnary, add special fields and construct the query
                for taxa in self.table_taxa:                
                    _tabtaxa = taxa["taxaname"].split()
                    taxa["id_taxonref"] = dict_id_taxonref.get(taxa["taxaname"], 0)
                    taxa["parentname"] = dict_parent.get(taxa["id_parent"], "")
                    taxa["basename"] = _tabtaxa[-1]
                    taxa["authors"] = functions.get_str_value(taxa["authors"])
                    taxa["id_rank"] = functions.dbtaxa().db_get_rank(taxa["rank"], "id_rank")
                    taxa["published"] = len (taxa["authors"]) > 0
                    taxa["accepted"] = True
                    taxa["autonym"] = False
                    if taxa["id_rank"] > 21 and len(_tabtaxa) >= 4:
                        taxa["autonym"] = (_tabtaxa[1] == taxa["basename"])

        #check existing taxa and drax the treeview model
        if self.table_taxa:
            # #set the id_taxonref for already existing taxa
            # for taxa in self.table_taxa:
            #     taxa["id_taxonref"] = dict_id_taxonref.get(taxa["taxaname"], 0)
            self.draw_list ()
            self.window.trView_childs.sortByColumn(1, Qt.AscendingOrder)
        #set an item msg if not found
        if model.rowCount() ==0:
            msg = msg or f"{self.PNTaxa.taxaname} is not found"
            model.appendRow([QtGui.QStandardItem("< No data > "), QtGui.QStandardItem(msg)],)
            self.proxy.setOnlyCheckable(False)
        #ajust columns

        self.window.trView_childs.resizeColumnToContents(0)
        self.window.trView_childs.resizeColumnToContents(1)
        #self.window.trView_childs.expandToDepth(1)
        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()


    def draw_list(self):
    #draw the hierarchical tree according to idparent and id
        if self.window.tabWidget_main.currentIndex() == 0:
            return
        #model = self.window.trView_childs.model()
        model = self.proxy.sourceModel()
        model.setRowCount(0)
        self.checkable = 0
        #disconnect the itemChanged signal
        try:
            model.itemChanged.disconnect(self.trview_childs_checked_click)
        except Exception:
            pass

        def draw_list_recursive(taxon, parent_item=None):
            #internal recursive function to build hierarchical tree according to idparent and id
            taxaref = f'{taxon["taxaname"]} {taxon.get("authors", "")}'.strip()
            _checkable = (taxon["id_taxonref"] == 0 and not taxon["autonym"]  )
            item = QtGui.QStandardItem(str(taxon["rank"]))         
            item1 = QtGui.QStandardItem(taxaref.strip())       
            item.setCheckable(False)
            item.setData(None, Qt.CheckStateRole)
            item.setCheckable(_checkable)
            taxon["item"] = item
            if _checkable:
                self.checkable += 1
            #add node to the model
            if parent_item is None:
                model.appendRow([item, item1])
            else:
                parent_item.appendRow([item, item1])
            for child in taxon["children"]:
                draw_list_recursive(child, item)

        #browse the table_taxa to build a tree structure
         #first create a dictionnary of parent
        dict_parent = {item["id"]: item for item in self.table_taxa}
        roots = []
        for taxa in self.table_taxa:
            taxa["children"]= []
            node_parent = dict_parent.get(taxa["id_parent"], None)
            if node_parent is None:
                roots.append(taxa)
            else:
                node_parent["children"].append(taxa)
        #add each root node to the model by recursive function
        for root in roots:
            draw_list_recursive(root)

        self.window.trView_childs.expandAll()
        #self.window.trView_childs.expandToDepth(1)
            
        #add message to the label
        index = self.window.tabWidget_main.currentIndex()
        _api_name = self.window.tabWidget_main.tabText(index).title()
        self.window.checkBox_filter_new.setVisible(False)
        if self.checkable > 0:
            self.window.checkBox_filter_new.setVisible(True)
            self.window.label_2.setText("Check taxa to add (Ctrl to add children)")
        else:
            self.window.label_2.setText("No new taxa to add from " + _api_name)
        #reconnect the itemChanged signal
        model.itemChanged.connect(self.trview_childs_checked_click) 
                    
    # def get_table_taxa_item(self,id, key):
    # #get a value from a key and id in the table_taxa
    #     return next((t.get(key, '') for t in self.table_taxa if t.get("id") == id), '')


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
        self.window = load_ui_from_resources("pn_edittaxa.ui")
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
        button_apply = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        button_close = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Close)

        button_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        button_close.setIcon (QtGui.QIcon(":/icons/nok.png"))

        button_apply.setEnabled(False)
        button_apply.clicked.connect(self.apply)
        self.comboBox_parent_setdata()
        self.taxaLineEdit_setdata()
        #self.input_name = self.window.taxaLineEdit.text()

    def comboBox_parent_setdata(self):
        #fill the combo box with valid parents for the current taxon
        self.window.parent_comboBox.clear()
        ls_valid_parents = functions.dbtaxa().db_get_valid_parents(self.PNTaxa.idtaxonref)
        index = -1
        for key, value in ls_valid_parents.items():
            self.window.parent_comboBox.addItem (key, value)
            if value == self.PNTaxa.id_parent:
                index = self.window.parent_comboBox.count()-1
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
                prefix = functions.dbtaxa().db_get_rank(id_rank, 'prefix')
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
        self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply).setEnabled(_apply)

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
        dict_tosave = {"id_taxonref":idtaxonref, "basename":newbasename, "authors":newauthors, "id_parent":newidparent, "published":published, "accepted":accepted, "id_rank" :self.PNTaxa.id_rank}
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
        #set the ui
        self.window = load_ui_from_resources("pn_movetaxa.ui")
        self.window.setMaximumHeight(1)
        
        self.window.comboBox_category.addItems(['Nomenclatural', 'Taxinomic'])
        self.window.comboBox_category.setCurrentIndex(0)
        self.window.comboBox_category.activated.connect(self.set_newtaxanames)
        
        self.window.comboBox_taxa.completer().setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.window.comboBox_taxa.activated.connect(self.set_newtaxanames)
        #button_OK = self.window.buttonBox

        button_apply = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        button_close = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Close)        
        button_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        button_close.setIcon (QtGui.QIcon(":/icons/nok.png"))

        button_apply.clicked.connect (self.accept) 
        button_close.clicked.connect (self.close)
        
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
        return


    def comboBox_taxa_setdata(self):
        #fill the combo box with valid sibling to merge for the current taxon
        self.window.comboBox_taxa.clear()
        ls_valid_sibling = functions.dbtaxa().db_get_valid_merges(self.PNTaxa.idtaxonref)
        index = -1
        for key, value in ls_valid_sibling.items():
            self.window.comboBox_taxa.addItem (key, value)
            if value == self.PNTaxa.idtaxonref:
                index = self.window.comboBox_taxa.count()-1
        self.window.comboBox_taxa.setCurrentIndex(index)
               
    def accept(self):
    #Valid the form, save the data into the dbase and return
    #a list of PNTaxa that have been updated
        if self.PNTaxa.idtaxonref == self.selected_idtaxonref:
            return
        self.updated = True
        self.close()
    
    
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
            #_authors = get(self.itemData.authors,'')
            _authors = self.itemData.authors or ''
            if self.itemData.isautonym:
                _authors = '[Autonym]'
            elif not self.itemData.published:
                _authors += ' (ined.)' #ined.'
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
        self.show_nodes_checked = 1
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
        self.beginResetModel()
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
                # self.beginInsertRows(
                #     self.createIndex(node_parent.row(), 0, node_parent),
                #     node_parent.childCount(),
                #     node_parent.childCount()
                # )
                self.items.append(myPNTaxa)
                self.setupModelData(myPNTaxa)
                #self.endInsertRows()
                #sort the model
                #self.sortItems(self.sort_column, self.sort_order, node_parent)
        self.endResetModel()

    # def refreshFilters(self):
    #     def match_filter(mode, value):
    #         if mode == 1:
    #             return True
    #         if mode == 2:
    #             return bool(value)
    #         return not bool(value)

    #     for item in self.items:
    #         node = self.getNode(item.idtaxonref)
    #         if node is None:
    #             continue
    #         parent = node.parentItem
    #         # --- COMBINED FILTER ---
    #         filters = [
    #                     (self.show_nodes_checked, item.taxaname_score),
    #                     (self.show_nodes_published, item.published),
    #                     (self.show_nodes_accepted, item.accepted),
    #                 ]
    #         _valid = parent is self.rootItem or all(match_filter(mode, value) for mode, value in filters)
    #         #print (_valid)
    #         if node in parent.childItems and not _valid:
    #             row = parent.childItems.index(node)
    #             self.beginRemoveRows(
    #                 self.createIndex(parent.row(), 0, parent),
    #                 row,
    #                 row
    #             )
    #             parent.childItems.pop(row)
    #             self.endRemoveRows()

    #         elif node not in parent.childItems and _valid:
    #             row = len(parent.childItems)
    #             self.beginInsertRows(
    #                 self.createIndex(parent.row(), 0, parent),
    #                 row,
    #                 row
    #             )
    #             parent.appendChild(node)
    #             self.endInsertRows()
    #     #self. beginResetModel()
    #     if self.show_nodes_with_children_only == 2:
    #         self.rootItem.childItems = [it for it in self.rootItem.childItems if it.childCount() != 0]
    #     #self.endResetModel()
    #     self.sortItems(self.sort_column, self.sort_order, self.rootItem)
    #                 #item.setVisible(valid_checked)


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
        # else:
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
                #if self.getNode(item.idtaxonref) is None:
                self.parent_nodes[item.idtaxonref] = PNTaxa_treeItem(item, self.rootItem)
                self.rootItem.appendChild(self.parent_nodes[item.idtaxonref])

        # third loop to create the children of the respective parent
        for item in items:
            #only add childs where id_rank >=21
            if getattr(item, 'id_rank', 0) < 21:
                continue
            idparent = getattr(item, 'id_parent', 0)
            if idparent in self.parent_nodes:
                childItem = PNTaxa_treeItem(item, self.parent_nodes[idparent])
                self.parent_nodes[item.idtaxonref] = childItem
                self.parent_nodes[idparent].appendChild(childItem)
        #emit signal to inform the model has been refreshed
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
    

####################
# Class to edit(New or update) synonym
class PNSynonym_edit (QtWidgets.QWidget):
# add/update a new synonym to a idtaxonref or search for a idtaxonref (PN_TaxaSearch) according to a synonym 
    button_click = pyqtSignal(object, int)
    add_signal  = pyqtSignal(str, str)
    edit_signal  = pyqtSignal(str, str)

    def __init__(self, myPNSynonym):
        super().__init__()
        #set the ui
        self.window = load_ui_from_resources("pn_editname.ui")
        self.Qline_name = self.window.name_linedit
        self.Qline_ref = self.window.taxaLineEdit
        self.Qcombobox = self.window.comboBox
        
        self.button_apply = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        button_close = self.window.buttonBox.button(QtWidgets.QDialogButtonBox.Close)        
        self.button_apply.setIcon (QtGui.QIcon(":/icons/ok.png"))
        button_close.setIcon (QtGui.QIcon(":/icons/nok.png"))

        self.myPNSynonym = myPNSynonym
        self.treeview_searchtaxa = None
        self.is_new = (self.myPNSynonym.synonym is None or self.myPNSynonym.idtaxonref == 0)
        self.Qline_name.textChanged.connect (self.valid_newname)
        self.Qcombobox.activated.connect(self.valid_newname)
        self.button_apply.clicked.connect (self.accept)
        button_close.clicked.connect (self.close)

    def setting_ui(self):
        #self.updated = False
        self.Qline_name.setReadOnly(not self.myPNSynonym.resolved)
        self.Qline_name.setText('') 
        self.window.setMaximumHeight(500)
        self.window.resize(500,500)
        self.Qcombobox.setCurrentText(str(self.myPNSynonym.category))
        self.Qline_name.setText(self.myPNSynonym.synonym)
        #resolved depends if idtaxonref is Null
        if not self.myPNSynonym.resolved:
            self.treeview_searchtaxa = PN_TaxaSearch()
            self.window.label_tip.setText('Select Reference...')
            #add the treeview_searchtaxa = Class PN_TaxaSearch() (cf. taxa_model.py)
            layout = self.window.QTreeViewSearch_layout
            layout.addWidget(self.treeview_searchtaxa)
            self.treeview_searchtaxa.setText(self.myPNSynonym.synonym)
            self.treeview_searchtaxa.selectionChanged.connect(self.valid_newname)
        else: #idtaxonref is not Null
            if self.is_new:
                self.window.label_tip.setText('New Synonym...')
            else:
                self.window.label_tip.setText('Edit Synonym...')
            self.Qline_ref.setText(self.myPNSynonym.taxon_ref)
            self.window.setMaximumHeight(1)
            self.Qline_name.setFocus()
        self.valid_newname()

    def show(self):
        self.setting_ui()
        self.window.show()
        self.window.exec()
        
    def close(self):
        self.window.close()

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
        self.button_apply.setEnabled(flag)

    def accept(self):
        #self.updated = False
        new_synonym = self.Qline_name.text().strip()
        new_category = self.Qcombobox.currentText().strip()
        if self.is_new:
            #add mode
            self.add_signal.emit(new_synonym, new_category)
        else:
            #edit mode
            self.edit_signal.emit(new_synonym, new_category)


