import re
import json
from PyQt5 import  QtSql
from datetime import datetime
from PyQt5 import QtWidgets

RANK_TYPOLOGY = {}
""" list_db_type_translate = {1:'boolean', 2:'integer', 3:'integer', 4:'integer', 5:'integer', 6:'numeric', 7: 'text', 10:'text', 14: 'date', 15:'date', 16:'date',
                          'bigint': 'integer', 'character varying': 'text','double precision' : 'numeric', 'real': 'numeric', 'smallint' : 'integer', 
                          'int64': 'integer', 'bool': 'boolean', 'float64': 'numeric'}
 """

list_db_traits = {
                    "stems": {"synonyms" : ['nb_stem', 'nb_tiges', 'tiges', 'tronc'], "type" : 'integer', "min": 1, "default":1, "tip": 'Number of stems at Breast Height [1m30]'},
                    "dbh": {"synonyms" : ['dhp', 'dbh_cm'], "type" : "numeric", "unit" : 'cm', "plot" :"hist", "min": 0, "max": 500, "tip": 'Diameter at Breast Height or 1m30 from the ground'},
                    "height":  {"synonyms" : ['hauteur', 'height_m'], "type" : "numeric", "unit" : 'm', "plot" :"hist", "min": 1, "max": 100, "tip": 'Height of the tree'},
                    "strata": {"synonyms" : ['strata'], "type" : "text", "tip": 'Tree stratum in the vertical direction'},
                    "bark_thickness": {"synonyms" : ['bark_thick'],"type" : "numeric", "unit" : 'mm', "plot" :"hist", "min": 1, "tip": 'Thickness of tree bark'},
                    "leaf_area": {"synonyms" : ['leafarea', 'leaf_area_cm2', 'leaf_area_cm²'], "type" : "numeric", "unit" : 'cm²', "plot" :"hist", "min": 0.01, "decimal": 5, "tip": 'Area of a leaf unit'},
                    "leaf_sla": {"synonyms" : ['sla', 'leafsla'], "type" : "numeric", "unit" : 'mm²/mg', "plot" :"hist", "min": 1, "max": 50, "decimal": 5, "tip": 'Specific Leaf Area'},
                    "leaf_ldmc": {"synonyms" : ['ldmc', 'leafldmc'], "type" : "numeric", "unit" : 'mg/g', "plot" :"hist", "min": 10, "max": 1000, "tip": 'Leaf Dry Matter Content'},
                    "leaf_thickness": {"synonyms" : ['leafthickness'], "type" : "numeric", "unit" : 'µm', "plot" :"hist", "min":10, "max": 1000, "tip": 'Thickness of the leaf'},
                    "wood_density": {"synonyms" : ['wd', 'wood_dens'],"type" : "numeric", "unit" : 'g/cm3', "plot" :"hist", "min": 0.1, "max": 2, "decimal": 5, "tip": 'Density of a wood core'},

                    "leaf_dry_weight": {"synonyms" : ['leafdryweight', 'dryleafmass', 'leafdrymatter', 'leaf_dry_weight_mg'],"type" : "numeric", "unit" : 'mg', "plot" :"hist", "min": 1, "max": 100000, "decimal": 2, "tip": 'Weight of a dry leaf unit'},
                    "leaf_fresh_weight": {"synonyms" : ['leaffreshweight', 'freshleafmass', 'leaffreshmatter', 'leaf_fresh_weight_mg'],"type" : "numeric", "unit" : 'mg', "plot" :"hist", "min": 10, "decimal": 2, "tip": 'Weight of a fresh leaf unit'},
                    "wood_core_diameter": {"synonyms" : ['core_diameter', 'core_diameter_mm', 'woodcorediameter'],"type" : "numeric", "unit" : 'mm', "plot" :"hist", "decimal": 3, "tip": 'Diameter of the wood core'},
                    "wood_core_length": {"synonyms" : ['core_length', 'woodcorelength', 'core_length_mm'],"type" : "numeric", "unit" : 'mm', "plot" :"hist", "decimal": 3, "tip": 'Length of the wood core'},
                    "wood_core_weight": {"synonyms" : ['core_weight', 'core_dry_weight', 'woodcoreweight', 'core_dry_weight_mg'],"type" : "numeric", "unit" : 'mg', "plot" :"hist", "decimal": 3, "tip": 'Dry weight of the wood core'}                    
                }
list_db_identity = {
                    "id" : {"synonyms" : ['id_individu', 'id_source', 'id_occurence', 'id_first_image', 'idoccurrence', 'id_collectionobject'], 
                            "type" : "integer"},
                    "taxaname" : {"synonyms" : ['taxa', 'taxonname', 'taxon', 'plantname', 'original_name','scientificname', 'nom_taxon_ref', 'nom_taxon', 'nomtaxon',
                                    'accepted_name'], "type" : "text", "tip": 'The name of the taxa'},
                    "identifier":  {"synonyms" : ['identifiant', 'code', 'number', 'tree'], "type" : 'text', "tip": 'The unique identifier for occurrences'},
                    "locality": {"value" : None, "type" : 'text', "editable" : True, "tip": 'The name of the locality where the occurrence was observed'},
                    "longitude": {"synonyms" : ['decimallongitude'],"type" : "numeric", "unit": 'DD-WGS84', "min": -180, "max": 180, "decimal": 8, "tip": 'The longitude where the plant was observed'},
                    "latitude": {"synonyms" : ['decimallatitude'],"type" : "numeric", "unit": 'DD-WGS84', "min": -90, "max": 90, "decimal": 8, "tip": 'The latitude where the plant was observed'},
                    "altitude": {"synonyms" : ['elevation'], "type" : 'numeric', "tip": 'The altitude where the plant was observed'},
                    "phenology" : {"synonyms" : ['phenologie'],"type" : "text"},
                    "flower": {"value" : None, "type" : 'boolean',"synonyms" : ['fleur', 'phenology'], "tip": 'Is the plant flowering ?'}, 
                    "fruit": {"value" : None, "type" : 'boolean',"synonyms" : ['fruit', 'phenology'], "tip": 'Is the plant fruiting ?'},
                    "month": {"synonyms" : ['month_obs','moisobservation', 'mois'],"type" : "integer", "default":datetime.now().month, "tip": 'The month when the plant was observed'},
                    "year": {"synonyms" : ['year_obs','anneeobservation'],"type" : "integer", "max": datetime.now().year, "default": datetime.now().year, "tip": 'The year when the plant was observed'},
                    "x": {"synonyms" : ['x_coordinate','coord_x', 'coordx'], "type" : 'numeric', "min": 0,  "tip": 'X coordinate on the plot'}, 
                    "y": {"synonyms" : ['y_coordinate','coord_y', 'coordy'], "type" : 'numeric', "min": 0,  "tip": 'Y coordinate on the plot'}, 
                }

list_db_fields = list_db_identity | list_db_traits
list_month = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
list_strata = ["", "Understorey", "Sub-canopy", "Canopy", "Emergent"]
list_db_fields["strata"]["items"] = list_strata
list_db_fields["month"]["items"] = list_month
list_numeric_db_fields = {key: value for key, value in list_db_fields.items() if value["type"] == "numeric"}

dict_identity = {   "name":'', 
                    "authors":'', 
                    "published": ['True', 'False']
                }
dict_leaf =     {   "type": ['Simple', 'Compound'], 
                    "phyllotaxy" : ['Alternate', 'Opposite', 'Verticillate'], 
                    "stipulate": ['True', 'False']
                }
dict_habit =    {   "epiphyte": ['True', 'False'], 
                    "herbaceous": ['True', 'False'], 
                    "liana" : ['True', 'False'], 
                    "parasite": ['True', 'False'], 
                    "shrub": ['True', 'False'],
                    "tree": ['True', 'False']
                }
dict_sexual =   {   "dioecious" :['True', 'False'],
                    "hermaphrodite": ['True', 'False'],
                    "fleshy fruit":['True', 'False'], 
                    "dispersal unit":['Seed', 'Fruit']
                }
dict_archi =    {   "model": ['Attims','Aubreville','Chamberlain','Champagnat','Cook','Corner','Fagerlind','Holtum','Koriba','Leuwenberg','Mangenot','Massart','McClure','Nozeran','Petit','Prevost','Rauh','Roux','Scarrone','Schoute','Stone','Tomlinson','Troll'],
                    "monocaulous" :['True', 'False'],
                    "cauliflorous":['True', 'False'], 
                    "rythmic growth":['True', 'False']
                }
dict_disperser ={   "anemochory":['True', 'False'], 
                    "barochory":['True', 'False'], 
                    "entomochory":['True', 'False'], 
                    "ornitochory":['True', 'False'], 
                    "myrmecochory":['True', 'False'], 
                    "saurochory":['True', 'False'],
                    "zoochorie":['True', 'False']
                }
dict_nc =       {   "status" :['Endemic','Autochtonous','Introduced']
                }
dict_properties = {}
dict_properties["identity"] = dict_identity
dict_properties["new caledonia"] = dict_nc
dict_properties["habit"] = dict_habit

dict_properties["leaf"] = dict_leaf
dict_properties["sexual"] = dict_sexual
dict_properties["disperser"] = dict_disperser
dict_properties["architecture"] = dict_archi

flower_reg_pattern = r'fl\.*|bt\.*|boutons?|cauliflor(e|a|ous)?|fert(?:ile|\.|)|fleurs?|inflorescences?|flowers?|buttons?|inflos?'
fruit_reg_pattern = r'fr\.*|figues?|fruits?|c[ôo]nes?|graines?|seeds?'


#common widget to set in a layout the database connection setting
#red if not connecter (dbopen=False), grren if connected(dbopen=True and self.db is not None)
class PN_database_widget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dbopen = False
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("background-color: transparent;")
        self.statusIndicator = QtWidgets.QWidget(frame)
        self.statusIndicator.setFixedSize(10, 10)
        self.statusConnection = QtWidgets.QLabel(None, frame)
        self.statusIndicator.setStyleSheet("background-color: rgb(255, 0, 0); border-radius: 5px;")
        self.statusConnection.setText("Not Connected")
        self.statusConnection.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        frame_layout = QtWidgets.QHBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        frame_layout.addWidget(self.statusIndicator)
        frame_layout.addWidget(self.statusConnection)
        self.setLayout(frame_layout)
    
    def open(self):
        import configparser
        config = configparser.ConfigParser()
        file_config = config.read('config.ini')
        section = 'database'
        if file_config and section in config.sections():
            self.db = QtSql.QSqlDatabase.addDatabase("QPSQL")
            self.db.setHostName(config['database']['host'])
            self.db.setUserName(config['database']['user'])
            self.db.setPassword(config['database']['password'])
            self.db.setDatabaseName(config['database']['database'])
            if self.db.open():
                self.dbopen = True
                default_db_name = QtSql.QSqlDatabase.database().databaseName()
                if default_db_name:
                    self.statusIndicator.setStyleSheet("background-color: rgb(0, 255, 0); border-radius: 5px;")
                    self.statusConnection.setText("Connected : "+ default_db_name)
            else:
                self.db.close()


def get_column_type(_type):
    #convert types in a standard postgresql format
    if _type in ['boolean', 'integer', 'numeric', 'text', 'date']:
        return _type
    elif _type in [1, 'bool']:
        return 'boolean'
    elif _type in [2,3,4,5,'bigint', 'smallint', 'int64', 'int32', 'int4','int2', 'int8']:
        return 'integer'
    elif _type in [6, 'double precision', 'real', 'float64', 'float32', 'float8', 'float4']:
        return 'numeric'
    elif _type in [7, 10, 'character varying', 'varchar', 'char']:
        return 'text'
    elif _type in [14, 15, 16, 20,'timestamp with time zone', 'timestamptz']:
        return 'date'
    else:
        return _type

def postgres_error(error):
    #convert the postgresl error in a text
    tab_text = error.text().split("\n")
    return '\n'.join(tab_text[:3])
    
def get_postgres_name(name):
    #check and correct invalid characters to be compatible with fields and database typography of postgresql
    name = re.sub(r'\W', '_', name.lower())
    if name[0].isdigit():
        name = '_' + name
    name = name [:63]
    return name

def get_all_names(fieldref):
    #return the list of names (key + synonyms) from list_db_fields
    if fieldref in list_db_fields:
        return [fieldref] + list_db_fields[fieldref].get("synonyms", [])
    return []

def get_reference_field(fieldname):
    #return the field_ref from a fieldname, check in key and synonyms of list_db_fields
    if fieldname in list_db_fields:
        return fieldname
    for key, value in list_db_fields.items():
        if fieldname in value.get("synonyms", '[]'):
            return key

#return any field value from the table taxonomy.taxa_reference    
def get_taxa_reference_value(id_taxonref, fieldname):
    """ 
        get a field value from the table taxonomy.taxa_reference according to a id_taxonref
    """
    if fieldname == 'taxonref':
        fieldname = 'CONCAT_WS (' ',taxaname, authors) AS taxonref'
    sql_txt = "SELECT " + fieldname + " FROM taxonomy.taxa_reference"
    sql_txt += "\nWHERE id_taxonref = " + str(id_taxonref)
    query = QtSql.QSqlQuery(sql_txt)
    query.next()
    return query.value(fieldname)

def get_str_value (value):
    """     
    Return the str value changing null values from database queries to Null string ('')
    """
    value = str(value).strip()
    if value.lower() not in ['null', 'none']:
        return value
    else:
        return ''
    
def get_dict_rank_value(idrank, key = None):
    #return data from ranks, load the table as a Json
    if len (RANK_TYPOLOGY) == 0:
        sql_query = "SELECT id_rank, row_to_json(t) json_row FROM (SELECT id_rank, rank_name, id_rankparent, suffix, prefix FROM taxonomy.taxa_rank ORDER BY id_rank) t"
        query = QtSql.QSqlQuery(sql_query)
        while query.next():
            RANK_TYPOLOGY[query.value("id_rank")] = json.loads(query.value("json_row"))
    if idrank in RANK_TYPOLOGY:
        if key is None:
            return RANK_TYPOLOGY[idrank].copy()
        else:
            return RANK_TYPOLOGY[idrank][key]

def get_dict_from_species(_taxa):
    #return a taxa dictionnary of properties from a _taxa string
    #decompose a taxaname (from species to hybrid)
    if len(_taxa) <= 0 : 
        return
    tab_result = {}
    tab_result["original_name"] = _taxa   
    index = -1
    #remove non-alphanumeric except space
    _taxa = re.sub (r'[0-9\sàâçèéêîôùû,;]',' ', _taxa)
    #standardize ssp, var and subsp
    _taxa = re.sub(r'\s+ssp\.?\s+',' subsp. ', _taxa)
    _taxa = re.sub(r'\s+subsp\s+',' subsp. ', _taxa)
    _taxa = re.sub(r'\s+var\s+',' var. ', _taxa)
    _taxa = re.sub(r'\s+forma\.?\s+',' f. ', _taxa)
#    _taxa = re.sub('\s+|,|\.+$','', _taxa)
    #delete end character (to improve, delete alla incorrect character at the end of the string)
    #make several run to extract ending character unwaiting
    _taxa = _taxa.strip()

    #split the resulting name
    tab_taxon = []
    tab_taxon = _taxa.split()
    if len(tab_taxon) < 2: 
        return

    #by default consider a species binomial name = 'genus + epithet'    
    tab_result["name"] =''
    tab_result['genus'] = tab_taxon[0].title()
    tab_result['species'] = tab_taxon[1].strip() #tab_result["name"]
    tab_result["name"] = ' '.join([tab_result['genus'],tab_result['species']])
    tab_result['prefix'] =''
    tab_result['infraspecies']=''
    tab_result['rank'] = ''
    tab_result['basename'] = ''
    tab_result['authors'] = ''
    tab_result["names"] = ''
    
    # #base name contain at least one upper case, probably the author name of a upper taxa than species (genus, family,...) -->return
    check_bn = re.sub(r'([A-Z])','',tab_result['species'])
    if check_bn != tab_result['species']:
       return

    _basename = tab_result['species']
    _authors = ' '.join(tab_taxon[2:len(tab_taxon)])
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
    
    for value in tab_result.values():
        #value = get_str_value(value)
        if value is None: 
            value =''
        value = value.strip()
        if value.lower() == 'null': 
            value =''
    tab_result['autonym'] = (tab_result['infraspecies'] == tab_result['species'])
    if tab_result['autonym']:
        _authors = ''
    _authors = _authors.strip()
    if _authors.lower() in ['sensu', 'ined', 'ined.', 'comb. ined.', 'comb ined']: 
        _authors =''

    tab_result['authors'] = _authors

    #tab_result =[]
    tab_allnames=[]
    _name = ' '.join([tab_result["genus"], tab_result["species"]])
    _authors = tab_result["authors"]

    if tab_result["rank"] == 'Hybrid':
        _name = ' '.join([tab_result["genus"], tab_result["prefix"],tab_result["species"]])

    if tab_result["infraspecies"] != '':
        #add simple name (= name_prefix_infra)
        _syno = ' '.join([_name, tab_result["prefix"], tab_result["infraspecies"]])
        tab_allnames.append(_syno.strip())
        if _authors !='':
            #version with authors
            _syno = ' '.join([_syno, _authors])
            tab_allnames.append(_syno.strip())
            #version for autonyms (name_authors_prefix_infra)
            if tab_result["infraspecies"] == tab_result["species"]:
                _syno = ' '.join([_name, _authors, tab_result["prefix"],tab_result["infraspecies"]])
                tab_allnames.append(_syno.strip()) 
    else :
        #add simple name
        tab_allnames.append(_name)
        #version with authors
        if _authors !='':
            _syno = ' '.join([_name, _authors])
            tab_allnames.append(_syno.strip())         
    tab_result["names"] = tab_allnames
    return tab_result

def get_taxa_identity(myPNTaxa):
    """     
    Return a json (dictionnary of sub-dictionnaries of taxa properties taxa identity + field properties (jsonb)
    """
    dict_db_properties = {}
    selecteditem = myPNTaxa
    if selecteditem  is None: 
        return
    #create a copy of dict_properties with empty values
    for _key, _value in dict_properties.copy().items():
        dict_db_properties[_key] = {}.fromkeys(_value,'')  
    
    #fill the identiy of the taxa, exit of error    
    tab_identity = dict_db_properties["identity"]
    try:
        tab_identity["authors"] =  selecteditem.authors
        if selecteditem.isautonym:
            tab_identity["published"] =  '[Autonym]'  
        else:
            tab_identity["published"] =  str(selecteditem.published)
        tab_identity["name"] =  selecteditem.basename     
    except Exception:
        return
    #fill the properties from the json field properties annexed to the taxa        
    try:
        json_props = get_taxa_reference_value(selecteditem.idtaxonref, "properties")
        json_props = json.loads(json_props)
        for _key, _value in dict_db_properties.items():
            try:
                tab_inbase = json_props[_key]
                if tab_inbase is not None:
                    for _key2, _value2 in tab_inbase.items():
                        _value2 = get_str_value(_value2)
                        if _value2 !='':
                            _value[_key2] = _value2.title()
            except Exception:
                continue
    except Exception:
        pass
    return dict_db_properties






# def get_str_lower_nospace(txt):
#     return txt.replace(" ", "").lower()

# def get_dict_rank_childs(idrank):
#     tab_childs ={}
#     if idrank == 1:
#         tab_childs.append(get_dict_rank_value(2))
#         tab_childs.append(get_dict_rank_value(3))

#     return tab_childs


# def get_taxa_metadata(myPNTaxa):
#     sql_query = "SELECT a.metadata FROM taxonomy.taxa_reference a"
#     sql_query += "\nWHERE a.id_taxonref = " + str(myPNTaxa.idtaxonref)
#     query = QtSql.QSqlQuery(sql_query)
    
#     query.next()
#     if not query.isValid():
#         return
#     if query.isNull("metadata"):
#         return
#     try:
#         json_data = query.value("metadata")
#     except Exception:
#         json_data = None
#         return
    
#     if json_data is None:
#         return
#     dict_db_properties = {}
#     for item, value in json.loads(json_data).items():
#         if  item not in dict_db_properties:
#             dict_db_properties[item] = {}
#         keys = ['url', 'webpage', '_links']
#         for key in keys:
#             if value.get(key,None) is not None:
#                 dict_db_properties[item][key] = value[key]

#     dict_db_properties = json.loads(json_data)
#     return dict_db_properties

# def get_traits_occurrences(myPNTaxa):
#     """     
#     Return a json (dictionnary of sub-dictionnaries of taxa traits from amap_data_occurences
#     """
#     selecteditem = myPNTaxa
#     if selecteditem  is None: 
#         return

#     sql_txt ="""
#      WITH dat_occ AS (SELECT * FROM amap_data_occurrences
#                         WHERE id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs (id_taxon_toreplace, True)))		
                        
# 	SELECT
# 		'dbh (cm)'::TEXT AS category,
#         count (b.dbh)::integer count,
#         avg(b.dbh) FILTER (WHERE b.dbh >5)::numeric(6,2) avg, 
#         NULL::numeric(6,2) min,        
#         max(b.dbh)::numeric(6,2) max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.dbh asc) FILTER (WHERE b.dbh > 5)::numeric(6,2) as median,
#         stddev(b.dbh)::numeric(6,2) stdv,
#         1 pos
#     FROM dat_occ b 
#    	UNION
# 	SELECT
# 		'height (m)'::TEXT AS category,
#         count (b.height)::integer count,
#         avg(b.height)::numeric(6,2) avg, 
#         NULL::numeric(6,2) min,
#         max(b.height)::numeric(6,2) max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.height asc)::numeric(6,2) as median,
#         stddev(b.height)::numeric(6,2) stdv,
#         2 pos
#     FROM dat_occ b 
#     UNION 
#     SELECT
# 		'wood density (g/cm3)'::TEXT AS category,
#         count (b.wood_density)::integer count,
#         avg(b.wood_density)::numeric(6,2) avg, 
#         min(b.wood_density)::numeric(6,2) min, 
#         max(b.wood_density)::numeric(6,2) max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.wood_density asc)::numeric(6,2) as median,
#         stddev(b.wood_density)::numeric(6,2) stdv,
#         3 pos
#     FROM dat_occ b
#     UNION
#     SELECT
# 		'leaf area (mm²)'::TEXT AS category,
#         count (b.leaf_area)::integer count,	
#         avg(b.leaf_area) ::numeric(6,2)  avg,
#         min(b.leaf_area) ::numeric(6,2)  min,
#         max(b.leaf_area) ::numeric(6,2)  max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.leaf_area asc)::numeric(6,2) as median,
#         stddev(b.leaf_area)::numeric(6,2) stdv,
#         4 pos
#     FROM dat_occ b 
#     UNION
#     SELECT
# 		'leaf sla (mm²/mg)'::TEXT AS category,
#         count (b.leaf_sla)::integer count,	
#         avg(b.leaf_sla) ::numeric(6,2) avg,
#         min(b.leaf_sla) ::numeric(6,2) min,
#         max(b.leaf_sla) ::numeric(6,2) max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.leaf_sla asc)::numeric(6,2) as median,
#         stddev(b.leaf_sla)::numeric(6,2) stdv,
#         5 pos
#     FROM dat_occ b
#     UNION
#     SELECT
#     	'leaf ldmc (mg/g)'::TEXT AS category,
#         count (b.leaf_ldmc)::integer count,	
#         avg(b.leaf_ldmc) ::numeric(6,2)  avg,
#         min(b.leaf_ldmc) ::numeric(6,2)  min,
#         max(b.leaf_ldmc) ::numeric(6,2)  max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.leaf_ldmc asc)::numeric(6,2) as median,
#         stddev(b.leaf_ldmc)::numeric(6,2) stdv,
#         6 pos
#     FROM dat_occ b
#     UNION
#     SELECT
#     	'leaf thickness (µm)'::TEXT AS category,
#         count (b.leaf_thickness)::integer count,	
#         avg(b.leaf_thickness) ::numeric(6,2)  avg,
#         min(b.leaf_thickness) ::numeric(6,2)  min,
#         max(b.leaf_thickness) ::numeric(6,2)  max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.leaf_thickness asc)::numeric(6,2) as median,
#         stddev(b.leaf_thickness)::numeric(6,2) stdv,
#         7 pos
#     FROM dat_occ b
#     UNION
#     SELECT
#     	'bark thickness (mm)'::TEXT AS category,
#         count (b.bark_thickness)::integer count,	
#         avg(b.bark_thickness) ::numeric(6,2)  avg,
#         min(b.bark_thickness) ::numeric(6,2)  min,
#         max(b.bark_thickness) ::numeric(6,2)  max,
#         percentile_cont(0.50) WITHIN GROUP (ORDER BY b.bark_thickness asc)::numeric(6,2) as median,
#         stddev(b.bark_thickness)::numeric(6,2) stdv,
#         8 pos
#     FROM dat_occ b
#     ORDER BY pos
#     """

#     sql_txt = sql_txt.replace('id_taxon_toreplace', str(selecteditem.idtaxonref))
#     #print (sql_txt)
#     query = QtSql.QSqlQuery(sql_txt)
#     tab_traits = {}
#     while query.next():
#         #to ensure order 
#         tab_trait ={'avg':'', "count":'', "min":'', "max":'', "median":'', "stdv":''}
#         for _key, _value in tab_trait.items():
#             tab_trait[_key] = get_str_value(query.value(_key))
#         tab_traits[query.value("category")] = tab_trait 
#     #print(tab_traits)
#     return tab_traits

#     sql_txt = sql_txt.replace('id_taxon_toreplace', str(selecteditem.idtaxonref))
#     query = QtSql.QSqlQuery(sql_txt)
#     tab_traits = {}
#     while query.next():
#         value = json.loads(query.value("json_value"))[0]
#         #to ensure order 
#         tab_trait ={'avg':'', "count":'', "min":'', "max":'', "median":'', "stdv":''}
#         for _key, _value in value.items():
#             tab_trait[_key] = get_str_value(_value)
#         tab_traits[query.value("category")] = tab_trait 
#     #print(tab_traits)
#     return tab_traits













if __name__ == '__main__':
    print (get_str_value(10) )
    taxa = get_dict_from_species('Miconia calvescens DC. var calvescens Birnbaum')
    print (taxa)
