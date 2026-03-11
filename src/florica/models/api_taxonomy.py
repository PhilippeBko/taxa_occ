import requests
from urllib.parse import quote_plus
import time
from dataclasses import dataclass
from bs4 import BeautifulSoup
import re
""" 


#exemple how to use api_taxonomy
1) #initialize the class
    api_Taxonomy = API_Taxonomy()
2) get the dictionnary of available API
    api_Taxonomy.api_classes
3) send a request to get a class from an API (ex: Tropicos)
    result = api_Taxonomy.get_APIclass("TROPICOS", "Miconia calvescens", "species", _key_tropicos)
4) if result is not None, the API object is available for several properties as
        #print (result.API_url)             #the url requested
        #print (result.API_error)           #a textual error message resulting from the search on url api (timeout, err404, no found taxon,...), None if no error
        #print (result.API_result)          #raw result from API (a dictionnary of taxa, each taxa is a dictionnary from API
        #print (result.API_taxon)           #the valid taxon extract frol API_result, one taxon among several taxa
        #print (result.get_metadata())      #a dictionnary of metadata (standardized) data from result.API_taxon composed of commons keys ("id", "name", "authors", "url", "webpage", "query_time") + additional keys depending on the API
        #print (result.get_synonyms())      #a list of synonyms (taxon + authors) from result.API_taxon
        #print (result.get_children())      #a list of dictionnary for any children (standardized) data from result.API_taxon composed of by standardized keys {"id", "taxaname", "authors", "rank", "id_parent"}
 """



#dictionnary to translate rank name to rank id (allow  comparaison into the hierarchy)
dict_idrank = {
    'order' : 8,
    'family': 10,
    'subfamily': 11,
    'tribu' : 12,
    'subtribu': 13,
    'genus': 14,
    'section' : 16,
    'species': 21, 
    'subspecies': 22,
    'variety': 23,
    'forma': 25,
    'cultivar': 28,
    'hybrid': 31
    }

#internal dataclass to transfer name and id_rank between API classes
@dataclass
class TaxonData:
    name: str
    idrank: int
    apikey: str = None

#general class to query a biodiversity API
class API_Taxonomy():
    """ class to query multiple biodiversity APIs """
    def __init__(self):
        self._taxonData = None
        self._api_class = None
        self.api_classes = {
            "POWO": {"class": API_POWO, "children":10, "search": 10},
            "IPNI": {"class": API_IPNI, "search": 10},
            "TAXREF": {"class": API_TAXREF, "children":8, "search": 8},
            "TROPICOS": {"class": API_TROPICOS, "children":14},
            "ENDEMIA": {"class": API_ENDEMIA, "children":14, "search": 10},
            "FLORICAL":{"class":  API_FLORICAL, "children":10, "search": 14},
            "INATURALIST": {"class": API_INATURALIST},
            "GBIF": {"class": API_GBIF},
        }
 
    def get_APIclass(self, api_name, name, rank,  api_key = None):
#   return the API class from the api_name (str = "POWO","IPNI"..)if the taxon name (str) is found
        #search for a taxon in the api
        api_class = self.api_classes.get(api_name, None)
        if api_class:
            api_class = api_class.get ("class", None)
            _idrank = dict_idrank.get(rank.lower(), 0)
            self._taxonData = TaxonData(name = name, idrank = _idrank, apikey = api_key)
            self._api_class = api_class(self._taxonData)
            return self._api_class
        return


##___class API_Abstract________________________
class API_Abstract ():
    """
    Abstract base class for biodiversity API wrappers.

    Provides common methods and attributes for querying taxa metadata,
    synonyms, and children, as well as utilities for rank translation.

    Attributes:
        ls_metadata (dict): Stores metadata fields like id, name, authors, url.
        ls_children (list): List of children taxa.
        ls_synonyms (list): List of synonyms.
        myTaxa (object): Current taxon object.
        self.API_taxon (dict): Taxon data retrieved from the API_result.
        self.API_result (dict): List of Taxon data retrieved from the API.
        self.API_error (str): the last error from the API.
    """

    def __init__(self, myTaxonData):
        """
        Initialize the abstract API class with empty metadata and taxa lists.
        """
        super().__init__()
        self.myTaxa = myTaxonData
        self.ls_metadata = {"id":None,"name": None, "authors":None, "url":None, "webpage":None, "query time":None}
        self.ls_children = []
        self.ls_synonyms = []
        self.API_error = None
        self.API_result = None  #set in get_taxon_fromURL, it's the raw resulting json request from url
        self.API_taxon = None    #set in get_taxon_from_API_Result, it's the validated API taxon dict, set from self.API_result

    def translate_rank(self, _rank):
        """
        Translate a taxonomic rank string or integer to a standard English rank name.
        Args:
            _rank (str): The input rank string (may include accents or abbreviations).
        Returns:
            str: Standardized rank name capitalized, or 'Unknown' if not found.
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
        try:
            _rank = _rank.replace('.','')
            _rank = _rank.replace('é','e')
            _rank = _rank.replace('è','e')
            _rank = _rank.lower()
        except Exception:
            pass
        for key, value in rank_translate.items():
            if _rank in [key]+ value:
                return key.capitalize()
        return 'Unknown'
   
    def get_responseAPI (self, _url, _timeout=5, _json = True):
        """
        Send a GET request to a URL and return JSON or text response.

        Args:
            _url (str): URL to request.
            _timeout (int, optional): Request timeout in seconds. Default is 5.
            _json (bool, optional): If True, parse response as JSON; else return text. Default True.
        Returns:
            dict or str: Parsed JSON response or raw text, or empty string on failure.
        """
        try:
            headers = {
                "User-Agent": "TaxaOcc/0.01 (+https://github.com/PhilippeBko/taxa_occ)"
            }
            
            _response = requests.get(_url, headers=headers, timeout=_timeout)
            _response.raise_for_status()
            return _response.json() if _json else _response.text
        except Exception:
            self.API_error = "Connection error - no response from API"
            return None
    
    def get_taxon_fromURL(self, url, list_items, field_name, field_id, filters = None):
        """
        Get the response from a URL and set the self.API_result.
        list_items = key(s) to search in _api_result (ex: ["results", "data"], search for dict ["results"]["data"])
        Args:
            url (str): URL to request.
            list_items (list): List of key(s) to search in _api_result
            field_name (str): Field name to search in self.API_result
            field_id (str): Field id to search in self.API_result
            filters (dict, optional): Filters to apply when searching the self.API_result
        """
        _api_result = self.get_responseAPI (url)
        self.ls_metadata["url"] = url
        if _api_result is None:
            return
        #load the self.API_result
        self.API_result = _api_result
        try:
            if list_items:
                for _items in list_items:
                    self.API_result = self.API_result[_items]
        except Exception:
            self.API_result = None
        #load the self.API_taxon
        self.get_taxon_from_API_Result(field_name, field_id, filters)

    def get_taxon_from_API_Result(self, field_name, field_id, filters = None):
        """
        Set the self.API_Taxon
        Find and set the taxon data matching `self.taxaname` from self.API_result.

        Args:
            field_name (str): Key name for taxon name field.
            field_id (str): Key name for taxon ID field.
            filters (dict, optional): Additional dictionnary filters to apply to the taxa dicts.
            
        Side Effects:
            Sets `self.API_taxon` to the matching taxon dict.
            Updates `self.ls_metadata["name"]` and `self.ls_metadata["id"]`.
        """
    #get the true taxa (= self.taxaname) from the list_taxa_api and set the self.API_taxon, the self.ls_metadata["name"] and the self.ls_metadata["id"]
        self.API_error = None
        self.API_taxon = {}

        #error handling to log_request
        if self.API_result is None:
            self.API_error = f"{self.taxaname} not found"
            return
        #check and force self.API_result to be a list
        if not isinstance(self.API_result, list):
            self.API_result = [self.API_result]

        #list_taxa_api = self.API_result
        ls_taxa_search = [self.search_taxaname, self.search_taxaname_noprefix]
        try:
            for taxa in self.API_result:
                #apply filters if exists
                if filters:
                    if not all(taxa.get(k) == v for k, v in filters.items()):
                        continue
                _name = taxa[field_name]
                _searchname = quote_plus(_name).lower()
                if _searchname in ls_taxa_search:
                    self.API_taxon = taxa
                    self.ls_metadata["name"] = self.taxaname
                    self.ls_metadata["id"] = self.API_taxon[field_id]
        except Exception:
            pass
        self.ls_metadata["query time"] =  time.strftime("%Y-%m-%d %H:%M:%S")
        if not self.API_taxon:
            self.API_error = f"{self.taxaname} is not found"

    def get_dict_value(self, dictionary, key):
        """
        Safely get a string value from a dictionary by key.

        Args:
            dictionary (dict): Dictionary to access.
            _key (str): Key to look up.
        Returns:
            str: Stripped string value if key exists; else None.
        """
        #return the value of a key in a dict or None
        try:
            if dictionary[key]:
                return dictionary[key]
            else:
                return None
        except Exception:
            return None
   
   
    #abstract functions for surclassing
    def get_metadata (self):
        return self.ls_metadata   
    
    def get_synonyms(self):
        return self.ls_synonyms

    def get_children (self):
        return self.ls_children
    
     # #properties, return values
    @property
    def API_url (self): 
        return self.ls_metadata["url"]
    @property
    def idrank (self):
        return self.myTaxa.idrank

    @property
    def taxaname (self):
        _taxaname = self.myTaxa.name.replace(chr(215), 'x')
        return _taxaname.strip()

    @property
    def search_taxaname (self):
        return quote_plus(self.taxaname.lower(), safe ='')

    @property
    def search_taxaname_noprefix (self):
        _taxaname = self.search_taxaname
        for prefix in ["+subsp.+", "+var.+", "+f.+", "+x+"]:
            _taxaname = _taxaname.replace(prefix, "+")
        return _taxaname

##################################################################################

##################################################################################
##___FLORICAL access class based on API_Abstract, using scrapping of the web page (no API service)________________________
class API_FLORICAL(API_Abstract):
    #dict_rank =  {0 : '', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'subSpecies', 23 : 'Variety', 31 : 'Species'}  
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        self.API_taxon = {}
        self.soup = None

        #get the response from the server
        _url_taxref = f"http://publish.plantnet-project.org/project/florical/search?q={self.search_taxaname}"
        self.ls_metadata["url"] = _url_taxref
        self.response = self.get_responseAPI(_url_taxref,10, False)
        if self.response is None:
            return
        #get the soup
        self.soup = BeautifulSoup(self.response, 'html.parser')
        if 'Florical' in self.soup.title.text:
            return
        else:            
            _key = self.soup.find_all("td", class_="first")
            _value = self.soup.find_all("td", class_="second")
            
            #get all taxonomic data
            for column, row in zip(_key, _value):
                key = column.find("span", class_="text-info").text
                value = row.text.strip()
                #get standardized keys
                if key == "Taxa name":
                    key = "original_name"
                elif key == "ui_taxon":
                    key = "rank"
                elif key == "id_taxon":
                    key = "id"
                else:
                    key = key.lower().replace(' ', '_')
                # to suppress in parentheses case as 'Arecaceae Bercht. & J.Presl [= Palmae Juss.] '
                value = re.sub(r"\[.*?\]", "", value)
                value = value.strip()
                self.API_taxon[key] = value

            #get the decomposed taxonomic data
            tab_taxon = self.get_dict_from_species(self.API_taxon["original_name"])
            if tab_taxon is None: 
                return
            
            #set commons fields values
            _family = self.API_taxon["family"].split()
            self.API_taxon["family"] = _family[0]
            self.API_taxon["name"] = tab_taxon["name"]
            self.API_taxon["authors"] = tab_taxon["authors"]
            self.API_taxon['species'] = tab_taxon['species']
            self.API_taxon['infraspecies'] = tab_taxon['infraspecies']
            self.API_taxon['prefix'] = tab_taxon['prefix']
            
    def get_metadata(self):
    #return a formated dict with taxonomic data
        if not self.API_taxon:
            return
        
        if self.taxaname == self.API_taxon["name"]:
            self.ls_metadata["name"] = self.API_taxon["name"]
            self.ls_metadata["family"] = self.API_taxon["family"]
            self.ls_metadata['genus'] = self.API_taxon['genus']
            self.ls_metadata['species'] = self.API_taxon['species']
            #self.ls_metadata['infraspecies'] = self.get_dict_value(self.API_taxon, "infraspecies")
            self.ls_metadata['authors'] = self.API_taxon['authors']
            self.ls_metadata["accepted"] = (self.API_taxon['valid'] == '1')
            #get the status 
            status = self.API_taxon['statut'].strip()
            try:
                status = status.split()[0]
            except Exception:
                status = ''
            self.ls_metadata["status"] = status
            #self.ls_metadata["habitat"] = self.API_taxon['Habitat']
            _id = self.API_taxon["id"]
            self.ls_metadata["id"] = _id
            self.ls_metadata["webpage"] = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/' + str(_id)
            return self.ls_metadata

    def get_synonyms(self):
    #return the synonyms
        if self.soup is None:
            return
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
        if self.response is None: 
            return
    #get all children from the current taxon
        self.ls_children = []

        _page = 1
        try:
            response = self.response
            soup = self.soup
        except Exception:
            return
        
        url = self.ls_metadata["url"]
        tab_urllinks = []
        
        while response:
            if 'Not Found' in soup.title.text:
                break
            if 'Florical' not in soup.title.text:
                break
                # _key = self.soup.find_all("td", class_="first")
                # _value = self.soup.find_all("td", class_="second")
                # for column, row in zip(_key, _value):
                #     key = column.find("span", class_="text-info").text
                #     value = row.text.strip()
                #     #get standardized keys
                #     if key == "Taxa name":
                #         tab_taxon = self.get_dict_from_species(value)
                #         tab_urllinks.append(value)
                #         break
            else:
                #else decompose the list of links to get all taxa properties
                hrefs = soup.find("div", class_="span12")
                hrefs = hrefs.find_all("a")
                for href in hrefs:
                    if 'collection' in href["href"]:
                        txt = href.text.replace('\n', ' ').strip()
                        txt_ls = [i.strip() for i in txt.split('-')]
                        #tab_taxon = self._get_taxon_dictionnary (tab_result['taxaname'])
                        tab_taxon = self.get_dict_from_species(txt_ls[2])
                        if tab_taxon is None: 
                            continue
                        #families are associated with authors, so we split the name
                        tab_taxa = txt_ls[1].split()
                        tab_taxon["family"] = tab_taxa[0]
                        _valid = not (self.idrank == 14 and tab_taxon['genus'] != self.taxaname)
                        if _valid:                            
                            tab_urllinks.append(tab_taxon)
            _page += 1
            #response = self.get_responseAPI(url +'&page=' +str(_page), False)
            response = requests.get(url +'&page=' +str(_page), timeout=3).text
            soup = BeautifulSoup(response, 'html.parser')

        #works with the tab_urllinks to create a hierarchical list of taxa from families to infraspecies
        #tab to produce _child = {"id" : '', "taxaname" : '', "authors" : '', "rank" : '', "id_parent" : ''}
        i = 1
        #n_genus = 0
        for taxon in tab_urllinks:
            if self._get_id_taxa(self.ls_children, taxon['family']) is None:
                #add if the family do not already exists
                _child = {"id" : str(i+1), "taxaname" : taxon['family'], "authors" : '', "rank" : 'Family', "id_parent" : str(i)}
                self.ls_children.append(_child)
                i +=2
            if self._get_id_taxa(self.ls_children, taxon['genus']) is None:
                 #add if the genus do not already exists and set the family id into id_parent
                _idparent = self._get_id_taxa(self.ls_children, taxon['family'])
                _child = {"id" : str(i), "taxaname" : taxon['genus'], "authors" : '', "rank" : 'Genus', "id_parent" : _idparent}
                self.ls_children.append(_child)
                #n_genus += 1
                i +=1
                
            if taxon['rank'] == 'Hybrid':
                _species = ' '.join([taxon['genus'], taxon['prefix'], taxon['species']])
            else:
                _species = ' '.join([taxon['genus'], taxon['species']])

            if self._get_id_taxa(self.ls_children, _species) is None:
                 #add if the species do not already exists and set the genus id into id_parent
                _idparent = self._get_id_taxa(self.ls_children, taxon['genus'])
                _child = {"id" : str(i), "taxaname" : _species, "authors" : taxon['authors'], "rank" : taxon['rank'], "id_parent" : _idparent}
                self.ls_children.append(_child)
                i +=1
            _infraspecies = taxon['infraspecies']
            if len(_infraspecies) >0:
                if self._get_id_taxa(self.ls_children, taxon['name']) is None:
                     #add if the infraspecific do not already exists and set the species id into id_parent
                    _idparent = self._get_id_taxa(self.ls_children, _species)
                    _child = {"id" : str(i), "taxaname" : taxon['name'], "authors" : taxon['authors'], "rank" : taxon['rank'], "id_parent" : _idparent}
                    self.ls_children.append(_child)
                    i +=1
        return self.ls_children

    def _get_id_taxa(self, tab, key):
        for taxa in tab:
            if taxa['taxaname'] == key:
                return str(taxa['id'])
            
    def get_dict_from_species(self, _taxa):
        #return a taxa dictionnary of properties from a _taxa string
        #decompose a taxaname (from species to hybrid)
        if len(_taxa) <= 0 : 
            return
        tab_result = {}   
        index = -1
        tab_result["original_name"] = _taxa    
        tab_result["name"] =''
        #standardize ssp, var and subsp
        _taxa = re.sub(r'\s+ssp\.?\s+',' subsp. ', _taxa)
        _taxa = re.sub(r'\s+subsp\s+',' subsp. ', _taxa)
        _taxa = re.sub(r'\s+var\s+',' var. ', _taxa)
        _taxa = re.sub(r'\s+forma\.?\s+',' f. ', _taxa)


        _taxa = _taxa.strip()
 
        #split the resulting name, and exit if only one word
        tab_taxon = []
        tab_taxon = _taxa.split()
        if len(tab_taxon) < 2: 
            return

        #by default consider a species binomial name = 'genus + epithet'
        tab_result['genus'] = tab_taxon[0].title()
        tab_result['species'] = tab_taxon[1].strip()
        tab_result["name"] = ' '.join([tab_result['genus'],tab_result['species']])
        tab_result['prefix'] =''
        tab_result['infraspecies']=''
        tab_result['rank'] = ''
        tab_result['basename'] = ''
        tab_result['authors'] = ''
        tab_result["names"] = ''
        
        #base name contain at least one upper case, probably the author name of a upper taxa than species (genus, family,...) -->return
        check_bn = re.sub(r'([A-Z])','',tab_result['species'])
        if check_bn != tab_result['species']:
            return

        #check for infraspecific
        if 'subsp.' in tab_taxon:
            tab_result['prefix'] ='subsp.'
            index = tab_taxon.index('subsp.')
            tab_result['rank'] = 'Subspecies'
        elif 'var.' in tab_taxon:
            tab_result['prefix'] ='var.'
            index = tab_taxon.index('var.')
            tab_result['rank'] = 'Variety'
        elif ' f. ' in _taxa:
            tab_result['prefix'] ='f.'
            index = tab_taxon.index('f.')
            tab_result['rank'] = 'Forma'
        elif 'x' in tab_taxon:
            index = tab_taxon.index('x')
            tab_result['rank'] = 'Hybrid'
        elif chr(215) in tab_taxon: #some api server use this character instead of 'x'
            index = tab_taxon.index(chr(215))
            tab_result['rank'] = 'Hybrid'
        else:
            tab_result['rank'] = 'Species'

        #get authors and basename considering autonyms and hybrids
        _basename = tab_result['species']
        _authors = ' '.join(tab_taxon[2:len(tab_taxon)])
        if tab_result['rank'] == 'Hybrid':
            tab_result['prefix'] ='x'
            _basename = tab_taxon[2]
            tab_result['species'] = _basename
            _authors = ' '.join(tab_taxon[index+2:len(tab_taxon)])
            tab_result["name"] = ' '.join([tab_result['genus'], tab_result['prefix'], tab_result['species']])
        elif index == len(tab_taxon)-2: #the taxa is ending by 'rank basename'
            _basename = tab_taxon[-1] 
            _authors = ' '.join(tab_taxon[2:index]) #suppoe authors between epithet and prefix
            tab_result['infraspecies'] = _basename #
            _name = ' '.join (tab_taxon[-2:]) #composite 'rank_basename'
            tab_result["name"] =  ' '.join([tab_result["name"], _name])
        elif index > 0: #the infraspecific prefix is not the penultimate term
            _basename = tab_taxon[index+1] ##' '.join(tab_taxon[index+1:index+2])
            _authors =  ' '.join(tab_taxon[index+2:len(tab_taxon)])
            tab_result['infraspecies'] = _basename
            tab_result["name"] =' '.join([tab_result["name"],tab_result['prefix'], _basename])
        tab_result['basename'] = _basename.lower()
        
        #clean empty values
        for value in tab_result.values():
            if value is None: 
                value =''
            value = value.strip()
            if value.lower() == 'null': 
                value =''
            
        #manage autonyms
        tab_result['autonym'] = (tab_result['infraspecies'] == tab_result['species'])
        if tab_result['autonym']:
            _authors = ''
        #manage authors
        _authors = _authors.strip()
        if _authors.lower() in ['sensu', 'ined', 'ined.', 'comb. ined.', 'comb ined']: 
            _authors =''
        tab_result['authors'] = _authors

        #get a list of all the names according to nomenclature
        # tab_allnames = []
        # _name = ' '.join([tab_result["genus"], tab_result["species"]])
        # _authors = tab_result["authors"]

        # if tab_result["rank"] == 'Hybrid':
        #     _name = ' '.join([tab_result["genus"], tab_result["prefix"],tab_result["species"]])

        # if tab_result["infraspecies"] != '':
        #     #add simple name (= name_prefix_infra)
        #     _syno = ' '.join([_name, tab_result["prefix"], tab_result["infraspecies"]])
        #     tab_allnames.append(_syno.strip())
        #     if _authors !='':
        #         #version with authors
        #         _syno = ' '.join([_syno, _authors])
        #         tab_allnames.append(_syno.strip())
        #         #version for autonyms (name_authors_prefix_infra)
        #         if tab_result['autonym']:
        #             _syno = ' '.join([_name, _authors, tab_result["prefix"],tab_result["infraspecies"]])
        #             tab_allnames.append(_syno.strip()) 
        # else :
        #     #add simple name
        #     tab_allnames.append(_name)
        #     #version with authors
        #     if _authors !='':
        #         _syno = ' '.join([_name, _authors])
        #         tab_allnames.append(_syno.strip())         
        # tab_result["names"] = tab_allnames
        return tab_result 

##___ENDEMIA access class based on API_Abstract________________________
class API_ENDEMIA(API_Abstract):
        
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        # #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        dict_rank =  {0 : '', 10 : 'Famille', 14 : 'Genre', 21 : 'Espece', 22 : 'Sous-espece', 23 : 'Variete', 25: 'Forme'}
        if self.idrank < 10:
            self.API_error = "No Result - Endemia only accept rank below the rank Family"
            return 
        
        try :
            _rank = dict_rank[self.idrank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = f"&rank={_rank}"
        _url_taxref = f"https://api.endemia.nc/v1/taxons?q={self.search_taxaname_noprefix}{_rank}&section=flore&includes=synonyms&maxitem=10"
        #get the result
        self.get_taxon_fromURL(_url_taxref,["data"], "full_name", "id")
        
    def get_metadata(self):
        #get metadata from Endemia
        if not self.API_taxon:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://endemia.nc/flore/fiche{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] = self.get_dict_value (self.API_taxon, "auteur")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self.get_dict_value (self.API_taxon, "rank"))
        # except Exception: 
        #     pass
        
        
        #if self.API_taxon["endemique"]:
        self.ls_metadata["endemic"] = self.get_dict_value (self.API_taxon, "endemique")
        self.ls_metadata["redlist_iucn"] = self.get_dict_value (self.API_taxon, "categorie_uicn")
        self.ls_metadata["protected"] = self.get_dict_value (self.API_taxon, "protected")
        #get details on protected status, nomenclature, habitat and images(= a 2nd query !)

        # _url_taxref = f"https://api.endemia.nc/v1/taxons/flore/{self.ls_metadata["id"]}"
        # try:
        #     _todos = self.get_responseAPI (_url_taxref, 2)
        #     _tab_attributes = _todos["data"]["attributes"]
        #     self.ls_metadata["published"] = (self.get_dict_value (_tab_attributes, "status") == "Published")
        #     self.ls_metadata["habitat"] = self.get_dict_value (_tab_attributes, "typehabitat")
        # except Exception:
        #     pass
        return self.ls_metadata

    def get_synonyms(self):
    #get the synonomys from the self.API_taxon
        if not self.API_taxon:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try:
            result_API = self.API_taxon["synonyms"]
        except Exception: 
            return
        for taxa in result_API:
            _name = self.get_dict_value (taxa, "full_name")
            _name = _name.strip()
            _author = self.get_dict_value (taxa, "auteur")
            _author = _author.strip()
            if _author:
                _name = _name + ' ' + _author
            if len(_name) > 0:
                tab_synonyms.add(_name.strip())
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

    def get_children(self):
        #get list of children
        if not self.API_taxon:
            return
        table_result = []
        table_valid = []
        _url_taxref = f"https://api.endemia.nc/v1/taxons?q={self.search_taxaname_noprefix}&section=flore"
        #get the response
        _api_result = self.get_responseAPI (_url_taxref)
        if _api_result is None:
            return
        try:
            self.API_result = _api_result["data"]
        except Exception:
            return
        
        for taxa in self.API_result:
            _rank = self.get_dict_value(taxa,"rank")
            _name = self.get_dict_value(taxa,"full_name")
            _rank = self.translate_rank(taxa["rank"])

            #do not accept taxa if no name or no rank
            if len(_rank)*len(_name)==0:
                continue
            #affect value
            taxa["rank"]=_rank
            taxa["full_name"]=_name
            taxa["id_parent"]= 0
            tb_taxa = _name.split()
            #get the parent name
            _parent =''
            if _rank in ['Subspecies', 'Variety']:
                _parent = ' '.join(tb_taxa[0:2])
            else:
                _parent = tb_taxa[0]
            #get the parent id
            for taxa2 in self.API_result:
                if taxa2["full_name"] == _parent:
                    taxa["id_parent"] = taxa2["id"]            
            #set the input taxa as the first taxa in the resulting list (table_result)
            if self.ls_metadata["id"] == taxa["id"]:
                taxa["id_parent"]=-1
                table_result.append(taxa)
            #add the valid tab to the final selection
            table_valid.append(taxa)
        #finally append only when taxa["id_parent"] > 0
        for taxa in table_valid:
            if taxa["id_parent"] * taxa["id"]> 0:
                table_result.append(taxa)
        #create and return the tab_children 
        self.ls_children = []
        for taxa in table_result:
            _child =  {"id" : taxa["id"], "taxaname" : taxa["full_name"], "authors" : taxa["auteur"], "rank" : taxa["rank"], "id_parent" : taxa["id_parent"]}
            self.ls_children.append(_child)
        return self.ls_children

##___TAXREF access class based on API_Abstract________________________
class API_TAXREF(API_Abstract):

    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        # #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        dict_rank =  {0 : '', 8 :'OR', 10 : 'FM', 11 : 'SBFM', 12 : 'TR', 13 : 'SBTR', 14 : 'GN', 21 : 'ES', 22 : 'SSES', 23 : 'VAR'} 
        try :
            _rank = dict_rank[self.idrank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = f"&taxonomicRanks={_rank}"
        #set the url to get the taxa from TaxRef
        _url_taxref = f"https://taxref.mnhn.fr/api/taxa/search?scientificNames={self.search_taxaname}{_rank}&kingdom=Plantae&domain=continental&page=1&size=5000"
        #get the response
        self.get_taxon_fromURL(_url_taxref,["_embedded","taxa"], "scientificName", "id")        


    def get_metadata(self):
        #get metadata from TaxRef (surclassing)
        if not self.API_taxon:
            return
        
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://inpn.mnhn.fr/espece/cd_nom/{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] =''
        self.ls_metadata["family"] = self.get_dict_value (self.API_taxon, "familyName")
        self.ls_metadata["accepted"] = self.API_taxon["referenceId"] == self.ls_metadata["id"]
        #get authors names and year of publication
        try:
            _authority = self.get_dict_value (self.API_taxon, "authority").split(",")
            self.ls_metadata["authors"] = _authority[0]
            self.ls_metadata["year"] = _authority[1]
            if len(self.ls_metadata["year"]) > 0:
                self.ls_metadata["nomenclature"] ="Published"
        except Exception: 
            pass
        return self.ls_metadata
       
    def get_children(self):
        if not self.API_taxon:
            return
        self.ls_children = []
        result_API = []
        _child = {}
        try:
            _url_taxref = f"https://taxref.mnhn.fr/api/taxa/{self.ls_metadata['id']}/children" #+str(self.id) + ""
            #print (_url_taxref)
            _todos = self.get_responseAPI (_url_taxref, 7)            
            result_API.append(self.API_taxon) #add the input taxa
            result_API += _todos["_embedded"]["taxa"] #get the children
        except Exception: 
            return
        #set the children in a list of dictionnary
        for taxa in result_API:
            _child =  {"id" : '', "taxaname" : '', "authors" : '', "rank" : 'Unknown', "id_parent" : ''} 
            _child["id"] = self.get_dict_value(taxa, "id")
            _child["id_parent"] = self.get_dict_value(taxa,"parentId")
            _child["taxaname"] = self.get_dict_value(taxa,"scientificName")
            try:
                _authority = self.get_dict_value(taxa,"authority").split(",")
                _child["authors"] = _authority[0]
            except Exception: 
                pass
            try:
                _child["rank"] = self.translate_rank(self.get_dict_value(taxa,"rankName"))
            except Exception:  
                pass
            self.ls_children.append(_child)
        return self.ls_children

    def get_synonyms(self):
    #get list of synonyms
        if not self.API_taxon:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try: 
            #need a new API query to get the synonyms   
            _url_taxref = f"https://taxref.mnhn.fr/api/taxa/{self.ls_metadata['id']}/synonyms" # + str(self.id) +""
            _todos = self.get_responseAPI (_url_taxref, 2)
            result_API = _todos["_embedded"]["taxa"]
        except Exception: 
            return
        for taxa in result_API:
            #get the name and the authors
            _name = self.get_dict_value(taxa,"scientificName")
            try:
                _authority = self.get_dict_value(taxa,"authority").split(",") #split to extract the authors from the date
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
    
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        #exclude higher taxa than family
        if self.idrank < 10:
            self.API_error = "No Result - IPNI only accept rank below the rank Family"
            return 
                
        # #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        dict_rank =  {0 : '', 10 : 'f_familial', 14 : 'f_generic', 21 : 'f_species', 31 : 'f_species'}

        try :
            _rank = dict_rank[self.idrank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = f"&f={_rank}"
        # _tabname = self.search_taxaname_noprefix.split("+")
        # if len(_tabname) == 1:
        #     if self.search_taxaname_noprefix.endswith("eae"):
        #         _rank = "&f=f_familial"
        #     else:
        #         _rank = "&f=f_generic"
        # else:
        #     _rank = "&f=f_species"

        _url_taxref =f"http://beta.ipni.org/api/1/search?perPage=5&cursor=%2A&q={self.search_taxaname_noprefix}{_rank}"
        #get the response
        self.get_taxon_fromURL(_url_taxref,["results"], "name", "fqId")

    def get_metadata(self):
        #get metadata from IPNI
        if not self.API_taxon:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] =f"https://www.ipni.org/n/{self.ls_metadata["id"]}"
        self.ls_metadata["authors"] = self.get_dict_value (self.API_taxon, "authors")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self.get_dict_value (self.API_taxon, "rank"))
        # except Exception: 
        #     pass
        
        self.ls_metadata["family"] = self.get_dict_value (self.API_taxon, "family")          
        self.ls_metadata["publication"] = self.get_dict_value (self.API_taxon, "reference")

        #get the year of publication
        _year = self.get_dict_value (self.API_taxon, "publicationYear")
        if _year is None:
            _year = self.get_dict_value (self.API_taxon, "publicationYearNote")
        #set the year if exists
        if _year:
            self.ls_metadata["year"] = _year
        #set published tag if year is not empty
        # if len(self.ls_metadata["year"]) >0:
        #     self.ls_metadata["nomenclature"] ="Published"
        return self.ls_metadata

##___POWO access class based on API_Abstract________________________
class API_POWO(API_Abstract):
    
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        #exclude higher taxa than family
        if self.idrank < 10:
            self.API_error = "No Result - POWO only accept rank below the rank Family"
            return         
        # #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        dict_rank =  {0 : '', 10 : 'families_f', 14 : 'genus_f', 21 : 'species_f', 31 : 'species_f'} 
        try :
            _rank = dict_rank[self.idrank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = f"&f={_rank}"
        #create url
        _url_taxref =f"https://powo.science.kew.org/api/2/search?perPage=5&cursor=%2A&q={self.search_taxaname}{_rank}" 
        self.get_taxon_fromURL(_url_taxref,["results"], "name", "fqId")
        
    def get_metadata(self):       
        #get the metadata from POWO
        if not self.API_taxon:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = 'https://powo.science.kew.org' + self.get_dict_value (self.API_taxon, "url")
        self.ls_metadata["family"] = self.get_dict_value (self.API_taxon, "family")    
        self.ls_metadata["authors"] = self.get_dict_value (self.API_taxon, "author")
        #self.ls_metadata["rank"] = self.translate_rank(self.get_dict_value (self.API_taxon, "rank"))
        self.ls_metadata["accepted"] = self.API_taxon["accepted"]
        return self.ls_metadata
        
        
    def get_synonyms(self):
    ##get the synonomys from the self.id
        if not self.API_taxon:
            return
        self.ls_synonyms = []
        result_API = []
        tab_synonyms = set() #use a set to avoid duplicates
        try: 
            #need a new API query to get the synonyms   
            _url_taxref = f"https://powo.science.kew.org/api/2/taxon/{self.ls_metadata["id"]}"
            _todos = self.get_responseAPI (_url_taxref, 5)
            result_API = _todos["synonyms"]
        except Exception: 
            return
        for taxa in result_API:
            #get the name and the authors
            _name = self.get_dict_value(taxa,"name")
            _authors = self.get_dict_value(taxa,"author")
            if _authors:
                _name = _name + ' ' + _authors
            if _name :
                tab_synonyms.add(_name)
        self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms

    def get_children(self):
        if not self.API_taxon:
            return
        def search_child_taxref(id_parent):
        #recursive - get the children list from an input id_parent
            tab_result = []
            for taxa in table_taxa:
                if taxa["id_parent"] == id_parent:
                    tab_result.append(taxa)
                    tab_result += search_child_taxref(taxa["index"])
            return tab_result
#-------------------------
    #get list of children

        table_taxa=[]
        _idrank = self.idrank
        _taxa = self.taxaname
        #search at the genus level if a species
        if _idrank >= 21:
            _idrank = 14
            _taxa = _taxa.split()[0]
        #translate rank
        try:
            _rank = self.translate_rank(_idrank)
            _rank.lower()
        except Exception:
            return
        _url_taxref =f"https://powo.science.kew.org/api/2/search?perPage=5000&cursor=%2A&q=&{_rank}={_taxa}&f=accepted_names"
        #_url_taxref = _url_taxref.replace(' ','%20')
        #increase the timeout to 20 seconds to allow big queries (up to 5000 names)
        _todos = self.get_responseAPI (_url_taxref, 20)
        #try to get result JSON

        table_taxref = {'fqId': self.API_taxon['fqId'], 'name': self.API_taxon['name'], 'author': self.API_taxon['author'], 'rank': self.API_taxon['rank']}
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
            _name = self.get_dict_value(taxa,"name")
            taxa["index"] = index
            _index_taxa_id[_name] = index
            index += 1
        #search for parent
        for taxa in table_taxref:
            _rank = self.get_dict_value(taxa,"rank").lower()
            _name = self.get_dict_value(taxa,"name")
            _id = self.get_dict_value(taxa,"fqId")
            if len(_rank)==0:
                continue
            taxa["id_parent"]=0
            #get the parent name by spliting the taxaname            
            tb_taxa = _name.split()
            _parent =''
            if _rank in ['subspecies', 'variety']:
                _parent = ' '.join(tb_taxa[0:2])
            elif _rank =='genus':
                _parent = self.get_dict_value(taxa,"family")
            else:
                _parent = tb_taxa[0]
            #get the parent id within the table itself (use _index_taxa_id)
            try:
                taxa["id_parent"] = _index_taxa_id[_parent]
            except Exception:
                pass
            #set the idroot and set the id_parent = -1
            if _id == self.ls_metadata["id"]:
                taxa["id_parent"]=-1
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
            _author = self.get_dict_value(taxa,"author")
            _rank = self.get_dict_value(taxa,"rank")
            _rank = self.translate_rank(_rank)
            _name = self.get_dict_value(taxa,"name")
            _child =  {"id" : taxa["index"], "taxaname" : _name, "authors" : _author, "rank" : _rank, "id_parent" : taxa["id_parent"]}
            self.ls_children.append(_child)
        return self.ls_children


class API_GBIF(API_Abstract):
#API for retrievin data from GBIF
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        _url_taxref = f"https://api.gbif.org/v1/species/match?name={self.search_taxaname_noprefix}&verbose=true"
        self.get_taxon_fromURL(_url_taxref, None, "canonicalName", "usageKey")
        if self.API_taxon :
            return
    #test for alternative in self.API_result
        try:
            self.API_result = self.API_result[0]["alternatives"]
            self.get_taxon_from_API_Result("canonicalName", "usageKey",{"kingdom": "Plantae"})
        except Exception:
            return

    def get_metadata(self):
    #get metadata from GBIF
        if not self.API_taxon:
            return
        self.ls_metadata["webpage"] = f"https://www.gbif.org/species/{self.ls_metadata["id"]}"
        _scientificname = self.get_dict_value (self.API_taxon, "scientificName")
        if len(_scientificname) > 0:
            _author = _scientificname.replace(self.ls_metadata["name"], "").strip()
            if _author:
                self.ls_metadata["authors"] = _author
        #self.ls_metadata["rank"] = self.get_dict_value (self.API_taxon, "rank").title()
        self.ls_metadata["class"] = self.get_dict_value (self.API_taxon, "class")
        self.ls_metadata["order"] = self.get_dict_value (self.API_taxon, "order")
        self.ls_metadata["family"] = self.get_dict_value (self.API_taxon, "family")
        self.ls_metadata["accepted"] = self.get_dict_value (self.API_taxon, "status") == 'ACCEPTED'
        return self.ls_metadata
    

class API_INATURALIST(API_Abstract):
#API for retrievin data from Inaturalist
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        _url_taxref = f"https://api.inaturalist.org/v1/taxa?q={self.search_taxaname_noprefix}"
        self.get_taxon_fromURL(_url_taxref,["results"], "matched_term", "id")

    
    def get_metadata(self):
    #get metadata from inaturalist
        if not self.API_taxon:
            return
        self.ls_metadata["webpage"] = f"https://www.inaturalist.org/observations?taxon_id={self.ls_metadata["id"]}"
        #self.ls_metadata["rank"] = self.get_dict_value (self.API_taxon, "rank").title()
        #self.ls_metadata["extinct"] = self.get_dict_value (self.API_taxon, "extinct")
        self.ls_metadata["occurrences"] = self.get_dict_value (self.API_taxon, "observations_count")
        if "conservation_status" in self.API_taxon:
            self.ls_metadata["redlist_iucn"] = self.get_dict_value (self.API_taxon["conservation_status"], "status").upper()
        return self.ls_metadata



##___TROPICOS access class based on API_Abstract________________________        
class API_TROPICOS(API_Abstract):
    def __init__(self, myTaxonData):
        super().__init__(myTaxonData)
        self.key_tropicos = myTaxonData.apikey
        _url_taxref =f"http://services.tropicos.org/Name/Search?name={self.search_taxaname_noprefix}&type=exact&apikey={self.key_tropicos}&format=json"
        self.ls_metadata["url"] = _url_taxref
        if self.key_tropicos is None:
            self.API_error = "Connection error - Use a valid api_key to access to Tropicos"
            return
        #get the response
        self.get_taxon_fromURL(_url_taxref, None, "ScientificName", "NameId")
        
    def get_metadata(self):
    #get metadata from Tropicos
        if not self.API_taxon:
            return
        #self.ls_metadata["name"] = self.name
        self.ls_metadata["webpage"] = f"https://www.tropicos.org/name/{self.ls_metadata["id"]}"        
        self.ls_metadata["authors"] = self.get_dict_value (self.API_taxon, "Author")
        self.ls_metadata["family"] = self.get_dict_value (self.API_taxon, "Family")
        # try:
        #     self.ls_metadata["rank"] = self.translate_rank(self.get_dict_value (self.API_taxon, "RankAbbreviation"))
        # except Exception:
        #     pass
        _valid = self.get_dict_value (self.API_taxon, "NomenclatureStatusName")
        #self.ls_metadata["accepted"] = (_valid =='Legitimate')
        if _valid =='Legitimate':
            self.ls_metadata["accepted"] = True
        elif _valid in ('Illegitimate','Invalid'):
            self.ls_metadata["accepted"] = False

        _publication = self.get_dict_value (self.API_taxon, "DisplayReference")
        if _publication:
            self.ls_metadata["publication"] = _publication

        _year = self.get_dict_value (self.API_taxon, "DisplayDate")
        if _year:
            self.ls_metadata["year"] = _year
            #self.ls_metadata["nomenclature"] ="Published"
        #self.ls_metadata["publication"] = self.get_dict_value (self.API_taxon, "DisplayReference")
        # self.ls_metadata["nomenclature"] ="Unpublished"
        # if len(self.ls_metadata["year"]) > 0:
        #     self.ls_metadata["nomenclature"] ="Published"
        return self.ls_metadata
        
    def get_synonyms(self):
    #get list of synonyms
        if not self.API_taxon:
            return
        tab_synonyms = set()
        try:
            _url_taxref =f"http://services.tropicos.org/Name/{self.ls_metadata["id"]}/Synonyms?apikey={self.key_tropicos}&format=json"
            #print (_url_taxref)
            result_API = self.get_responseAPI (_url_taxref)
        except Exception: 
            return
        #get dictionnary 
        if not result_API:
            return
        for taxa in result_API:
            if taxa.get('SynonymName', None):
                _synonym = taxa['SynonymName']
                _name = self.get_dict_value (_synonym, "ScientificNameWithAuthors")
                tab_synonyms.add(_name)
            self.ls_synonyms = list(tab_synonyms)
        return self.ls_synonyms


    def get_children(self):
        #get list of children
        # _url_taxref =f"http://services.tropicos.org/Name/Search?name={self.search_taxaname_noprefix}&type=exact&apikey={self.key_tropicos}&format=json"
        # _url_taxref = self.ls_metadata["url"].replace('&type=exact','&type=wildcard')
        _url_taxref =f"http://services.tropicos.org/Name/Search?name={self.search_taxaname_noprefix}&type=wildcard&apikey={self.key_tropicos}&format=json"
        #get the response
        api_result = self.get_responseAPI (_url_taxref,10)
        if api_result is None:
            return
       
        _root = {}
        #create a dict index to search id_parent from scientific name
        dict_nameid = {}
        for taxa in api_result:
            dict_nameid[taxa["ScientificName"]] = taxa["NameId"]

        for taxa in api_result:
            taxa["id_parent"] = 0
            _rank = self.translate_rank(taxa["RankAbbreviation"])
            _idrank = dict_idrank.get(_rank.lower(), 0)
            if _idrank < self.idrank:
                continue
            _name = self.get_dict_value(taxa,"ScientificName")
            taxa["rank"] = _rank

            #get the parent name
            tb_taxa = _name.split()
            if _idrank > 21:
                _parent = ' '.join(tb_taxa[0:2])
            else:
                _parent = tb_taxa[0]
            #set the input taxa as the first taxa in the resulting list (table_result)
            if self.ls_metadata["id"] == taxa["NameId"]:
                taxa["id_parent"] = -1
                _root =  taxa
            else:
                #get the parent id
                taxa["id_parent"] = dict_nameid.get (_parent, 0)

        #create and return the tab_children 
        self.ls_children = []
        # _root = dict_nameid.get (_parent, 0)
        # _root["id_parent"] = -1
        #add the parent on the first row
        _child =  {"id" : _root["NameId"], "taxaname" : _root["ScientificName"], "authors" : _root["Author"], "rank" : _root["rank"], "id_parent" : -1}
        self.ls_children.append(_child)
        #append only when taxa["id_parent"] > 0
        for taxa in api_result:
            if taxa["id_parent"] * taxa["NameId"]> 0:
                _child =  {"id" : taxa["NameId"], "taxaname" : taxa["ScientificName"], "authors" : taxa["Author"], "rank" : taxa["rank"], "id_parent" : taxa["id_parent"]}
                self.ls_children.append(_child)

        return self.ls_children

# api_classe = API_Taxonomy("afa96b37-3c48-4c1c-8bec-c844fb2b9c92")
# name = "Miconia calvescens"
# rank = "species"
# base = "IPNI"
# if api_classe.search_taxon(name, rank, base):
#     print (api_classe.get_metadata())

