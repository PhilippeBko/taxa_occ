import re
import sys
import json
import webbrowser

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtSql
from PyQt5.QtCore import *

from taxa_model import *
from occ_model import *
from api_thread import *
from class_synonyms import *
from edit_taxaname import *
import json
import requests
from bs4 import BeautifulSoup


def createConnection(db):
    db.setHostName("localhost")
    # db.setDatabaseName("test")
    # db.setUserName("postgres")
    # db.setPassword("postgres")
    db.setDatabaseName("test")
    db.setUserName("postgres")
    db.setPassword("postgres")    
    #app2 = QApplication([])
    if not db.open():
        QMessageBox.critical(None, "Cannot open database",
                             "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        return False
    return True


class PN_add_Florical(QtWidgets.QMainWindow):
    data_prefix = {11: 'subfam.', 12: 'tr.', 13: 'subtr.', 15: 'subg.', 16: 'sect.', 17: 'subsect.',
                   18: 'ser.', 19: 'subser.', 21: '', 22: 'subsp.', 23: 'var.', 25: 'f.', 28: 'cv.', 31: 'x'}

    def __init__(self, QtSql):  # mode_edit = 0 (edition), mode_edit = 1 (add), mode_edit = 2 (move)
        super().__init__()
        self.QtSql = QtSql
        self.window = uic.loadUi("pn_florical.ui")
        model = QtGui.QStandardItemModel()
        self.window.links_tableView.setModel(model)
        self.window.links_tableView.hideColumn(1)
        self.window.links_tableView.horizontalHeader().setStretchLastSection(True)
        self.query = None

        self.window.search_pushButton.clicked.connect(self.button_click)
        # self.window.url_lineEdit.returnPressed.connect(self.linkbutton_click)
        self.window.url_lineEdit.textChanged.connect(self.clean_query)
        self.window.result_tabWidget.currentChanged.connect(self.linkbutton_click)
        

    def close(self):
        self.window.close()

    def show(self):
        self.window.show()
        self.window.exec_()
        
    def button_click(self):
        self.query = None
        self.linkbutton_click()


    def clean_query(self):
        self.query = None



    def linkbutton_click(self):
        if self.query == None:
            self.window.links_tableView.model().setRowCount(0)
            url = self.window.url_lineEdit.text().strip()
            url = url.replace("/florical_fr/", "/florical/")
            florical = Check_florical("Myrsine")
            ls_taxa = florical.get_details_urls(url)
            sql_query = "VALUES"
            separator = ''
            i = 0
            for n in ls_taxa:
                url = n["link"]
                sql_query += separator + \
                    " (" + str(i) + ",'" + str(n["taxaname"]).strip() + "')"
                separator = ","
                i += 1
            sql_query = "SELECT taxa_florical.index, taxa_florical.taxa, id_taxonref, original_name, id_synonym FROM (" +  sql_query + ") AS taxa_florical(index,taxa)"
            sql_query += "\n LEFT JOIN taxonomy.taxa_keynames tr ON taxonomy.pn_taxa_keyname(taxa_florical.taxa) = tr.key_name"
            self.query = QtSql.QSqlQuery(sql_query)

        index = self.window.result_tabWidget.currentIndex()
        model = self.window.links_tableView.model()
        #model.appendRow([QtGui.QStandardItem(str(x['taxaname'])) for x in ls_taxa])
        # print(ls_taxa)

        font = QtGui.QFont()
        font.setItalic(True)
        model.setRowCount(0)


        self.query.first()
        while self.query.next():
            i = self.query.value('index')
            if index == 0 and self.query.value('id_taxonref') > 0 and self.query.value('id_synonym') == None:
                display = True
            else:
                display = (index == 2 and self.query.value('id_taxonref') == None) or (index == 1 and self.query.value('id_synonym') > 0)

            if display:
                item = QtGui.QStandardItem(str(self.query.value('taxa')))
                item1 = QtGui.QStandardItem(str(self.query.value('index')))
                model.appendRow([item, item1])
                # item.setCheckable(True)
                # item.setCheckState(2)
        self.window.links_tableView.hideColumn(1)
            # item = model.item(i,0)
            # key_index = model.item(i,0).index()
            # if query.value('id_taxonref') == None:
            #     model.setData(key_index, font, Qt.FontRole)
            # if query.value('id_synonym') >0:
            #     model.setData(key_index, QtGui.QBrush(QtGui.QColor(255, 0, 0)), Qt.ForegroundRole)

        #print (sql_query)
          #print (florical.get_details_data(url))
            # taxa_json = json.dumps(florical.get_details_data(url), indent=2)
            # sql_query = "SELECT * FROM taxonomy.pn_taxa_add_json ('" +taxa_json +"')"
            # # QtSql.QSqlQuery.exec_(sql_query)
            # query = QtSql.QSqlQuery (sql_query)
            # query.next()


class Check_florical():
    def __init__(self, taxaname):
       # self.sql_query = "SELECT taxaname, basename, authors, id_endemia, id_florical FROM taxonomy.taxa_reference where id_endemia is not null"
       # self.query = QtSql.QSqlQuery ( self.sql_query)
        self.tab_result = []
        self.taxaname = taxaname
    #     url='http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/4221'
    #     url ='http://publish.plantnet-project.org/project/florical/search?q=Zygogynum amplexicaule'
    # #the taxa 553 included synonyms and types
    #     url = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/553'
    #     #url = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/3886'
    #     url = 'http://publish.plantnet-project.org/project/florical/search?q=Zygogynum pomiferum'
        url = 'http://publish.plantnet-project.org/project/florical/search?q=' + taxaname
        # self.get_details_urls()
        # self.get_details_urls(url)
        #print (self.tab_result)
        # exit()


    def get_children_urls(self, url=None):
        
        url = 'http://publish.plantnet-project.org/project/florical/search?q=' + self.taxaname
        _page = 1
        
        response = requests.get(url)
        tab_urllinks = []
        while response:
            soup = BeautifulSoup(response.text, 'html.parser')
            tab_result = {}

            if 'Florical' in soup.title.text:
                hrefs = soup.find("div", class_="span12")
                hrefs = hrefs.find_all("a")
                for href in hrefs:
                    if 'collection' in href["href"]:
                        txt = href.text.replace('\n', ' ').strip()
                        txt_ls = [i.strip() for i in txt.split('-')]
                        tab_result = {}
                        tab_result = {"family" : '', "genus" :'', "species": '', "infraspecies": '', "taxaname" : '',"basename":'', "authors" : '', "rank" : '', "id" : ''}
                        index = 0
                        _basename =''
                        #get the family, genus, species and taxaname
                        tab_taxon = txt_ls[1].split()
                        tab_result['family'] = tab_taxon[0]
                        tab_result['taxaname'] = txt_ls[2]
                        tab_taxon = tab_result['taxaname'].split()
                        tab_result['genus'] = tab_taxon[0]
                        tab_result['species'] = ' '.join(tab_taxon[0:2])
                        _basename = tab_taxon[1]
                        _authors = ' '.join(tab_taxon[2:len(tab_taxon)])
                        #check for infraspecific
                        if 'subsp.' in tab_taxon:
                            index = tab_taxon.index('subsp.')
                            tab_result['rank'] = 'Subspecies'
                        elif 'var.' in tab_taxon:
                            index = tab_taxon.index('var.')
                            tab_result['rank'] = 'Variety'
                        elif 'f.' in tab_taxon:
                            index = tab_taxon.index('f.')
                            tab_result['rank'] = 'Forma'
                        else:
                            tab_result['rank'] = 'Species'

                        #get authors and basename considering autonyms
                        if index == len(tab_taxon)-2:
                            _basename = tab_taxon[-1] ##' '.join(tab_taxon[index+1:1])
                            _authors = ' '.join(tab_taxon[2:index])
                            tab_result['infraspecies'] = tab_result['species'] + ' ' +' '.join(tab_taxon[-2:])
                        elif index > 0:
                            _basename = ' '.join(tab_taxon[index+1:index+2])
                            _authors =  ' '.join(tab_taxon[index+2:len(tab_taxon)])
                            tab_result['infraspecies'] = ' '.join(tab_taxon[0:4])
                        
                        tab_result['basename'] = _basename.strip()
                        tab_result['authors'] = _authors.strip()
                        tab_result['link'] = 'http://publish.plantnet-project.org' + href["href"]
                        #get the id
                        tab_id = tab_result['link'].split('/')
                        tab_result['id'] =tab_id[-1]

                        #print (tab_result['taxaname'],tab_result['family'],tab_result['genus'],tab_result['species'], tab_result['basename'], tab_result['authors'], tab_result['rank'])
                        #print (tab_result)
                        tab_urllinks.append(tab_result)
            _page += 1
            url = 'http://publish.plantnet-project.org/project/florical/search?q=' + self.taxaname +'&page=' +str(_page)
            response = requests.get(url)
        tab_result = []
        #_child = {"id" : '', "taxaname" : '', "authors" : '', "rank" : '', "idparent" : ''}
        i = 1
        for taxon in tab_urllinks:
            #if not taxon['family'] in tab_result:
            if self._get_id_taxa(tab_result, taxon['family']) == None:
                _child = {"id" : str(i), "taxaname" : taxon['family'], "authors" : '', "rank" : 'Family', "idparent" : str(i)}
                tab_result.append(_child)
                i +=1
            if self._get_id_taxa(tab_result, taxon['genus']) == None:
                _idparent = self._get_id_taxa(tab_result, taxon['family'])
                _child = {"id" : str(i), "taxaname" : taxon['genus'], "authors" : '', "rank" : 'Genus', "idparent" : _idparent}
                tab_result.append(_child)
                i +=1
            if self._get_id_taxa(tab_result, taxon['species']) == None:
                _idparent = self._get_id_taxa(tab_result, taxon['genus'])
                _child = {"id" : str(i), "taxaname" : taxon['species'], "authors" : taxon['authors'], "rank" : 'Species', "idparent" : _idparent}
                tab_result.append(_child)
                i +=1
            _infraspecies = taxon['infraspecies']
            if len(_infraspecies) >0:
                if self._get_id_taxa(tab_result, _infraspecies) == None:
                    _idparent = self._get_id_taxa(tab_result, taxon['species'])
                    _child = {"id" : str(i), "taxaname" : _infraspecies, "authors" : taxon['authors'], "rank" : taxon['rank'], "idparent" : _idparent}
                    tab_result.append(_child)
                    i +=1
        return tab_result

    def _get_id_taxa(self, tab, key):
        for taxa in tab:
            if taxa['taxaname'] == key:
                return str(taxa['id'])


    def get_details_urls(self, url=None):
        self.tab_result = []
        if url == None:
            url = 'http://publish.plantnet-project.org/project/florical/search?q=' + self.taxaname
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title #find("title").text
        tab_result = {}
        if 'Florical' in title:
            hrefs = soup.find("div", class_="span12")
            hrefs = hrefs.find_all("a")
            for href in hrefs:
                if 'collection' in href["href"]:
                    txt = href.text.replace('\n', ' ').strip()
                    #txt_ls = txt.split('-')
                    txt_ls = [i.strip() for i in txt.split('-')]
                   # print (txt_ls)
                    tab_result = {}
                    tab_result['taxaname'] = txt_ls[2]
                    tab_result['link'] = 'http://publish.plantnet-project.org' + href["href"]
                    #print (tab_result)
                    self.tab_result.append(tab_result)
        else:
            columns = soup.find_all("td", class_="first")
            rows = soup.find_all("td", class_="second")
            for column, row in zip(columns, rows):
                text_info = column.find("span", class_="text-info").text
                if text_info in ('Taxa name', 'Taxon'):
                    tab_result['taxaname'] = row.text.replace(
                        '\n', ' ').strip()
                if text_info == 'id_taxon':
                    tab_result['link'] = 'http://publish.plantnet-project.org/project/florical/collection/florical/taxons/details/' + row.text.strip()
                    self.tab_result.append(tab_result)
        return (self.tab_result)

    def get_details_data(self, url):
        self.tab_result = []
        url = url.replace("/florical_fr/", "/florical/")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find("title").text

        if 'Florical' in title:
            hrefs = soup.find("div", class_="span12")
            hrefs = hrefs.find_all("a")
            for href in hrefs:
                if 'collection' in href["href"]:
                    self.get_details_data(
                        'http://publish.plantnet-project.org' + href["href"])
            # exit()
        else:
            columns = soup.find_all("td", class_="first")
            rows = soup.find_all("td", class_="second")
            tab_result = {}
            tab_result["Taxa name"] = ''
            for column, row in zip(columns, rows):
                key = column.find("span", class_="text-info").text
                value = row.text.strip()
                # to suppress in parantheses case as 'Arecaceae Bercht. & J.Presl [= Palmae Juss.] '
                value = re.sub("[\[].*?[\]]", "", value)
                value = value.strip()
                tab_result[key] = value
                tab_taxa = value.split()
                if key == 'Family':
                    tab_result['Family'] = tab_taxa[0]
                    tab_result['Authors Family'] = ' '.join(
                        tab_taxa[1:len(tab_taxa)])
                    tab_result['Genus'] = ''
                    tab_result['Subgenus'] = ''
                if key == 'Species':
                    tab_result['Species'] = tab_taxa[1]
                    tab_result['Authors Species'] = ' '.join(
                        tab_taxa[2:len(tab_taxa)])
                if key == 'Taxa name':
                    tab_result['Species'] = ''
                    tab_result['Authors Species'] = ''
                    index = 0
                    if 'var.' in tab_taxa:
                        index = tab_taxa.index('var.')
                    elif 'subsp.' in tab_taxa:
                        index = tab_taxa.index('subsp.')
                    if index > 0:
                        tab_result['Infraspecific'] = tab_taxa[index + 1]
                        tab_result['Authors Infraspecific'] = ''
                        tab_result['Autonym'] = (
                            tab_taxa[1] == tab_taxa[index + 1])
                        if not tab_result['Autonym']:
                            tab_result['Authors Infraspecific'] = ' '.join(
                                tab_taxa[index+2:len(tab_taxa)])

            synonyms = soup.find("div", id="collapse5cf7bc681d027852d1a7cf36")
            tab_synonyms = []
            ##print (synonyms)
            if not synonyms == None:
                synonyms = synonyms.find_all("tr")
                i = 0
                for synonym in synonyms:
                    if i > 0:
                        tab_synonyms.append(
                            synonym.text.strip().split('\n')[0])
                    i += 1
            if len(tab_synonyms) > 0:
                tab_result['Synonyms'] = tab_synonyms
            self.tab_result.append(tab_result)
        return (tab_result)
       # exit()


class Check_endemia():
    def __init__(self):
        self.taxa_added = 0
        self.sql_query = "SELECT id_taxonref, taxaname, authors, id_endemia, id_rank "
        #self.sql_query += " FROM taxonomy.taxa_reference where id_endemia is not null and is_tree and iucn is NULL"
        self.sql_query += "\nFROM taxonomy.taxa_reference"
        self.sql_query += "\nWHERE _condition_"
        self.sql_query += "\nORDER BY taxaname"

        # self.sql_query = "SELECT a.id_taxonref, a.taxaname, a.authors, a.id_endemia, a.id_rank "
        # self.sql_query += "\nFROM taxonomy.taxa_reference a"
        # self.sql_query += "\nLEFT JOIN taxonomy.taxa_reference b ON b.id_taxonref = a.id_parent"
        # self.sql_query += "\nWHERE b.id_taxonref IS NULL AND a.id_rank>21"
        #self.sql_query += "\nLIMIT 1500"
        
    def test_endemia():
        sql_tmp = "Select id_taxonref, taxaname, authors, id_rank from taxonomy.taxa_names where id_rank = 21"
        query = QtSql.QSqlQuery(sql_tmp)
        while query.next():
            myPNTaxa = PNTaxa(query.value("id_taxonref"), query.value("taxaname"), query.value("authors"),query.value("id_rank"))
            _classeAPI = API_ENDEMIA(myPNTaxa)
            _classeAPI.get_metadata()

    def update_statut(self):
        sql_query = self.sql_query.replace("_condition_", "taxaname = 'Marsdenia lyonsioides'") ##id_rank >=21 AND statut IS NULL")
        #print (sql_query)
        query = QtSql.QSqlQuery(sql_query)
        tab_endemic  = []
        while query.next():
            # query.value("id_endemia")
            niamoto_name = str(query.value("taxaname")) ###'Glochidion billardierei' ###str(query.value("taxaname"))
            url_taxref = "https://api.endemia.nc/v1/taxons?q="+ niamoto_name + '&section=flore&includes=synonyms'
            _response = requests.get(url_taxref, timeout=2)
            ls_response = json.loads(_response.text)
            
            try:
                id_taxonref = str(query.value("id_taxonref"))
                for name in ls_response["data"]:
                    endemia_name = name["full_name"].strip()
                    if endemia_name == niamoto_name:
                        endemia_statut = name["endemique"]
                        if endemia_statut:
                            tab_endemic.append(id_taxonref)
                            #print (niamoto_name, "Endemique", id_taxonref)
            except:
                pass
        #print (",".join(tab_endemic))
        if len(tab_endemic)>0:
            sql_query = "UPDATE taxonomy.taxa_reference SET statut = 'E' WHERE id_taxonref IN ("  + ",".join(tab_endemic) + ")"
            print (sql_query)
            query = QtSql.QSqlQuery(sql_query)
                    
    def clean_text(self, txt):
        #get lower text
        txt = txt.strip().lower()
        #replace multi space and dot by 1 space
        txt = re.sub('\s+|\\.+',' ', txt)
        #replace non-accepted word by space
        txt = re.sub('\scomb\s|\sined\s|\ssp\s|\snov\s|\sspp\s',' ', txt)
        #keep only characters
        return re.sub ('[^a-z]','', txt)
    


    def jaccard_similarity(self, x,y):
        """ returns the jaccard similarity between two lists """
        intersection_cardinality = len(set.intersection(*[set(x), set(y)]))
        union_cardinality = len(set.union(*[set(x), set(y)]))
        return intersection_cardinality/float(union_cardinality)   

    def get_data_from_endemia (self, id_endemia):
        #return a table with taxa properties fill through endemia API
        try:
            url_api = "http://api.endemia.nc/v1/taxons/flore/"+ str(id_endemia)
            _response = requests.get(url_api, timeout=3)
            ls_response = json.loads(_response.text)
        except:
            return
        
        taxonomy = ls_response["data"]["taxonomy"]
        #create and fill taxa_endemia with basics infos
        taxa_endemia = {"id_endemia":id_endemia}
        taxa_endemia["name"] = get_str_value(taxonomy["name"])
        taxa_endemia["basename"] = None
        taxa_endemia["authors"] = None
        #get the hierarchy
        taxonomy = taxonomy["ancestors"]
        for name in taxonomy:
            _name = {}
            _name["id_endemia"] = name["code"]
            _name["name"] = get_str_value(name["text"])
            _name["id_parent"] = name["parent"]
            _name["id_rank"] = None
            #set the rank tab and translate rank from endemia to taxonomy.taxa_rank
            if name["rank"] == 15:
                _name["id_rank"] = 23
                taxa_endemia["variety"] = _name
            if name["rank"] == 14:
                _name["id_rank"] = 22
                taxa_endemia["subspecies"] = _name
            elif name["rank"] == 13:
                _name["id_rank"] = 21
                taxa_endemia["species"] = _name
            elif name["rank"] == 10:
                _name["id_rank"] = 14
                taxa_endemia["genus"] = _name
            elif name["rank"] == 6:
                _name["id_rank"] = 10
                taxa_endemia["family"] = _name
            
        #get the attributes
        autonym = False
        taxonomy = ls_response["data"]["attributes"]
        if taxonomy["rank_id"]>=14:
            _dictmp = get_dict_from_species(taxa_endemia["name"])
            autonym =  _dictmp['autonym']

        if not autonym:
            #manage authors, exclude some words (comb. ined....)
            authors = get_str_value(taxonomy["auteur"])
            authors = re.sub('\s+ined.$','', authors)
            authors = re.sub('\s+nov.$','', authors)
            authors = re.sub('\s+sp.$','', authors)
            authors = re.sub('\s+comb.$','', authors)
            authors = authors.strip()
            authors = authors.strip(",")
            authors = get_str_value(authors)
            if len(authors) > 0:
                taxa_endemia["authors"] = get_str_value(authors)
        
        taxa_endemia["basename"] = taxonomy["nom"]
        taxa_endemia["published"] = (taxonomy["status"] == 'Published')
        taxa_endemia["endemic"] = (taxonomy["endemique"] == "o")
        taxa_endemia["iucn"] = None
        iucn = get_str_value(taxonomy["categorie_uicn"])
        if len(iucn) > 0:
            taxa_endemia["iucn"] = iucn
        taxa_endemia["id_florical"] = taxonomy["id_florical"]
        taxa_endemia["is_tree"] = None
        taxa_endemia["is_liana"] = None
        if not taxonomy["typeplante"] is None:
            if taxonomy["typeplante"].lower() == "a":
                taxa_endemia["is_tree"] = True
            elif taxonomy["typeplante"].lower() == "l":
                taxa_endemia["is_liana"] = True
        
        taxa_endemia["id_rank"] = None
        #taxa_endemia["id_taxonref"] = None
        translate_rank ={6:10, 10:14, 13:21, 14:22, 15:23}
        try:
            taxa_endemia["id_rank"] = translate_rank[taxonomy["rank_id"]]
        except:
            print ("UNKNOWN RANK : " + taxonomy["rank_id"])
            pass
        return taxa_endemia
    
    def update_from_endemia (self, id_endemia, id_taxonref):
        tab_endemia = self.get_data_from_endemia(id_endemia)
        if tab_endemia is None: return
        sql = "UPDATE taxonomy.taxa_reference SET "
        sql += "id_endemia = " + str(tab_endemia["id_endemia"])
        if not tab_endemia["authors"] is None:
            sql += ", authors = '" + str(tab_endemia["authors"]) +"'"
        sql += ", published = " + str(tab_endemia["published"])
        if tab_endemia["endemic"]: 
            sql += ", statut = 'E'"
        if not tab_endemia["iucn"] is None:
            sql += ", iucn = '" + str(tab_endemia["iucn"])  +"'"
        if not tab_endemia["id_florical"] is None:
            sql += ", id_florical = " + str(tab_endemia["id_florical"])
        if tab_endemia["is_tree"]:
            sql += ", is_tree = True "
        if tab_endemia["is_liana"]:
            sql += ", is_liana = True"
        
        sql +=" WHERE id_taxonref = " + str(id_taxonref)
        return sql

    def set_synonyms(self):
        tab_synonyms = {}
        sql_query = self.sql_query.replace("_condition_", "id_rank >=21")
        #sql_query +=  " LIMIT 1000"
        self.query = QtSql.QSqlQuery(sql_query) 
        print ('search for synonyms...')       
        while self.query.next():
            #properties of the local taxon to search in endemia API
            taxa_name = get_str_value(self.query.value("taxaname"))
            taxa_author = get_str_value(self.query.value("authors"))

            id_rank = self.query.value("id_rank")
            autonym = False
            if id_rank >21:
                _tmpdict = get_dict_from_species (taxa_name)
                taxa_name = _tmpdict['name']
                autonym = _tmpdict['autonym']
                if autonym:
                    taxa_author =''
 
            taxa_idendemia = self.query.value("id_endemia")
            taxa_fullname = (taxa_name + ' ' +taxa_author).strip()
            taxa_search = self.clean_text(taxa_fullname)
            taxa_idtaxonref = self.query.value("id_taxonref")
            get_dict_from_species('Miconia calcvescens comb. ined.')
            #url of endemia API
            try:
                url_taxref = "https://api.endemia.nc/v1/taxons?q="+ taxa_name + '&section=flore&includes=synonyms'
                _response = requests.get(url_taxref, timeout=3)
                ls_response = json.loads(_response.text)
            except:
                continue
                    
            for name in ls_response["data"]:
                #get basic infos
                endemia_id = name["id"]                    
                endemia_name = get_str_value(name["full_name"])
                endemia_author = get_str_value(name["auteur"])
                if autonym:
                    endemia_author = ''
                endemia_fullname = (endemia_name + ' '+ endemia_author).strip()    #self.clean_text(endemia_name+endemia_author)
                endemia_search = self.clean_text(endemia_fullname)
                #search from name
                if taxa_search == endemia_search:
                    #full equalities (taxaname + authors)     
                    endemia_synonyms = name["synonyms"]
                    tb_synonyms = []
                    for synonym in endemia_synonyms:
                        author_synonym = get_str_value(synonym["auteur"]).strip()
                        if author_synonym == 'sensu': continue
                        if len(get_str_value(synonym["full_name"])) <5 : continue

                        endemia_synonym = get_str_value(synonym["full_name"]).strip()
                        endemia_synonym = endemia_synonym.strip('.')
                        endemia_synonym = re.sub ('\s+', ' ', endemia_synonym)
                        
                        #author_synonym = re.sub('\ssensu$', '', author_synonym)
                        author_synonym = re.sub('\sined\.\s*$', '', author_synonym)
                        author_synonym = re.sub('\scomb\.\s*$', '', author_synonym)
                        endemia_synonym += ' ' + author_synonym

                        taxa = get_dict_from_species (endemia_synonym)
                        if taxa is None : continue
                        for item in taxa['names']:
                            sql = "SELECT * FROM taxonomy.pn_taxa_edit_synonym('_taxaname_', 'Nomenclatural', _idtaxonref_)"
                            sql = sql.replace("_taxaname_", item)
                            sql = sql.replace("_idtaxonref_", str(taxa_idtaxonref))
                            result = QtSql.QSqlQuery (sql)
                            code_error = result.lastError().nativeErrorCode ()
                            if len(code_error) == 0:
                                print ( "Synonym added : "+ item + " == " + taxa_fullname)
                    #     if len(author_synonym) > 0:
                    #         endemia_synonym += ' ' + author_synonym
                    #         if not endemia_synonym in tb_synonyms:
                    #             tb_synonyms.append(endemia_synonym)
                                
                    # for synonym in tb_synonyms:
                    #     sql = "SELECT * FROM taxonomy.pn_taxa_edit_synonym('_taxaname_', 'Nomenclatural', _idtaxonref_)"
                    #     sql = sql.replace("_taxaname_", synonym)
                    #     sql = sql.replace("_idtaxonref_", str(taxa_idtaxonref))
                    #     result = QtSql.QSqlQuery (sql)
                    #     code_error = result.lastError().nativeErrorCode ()
                    #     if len(code_error) == 0:
                    #         print ( "Synonym added : "+ synonym + " == " + taxa_fullname)
                       #print(sql)

                       # tab_synonyms[taxa_idtaxonref] = tb_synonyms
                        #print (endemia_synonym + ' = ' + taxa_fullname)   
    

        # for idtaxonref, synonyms in tab_synonyms.items():
        #     for item in synonyms:
        #         sql = "INSERT INTO taxonomy.taxa_synonym (synonym, category, id_taxonref, clean_name)"
        #         sql += "\nVALUES ('_taxaname_', 'Nomenclatural', _idto, taxonomy.pn_taxa_keyname('_taxaname'));"
        #         #sql += "\nDELETE FROM taxonomy.taxa_reference WHERE id_taxonref=_idfrom;"
        #         sql = "SELECT * FROM taxonomy.pn_taxa_edit_synonym('_taxaname_', 'Nomenclatural', _idtaxonref_)"
        #         sql = sql.replace("_taxaname_", item)
        #         sql = sql.replace("_idtaxonref_", str(idtaxonref))
        #         result = QtSql.QSqlQuery (sql)
        #         print (sql)




    def search_synonyms(self):
        sql_query = self.sql_query.replace("_condition_", "id_rank >=21") 
        self.query = QtSql.QSqlQuery(sql_query)
        
        tab_synonyms = []
        tab_nofound = []
        self.taxa_added = 0

        #create the tab_synonyms with the taxa to merged/created
        print ("search for synonyms...")
        valid_all = False
        while self.query.next():
            #properties of the local taxon to search in endemia API
            taxa_name = get_str_value(self.query.value("taxaname"))
            taxa_author = get_str_value(self.query.value("authors"))

            id_rank = self.query.value("id_rank")
            autonym = False
            if id_rank >21:
                _tmpdict = get_dict_from_species (taxa_name)
                taxa_name = _tmpdict['name']
                autonym = _tmpdict['autonym']
                if autonym:
                    taxa_author =''
 
            taxa_idendemia = self.query.value("id_endemia")
            taxa_fullname = (taxa_name + ' ' +taxa_author).strip()
            taxa_search = self.clean_text(taxa_fullname)
            taxa_idtaxonref = str(self.query.value("id_taxonref"))

            #url of endemia API
            try:
                url_taxref = "https://api.endemia.nc/v1/taxons?q="+ taxa_name + '&section=flore&includes=synonyms'
                _response = requests.get(url_taxref, timeout=3)
                ls_response = json.loads(_response.text)
            except:
                continue
            
            #search for names in all responses including synonyms, update data if necessary
            for name in ls_response["data"]:
                #get basic infos
                endemia_id = name["id"]                    
                endemia_name = get_str_value(name["full_name"])
                endemia_author = get_str_value(name["auteur"])
                if autonym:
                    endemia_author = ''
                endemia_fullname = (endemia_name + ' '+ endemia_author).strip()    #self.clean_text(endemia_name+endemia_author)
                endemia_search = self.clean_text(endemia_fullname)
                valid = False
                msg_suffix = "Taxon id" + str(taxa_idtaxonref) + ": " + taxa_fullname + " = " + endemia_fullname
                #search from name
                if taxa_search == endemia_search:
                    #full equalities (taxaname + authors)
                    valid = True
                    if taxa_idendemia == endemia_id :
                        break
                elif self.clean_text(taxa_name) == self.clean_text(endemia_name):
                    #similar taxaname
                    if valid_all:
                        valid = True
                    # elif autonym:
                    #     valid = True
                    #     if taxa_idendemia == endemia_id :
                    #         break                       
                    elif endemia_id == taxa_idendemia:
                        #authors difference, calculate similarity
                        similarity = self.jaccard_similarity(taxa_search, endemia_search)
                        if similarity > 0.9 :
                            valid = True
                        else:
                        #ask user for lower similarity
                            msg = "Validate authors, " + msg_suffix
                            msg += "\nDo you accept this update ? yes/no/all : "
                            user_input = input(msg)
                            if user_input[0].lower() == 'a':
                                valid_all = True
                                valid = True
                            else:
                                valid = (user_input[0].lower() == 'y')
                    else:
                    #similar taxaname, but author and id_endemia different (ask for user)
                        msg = "Validate authors/id_endemia, " + msg_suffix
                        msg += "\nDo you accept this update ? yes/no/all : "
                        user_input = input(msg)
                        if user_input[0].lower() == 'a':
                            valid_all = True
                            valid = True
                        else:
                            valid = (user_input[0].lower() == 'y')
                if valid:
                    sql_update = self.update_from_endemia(endemia_id, taxa_idtaxonref)
                    #print (sql_update)
                    print ("UPDATE " + msg_suffix)
                    query = QtSql.QSqlQuery()
                    query.exec(sql_update)
                    break

                if valid == False:
                    for name in ls_response["data"]:
                        #in other cases look for synonyms and add to tab_synonyms if found
                        endemia_synonyms = name["synonyms"]
                        id_endemia = name["id"]
                        for synonym in endemia_synonyms:
                            endemia_synonym = get_str_value(synonym["full_name"])
                            author_synonym = get_str_value(synonym["auteur"])
                            synonym_search = self.clean_text(endemia_synonym+author_synonym)
                            #add an entry if name = one of the synonyms
                            if self.clean_text(taxa_name) == self.clean_text(endemia_synonym):
                                # valid = True
                                # if len(taxa_author) * len(author_synonym) > 0 :
                                #     if self.jaccard_similarity(taxa_search, synonym_search) > 0.9: #taxa_search == synonym_search :   #self.clean_text(taxa_name) == endemia_synonym:
                                #     #if self.clean_text(taxa_author) == author_synonym:
                                valid = True
                                tab_synonym = {"id_taxonref": taxa_idtaxonref, "taxaname": taxa_name, "id_accepted":None, 'id_endemia': id_endemia, 'endemia_name' : endemia_name}
                                tab_synonyms.append(tab_synonym)
                                break
                    if valid: break
            #collect not found taxaname into tab_nofound
            if not valid:
                print (taxa_name, taxa_author, taxa_idtaxonref)
                tab_nofound.append([taxa_name, taxa_author, taxa_idtaxonref])
            # except:
            #     pass
        print (tab_nofound)
        print (str(len(tab_synonyms))+ " : synonyms to manage")
        if len(tab_synonyms) == 0:return
        
        
        #print ("search for taxa to add...")     
        i = 0
        #search through the synonyms entries for existing taxa or taxa to create
        for taxa in tab_synonyms:
            #search an accepted_name (in taxa_reference)
            endemia_name = taxa['endemia_name']
            idtaxonref = self.get_idtaxonref(endemia_name)
            #if already exists, set the id_taxonref as the id_accepted
            if idtaxonref is not None:
                taxa['id_accepted'] = idtaxonref
                #continue
            else:
            #other case, search for taxa informations on endemia
                id_endemia = taxa['id_endemia']
                taxa_endemia = self.get_data_from_endemia(id_endemia)
                if taxa_endemia is None : return
                
                taxa_idrank = taxa_endemia["id_rank"]
                #Test the family, mandatory
                text = taxa_endemia['family']["name"]
                id_family = self.get_idtaxonref(text)
                taxa_endemia['family']["id_taxonref"] = id_family
                if id_family is None:
                    print ("the family " + text + 'do not exist. Add before update')
                    continue
                #create genus, child of family,  if do not exist
                try:
                    text = taxa_endemia['genus']["name"]
                    id_genus = self.get_idtaxonref(text)
                    taxa_endemia['genus']["id_taxonref"] = id_genus
                    if id_genus is None:
                        id_genus_endemia = taxa_endemia['genus']["id_endemia"]
                        id_genus = self.add_taxa (id_genus_endemia, id_family)
                except:
                    pass
                #create species, child of genus, if do not exist
                try:
                    text = taxa_endemia['species']["name"]
                    id_species = self.get_idtaxonref(text)
                    if id_species is None:
                        id_species_endemia = taxa_endemia['species']["id_endemia"]
                        id_species = self.add_taxa (id_species_endemia, id_genus)
                except:
                    pass
                #add the accepted taxa itself
                #str_idendemia = str(taxa['id_endemia'])
                if taxa_idrank ==21:
                    taxa_idparent = id_genus
                elif taxa_idrank ==14:
                    taxa_idparent = id_family
                elif taxa_idrank > 21:
                    taxa_idparent = id_species
                else:
                    break
                #set the new id_taxonref to the id_accepted 
                taxa['id_accepted'] = self.add_taxa (id_endemia, taxa_idparent)
            
        #manage merge between taxas, all are now created
        # sql_query = "SELECT * FROM taxonomy.pn_taxa_merge (_idfrom, _idto,'', True)"
        # i = 0
        # for taxa in tab_synonyms:
            #add synonyms, merged id_taxonref with id_accepted
            if not taxa['id_accepted'] is None:
                # sql = "SELECT * FROM taxonomy.pn_taxa_merge (_idfrom, _idto,'', True)"

                # sql = "SELECT taxonomy.pn_taxa_edit_synonym ('_taxaname','Nomenclatural',_idto)"

                sql = "INSERT INTO taxonomy.taxa_synonym (synonym, category, id_taxonref)"
                sql += "\nVALUES ('_taxaname', 'Nomenclatural', _idto);"
                sql += "\nDELETE FROM taxonomy.taxa_reference WHERE id_taxonref=_idfrom;"
                #sql +="\nRETURNING id_synonym"

                sql = sql.replace("_taxaname", taxa["taxaname"])



                sql = "CALL taxonomy.pn_taxa_synonymy (_idfrom, _idto,'Taxinomic')"
                sql = sql.replace("_idfrom", str(taxa['id_taxonref']))
                sql = sql.replace("_idto", str(taxa['id_accepted']))

                
                #print (taxa['id_taxonref'], taxa['id_accepted'])
                result = QtSql.QSqlQuery (sql)


                code_error = result.lastError().nativeErrorCode ()
                #print ( "Synonym added : "+ taxa["taxaname"] + " == " + taxa["endemia_name"])
                #i +=1
                if len(code_error) == 0:
                    print ( "Synonym added : "+ taxa["taxaname"] + " == " + taxa["endemia_name"])
                    # sql = "DELETE FROM taxonomy.taxa_reference WHERE id_taxonref=" +str(taxa['id_taxonref'])
                    # QtSql.QSqlQuery (sql)
                    i +=1
                else:
                    print (str(taxa['id_taxonref']),result.lastError().text())
        print (str(self.taxa_added) + " taxa added")
        print (str(i) + " taxa merged")
        #print (tab_synonyms)

    def get_idtaxonref (self, str_taxon):
        sql_query = "SELECT id_taxonref FROM taxonomy.taxa_reference WHERE taxaname = '" + str_taxon +"'"
        #to test for all the name, specially for autonym
        sql_query = "SELECT id_taxonref FROM taxonomy.taxa_keynames WHERE original_name = '" + str_taxon +"' AND id_synonym IS NULL LIMIT 1"

        query = QtSql.QSqlQuery(sql_query)
        while query.next():
            return query.value("id_taxonref")

    def add_taxa (self, id_endemia, id_parent):
        str_id_endemia = str(id_endemia)
        str_idparent = str(id_parent)
        taxa_endemia = self.get_data_from_endemia(id_endemia)
        # translate_rank ={6:'10', 10:'14', 13:'21', 14:'22', 15:'23'}
        # url_taxref2 = "https://api.endemia.nc/v1/taxons/flore/"+ str_id_endemia
        # _response2 = requests.get(url_taxref2, timeout=2)
        # ls_response2 = json.loads(_response2.text)
        # #search for the name in the taxa_reference
        endemia_name = taxa_endemia["name"]
        idtaxonref = self.get_idtaxonref(endemia_name)
        if idtaxonref is not None:
            return idtaxonref
        # #get informations for the taxa to add
        # taxa2 = ls_response2["data"]["attributes"]
        #taxa_idrank = taxa2["rank_id"]
        taxa_name = taxa_endemia["name"]
        taxa_idrank = taxa_endemia["id_rank"] #translate_rank[taxa_idrank]
        taxa_basename = taxa_endemia["basename"]  #taxa2["nom"]
        taxa_authors = taxa_endemia["authors"]  #= get_str_value(taxa2["auteur"])
        taxa_published = taxa_endemia["published"] #str(taxa2["status"]== "Published")
        taxa_endemic = taxa_endemia["endemic"] 
        #add taxa
        sql_query = "SELECT * FROM taxonomy.pn_taxa_edit "
        sql_query+= "(0, '_basename', '_authors', _idparent, _idrank, _published, True)"
        sql_query = sql_query.replace("_basename", taxa_basename)
        sql_query = sql_query.replace("_authors", get_str_value(taxa_authors))
        sql_query = sql_query.replace("_idparent", str_idparent)
        sql_query = sql_query.replace("_idrank", str(taxa_idrank))
        sql_query = sql_query.replace("_published", get_str_value(taxa_published))
        query = QtSql.QSqlQuery(sql_query)
        code_error = query.lastError().nativeErrorCode ()        
        idtaxonref = self.get_idtaxonref(taxa_name)
        if len(code_error) == 0:
            print ("taxa added: " + taxa_name, "id_taxonref = " +str(idtaxonref))
            self.taxa_added += 1
        else:
            print ("Undefined error : " +  query.lastError().text())


        # get the idtaxonref from the endemia_name

        #print (sql_query)
        # set supplementary informations
        if taxa_endemia["id_florical"] is None:
            str_id_florical ='NULL'
        else:
            str_id_florical = str(taxa_endemia["id_florical"])
        sql_query = "UPDATE taxonomy.taxa_reference"
        sql_query += "\nSET id_endemia = " + str_id_endemia + ", id_florical = " + str_id_florical
        sql_query += "\nWHERE id_taxonref = " + str(idtaxonref)
        query = QtSql.QSqlQuery(sql_query)
        #add endemic statut
        if taxa_endemic:
            sql_query = "UPDATE taxonomy.taxa_reference"
            sql_query += "\nSET statut = 'E' WHERE id_taxonref = " + str(idtaxonref)
            query = QtSql.QSqlQuery(sql_query)

        return  idtaxonref


            
                # _attributes = ls_response["data"][0]
                # endemia_name = _attributes["full_name"].strip()
                # endemia_authors = _attributes["auteur"].strip()
                


                # if endemia_name != niamoto_name:
                     
                #     endemia_dictname = get_dict_from_species(endemia_name)
                    
                #    #if not (id_rank == 21 and endemia_dictname["autonym"]):
                        
                #     _synonyms = _attributes["synonyms"]
                #     tab_synonyms = []
                #     for _value in _synonyms:
                #         _synonym = _value["full_name"].strip()
                #         if not _synonym in tab_synonyms:
                #             tab_synonyms.append(_synonym)
                #     _synonym = ""
                #     if niamoto_name in tab_synonyms:
                #         print (id_taxonref, niamoto_name, ' == ', endemia_name, endemia_authors) #, _synonym)
                #     else:
                #         print (id_taxonref, niamoto_name, ' = ', endemia_name, endemia_authors) #, _synonym)
                #if len (tab_synonyms)>0:
                        # _synonym = "(Synonyms : " + ', '.join(tab_synonyms) + ")"
                        
                        #     _synonym = "(Synonyms)"

                            
                # if _eval is not None:
                #     print(str(self.query.value("id_taxonref")),
                #           self.query.value("taxaname"), _eval)
                #     sql = "UPDATE taxonomy.taxa_reference SET iucn ='" + _eval + \
                #         "' WHERE id_taxonref = " +  str(self.query.value("id_taxonref"))
                #     QtSql.QSqlQuery(sql)
               # if self.query.value("id_florical") != _idflorical:
                #    print (str(self.query.value("id_endemia")), self.query.value("taxaname"), self.query.value("id_florical"), _idflorical)




if __name__ == '__main__':
    app = QApplication(sys.argv)
   # window = uic.loadUi("pn_main.ui")

# connection to the database
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")

    if not createConnection(db):
        sys.exit("error")

    test = 0

    if test == 0:
        endemia = Check_endemia()
        endemia.test_endemia()
        #endemia.set_synonyms() #search_synonyms()
        #endemia.update_statut()
    elif test == 1:  # retourne les liens urls florical correspondant au taxa passé en argument
        florical = Check_florical(
            "Pseuderanthemum carruthersii var. atropurpureum")
        ls_result = []
        ls_taxa = []
        ls_taxa = florical.get_details_urls()
        for n in ls_taxa:
            url = n["link"]
            #print (florical.get_details_data(url))
            taxa_json = json.dumps(florical.get_details_data(url), indent=2)
            sql_query = "SELECT * FROM taxonomy.pn_taxa_add_json ('" + \
                taxa_json + "')"
            # QtSql.QSqlQuery.exec_(sql_query)
            query = QtSql.QSqlQuery(sql_query)
            query.next()
            # sql_query = "SELECT id_taxonref, taxaname, basename, authors, statut, id_florical  FROM taxonomy.taxa_reference WHERE id_rank = 14 AND basename ='"
            # sql_query += taxa_json["Genus"].lower() +"'"
            # sql_query += "\n UNION "
            # sql_query += "SELECT id_taxonref, taxaname, basename, authors, statut, id_florical  FROM taxonomy.taxa_reference WHERE id_rank = 21 AND basename ='"
            # sql_query += taxa_json["Species"].lower() +"'"

            # ls_result.append(florical.get_details_data(url))
        print(ls_result)
    elif test == 2:  # check la base taxa_reference vs florical pour les arbres
        sql_query = "SELECT id_taxonref, taxaname, basename, authors, id_endemia, id_florical, id_rank "
        sql_query += " FROM taxonomy.taxa_reference where is_tree and statut IN ('A', 'E')"
        query = QtSql.QSqlQuery(sql_query)
        while query.next():
            taxaname = query.value("taxaname")
            _id_rank = query.value("id_rank")
            taxaname = re.sub('[{}]', '', taxaname)
            florical = Check_florical(taxaname)
            ls_taxa = []
            ls_taxa = florical.get_details_urls()
    elif test == 3:
        truc = Check_florical('Zygogynum')
        print(truc.get_children_urls())
    elif test == 5:
        sql_query = "SELECT b.id_taxonref, b.statut, b.nomenclature,"
        sql_query += "\nCASE WHEN b.is_tree AND b.is_liana THEN 'tree, liana'"
        sql_query += "\nWHEN b.is_liana THEN 'liana'"
        sql_query += "\nWHEN b.is_tree THEN 'tree' END AS habit,is_tree, is_liana,"
        sql_query += "\nCASE WHEN dioecious THEN FALSE WHEN sexual_system = 'hermaphroditic' THEN TRUE ELSE NULL END::text AS hermaphroditic,"
        sql_query += "\nleaf_type,dioecious::text,fleshyfruit::text,dispersal_unit,cauliflorous::text,disperser,"
        sql_query += "\nmonocaulous::text,rythmic_growth::text,architecture AS model"
        sql_query += "\nFROM taxonomy.taxa_reference b LEFT JOIN taxonomy.taxa_morphology a ON a.id_taxaref = b.id_taxonref"
        sql_query += "\nWHERE  (b.is_tree OR b.is_liana OR b.statut IS NOT NULL OR a.id_taxaref IS NOT null)"
        #sql_query += "\nAND b.id_taxonref = 4604"
        #print (sql_query)
        query = QtSql.QSqlQuery(sql_query)
        while query.next():
            tab_json ={}


            tab_habit={}
            if query.value("is_tree"):
                tab_habit["tree"]= 'True'
            if query.value("is_liana"):
                tab_habit["liana"]= 'True'
            if len(tab_habit)>0:                
                tab_json["habit"] = tab_habit            
            
            tab_nc={}             
            _statut = str(query.value("statut"))
            if _statut == 'A':
                _statut = 'Autochtonous'
            elif _statut == 'E':
                _statut = 'Endemic'
            elif _statut == 'I':
                _statut = 'Introduced'
            else:
                _statut = ''
            if _statut !='':
                tab_nc ["statut"] = _statut
                tab_json["new caledonia"] = tab_nc

            if str(query.value("leaf_type")) !='':
                test={}
                test["type"] = str(query.value("leaf_type")).title()
                #test["phyllotaxy"] = str(query.value("phyllotaxy"))
                tab_json["leaf"] = test
                 
            tab_sexual={}
            if str(query.value("dioecious")) !='':
                tab_sexual["dioecious"] = str(query.value("dioecious")).title()
            if str(query.value("hermaphroditic")) !='':
                tab_sexual["hermaphrodite"] = str(query.value("hermaphroditic")).title()
            if str(query.value("fleshyfruit")) !='':
                tab_sexual["fleshy fruit"] = str(query.value("fleshyfruit")).title()
            
            if str(query.value("dispersal_unit")) !='':
                tab_sexual["dispersal unit"] = str(query.value("dispersal_unit")).title()
            # _dispersal_unit = str(query.value("dispersal_unit"))
            # if len(_dispersal_unit)>0:
            #     _dispersal_unit = _dispersal_unit.replace(' ','')
            #     tab_sexual["dispersal unit"] = _dispersal_unit.split(',')
            #     [x.title() for x in tab_sexual["dispersal unit"]]

            if len(tab_sexual)>0:
                tab_json["sexual"] = tab_sexual

            tab_disperser = {}
            _disperser = str(query.value("disperser"))
            if len(_disperser) > 0:
                _disperser = _disperser.replace(' ','')
                _disperser = _disperser.split(',')
               #_disperser = [x.lower() for x in _disperser]
                for disperser in _disperser:
                    tab_disperser[disperser.strip().lower()] = 'True'
            if len(tab_disperser)>0:
                tab_json["disperser"] = tab_disperser


            #else:
                #json_props = json_props.replace("[_disperser]", _nullvalue)


            tab_archi={}
            if str(query.value("model")) !='':
                tab_archi["model"] = str(query.value("model")).title()
            if str(query.value("monocaulous")) !='':
                tab_archi["monocaulous"] = str(query.value("monocaulous")).title()
            if str(query.value("cauliflorous")) !='':
                tab_archi["cauliflorous"] = str(query.value("cauliflorous")).title()
            if str(query.value("rythmic_growth")) !='':
                tab_archi["rythmic growth"] = str(query.value("rythmic_growth")).title()
            if len(tab_archi)>0:
                tab_json["architecture"] = tab_archi

     
            
            json_props = json.dumps(tab_json)
            _published = not str(query.value("nomenclature")) in ['Unpublished', 'Autonym']
            sql_query2 = "UPDATE taxonomy.taxa_reference SET properties = '" +  json_props + "',"
            sql_query2 +=" published = " + str(_published)
            sql_query2 += " WHERE id_taxonref = " +  str(query.value("id_taxonref"))
            print (json_props)
            db.exec(sql_query2)
            ###TO DO 'ALTER TABLE taxonomy.taxa_reference ADD published boolean NULL DEFAULT True;'
            
            
            
            # if str(query.value("nomenclature")) in ['Unpublished', 'Autonym']:
            #     _published = False
            # else:
            #     _published = True
            # _published = not str(query.value("nomenclature")) in ['Unpublished', 'Autonym']
            # sql_query2 = "UPDATE taxonomy.taxa_reference SET published = " + _published
            # sql_query2 += " WHERE id_taxonref = " +  str(query.value("id_taxonref"))
            # print (json_props)
            # db.exec(sql_query2)

            #test =json.dumps(json_props)
            #print (json_crop)
        #newtest = PN_add_Florical(QtSql)
       # url_taxref = 'https://api.endemia.nc/v1/taxons?q=Myrsine'
        #newtest.show()
    # truc = Check_florical('Zygogynum pomiferum')
    # print (truc.get_details_urls())
    #exit()

    #sys.exit(app.exec_())
    #Check_florical('Zygogynum pomiferum')
    # print (truc.get_details_urls())
    exit()
    sys.exit(app.exec_())
