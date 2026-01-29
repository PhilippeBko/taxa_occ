import os
import sys

import re
from datetime import datetime

#BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
#sys.path.insert(0, BASE_DIR)

def resource_path(*paths):
    return os.path.join(BASE_DIR, *paths)




# functions.py
class ServiceRegistry:
    def __init__(self, dbconn, taxa=None, plot=None):
        self.db = dbconn
        self.taxa = taxa
        self.plot = plot


_registry = None

def init_registry(registry):
    global _registry
    if _registry is not None:
        raise RuntimeError("Registry already initialized")
    _registry = registry

def services():
    if _registry is None:
        raise RuntimeError("Registry not initialized")
    return _registry

def dbtaxa():
    return services().taxa

def db():
    return services().db


# class AppContext:
#     def __init__(self, PN_database):
#         self.dbtaxa = PN_database


# _context = None

# def init_context(context: AppContext):
#     global _context
#     if _context is not None:
#         raise RuntimeError("Context already initialized")
#     _context = context

# def dbase() -> AppContext:
#     if _context is None:
#         raise RuntimeError("Context not initialized")
#     return _context.dbtaxa





#synonyms for database value
dict_strata = {
    "understorey": [1, "sous-bois", "sotobosque", "understory"], 
    "sub-canopy": [2, "sous-canopée", "sub-cubierta"], 
    "canopy": [3, "canopée", "cubierta"], 
    "emergent": [4, "émergent","emergente"]
}
dict_month = {
    1: ["january","enero","janvier", "janv.", "jan.", "ene."], 
    2: ["february","febrero", "février", "feb.", "fev.", "fév."], 
    3: ["march", "marzo", "mars"],
    4: ["april", "abril", "avril"], 
    5: ["may", "mayo", "mai"], 
    6: ["june", "junio", "juin"],
    7: ["july", "julio", "juillet"], 
    8: ["august", "agosto", "août", "aug.", "ago."], 
    9: ["september", "septiembre", "septembre", "sept.", "sep"],
    10: ["october", "octubre", "octobre", "oct."], 
    11: ["november", "noviembre", "novembre", "nov."], 
    12: ["december", "diciembre", "décembre", "déc.", "dec.", "dic."]
}

""" list_db_type_translate = {1:'boolean', 2:'integer', 3:'integer', 4:'integer', 5:'integer', 6:'numeric', 7: 'text', 10:'text', 14: 'date', 15:'date', 16:'date',
                          'bigint': 'integer', 'character varying': 'text','double precision' : 'numeric', 'real': 'numeric', 'smallint' : 'integer', 
                          'int64': 'integer', 'bool': 'boolean', 'float64': 'numeric'}
 """

list_db_traits = {
                    "stems": {"synonyms" : ['nb_stem', 'nb_tiges', 'tiges', 'tronc'], "type" : 'integer', "min": 1, "default":1, "tip": 'Number of stems at Breast Height [1m30]'},
                    "dbh": {"synonyms" : ['dhp', 'dbh_cm'], "type" : "numeric", "unit" : 'cm', "plot" :"hist", "min": 0, "max": 500, "tip": 'Diameter at Breast Height or 1m30 from the ground'},
                    "height":  {"synonyms" : ['hauteur', 'height_m'], "type" : "numeric", "unit" : 'm', "plot" :"hist", "min": 1, "max": 100, "tip": 'Height of the tree'},
                    "strata": {"synonyms" : ['strate'], "type" : "text", "translate": dict_strata, "tip": 'Tree stratum in the vertical direction'},
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
                    "locality": {"type" : 'text', "editable" : True, "tip": 'The name of the locality where the occurrence was observed'},
                    "longitude": {"synonyms" : ['decimallongitude'],"type" : "numeric", "unit": 'DD-WGS84', "min": -180, "max": 180, "decimal": 8, "tip": 'The longitude where the plant was observed'},
                    "latitude": {"synonyms" : ['decimallatitude'],"type" : "numeric", "unit": 'DD-WGS84', "min": -90, "max": 90, "decimal": 8, "tip": 'The latitude where the plant was observed'},
                    "altitude": {"synonyms" : ['elevation'], "type" : 'numeric', "tip": 'The altitude where the plant was observed'},
                    "phenology" : {"synonyms" : ['phenologie'],"type" : "text"},
                    "flower": {"synonyms" : ['fleur', 'phenology'], "type" : 'boolean', "tip": 'Is the plant flowering ?'}, 
                    "fruit": {"synonyms" : ['fruit', 'phenology'], "type" : 'boolean', "tip": 'Is the plant fruiting ?'},
                    "month": {"synonyms" : ['month_obs','moisobservation', 'mois'],"type" : "integer", "default":datetime.now().month, "translate": dict_month, "tip": 'The month when the plant was observed'},
                    "year": {"synonyms" : ['year_obs','anneeobservation'],"type" : "integer", "max": datetime.now().year, "default": datetime.now().year, "tip": 'The year when the plant was observed'},
                    "x": {"synonyms" : ['x_coordinate','coord_x', 'coordx'], "type" : 'numeric', "min": 0,  "tip": 'X coordinate on the plot'}, 
                    "y": {"synonyms" : ['y_coordinate','coord_y', 'coordy'], "type" : 'numeric', "min": 0,  "tip": 'Y coordinate on the plot'}, 
                }

list_month = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
list_strata = ["", "Understorey", "Sub-canopy", "Canopy", "Emergent"]
list_db_traits["strata"]["items"] = list_strata
list_db_identity["month"]["items"] = list_month
list_db_fields = list_db_identity | list_db_traits
list_numeric_db_fields = {key: value for key, value in list_db_fields.items() if value["type"] == "numeric"}


list_db_properties = {
    # "identity":{"name": {"type": "text"}, 
    #             "authors": {"type": "text"}, 
    #             "published": {"type": 'boolean'},
    #             "rank": {"type": 'text', "items": ['Species', 'Subspecies', 'Variety', 'Hybrid']},
    #            },
    "leaf" : {"type": {"type": "text", "items": ['Simple', 'Compound', 'Phyllode']}, 
             "phyllotaxy": {"type": "text", "items": ['Alternate', 'Opposite', 'Verticillate']}, 
             "stipulate": {"type": 'boolean'}
             },
    "habit": {"epiphyte": {"type": 'boolean'},
                "herbaceous": {"type": 'boolean'},
                "liana": {"type": 'boolean'},
                "parasite": {"type": 'boolean'},
                "shrub": {"type": 'boolean'},
                "tree": {"type": 'boolean'}
             },
    "sexual": {"dioecious": {"type": 'boolean'},
                "hermaphrodite": {"type": 'boolean'},
                "fleshy fruit": {"type": 'boolean'}, 
                "dispersal unit": {"type": 'text', "items": ['Seed', 'Fruit']}
             },
    "architecture": {"model": {"type": 'text', "items": ['Attims','Aubreville','Chamberlain','Champagnat','Cook','Corner','Fagerlind','Holtum','Koriba','Leuwenberg','Mangenot','Massart','McClure','Nozeran','Petit','Prevost','Rauh','Roux','Scarrone','Schoute','Stone','Tomlinson','Troll']},
                    "monocaulous": {"type": 'boolean'},
                    "cauliflorous": {"type": 'boolean'}, 
                    "rythmic growth": {"type": 'boolean'}
             },
    "disperser": {"anemochory": {"type": 'boolean'}, 
                    "barochory": {"type": 'boolean'}, 
                    "entomochory": {"type": 'boolean'}, 
                    "ornitochory": {"type": 'boolean'}, 
                    "myrmecochory": {"type": 'boolean'}, 
                    "saurochory": {"type": 'boolean'},
                    "zoochorie": {"type": 'boolean'}
             },
    "new caledonia": {"status": {"type": 'text', "items": ['Endemic','Autochtonous','Introduced']}
     }
}

flower_reg_pattern = r'fl\.*|bt\.*|boutons?|cauliflor(e|a|ous)?|fert(?:ile|\.|)|fleurs?|inflorescences?|flowers?|buttons?|inflos?'
fruit_reg_pattern = r'fr\.*|figues?|fruits?|c[ôo]nes?|graines?|seeds?|figs?'


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
    
# def get_postgres_name(name):
#     #check and correct invalid characters to be compatible with fields and database typography of postgresql
#     name = re.sub(r'\W', '_', name.lower())
#     if name[0].isdigit():
#         name = '_' + name
#     name = name [:63]
#     return name

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

def get_str_value (value):
    """     
    Return the str value changing null values from database queries to Null string ('')
    """
    value = str(value).strip()
    if value.lower() not in ['null', 'none']:
        return value
    else:
        return ''



def get_dict_from_species(taxa: str):
    """
    Parse a botanical taxon name (species → infraspecies → hybrid)
    Returns a dict or None if the name is not a valid species-level taxon.
    """

    if not taxa or not taxa.strip():
        return None

    result = {
        'original_name': taxa,
        'genus': '',
        'species': '',
        'infraspecies': '',
        'rank': '',
        'prefix': '',
        'basename': '',
        'authors': '',
        'autonym': False,
        'name': '',
        'names': []
    }

    # --------------------------------------------------
    # 1. Normalisation
    # --------------------------------------------------
    norm_rules = {
        r'\bssp\.?\b': 'subsp.',
        r'\bsubsp\b': 'subsp.',
        r'\bvar\b': 'var.',
        r'\bforma\.?\b': 'f.',
    }

    for pat, rep in norm_rules.items():
        taxa = re.sub(pat, rep, taxa, flags=re.I)

    taxa = ' '.join(taxa.split())
    tokens = taxa.split()
    result['basename'] = tokens[0].lower()
    if len(tokens) < 2:
        return None

    # --------------------------------------------------
    # 2. Genus + species (hard requirement)
    # --------------------------------------------------
    result['rank'] = 'Species'
    genus, species = tokens[0], tokens[1]

    # Reject higher taxa or malformed epithets
    if re.search(r'[A-Z]', species):
        return None

    result['genus'] = genus.title()
    result['species'] = species.lower()
    result['basename'] = result['species']
    result['name'] = f"{result['genus']} {result['species']}"

    # --------------------------------------------------
    # 3. Rank detection
    # --------------------------------------------------
    rank_tokens = {
        'subsp.': 'Subspecies',
        'var.': 'Variety',
        'f.': 'Forma'
    }

    rank_index = None

    # Hybrid (x or ×) takes priority
    if 'x' in tokens[1:] or chr(215) in tokens:
        result['rank'] = 'Hybrid'
        result['prefix'] = 'x'
        try:
            x_index = tokens.index('x')
        except ValueError:
            x_index = tokens.index(chr(215))

        if x_index + 1 >= len(tokens):
            return None

        result['species'] = tokens[x_index + 1].lower()
        result['basename'] = result['species']
        result['name'] = f"{result['genus']} x {result['species']}"
        authors_start = x_index + 2

    else:
        authors_start = 2
        for t, r in rank_tokens.items():
            if t in tokens:
                rank_index = tokens.index(t)
                result['rank'] = r
                result['prefix'] = t
                break

        if rank_index is not None:
            if rank_index + 1 >= len(tokens):
                return None
            result['infraspecies'] = tokens[rank_index + 1].lower()
            result['basename'] = result['infraspecies']
            result['name'] += f" {result['prefix']} {result['infraspecies']}"
            authors_start = rank_index + 2

    # --------------------------------------------------
    # 4. Authors
    # --------------------------------------------------
    authors = ' '.join(tokens[authors_start:]).strip()

    if authors.lower() in {'sensu', 'ined', 'ined.', 'comb. ined.', 'comb ined'}:
        authors = ''

    result['authors'] = authors

    # --------------------------------------------------
    # 5. Autonym
    # --------------------------------------------------
    if result['infraspecies'] and result['infraspecies'] == result['species']:
        result['autonym'] = True
        result['authors'] = ''

    # --------------------------------------------------
    # 6. Generate all nomenclatural names
    # --------------------------------------------------
    base_name = f"{result['genus']} {result['species']}"

    if result['rank'] == 'Hybrid':
        base_name = f"{result['genus']} x {result['species']}"

    names = []

    if result['infraspecies']:
        n = f"{base_name} {result['prefix']} {result['infraspecies']}"
        names.append(n)
        if result['authors']:
            names.append(f"{n} {result['authors']}")
            if result['autonym']:
                names.append(
                    f"{base_name} {result['authors']} {result['prefix']} {result['infraspecies']}"
                )
    else:
        names.append(base_name)
        if result['authors']:
            names.append(f"{base_name} {result['authors']}")

    result['names'] = names

    return result










