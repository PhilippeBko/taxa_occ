import json
import re
from PyQt5 import  QtSql
from core import functions
import uuid


class DatabaseConnection:
    def __init__(self):
        self.db = None

    def open_from_config(self, config_path):
        import configparser
        config = configparser.ConfigParser()
        read_files = config.read(config_path)
        if not read_files:
            print(f"Warning, unable to read the config file : {config_path}")
            return False    

        section = 'postgresql'
        if section not in config.sections():
            print(f"Warning, section [{section}] not found in config file : {config_path}")
            return False
        
        return self.open(config['postgresql']['host'], 
                            config['postgresql']['user'], 
                            config['postgresql']['password'], 
                            config['postgresql']['database'])

    def open(self, host, user, password, database, port = 5432):
        if self.db:
            if self.db.isValid():
                self.db.close()
                del self.db
            #QtSql.QSqlDatabase.removeDatabase(conn_name)
        
        conn_name = "x-nomen" +str(uuid.uuid4())
        self.db = QtSql.QSqlDatabase.addDatabase("QPSQL", conn_name)
        self.db.setPort(port)
        self.db.setHostName(host)
        self.db.setUserName(user)
        self.db.setPassword(password)
        self.db.setDatabaseName(database)
        if self.db.open():
            return True
        else:
            self.db = None
            return False
    def close(self):
        if self.db:
            self.db.close()
            self.db = None
    def exec(self, sql):
        return self.db.exec(sql)

    def last_error(self):
        return self.db.lastError()

    def dbname(self):
        if self.db:
            return self.db.databaseName()
        return None
    
    def postgres_error(self):
        #convert the postgresl error in a text
        error = self.last_error()
        tab_text = error.text().split("\n")
        return '\n'.join(tab_text[:3])

#     def run_sql_scripts(self, db_name, host, user, password):
#         # Vérifier si le schema existe
#         sql_query = "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'taxonomy';"
#         query = self.db.exec(sql_query)
#         schema_exists = query.next()
#         if schema_exists:
#             return 

#     # Schema absent → exécuter les scripts
#         scripts = ['/home/birnbaum/Documents/Calédonie/sql/dbeaver/workspace6/data_occurrences/Scripts/taxa_occ/create_schema_taxonomy.sql',
#                    '/home/birnbaum/Documents/Calédonie/sql/dbeaver/workspace6/data_occurrences/Scripts/taxa_occ/config_schema_taxonomy.sql']
        
#         for script_path in scripts:
#             if not os.path.isfile(script_path):
#                 print (f"SQL File not found : {script_path}")

#             # send scripts to psql
#             cmd = [
#                 "psql",
#                 "-d", self.db.databaseName(),
#                 "-h", host,
#                 "-U", user,
#                 "-f", script_path
#             ]
#             try:
#                 # 
#                 subprocess.run(cmd, capture_output=True, text=True, check=True)
#                 #print(result.stdout)
#             except subprocess.CalledProcessError as e:
#                 print (f"Error in execution {script_path} : {e.stderr}")

#         return 
#     


    
class PN_dbTaxa:
#a subClass to manage the database of taxa (taxonomy schema), connexion with a DatabaseConnection (composition)
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.rank_typology = None
        self.ls_taxa_groups = None

#############################
   
    def field_dbase(self, fieldname, id_taxonref):
        """get a field value from the taxonomy.taxa_reference according to a id_taxonref"""
        sql_query = f"""
                    SELECT 
                        {fieldname} 
                    FROM
                        taxonomy.taxa_reference
                    WHERE
                        id_taxonref = {id_taxonref}
                   """
        #execute the query
        query = self.db.exec(sql_query)
        value = None
        if query.next():
            value = query.value(fieldname)

        query.finish()
        del query
        return value
    
    def db_execute_sql(self, sql_query, error_msg = True):
        #execute a sql query and return True or False if error
        result = self.db.exec(sql_query)
        return not result.lastError().isValid()
    
    def db_add_synonym(self, id_taxonref, synonym, category = 'Orthographic', error_msg = False):
        #add a synonym to a id_taxonref, return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_add ({id_taxonref}, '{synonym}', '{category}')"
        #execute the query
        return self.db_execute_sql(sql_query, error_msg)

    def db_edit_synonym(self, old_synonym, new_synonym, new_category = 'Orthographic'):
        #edit a synonym return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_update ('{old_synonym}','{new_synonym}', '{new_category}')"
        #execute the query
        return self.db_execute_sql(sql_query)

    def db_delete_synonym(self, synonym):
        #delete a synonym from the taxonomy.taxa_names table, return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_delete ('{synonym}')"
        #execute the query
        return self.db_execute_sql(sql_query)
    
    def db_update_properties (self, id_taxonref, json_properties):
        #update the properties json of a taxonref from a json string, return True or False if error
        if json_properties is None:
            json_properties = 'NULL'
        else:
            json_properties = json_properties.replace("'", "''")  # escape single quotes
            json_properties = f"'{json_properties}'::jsonb"
        sql_query = f"""UPDATE taxonomy.taxa_reference 
                        SET properties = {json_properties}
                        WHERE id_taxonref = {id_taxonref} 
                        AND id_rank >= 21;
                    """
        #execute the query
        return self.db_execute_sql(sql_query)
    
    def db_update_metadata (self, id_taxonref, json_metadata):
        #return sql statement to update the metadata json of a taxonref
        if json_metadata is None:
            json_metadata = 'NULL'
        else:
            json_metadata = json_metadata.replace("'", "''")  # escape single quotes
            json_metadata = f"'{json_metadata}'::jsonb"
        sql_query = f"""UPDATE taxonomy.taxa_reference 
                        SET metadata = {json_metadata}
                        WHERE id_taxonref = {id_taxonref};
                    """
        #execute the query
        return self.db_execute_sql(sql_query)
    
    def db_merge_reference (self, from_idtaxonref, to_idtaxonref, category='Orthographic'):
        #set two taxa as synonyms
        if to_idtaxonref == from_idtaxonref:
            return False
        sql_query = f"CALL taxonomy.pn_taxa_set_synonymy({from_idtaxonref}, {to_idtaxonref}, '{category}');"
        #execute the query
        return self.db_execute_sql(sql_query)
    


##############################
    def db_get_rank(self, key, field = None):
    #set the global dictionnary of rank typology if not exists and returns the dictionnary of a rank from its id_rank or rank_name
    
    #create a query to copy the table taxonomy.taxa_rank in a dictionnary
        if self.rank_typology is None:
            sql_query = """
                SELECT id_rank, rank_name, row_to_json(t) json_row 
                FROM 
                    (SELECT id_rank, rank_name, id_rankparent, suffix, prefix, childs
                    FROM taxonomy.taxa_rank a,
                    LATERAL 
                        (SELECT
                            to_json(array_agg(id_rank)) AS childs
                        FROM
                            taxonomy.pn_ranks_children(a.id_rank) b
                        ) z
                    ) t
                ORDER BY 
                    id_rank
            """
        #execute the query
            query = self.db.exec(sql_query)
            self.rank_typology = {}
        #fill the dictionnary with a both entries: id_rank and rank_name as key
            while query.next():
                self.rank_typology[query.value("id_rank")] = json.loads(query.value("json_row"))
                self.rank_typology[query.value("rank_name")] = json.loads(query.value("json_row"))

            query.finish()
            del query
    
    #return for the rank (key), the dictionnary and field value if field is not None
        if key in self.rank_typology:
            if field is None:
                return self.rank_typology[key].copy()
            else:
                return self.rank_typology[key][field]
        return None
    
    def db_get_searchnames (self, ls_search_name):
        """return a dictionnary {"name": id_taxonref} of names founded into the database from a list of names (ls_search_name)
            #ex: return {"Amborella": 300, "Amborella trichopoda": 1802}
            from a the list ['Amborella', 'Amborella trichopoda', 'Miconia foo']
        """
        sql_query = f"""
                    SELECT 
                        jsonb_object_agg(original_name, id_taxonref)
                    FROM 
                        taxonomy.pn_taxa_searchnames(ARRAY{ls_search_name})
                    WHERE 
                        id_taxonref IS NOT NULL;
                    """
        #execute the query
        query = self.db.exec(sql_query)
        json_list ={}
        if query.next():
            result = query.value(0)
            if result:
                json_list = json.loads(result)
        query.finish() 
        del query
        return json_list
    
    def db_get_fuzzynames(self, search_name, score = 0.4):
        """return a dictionnary where key = taxonref and value = a dictionnary (id_taxonref, score,  synonyms: List[str])
            #ex: {'Amborella trichopoda Baill.': {"id_taxonref": 1802, "score": 0.95, "synonym": ['Amborella trichopodo', 'Amborella']}, ...}
        """
        if len(search_name) < 4:
            return
        if len(search_name) < 8:
            score = 0.2
        #create sql query
        sql_query = f"""
            SELECT 
                a.taxonref, a.score, a.id_taxonref, json_agg(DISTINCT c.name ORDER BY c.name) AS synonym
            FROM 
                taxonomy.pn_taxa_searchname('{search_name}', {score}::numeric) a 
            LEFT JOIN 
                taxonomy.taxa_nameset c 
            ON 
                a.id_taxonref = c.id_taxonref AND c.category <> 1
            GROUP BY a.taxonref, a.score, a.id_taxonref
            ORDER 
                BY score DESC
        """
        #execute sql_query and return json result
        query = self.db.exec(sql_query)
        dict_db_names = {}
        while query.next():
            dict_db_names[query.value("taxonref")] = {
                "id_taxonref": query.value("id_taxonref"),
                "score": query.value("score"),
                "synonym": json.loads(query.value("synonym"))
            }
        query.finish()
        del query
        return dict_db_names

       
    def db_get_valid_merges (self, id_taxonref):
        """return a dictionnary {"name": id_taxonref} of valid sibling for merging taxa based on the id_rank
            #ex: return {'Acorales': 17056, 'Alismatales': 17057, 'Amborellales': 16183,...}
            when searching for a order
        """
        sql_query = f"""
                    SELECT
                    n.taxaname, n.id_taxonref
                    FROM taxonomy.taxa_names n
                    JOIN taxonomy.taxa_reference r ON r.id_taxonref = {id_taxonref}
                    WHERE
                        (r.id_rank < 21 AND n.id_rank = r.id_rank)
                        OR
                        (r.id_rank >= 21 AND n.id_rank >= 21)
                    ORDER BY n.taxaname;
                    """
        #execute the query
        query = self.db.exec(sql_query)
        taxa_dict = {}
        while query.next():
            taxa_dict[query.value(0)] = query.value(1)
        query.finish()  
        del query
        return taxa_dict
    
    def db_get_valid_parents (self, id_taxonref):
        """return a dictionnary {"name": id_taxonref} of valid parents for id_taxonref based on the id_rank
            #ex: return {'Acorales': 17056, 'Alismatales': 17057, 'Amborellales': 16183,...}
            when searching for a family
        """
        sql_query = f"""
                SELECT
                n.taxaname,                 n.id_taxonref
                FROM taxonomy.taxa_names n
                JOIN taxonomy.taxa_reference r ON r.id_taxonref = {id_taxonref}
                JOIN taxonomy.taxa_rank tr ON r.id_rank = tr.id_rank
                WHERE
                    n.id_rank >= tr.id_rankparent
                AND n.id_rank < tr.id_rank
                ORDER BY n.taxaname;
                """
        #execute the query
        query = self.db.exec(sql_query)
        taxa_dict = {}
        while query.next():
            taxa_dict[query.value(0)] = query.value(1)
        query.finish()  
        del query
        return taxa_dict


    
    def db_get_names(self, id_taxonref):
        """return a dictionnary of list of all the names linked to a id_taxonref and organized by categories
            #ex: {'Autonyms': ['Amborella trichopoda Baill.', 'Amborella trichopoda'], 'Nomenclatural': ['Platyspermation crassifolium', 'Platyspermation crassifolium Guillaumin']}
        """
        sql_query = f"""
                    SELECT 
                        a.name,  a.category, a.id_category 
                    FROM 
                        taxonomy.pn_names_items({id_taxonref}) a 
                    ORDER BY 
                        a.id_category, a.name
                    """
        #execute the query
        query = self.db.exec(sql_query)
        dict_db_names = {'Autonyms': []} #to ensure the first row
        while query.next():
            #groups any name by category
            if query.value("id_category") < 5:
                _category = 'Autonyms'
            else:
                _category = query.value("category")
            #add category to the final result if not exists
            if _category not in dict_db_names:
                dict_db_names[_category] = []
            dict_db_names[_category].append(query.value("name"))
        query.finish()
        del query
        return dict_db_names
    
    def db_get_apg4_clades (self):
        #return the list of distinct clades from the apg4 table (field clade), [] if nothing
        #typically ['ANA Grade', 'Ceratophyllales', 'Chloranthales', 'Core Eudicots', 'Magnoliids', 'Monocots']
        #sql_query = "SELECT json_agg(DISTINCT a.group_taxa) AS json_list FROM taxonomy.wfo_order a WHERE a.group_taxa IS NOT NULL;"
        if self.ls_taxa_groups:
            return self.ls_taxa_groups
        sql_query = """
                    SELECT clade
                    FROM
                        (SELECT clade_apg AS clade, 1 AS orderby FROM taxonomy.taxa_wfo
                            UNION
                         SELECT group_taxa AS clade, 0 AS orderby FROM taxonomy.taxa_wfo
                        )
                    WHERE clade IS NOT NULL
                    ORDER BY orderby, clade;
                    """
        #execute the query
        query = self.db.exec(sql_query)
        json_list = []
        while query.next():
            json_list.append(query.value("clade"))
        query.finish()
        del query
        #save the list of distinct clades (re-use without querying database)
        self.ls_taxa_groups = json_list
        return json_list
    
    def db_get_taxa_wfo(self, basename = None):
        #return the list of children from taxonomy.taxa_wfo, each item is a dictoinnary(id, taxaname, authors, rank, id_parent)
        table_taxa = []
        # sql_query = f"""WITH RECURSIVE tree AS (
        #                     -- anchor
        #                     SELECT
        #                         t.id_taxonref,
        #                         t.id_parent,
        #                         t.id_rank,
        #                         t.basename,
        #                         t.authors
        #                     FROM taxonomy.taxa_wfo t
        #                     --WHERE t.basename = '{basename}'
        #                     --WHERE t.group_taxa = 'Bryophytes'

        #                     UNION 

        #                     -- recursivity
        #                     SELECT
        #                         c.id_taxonref,
        #                         c.id_parent,
        #                         c.id_rank,
        #                         c.basename,
        #                         c.authors
        #                     FROM taxonomy.taxa_wfo c
        #                     JOIN tree p ON c.id_parent = p.id_taxonref
        #                 )

        #                 SELECT id_taxonref, INITCAP(basename) basename,  authors, rank_name, id_parent
        #                 FROM tree a
        #                 INNER JOIN taxonomy.taxa_rank c ON a.id_rank = c.id_rank 
        #                 ORDER BY a.id_rank, basename;	
        #                 """
        sql_where = ''
        if basename:
            basename = basename.strip().lower()
            #sql_where = f"""WHERE lower(t.basename) = '{basename}' OR lower(t.group_taxa) = '{basename}' OR lower(t.clade_apg) ='{basename}'"""
            sql_where = f"""WHERE '{basename}' IN (lower(t.basename), lower(t.group_taxa), lower(t.clade_apg))"""
        sql_query = f"""WITH RECURSIVE
                        anchor AS (
                            SELECT
                                t.id_taxonref,
                                t.id_parent,
                                t.id_rank,
                                t.basename,
                                t.authors
                            FROM taxonomy.taxa_wfo t
                            {sql_where}
                        ),
                        children AS (
                            SELECT * FROM anchor
                            UNION ALL
                            SELECT
                                c.id_taxonref,
                                c.id_parent,
                                c.id_rank,
                                c.basename,
                                c.authors
                            FROM taxonomy.taxa_wfo c
                            JOIN children p ON c.id_parent = p.id_taxonref
                        ),
                        parents AS (
                            SELECT * FROM anchor
                            UNION ALL
                            SELECT
                                c.id_taxonref,
                                c.id_parent,
                                c.id_rank,
                                c.basename,
                                c.authors
                            FROM taxonomy.taxa_wfo c
                            JOIN parents p ON p.id_parent = c.id_taxonref
                        ),
                        hierarchical AS (
                            SELECT * FROM children
                            UNION 
                            SELECT * FROM parents
                        )

                        SELECT a.id_taxonref as id, a.id_parent, a.id_rank, a.basename, a.authors, b.basename AS parentname, d.id_taxonref
                        FROM hierarchical a
                        LEFT JOIN hierarchical b ON a.id_parent = b.id_taxonref
                        LEFT JOIN taxonomy.taxa_reference d ON lower(a.basename) =  d.basename
                        ORDER BY a.id_rank; """
        
        query = functions.db().exec(sql_query)
        while query.next():
            item = {
                "id": query.value("id"),
                "id_taxonref": query.value("id_taxonref"),
                "id_rank" : query.value("id_rank"),
                "id_parent": query.value("id_parent"),
                "taxaname": query.value("basename").title(),
                "basename": query.value("basename"),
                "parentname": query.value("parentname"),
                "authors": query.value("authors"),
                "rank": functions.dbtaxa().db_get_rank(query.value("id_rank"), "rank_name"),
                "published" : True,
                "accepted" : True,
                "autonym" : False
            }
            table_taxa.append(item)
        return table_taxa

    def db_get_json_taxa(self, grouped_idrank, dict_filter = None):
        """
            return a list of dictionnaries (dict_taxa) with taxaname infos from the database as
                [{"id_taxonref":integer, "id_parent":integer, "id_rank" :integer, "taxaname":text, "authors":text, "published":boolean, "accepted":boolean, 
                "taxaname_score":numeric, "authors_score":numeric"}, ...]
            apply a filter on the query
                dict_filter = {"id_taxonref" : integer, "search_name": text, "clade": text[None], "properties": dictionnary, "refresh": boolean[False]}
                where :
                refresh -> only return childs of idtaxonref impacted by a name change (avoid refresh all childs of a rank but only those linked by name combination)
                properties -> a dictionnary as in properties field (cf. list_db_properties)
        """
        sql_where_taxa = ''
        tab_sql = ["id_rank >= 21"]
        nb_filter = 0
        base_taxa = 'all_taxa'
        #sql_from_taxa = "taxonomy.taxa_reference"
        sql_inner_join_taxa =''

        if dict_filter:
        #1) text filter: sql_where_taxa from the lineEdit_search
            txt_search = dict_filter.get("search_name", '')
            if len(txt_search) > 0:
                text_search = re.sub(r'[\*\%]', '', txt_search)
                #return a sql statement for searching taxanames
                #sql_taxa_searchNames = f"SELECT id_taxonref FROM taxonomy.pn_taxa_searchname ('%{text_search}%')"

                sql_where_taxa = f"""\na.id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_searchname ('%{text_search}%'))"""
                tab_sql.append(sql_where_taxa)
                nb_filter = 1
                
            #2) properties filter: sql_where_taxa from the PN_trview_filter (get the dict_user properties=
            tab_properties = dict_filter.get("properties", {})
            for key, value in tab_properties.items():
                for key2, value2 in value.items():
                    if value2:
                        _prop = "(properties  @> '{%key%:{%key2%:%value%}}')"
                        _prop = _prop.replace('%', chr(34))
                        _prop = _prop.replace('key2', key2)
                        _prop = _prop.replace('key', key)
                        _prop = _prop.replace('value', value2)
                        tab_sql.append(_prop)
                        nb_filter += 1
            #3) set the id_taxonref
            idtaxonref = dict_filter.get("id_taxonref", 0)
            if idtaxonref >0:
                _refresh = False #dict_filter.get("refresh", False)
                #sql_inner_join_taxa = f"INNER JOIN taxonomy.pn_taxa_childs ({idtaxonref},True, {_refresh}) z ON z.id_taxonref = a.id_taxonref"
                #tab_sql.append (f"a.id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs ({idtaxonref},True, {_refresh}))")
                sql_inner_join_taxa = f"""INNER JOIN 
                                        (SELECT id_taxonref FROM taxonomy.pn_taxa_childs ({idtaxonref},True)
                                        UNION
	                                    SELECT id_taxonref FROM taxonomy.pn_taxa_parents ({idtaxonref},False)
                                        ) z ON a.id_taxonref = z.id_taxonref"""
                    
            #4) APG Filter: add a filter for APG clade
            clade_sql = dict_filter.get("clade", None)
            if clade_sql:
                base_taxa = 'apg_taxa'
            dict_filter["nb_filter"] = nb_filter
        
        #5) create query: set the final sql_query, including sql_where_taxa and sql_join
        sql_where_taxa = f" WHERE id_rank = {grouped_idrank} OR (" + " AND ".join(tab_sql) + ")"
        #sql_where_taxa += f" OR id_rank = {idrankparent}"
        sql_query = f"""
        WITH 
            order_apg AS 
                (SELECT DISTINCT
                    b.id_taxonref AS id_order,
                    taxonomy.pn_taxa_getparent(b.id_taxonref, {grouped_idrank}) AS id_parent --to change
                FROM taxonomy.taxa_wfo a
                INNER JOIN taxonomy.taxa_reference b ON lower(a.basename) = b.basename
                WHERE b.id_rank = 8 
                AND a.group_taxa = '{clade_sql}'
                OR a.clade_apg = '{clade_sql}'
                ),
            all_taxa AS            
                (SELECT a.id_taxonref, id_rank,
                	CASE WHEN id_rank >=21 THEN taxonomy.pn_taxa_getparent(a.id_taxonref, {grouped_idrank})
                	     ELSE id_parent
                	END
                	AS id_parent
                    FROM taxonomy.taxa_reference a
                    {sql_inner_join_taxa}
                    {sql_where_taxa}
                ),
            apg_taxa AS
                (SELECT DISTINCT a.id_taxonref, a.id_parent, a.id_rank
                    FROM all_taxa a
                    LEFT JOIN order_apg b ON a.id_taxonref = b.id_parent
                    LEFT JOIN order_apg c ON taxonomy.pn_taxa_getparent(a.id_taxonref, 8) = c.id_order
                    WHERE c.id_order IS NOT NULL OR b.id_parent IS NOT NULL
                ),
            score_taxa AS 
                (SELECT 
                    a.id_taxonref, b.id_parent, a.id_rank,
                    a.taxaname, a.authors, a.published, a.accepted,
                    (a.metadata->'score'->>'taxaname_score')::numeric AS taxaname_score,
                    (a.metadata->'score'->>'authors_score')::numeric AS authors_score
                    FROM {base_taxa} b
                    INNER JOIN taxonomy.taxa_names a ON a.id_taxonref = b.id_taxonref
                    ORDER BY taxaname
                    )
            SELECT json_agg(row_to_json(score_taxa)) FROM score_taxa;
        """
        #execute the query
        result = self.db.exec (sql_query)
        json_list = [] #if no result, return empty json_list 
        if result.next():
            json_text = result.value(0)
            if json_text:
                json_list = json.loads(json_text)

        result.finish()
        del result
        return json_list

#############################
    def db_get_taxon(self, id_taxonref):
        """return a json with basic taxa fields from id_taxonref in taxa_reference"""
        sql_query = f"""
                    SELECT 
                        taxaname, authors, id_rank, published, accepted, id_parent 
                    FROM
                        taxonomy.taxa_names
                    WHERE
                        id_taxonref = {id_taxonref}
                   """
        #execute the query
        query = self.db.exec(sql_query)
        json_taxa = {}
        if query.next():
            json_taxa = {
                "id_taxonref": id_taxonref,
                "id_parent": query.value("id_parent"),
                "id_rank": query.value("id_rank"),
                "taxaname": query.value("taxaname"),
                "authors": query.value("authors"),
                "published": query.value("published"),
                "accepted": query.value("accepted")
            }
        query.finish()
        del query
        return json_taxa

#############################
    def db_get_list_hierarchy(self, id_taxonref, id_rank = None):
        """return a json with hierarchy from Plantae to Childs of a id_taxonref"""
        # Get the hierarchy for the selected taxa
        try:
            if id_taxonref * id_rank == 0:
                return
        except Exception:
            return
        str_idtaxonref = str(id_taxonref)
        #sql_where = ''
        # extend to all taxa included in the genus when id_rank > genus (e.g. for species return all sibling species within the genus)
        #or in other words, set to the genus rank when id_rank > genus
        if id_rank > 14: #get the genus rank at minimum
            str_idtaxonref = f"""(SELECT * FROM taxonomy.pn_taxa_getparent({str_idtaxonref},14))"""

        # sql_where = ''
        # create the SQL query to get the hierarchy of taxa
        sql_query = f"""SELECT 
                            b.id_taxonref, id_rank, id_parent, taxaname,  authors, published, accepted
                            FROM
                                (SELECT 
                                    id_taxonref
                                FROM    
                                    taxonomy.pn_taxa_parents({str_idtaxonref}, True)
                                UNION 
                                SELECT 
                                    id_taxonref
                                FROM 
                                    taxonomy.pn_taxa_childs({str_idtaxonref}, False)
                                ) a
                            INNER JOIN 
                                taxonomy.taxa_names b 
                            ON 
                                a.id_taxonref = b.id_taxonref
                        ORDER BY 
                            id_rank, taxaname;
                    """
        # execute the Query and fill the list_hierarchy of dictionnary
        query = self.db.exec(sql_query)
        #set the taxon to the hierarchical model rank = taxon
        ls_hierarchy = []
        while query.next():
            ls_hierarchy.append({
                "id_taxonref": query.value('id_taxonref'), 
                "id_parent": query.value('id_parent'), 
                "id_rank" : query.value('id_rank'), 
                "taxaname": query.value('taxaname').strip(), 
                "authors": query.value('authors').strip(), 
                "published": query.value('published'), 
                "accepted": query.value('accepted')
                }
            )
        query.finish()
        del query   
        return ls_hierarchy
    
    def db_get_properties (self, id_taxonref):
        """     
        Return a json (dictionnary of sub-dictionnaries of taxa properties taxa identity + field properties (jsonb)
        from a PNTaxa class
        """
        dict_db_properties = {}
        #create a copy of dict_properties with empty values
        for _key, _value in functions.list_db_properties.copy().items():
            dict_db_properties[_key] = {}.fromkeys(_value,'')
        #fill the properties from the json field properties annexed to the taxa        
        try:
            json_props = self.field_dbase("properties", id_taxonref)
            json_props = json.loads(json_props)
            for _key, _value in dict_db_properties.items():
                try:
                    tab_inbase = json_props[_key]
                    if tab_inbase is not None:
                        for _key2, _value2 in tab_inbase.items():
                            #_value2 = functions.get_str_value(_value2)
                            if _value2:
                                _value[_key2] = _value2.title()
                except Exception:
                    continue
        except Exception:
            pass
        return dict_db_properties

    def db_get_properties_count (self, id_taxonref):
        #load all the similar names of the taxa to a json dictionnary
        sql_query = f"""
            WITH childs_taxaname AS 
                (
                    SELECT b.id_taxonref, b.properties 
                    FROM 
                    taxonomy.pn_taxa_childs({id_taxonref}) a
                    INNER JOIN taxonomy.taxa_reference b ON a.id_taxonref = b.id_taxonref
                    WHERE b.id_rank >=21
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
        #execute the query
        query = self.db.exec(sql_query)
        query.next()
        json_props = query.value("json_result")
        if json_props:
            json_props = json.loads(json_props)
        else:
            json_props = None
        query.finish()        
        del query
        return json_props



    
    def db_get_metadata (self, id_taxonref):
        #load metadata json from database
        json_data = self.field_dbase("metadata", id_taxonref)
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


    

    
    def db_delete_reference(self, id_taxonref):
        #delete a reference in the taxonomy.taxa_reference table
        # #return the list of id_taxonref deleted (including childs) or []
        ls_todelete = []
        #get the childs that will be deleted through foreign keys
        #sql_query = self.sql_taxa_get_childs(id_taxonref, True)
        sql_query = f"SELECT id_taxonref FROM taxonomy.pn_taxa_childs ({id_taxonref}, True)"
        result = self.db.exec(sql_query)
        if not result.lastError().isValid():
            while result.next():
                ls_todelete.append(result.value("id_taxonref"))
        # delete the id_taxonref (and childs through integrity constraints)
        if ls_todelete:
            sql_query = f"SELECT taxonomy.pn_taxa_delete ({id_taxonref}) AS id_taxonref"
            result = self.db.exec(sql_query)
            if not result.lastError().isValid():
                return ls_todelete
        return []
    
    def db_save_dict_taxa(self, dict_tosave):
        #save a taxa dictionnary in the database, return id_taxonref (new or updated) or None if error
        #dict_tosave = {"id_taxonref":integer, "id_parent":integer, "id_rank" :integer, "basename":text, "authors":text, "parentname":text[None], "published":boolean, "accepted":boolean}
        #code_error = ''
        return_idtaxonref = None
        idtaxonref = dict_tosave.get("id_taxonref", None)
        if idtaxonref is None:
            return None
        
        basename = dict_tosave.get("basename", None)
        if basename:
            basename = basename.strip().lower()
        else:
            return None
        #test for the types of update (according to specific fields parentname or id_parent)
        _parentname = dict_tosave.get("parentname", None)
        _idparent = dict_tosave.get("id_parent", None)
        published = dict_tosave.get("published", None)
        accepted = dict_tosave.get("accepted", None)
        authors = dict_tosave.get("authors", "").strip()
        authors = authors.replace("'", "''")  # escape single quotes
        idrank = dict_tosave.get("id_rank", None)

    #create the from_query depending if parentname/id_parent are present into the dictionnayr dict_tosave
    # if idtaxonref = 0 the function taxonomy.pn_taxa_edit will add a new taxonref, else edit the idtaxonref
        if _parentname:# get the id_parent from the parentname
            _parentname = _parentname.strip().lower() #.replace(' ', '')
            sql_update = f"""(SELECT 
                                taxonomy.pn_taxa_edit ({idtaxonref}, '{basename}', '{authors}', taxa.id_parent, {idrank}, {published},{accepted}) AS id_taxonref 
                            FROM
                                (SELECT 
                                    a.id_taxonref AS id_parent
                                FROM
                                    taxonomy.taxa_nameset a
                                WHERE 
                                    lower(a.name) = '{_parentname}'
                                ) taxa
                            )
                        """
        elif _idparent:
            sql_update = f"""SELECT 
                                taxonomy.pn_taxa_edit ({idtaxonref}, '{basename}', '{authors}', {_idparent}, {idrank}, {published},{accepted}) AS id_taxonref"""
        else:
            return
        
    #1 - execute the sql_update and get the id_taxonref (update or add), if no error 
        sql_update = sql_update.replace("None", "NULL")
        #print (sql_update)
        result = self.db.exec (sql_update)
        #code_error = result.lastError().nativeErrorCode()

        #if no errors, return the id_taxonref
        # if result.lastError().isValid():
        #     msg = self.db().postgres_error()
        #     self.critical_msgbox ("Database error", msg)
        # el
        if result.next():
            return_idtaxonref = result.value("id_taxonref")    
        return return_idtaxonref
    

