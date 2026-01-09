###########################################
#imports
import subprocess
import os
import webbrowser
import json
import re
from PyQt5 import QtGui, QtSql, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal,QEvent #, QItemSelectionModel
#from core import functions
###########################################

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
        file_config = config.read('config.ini')
        section = 'database'
        if file_config and section in config.sections():
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
    #a class to manage the database of taxa
    def __init__(self, parent=None):
        super().__init__(parent)
        #self.db = None

    # def open(self):
    #     super().open("db_taxa")

    def db_get_apg4_clades (self):
        #return the list of distinct clades from the apg4 table (field clade), [] if nothing
        #typically ['ANA Grade', 'Ceratophyllales', 'Chloranthales', 'Core Eudicots', 'Magnoliids', 'Monocots']
        #sql_query = "SELECT json_agg(DISTINCT a.group_taxa) AS json_list FROM taxonomy.wfo_order a WHERE a.group_taxa IS NOT NULL;"
    
        sql_query = """
                    SELECT json_agg(DISTINCT clade) AS json_list 
                    FROM
                    (
                        SELECT clade_apg AS clade FROM taxonomy.taxa_group
                            UNION ALL
                        SELECT group_taxa AS clade FROM taxonomy.taxa_group
                    )
                    WHERE clade IS NOT NULL
                    ;
                    """
        #sql_query = "SELECT json_agg(DISTINCT a.group_taxa ||'-'|| a.clade_apg) AS json_list FROM taxonomy.wfo_order a;"

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
        #print(sql_query)
        result = self.db.exec (sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return []
        if result.next():
            json_text = result.value(0)
            if json_text:
                return json.loads(json_text)
        #print (sql_query)
        return []


    
    def db_add_synonym(self, id_taxonref, synonym, category = 'Orthographic', error_msg = False):
        #add a synonym to a id_taxonref, return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_add ({id_taxonref}, '{synonym}', '{category}')"
        result = self.db.exec(sql_query)
        if result.lastError().isValid() and error_msg:
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return not result.lastError().isValid()

    def db_edit_synonym(self, old_synonym, new_synonym, new_category = 'Orthographic'):
        #edit a synonym return True or False if error
        sql_query = f"SELECT taxonomy.pn_names_update ('{old_synonym}','{new_synonym}', '{new_category}')"
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
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
    
    def db_update_properties (self, id_taxonref, json_properties):
        #update the properties json of a taxonref from a json string, return True or False if error
        if json_properties is None:
            json_properties = 'NULL'
        else:
            json_properties = f"'{json_properties}'::jsonb"
        sql_query = f"""UPDATE taxonomy.taxa_reference 
                    SET properties = {json_properties}
                    WHERE id_taxonref = {id_taxonref} AND id_rank >= 21;"""
        result = self.db.exec(sql_query)
        if result.lastError().isValid():
            msg = self.postgres_error(result.lastError())
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return False
        return True
               
    def db_update_metadata (self, id_taxonref, json_metadata):
        #return sql statement to update the metadata json of a taxonref
        if json_metadata is None:
            json_metadata = 'NULL'
        else:
            json_metadata = f"'{json_metadata}'::jsonb"
        sql_query = f"""UPDATE taxonomy.taxa_reference 
                    SET metadata = {json_metadata}
                    WHERE id_taxonref = {id_taxonref};"""
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
    
    def db_save_dict_taxa(self, dict_tosave): #database_save_taxon(dict_tosave):
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
    

    # def sql_taxa_searchNames(self, text_search):
    #     text_search = re.sub(r'[\*\%]', '', text_search)
    #     #return a sql statement for searching taxanames
    #     return f"SELECT id_taxonref FROM taxonomy.pn_taxa_searchname ('%{text_search}%')"



    # def sql_apg4_clade_json (self):
    #     #return sql statement to get the list of distinct clades from the apg4 table
    #     return "SELECT json_agg(DISTINCT a.clade) AS json_list FROM taxonomy.apg4 a WHERE clade IS NOT NULL;"   


    
    # def sql_taxa_add_synonym(self, id_taxonref, synonym, category = 'Orthographic'):
    #     #return a sql statement for adding a synonym
    #     return f"SELECT taxonomy.pn_names_add ({id_taxonref}, '{synonym}', '{category}')"
    
    # def sql_update_metadata_json (self, id_taxonref, json_metadata):
    #     #return sql statement to update the metadata json of a taxonref
    #     return f"""UPDATE taxonomy.taxa_reference 
    #                 SET metadata = '{json_metadata}'::jsonb
    #                 WHERE id_taxonref = {id_taxonref};"""
    # def sql_taxa_delete_synonym(self, synonym):
    #     #return a sql statement for deleting a synonym
    #     return f"SELECT taxonomy.pn_names_delete ('{synonym}')"
    
    # def sql_taxa_get_childs(self, id_taxonref, include_self=True):
    #     #return a sql statement for getting the id_taxonref childs of a taxonref
    #     return f"SELECT id_taxonref FROM taxonomy.pn_taxa_childs ({id_taxonref}, {include_self})"
    # def sql_taxa_delete_reference(self, id_taxonref):
    #     #return a sql statement for deleting a reference name
    #     return f"SELECT taxonomy.pn_taxa_delete ({id_taxonref}) AS id_taxonref"
#class to display a search widget composed of a search text and and treeview result with  matched taxa and score
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
        _score = 0.4
        #exlude search according to number of characters
        if len(search_txt) < 4:
            return
        if len(search_txt) < 8:
            _score = 0.2
        #create sql query
        sql_query = f"""
            SELECT 
                a.taxonref, a.score, a.id_taxonref, c.name AS synonym
            FROM 
                taxonomy.pn_taxa_searchname('{search_txt}', {_score}::numeric) a 
            INNER JOIN 
                taxonomy.taxa_nameset c 
            ON 
                a.id_taxonref = c.id_taxonref AND c.category <> 1
            ORDER 
                BY score DESC, synonym ASC
        """
        #print (sql_query)
        query = QtSql.QSqlQuery (sql_query)
        dict_nodes = {}
        tab_header = ['taxonref', 'score']
        while query.next():
            id_taxonref = query.value('id_taxonref')
            if id_taxonref in dict_nodes:
                ref_item = dict_nodes[id_taxonref]
            else:
                #create the node if not already existed
                ref_item = [QtGui.QStandardItem(str(query.value(x))) for x in tab_header]
                ref_item[0].setData(id_taxonref, Qt.UserRole)
                ref_item[1].setTextAlignment(Qt.AlignCenter)
                self.model.appendRow(ref_item)
                dict_nodes[id_taxonref] = ref_item
                #set score in red if below 50
                if query.value('score') < 50:
                    _color =  QtGui.QColor(255, 0, 0)
                    ref_item[1].setData(QtGui.QBrush(_color), Qt.ForegroundRole)
            if query.value('synonym'):
                ref_item[0].appendRow ([QtGui.QStandardItem(query.value('synonym'))])
                
        if self.model.rowCount() > 0:
            self.treeview_scoretaxa.resizeColumnToContents(1)
            self.treeview_scoretaxa.setExpanded(self.model.index(0, 0), True)
            self.treeview_scoretaxa.header().setStretchLastSection(False)
            self.treeview_scoretaxa.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.treeview_scoretaxa.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)


#class to display a treeview with hiercharchical taxonomy
# class PN_TaxaQTreeView(QtWidgets.QTreeView):
#     """
#     The PN_TaxaQTreeView class is a custom class that inherits from QtWidgets.QTreeView.
#     It is designed to display a hierarchical taxonomic structure.
#     The class takes a PNTaxa object as input to define the taxonomic hierarchy.

#     Attributes:
#         None

#     Methods:
#         __init__ : Initializes the tree view window, disabling editing capabilities.
#         setdata : Defines the taxonomic hierarchy based on a PNTaxa object. It creates a SQL query to retrieve the hierarchy, executes the query, and populates the tree view with the results.
#         selecteditem : Returns a PNTaxa object corresponding to the selected item in the tree view.

#     Notes:
#         The setdata method is the primary method of the class, as it retrieves and populates the taxonomic hierarchy from a PNTaxa object.
#         The selecteditem method is a convenience function to retrieve the data of the selected item as a PNTaxa object.
#     """
#     def __init__(self):
#         super().__init__()
#         self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    
    
#     def setdata(self, myPNTaxa):
# # Get the hierarchy for the selected taxa
#         model = QtGui.QStandardItemModel()
#         #model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
#         self.setModel(model)
#         self.setColumnWidth(0, 300)
#         ls_hierarchy = myPNTaxa.list_hierarchy
#         if not ls_hierarchy:
#             return

#         dict_idtaxonref = {}
#         for item in ls_hierarchy:
#             dict_idtaxonref[item.idtaxonref] = [QtGui.QStandardItem(item.rank_name), QtGui.QStandardItem(item.taxonref)]

#         for item in ls_hierarchy:
#             #search for a parent_item in the dictionnary of item index on id_taxonref
#             item_parent = dict_idtaxonref.get(item.id_parent, None)
#             item_taxon = dict_idtaxonref.get(item.idtaxonref, None)
#             #append as child or root
#             if item_parent:
#                 item_parent[0].appendRow(item_taxon)
#             else:
#                 # append as a new line if item not found (or first item)
#                 model.appendRow(item_taxon)
#             #if item_rank:
#             item_taxon[0].setData(item, Qt.UserRole)
#             # set italic if not published
#             if not item.published:
#                 font = QtGui.QFont()
#                 font.setItalic(True)
#                 model.setData(item_taxon[0].index(), font, Qt.FontRole)

#         # set bold the current id_taxonref line (2 first cells) and italized authors if not published
#         current_item = dict_idtaxonref.get(myPNTaxa.idtaxonref, None)
#         if current_item:
#             font = QtGui.QFont()
#             font.setBold(True)
#             key_index = current_item[0].index() #save key_index if found
#             model.setData(current_item[0].index(), font, Qt.FontRole)
#             model.setData(current_item[0].index(), font, Qt.FontRole)

#         if key_index:
#             #select and ensure visible the key_index (automatic scroll)
#             self.selectionModel().setCurrentIndex(key_index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
#             self.scrollTo(key_index,QtWidgets.QAbstractItemView.PositionAtCenter)  # PositionAtTop/EnsureVisible
            
#         self.setHeaderHidden(True)
#         self.expandAll()

#     def selecteditem(self):
#         #return a PNTaxa for the selected item into the hierarchical model
#         return self.currentIndex().siblingAtColumn(0).data(Qt.UserRole)



#     def setdata2(self, myPNTaxa):
# # Get the hierarchy for the selected taxa
#         model = QtGui.QStandardItemModel()
#         model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
#         self.setModel(model)
#         self.setColumnWidth(0, 300)
#         try:
#             if myPNTaxa.idtaxonref * myPNTaxa.id_rank == 0:
#                 return
#         except Exception:
#             return
#         str_idtaxonref = str(myPNTaxa.idtaxonref)
#         sql_where = ''
#         # extend to all taxa included in the genus when id_rank > genus (e.g. for species return all sibling species within the genus)
#         #or in other words, set to the genus rank when id_rank > genus
#         if myPNTaxa.id_rank > 14: #get the genus rank at minimum
#             str_idtaxonref = f"""(SELECT * FROM taxonomy.pn_taxa_getparent({str_idtaxonref},14))"""
#         if myPNTaxa.id_rank < 10: #limit the deepth to the families level
#             sql_where = "\nWHERE a.id_rank <=10"
#         # create the SQL query to get the hierarchy of taxa
#         sql_query = f"""SELECT 
#                             id_taxonref, id_rank, id_parent, taxaname,  coalesce(authors,'')::text authors, published, accepted 
#                         FROM
#                             (SELECT 
#                                 id_taxonref, id_rank, id_parent, taxaname,  authors, published, accepted
#                             FROM    
#                                 taxonomy.pn_taxa_parents({str_idtaxonref}, True)
#                             UNION 
#                             SELECT 
#                                 id_taxonref, id_rank, id_parent, taxaname,  authors, published, accepted
#                             FROM 
#                                 taxonomy.pn_taxa_childs({str_idtaxonref}, False)
#                             ) a
#                             {sql_where}
#                         ORDER BY 
#                             a.id_rank, a.taxaname
#                     """
#         #print (sql_query)
#         model = self.model()
#         # model.setRowCount(0)
#         model.setColumnCount(2)
#         # execute the Query and fill the treeview standarditemmodel based on search id_parent into the third column containing id_taxonref
#         query = QtSql.QSqlQuery(sql_query)
#         #set the taxon to the hierarchical model rank = taxon
#         key_index = None
#         dict_idtaxonref = {}
#         while query.next():
#             id_taxonref = query.value('id_taxonref')
#             idrank = query.value('id_rank')
#             taxaname = query.value('taxaname').strip()
#             authors = query.value('authors').strip()
#             published = query.value('published')
#             accepted = query.value('accepted')
#             dict_item = {'idtaxonref': id_taxonref, 'taxaname': taxaname, 'authors': authors, 'published': published, 'accepted': accepted, 'idrank': idrank, 'parent': ''}
#             #create the items
#             _rankname = functions.get_dict_rank_value(idrank,'rank_name')
#             ##set the authors and composite taxonref
#             if len(authors) > 0 and not published:
#                 authors = authors + ' ined.' 
#             _taxonref = taxaname + ' ' + authors
#             _taxonref = _taxonref.strip()
#             #create the QStandardItem for the taxon
#             item = QtGui.QStandardItem(_rankname)
#             item1 = QtGui.QStandardItem(_taxonref)

#             #search for a parent_item in the dictionnary of item index on id_taxonref
#             item_parent = dict_idtaxonref.get(query.value('id_parent'), None)
#             if item_parent:
#                 # get the first col of the QStandardItem
#                 index = item_parent.index()
#                 dict_item["parent"] = index.data(Qt.UserRole).get('taxaname', '')
#                 # append a child to the item
#                 model.itemFromIndex(index).appendRow([item, item1],)
#             else:
#                 # append as a new line if item not found (or first item)
#                 model.appendRow([item, item1],)
#             if item:
#                 item.setData(dict_item, Qt.UserRole)
#                 dict_idtaxonref[id_taxonref] = item
            
#             # set bold the current id_taxonref line (2 first cells) and italized authors if not published
#             if not published:
#                 font = QtGui.QFont()
#                 font.setItalic(True)
#                 model.setData(item1.index(), font, Qt.FontRole)
#             if id_taxonref == myPNTaxa.idtaxonref:
#                 font = QtGui.QFont()
#                 font.setBold(True)
#                 key_index = item.index() #save key_index if found
#                 model.setData(item.index(), font, Qt.FontRole)
#                 model.setData(item1.index(), font, Qt.FontRole)
#         if key_index:
#             #select and ensure visible the key_index (automatic scroll)
#             self.selectionModel().setCurrentIndex(key_index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
#             self.scrollTo(key_index,QtWidgets.QAbstractItemView.PositionAtCenter)  # PositionAtTop/EnsureVisible

#         self.setHeaderHidden(True)

#         #self.resizeColumnToContents()
#         self.hideColumn(2)
#         self.expandAll()
