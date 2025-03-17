import sys
import json
import requests
import time
import re
from core import functions as commons
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup

class TaxRefThread (QThread):
    #rowSearch_Signal = pyqtSignal(str, str, str)
    Result_Signal = pyqtSignal(str, object)
    #key_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
    def __init__(self, parent, myPNTaxa = None, filter = None):
        QThread.__init__(self, parent)
        self.PNTaxa_model = myPNTaxa
        self.status = 0
        self.list_api =  ["FLORICAL","ENDEMIA","TAXREF","IPNI","POWO", "TROPICOS"]
        # test for a _filter (= one of the valid base (IPNI, POWO, TAXREF, TROPICOS))
        try:
            if filter in self.list_api:
                self.list_api = [filter]
        except Exception:
            pass
        
    def kill(self):
        try:
            self.Result_Signal.emit("END", None)
        finally :
            self.status = 0

    def run(self):
        self.status = 1
        _list_api = {}
        if self.PNTaxa_model is None:
            self.Result_Signal.emit("END", None)
            return
        for base in self.list_api:
            #check for internet connexion 
            # try:
            if self.status == 0: 
                return
            if base=="TAXREF":
                _classeAPI = API_TAXREF(self.PNTaxa_model)
            elif base=="TROPICOS":
                _classeAPI = API_TROPICOS(self.PNTaxa_model)
            elif base=="IPNI":
                _classeAPI = API_IPNI(self.PNTaxa_model)
            elif base=="POWO":
                _classeAPI = API_POWO(self.PNTaxa_model)
            elif base=="FLORICAL":
                _classeAPI = API_FLORICAL(self.PNTaxa_model)
            elif base=="ENDEMIA":
                _classeAPI = API_ENDEMIA(self.PNTaxa_model)
                
            _classeAPI.get_metadata()
            _json = _classeAPI.metadata
            if self.status == 0 : 
                return
            _json["Query Time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.Result_Signal.emit(str(base), _json)
            if len(_json["url"]) * len(_json["name"]) > 0:
                _list_api[base] = _json
            if self.status == 0 :
                return
            time.sleep(0.2)
        self.Result_Signal.emit("END", _list_api)

##___class API_Abstract________________________
class API_Abstract ():
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
        super().__init__()
        self.list_field = {"name":'',"url":'', "webpage":''}
        self.ls_children = []

    def translate_rank(self, _rank):
        #return the standard name for a rank
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
        
        # if _rank in self.rank_translate.keys():
        #     return _rank.capitalize()
        # else:
        #     for key, value in self.rank_translate.items():
        #         if _rank in value:
        #             return key.capitalize()
        return 'Unknown'
   
    def api_response (self, _url, _timeout=2, _json = True):
    #send a request to the server and return the response (_json or text formated) waiting for a timeout
        try:
            _response = requests.get(_url, timeout=_timeout)
            if _json:
                return json.loads(_response.text)
            else:
                return _response.text
        except Exception:
            return ''

    def _get_list_value(self, dict, _key):
        try:
            return str(dict[_key]).strip()
        except Exception:
            return ''
        
    def get_children(self):
        self.list_field = []

    @property
    def metadata (self):
        return self.list_field
    
    @property
    def children (self):
        return self.ls_children
    
    @property
    def url(self):
        return self.list_field["url"]
##################################################################################

##################################################################################
##___FLORICAL access class based on API_Abstract, using scrapping of the web page (no API service)________________________
class API_FLORICAL(API_Abstract):
    #dict_rank =  {0 : '', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'subSpecies', 23 : 'Variety', 31 : 'Species'}  
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        self.tab_result = {}
        _taxa = self.myTaxa.taxaname
        if self.myTaxa.id_rank == 31:
            _taxa = _taxa.replace(' x ', ' ' + chr(215) + ' ')
        _url_taxref = "http://publish.plantnet-project.org/project/florical/search?q=" +_taxa
        _url_taxref = _url_taxref.replace(' ','%20')
        self.response = self.api_response(_url_taxref,3, False)
        if len(self.response) == 0:
            return
        self.soup = BeautifulSoup(self.response, 'html.parser')
        ###florical is not consistent with antonyms names (genus_species_authors_subspecies or genus_species_subspecies_authors)
        if 'Florical' in self.soup.title.text:
            if self.myTaxa.taxaname != self.myTaxa.simple_taxaname:
                _taxa = self.myTaxa.simple_taxaname
                _url_taxref = "http://publish.plantnet-project.org/project/florical/search?q=" +_taxa
                _url_taxref = _url_taxref.replace(' ','%20')
                self.response = self.api_response(_url_taxref,3, False)
                self.soup = BeautifulSoup(self.response, 'html.parser')
        if len(self.response) == 0:
            return
        
        self.taxaname = ''
        self.family = ''
        #soup = self.soup
        self.list_field["url"] = _url_taxref
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
            self.list_field["family"] = self.family #tab_taxa[0]
            self.list_field["name"] = tab_taxon['name']                
            self.list_field['genus'] = tab_taxon['genus']
            self.list_field['species'] = tab_taxon['species']
            self.list_field['infraspecies'] = tab_taxon['infraspecies']
            self.list_field['rank'] = tab_taxon['rank']
            self.list_field['basename'] = tab_taxon['basename']
            self.list_field['authors'] = tab_taxon['authors']
            self.list_field["accepted"] = str((self.tab_result['Valid'] == '1'))
            status = self.tab_result['Statut'].strip()
            try:
                status = status.split()[0]
            except Exception:
                status =''
            self.list_field["status"] = status
            self.list_field["habitat"] = self.tab_result['Habitat']

            #add synonyms
            _id = self.tab_result["id_taxon"]
            self.list_field["webpage"] = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/' + str(_id)
            t_synonyms = self.get_synonyms()
            if t_synonyms is not None:
                self.list_field["synonyms"] = t_synonyms
        
        return self.list_field
            # _links = {}
            # _links ["Florical"] = "http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/" + _url_florical
            # self.list_field["_links"] = _links

    def get_synonyms(self):
    #return the synonyms
        synonyms = self.soup.find("div", id="collapse5cf7bc681d027852d1a7cf36")
        tab_synonyms = []
        if synonyms is not None:
            synonyms = synonyms.find_all("tr")
            i = 0
            for synonym in synonyms:
                if i > 0:
                    _syno = synonym.text.strip().split('\n')[0]
                    tab_synonyms.append(_syno)
                i += 1
        return tab_synonyms

    def get_children(self):
    #get all children from the current taxon
        #url = 'http://publish.plantnet-project.org/project/florical/search?q=' + self.myTaxa.taxaname
        _page = 1
        try:
            response = self.response #requests.get(url)
            soup = self.soup
        except Exception:
            return
        url = self.list_field["url"]
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
            #response = self.api_response(url +'&page=' +str(_page), False)
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
    #dict_translate =  {'' : 'Unknown', 'Famille' : 'Family', 'Genre' : 'Genus', 'Espece' : 'Species', 'Sous-espece' : 'Subspecies', 'Variete' : 'Variety', 'Forme' : 'Forma'} 
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        _url_taxref = "https://api.endemia.nc/v1/taxons?q="+ self.myTaxa.simple_taxaname +'&section=flore&includes=synonyms'
        self.todos = self.api_response (_url_taxref, 2)
        self.list_field["url"] =_url_taxref
        
    def get_metadata(self):
        table_API = []
        try:
            table_API = self.todos["data"][0]
        except Exception: 
            return
        #get metadata on names
        _name = self._get_list_value (table_API, "full_name")
        if _name is None: 
            return        
        _id = self._get_list_value (table_API, "id")
        self.list_field["id"] =  str(_id)
        self.list_field["name"] = _name
        self.list_field["webpage"] = 'https://endemia.nc/flore/fiche'+ str(_id)
        try:
            self.list_field["rank"] = self.translate_rank(self._get_list_value (table_API, "rank"))
        except Exception: 
            pass       
        self.list_field["authors"] = self._get_list_value (table_API, "auteur")
        self.list_field["nomenclature"] =''        
        if table_API["endemique"]:
            self.list_field["status"] = "Endemic"
        self.list_field["habitat"] =''
        self.list_field["protected"] = self._get_list_value (table_API, "protected")

        #get details on protected status, nomenclature, habitat and images(= a 2nd query !)
        _url_taxref = "https://api.endemia.nc/v1/taxons/flore/"+ str(_id)
        _todos = self.api_response (_url_taxref, 2)
        try:
            table_API = _todos["data"]["attributes"]
        except Exception:
            return
        self.list_field["redlist"] = self._get_list_value (table_API, "categorie_evaluation")  
        self.list_field["nomenclature"] = self._get_list_value (table_API, "status")
        self.list_field["habitat"] = self._get_list_value (table_API, "typehabitat")
        
        #get synonyms
        t_synonyms = self.get_synonyms()
        if t_synonyms is not None:
            self.list_field["synonyms"] = t_synonyms
        return self.list_field

    def get_synonyms(self):
        table_API = []
        tab_synonyms = []        
        try:
            table_API = self.todos["data"][0]["synonyms"]
        except Exception: 
            return
        for taxon in table_API:
            _name = taxon["full_name"].strip()
            if taxon["auteur"]:
                _name = _name + ' ' + taxon["auteur"].strip()
            if _name not in tab_synonyms:
                if len(_name) > 0:
                    tab_synonyms.append(_name.strip())
        return tab_synonyms

    def get_children(self):
        #get list of children
        table_result = []
        table_json= []
        table_valid = []
                   
        table_json = self.todos["data"]
        for taxa in table_json:
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
            for taxa2 in table_json:
                if taxa2["full_name"] == _parent:
                    taxa["idparent"] = taxa2["id"]            
            #set the input taxa as the first taxa in the resulting list (table_result)
            if _rank == self.myTaxa.rank_name and _name==self.myTaxa.simple_taxaname:
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
    dict_rank =  {0 : '',8 :'OR', 10 : 'FM', 11 : 'SBFM', 12 : 'TR', 13 : 'SBTR', 14 : 'GN', 21 : 'ES', 22 : 'SSES', 23 : 'VAR'} 
    #dict_translate =  {'' : 'Unknown', 'Ordre' : 'Order', 'Famille' : 'Family', 'Sous-Famille' : 'SubFamily', 'Tribu' : 'Tribu','Sous-Tribu':'SubTribu', 'Genre' : 'Genus', 'Section' : 'Section', 'Espèce' : 'Species', 'Sous-Espèce' : 'Subspecies', 'Variété' : 'Variety'} 
            
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        self.dict_taxref = {}
        self.id = 0
        #set the rank level to avoid to load every taxa matching with the name
        _rank = ''
        try :
            _rank = self.dict_rank[self.myTaxa.id_rank]
        except Exception:
            _rank =''
        finally:
            if len(_rank) > 0: 
                _rank = "&taxonomicRanks=" +_rank
        _url_taxref = "https://taxref.mnhn.fr/api/taxa/search?scientificNames=" + self.myTaxa.simple_taxaname + _rank +"&domain=continental&page=1&size=5000"
        _url_taxref = _url_taxref.replace(' ','%20')
        self.list_field["url"] =_url_taxref
        _todos = self.api_response (_url_taxref, 3)
        try:
            for taxa in _todos["_embedded"]["taxa"]:
                if taxa["scientificName"] == self.myTaxa.simple_taxaname:
                    self.dict_taxref = taxa
                    break
        except Exception:
            return
        self._name = self._get_list_value (self.dict_taxref, "scientificName")
        self.id = self._get_list_value (self.dict_taxref, "id")

    def get_metadata(self):
        if self.id == 0: 
            return
        try:
            self.list_field["name"] = self._name            
            self.list_field["rank"] = self.translate_rank(self._get_list_value (self.dict_taxref, "rankName"))
        except Exception: 
            return

        self.list_field["family"] = self._get_list_value (self.dict_taxref, "familyName")
        self.list_field["authors"] =''
        _accepted = self._get_list_value (self.dict_taxref, "referenceId") == self.id
        self.list_field["accepted"] = str(_accepted)
        _authority = self._get_list_value (self.dict_taxref, "authority").split(",")
        try:
            self.list_field["authors"] = _authority[0]
            self.list_field["year"] = _authority[1]
        except Exception: 
            pass
        try:
            if len(self.list_field["year"]) > 0:
                self.list_field["nomenclature"] ="Published"
        except Exception: 
            pass
        self.list_field["webpage"] = 'https://inpn.mnhn.fr/espece/cd_nom/'+ str(self.id)
        #get the synonyms
        t_synonyms = self.get_synonyms()
        if t_synonyms is not None:
            self.list_field["synonyms"] = t_synonyms
        return self.list_field
       
    def get_children(self):
        if self.id == 0 : 
            return   
        
        self.ls_children = []
        table_taxa = []
        _child = {}
        try:
            _url_taxref = "https://taxref.mnhn.fr/api/taxa/" +str(self.id) + "/children"
            _todos = self.api_response (_url_taxref, 7)            
            table_taxa.append(self.dict_taxref) #add the input taxa
            table_taxa += _todos["_embedded"]["taxa"] #get the children
        except Exception: 
            return
        for taxa in table_taxa:
            _child =  {"id" : '', "taxaname" : '', "authors" : '', "rank" : 'Unknown', "idparent" : ''} 
            _child["id"] = self._get_list_value(taxa, "id")
            _child["idparent"] = self._get_list_value(taxa,"parentId")
            _child["taxaname"] = self._get_list_value(taxa,"scientificName")
            _authority = self._get_list_value(taxa,"authority").split(",")
            try:
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
        tab_synonyms = []
        if self.id == 0 : 
            return    
        _url_taxref = "https://taxref.mnhn.fr/api/taxa/" + str(self.id) +"/synonyms"
        
        _todos = self.api_response (_url_taxref, 2)
        try:
            result_API = _todos["_embedded"]["taxa"]
        except Exception: 
            return
        t = True
        i = 0
        while t:
            try:
                #delete potential comma and date combination at the end of the name
                _name = result_API[i]["fullName"].split(',')
                _name = _name[0].strip()
                t = True
                tab_synonyms.append(_name)
            except Exception:
                t = False
            i += 1
        return tab_synonyms
        
##___IPNI access class based on API_Abstract________________________
class API_IPNI(API_Abstract):
    #dict_translate =  {'' : 'Unknown', 'fam.' : 'Family', 'gen.' : 'Genus', 'spec.' : 'Species', 'subsp.' : 'Subspecies', 'var.' : 'Variety'} 

    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa

    def get_metadata(self):
        self.result_API = []
        self._rank = ''
        _taxa = self.myTaxa.simple_taxaname        
        if self.myTaxa.id_rank == 10:
            self._rank = "&f=f_familial"
        elif self.myTaxa.id_rank == 14:
            self._rank = "&f=f_generic" 
        elif self.myTaxa.id_rank == 21:
            self._rank = "&f=f_species"
        elif self.myTaxa.id_rank == 31:
            self._rank = "&f=f_species"
            _taxa = _taxa.replace (' x ',' ')

        _url_taxref ="http://beta.ipni.org/api/1/search?perPage=1&cursor=%2A&q=" + _taxa + self._rank
        _url_taxref = _url_taxref.replace(' ','+')
        self.list_field["url"] =_url_taxref
        _todos = self.api_response (_url_taxref,2)
        try:
            self.result_API = _todos["results"][0]
        except Exception: 
            return
        _name = self._get_list_value (self.result_API, "name")
        if _name is None: ##!= _taxa:
            return
        self.list_field["name"] = _name
        self.list_field["family"] = self._get_list_value (self.result_API, "family")
        self.list_field["authors"] = self._get_list_value (self.result_API, "authors")
        try:
            self.list_field["rank"] = self.translate_rank[self._get_list_value (self.result_API, "rank")]
        except Exception: 
            pass

        _year = self._get_list_value (self.result_API, "publicationYear")
        if len(_year) == 0:
            self.list_field["year"] = self._get_list_value (self.result_API, "publicationYearNote")
        else:
            self.list_field["year"] = _year
        self.list_field["publication"] = self._get_list_value (self.result_API, "reference")
        if len(self.list_field["year"]) >0:
            self.list_field["nomenclature"] ="Published"

        _url_ipni = self.result_API["fqId"]
        self.list_field["webpage"] ='https://www.ipni.org/n/'+ _url_ipni
        return self.list_field

##___POWO access class based on API_Abstract________________________
class API_POWO(API_Abstract):
    #dict_rank =  {0 : '', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'Subspecies', 23 : 'Subspecies', 31:'Hybrid'} 
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        self.table_taxref=[]

        
    def get_children(self):
        #get list of children
        _idrank = self.myTaxa.id_rank
        _taxa = self.myTaxa.simple_taxaname
        #search at the genus level if a species
        if _idrank==21:
            _idrank = 14
            _taxa = self.myTaxa.simple_taxaname.split()[0]
        #translate rank
        try:
            _rankRoot = self.translate_rank(self.myTaxa.id_rank)
            _rank = self.translate_rank(_idrank)
        except Exception:
            return
        _url_taxref = "https://powo.science.kew.org/api/2/search?perPage=5000&cursor=%2A&q="+'&'+_rank +'='+_taxa +'&f=accepted_names'
        _url_taxref = _url_taxref.replace(' ','%20')
        #increase the timeout to 7 to allow big queries (up to 5000 names)
        _todos = self.api_response (_url_taxref, 7)
        #try to get result JSON
        try:
            table_taxref = _todos["results"]
        except Exception:
            return
        #Create the table_data with an empiric id (a simple counter)
        self.table_data=[]
        id = 1
        idroot=0
        for taxa in table_taxref:
            _rank = self._get_list_value(taxa,"rank")
            _name = self._get_list_value(taxa,"name")
            if len(_rank)==0:
                continue
            taxa["idparent"]=0
            taxa["id"] = id
            id += 1
            #get the parent name by spliting the taxaname            
            tb_taxa = _name.split()
            _parent =''
            if _rank in ['Subspecies', 'Variety']:
                _parent = ' '.join(tb_taxa[0:2])
            elif _rank =='Genus':
                _parent = self._get_list_value(taxa,"family")
            else:
                _parent = tb_taxa[0]
            #get the parent id within the table itself
            for taxa2 in table_taxref:
                if taxa2["name"] == _parent:
                    taxa["idparent"]=taxa2["id"]            
            #set the search taxa as the first element in the resulting list (self.table_data)
            if _rank == _rankRoot and _name==self.myTaxa.simple_taxaname:
                taxa["idparent"]=-1
                idroot = taxa["id"]
                self.table_data.append(taxa)
            self.table_taxref.append(taxa)
        #no result for the root
        if idroot==0: 
            return
        #finally append childs only from the search taxon [root]
        self.table_data += self.search_child_taxref(idroot)
        self.ls_children =[]
        for taxa in self.table_data:
               # print (taxa["full_name"],taxa["auteur"],_rank,taxa["id"], _parent,taxa["idparent"])
            _author = self._get_list_value(taxa,"author")
            _rank = self._get_list_value(taxa,"rank")
            _name = self._get_list_value(taxa,"name")
            _child =  {"id" : taxa["id"], "taxaname" : _name, "authors" : _author, "rank" : _rank, "idparent" : taxa["idparent"]}
            self.ls_children.append(_child)
        return self.ls_children


    def search_child_taxref(self, idparent):
        #recursive - get the children list from an input idparent
        tab_result = []
        for taxa in self.table_taxref:
            if taxa["idparent"] == idparent:
                tab_result.append(taxa)
                tab_result += self.search_child_taxref(taxa["id"])
        return tab_result

    def get_metadata(self):       
        self._rank = ''
        result_API = []
        if self.myTaxa.id_rank == 10:
            self._rank = "&f=families_f" #"&f=f_familial"
        elif self.myTaxa.id_rank == 14:
            self._rank = "&f=genus_f"  #"&f=f_genus" 
        elif self.myTaxa.id_rank == 21:
            self._rank = "&f=species_f" #"&f=f_species"
        _url_taxref ="https://powo.science.kew.org/api/2/search?perPage=500&cursor=%2A&q=" + self.myTaxa.simple_taxaname + self._rank
        _url_taxref = _url_taxref.replace(' ','+')
        _todos = self.api_response (_url_taxref,2)
        self.list_field["url"] =_url_taxref
        try:
            result_API = _todos["results"][0]
        except Exception: 
            return
        _name = self._get_list_value (result_API, "name")

        if self.myTaxa.id_rank == 31:
            _name = _name.replace(chr(215), 'x')
            
        if _name is None: #!= self.myTaxa.simple_taxaname:
            return
        self.list_field["name"] = _name
        self.list_field["family"] = self._get_list_value (result_API, "family")    
        self.list_field["authors"] = self._get_list_value (result_API, "author")
        self.list_field["rank"] = self._get_list_value (result_API, "rank")
        self.list_field["accepted"] = self._get_list_value (result_API, "accepted")
        _url_powo = self._get_list_value (result_API, "url")
        self.list_field["webpage"] = 'https://powo.science.kew.org' + _url_powo
        return self.list_field

##___TROPICOS access class based on API_Abstract________________________        
class API_TROPICOS(API_Abstract):
   # dict_translate =  {'' : 'Unknown', 'fam.' : 'Family', 'gen.' : 'Genus', 'sp.' : 'Species', 'subsp.' : 'Subspecies', 'var.' : 'Variety'} 

    key_tropicos = "afa96b37-3c48-4c1c-8bec-c844fb2b9c92"
    def __init__(self, myPNTaxa = None):
        super().__init__()
        self.myTaxa = myPNTaxa
        self.id = 0

    def get_metadata(self):
        result_API = []
        self._rank = ''
        _type_search = "exact"
        _taxaname = self.myTaxa.simple_taxaname
        #delete the terms "subsp., var. and f." to search in Tropicos when infraspecies
        if self.myTaxa.id_rank > 21:
            _taxaname = _taxaname.replace(" subsp. "," ")
            _taxaname = _taxaname.replace(" var. "," ")
            _taxaname = _taxaname.replace(" f. "," ")
            _taxaname = _taxaname.replace(" x "," ")
            _type_search = "wildcard"
        _url_taxref ="http://services.tropicos.org/Name/Search?name=" + _taxaname +"&type="+ _type_search +"&apikey=" + self.key_tropicos+ "&format=json"
        _url_taxref = _url_taxref.replace(' ','+')
        _todos = self.api_response (_url_taxref,2)
        self.list_field["url"] =_url_taxref
        try :
            result_API = _todos[0]
            _id = result_API["NameId"]
            self.id = result_API["NameId"]
        except Exception: 
            return 
        _name = self._get_list_value (result_API, "ScientificName")
        if _name is None:
            return
        self.list_field["name"] = _name
        self.list_field["family"] = self._get_list_value (result_API, "Family")        
        self.list_field["authors"] = self._get_list_value (result_API, "Author")
        try:
            self.list_field["rank"] = self.translate_rank(self._get_list_value (result_API, "RankAbbreviation"))
        except Exception:
            pass
        _valid = self._get_list_value (result_API, "NomenclatureStatusName")
        if _valid =='Legitimate':
            self.list_field["accepted"] = 'True'
        elif _valid in ('Illegitimate','Invalid'):
            self.list_field["accepted"] = 'False'
        self.list_field["year"] = self._get_list_value (result_API, "DisplayDate")        
        self.list_field["publication"] = self._get_list_value (result_API, "DisplayReference")
        self.list_field["nomenclature"] ="Unpublished"
        if len(self.list_field["year"]) >0:
            self.list_field["nomenclature"] ="Published"
        _url_tropicos = self._get_list_value (result_API, "NameId")
        self.list_field["webpage"] = 'https://www.tropicos.org/name/' + _url_tropicos
        return self.list_field
        
    # def get_synonyms(self):
    #do not work in tropicos (no synonyms)
    # #get list of synonyms
    #     if self.id == 0 : 
    #         return
        
    #     _url_taxref =f"http://services.tropicos.org/Name/{self.id}/synonyms?apikey={self.key_tropicos}&format=json"
    #     _todos = self.api_response (_url_taxref,2)
    #     tab_synonyms = []
    #     try:
    #         result_API = _todos["_embedded"]["taxa"]
    #     except Exception: 
    #         return
    #     t = True
    #     i = 0
        
    #     while t:
    #         try:
    #             #delete potential comma and date combination at the end of the name
    #             _name = result_API[i]["fullName"].split(',')
    #             _name = _name[0].strip()
    #             t = True
    #             tab_synonyms.append(_name)
    #         except Exception:
    #             t = False
    #         i +=1
    #     return tab_synonyms


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
    import models.taxa_model as taxa_model
    app=QtWidgets.QApplication(sys.argv)
    #class_taxa = PNTaxa(123,'Zygogynum pancheri subsp. rivulare', 'DC.', 22)
    class_taxa = taxa_model.PNTaxa(123,'Zygogynum bicolor', 'DC.', 21)
    metadata_worker = TaxRefThread (app, class_taxa,"FLORICAL")
    metadata_worker.Result_Signal.connect(test_signal)
    

    #metadata_worker.set_taxaname("Miconia calvescens")
    metadata_worker.PNTaxa_model = class_taxa
    metadata_worker.start()
     #metadata_worker.kill()
        #window.identity_tableView.r22
    
    app.exec_()
    sys.exit(app.exec_())

