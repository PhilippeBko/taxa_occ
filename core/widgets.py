# Standard library
import json
import os
import re
import subprocess
import webbrowser

# Third-party
from PyQt5 import QtGui, QtSql, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QEvent

# Internal
from core import functions




##class LinkDelegate to create hyperlink of the QTreeView from Qtreeview_Json
class LinkDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()
        # check for an internet hyperlink
        if text and text.startswith("http"):
            # draw text in blue when its an hyperlink
            painter.save()
            painter.setPen(QtGui.QColor(100, 149, 237))  # (Cornflower Blue)
            painter.drawText(option.rect, Qt.AlignLeft, text)
            painter.restore()
        else:
            # draw text normally
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        text = index.data()
        # change the cursor if cell is an internet hyperlink and open the link if clicked
        if text and text.startswith("http"):
            if event.type() == event.MouseMove:
                QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.PointingHandCursor))
            elif event.type() == event.MouseButtonRelease:
                webbrowser.open(text)
                return True
            elif event.type() == QEvent.Leave:
                QtWidgets.QApplication.restoreOverrideCursor()
        else:
            # Restore the default cursor
            QtWidgets.QApplication.restoreOverrideCursor()
        return super().editorEvent(event, model, option, index)

#Class Qtreeview_Json to fill a QTreeView with a json 
class PN_JsonQTreeView(QtWidgets.QTreeView):
    """
    A custom QTreeView widget that displays data from a JSON object.
    ex: json_data = {'identity': {'name': 'acacia', 'authors': 'Mill.', 'published': 'True', 'accepted': 'True'}, 'habit': {'epiphyte': '' ....and so on

    Args:
        checkable (bool, optional): Whether the first column is checkable. Defaults to False.
        list_inRows (bool, optional): Whether lists are displayed in rows. Defaults to False.
        header (list, optional): A list of column headers to display. Defaults to None.

    Attributes:
        changed_signal (pyqtSignal): A signal emitted when the data in the tree view is changed.

    Methods:
        refresh(): Refreshes the tree view with the current data.
        setData(json_data): Sets the data in the tree view from a JSON object.
        dict_user_properties(): Retrieves the data from the tree view and returns it as a dictionary.
        dict_db_properties(): A dictionary containing the original json_data receive in the setdata() methods.
        _validate(): Compares the original data with the current data in the tree view and emits a signal if they are different.
    """
    changed_signal  = pyqtSignal(bool)
    def __init__(self, checkable = False, list_inRows = False, header = None):
        super().__init__()
        self.tab_header = header
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        # if header is None:
        #     self.header().hide()
        self.dict_db_properties = {}
        self.id = None
        self.checkable = checkable
        link_delegate = LinkDelegate()
        self.setItemDelegate(link_delegate)
        self.list_inRows = list_inRows
        self.header().setDefaultAlignment(Qt.AlignCenter)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    # def clear (self):
    #     model = QtGui.QStandardItemModel()
    #     self.setModel(model)

    def refresh(self):
        self.setData(self.dict_db_properties)

    def setData(self, json_data = None):
    #set the json_data into the treeview model
        def _set_dict_properties (item_base, _dict_item):
        #internal function to set recursively add the data into the treeview model
            if _dict_item is None : 
                return
            for _key, _value in _dict_item.items():
                _key = _key[0].upper() + _key[1:]
                item_key = QtGui.QStandardItem(str(_key))
                item_value = QtGui.QStandardItem(None)
                if type(_value) is dict:
                    item_base.appendRow([item_key, item_value],)
                    _set_dict_properties(item_key, _value)
                elif type(_value) is list:
                    item_key.setCheckable(self.checkable)
                    if self.list_inRows:
                        ls_items = [item_key]
                        for val in _value:
                            item = QtGui.QStandardItem(str(val))
                            item.setTextAlignment(Qt.AlignCenter)
                            ls_items.append(item)
                        item_base.appendRow(ls_items)
                    else:
                        dict_key = {}
                        i = 1
                        for val in _value:
                            item_value = QtGui.QStandardItem(str(val))
                            if _key in dict_key:
                                itemkey = dict_key[_key]
                            else:
                                itemkey = QtGui.QStandardItem(str(_key))
                                item_base.appendRow([itemkey, None],)
                                dict_key[_key] = itemkey
                            itemkey.appendRow([item_value])
                            i += 1
                else:
                    item_value = QtGui.QStandardItem(str(_value))
                    item_base.appendRow([item_key, item_value],)


    #main part of the function
    # set the treeview widget model values
        self.model().clear()
        if not json_data: 
            return
        try:
            #disconnect the changed event to avoid multiple validation processes
            self.model().dataChanged.disconnect(self._validate)
        except Exception:
            pass
        #add nodes to treeview from dict_db_properties
        _set_dict_properties (self.model(), json_data)
        self.dict_db_properties = json_data
    #ajust header
        header = self.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        if self.tab_header:
            self.header().show()
            self.model().setHorizontalHeaderLabels(self.tab_header)
            for col in range(1, self.model().columnCount()):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        else:
            self.header().hide()
    ##validate and expand the treeview
        self._validate()
        self.expandAll()
    ##connect the changed event to validate the data
        self.model().dataChanged.connect(self._validate)

    def dict_user_properties(self, item_base = None):
    #get the json_data from the treeview model (with changed values)
        tab_value = {}
        if item_base is None:
            item_base = self.model()
        if item_base is None:
            return tab_value
        for i in range(item_base.rowCount()):
            item = item_base.item(i) ##.data(0)
            if item is None: 
                continue
            key = item.data(0).lower()
            tab_tmp = {}
            for a in range (item.rowCount()):
                _key = item.child(a).data(0).lower()
                _value = item.child(a).index().siblingAtColumn(1).data(0)
                tab_tmp[_key] = _value
            if len(tab_tmp) > 0:
                tab_value[key] = tab_tmp
        return (tab_value)

    def changed (self):
    #test the equality between the db and user tab properties
        return (self.dict_db_properties != self.dict_user_properties())

    def _validate(self, index = None):
    #test if changed, underline column 0 for changed value and emit a signal
        if index is not None:
            font = QtGui.QFont()
            _bold = False
            try:
                field_table = index.parent().data(0).lower()
                field_name = index.siblingAtColumn(0).data().lower()
                field_value = index.siblingAtColumn(1).data()
                _bold = (field_value != self.dict_db_properties[field_table][field_name])
            except Exception:
                pass
            font.setUnderline(_bold)
            self.model().setData(index.siblingAtColumn(0), font, Qt.FontRole)
        self.changed_signal.emit(self.changed())

class PN_DatabaseConnect(QtWidgets.QWidget):
    """
    A custom widget for displaying the status of a database connection.

    The widget consists of a status indicator (a red or green circle) and a label indicating the connection status.
    The database connection is established using parameters stored in a `config.ini` configuration file.

    Attributes:
        dbopen (bool): Indicates whether the database connection is open.
        statusIndicator (QtWidgets.QWidget): The connection status indicator.
        statusConnection (QtWidgets.QLabel): The label indicating the connection status.

    Methods:
        open(): Opens the database connection using the parameters from the configuration file.
    """
    # ... (the class code remains unchanged):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dbopen = False
        self.db = None
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("background-color: transparent;")
        self.statusIndicator = QtWidgets.QWidget(frame)
        self.statusIndicator.setFixedSize(10, 10)
        self.statusIndicator.setStyleSheet("background-color: rgb(255, 0, 0); border-radius: 5px;")
        self.statusConnection = QtWidgets.QLabel(None, frame)
        self.statusConnection.setText("Not Connected")
        self.statusConnection.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        frame_layout = QtWidgets.QHBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        frame_layout.addWidget(self.statusIndicator)
        frame_layout.addWidget(self.statusConnection)
        self.setLayout(frame_layout)
    
    def open(self, db_name=''):
        import configparser
        config = configparser.ConfigParser()
        config_file = functions.resource_path("config.ini")
        read_files = config.read(config_file)

        if not read_files:
            print(f"Warning, unable to read the config file : {config_file}")
            return False
    

        section = 'database'
        if section not in config.sections():
            print(f"Warning, section [{section}] not found in config file : {config_file}")
            return False

        if config.has_option(section, 'host') and config.has_option(section, 'user') and config.has_option(section, 'password') and config.has_option(section, 'database'):
            self.db = QtSql.QSqlDatabase.addDatabase("QPSQL") #, db_name)

            self.db.setHostName(config['database']['host'])
            self.db.setUserName(config['database']['user'])
            self.db.setPassword(config['database']['password'])
            self.db.setDatabaseName(config['database']['database'])
            if self.db.open():
                self.dbopen = True
                default_db_name = self.db.databaseName()
                host_name = self.db.hostName()
                user_name = self.db.userName()
                password = self.db.password()
                if default_db_name:
                    self.statusIndicator.setStyleSheet("background-color: rgb(0, 255, 0); border-radius: 5px;")
                    self.statusConnection.setText("Connected : "+ default_db_name)
                    self.run_sql_scripts(default_db_name, host_name, user_name, password)
            else:
                self.db.close()
                self.db = None
    
    def db_get_searchname(self, search_name, score = 0.4):
    #this function Taxa is set in the PN_DatabaseConnect class to be shared between subclasses
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
        return dict_db_names

    def run_sql_scripts(self, db_name, host, user, password):
        # Vérifier si le schema existe
        sql_query = "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'taxonomy';"
        query = self.db.exec(sql_query)
        schema_exists = query.next()
        if schema_exists:
            return 

    # Schema absent → exécuter les scripts
        scripts = ['/home/birnbaum/Documents/Calédonie/sql/dbeaver/workspace6/data_occurrences/Scripts/taxa_occ/create_schema_taxonomy.sql',
                   '/home/birnbaum/Documents/Calédonie/sql/dbeaver/workspace6/data_occurrences/Scripts/taxa_occ/config_schema_taxonomy.sql']
        
        for script_path in scripts:
            if not os.path.isfile(script_path):
                print (f"SQL File not found : {script_path}")

            # send scripts to psql
            cmd = [
                "psql",
                "-d", self.db.databaseName(),
                "-h", host,
                "-U", user,
                "-f", script_path
            ]
            try:
                # 
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                #print(result.stdout)
            except subprocess.CalledProcessError as e:
                print (f"Error in execution {script_path} : {e.stderr}")

        return 


    def postgres_error(self, error):
        #convert the postgresl error in a text
        tab_text = error.text().split("\n")
        return '\n'.join(tab_text[:3])
    
class PN_dbTaxa(PN_DatabaseConnect):
#a subClass to manage the database of taxa (taxonomy schema), inherit from PN_DatabaseConnect
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rank_typology = None
        #self.db = None

    def dict_rank_value(self, key, field = None):
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
        #return for the rank (key), the dictionnary and field value if field is not None
        if key in self.rank_typology:
            if field is None:
                return self.rank_typology[key].copy()
            else:
                return self.rank_typology[key][field]
        return None
    


        
    def db_get_valid_merges (self, id_taxonref):
        """return a dictionnary {"name": id_taxonref} of valid sibling for merging taxa based on the id_rank
            #ex: return {'Acorales': 17056, 'Alismatales': 17057, 'Amborellales': 16183,...}
            when searching for a order
        """
        sql_query = f"""
                    SELECT
                    n.taxaname,
                    n.id_taxonref
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
        return taxa_dict
    
    def db_get_valid_parents (self, id_taxonref):
        """return a dictionnary {"name": id_taxonref} of valid parents for id_taxonref based on the id_rank
            #ex: return {'Acorales': 17056, 'Alismatales': 17057, 'Amborellales': 16183,...}
            when searching for a family
        """
        sql_query = f"""
                SELECT
                n.taxaname,
                n.id_taxonref
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
        return taxa_dict

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
        if query.next():
            result = query.value(0)
            if result:
                return json.loads(result)
        return {}

    
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
        return dict_db_names
    
    def db_get_apg4_clades (self):
        #return the list of distinct clades from the apg4 table (field clade), [] if nothing
        #typically ['ANA Grade', 'Ceratophyllales', 'Chloranthales', 'Core Eudicots', 'Magnoliids', 'Monocots']
        #sql_query = "SELECT json_agg(DISTINCT a.group_taxa) AS json_list FROM taxonomy.wfo_order a WHERE a.group_taxa IS NOT NULL;"
    
        sql_query = """
                    SELECT json_agg(DISTINCT clade) AS json_list 
                    FROM
                        (SELECT clade_apg AS clade FROM taxonomy.taxa_group
                            UNION ALL
                         SELECT group_taxa AS clade FROM taxonomy.taxa_group
                        )
                    WHERE clade IS NOT NULL;
                    """
        #execute the query
        query = self.db.exec(sql_query)
        if query.next():
            result = query.value("json_list")
            if result:
                return json.loads(result)
        return []

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
                    taxonomy.pn_taxa_getparent(id_taxonref, {grouped_idrank}) AS id_parent --to change
                FROM taxonomy.taxa_group a
                INNER JOIN taxonomy.taxa_reference b ON lower(a.rank_order) = b.basename
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
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return []
        if result.next():
            json_text = result.value(0)
            if json_text:
                return json.loads(json_text)
        return []
    
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
        if query.next():
            return {
                "id_taxonref": id_taxonref,
                "id_parent": query.value("id_parent"),
                "id_rank": query.value("id_rank"),
                "taxaname": query.value("taxaname"),
                "authors": query.value("authors"),
                "published": query.value("published"),
                "accepted": query.value("accepted")
            }

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
        return ls_hierarchy

#############################    
    def db_add_synonym(self, id_taxonref, synonym, category = 'Orthographic', error_msg = False):
        #add a synonym to a id_taxonref, return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_add ({id_taxonref}, '{synonym}', '{category}')"
        #execute the query
        result = self.db.exec(sql_query)
        if result.lastError().isValid() and error_msg:
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return not result.lastError().isValid()

    def db_edit_synonym(self, old_synonym, new_synonym, new_category = 'Orthographic'):
        #edit a synonym return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_update ('{old_synonym}','{new_synonym}', '{new_category}')"
        #execute the query
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return not result.lastError().isValid()

    def db_delete_synonym(self, synonym):
        #delete a synonym from the taxonomy.taxa_names table, return True or False if error
        #sql_query = self.sql_taxa_delete_synonym(synonym)
        sql_query = f"SELECT taxonomy.pn_names_delete ('{synonym}')"
        #execute the query
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
    
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
        query.next()
        return query.value(fieldname)
    
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
                            _value2 = functions.get_str_value(_value2)
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
        return json_props


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
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
    
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
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
    
    def db_merge_reference (self, from_idtaxonref, to_idtaxonref, category='Orthographic'):
        #set two taxa as synonyms
        if to_idtaxonref == from_idtaxonref:
            return False
        sql_query = f"CALL taxonomy.pn_taxa_set_synonymy({from_idtaxonref}, {to_idtaxonref}, '{category}');"
        #execute the query
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
    
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
            #sql_query = self.sql_taxa_delete_reference(id_taxonref)
            sql_query = f"SELECT taxonomy.pn_taxa_delete ({id_taxonref}) AS id_taxonref"
            result = self.db.exec(sql_query)
            if result.lastError().isValid():
                msg = self.postgres_error(result.lastError())
                QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
                return []
        return ls_todelete
    
    def db_save_dict_taxa(self, dict_tosave):
        #save a taxa dictionnary in the database, return id_taxonref (new or updated) or None if error
        #dict_tosave = {"id_taxonref":integer, "id_parent":integer, "id_rank" :integer, "basename":text, "authors":text, "parentname":text[None], "published":boolean, "accepted":boolean}
        code_error = ''
        msg = ''
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
                                    lower(a.name) ='{_parentname}'
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
        code_error = result.lastError().nativeErrorCode()

        #if no errors, set the id_taxonref to the dict_tosave
        if len(code_error) == 0:
            if result.next():
                return_idtaxonref = result.value("id_taxonref")
            #dict_tosave["id_taxonref"] = return_idtaxonref            
        else:
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return return_idtaxonref
    

