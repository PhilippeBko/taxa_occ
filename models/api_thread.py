import sys
#import json
import requests
from urllib.parse import quote_plus
import time
import re
from core import functions as commons
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup

class API_Thread (QThread):
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
        Initialize the thread with optional taxon model and API filter.
        """
        QThread.__init__(self, parent)
        self.PNTaxa_model = myPNTaxa
        self.status = 0
        self.list_api =  ["POWO","TAXREF","IPNI","TROPICOS","ENDEMIA","FLORICAL", "INATURALIST", "GBIF"]
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
        api_classes = {
            "TAXREF": API_TAXREF,
            "TROPICOS": API_TROPICOS,
            "IPNI": API_IPNI,
            "POWO": API_POWO,
            "FLORICAL": API_FLORICAL,
            "ENDEMIA": API_ENDEMIA,
            "INATURALIST": API_INATURALIST,
            "GBIF": API_GBIF,
        }
        
        #test for a effective connection
        try:
            requests.get("https://www.google.com", timeout=2)
        except Exception:
            self.Result_Signal.emit("NOTCONNECTED", None)
            return
        if self.PNTaxa_model is None:
            self.Result_Signal.emit("END", None)
            return
        self.status = 1
        for base in self.list_api:
            #check for status
            if self.status == 0: 
                return
            api_class = api_classes.get(base)
            if api_class:
                _classeAPI = api_class(self.PNTaxa_model)

            #get metadata
            _json = _classeAPI.get_metadata()
            if _json is None:
                continue
            _json = {k: v for k, v in _json.items() if v is not None}
            # add synonyms
            #use self.status a counter of successeful metadata queries (= API response)
            self.status += 1
            t_synonyms = _classeAPI.get_synonyms()
            if t_synonyms is not None:
                _json["synonyms"] = t_synonyms

            if self.status == 0 : 
                return
            _json["query time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.Result_Signal.emit(str(base), _json)
            if _json["url"] and _json["name"]:
                _list_api[base] = _json
            if self.status == 0 :
                return
            time.sleep(0.2)
        self.Result_Signal.emit("END", _list_api)

    @property 
    def total_api_calls(self):
        return (self.status-1)
        _total_api_servers = len(self.list_api)
        if _total_api_servers > 0:
            return int(100 * (self.status-1) / _total_api_servers)

##___class API_Abstract________________________
class API_Abstract ():
    """
    Abstract base class for biodiversity API wrappers.

    Provides common methods and attributes for querying taxa metadata,
    synonyms, and children, as well as utilities for rank translation.

    Attributes:
        rank_translate (dict): Mapping of taxonomic ranks to translations and codes.
        ls_metadata (dict): Stores metadata fields like id, name, authors, url.
        ls_children (list): List of children taxa.
        ls_synonyms (list): List of synonyms.
        myTaxa (object): Current taxon object.
        taxonAPI (dict): Taxon data retrieved from the API.
    """
    rank_translate = {
        'order' : ['ordre', 8],
        'family':['famille', 'fam', 10],
        'subfamily':['sous-famille', 'sous-fam', 11],
        'tribu' : ['tribu', 12],
        'subtribu':['sous-tribu', 13],
        'genus':['genre', 'gen', 14],
        'section' : ['section', 16],
        'species':['espece', 'sp', 'spec', 21], 
        'subspecies':[ 'sous-espece', 'subsp', 'subspec', 22],
        'variety':['variete', 'var', 23],
        'forma':['forme', 25],
        'cultivar':['cv', 28],
        'hybrid':['hybride', 'hyb', 31]
     }

    def __init__(self):
        """
        Initialize the abstract API class with empty metadata and taxa lists.
        """
        super().__init__()
        self.ls_metadata = {"id":None,"name": None, "authors":None, "url":None, "webpage":None}
        self.ls_children = []
        self.ls_synonyms = []
        self.myTaxa = None
        self.taxonAPI = None

    def translate_rank(self, _rank):
        """
        Translate a taxonomic rank string to a standard English rank name.

        Args:
            _rank (str): The input rank string (may include accents or abbreviations).
        Returns:
            str: Standardized rank name capitalized, or 'Unknown' if not found.
        """
        try:
            _rank = _rank.replace('.','')
            _rank = _rank.replace('é','e')
            _rank = _rank.replace('è','e')
            _rank = _rank.lower()
        except Exception:
            pass
        for key, value in self.rank_translate.items():
            if _rank in [key]+ value:
                return key.capitalize()
        return 'Unknown'
   
    def _get_responseAPI (self, _url, _timeout=2, _json = True):
        """
        Send a GET request to a URL and return JSON or text response.

        Args:
            _url (str): URL to request.
            _timeout (int, optional): Request timeout in seconds. Default is 2.
            _json (bool, optional): If True, parse response as JSON; else return text. Default True.
        Returns:
            dict or str: Parsed JSON response or raw text, or empty string on failure.
        """
        #_url = self.ls_metadata["url"]
        try:
            _response = requests.get(_url, timeout=_timeout)
            _response.raise_for_status()
            return _response.json() if _json else _response.text
        except Exception:
            return ''
        
    def _get_taxonAPI(self, list_taxa_api, field_name, field_id, filters = None):
        """
        Find and set the taxon data matching `self.myTaxa.simple_taxaname` from a list of taxa.

        Args:
            list_taxa_api (list): List of taxon dicts from API.
            field_name (str): Key name for taxon name field.
            field_id (str): Key name for taxon ID field.
            filters (dict, optional): Additional dictionnary filters to apply to the taxa dicts.
            
        Side Effects:
            Sets `self.taxonAPI` to the matching taxon dict.
            Updates `self.ls_metadata["name"]` and `self.ls_metadata["id"]`.
        """
    #get the true taxa (= self.myTaxa.simple_taxaname) from the list_taxa_api and set the self.taxonAPI, the self.ls_metadata["name"] and the self.ls_metadata["id"]
        self.taxonAPI = {}
        ls_taxa_search = [self.search_taxaname, self.search_taxaname_noprefix]
        try:
            for taxa in list_taxa_api:
                if filters:
                    if not all(taxa.get(k) == v for k, v in filters.items()):
                        continue
                _name = taxa[field_name] #self.search_taxaname.replace("+", " ")

                _searchname = quote_plus(_name).lower()
                if _searchname in ls_taxa_search: #and _name.lower() == self.myTaxa.simple_taxaname.lower():
                    self.taxonAPI = taxa
                    self.ls_metadata["name"] = self.myTaxa.simple_taxaname
                    self.ls_metadata["id"] = self.taxonAPI[field_id] #self._get_list_value (self.taxonAPI, field_id)
                    break
        except Exception: 
            return

    def _get_list_value(self, dictionary, _key):
        """
        Safely get a string value from a dictionary by key.

        Args:
            dictionary (dict): Dictionary to access.
            _key (str): Key to look up.
        Returns:
            str: Stripped string value if key exists; else empty string.
        """
        #return the value of a key in a dict or ''
        try:
            if dictionary[_key]:
                return dictionary[_key]
            else:
                return None
        except Exception:
            return None
    
    #abstract functions for surclassing
    def get_synonyms(self):
        return self.ls_synonyms

    def get_childen (self):
        return self.ls_children

    def get_metadata (self):
        return self.ls_metadata
    
    # #properties, return lists
    @property
    def search_taxaname (self):
        _taxaname = self.myTaxa.simple_taxaname.replace(chr(215), 'x')
        return quote_plus(_taxaname.lower(), safe ='')

    @property
    def search_taxaname_noprefix (self):
        _taxaname = self.search_taxaname
        for prefix in ["+subsp.+", "+var.+", "+f.+", "+x+"]:
            _taxaname = _taxaname.replace(prefix, "+")
        return _taxaname

    # @property
    # def metadata (self):
    #     return self.ls_metadata
    
    # @property
    # def children (self):
    #     return self.ls_children
    
    # @property
    # def url(self):
    #     return self.ls_metadata["url"]
##################################################################################

##################################################################################
##___FLORICAL access class based on API_Abstract, using scrapping of the web page (no API service)________________________
class API_FLORICAL(API_Abstract):
    #dict_rank =  {0 : '', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'subSpecies', 23 : 'Variety', 31 : 'Species'}  
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.taxaname = ''
        self.family = '' 
        self.tab_result = {}
        self.myTaxa = myPNTaxa
        #_taxa = self.myTaxa.taxaname
        _taxaname = quote_plus(self.myTaxa.simple_taxaname)
        # if self.myTaxa.id_rank == 31:
        #     _taxa = _taxa.replace(' x ', ' ' + chr(215) + ' ')

        _url_taxref = f"http://publish.plantnet-project.org/project/florical/search?q={self.search_taxaname}"
        _url_taxref = _url_taxref.replace(' ','%20')
        self.response = self._get_responseAPI(_url_taxref,10, False)
        if len(self.response) == 0:
            return
        self.soup = BeautifulSoup(self.response, 'html.parser')
        ###florical is not consistent with antonyms names (genus_species_authors_subspecies or genus_species_subspecies_authors)
        if 'Florical' in self.soup.title.text:
            if self.myTaxa.taxaname != self.myTaxa.simple_taxaname:
                #_taxa = self.myTaxa.simple_taxaname
                _url_taxref = f"http://publish.plantnet-project.org/project/florical/search?q={_taxaname}"
                _url_taxref = _url_taxref.replace(' ','%20')
                self.response = self._get_responseAPI(_url_taxref,3, False)
                self.soup = BeautifulSoup(self.response, 'html.parser')
               
            if len(self.response) == 0:
                return

        #soup = self.soup
        self.ls_metadata["url"] = _url_taxref
        #title = soup.find("title").text
        if 'Florical' in self.soup.title.text:
        #if 'Florical' in title:
            #in this case, it's a list of taxa or null values
            #must use get_children
            
            return
        else:
            
            _key = self.soup.find_all("td", class_="first")
            _value = self.soup.find_all("td", class_="second")
            
            #get all taxonomic data
            for column, row in zip(_key, _value):
                key = column.find("span", class_="text-info").text
                value = row.text.strip()
                # to suppress in parentheses case as 'Arecaceae Bercht. & J.Presl [= Palmae Juss.] '
                value = re.sub(r"\[.*?\]", "", value)
                value = value.strip()
                self.tab_result[key] = value

            tab_taxa = self.tab_result["Family"].split()
            self.family = tab_taxa[0]
            self.taxaname = self.tab_result["Taxa name"]
            
    def get_metadata(self):
    #return a formated dict with taxonomic data
        tab_taxon = commons.get_dict_from_species(self.taxaname)
        if tab_taxon is None: 
            return

        _rank = tab_taxon["rank"]
        if self.myTaxa.rank_name == _rank:
            self.ls_metadata["family"] = self.family #tab_taxa[0]
            self.ls_metadata["name"] = tab_taxon['name']                
            self.ls_metadata['genus'] = tab_taxon['genus']
            self.ls_metadata['species'] = tab_taxon['species']
            self.ls_metadata['infraspecies'] = self._get_list_value (tab_taxon, "infraspecies") #tab_taxon['infraspecies']
            #self.ls_metadata['rank'] = tab_taxon['rank']
            #self.ls_metadata['basename'] = tab_taxon['basename']
            self.ls_metadata['authors'] = tab_taxon['authors']
            self.ls_metadata["accepted"] = (self.tab_result['Valid'] == '1')
            status = self.tab_result['Statut'].strip()
            try:
                status = status.split()[0]
            except Exception:
                status =''
            self.ls_metadata["status"] = status
            #self.ls_metadata["habitat"] = self.tab_result['Habitat']

            #add synonyms
            _id = self.tab_result["id_taxon"]
            self.ls_metadata["id"] = _id
            self.ls_metadata["webpage"] = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/' + str(_id)
            # t_synonyms = self.get_synonyms()
            # if t_synonyms is not None:
            #     self.ls_metadata["synonyms"] = t_synonyms
        
        return self.ls_metadata
            # _links = {}
            # _links ["Florical"] = "http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/" + _url_florical
            # self.ls_metadata["_links"] = _links

    def get_synonyms(self):
    #return the synonyms
        synonyms = self.soup.find("div", id="collapse5cf7bc681d027852d1a7cf36")
        tab_synonyms = set()
        if synonyms is not None:
            synonyms = synonyms.find_all("tr")
            i = 0
            for synonym in synonyms:
                if i > 0:
                    _syno = synonym.text.strip().split('\n')[0]
                    tab_synonyms.add(_syno)
                i += 1
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

    def get_children(self):
    #get all children from the current taxon
        #url = 'http://publish.plantnet-project.org/project/florical/search?q=' + self.myTaxa.taxaname
        _page = 1
        try:
            response = self.response #requests.get(url)
            soup = self.soup
        except Exception:
            return
        url = self.ls_metadata["url"]
        tab_urllinks = []
        
        while response:
            if 'Not Found' in soup.title.text:
                break

            if 'Florical' not in soup.title.text:
                #if only one taxon, florical switch to the taxa page (not a list of links)
                tab_taxon = commons.get_dict_from_species(self.taxaname)
                if tab_taxon is None: 
                    continue
                tab_taxon["family"] = self.family
                tab_urllinks.append(tab_taxon)
            else:
                #else decompose the list of links to get all taxa properties
                hrefs = soup.find("div", class_="span12")
                hrefs = hrefs.find_all("a")
                for href in hrefs:
                    if 'collection' in href["href"]:
                        txt = href.text.replace('\n', ' ').strip()
                        txt_ls = [i.strip() for i in txt.split('-')]
                        #tab_taxon = self._get_taxon_dictionnary (tab_result['taxaname'])
                        tab_taxon = commons.get_dict_from_species(txt_ls[2])
                        if tab_taxon is None: 
                            continue
                        #families are associated with authors, so qe split the name
                        tab_taxa = txt_ls[1].split()
                        tab_taxon["family"] = tab_taxa[0]
                        _valid = not (self.myTaxa.id_rank == 14 and tab_taxon['genus'] != self.myTaxa.taxaname)
                        if _valid:
                            
                            tab_urllinks.append(tab_taxon)
            _page += 1
            #response = self._get_responseAPI(url +'&page=' +str(_page), False)
            response = requests.get(url +'&page=' +str(_page), timeout=3).text
            soup = BeautifulSoup(response, 'html.parser')

        #works with the tab_urllinks to create a hierarchical list of taxa from families to infraspecies
        self.ls_children = []
        #tab to produce _child = {"id" : '', "taxaname" : '', "authors" : '', "rank" : '', "idparent" : ''}
        i = 1
        #n_genus = 0
        for taxon in tab_urllinks:
            if self._get_id_taxa(self.ls_children, taxon['family']) is None:
                #add if the family do not already exists
                _child = {"id" : str(i+1), "taxaname" : taxon['family'], "authors" : '', "rank" : 'Family', "idparent" : str(i)}
                self.ls_children.append(_child)
                i +=2
            if self._get_id_taxa(self.ls_children, taxon['genus']) is None:
                 #add if the genus do not already exists and set the family id into idparent
                _idparent = self._get_id_taxa(self.ls_children, taxon['family'])
                _child = {"id" : str(i), "taxaname" : taxon['genus'], "authors" : '', "rank" : 'Genus', "idparent" : _idparent}
                self.ls_children.append(_child)
                #n_genus += 1
                i +=1
                
            if taxon['rank'] == 'Hybrid':
                _species = ' '.join([taxon['genus'], taxon['prefix'], taxon['species']])
            else:
                _species = ' '.join([taxon['genus'], taxon['species']])

            if self._get_id_taxa(self.ls_children, _species) is None:
                 #add if the species do not already exists and set the genus id into idparent
                _idparent = self._get_id_taxa(self.ls_children, taxon['genus'])
                _child = {"id" : str(i), "taxaname" : _species, "authors" : taxon['authors'], "rank" : taxon['rank'], "idparent" : _idparent}
                self.ls_children.append(_child)
                i +=1
            _infraspecies = taxon['infraspecies']
            if len(_infraspecies) >0:
                if self._get_id_taxa(self.ls_children, taxon['name']) is None:
                     #add if the infraspecific do not already exists and set the species id into idparent
                    _idparent = self._get_id_taxa(self.ls_children, _species)
                    #_taxa = ' '.join ([taxon['genus'],taxon['species'], taxon['species'], taxon['species']])
                    _child = {"id" : str(i), "taxaname" : taxon['name'], "authors" : taxon['authors'], "rank" : taxon['rank'], "idparent" : _idparent}
                    self.ls_children.append(_child)
                    i +=1
        return self.ls_children

    def _get_id_taxa(self, tab, key):
        for taxa in tab:
            if taxa['taxaname'] == key:
                return str(taxa['id'])

##___ENDEMIA access class based on API_Abstract________________________
class API_ENDEMIA(API_Abstract):
        
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _url_taxref = f"https://api.endemia.nc/v1/taxons?q={self.search_taxaname_noprefix}&section=flore&includes=synonyms"
        self.ls_metadata["url"] =_url_taxref
        #get the response
        self.todos = self._get_responseAPI (_url_taxref, 2)
        #load the self.taxonAPI
        try:
            self.api_result = self._get_responseAPI (_url_taxref, 2)["data"]
            self._get_taxonAPI(self.api_result, "full_name", "id")
        except Exception:
            return
        
    def get_metadata(self):
        #get metadata from Endemia
        if not self.taxonAPI:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://endemia.nc/flore/fiche{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] = self._get_list_value (self.taxonAPI, "auteur")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self._get_list_value (self.taxonAPI, "rank"))
        # except Exception: 
        #     pass
        
        
        #if self.taxonAPI["endemique"]:
        self.ls_metadata["endemic"] = self._get_list_value (self.taxonAPI, "endemique")
        self.ls_metadata["redlist_iucn"] = self._get_list_value (self.taxonAPI, "categorie_uicn")
        self.ls_metadata["protected"] = self._get_list_value (self.taxonAPI, "protected")
        #get details on protected status, nomenclature, habitat and images(= a 2nd query !)

        # _url_taxref = f"https://api.endemia.nc/v1/taxons/flore/{self.ls_metadata["id"]}"
        # try:
        #     _todos = self._get_responseAPI (_url_taxref, 2)
        #     _tab_attributes = _todos["data"]["attributes"]
        #     self.ls_metadata["published"] = (self._get_list_value (_tab_attributes, "status") == "Published")
        #     self.ls_metadata["habitat"] = self._get_list_value (_tab_attributes, "typehabitat")
        # except Exception:
        #     pass
        return self.ls_metadata

    def get_synonyms(self):
    #get the synonomys from the self.taxonAPI
        if not self.taxonAPI:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try:
            result_API = self.taxonAPI["synonyms"]
        except Exception: 
            return
        for taxa in result_API:
            _name = self._get_list_value (taxa, "full_name")
            _name = _name.strip()
            _author = self._get_list_value (taxa, "auteur")
            _author = _author.strip()
            if _author:
                _name = _name + ' ' + _author
            if len(_name) > 0:
                tab_synonyms.add(_name.strip())
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

    def get_children(self):
        #get list of children
        table_result = []
        table_valid = []
        for taxa in self.api_result:
            _rank = self._get_list_value(taxa,"rank")
            _name = self._get_list_value(taxa,"full_name")
            _rank = self.translate_rank(taxa["rank"])

            #do not accept taxa if no name or no rank
            if len(_rank)*len(_name)==0:
                continue
            #affect value
            taxa["rank"]=_rank
            taxa["full_name"]=_name
            taxa["idparent"]= 0
            tb_taxa = _name.split()
            #get the parent name
            _parent =''
            if _rank in ['Subspecies', 'Variety']:
                _parent = ' '.join(tb_taxa[0:2])
            else:
                _parent = tb_taxa[0]
            #get the parent id
            for taxa2 in self.api_result:
                if taxa2["full_name"] == _parent:
                    taxa["idparent"] = taxa2["id"]            
            #set the input taxa as the first taxa in the resulting list (table_result)
            if self.ls_metadata["id"] == taxa["id"]:
                taxa["idparent"]=-1
                table_result.append(taxa)
            #add the valid tab to the final selection
            table_valid.append(taxa)
        #finally append only when taxa["idparent"] > 0
        for taxa in table_valid:
            if taxa["idparent"] * taxa["id"]> 0:
                table_result.append(taxa)
        #create and return the tab_children 
        self.ls_children = []
        for taxa in table_result:
            _child =  {"id" : taxa["id"], "taxaname" : taxa["full_name"], "authors" : taxa["auteur"], "rank" : taxa["rank"], "idparent" : taxa["idparent"]}
            self.ls_children.append(_child)
        return self.ls_children

##___TAXREF access class based on API_Abstract________________________
class API_TAXREF(API_Abstract):

    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        # #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        dict_rank =  {0 : '',8 :'OR', 10 : 'FM', 11 : 'SBFM', 12 : 'TR', 13 : 'SBTR', 14 : 'GN', 21 : 'ES', 22 : 'SSES', 23 : 'VAR'} 
        try :
            _rank = dict_rank[self.myTaxa.id_rank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = f"&taxonomicRanks={_rank}"
        #set the url to get the taxa from TaxRef
        _url_taxref = f"https://taxref.mnhn.fr/api/taxa/search?scientificNames={self.search_taxaname}{_rank}&domain=continental&page=1&size=5000" #+ self.myTaxa.simple_taxaname + _rank +"&domain=continental&page=1&size=5000"
        # _url_taxref = _url_taxref.replace(' ','%20')
        #_url_taxref = f"https://taxref.mnhn.fr/api/taxa/fuzzyMatch?term={self.search_taxaname_noprefix}"
        self.ls_metadata["url"] =_url_taxref
        #get the response
        _todos = self._get_responseAPI (_url_taxref, 3)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI(_todos["_embedded"]["taxa"], "scientificName", "id", {"kingdomName": "Plantae"})
        except Exception:
            return

    def get_metadata(self):
        #get metadata from TaxRef (surclassing)
        if not self.taxonAPI:
            return
        
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://inpn.mnhn.fr/espece/cd_nom/{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] =''
        # try:      
        #     self.ls_metadata["rank"] = self.translate_rank(self._get_list_value (self.taxonAPI, "rankName"))
        # except Exception: 
        #     pass

        self.ls_metadata["family"] = self._get_list_value (self.taxonAPI, "familyName")
        self.ls_metadata["accepted"] = self.taxonAPI["referenceId"] == self.ls_metadata["id"]
        #get authors names and year of publication
        try:
            _authority = self._get_list_value (self.taxonAPI, "authority").split(",")
            self.ls_metadata["authors"] = _authority[0]
            self.ls_metadata["year"] = _authority[1]
            if len(self.ls_metadata["year"]) > 0:
                self.ls_metadata["nomenclature"] ="Published"
        except Exception: 
            pass
        return self.ls_metadata
       
    def get_children(self):
        if not self.taxonAPI:
            return
        self.ls_children = []
        result_API = []
        _child = {}
        try:
            _url_taxref = f"https://taxref.mnhn.fr/api/taxa/{self.ls_metadata['id']}/children" #+str(self.id) + ""
            #print (_url_taxref)
            _todos = self._get_responseAPI (_url_taxref, 7)            
            result_API.append(self.taxonAPI) #add the input taxa
            result_API += _todos["_embedded"]["taxa"] #get the children
        except Exception: 
            return
        #set the children in a list of dictionnary
        for taxa in result_API:
            _child =  {"id" : '', "taxaname" : '', "authors" : '', "rank" : 'Unknown', "idparent" : ''} 
            _child["id"] = self._get_list_value(taxa, "id")
            _child["idparent"] = self._get_list_value(taxa,"parentId")
            _child["taxaname"] = self._get_list_value(taxa,"scientificName")
            try:
                _authority = self._get_list_value(taxa,"authority").split(",")
                _child["authors"] = _authority[0]
            except Exception: 
                pass
            try:
                _child["rank"] = self.translate_rank(self._get_list_value(taxa,"rankName"))
            except Exception:  
                pass
            self.ls_children.append(_child)
        return self.ls_children

    def get_synonyms(self):
    #get list of synonyms
        if not self.taxonAPI:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try: 
            #need a new API query to get the synonyms   
            _url_taxref = f"https://taxref.mnhn.fr/api/taxa/{self.ls_metadata['id']}/synonyms" # + str(self.id) +""
            _todos = self._get_responseAPI (_url_taxref, 2)
            result_API = _todos["_embedded"]["taxa"]
        except Exception: 
            return
        for taxa in result_API:
            #get the name and the authors
            _name = self._get_list_value(taxa,"scientificName")
            try:
                _authority = self._get_list_value(taxa,"authority").split(",") #split to extract the authors from the date
                _authors = _authority[0].strip()
            except Exception:
                _authors = ''
            if len(_authors) > 0:
                _name = _name + ' ' + _authors
            if len(_name) > 0:
                tab_synonyms.add(_name)
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

##___IPNI access class based on API_Abstract________________________
class API_IPNI(API_Abstract):
    
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _rank = ''
        _taxa = self.myTaxa.simple_taxaname        
        if self.myTaxa.id_rank == 10:
            _rank = "f_familial"
        elif self.myTaxa.id_rank == 14:
            _rank = "f_generic" 
        elif self.myTaxa.id_rank == 21:
            _rank = "f_species"
        elif self.myTaxa.id_rank == 31:
            _rank = "f_species"
            _taxa = _taxa.replace (' x ',' ')
        #_taxaname = quote_plus(_taxa)

        _url_taxref =f"http://beta.ipni.org/api/1/search?perPage=100&cursor=%2A&q={self.search_taxaname_noprefix}&f={_rank}"
        #_url_taxref =f"http://beta.ipni.org/api/1/search?perPage=1&q={self.search_taxaname}&f={_rank}"
        # _url_taxref =f"http://beta.ipni.org/api/1/search?perPage=1&q={self.search_taxaname}"
        # _url_taxref = _url_taxref.replace(' ','+')
        self.ls_metadata["url"] =_url_taxref
        #get the response
        _todos = self._get_responseAPI (_url_taxref,2)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI(_todos["results"], "name", "fqId")
        except Exception:
            return

    def get_metadata(self):
        #get metadata from IPNI
        if not self.taxonAPI:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] =f"https://www.ipni.org/n/{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] = self._get_list_value (self.taxonAPI, "authors")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self._get_list_value (self.taxonAPI, "rank"))
        # except Exception: 
        #     pass
        
        self.ls_metadata["family"] = self._get_list_value (self.taxonAPI, "family")          
        self.ls_metadata["publication"] = self._get_list_value (self.taxonAPI, "reference")

        #get the year of publication
        _year = self._get_list_value (self.taxonAPI, "publicationYear")
        if _year is None:
            _year = self._get_list_value (self.taxonAPI, "publicationYearNote")
        #set the year if exists
        if _year:
            self.ls_metadata["year"] = _year
        #set published tag if year is not empty
        # if len(self.ls_metadata["year"]) >0:
        #     self.ls_metadata["nomenclature"] ="Published"
        return self.ls_metadata

##___POWO access class based on API_Abstract________________________
class API_POWO(API_Abstract):
    
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _rank = ''
        #result_API = []
        if self.myTaxa.id_rank == 10:
            _rank = "families_f" #"&f=f_familial"
        elif self.myTaxa.id_rank == 14:
            _rank = "genus_f"  #"&f=f_genus" 
        elif self.myTaxa.id_rank == 21:
            _rank = "species_f" #"&f=f_species"
        #_taxaname = quote_plus(self.myTaxa.simple_taxaname)
        _url_taxref =f"https://powo.science.kew.org/api/2/search?perPage=500&cursor=%2A&q={self.search_taxaname}&f={_rank}" 
        #_url_taxref = _url_taxref.replace(' ','+')
        self.ls_metadata["url"] =_url_taxref
        #get the response
        _todos = self._get_responseAPI (_url_taxref,2)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI(_todos["results"], "name", "fqId")
        except Exception:
            return
        
    def get_metadata(self):       
        #get the metadata from POWO
        if not self.taxonAPI:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = 'https://powo.science.kew.org' + self._get_list_value (self.taxonAPI, "url")
        self.ls_metadata["family"] = self._get_list_value (self.taxonAPI, "family")    
        self.ls_metadata["authors"] = self._get_list_value (self.taxonAPI, "author")
        #self.ls_metadata["rank"] = self.translate_rank(self._get_list_value (self.taxonAPI, "rank"))
        self.ls_metadata["accepted"] = self.taxonAPI["accepted"]
        return self.ls_metadata
        
        
    def get_synonyms(self):
    ##get the synonomys from the self.id
        if not self.taxonAPI:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try: 
            #need a new API query to get the synonyms   
            _url_taxref = f"https://powo.science.kew.org/api/2/taxon/{self.ls_metadata["id"]}"
            _todos = self._get_responseAPI (_url_taxref, 5)
            result_API = _todos["synonyms"]
        except Exception: 
            return
        for taxa in result_API:
            #get the name and the authors
            _name = self._get_list_value(taxa,"name")
            _authors = self._get_list_value(taxa,"author")
            if len(_authors) > 0:
                _name = _name + ' ' + _authors
            if len(_name) > 0:
                tab_synonyms.add(_name)
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

    def get_children(self):
        if not self.taxonAPI:
            return
        def search_child_taxref(idparent):
        #recursive - get the children list from an input idparent
            tab_result = []
            for taxa in table_taxa:
                if taxa["idparent"] == idparent:
                    tab_result.append(taxa)
                    tab_result += search_child_taxref(taxa["index"])
            return tab_result
#-------------------------
    #get list of children

        table_taxa=[]
        _idrank = self.myTaxa.id_rank
        _taxa = self.myTaxa.simple_taxaname
        #search at the genus level if a species
        if _idrank >= 21:
            _idrank = 14
            _taxa = self.myTaxa.simple_taxaname.split()[0]
        #translate rank
        try:
            _rank = self.translate_rank(_idrank)
            _rank.lower()
        except Exception:
            return
        _url_taxref =f"https://powo.science.kew.org/api/2/search?perPage=5000&cursor=%2A&q=&{_rank}={_taxa}&f=accepted_names"
        #_url_taxref = _url_taxref.replace(' ','%20')
        #increase the timeout to 20 seconds to allow big queries (up to 5000 names)
        _todos = self._get_responseAPI (_url_taxref, 20)
        #try to get result JSON

        table_taxref = {'fqId': self.taxonAPI['fqId'], 'name': self.taxonAPI['name'], 'author': self.taxonAPI['author'], 'rank': self.taxonAPI['rank']}
        table_taxref = [table_taxref]
        try:
            table_taxref = _todos["results"]
        except Exception:
            return

        #Create the _table_data with an empiric id and a index of the dictionary to speed search        
        _table_data=[]
        index = 1
        idroot = 0
        _index_taxa_id = {}
        #_index_taxa_id = {tax["name"]: tax["id"] for tax in table_taxref}
        for taxa in table_taxref:
            _name = self._get_list_value(taxa,"name")
            taxa["index"] = index
            _index_taxa_id[_name] = index
            index += 1
        #search for parent
        for taxa in table_taxref:
            _rank = self._get_list_value(taxa,"rank").lower()
            _name = self._get_list_value(taxa,"name")
            _id = self._get_list_value(taxa,"fqId")
            if len(_rank)==0:
                continue
            taxa["idparent"]=0
            #get the parent name by spliting the taxaname            
            tb_taxa = _name.split()
            _parent =''
            if _rank in ['subspecies', 'variety']:
                _parent = ' '.join(tb_taxa[0:2])
            elif _rank =='genus':
                _parent = self._get_list_value(taxa,"family")
            else:
                _parent = tb_taxa[0]
            #get the parent id within the table itself (use _index_taxa_id)
            try:
                taxa["idparent"] = _index_taxa_id[_parent]
            except Exception:
                pass
            #set the idroot and set the idparent = -1
            if _id == self.ls_metadata["id"]:
                taxa["idparent"]=-1
                idroot = taxa["index"]
                _table_data.append(taxa)
            table_taxa.append(taxa)

        #no result for the root
        if idroot==0: 
            return
        #finally kept get only childs of the root [index=idroot]
        _table_data += search_child_taxref(idroot)
        self.ls_children =[]
        for taxa in _table_data:
            _author = self._get_list_value(taxa,"author")
            _rank = self._get_list_value(taxa,"rank")
            _rank = self.translate_rank(_rank)
            _name = self._get_list_value(taxa,"name")
            _child =  {"id" : taxa["index"], "taxaname" : _name, "authors" : _author, "rank" : _rank, "idparent" : taxa["idparent"]}
            self.ls_children.append(_child)
            #print (_child)
        return self.ls_children


class API_GBIF(API_Abstract):
#API for retrievin data from GBIF
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _url_taxref = f"https://api.gbif.org/v1/species/match?name={self.search_taxaname_noprefix}"
        self.ls_metadata["url"] =_url_taxref
        _todos = self._get_responseAPI (_url_taxref,2)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI([_todos], "canonicalName", "usageKey")
        except Exception:
            return
    
    def get_metadata(self):
    #get metadata from GBIF
        if not self.taxonAPI:
            return
        self.ls_metadata["webpage"] = f"https://www.gbif.org/species/{self.ls_metadata["id"]}"
        _scientificname = self._get_list_value (self.taxonAPI, "scientificName")
        if len(_scientificname) > 0:
            self.ls_metadata["authors"] = _scientificname.replace(self.ls_metadata["name"], "").strip()
        #self.ls_metadata["rank"] = self._get_list_value (self.taxonAPI, "rank").title()
        self.ls_metadata["class"] = self._get_list_value (self.taxonAPI, "class")
        self.ls_metadata["order"] = self._get_list_value (self.taxonAPI, "order")
        self.ls_metadata["family"] = self._get_list_value (self.taxonAPI, "family")
        self.ls_metadata["accepted"] = self._get_list_value (self.taxonAPI, "status") == 'ACCEPTED'
        return self.ls_metadata
    

class API_INATURALIST(API_Abstract):
#API for retrievin data from Inaturalist
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _url_taxref = f"https://api.inaturalist.org/v1/taxa?q={self.search_taxaname_noprefix}"
        self.ls_metadata["url"] =_url_taxref
        _todos = self._get_responseAPI (_url_taxref,2)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI(_todos["results"], "matched_term", "id")
        except Exception:
            return
    
    def get_metadata(self):
    #get metadata from inaturalist
        if not self.taxonAPI:
            return
        self.ls_metadata["webpage"] = f"https://www.inaturalist.org/observations?taxon_id={self.ls_metadata["id"]}"
        #self.ls_metadata["rank"] = self._get_list_value (self.taxonAPI, "rank").title()
        #self.ls_metadata["extinct"] = self._get_list_value (self.taxonAPI, "extinct")
        self.ls_metadata["occurrences"] = self._get_list_value (self.taxonAPI, "observations_count")
        if "conservation_status" in self.taxonAPI:
            self.ls_metadata["redlist_iucn"] = self._get_list_value (self.taxonAPI["conservation_status"], "status").upper()
        return self.ls_metadata



##___TROPICOS access class based on API_Abstract________________________        
class API_TROPICOS(API_Abstract):
    key_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _url_taxref =f"http://services.tropicos.org/Name/Search?name={self.search_taxaname_noprefix}&type=wildcard&apikey={self.key_tropicos}&format=json"
        self.ls_metadata["url"] =_url_taxref
        #get the response
        _todos = self._get_responseAPI (_url_taxref,2)
        #set the self.taxonAPI
        try:
            self._get_taxonAPI(_todos, "ScientificName", "NameId")
        except Exception:
            return

    def get_metadata(self):
    #get metadata from Tropicos
        if not self.taxonAPI:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://www.tropicos.org/name/{self.ls_metadata["id"]}"        
        self.ls_metadata["authors"] = self._get_list_value (self.taxonAPI, "Author")
        self.ls_metadata["family"] = self._get_list_value (self.taxonAPI, "Family")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self._get_list_value (self.taxonAPI, "RankAbbreviation"))
        # except Exception:
        #     pass
        _valid = self._get_list_value (self.taxonAPI, "NomenclatureStatusName")
        #self.ls_metadata["accepted"] = (_valid =='Legitimate')
        if _valid =='Legitimate':
            self.ls_metadata["accepted"] = True
        elif _valid in ('Illegitimate','Invalid'):
            self.ls_metadata["accepted"] = False

        _publication = self._get_list_value (self.taxonAPI, "DisplayReference")
        if _publication:
            self.ls_metadata["publication"] = _publication

        _year = self._get_list_value (self.taxonAPI, "DisplayDate")
        if _year:
            self.ls_metadata["year"] = _year
            #self.ls_metadata["nomenclature"] ="Published"
        #self.ls_metadata["publication"] = self._get_list_value (self.taxonAPI, "DisplayReference")
        # self.ls_metadata["nomenclature"] ="Unpublished"
        # if len(self.ls_metadata["year"]) > 0:
        #     self.ls_metadata["nomenclature"] ="Published"
        return self.ls_metadata
        
    def get_synonyms(self):
    #get list of synonyms
        if not self.taxonAPI:
            return
        tab_synonyms = set()
        try:
            _url_taxref =f"http://services.tropicos.org/Name/{self.ls_metadata["id"]}/Synonyms?apikey={self.key_tropicos}&format=json"
            #print (_url_taxref)
            result_API = self._get_responseAPI (_url_taxref,2)
        except Exception: 
            return
        #get dictionnary 
        for taxa in result_API:
            if taxa.get('SynonymName', None):
                _synonym = taxa['SynonymName']
                _name = self._get_list_value (_synonym, "ScientificNameWithAuthors")
                tab_synonyms.add(_name)
            self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms


 ###-TESTS-##################





def test_signal(base,api_json):
    
    #f metadata_worker.status==0: return
    if base == "END":
        try :
            #complete Json
            print (api_json)
        finally:
            raise SystemExit
    else:
        #partial json, for any base
        print(base, api_json)


if __name__ == '__main__':
    # import models.taxa_model as taxa_model
    app=QtWidgets.QApplication(sys.argv)
    # #class_taxa = PNTaxa(123,'Zygogynum pancheri subsp. rivulare', 'DC.', 22)
    # class_taxa = taxa_model.PNTaxa(123,'Zygogynum bicolor', 'DC.', 21)
    # metadata_worker = API_Thread (app, class_taxa,"FLORICAL")
    # metadata_worker.Result_Signal.connect(test_signal)
    

    # #metadata_worker.set_taxaname("Miconia calvescens")
    # metadata_worker.PNTaxa_model = class_taxa
    # metadata_worker.start()
    #  #metadata_worker.kill()
    #     #window.identity_tableView.r22
    
    app.exec_()
    sys.exit(app.exec_())

