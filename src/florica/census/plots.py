#external modules
import os
import sys
import re
import copy
import json
import csv
import math

import pandas as pd

from PyQt5 import uic, QtWidgets, QtCore, QtSql, QtGui
from PyQt5.QtCore import Qt
########################################
from models.occ_model import PN_taxa_resolution_model
from models.taxa_model import PNSynonym, PN_TaxaSearch
from core.widgets import PN_JsonQTreeView, PN_dbTaxa , PN_DatabaseConnect
from core.functions import (get_str_value, get_all_names, get_reference_field, postgres_error, list_db_fields, 
                           flower_reg_pattern, fruit_reg_pattern, AppContext, init_context
                           )
########################################


#default parameters
PLOT_DEFAULT_DECIMAL = 2
DBASE_DATETIME_FORMAT = "yyyy-MM-dd hh:mm:ss.zzz t"
DBASE_SCHEMA = 'plots'
DBASE_SCHEMA_TAXONOMY = 'taxonomy'
DBASE_SCHEMA_TREES = DBASE_SCHEMA + '.trees'
DBASE_SCHEMA_PLOTS = DBASE_SCHEMA + '.plots'

#structure of the trees/plots tables, based on list_db_fields
#field_name :{value, type, items, translate, unit, decimal, min, max, editable, enabled, tip, details, synonyms}
dict_db_plot = {
                "id_plot": {"value" : None, "type" : 'integer', 'enabled': False},
                "collection": {"value" : None, "type" : 'text', "editable" : True},
                "locality":list_db_fields["locality"],
                "plot": {"value" : None, "type" : 'text'},
                "longitude":list_db_fields["longitude"],
                "latitude":list_db_fields["latitude"],
                "altitude":list_db_fields["altitude"],
                "type": {"value" : None, "type" : 'text', "items" : ["Circle", "Point", "Rectangle"]},
                "width": {"value" : None, "type" : 'numeric'},
                "radius": {"value" : None, "type" : 'numeric', "visible": False},
                "length": {"value" : None, "type" : 'numeric'},
                "area" : {"value": None, "type" : 'numeric', "enabled": False, "visible": True}             
                }

dict_db_tree = {
                "id_tree": {"value" : None, "type" : 'integer', 'enabled': False},  
                "identifier":list_db_fields["identifier"],
                "taxaname" :list_db_fields["taxaname"],
                "month":list_db_fields["month"],
                "year":list_db_fields["year"],
                "strata":list_db_fields["strata"],
                "stems":list_db_fields["stems"],                
                "dbh":list_db_fields["dbh"],
                "height":list_db_fields["height"],
                "bark_thickness":list_db_fields["bark_thickness"],
                "leaf_area":list_db_fields["leaf_area"],
                "wood_density":list_db_fields["wood_density"],
                "leaf_sla":list_db_fields["leaf_sla"],
                "leaf_ldmc":list_db_fields["leaf_ldmc"],
                "x":list_db_fields["x"],
                "y":list_db_fields["y"],
                "notes":  {"value" : None, "type" : 'memo',"synonyms" : ['comment', 'comments', 'commentaire', 'note'], "tip": 'Some notes about the observation'}, 
                "flower":list_db_fields["flower"],
                "fruit":list_db_fields["fruit"],
                "dead": {"value" : None, "type" : 'boolean', "default": False, "tip": 'Is the plant is dead ?'},
                "time_updated": {"value" : None, "type" : 'date', 'enabled': False},
                "history": {"value" : None, "type" : 'integer', 'enabled': False, 'visible': False}
                }
# add perimeter synonyms to dbh synonyms list
dbh_perimeter_synonyms = ["perimeter", "perim.", "périmètre", "périm.", "perimetro", "circumference", 
                      "circonférence", "circonf", "circ.", "girth", "circunferencia", "circ"]
dict_db_tree["dbh"]["synonyms"] += dbh_perimeter_synonyms
#create a composite dictionnary
dict_db_ncpippn = dict_db_plot | dict_db_tree


def get_typed_value(field_name, field_value, for_sql = False):
#high level function, return the value casted to the right type, raised an error if not possible
    if field_name in dict_db_ncpippn:
        field_def = dict_db_ncpippn[field_name]
    elif field_name in list_db_fields:
        field_def = list_db_fields[field_name]
    else:
        return
    _type = field_def["type"]
    error_code = 1000
    msg = "Error in type conversion for the field " + field_name
    if field_value is not None:
        try:
            if _type == 'integer':
                field_value = int(float(field_value))
            elif _type == 'numeric':
                _decimal = field_def.get("decimal", PLOT_DEFAULT_DECIMAL)
                field_value = round(float(field_value), _decimal)
            elif _type in ['text', 'memo']:
                field_value = str(field_value)
            elif _type == 'boolean':
                field_value = bool(field_value)
            elif _type == 'date':
                if isinstance(field_value, QtCore.QDateTime):
                    field_value = field_value.toString(DBASE_DATETIME_FORMAT)
            #check boundaries for numeric values
            if _type in ['integer', 'numeric']:
                if field_def.get("min", None) is not None and field_value < field_def["min"]:
                    msg = "Error : The value must be greater than " + str(field_def["min"])
                    raise ValueError(msg, 1001)
                if field_def.get("max", None) is not None and field_value > field_def["max"]:
                    msg = "Error : The value must be lower than " + str(field_def["max"])
                    raise ValueError(msg, 1002)
        except Exception :
            raise ValueError(msg, error_code)
            field_value = None
    #transform to SQL value if flag for_sql True
    if for_sql:
        if not field_value:
            field_value = 'NULL'
        elif _type in ['text', 'memo', 'date']:
            field_value = field_value.replace("'", "''")
            field_value = "'" + field_value + "'"
    return field_value

def database_execute_query(sql_query):
#High level, execute query and return True or Value if included in query
    query = QtSql.QSqlQuery(sql_query)
    values_list = []
    if query.isActive():
        #success in query execution
        try:
            while query.next():
                value = query.value(0)
                values_list.append(value)
            if not values_list: #no returning value
                return True
            elif len(values_list) == 1: #One returning value
                return values_list[0]
            else:
                return values_list #list of returning value
        except Exception:
            return True
    else:
        #error in query execution
        msg = postgres_error(query.lastError())
        QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return False
        





class HighlightColumnDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        painter.save()
        brush = QtGui.QBrush(QtGui.QColor(128, 128, 128, 50))
        painter.fillRect(option.rect, brush)
        painter.restore()
        if not index.siblingAtColumn(1).data():
            font = QtGui.QFont()
            font.setItalic(True)
            index.model().itemFromIndex(index).setFont(font)

class CSVImporter(QtWidgets.QDialog):
#The main class of the dialog
    def __init__(self, table_def):
        super().__init__()
        #final list of trees to be imported
        #dictionnary (identifier:id_plot) of trees imported already present in the table trees 
        self.dict_identifier_toUpdate = {}
        self.rows_imported = 0
        # load the GUI
        #self.column_value = 2
        self.dict_items = {}
        # if not table_def:
        #     table_def = copy.deepcopy(dict_db_ncpippn)
        self.tabledef = table_def
        #self.dict_trees_import = table_def
        self.type_columns = None
        self.dataframe = None
        self.buttonOK = False
        self.window = uic.loadUi("ui/pn_ncpippn_import.ui")
        validator = QtGui.QIntValidator(2, 2147483647)
        self.window.lineEdit.setValidator(validator)
        self.window.progressBar.setVisible(False)
       # self.headers = None
        self.window.pushButton_import.clicked.connect(self.load)
        self.window.button_previous.clicked.connect(lambda: self.navigate(False))
        self.window.button_next.clicked.connect(lambda: self.navigate(True))
        self.window.lineEdit.textChanged.connect(self.loadValue)
        self.window.button_search_errors.clicked.connect(self.search_nexttError)
        self.window.buttonbox_import.button(QtWidgets.QDialogButtonBox.Ok).clicked.connect(self.validate)
        self.window.buttonbox_import.button(QtWidgets.QDialogButtonBox.Cancel).clicked.connect(self.close)
        self.window.tblview_columns.clicked.connect(self.tblview_columns_clicked)
        # set the delegate for columns coloring
        delegate = HighlightColumnDelegate()
        self.window.tblview_columns.setItemDelegateForColumn(3, delegate)
        self.window.tblview_columns.setItemDelegateForColumn(0, delegate)

    def tblview_columns_clicked(self):
        """
        Handles the event triggered when a row in the tblview_columns table is selected.
        
        Retrieves the field name and its definition from the dict_trees_import dictionary.
        Updates the label_db_column text with the field name and its type.
        Creates a notice text based on the field definition's tip, unit, and details.
        Sets the toolTip for the selected column item with the notice text.
        Updates the label_infos_db text with the notice text.
        
        Parameters:
            self (CSVImporter): The instance of the CSVImporter class.
        
        Returns:
            None
        """
        index = self.window.tblview_columns.currentIndex() 
        field_name = index.siblingAtColumn(0).data()
        if field_name in self.dict_trees_import:
            field_def = self.dict_trees_import[field_name]
        else:
            field_name = index.siblingAtColumn(1).data()
            field_name = get_reference_field(field_name)
            field_def = list_db_fields[field_name]

        column_txt = field_name.upper() + " [" + field_def["type"] + "]"
        self.window.label_db_column.setText(column_txt)
        notice = ''
        sep = ''
        self.window.label_infos_db.setText(notice)
        self.window.label_infos_error.setText('')
        #create text to display according to field_def tip, unit and details (cf. load_dict_trees_import)
        if "tip" in field_def:
            notice = field_def["tip"]
            sep = " - "
        if "unit" in field_def:
            notice += sep + '(' + field_def["unit"] + ')'
            sep = " - "
        if notice:
            self.window.label_infos_db.setText(notice)
            self.window.tblview_columns.model().itemFromIndex(index).setToolTip(notice)
        #add combination tip and unit as toolTip
        if field_def.get("details", None):
            self.window.tblview_columns.model().itemFromIndex(index).setToolTip(field_def["details"])
            
        #add details (how calculation was done, cf. load_dict_trees_import)
        if "error" in field_def:
            self.window.label_infos_error.setText(field_def["error"])


    def load(self, filename = None):
        # def is_synonym(fieldref, fieldname):
        # #return True if fieldname is equal or a synonym to fieldref
        #     fieldname = fieldname.strip(' ').lower()
        #     fieldref = fieldref.strip(' ').lower()
        #     if fieldref == fieldname:
        #         return True
        #     synonym = dict_db_ncpippn[fieldref].get("synonyms", None)
        #     if synonym and fieldname in synonym:
        #         return True
        #     return False

        #main function to load a csv file, or to open fileBowser
        #import os 
        #import csv
        if not isinstance(filename, str):
            filename = None
        try:
            os.path.exists(filename)
        except Exception:
            filename = None

        if filename is None:
        #set parameters to QfileDialog
            options = QtWidgets.QFileDialog.Options()
            options |= QtWidgets.QFileDialog.ReadOnly
            file_dialog = QtWidgets.QFileDialog()
            file_dialog.setNameFilter("Fichiers CSV (*.csv)")
            file_dialog.setDefaultSuffix("csv")
            filename, file_type = file_dialog.getOpenFileName(None, "Import a CSV File", "", "CSV Files (*.csv);;All files (*)", options=options)
            if not filename: 
                return
        with open(filename, 'r', encoding='utf-8') as file:
            # Lire une portion du fichier pour l'analyse
            sample = file.readline()
            # Utiliser csv.Sniffer pour déduire le délimiteur
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
        #read the csv file and set the rows and columns
        try:
            self.dataframe = pd.read_csv(filename, sep=delimiter, encoding='utf-8', low_memory=False, quotechar='"', skipinitialspace=True)
            self.dataframe = self.dataframe.dropna(how='all')  #keep only row with data
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Invalid Datasource", str(e), QtWidgets.QMessageBox.Cancel)
            return
        #Test for lines
        if self.dataframe.shape[0] <= 0:
            QtWidgets.QMessageBox.critical(None, "Invalid Datasource", "The file is empty", QtWidgets.QMessageBox.Cancel)
            return
        self.dataframe.columns = self.dataframe.columns.str.lower()
        _summary = str(self.dataframe.shape[0]) + ' rows, ' + str(self.dataframe.shape[1]) + ' columns - current row:'
        self.window.label_summary.setText(_summary)
        self.window.linedit_source_file.setText (filename)
        #check for primary types excluding null-values
        self.type_columns = self.dataframe.dropna().dtypes
        model = QtGui.QStandardItemModel()

        self.dict_items = {}
        self.dict_trees_import = self.tabledef.copy()
        #add item and create a clef for any item from field in dict_trees_import
        for key, field_def in self.dict_trees_import.items():
            item = QtGui.QStandardItem(key)
            #model.appendRow(item)
            self.dict_items[key] = item

        #add subfields according to composite fields
        if self.dict_trees_import.get ("leaf_sla", None):
            self.dict_trees_import["leaf_dry_weight"] = list_db_fields["leaf_dry_weight"].copy()
            self.dict_trees_import["leaf_area"] = list_db_fields["leaf_area"].copy()
        if self.dict_trees_import.get ("leaf_ldmc", None):
            self.dict_trees_import["leaf_fresh_weight"] = list_db_fields["leaf_fresh_weight"].copy()
            self.dict_trees_import["leaf_dry_weight"] = list_db_fields["leaf_dry_weight"].copy() 
        if self.dict_trees_import.get ("wood_density", None):
            self.dict_trees_import["wood_core_diameter"] = list_db_fields["wood_core_diameter"].copy()
            self.dict_trees_import["wood_core_length"] = list_db_fields["wood_core_length"].copy() 
            self.dict_trees_import["wood_core_weight"] = list_db_fields["wood_core_weight"].copy()

        #set the imported structure to any fields ({"column": header, "value": None, "code" : None})
        imported = 0
        for key, field_def in self.dict_trees_import.items():
            #clean the import structure
            key_header = None
            if field_def.get("import", None):
                del field_def["import"]            
            #test if key (and synonyms) is in type_columns (CSV)
            header = (next((elem for elem in get_all_names(key) if elem in self.type_columns), None))
            #set the code to be evaluate during decodage (cf. self.load_dict_trees_import)
            #check for field_column allowing to calculate special values as leaf_sla (if leaf_area and leaf_dry_weight are present)
            code = None
            code = f"dataline['{header}']"
            if header:
                imported += 1
                key_header = {"column": header, "value": None, "code" : code}
                field_def["import"] = key_header

        #return if no column was imported
        if imported == 0:
            return
        
        # #append 2 columns for the row (db_field & csv_field)
        for key, field_def in self.dict_trees_import.items():
            item2 = None
            field_def_import = field_def.get("import", None)
            if field_def_import:
                item2 = QtGui.QStandardItem(field_def_import["column"])            
            if key in self.dict_items:
                item = self.dict_items[key]
                model.appendRow([item, item2])
            #append subrows for composite fields
                if key == "leaf_sla":
                    self.fill_model_headers ("leaf_area", item)
                    self.fill_model_headers ("leaf_dry_weight", item)
                elif key == "leaf_ldmc":
                    self.fill_model_headers ("leaf_dry_weight", item)
                    self.fill_model_headers ("leaf_fresh_weight", item)
                elif key == "wood_density":
                    self.fill_model_headers ("wood_core_weight", item)
                    self.fill_model_headers ("wood_core_length", item)
                    self.fill_model_headers ("wood_core_diameter", item)
        
        #to create a dictionnary of identifier in the CSV file that already exists in the db, table trees (UPDATE)
        if self.dict_trees_import.get("identifier", None):
            if self.dict_trees_import["identifier"].get("import", None):
                column = self.dict_trees_import["identifier"]["import"]["column"]
                #look for duplicate identifier (error)
                double = self.dataframe[column].duplicated(keep=False)
                if double.any():
                    double_identifier = self.dataframe[double][column].iloc[0]
                    msg = "CSV file contains duplicated identifier: " + double_identifier
                    QtWidgets.QMessageBox.critical(None, "No identifier", msg, QtWidgets.QMessageBox.Ok)
                    return

                #get a list of unique non null identifier
                non_null_identifier = self.dataframe[column].dropna().unique().tolist()
                #create the dictionnary of updated identifier
                if non_null_identifier:
                    #clause_in = ", ".join(tab_identifier)
                    clause_in = ", ".join(["'{}'".format(item) for item in non_null_identifier])
                    sql_query = f"""SELECT 
                                        identifier, 
                                        {DBASE_SCHEMA_TREES}.id_plot, 
                                        plot 
                                    FROM 
                                        {DBASE_SCHEMA_TREES} 
                                    JOIN 
                                        {DBASE_SCHEMA_PLOTS} 
                                    ON 
                                        {DBASE_SCHEMA_TREES}.id_plot = {DBASE_SCHEMA_PLOTS}.id_plot 
                                    WHERE 
                                        identifier IN ({clause_in})
                                """ 
                    query = QtSql.QSqlQuery(sql_query)
                    self.dict_identifier_toUpdate = {}
                    while query.next():
                        self.dict_identifier_toUpdate[query.value("identifier")] = [query.value("id_plot"), query.value("plot")]
            else:
                #error the CSV file must contain an identifier
                msg = str(['identifier'] + list_db_fields["identifier"]["synonyms"])
                msg = "CSV file must contain one unique identifier column from " + msg
                QtWidgets.QMessageBox.critical(None, "No identifier", msg, QtWidgets.QMessageBox.Ok)
                model = QtGui.QStandardItemModel()
                self.window.tblview_columns.setModel(model)
                return
        
        # Add header for columns and set the mdoel
        model.setHorizontalHeaderItem(0, QtGui.QStandardItem("DB column"))
        model.setHorizontalHeaderItem(1, QtGui.QStandardItem("CSV column"))
        model.setHorizontalHeaderItem(2, QtGui.QStandardItem("CSV value")) # [" + str(index) + "]"))
        model.setHorizontalHeaderItem(3, QtGui.QStandardItem("DB value"))
        self.window.tblview_columns.setModel(model)
        self.loadValue ()

    def fill_model_headers(self, field_name, item):
        #create the subitems for nested fields
        try:
            item2 = QtGui.QStandardItem(self.dict_trees_import[field_name]["import"]["column"])
            #item.appendRow([QtGui.QStandardItem(field_name), item2])
        except Exception:
            item2 = None
        if item:
            item.appendRow([QtGui.QStandardItem(field_name), item2])

    def loadValue(self, index = 0):
    #load the line corresponding to index (connect with lineedit_changed signal)
        #check for index coherence
        try:
            index = int(index)
        except Exception:
            index = 1
        index = max(1, index)
        index = min(self.dataframe.shape[0], index)
        #set the correct index without slot evenet
        self.window.lineEdit.textChanged.disconnect(self.loadValue)
        self.window.lineEdit.setText(str(index))
        self.window.lineEdit.textChanged.connect(self.loadValue)
        self.window.label_infos_db.setText(None)
        self.window.label_db_column.setText(None)
        #create the model for tableview_colums
        model = self.window.tblview_columns.model()

        #load the value into the dict_trees_import
        self.load_dict_trees_import(index-1)

        #fill the model with dict_trees_import values and import dictionnary
        self.fill_model_value(model.invisibleRootItem())
        #manage label according to add or update
        field_identifier = self.dict_trees_import.get("identifier", None)
        if field_identifier:
            import_value = field_identifier["value"]
            
            if import_value in self.dict_identifier_toUpdate:
                msg = "UPDATE " + str(import_value)
                self.window.label_db_action.setText("UPDATE " + str(import_value))
                msg += " [Plot: " + str(self.dict_identifier_toUpdate[import_value][1]) + "]"
                self.window.label_db_action.setStyleSheet("color: #007bff;")
            else:
                msg = "ADD " + str(import_value)
                self.window.label_db_action.setText("ADD " + str(import_value))
                self.window.label_db_action.setStyleSheet("color: #28a745;")
                try:
                    longitude = float (self.dict_trees_import["longitude"]["value"])
                    latitude = float (self.dict_trees_import["latitude"]["value"])
                    if longitude * latitude:
                        msg += f" [New Point : {longitude}, {latitude}]"
                        self.window.label_db_action.setStyleSheet("color:rgb(171, 180, 37);")
                except Exception:
                    current_locality = dict_db_plot["plot"]["value"]
                    msg += f" [Plot: {current_locality}]"
            self.window.label_db_action.setText(msg)



                        #updating = True
                        #locality = self.dict_identifier_toUpdate[import_value][1]

        #ajust column sizes
        for col in range(model.columnCount()):
            self.window.tblview_columns.resizeColumnToContents(col)
        self.window.tblview_columns.expandAll()
        self.window.tblview_columns.selectionModel().selectionChanged.connect(self.tblview_columns_clicked)

#recursive function to fill the model according to the fieldname on first column (included childs)
    def fill_model_value (self, item):
        #fill the model with value in a recursive mode (browse the tree)
        if item is None:
            return
        #locality = None
        for row in range(item.rowCount()):
            item0 = item.child(row)
            #self.set_column_directly(item0, 1, None)
            self.set_column_directly(item0, 2, None)
            #self.set_column_directly(item0, 3, None)
            #get the field_name and field_def
            field_name = item0.text()
            field_def = self.dict_trees_import.get(field_name, None)
            if field_def is None:
                field_def = list_db_fields.get(field_name, None)
            if field_def is None:
                continue
            import_value = None
            #check for import dictionnary
            dict_import = field_def.get("import", None)
            if dict_import:
                import_value = dict_import["value"]
                if import_value is not None:
                    #self.set_column_directly(item0, 1, str(dict_import["column"]))
                    newitemValue = self.set_column_directly(item0, 2, str(import_value))
                    newitemValue.setData(None, Qt.ForegroundRole)
                    if field_def.get("error", None):
                        newitemValue.setForeground(QtGui.QBrush(QtGui.QColor(255, 0, 0)))
                    # elif field_name == "identifier" and import_value in self.dict_identifier_toUpdate:
                    #     #updating = True
                    #     locality = self.dict_identifier_toUpdate[import_value][1]
                    self.set_column_directly(item0, 2, str(import_value))
                
            #set the dbase value (column 3) only for root items
            if not item0.parent():
                dbase_value = self.dict_trees_import[field_name]["value"]
                self.set_column_directly(item0, 3, None)
                if dbase_value is not None:
                    self.set_column_directly(item0, 3, str(dbase_value))
                    #newitem = QtGui.QStandardItem(str(dbase_value))
                    # if locality and field_name == "identifier":
                    #     self.dict_trees_import["locality"]["value"] = locality
                    
            #recursivity to fill the model with sub-items
            self.fill_model_value(item0)

    def set_column_directly(self, item, column_index, value):
        self.window.label_infos_error.setText('')
        # get the parent or root
        parent = item.parent() or item.model().invisibleRootItem()
        # Obtenir la ligne de l'item
        row = item.row()
        # Accéder à l'élément dans la colonne spécifiée
        sibling_item = parent.child(row, column_index)
        if sibling_item is None:
            sibling_item = QtGui.QStandardItem(value)
            parent.setChild(row, column_index, sibling_item)
        else:
            sibling_item.setText(value)
        return sibling_item

    def navigate(self, forward = True):
    #allow to navidate forward (by default) or backward
        current_index = self.window.lineEdit.text()
        if current_index.isdigit():
            current_index = int(current_index)
        else:
            current_index = 1
        if forward:
            current_index += 1
        else:
            current_index -= 1
        self.window.lineEdit.setText(str(current_index))

    def search_nexttError (self):
    #set the value to the next row with error
        self.window.button_search_errors.setEnabled(False)
        self.window.button_search_errors.repaint()
        first = int(self.window.lineEdit.text()) + 1
        while first < self.dataframe.shape[0]:
            if not self.load_dict_trees_import(first-1):
                self.window.lineEdit.setText(str(first))
                break
            first += 1
        self.window.button_search_errors.setEnabled(True)

    def get_id_plot(self):
    #return the id_plot corresponding to the identifier from current dict_trees_import
    # id_plot if identifier is present in table trees; -1 if not present; 0 if not present but longitude/latitude are valid coordinates
        idplot = -1
        try:
            idplot = self.dict_identifier_toUpdate[self.dict_trees_import["identifier"]["value"]][0]
        except Exception:
            _longitude = self.dict_trees_import["longitude"]["value"]
            _latitude = self.dict_trees_import["latitude"]["value"]
            if _longitude and _latitude:
                idplot = 0
        return idplot
    

    def get_table_update (self):        
    #get the table update, all rows imported from the dataframe with corected errors
        dict_update = {}
        self.window.progressBar.setVisible(True)
        self.window.progressBar.setMaximum(self.dataframe.shape[0])
        nb_lines = self.dataframe.shape[0]
        for i in range(nb_lines):
            _tmp = []
            #load the dict_trees_import with the line i
            self.load_dict_trees_import(i)
            for field_def in self.dict_trees_import.values():
                value = field_def["value"]
                _tmp.append(value)            
            #add list of imported data to the dict_update with idplot as key (0 :longituteLlatitude, - 1:current plot and >0 identifier found)
            if _tmp:            
                idplot = self.get_id_plot()
                #create dict_update[idplot]
                if idplot not in dict_update:
                    dict_update[idplot] = []
                dict_update[idplot].append(_tmp)
            self.window.progressBar.setValue(i)
        self.window.progressBar.setVisible(False)
        return dict_update               
   
    def load_dict_trees_import(self, line_index = 0):
        #import data from the dataframe at the line index
        #set the translated value to each column in self.dict_trees_import
        """ 
            effective translation        
            - month translate input month (text : english, french, spanish and abbreviatins) into an integer (0-12) required by database
            - strata translate strata from integer, or text (english, french, spanish and abbreviatins) to common english term
                special case, if strata.value = 0, the tree is dead and no informations are saved on strata
            - dbh if succession of numeric termes separated by ";"then compute the DBH from the sum of area of each DBH and save the number of stems as the number of terms in the DBH list
                special case, if circumference (or synonyms) are found, then compute the DBH from the circumference
            - flower/fruit, if text (phenology and synonyms), search for commons terms for flower: (cf. flower_reg_pattern and fruit_reg_pattern) and set true or false if found by regex
            - auto-calculate wood_density, leaf_sla, leaf_ldmc if specific fields are included in csv field "leaf_area", "leaf_dry_weight", "leaf_fresh_weight", "leaf_dry_weight"
                "core_length", "core_dry_weight", "core_diameter"        
        """

        #get the line_index in the dataframe to import
        dataline = self.dataframe.iloc[line_index].dropna()
        fix_dead = False
        no_error = True
        tab_stems_dbh = None


        for field_name, field_def in self.dict_trees_import.items():
            import_value = None
            #set the default value first
            field_def["value"] = None
            field_def["details"] = None
#TODO: allow user to set default value
            # if dict_db_ncpippn[field_name].get("default", None) is not None:
            #     field_def["value"] =  dict_db_tree[field_name]["default"]
#END TODO
        #get the import dictionnary
            dict_import = field_def.get("import", None)
            if not dict_import:
                continue
        ###with a dict_import
            field_csv  = dict_import["column"]
            #set the import value
            if field_csv in dataline:
                import_value = dataline[field_csv]
            dict_import["value"] = import_value
            #set the import_value (if no import_value, the value is None)
            field_def["value"] = import_value
            
            #return if not import_value in the field_csv
            if import_value is None:
                continue

            #check for numeric values            
            if field_def["type"] in ['integer', 'numeric']:
                #replace comma by dot (correcting french-english keyboard in string)
                if isinstance(import_value, str):
                    import_value = import_value.replace(",", ".")
                try:
                    import_value = float(import_value)
                    if import_value.is_integer():
                        import_value = int(import_value)
                except Exception:
                    pass
            

            #manage special translation (dbh, fruits/flowers and month/strata)
            field_value = None
            if field_name == 'dbh':
                #test if perimeter
                #isgirth = field_csv in dbh_perimeter_synonyms
                total_area = 0
                #split the values to find multi-stems
                tab_stems_dbh = str(import_value).split(";")
                #compute the sum of area for each stem
                for i in range(len(tab_stems_dbh)):
                    float_dbh = None
                    try:
                        float_dbh = float(tab_stems_dbh[i])
                        if field_csv in dbh_perimeter_synonyms: #compute dbh if value is perimeter
                            field_def["details"] = f"The DBH was computed from the formula\n{field_csv}/PI"
                            float_dbh = float_dbh/math.pi
                        total_area += math.pi * (float_dbh/2)**2
                    except Exception:
                        continue
                #compute the resulting DBH from the total area
                field_value = 2*math.sqrt(total_area/math.pi)
            elif field_name in ['flower', 'fruit']:
                #ok if a form of boolean
                if import_value in ['True', 'False', True, False, 1, 0]:
                    field_value = bool(import_value)
                    continue
                elif isinstance (import_value, str): #considering regex search in a str
                    reg_pattern = flower_reg_pattern
                    if field_name == 'fruit':
                        reg_pattern = fruit_reg_pattern
                    field_value = False
                    try:
                        if re.search (reg_pattern, import_value, re.IGNORECASE):
                            field_value = True
                            field_def["details"] = "Value was extracted from search in text column " + field_csv
                    except Exception:
                        #for debugging
                        print ('error in regex', line_index, import_value, field_value, field_name)
                        field_value = False
            elif field_name in ["month", "strata"]:
                #dict_list = dict_strata if field_name == "strata" else dict_month
                dict_list = field_def.get("translate", {})
                #translate month to integer according to dict_month
                try:
                    #import_value = int(float(import_value)) #try to translate as an integer
                    import_value = float(import_value)
                    if import_value.is_integer():
                        import_value = int(import_value)
                    if import_value == 0 and field_name == "strata": #tree is considered as dead
                        fix_dead = True
                except Exception:
                    import_value = import_value.lower()
                #search for translation through dict_synonyms
                if import_value in dict_list:
                    field_value = import_value
                else:
                    for key, list_value in dict_list.items():
                        if import_value in list_value:
                            field_value = key
                            break
                #if field_value is str (item), capitalize:
                if isinstance(field_value, str):
                    field_value = field_value.capitalize()
            else:
                field_value = import_value
                
            field_def["value"] = field_value
            dict_import["value"] = import_value


    #actions link to the overall dict_trees_import
        #test for longitude/latitude validity, None to location if invalid
        try:
            _test = self.dict_trees_import["longitude"]["value"] * self.dict_trees_import["latitude"]["value"]
        except Exception:
            self.dict_trees_import["longitude"]["value"] = None
            self.dict_trees_import["latitude"]["value"] = None
            self.dict_trees_import["locality"]["value"] = None

        #set the stems number according to the len of tab_stems_dbh
        #excepting if 1 stems in tab_stems_dbh and _stems >=0
        if tab_stems_dbh:
            _stems = self.dict_trees_import["stems"]["value"]
            if len(tab_stems_dbh) == 1 and not _stems:
                _stems = 1
                self.dict_trees_import["stems"]["details"] = "The number of stems was computed from DBH column"
            elif len(tab_stems_dbh) > 1:
                _stems = len(tab_stems_dbh)
                self.dict_trees_import["stems"]["details"] = "The number of stems was computed from DBH column"
            self.dict_trees_import["stems"]["value"] = int(_stems)

        #set to dead if strata = 0
        try:
            if fix_dead:
                self.dict_trees_import["dead"]["value"] = True
                self.dict_trees_import["strata"]["value"] = None
        except Exception:
            pass
        #set auto-calculate columns (leaf_sla, leaf_ldmc, wood_density), if raw data are available in dataline
        #Try to calculate leaf_sla from leaf_area and leaf_dry_weight

        tab_keys = ['leaf_area', 'leaf_fresh_weight', 'leaf_dry_weight', 'wood_core_length','wood_core_diameter', 'wood_core_weight']
        dict_keys = {"leaf_sla": "100 * leaf_area / leaf_dry_weight", 
                     "leaf_ldmc": "1000 * leaf_dry_weight / leaf_fresh_weight",
                     "wood_density": " wood_core_weight / (3.141592654 * wood_core_length * ((wood_core_diameter / 2)**2))"
                     }
        for dict_key, value in dict_keys.items():
            try:
                tabledef = self.dict_trees_import[dict_key]
                if tabledef["value"] is None:
                    msg_details = f"The value of {dict_key} was computed using the formula:\n{value}"
                    for keys in tab_keys:
                        value = value.replace(keys, f"float(self.dict_trees_import['{keys}']['value'])")
                    tabledef["value"] = eval(value)
                    tabledef["details"] = msg_details
            except Exception:
                pass                

            # value = "100 * leaf_area / leaf_dry_weight"
            
            
            # tabledef = self.dict_trees_import[key]
            # if tabledef["value"] is None:
            #     value = 100 * self.dict_trees_import["leaf_area"]["value"] / self.dict_trees_import["leaf_dry_weight"]["value"]
            #     value = eval(value)
            #     tabledef["value"] = value
                #tabledef["import"] = {"column": 'Calculated', "value": value}

        # try:
        #     key = "leaf_ldmc"
        #     tabledef = self.dict_trees_import[key]
        #     if tabledef["value"] is None:            
        #         value = 1000 * float(self.dict_trees_import["leaf_dry_weight"]["value"]) / float(self.dict_trees_import["leaf_fresh_weight"]["value"])
        #         tabledef["value"] = value
        #         #tabledef["import"] = {"column": 'Calculated', "value": value}
        # except Exception:
        #     pass
        # try:
        #     key = "C"
        #     tabledef = self.dict_trees_import[key]
        #     if tabledef["value"] is None:  
        #         value = 314.1592654 * float(self.dict_trees_import["wood_core_length"]["value"])*((float(self.dict_trees_import["wood_core_diameter"]["value"])/2) **2)
        #         value = self.dict_trees_import["wood_core_weight"]["value"] / value
        #         tabledef["value"] = value
        #         #tabledef["import"] = {"value": value}         
        # except Exception:
        #     pass
        #do a check for errors (conversion or min or max)
        for field_name, field_def in self.dict_trees_import.items():
            dict_import = field_def.get("import", None)
            #if dict_import is not None:
                #continue
            if "error" in field_def:
                del field_def["error"]
            #set the final value
            field_value = field_def["value"]
            if field_value:
                #save typed value (as in table, none if not typed and error code add to dict_import definition)
                try:
                    field_def["value"] = get_typed_value(field_name, field_value)
                except ValueError as err:
                    field_def["value"] = None
                    field_def["error"] = err.args[0]
                    no_error = False
        return no_error

    def show_modal(self):
        self.window.exec_()
        
    def close(self):
        self.window.close()       
    
    def validate (self):
        def on_cancel_clicked():
        #cancel transaction
            win_preview.close()
            
        def updateChildItems(item):
            state = item.checkState()
            for row in range(item.rowCount()):
                child = item.child(row)
                if child.isCheckable():
                    child.setCheckState(state)

        def onItemChanged(item):
            if item.isCheckable():
                updateChildItems(item)

        def on_ok_clicked():
        #validate update and insert occurrences from the Preview Updater
            #create a list of exclude id_plot for inserting or updating (add id_plot from unchecked item.data())
            tab_insert_exclude_idplot = [] 
            tab_update_exclude_idplot  = []
            # try:
            #     if item_insert[0].checkState() == 0:
            #         tab_insert_exclude_idplot.append (-1)
            # except Exception:
            #     pass
            # try:
            #     if item_point[0].checkState() == 0:
            #         tab_insert_exclude_idplot.append (0)
            # except Exception:
            #     pass
            for row in range(item_insert.rowCount()):
                if item_insert.child(row, 0).checkState() == 0:
                    tab_insert_exclude_idplot.append (item_insert.child(row, 0).index().data(Qt.UserRole))
            for row in range(item_update.rowCount()):
                if item_update.child(row, 0).checkState() == 0:
                    tab_update_exclude_idplot.append (item_update.child(row, 0).index().data(Qt.UserRole))
        
            #read the items value in table_imported_csv to create sql statement
            list_toUpdate = []
            list_toInsert = []
            list_points = []
            index_locality = column_indexes["locality"]
            index_longitude = column_indexes["longitude"]
            index_latitude = column_indexes["latitude"]

            for idplot, ls_list_update in dict_imported_csv.items():
                #test for exclusion of unchecked id_plot (cf. model, previously checked)
                if idplot <= 0 and idplot in tab_insert_exclude_idplot:
                    continue
                elif idplot in tab_update_exclude_idplot:
                    continue

                for list_update in ls_list_update:
                    #check values for dbase compatibility (NULL/None and Text), and create list of sql statement
                    row = 0
                    _tmp =[]
                    _tabcolumn = []
                    _tabvalue = []
                    identifier = list_update[index_identifier]
                    for value in list_update:
                        if value:
                            field_name = tab_column[row]
                            str_value = get_str_value(value)
                            if row in tab_index_text: #columns cast as text (cf. previous)
                                str_value = "'" + str_value + "'"
                            #set the correct value to the list
                            list_update[row] = str_value
                            #do not include identifier and fields not in table trees in the update statement
                            if field_name in column_trees:
                                _tabcolumn.append(field_name)
                                _tabvalue.append(str_value)
                                if row != index_identifier:
                                    _tmp.append (field_name + " = " + str_value)
                        row += 1
                    if _tmp and identifier and idplot > 0:
                        sql_query =  f"UPDATE {DBASE_SCHEMA_TREES} SET {', '.join(_tmp)} WHERE identifier = '{identifier}' AND id_plot = {idplot};"
                        list_toUpdate.append(sql_query)
                    elif _tabvalue:
                        if idplot == 0: #new point, (longitude & latitude and no identifier or not in the current table trees)
                            latitude = list_update[index_latitude]
                            longitude = list_update[index_longitude]
                            locality = list_update[index_locality]
                            locality = str(locality).strip("'")
                            #create a couple of query, first try to insert a new plot (nothing if conflict (see dbase constraint)) 
                            # and second to insert treesthen select plot
                            sql_toInsert = f"""
                            INSERT INTO {DBASE_SCHEMA_PLOTS} (plot, locality, longitude, latitude, type)
                            VALUES ('{identifier}', '{locality}', {longitude}, {latitude}, 'Point')
                            ON CONFLICT DO NOTHING;
                            INSERT INTO {DBASE_SCHEMA_TREES} (id_plot, {', '.join(_tabcolumn)})
                            SELECT id_plot, {', '.join(_tabvalue)}
                            FROM {DBASE_SCHEMA_PLOTS}
                            WHERE longitude = {longitude} AND latitude = {latitude} AND type = 'Point';
                            """
                            sql_toInsert = sql_toInsert.replace("'None'", 'NULL')
                            list_points.append(sql_toInsert)
                        else:
                            str_id_plot = str(idplot)
                            if idplot == -1:
                                str_id_plot = str(dict_db_plot["id_plot"]["value"])
                            sql_toInsert = f"""
                            INSERT INTO {DBASE_SCHEMA_TREES} (id_plot, {', '.join(_tabcolumn)})
                            VALUES ({str_id_plot}, {', '.join(_tabvalue)})
                            ON CONFLICT (id_plot, identifier) DO NOTHING RETURNING identifier;
                            """          
                            list_toInsert.append (sql_toInsert)
                    # list_update[-1:] = [str(id_plot)]
                    # list_toInsert.append ("\n(" + ', '.join(list_update) + ")")

        #execute query
            sql_toInsert =''
            sql_toUpdate = ''
            self.rows_imported = 0
            #to create a log journal, save les id_tree et id_history max
            sql_log = """SELECT 
                            (SELECT 
                                max(id_tree) 
                            FROM 
                                plots.trees
                            ) AS id_tree,
                            (SELECT 
                                max(id_history) 
                            FROM 
                                plots.trees_history
                            ) AS id_history
                  """
            query = QtSql.QSqlQuery(sql_log)
            query.next()
            id_tree = query.value("id_tree")
            id_history = query.value("id_history")

            if list_points:
                sql_toInsert = "\n".join(list_points)
                self.rows_imported += len(list_points)
                #print (sql_toInsert)
                database_execute_query(sql_toInsert)
            if list_toInsert:
                sql_toInsert = "\n".join(list_toInsert)
                self.rows_imported += len(list_toInsert)
                #print (sql_toInsert)
                database_execute_query(sql_toInsert)
            if list_toUpdate:
                sql_toUpdate = "\n".join(list_toUpdate)
                self.rows_imported += len(list_toUpdate)
                #print (sql_toInsert)
                database_execute_query(sql_toUpdate)
            win_preview.close()

            #to detect change
            sql_log = f"""
                        SELECT 
                            b.sql, 
                            a.* 
                        FROM 
                            plots.trees a 
                        INNER JOIN 
                            (SELECT 
                                'UPDATE' sql, 
                                id_tree 
                             FROM 
                                plots.trees_history 
                            WHERE 
                                id_history > {id_history}
                            UNION
                            SELECT 
                                'INSERT' sql, 
                                id_tree 
                            FROM 
                                plots.trees 
                            WHERE 
                                id_tree > {id_tree}
                            ) b 
                        ON 
                            a.id_tree = b.id_tree
                        ORDER BY 
                            id_tree ASC
                    """
            query = QtSql.QSqlQuery(sql_log)
            while query.next():
                print (query.value(0), query.value(1), query.value(2))
                
            self.close()
            
            
    #Begining of the core function
        self.buttonOK = True
        tab_index_text = []
        tab_column = []
        index_identifier = -1
        column_indexes = {}
        column_trees = {}

        #get current values from dict_db_plot
        current_collection = dict_db_plot["collection"]["value"]
        current_locality = dict_db_plot["locality"]["value"]
        current_plot = dict_db_plot["plot"]["value"]
        id_plot = dict_db_plot["id_plot"]["value"]
        
        row = 0
        #get index of columns to casted as text type (for quick access in next loop)
        for field_name, field_def in self.dict_trees_import.items():
            #create a tab_index, a list of index of columns to casted as text type in the next loop
            tab_column.append(field_name)
            column_indexes[field_name] = row
            if field_name in dict_db_tree:
                column_trees[field_name] = row
            if field_def["type"] in ["text", "memo"]:
                tab_index_text.append(row)
            if field_name == "identifier": 
                index_identifier = row
            row += 1

    #manage preview for updating and adding trees
        dict_imported_csv = self.get_table_update()
    #load a query to get details on plots
        list_str_idplot = [str(key) for key in dict_imported_csv.keys() if key > 0]
        #create the sql_satement of found plots for display
        sql_query = f"""
                        SELECT 
                            '{current_collection}' AS collection, 
                            '{current_locality}' AS locality, 
                            NULL AS plot, 
                            0 AS id_plot
                        FROM 
                            {DBASE_SCHEMA_PLOTS}
                        UNION
                        SELECT 
                            '{current_collection}' AS collection, 
                            '{current_locality}' AS locality, 
                            NULL AS plot, 
                            -1 AS id_plot
                        FROM 
                            {DBASE_SCHEMA_PLOTS}
                    """
        if list_str_idplot:
                    sql_query += f"""
                        UNION
                        SELECT 
                            collection, 
                            locality, 
                            plot, 
                            id_plot
                        FROM 
                            {DBASE_SCHEMA_PLOTS}
                        WHERE 
                            id_plot IN ({", ".join(list_str_idplot)})                        
                    """
        sql_query += "\nORDER BY plot, locality, collection"
        
        query = QtSql.QSqlQuery(sql_query)
        #load the model for treeview            
        tab_header = ["Plot", "Locality", "Collection", "Count"]
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(tab_header)
        model.setColumnCount(4)
        font = QtGui.QFont()
        font.setBold(True)
        
        #create the three root nodes
        #nodes for new inventory points (idplot = 0)
        #tab_adding = dict_imported_csv.get(0, [])
        # item_point = [QtGui.QStandardItem("Adding inventory points"), None, None, QtGui.QStandardItem(str(len(tab_adding)))]
        # item_point[0].setFont(font)
        # model.appendRow(item_point)

        #nodes for new occurrences in current plot (idplot = -1)
        #tab_inserted = dict_imported_csv.get(-1, [])
        item_insert = QtGui.QStandardItem("Adding occurrences") ##,None, None, QtGui.QStandardItem(str(len(tab_inserted)+len(tab_adding)))]
        item_insert.setFont(font)
        item_insert.setCheckable(True)
        item_insert.setCheckState(Qt.Checked)
        model.appendRow(item_insert)
            
        #nodes for new occurrences other plots (idplot >0)
        item_update = QtGui.QStandardItem("Updating occurrences")
        item_update.setFont(font)
        item_update.setCheckable(True)
        item_update.setCheckState(Qt.Checked)
        model.appendRow(item_update)

        #browse the query result and add result if some
        total_updated = 0
        total_inserted = 0
        while query.next():
            id_plot = query.value("id_plot")
            ls_imported = dict_imported_csv.get(id_plot, None)
            if not ls_imported:
                continue
            count = len(ls_imported)
            if id_plot == 0:
                    item = [
                                QtGui.QStandardItem("Inventory points"),None, None,
                                QtGui.QStandardItem(str(count))
                            ]
                    item_insert.appendRow(item)
                    total_inserted += count
                    #item = item_point
            else:
                if id_plot > 0:
                    item = [
                                QtGui.QStandardItem(query.value("plot")),
                                QtGui.QStandardItem(query.value("locality")),
                                QtGui.QStandardItem(query.value("collection")),
                                QtGui.QStandardItem(str(count))
                            ]
                    total_updated += count
                    item_update.appendRow(item)
                else:
                    item = [
                                QtGui.QStandardItem(current_plot),
                                QtGui.QStandardItem(current_locality),
                                QtGui.QStandardItem(current_collection),
                                QtGui.QStandardItem(str(count))
                            ]
                    total_inserted += count
                    item_insert.appendRow(item)

            #set the id_plot to the parent item
            item[0].setCheckable(True)
            item[0].setCheckState(Qt.Checked)  
            item[0].setData(id_plot, role=Qt.UserRole)
            #append the child rows to item
            for row in dict_imported_csv[id_plot]:
                row_item = [QtGui.QStandardItem(str(row[index_identifier]))]
                if id_plot == 0:
                    locality = row[column_indexes["locality"]]
                    if locality:
                        #locality = current_locality
                        row_item.append(QtGui.QStandardItem(str(locality)))
                    #row_item.append(QtGui.QStandardItem(current_collection)) 
                item[0].appendRow (row_item)
        #set the total account of updated row
        model.setItem(item_update.row(), 3, QtGui.QStandardItem(str(total_updated)))
        model.setItem(item_insert.row(), 3, QtGui.QStandardItem(str(total_inserted)))
        
        #load UI for preview and fill the treeview
        win_preview = uic.loadUi("ui/pn_update_preview.ui")
        win_preview.buttonBox.accepted.connect(on_ok_clicked)
        win_preview.buttonBox.rejected.connect(on_cancel_clicked)
        trview_result = win_preview.trView_preview
        trview_result.setModel(model)
        model.itemChanged.connect(onItemChanged)
        #trview_result.setExpanded(item_update.index(), True)
        # trview_result.setExpanded(item_insert.index(), True)
        for column in range(model.columnCount()):
                trview_result.resizeColumnToContents(column)
        # Stretch the first column
        trview_result.header().setStretchLastSection(False)
        trview_result.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        #open the preview
        win_preview.exec_()





###MAIN WINDOWS
#Class CustomDelegate is used by the MainWindow class to edit the properties of the trees and plots
class CustomDelegate(QtWidgets.QStyledItemDelegate):
    dataChanged = QtCore.pyqtSignal(str, object)  # Signal after data is changed
    textUpdated = QtCore.pyqtSignal(str, object)  # Signal during text edition
    def __init__(self, parent=None):
        super().__init__(parent)
        self.valid = False
        self.table_def = dict_db_ncpippn
        self.currentIndex = None
        self.text_editor = None

    def get_header (self, index):
        #return the lower case name in the column 0
        row = index.row()
        return index.sibling(row, 0).data(Qt.DisplayRole).lower()
    def is_enabled(self, index):
        header = self.get_header (index)
        return self.table_def[header].get('enabled', True)

    def paint(self, painter, option, index):
        # Paint row according to excluded columns
        if not self.is_enabled(index): #and not enabled: #header in self.exclude_columns:
            option = QtWidgets.QStyleOptionViewItem(option)
            self.initStyleOption(option, index)
            option.palette.setColor(QtGui.QPalette.Text, QtGui.QColor(120, 120, 120))  # Couleur grise pour le texte
            font = QtGui.QFont()
            font.setItalic(True)
            #font.setPointSize(11)
            option.font = font
            super().paint(painter, option, index)        
        else:
            super().paint(painter, option, index)
    
    def handle_event (self):
    #handle editing of text and emit textUpdated signal
        self.valid = True
        if not isinstance (self.text_editor, QtWidgets.QLineEdit):
            return
        try:
            header = self.get_header (self.currentIndex)
            value = self.text_editor.text()
            self.textUpdated.emit(header, value)
        except Exception:
            return       

    def createEditor(self, parent, option, index):
    #create the editor according to the field type
        self.valid = False
        self.currentIndex = index
        self.text_editor = None
        header = self.get_header (index)
        if index.column() == 0 or not self.is_enabled(index): #header in self.exclude_columns:
            return None
        #get the field definition
        field_def = self.table_def.get(header, {})
        if not field_def:
            return
        #create editor according to the field type
        if field_def["type"] == 'boolean':
            return
        elif "items" in field_def:
            editor = QtWidgets.QComboBox(parent)
            editor.addItems(field_def["items"])
            if field_def.get("editable", False):
                editor.setEditable(True)
                editor.lineEdit().setFont (editor.font())
        elif field_def["type"] == 'integer':
            editor = QtWidgets.QSpinBox(parent)
            editor.setSingleStep(1)
            if "min" in field_def:
                editor.setMinimum(field_def["min"])
            if "max" in field_def:
                editor.setMaximum(field_def["max"])
        elif field_def["type"] == 'numeric':
            editor = QtWidgets.QDoubleSpinBox(parent)
            editor.setMaximum(float(1E6))          
            decimals = field_def.get("decimal", PLOT_DEFAULT_DECIMAL)
            if decimals <= 2:
                editor.setSingleStep(1)
            else:
                editor.setSingleStep(0.1)
            editor.setDecimals(decimals)
            if "min" in field_def:
                editor.setMinimum(field_def["min"])                               
            if "max" in field_def:
                editor.setMaximum(field_def["max"]) 
        elif field_def["type"] == 'memo':
            editor = QtWidgets.QTextEdit(parent)
            editor.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        else:
            editor = QtWidgets.QLineEdit(parent)
            editor.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.text_editor = editor
        #set the tooltip            
        _tip = field_def.get("tip", header)
        if "unit" in field_def:
            _unit = field_def["unit"]
            _tip += " (" + _unit + ")"
        if _tip != header:
            editor.setToolTip (_tip)            
        #set the slot events
        if isinstance (editor, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
            editor.valueChanged.connect(self.handle_event)
        elif isinstance (editor, QtWidgets.QComboBox):
            editor.currentTextChanged.connect(self.handle_event)
        else:
            editor.textChanged.connect(self.handle_event)
        return editor

    def setEditorData(self, editor, index):
    #set the value to the editor
        value = index.data(Qt.EditRole)
        value = get_str_value(value)
        try:
            if isinstance(editor, QtWidgets.QComboBox):
                if isinstance(value, int):
                    editor.setCurrentIndex(value)
                else:
                    editor.setCurrentText(value)
            elif isinstance(editor, QtWidgets.QSpinBox):
                editor.setValue(int(value))
            elif isinstance(editor, QtWidgets.QDoubleSpinBox):
                if len(value) > 0:
                    value = float(str(value).replace(",", "."))
                    editor.setValue(float(value))
            else:
                editor.setText(str(value))
        except Exception:
            pass

    def setModelData(self, editor, model, index):
    #set the value to the model through a signal
        if not self.valid : 
            return
        header = self.get_header (index)
        #get the field definition
        field_def = self.table_def.get(header, {})
        if not field_def:
            return
        #check for value, do not alter the model, emit signal dataChanged
        if isinstance(editor, QtWidgets.QComboBox):
            if editor.currentText().strip() == "":
                value = None
            elif field_def["type"] in ['integer', 'numeric']:
                value = editor.currentIndex()
            else:
                value = editor.currentText()
        elif isinstance(editor, QtWidgets.QSpinBox):
            value = int(editor.value())
        elif isinstance(editor, QtWidgets.QDoubleSpinBox):
            decimals = field_def.get("decimal", PLOT_DEFAULT_DECIMAL)
            value = round(float(editor.value()), decimals)
        elif isinstance(editor, QtWidgets.QTextEdit):
            value = editor.toPlainText()
        else:
            value = editor.text()
        self.dataChanged.emit(header, value)
        #model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)



# Subclass QtWidgets.QMainWindow to customize your application's main window
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        #get copy of dbase dictionnaries for user modifications
        self.dict_user_plot = copy.deepcopy(dict_db_plot)
        self.dict_user_tree = copy.deepcopy(dict_db_tree)
        self.current_collection = None

        # load the GUI
        self.ui = uic.loadUi("ui/plots.ui")

        #add the treeview_searchtaxa widget
        self.treeview_searchtaxa = PN_TaxaSearch()
        layout = self.ui.QTreeViewSearch_layout
        layout.addWidget(self.treeview_searchtaxa)
        self.treeview_searchtaxa.selectionChanged.connect(self.set_buttons_taxa_enabled)
        self.treeview_searchtaxa.doubleClicked.connect(self.treeview_searchtaxa_dbleClicked)

        #add statusBar
        self.statusLabel = QtWidgets.QLabel('Select a Collection', self)
        self.ui.statusBar().addWidget(self.statusLabel) 
        
        #add a frame with a button / menu export
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("background-color: transparent;")
        frame_layout = QtWidgets.QHBoxLayout(frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        export_button = QtWidgets.QPushButton()
        export_button.setText("Export data")
        export_menu = QtWidgets.QMenu()
        menu_items = ["Plots", "Trees", "Taxa", "Occurrences"]
        for item in menu_items:
            action = QtWidgets.QAction(item, self)
            action.triggered.connect(lambda checked, item=item: self.export_menu(item.lower()))
            export_menu.addAction(action)
        export_button.setMenu(export_menu)
        frame_layout.addWidget(export_button)        
        self.ui.statusBar().addPermanentWidget(frame)

        #add new/delete button to buttonBox_tree
        self.button_apply_tree = self.ui.buttonBox_tree.button(QtWidgets.QDialogButtonBox.Apply)
        self.button_cancel_tree = self.ui.buttonBox_tree.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_new_tree = QtWidgets.QPushButton("New")
        self.button_new_tree.setIcon(QtGui.QIcon.fromTheme("document-new"))
        self.button_delete_tree = QtWidgets.QPushButton("Delete")
        self.button_delete_tree.setIcon(QtGui.QIcon.fromTheme("edit-delete"))

        #add new/delete button on buttonBox_plot
        self.button_apply_plot = self.ui.buttonBox_plot.button(QtWidgets.QDialogButtonBox.Apply)
        self.button_cancel_plot = self.ui.buttonBox_plot.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_new_plot = QtWidgets.QPushButton("New")
        self.button_new_plot.setIcon(QtGui.QIcon.fromTheme("document-new"))
        self.button_delete_plot = QtWidgets.QPushButton("Delete")
        self.button_delete_plot.setIcon(QtGui.QIcon.fromTheme("edit-delete"))

        #set buttons disabled by default
        self.button_apply_tree.setEnabled(False)
        self.button_new_tree.setEnabled(False)
        self.button_new_plot.setEnabled(False)
        self.button_cancel_tree.setEnabled(False)
        self.button_delete_tree.setEnabled(False)
        self.button_apply_plot.setEnabled(False)
        self.button_cancel_plot.setEnabled(False)
        self.button_delete_plot.setEnabled(False)
        self.ui.frame_history_slider.setVisible(False)

        #add buttons to buttonBox
        self.ui.buttonBox_tree.addButton(self.button_new_tree, QtWidgets.QDialogButtonBox.ActionRole)
        self.ui.buttonBox_tree.addButton(self.button_delete_tree, QtWidgets.QDialogButtonBox.ActionRole)
        self.ui.buttonBox_plot.addButton(self.button_new_plot, QtWidgets.QDialogButtonBox.ActionRole)
        self.ui.buttonBox_plot.addButton(self.button_delete_plot, QtWidgets.QDialogButtonBox.ActionRole)

        #connect to the database
        connected_indicator = PN_DatabaseConnect()
        self.ui.statusBar().addPermanentWidget(connected_indicator)
        connected_indicator.open()        
        if not connected_indicator.dbopen:
            return #return if not open
        self.db = connected_indicator.db
        init_context(AppContext(connected_indicator))
        
        #self.trview_identity = self.ui.trView_resume
        self.PN_trview_identity = PN_JsonQTreeView ()
        layout = self.ui.tabWidget_tree.widget(3).layout()
        layout.addWidget(self.PN_trview_identity)
        self.PN_trview_identity.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        #connect slot to function event
        self.ui.tabWidget_tree.currentChanged.connect(self.fill_trview_resume)
        self.button_new_plot.clicked.connect(self.button_new_plot_click)
        self.button_new_tree.clicked.connect(self.button_new_tree_click)
        self.button_apply_tree.clicked.connect(self.button_apply_tree_click)
        self.button_apply_plot.clicked.connect(self.button_apply_plot_click)
        self.button_delete_tree.clicked.connect(self.button_delete_tree_click)
        self.button_delete_plot.clicked.connect(self.button_delete_plot_click)
        self.button_cancel_tree.clicked.connect(self.button_cancel_tree_click)
        self.button_cancel_plot.clicked.connect(self.button_cancel_plot_click)
        self.ui.comboBox_collections.currentIndexChanged.connect(self.load_collections)
        self.ui.comboBox_types.activated.connect(self.load_plots)
        self.ui.filter_button_dead.toggled.connect(self.load_trees)
        self.ui.filter_button_historical.toggled.connect(self.load_trees)
        self.ui.filter_button_trait.toggled.connect(self.load_trees)
        self.ui.filter_button_fruit.toggled.connect(self.load_trees)
        self.ui.filter_button_flower.toggled.connect(self.load_trees)
        self.ui.filter_button_allometry.toggled.connect(self.load_trees)
        self.ui.button_replace_taxa.clicked.connect(self.replace_taxanames)
        self.ui.button_add_synonym.clicked.connect(self.add_synonym)
        self.ui.slider_history.valueChanged.connect(self.slider_history_seturrentIndex)
        self.ui.button_import_trees.clicked.connect(self.button_import_trees_click)
        self.ui.lineEdit_identifier.textChanged.connect(self.load_plots) 
        
        #set the editors delegate to Qtableview(s)
        self.delegate = CustomDelegate()
        self.ui.tableView_tree.setItemDelegate(self.delegate)
        self.ui.tableView_plot.setItemDelegate(self.delegate)
        self.delegate.dataChanged.connect(self.data_changed)
        self.delegate.textUpdated.connect(self.text_changed)

        #set the dragdrop
        self.ui.tableView_plots.setDragEnabled(True)
        self.ui.treeView_collections.setAcceptDrops(True)
        self.ui.treeView_collections.dropEvent = self.treeView_collections_dropEvent
        self.ui.treeView_collections.dragEnterEvent = self.treeView_collections_dragEnterEvent
        self.ui.tableView_trees.setDragEnabled(True)
        self.ui.tableView_plots.setAcceptDrops(True)
        self.ui.tableView_plots.dropEvent = self.tableview_plots_dropEvent

        #execute a selection on combobox collections
        self.button_new_plot.setEnabled(True)
        self.ui.comboBox_collections.setCurrentIndex(0)

    def export_menu(self, item):
    #export data to CSV file
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.ReadOnly
        #options |= QtWidgets.QFileDialog.DontUseNativeDialog
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setNameFilter("Fichiers CSV (*.csv)")
        file_dialog.setDefaultSuffix("csv")
        file_name, _ = file_dialog.getSaveFileName(
            None, "Export to CSV File", "", "CSV Files (*.csv);;All files (*)", options=options)
        #exit of no file name
        if not file_name:
            return
        #check for csv extension
        if not file_name.lower().endswith(".csv"):
            file_name += ".csv"
        delimiter = ';'
    #export either plots, trees, taxa and occurrences
        sql = ""
        data = []
        if item == 'plots':
            sql = f"SELECT * FROM {DBASE_SCHEMA_PLOTS} ORDER BY plot"
        elif item == 'taxa':
            data = self.ui.tblView_resolution.model().getdata(True)        
        elif item in  ('trees', 'occurrences'):
            ls_trees_fields = []
            for column, value in dict_db_tree.items():
                if value.get('enabled', True):
                    ls_trees_fields.append("a." + column)
            if item == 'occurrences':
                for column, value in dict_db_plot.items():
                    if value.get('enabled', True) and column not in ('radius'):
                        ls_trees_fields.append("b." + column)
            sql = f"""
                    WITH query AS 
                        (SELECT {','.join(ls_trees_fields)}, b.id_plot, a.id_tree
                        FROM
                        {DBASE_SCHEMA_TREES} a
                        INNER JOIN {DBASE_SCHEMA_PLOTS} b ON a.id_plot = b.id_plot
                        {self.get_trees_sql_where()}
                        ORDER BY taxaname)
                    SELECT b.taxonref, a.*, b.id_taxonref AS id_taxa
                    FROM query a
                    LEFT JOIN {DBASE_SCHEMA_TAXONOMY}.pn_taxa_searchnames (array(select DISTINCT taxaname::TEXT from query)) b
                    ON a.taxaname = b.original_name
                    ORDER BY identifier
                """
        if sql:
            #print (sql)
            query = self.db.exec(sql)
            if query.isActive():
                record = query.record()
                data.append([record.fieldName(x) for x in range(record.count())])
                while query.next():
                    _data = []
                    for x in range(record.count()-1):
                        _value = get_str_value(query.value(record.fieldName(x)))
                        if delimiter in _value:
                            _value = '"' + _value + '"'
                        _data.append(_value)
                    data.append(_data)
        #write the data into the CSV file_name
        with open(file_name, "w", newline="") as file:
            writer = csv.writer(file, delimiter=delimiter, skipinitialspace = True, quotechar='"', quoting=csv.QUOTE_NONNUMERIC)
            writer.writerows(data)
    
    def set_dict_dbase(self, id, table):
    #fill the dict_dbase (tree or plot) from database and reload the dict_user (plot or tree)
        if table == 'plots':
            sql_select = f"SELECT * FROM {DBASE_SCHEMA_PLOTS} WHERE id_plot = {id}"
            dict_user = dict_db_plot
        elif table == 'trees':
            #list of fields
            ls_fields = []
            for dbcolumn, field_def in dict_db_tree.items():
                if dbcolumn not in ["history"]:
                    ls_fields.append(dbcolumn)
            sql_fields = ", ".join(ls_fields)
            sql_select = f"SELECT {sql_fields} FROM {DBASE_SCHEMA_TREES} WHERE id_tree = {id} UNION "
            sql_select += f"SELECT {sql_fields} FROM {DBASE_SCHEMA_TREES}_history WHERE id_tree = {id}"
            sql_select += "\nORDER BY time_updated DESC"
            dict_user = dict_db_tree
            dict_db_tree["history"]["items"] = []
            dict_db_tree["history"]["value"] = 0
        else:
            return
        #set the dictionnary values to None
        for dbcolumn, field_def in dict_user.items():
            field_def["value"] = None
        #if id, set data from the sql query (including historical data for trees)
        list_db_tree_history = []
        if id:
            #play the query and set the data to dict_user
            query = self.db.exec(sql_select)
            _tmp = dict_user
            while query.next():
                for dbcolumn in _tmp.keys():
                    value = None
                    try:
                        if query.record().indexOf(dbcolumn) != -1:
                            if not query.isNull(dbcolumn):
                                value = query.value(dbcolumn)
                            _tmp[dbcolumn]["value"] = value
                    except Exception:
                        pass
                #in case of plots, only one row is returned
                #in case of trees, the next rows come from tree history
                list_db_tree_history.append(_tmp)
                _tmp = copy.deepcopy(dict_db_tree)
                    #elf.load_tree_history()
        elif table == 'trees':
            #new tree, set the default values
            dict_user["dead"]["value"] = False
            dict_user["month"]["value"] = dict_user["month"]["default"] # datetime.now().month        
            dict_user["year"]["value"] = dict_user["year"]["default"] #datetime.now().year
        elif table == 'plots':
            #new plot, set the default values
            for key in ["collection", "locality", "type", "width", "length", "radius"]:
                dict_user[key]["value"] = self.dict_user_plot[key]["value"]
                    #set default values for null values
            if not dict_user["type"]["value"]:
                dict_user["type"]["value"] = dict_user["type"]["default"]
            if not dict_user["width"]["value"]:
                dict_user["width"]["value"] = 0
                dict_user["length"]["value"] = 0
                dict_user["radius"]["value"] = 0

        #in any case ajust dict_user trees and plots
        if table == 'plots':
            dict_user['radius']["value"] = dict_user['width']["value"]
            self.dict_user_plot = copy.deepcopy(dict_user)
        elif table == 'trees':
            #restore history index to 0
            dict_user["history"]["value"] = 0
            dict_user["history"]["items"] = list_db_tree_history[1:]
            self.dict_user_tree = copy.deepcopy(dict_user)


    def get_dict_update(self, table):
    #return a update dictionnary to save in the database (={"id":id,  "table":table, + fields with value})
        dict_user = {}
        if table == "trees":
            dict_user = self.dict_user_tree
            field_id = "id_tree"
        elif table == "plots" :
            dict_user = self.dict_user_plot
            field_id = "id_plot"
        id = dict_user[field_id]["value"]
        #detect for new record
        isNew = not isinstance(id, int)
        if isNew:
            id = None
        dict_update ={"id":id, "table":table}
        #create the tab_update according to the field_def properties (visible, enabled)
        for field_name, field_def in dict_user.items():
            if not field_def.get ("enabled", True):
                continue
            #must be visible and New or Changed
            if field_def.get ("visible", True) and (isNew or field_def.get ("changed", False)) :
                value = field_def["value"]
                if field_name == "radius":
                    field_name = "width"
                dict_update[field_name] = value
        #if fields to update
        if len(dict_update) > 2:
            return dict_update
        return {}

    def update_data_ui (self, dict_update):
    #update the UI according to the dict_update
        #local function
        def update_tableview_data( model, column_id):
        #Internal function to update model of tableview (trees or plot) according to dict_update
            dict_headers = {model.headerData(i, Qt.Horizontal):i for i in range(model.columnCount()) if dict_update.get(model.headerData(i, Qt.Horizontal), False)}
            if not dict_headers:
                return
            #loop on the model to search for tab_ids and columns to update
            for row in range(model.rowCount()):
                index = model.index(row, column_id)
                if model.data(index, role = Qt.UserRole) in tab_ids:
                    for key, column in dict_headers.items():
                        value = self.tableview_formated_value(dict_update[key])
                        rowindex = index.siblingAtColumn(column)
                        model.setData(rowindex, value, role=Qt.DisplayRole)
    ######begining of the main function
        #get the id(s) set to a list of integer
        tab_ids = dict_update["id"]
        if not isinstance(tab_ids, list):
            tab_ids = [tab_ids]
        tab_ids = list(map(int, tab_ids))
        #set the model
        if dict_update["table"] == "plots":
            model = self.ui.tableView_plots.model()
            #model_edit = self.ui.tableView_plot.model()
        else:
            model = self.ui.tableView_trees.model()
            #model_edit = self.ui.tableView_tree.model()
        #refresh tableview plots and trees (both if plots because of commons plot name)
        
        update_tableview_data (model, 0)
        if dict_update["table"] == "plots":
            update_tableview_data(self.ui.tableView_trees.model(), 1)
        # print ("before update_tableview_data")
        #search for update in row headers of tree and plot edition lists
        # num_rows = model_edit.rowCount()
        # id = tab_ids[0]
        # dict_user = {model_edit.index(i, 0).data().lower():i for i in range(num_rows) if dict_update.get(model_edit.index(i, 0).data().lower(), False)}
        # if id and dict_user:
        #     if model_edit.index(0, 1).data() == id:
        #         for key, row in dict_user.items():
        #             value = self.tableview_formated_value(dict_update[key])
        #             model_edit.item(row, 1).setData(value, role = Qt.DisplayRole)
        # print ("after update_tableview_data")
    #if collection/locality in dict_update, update the list of collections and refresh plots
        if dict_update.get(self.current_collection, False):
            self.load_collections(dict_update[self.current_collection])
            self.load_plots(id)
            self.create_dict_user(False)
    #in any case update/refresh the tableview_resolution if taxaname updated
        if dict_update.get("taxaname", False):
            self.load_taxa()
            self.tableview_resolution_selectedItem(dict_update["taxaname"])
                                
    def save_dict_update(self, dict_update):
    #create the sql statement related to dict_update (dictionnary of update composed of id, table + fields and values)
        #define field_id (id_tree or id_plot)
        field_id = 'id_plot'
        table = dict_update["table"]
        if table == "trees":
            field_id = 'id_tree'
            dict_update["time_updated"] = QtCore.QDateTime.currentDateTime()
        #manage id, as a list of string for SQL 
        ids = dict_update['id']
        if ids:
            if not isinstance(ids, list):
                ids = [ids]
            tab_ids = list(map(str, ids))
            ids = ",".join(tab_ids)
        #create tab for update, check for type coherence according to dict_db_ncpippn (dbase) definition        
        tab_update = []
        sql_column = []
        sql_value = []
        for key, value in dict_update.items():
            if isinstance(value, list):
                continue
            if key in ['id', 'table']:
                continue
            #transform value in sql string
            value = get_typed_value(key.lower(), value, True)
            if not value:
                continue
            tab_update.append(key + "=" + str(value))
            #add to insert if not NULL
            if value != 'NULL':
                sql_column.append(key)
                sql_value.append(str(value))
        #execute INSERT
        if sql_column and not ids: #new, execute Insert
            sql_query = f"INSERT INTO {DBASE_SCHEMA}.{table}"
            sql_query += f"({', '.join(sql_column)}) VALUES ({', '.join(sql_value)})"
            sql_query += f"\nRETURNING {field_id}"
        else: #or execute UPDATE
            sql_query = f"UPDATE {DBASE_SCHEMA}.{table}"
            sql_query += "\nSET " + ", ".join (tab_update)
            sql_query += f"\nWHERE {field_id} IN ({str(ids)})"
            sql_query += f"\nRETURNING {field_id}"
        #return if no sql_query
        if len(sql_query) == 0:
            return False
        
        #execute query (return id_plot/id_tree for insert/update)
        result = database_execute_query(sql_query)

        #Refresh UI if refresh is enabled (by default)
        if result and dict_update.get("refresh", True):
            #restore dict_db from database (trees or plots)
            self.set_dict_dbase(result, table)
            dict_update["id"] = result
            if table == "trees" and not ids: #a new tree was created (result by RETURNING id_tree)
                self.load_trees(id_tree = result)
            self.update_data_ui (dict_update)
            self.show_dict_user()
            
            
        #in any case (refresh or not) return True if result
        if result:
            return True
        else:
            return False
        


    def tableview_formated_value(self, value):
    #return the value formatted to be display in a tableview (plots, trees, plot, tree)
        if isinstance(value, QtCore.QDateTime):
            value = value.toString("yyyy/MM/dd")
        else:
            value = get_str_value(value)
        return value

    def tableview_trees_filter(self, item):
        #create a filter on table_view_trees from an input item
        taxa =""
        if item:
            taxa = item.data()
        self.ui.tableView_trees.model().setFilterFixedString(taxa)

    def tableview_trees_add_item(self, model, id_tree, id_plot, tab_tree):
    #add an item to the table_view_trees from a list tab_tree
        tab_items = []
        for item in tab_tree:
            item = self.tableview_formated_value(item)
            item = QtGui.QStandardItem(item)
            tab_items.append(item)
        tab_items[0].setData(id_tree, role=Qt.UserRole)
        tab_items[1].setData(id_plot, role=Qt.UserRole)
        model.appendRow(tab_items)
        return tab_items[0]
            
    def tableview_trees_del_items(self):
    #delete selected trees from the tableView_trees.model()
        selection_model = self.ui.tableView_trees.selectionModel()
        selection_model.selectionChanged.disconnect(self.create_dict_user)
        selected_indexes = self.ui.tableView_trees.selectionModel().selectedRows()
        model = self.ui.tableView_trees.model()
        rows = [item.row() for item in selected_indexes]
        # reverse the list to avoid messing up the indices
        if rows:
            rows.sort(reverse=True)
            for row in rows:
                model.removeRow(row)            
            index = self.ui.tableView_trees.currentIndex()
            self.ui.tableView_trees.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
            self.create_dict_user()
            self.load_taxa()
        selection_model.selectionChanged.connect(self.create_dict_user)
    
    def tableView_plots_del_items(self):
    #delete selected plot from the tableView_plots.model()
        selection_model = self.ui.tableView_plots.selectionModel()
        selection_model.selectionChanged.disconnect(self.tableview_plots_selectionChanged)
        selected_indexes = self.ui.tableView_plots.selectionModel().selectedRows()
        model = self.ui.tableView_plots.model()
        rows = [item.row() for item in selected_indexes]
        # reverse the list to avoid messing up the indices
        if rows:
            rows.sort(reverse=True)
            for row in rows:
                model.removeRow(row)            
            index = self.ui.tableView_plots.currentIndex()
            self.ui.tableView_plots.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
            self.tableview_plots_selectionChanged()
        selection_model.selectionChanged.connect(self.tableview_plots_selectionChanged)

    def tableview_plots_selectionChanged(self):
    #a tableview_plots slot, set resolution_model and resume.setModel to None to enforce load_taxa
        self.ui.tblView_resolution.setModel(None)
        self.PN_trview_identity.setModel(None)
        self.load_trees()
        self.fill_trview_resume()

    def tableview_plots_dropEvent(self, event):
    #manage drop event on treeView_collections
        super().dropEvent(event)
        #event.ignore()
        target_index = self.ui.tableView_plots.indexAt(event.pos()).siblingAtColumn(0)
        #row = self.ui.tableView_trees.currentIndex() #target_index.row()
        #self.ui.tableView_plots.viewport().update()
        if event.source() == self.ui.tableView_trees:
            # selection = self.ui.tableView_plots.selectionModel()
            # selection.selectionChanged.disconnect()
            if target_index.isValid() : #and target_index.parent().isValid():
                selected_indexes = self.ui.tableView_trees.selectionModel().selectedRows()
                ids = [str(index.data(role=Qt.UserRole)) for index in selected_indexes]
                new_idplot = str(target_index.data(Qt.UserRole))
                msg = f"Are you sure to move the selected occurrence(s)\n to the plot < {target_index.data()} >?"
                if QtWidgets.QMessageBox.question(None, "Move Occurrences", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                    dict_update = {"id":ids, "table": "trees", "id_plot":new_idplot, "refresh":False}
                    #self.save_dict_update(dict_update)
                    if self.save_dict_update(dict_update):
                        self.tableview_trees_del_items()
                        #self.load_taxa()
        event.ignore()
        # QTest.mouseClick(self.ui.tableView_plots.viewport(), Qt.RightButton, Qt.NoModifier, QPoint(-100, -100))
        # return
        ###########################
        #simulate a click at the top-left corner of the viewport to hide DropIndicator (not a normal situation, it's just the way I found)
        #  Temporarily disable selections
        self.ui.tableView_plots.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        pos = QtCore.QPoint(-1, -1)
        mouse_event_press = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        mouse_event_release = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QtWidgets.QApplication.sendEvent(self.ui.tableView_plots.viewport(), mouse_event_press)
        QtWidgets.QApplication.sendEvent(self.ui.tableView_plots.viewport(), mouse_event_release)
        # Re-enable selections
        self.ui.tableView_plots.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # Restore the previous selection mode
        # Update the viewport to hide the drop indicator
        self.ui.tableView_plots.viewport().update()

    def tableview_resolution_selectedItem(self, taxa_search):
    #set the taxa_search in the tblView_resolution        
        model = self.ui.tblView_resolution.model()
        if model is None: 
            return
        for row in range(model.rowCount()):
            if model.index(row, 0).data() == taxa_search:
                self.ui.tblView_resolution.setCurrentIndex(model.index(row, 0))

    def treeView_collections_dragEnterEvent(self, event):
    #allow drag on treeView_collections only for self.ui.tableView_plots
        if event.source() == self.ui.tableView_plots:
            event.accept()

    def treeView_collections_dropEvent(self, event):
    #manage drop event on treeView_collections
        super().dropEvent(event)
        target_index = self.ui.treeView_collections.indexAt(event.pos())
        if not target_index.parent().isValid():
            return
        #self.ui.treeView_collections.viewport().update()
        if event.source() == self.ui.tableView_plots:
            if target_index.isValid():
                selected_indexes = self.ui.tableView_plots.selectionModel().selectedRows()
                ids = [str(index.data(role=Qt.UserRole)) for index in selected_indexes]                
                itemText = str(target_index.data()) #.replace("'", "''")
                msg = f"Are you sure to move the selected plot(s)\n to the {self.current_collection} < {target_index.data()} >?"
                if QtWidgets.QMessageBox.question(None, "Move Plot", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                    if itemText == '< unclassified >':
                        itemText = None
                    dict_update = {"id":ids, "table": "plots", self.current_collection:itemText, "refresh": False}
                    self.save_dict_update(dict_update)
                    self.tableView_plots_del_items()
                    # event.ignore()
                    return
        #add a virtual click to unfreeze treeView_collections
        event.ignore()
        #QTest.mouseClick(self.ui.treeView_collections.viewport(), Qt.LeftButton, Qt.NoModifier, QtCore.QPoint(-1, -1))
        
    def treeView_collections_updateItem(self, index):
    #update the text of a node (collection, locality or plot) in treeView_collections
        new_name = index.data(Qt.DisplayRole).strip("'")
        old_name = index.data(Qt.UserRole).strip("'")
        if new_name == old_name : 
            return
        #create name for postgressql query
        str_new_collection = new_name.replace("'", "''")
        str_old_collection = old_name.replace("'", "''")
        sql_query = f"""UPDATE {DBASE_SCHEMA_PLOTS} 
                        SET {self.current_collection} = '{str_new_collection}' 
                        WHERE {self.current_collection} = '{str_old_collection}'
                    """
        #save into the dbase
        if database_execute_query(sql_query):
            #id_plot = self.get_current_id_plot()
            self.load_collections(new_name)
            #self.load_plots(id_plot)
            self.dict_user_plot[self.current_collection]["value"] = new_name
            #self.set_dict_dbase(id_plot, 'plots')
            self.show_dict_user()

            #self.create_dict_user()
        else:
            #Database error, restore previous text
            index.setData(old_name, Qt.DisplayRole)

    def treeview_searchtaxa_dbleClicked(self, index):
        #new_taxaname = index.siblingAtColumn(0).data()
        new_taxaname = self.treeview_searchtaxa.selectedTaxa()
        if new_taxaname is None:
            return
        tab_name = self.ui.tabWidget_tree.currentWidget().objectName()
    #set the new taxaname
        if tab_name == 'tab_tree':
            self.data_changed("taxaname", new_taxaname)
        elif tab_name == 'tab_taxa':
            index = self.ui.tblView_resolution.currentIndex()
            old_taxaname = index.siblingAtColumn(0).data()
            model = self.ui.tableView_trees.model()
            ids = []
            #create the list of id_tree for occurrences matching with old_taxaname
            for index in model.match(model.index(0, 0), Qt.DisplayRole, old_taxaname, -1, Qt.MatchExactly | Qt.MatchRecursive):
                ids.append(str(index.data(Qt.UserRole)))
            if len(ids) > 0:
                msg = (
                        f"This action will change taxaname '{old_taxaname}' to '{new_taxaname}'\n\n"
                        f"Are you sure to apply transformation for {len(ids)} occurrence(s)?"
                      )
                if QtWidgets.QMessageBox.question(None, "Identification", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                    dict_update = {"id":ids, "table": "trees", "taxaname": new_taxaname}
                    self.save_dict_update (dict_update)

    def slider_history_seturrentIndex(self, index):
    #create the dict_user_tree according to the slider index (0 is current set)
        if dict_db_tree["history"].get("items", None) is None:
            return
        dict_db_tree["history"]["value"] = 0
        if index > 0:
            self.dict_user_tree = dict_db_tree["history"]["items"][index-1]
            dict_db_tree["history"]["value"] = index
        else:
            self.dict_user_tree = copy.deepcopy(dict_db_tree)
        self.show_dict_user()

    def button_import_trees_click(self):
    #import new trees from a csv file in the current plot
        id_plot = self.get_current_id_plot()
        if not id_plot:
            return
        
        dict_import = {}
        tab_column = []
        tab_index_text = []
        row = 0
        #create the dict_import from dict_user_tree with only editable columns
        for field_name, field_def in dict_db_tree.items():
            if not field_def.get("enabled", True) or not field_def.get("visible", True):
                continue
            dict_import[field_name] = copy.deepcopy(field_def)
            dict_import[field_name]["value"] = None
            tab_column.append(field_name)
            #create a tab_index, a list of index of columns to casted as text type in the next loop
            if dict_db_ncpippn[field_name]["type"] in ["text", "memo"]:
                tab_index_text.append(row)
            row += 1
        #add id_plot as last colum
        dict_import["locality"] = copy.deepcopy(dict_db_plot["locality"])
        dict_import["longitude"] = copy.deepcopy(dict_db_plot["longitude"])
        dict_import["latitude"] = copy.deepcopy(dict_db_plot["latitude"])
        tab_column.append("id_plot")
        #load the class and UI
        CSV_Importer = CSVImporter(dict_import)
        CSV_Importer.load()
        CSV_Importer.show_modal()
        if CSV_Importer.rows_imported > 0:
            self.load_plots()
        print (str(CSV_Importer.rows_imported) + " trees imported")


    def button_new_tree_click(self):
    #add a new tree, copy the current self.dict_user_plot to inherit some values
        #if is an history data, restore it
        index_tree = dict_db_tree["history"]["value"]
        if index_tree > 0:
            msg = "Are you sure to restore the history data as the current record ?"
            msg += "\n all recent data will be deleted"
            if QtWidgets.QMessageBox.question(None, "Restore History", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                id = dict_db_tree["id_tree"]["value"]
                time_updated = self.dict_user_tree["time_updated"]["value"]
                #restore a historical record
                tab_update = []
                #create the update query for any enabled field of the current dict_user_tree (history)
                dict_update = {"id":id, "table": "trees"}
                for field_name, field_def in self.dict_user_tree.items():
                    if field_name in ['id_tree', 'history']:
                        continue
                    if dict_db_tree[field_name].get ("visible", True):
                        value = field_def["value"]
                        #set the value to the dict_db_tree
                        dict_db_tree[field_name]["value"] = value
                        dict_update[field_name] = value                        
                        value = get_typed_value(field_name, value, True)
                        tab_update.append(field_name + " = " + str(value))
                        
                if tab_update:
                    #disable trigger before restoring history data
                    sql_query = f"ALTER TABLE {DBASE_SCHEMA_TREES} DISABLE TRIGGER trigger_on_update;"
                    sql_query += f"\nUPDATE {DBASE_SCHEMA_TREES}"
                    #sql_query += "\nSET " + ", ".join (tab_update)
                    sql_query += f"\nSET {', '.join (tab_update)}"
                    sql_query += f"\nWHERE id_tree = {id};"
                    sql_query += f"\nALTER TABLE {DBASE_SCHEMA_TREES} ENABLE TRIGGER trigger_on_update;"
                    sql_query +=  (
                        f"\nDELETE FROM {DBASE_SCHEMA_TREES}_history"
                        f"\nWHERE id_tree = {id} AND time_updated > TIMESTAMP '{time_updated.toString(DBASE_DATETIME_FORMAT)}' - INTERVAL '0.1 second'"
                            )
                if not database_execute_query(sql_query) :
                    print ('Error on database update', sql_query)
                    return
                #ajust the tree history list of items, keep only oldest records than current one
                dict_db_tree["history"]["items"] = dict_db_tree["history"]["items"][index_tree:]
                dict_db_tree["history"]["value"] = 0
                #update ui for edited value
                self.update_data_ui(dict_update)
        else:
            #set a new dbase record for plot
            self.set_dict_dbase(None, 'trees')
        self.show_dict_user()

    # def set_new_dict_user_trees(self):
    # #set dict_user_trees to new with defaut values
    #     self.set_dict_dbase(None, 'trees')
        #set default values for NEW
        # self.dict_user_tree["dead"]["value"] = False
        # self.dict_user_tree["month"]["value"] = datetime.now().month        
        # self.dict_user_tree["year"]["value"] = datetime.now().year

    def button_new_plot_click(self):
        self.set_dict_dbase(None, 'plots')
        self.show_dict_user()

    def button_apply_tree_click(self):
    #apply changed to trees table
        #verifiy for a valid id_plot
        id_plot = None
        id_plot = self.get_current_id_plot()
        if not id_plot:
            return
        #select indexes of selected rows
        selected_indexes = self.ui.tableView_trees.selectionModel().selectedRows()
        #get the dict update
        dict_update = self.get_dict_update("trees")
        dict_update["id"] = [index.data(role=Qt.UserRole) for index in selected_indexes]
        #add id_plot for insert new
        dict_update["id_plot"] = id_plot
        #save the dict_update
        self.save_dict_update(dict_update)        

    def button_apply_plot_click(self):
    #apply changed to plots table
        #check for coherence in data
        dict_user = self.dict_user_plot
        _type = dict_user["type"]["value"]
        area = None
        msg = None
        #check for value
        try: #check for longitude, latitude (mandatory and in special range)
            long = float (dict_user["longitude"]["value"])
            lat = float (dict_user["latitude"]["value"])
            if long < -180 or long > 180:
                msg = "Error: longitude must be a numeric value between -180 and 180"
            if lat < -90 or lat > 90:
                msg = "Error: latitude must be a numeric value between -90 and 90"
        except Exception:
            msg = "Error: longitude and latitude must have a non-NULL numeric value"

        #check for type
        if not _type:
            msg = "Error: Type must have a non-NULL value (Rectangle, Point or Circle)"
        elif _type == 'Rectangle':
            try:
                area = float (dict_user["width"]["value"]) *  float (dict_user["length"]["value"])
                if area <= 0:
                    msg = "Error: a plot must have a positive area (width x length > 0)"
            except Exception:
                msg = "Error: width or length must have a non-NULL numeric value"
        elif _type == 'Circle':
            try:
                if (float (dict_user["radius"]["value"])  ** 2) <= 0:
                    msg = "Error: a circular plot must have a positive area (radius > 0)"        
            except Exception:
                msg = "Error: radius must have a non-NULL numeric value"

        #return a msg and quit if errors
        if msg:
            QtWidgets.QMessageBox.critical(None, "Database error", msg, QtWidgets.QMessageBox.Ok)
            return
        
        #save self.dict_user_plot if no errors
        dict_update = self.get_dict_update("plots")
        self.save_dict_update(dict_update)

    def button_cancel_tree_click(self):
    #restore the database tree definition
        self.dict_user_tree = copy.deepcopy(dict_db_tree)
        self.show_dict_user()

    def button_cancel_plot_click(self):
    #restore the database plot definition
        self.dict_user_plot = copy.deepcopy(dict_db_plot)
        self.show_dict_user()
    
    def button_delete_tree_click (self):
    #delete selected trees and/or trees history from the database
        index_tree = dict_db_tree["history"]["value"]
        if index_tree > 0:
            msg = "Are you sure to delete the history data ?"
            if QtWidgets.QMessageBox.question(None, "Delete History", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                id = self.dict_user_tree["id_tree"]["value"]
                time_updated = self.dict_user_tree["time_updated"]["value"]
                #select historical record with an interval to ensure capture of the exact time
                sql_query = f"""
                        DELETE FROM 
                            {DBASE_SCHEMA_TREES}_history
                        WHERE 
                            id_tree = {id}
                        AND
                            time_updated BETWEEN TIMESTAMP '{time_updated.toString(DBASE_DATETIME_FORMAT)}' - INTERVAL '0.1 second'
                        AND
                            TIMESTAMP '{time_updated.toString(DBASE_DATETIME_FORMAT)}' + INTERVAL '0.1 second'                        
                    """
                    # f"\nWHERE id_tree = {id} AND time_updated BETWEEN TIMESTAMP '{time_updated.toString(DBASE_DATETIME_FORMAT)}' - INTERVAL '0.1 second'"
                    # f"\nAND TIMESTAMP '{time_updated.toString(DBASE_DATETIME_FORMAT)}' + INTERVAL '0.1 second'"
                        
                if not database_execute_query(sql_query) :
                    print ('Error on database delete', sql_query)
                    return
                #ajust the tree history list of items, delete the current one
                del dict_db_tree["history"]["items"][index_tree-1]
                dict_db_tree["history"]["value"] = 0
                self.dict_user_tree = copy.deepcopy(dict_db_tree)
                self.show_dict_user()
        else:

            msg = "Are you sure to delete the selected occurrence(s) ?"
            msg += "\nThis will remove all history data"
            if QtWidgets.QMessageBox.question(None, "Delete Occurrences", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                selected_indexes = self.ui.tableView_trees.selectionModel().selectedRows()
                ids = [str(index.data(role=Qt.UserRole)) for index in selected_indexes]
                sql_query =  (
                    f"DELETE FROM {DBASE_SCHEMA_TREES}"
                    f"\nWHERE id_tree IN ({', '.join (ids)})"
                        )
        #if database successful
                if not database_execute_query(sql_query) :
                    print ('Error on database delete', sql_query)
                    return
                self.tableview_trees_del_items()

    def button_delete_plot_click (self):
    #delete selected plot from the database
        #ids = str(id)
        plot_name = self.dict_user_plot["plot"]["value"]
        msg = f"Are you sure to delete the plot < {plot_name} > ?"
        msg += "\nThis will also remove all occurrences related to this plot"
        if QtWidgets.QMessageBox.question(None, "Delete Plot", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            id = self.dict_user_plot["id_plot"]["value"]            
            sql_query =  (
                    f"DELETE FROM {DBASE_SCHEMA_PLOTS}\nWHERE id_plot = {id}"
                    )
            if not database_execute_query(sql_query) :
                print ('Error on database delete', sql_query) #for debugging
                return
 
            #update the model to reflect database update
            row = 0
            try:
                model = self.ui.tableView_plots.model()
                for row in range(model.rowCount()):
                    index = model.index(row, 0)
                    if model.data(index, role = Qt.UserRole) == id:
                        model.removeRow(row)
                        selected_index = model.index(max(0, row-1),0)
                        self.ui.tableView_plots.setCurrentIndex(selected_index)
                        break
            except Exception:
                pass


    def load_collections(self, itemText = None):
        model = QtGui.QStandardItemModel()
        #if not self.dbopen: return
        if itemText == -1:
            return
        #print ("load_collections", itemText)
    #load the collection from the selected column (collection or locality)
        self.current_collection = self.ui.comboBox_collections.currentText().lower() 
        self.statusLabel.setText('Select a ' + self.current_collection)
        #create the sql statement
        sql_query = f"""SELECT 
                            collection, 
                            locality 
                        FROM 
                            {DBASE_SCHEMA_PLOTS}
                        GROUP BY 
                            collection, locality
                        ORDER BY 
                            {self.current_collection} NULLS FIRST
                    """
        query = self.db.exec(sql_query) 

        ls_collection = ['']
        ls_localities = ['']
        _dict_collection = {}
        item_root = QtGui.QStandardItem("< Plots >")
        model.appendRow(item_root)
       
        while query.next():
            #get values from query
            root_node = str(query.value(self.current_collection))
            locality = str(query.value("locality"))
            collection = str(query.value("collection"))
            #manage unreferenced plot
            if query.isNull(self.current_collection):
                root_node = "< unclassified >"
            else:
                root_node = str(query.value(self.current_collection))
            # manage a local dictionnary to conserve the root nodes
            if root_node not in _dict_collection:
                _dict_collection[collection] = []
                collectionItem = QtGui.QStandardItem()
                collectionItem.setData(root_node, Qt.DisplayRole)
                collectionItem.setData(root_node, Qt.UserRole)
                item_root.appendRow([collectionItem])
                _dict_collection[root_node] = collectionItem
            # create the list of collection/localities for edition
            if collection not in ls_collection:
                ls_collection.append(collection)
            if locality not in ls_localities:
                ls_localities.append(locality)
        
        #set the collections and localities lists in the dict_db_plot
        dict_db_plot["collection"]["items"] = sorted(ls_collection)
        dict_db_plot["locality"]["items"] = sorted(ls_localities)        
        #set the model
        self.ui.treeView_collections.setModel(model)
        
        #disconnect the slot (if connected) before selecting
        selection_model = self.ui.treeView_collections.selectionModel()
        if itemText in[0,1]:
            #connect slot before (load_plots will be fired)
            selection_model.selectionChanged.connect(self.load_plots)
            item = model.index(0, 0)
            self.ui.treeView_collections.setCurrentIndex(item)
            self.ui.treeView_collections.expand(item_root.index())
        elif itemText in _dict_collection:
            item = _dict_collection[itemText]
            #connect slot after (load_plots will not be fired)
            self.ui.treeView_collections.setCurrentIndex(item.index())
            selection_model.selectionChanged.connect(self.load_plots)
        #connect the slots for editing
        model.itemChanged.connect(self.treeView_collections_updateItem)

        
    def load_plots(self, id_plot = None):
        #print ("load_plots", id_plot)
    #load the plots according to the selected treeView_collections item (collection or locality)
        model_plots = QtGui.QStandardItemModel()
        try:
            current_terms = self.ui.treeView_collections.currentIndex().data()
            current_terms = current_terms.replace("'", "''")
        except Exception:
            current_terms = None
        if not current_terms:
            return
        
        additional_term = 'collection'
        if self.current_collection == 'collection':
            additional_term = "locality"
        ls_columns = ['plot', additional_term, 'type'] ##, 'longitude', 'latitude', 'altitude']
        model_plots.setHorizontalHeaderLabels(ls_columns)
        

        _plottype = ""
        _tmp = []
        _sqlwhere = ''
        #create the sql statement
        if self.ui.treeView_collections.currentIndex().parent().isValid():
            if current_terms != '< unclassified >':
                _tmp.append(f"{self.current_collection} = '{current_terms}'")
            else:
                _tmp.append(f"{self.current_collection} IS NULL")
        if self.ui.comboBox_types.currentIndex() > 0:
            _plottype = self.ui.comboBox_types.currentText()
            _plottype = f"\nAND type = '{_plottype}'"
            _tmp.append(f"type = '{self.ui.comboBox_types.currentText()}'")


        if self.ui.lineEdit_identifier.text():
            #if len (self.ui.lineEdit_identifier.text()) > 3:
            _tmp.append(f"identifier ILIKE '%{self.ui.lineEdit_identifier.text()}%'")

        if len(_tmp) > 0:
            _sqlwhere = " WHERE " + " AND ".join(_tmp)
        #add virtual name (plot_name) by coalescence when plot is NULL
        # sql_query = f"""SELECT id_plot, COALESCE (plot, LEFT(TYPE, 1) ||  LPAD(id_plot::text, 6, '0')) as plot, {', '.join(ls_columns[1:])} 
        #               FROM ncpippn.plots 
        #               WHERE {self.current_collection} = '{current_terms}'{_plottype}
        #               ORDER BY {self.current_collection}, plot
        #               """
        # sql_query = f"""SELECT id_plot, COALESCE (plot, LEFT(TYPE, 1) ||  LPAD(id_plot::text, 6, '0')) as plot, {', '.join(ls_columns[1:])} 
        #               FROM ncpippn.plots {_sqlwhere}
        #               ORDER BY plot
        #               """        
        # sql_query = f"""SELECT id_plot, plot, {', '.join(ls_columns[1:])} 
        #               FROM {DBASE_SCHEMA_PLOTS} {_sqlwhere}
        #               ORDER BY plot
        #               """

        #if self.ui.lineEdit_identifier.text():
            #if len (self.ui.lineEdit_identifier.text()) > 3:
        sql_query = f"""
                        SELECT 
                            a.id_plot, 
                            plot, 
                            {', '.join(ls_columns[1:])} 
                        FROM 
                            {DBASE_SCHEMA_PLOTS} a 
                        LEFT JOIN 
                            plots.trees b 
                        ON 
                            a.id_plot = b.id_plot {_sqlwhere}
                        GROUP BY 
                            a.id_plot, a.plot, a.locality, a.type
                        ORDER BY
                            plot
                      """       
        query = self.db.exec(sql_query)
        #add the plot to the model_plots
        selected_index = None
        while query.next():
            tab_items = []
            for column in ls_columns:
                item = query.value(column)
                #format value in str
                if query.isNull(column):
                    item = None
                elif isinstance(item, QtCore.QDateTime):
                    item = item.toString(DBASE_DATETIME_FORMAT)
                else:
                    item = str(item)
                #add value to model
                item = QtGui.QStandardItem(item)
                tab_items.append(item)
            
            if tab_items:
                item_idplot = query.value("id_plot")
                #set the virtual PlotName
                tab_items[0].setData(query.value("plot"), role = Qt.DisplayRole)
                tab_items[0].setData(item_idplot, role = Qt.UserRole)
                model_plots.appendRow(tab_items)
                if item_idplot == id_plot:
                    selected_index = tab_items[0].index()
        
        self.ui.tableView_plots.setModel(model_plots)
        self.ui.tableView_plots.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        #resize to content except taxa column (= stretch)
        self.ui.tableView_plots.resizeColumnsToContents()
        header = self.ui.tableView_plots.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        #disconnect slot (if connected) before updated
        selection = self.ui.tableView_plots.selectionModel()
        #selection.selectionChanged.disconnect()
        if not selected_index:
            #select the first row and connect slot before updating selection
            selected_index = model_plots.index(0,0)
            selection.selectionChanged.connect(self.tableview_plots_selectionChanged)
            self.ui.tableView_plots.setCurrentIndex(selected_index)
        else:
            #set the current selected_index and connect slot after updating (not load_trees fired)
            self.ui.tableView_plots.setCurrentIndex(selected_index)
            self.ui.tableView_plots.scrollTo(selected_index, QtWidgets.QAbstractItemView.PositionAtCenter)
            selection.selectionChanged.connect(self.tableview_plots_selectionChanged)
    
    def get_trees_sql_where(self):
    #construct the sql where statement for the trees table according to buttons filters
        try:
            selected_indexes = self.ui.tableView_plots.selectionModel().selectedRows()
        except Exception:
            selected_indexes = None
        if selected_indexes is None :
            return
        #create the sql_where statement
        _tabtmp = []
        #add id_plot selection
        first_column_indexes = [index.sibling(index.row(), 0) for index in selected_indexes]
        selected_plots = ",".join([str(index.data(Qt.UserRole)) for index in first_column_indexes])
        _tabtmp.append(f"a.id_plot IN ({selected_plots})")
        #add others filters
        if self.ui.filter_button_dead.isChecked():
            _tabtmp.append("dead iS NOT TRUE")
        if self.ui.filter_button_trait.isChecked():
            _tabtmp.append("COALESCE (bark_thickness, leaf_area, leaf_sla, leaf_ldmc, wood_density) IS NOT NULL")
        if self.ui.filter_button_fruit.isChecked():
            _tabtmp.append("fruit")
        if self.ui.filter_button_flower.isChecked():
            _tabtmp.append("flower")            
        if self.ui.filter_button_allometry.isChecked():
            _tabtmp.append("dbh IS NOT NULL AND height IS NOT NULL")

        # if self.ui.lineEdit_identifier.text():
        #     if len (self.ui.lineEdit_identifier.text()) > 3:
        #         _tabtmp.append(f"identifier ILIKE '%{self.ui.lineEdit_identifier.text()}%'")
        #         _tabtmp = _tabtmp[1:]
        #create the final sql statement (add where accordind to _tabtmp)
        if len (_tabtmp) > 0:
            #sql_select += f"\nWHERE {' AND '.join(_tabtmp)}"
            return f"WHERE {' AND '.join(_tabtmp)}"

    def get_properties_json(self):
    #return the json properties for the selected plots
        #get the list of selected id_plot 
        selected_indexes = self.ui.tableView_plots.selectionModel().selectedRows()
        if not selected_indexes:
            return
        idplots = ', '.join([str(index.data(role=Qt.UserRole)) for index in selected_indexes])
        #get the sql query for the traits
        fieldname = ['dbh','height', 'bark_thickness', 'leaf_area', 'leaf_ldmc', 'leaf_sla', 'wood_density']
        tab_sql = []
        for item in fieldname:
            decimal = list_db_fields[item].get("decimal", PLOT_DEFAULT_DECIMAL)
            unit = list_db_fields[item].get("unit", 'NULL')
            sql = f"""SELECT 
                        '{item}' as key, count({item}), round(avg({item}), {decimal}) as avg, 
                        round(min ({item}), {decimal}) as min, round(max({item}), {decimal}) as max, 
                        round(stddev({item}), {decimal}) as stddev, '{unit}' as unit
                      FROM 
                        trees
                    """
            tab_sql.append(sql)
        #get the phenology, trees infos and strata
        sql =  "SELECT 'flower' as key, count(flower) FILTER (WHERE flower), NULL, NULL, NULL, NULL, NULL FROM trees"
        tab_sql.append(sql)
        sql =  "SELECT 'fruit' as key, count(fruit) FILTER (WHERE fruit), NULL, NULL, NULL, NULL, NULL FROM trees"
        tab_sql.append(sql)
        #get the strata distribution
        sql ="""SELECT 
                    'strata' as key, 
                    count(id_tree) FILTER (WHERE lower(strata) ='understorey'), 
                    count(id_tree) FILTER (WHERE lower(strata) ='sub-canopy'), 
                    count(id_tree) FILTER (WHERE lower(strata) ='canopy'), 
                    count(id_tree) FILTER (WHERE lower(strata) ='emergent'), NULL, NULL 
                  FROM trees
             """
        tab_sql.append(sql)
        #get the trees infos
        sql =  "SELECT 'trees' as key, count(id_tree), count(id_tree) FILTER (WHERE dead IS NOT True), count(DISTINCT taxaname), NULL, NULL, NULL FROM plots"
        tab_sql.append(sql)
        #get the richness properties
        ls_idtaxonref = []
        for item in self.ui.tblView_resolution.model()._data:
            ls_idtaxonref.append (item.id_taxonref)
        ls_idtaxonref = ', '.join(map(str,ls_idtaxonref))
        sql_query = f"""
                    SELECT
                        'richness' as key,
                        count(distinct id_family) as families,
                        count(distinct id_genus) as genus,
                        count(distinct id_species) as species,
                        count(distinct id_infra) as infra, NULL, NULL 
                    FROM 
                        taxonomy.taxa_hierarchy
                    WHERE
                        id_taxonref IN ({ls_idtaxonref})
                    """
        tab_sql.append(sql_query)
        #create the union query from tab_sql
        data_sql = " \n UNION\n".join(tab_sql)

        #create the final query
        sql_query = f"""
                    WITH 
                        plots AS (SELECT * FROM plots.trees WHERE id_plot IN ({idplots})),
                        trees AS (SELECT * FROM plots WHERE dead IS DISTINCT FROM True),
                        data AS (
                                {data_sql}
                                )
                        SELECT
                            jsonb_object_agg
                            (
                                key,
                                jsonb_build_object
                                (
                                    'count', count,
                                    'average', avg,
                                    'min', min,
                                    'max', max,
                                    'stddev', stddev,
                                    'unit', unit
                                )
                            ) AS result_json
                        FROM
                            data
                    """

        #execute the query and get the json
        query = self.db.exec(sql_query)
        query.next()
        json_properties = query.value("result_json")
        if json_properties:
            json_properties = json.loads(json_properties)            
            #sort the dict to be more smart
            dict_sort = {} #{'richness': {}}
            fieldname = ['trees', 'richness','flower', 'fruit', 'strata'] + fieldname
            #fill the dict_sort with sorted value
            for item in fieldname:
                dict_sort[item] = {'unit':json_properties[item]['unit'], 'count':json_properties[item]['count'], 'average':json_properties[item]['average'], 
                                   'min':json_properties[item]['min'], 'max':json_properties[item]['max'], 'stddev':json_properties[item]['stddev'] 
                                   }
            #modify some key names (del and create)
            dict_sort['trees']['alive'] = dict_sort['trees'].pop('average')
            dict_sort['trees']['dead'] = dict_sort['trees']['count'] - dict_sort['trees']['alive']
            
            dict_sort['strata']['emergent'] = dict_sort['strata'].pop('max')
            dict_sort['strata']['canopy'] = dict_sort['strata'].pop('min')
            dict_sort['strata']['sub-canopy'] = dict_sort['strata'].pop('count')
            dict_sort['strata']['understorey'] = dict_sort['strata'].pop('average')

            dict_sort['richness']['taxa'] = dict_sort['trees'].pop('min')
            dict_sort['richness']['families'] = dict_sort['richness'].pop('count')
            dict_sort['richness']['genus'] = dict_sort['richness'].pop('average')
            dict_sort['richness']['species'] = dict_sort['richness'].pop('min')
            dict_sort['richness']['infra'] = dict_sort['richness'].pop('max')
            #delete key with None value
            for clef, sous_dico in dict_sort.items():
                dict_sort[clef] = {k: v for k, v in sous_dico.items() if v is not None}
              
            return dict_sort






    def load_trees(self, id_tree = None):
        #if not self.dbopen: return
    #load the main tableview_trees with trees and plot information
        #print ("load_trees", id_tree)
        #clear the list and create a proxy model        
        model_trees = QtGui.QStandardItemModel() #NCPIPPN_tree_model() #
        proxy_model = QtCore.QSortFilterProxyModel()
        proxy_model.setSourceModel(model_trees)
        proxy_model.setFilterKeyColumn(0)

        #create the query according to the treeview selected item and filters
        try:
            selected_indexes = self.ui.tableView_plots.selectionModel().selectedRows()
        except Exception:
            selected_indexes = None
        if selected_indexes is None :
            return


        #create the query
        ls_columns = ['taxaname', 'identifier', 'plot', 'year', 'dead', 'time_updated']
        # sql_select = f"""SELECT id_tree, a.id_plot, {', '.join(ls_columns)} 
        #             FROM {DBASE_SCHEMA_TREES} a
        #             INNER JOIN {DBASE_SCHEMA_PLOTS} b ON a.id_plot = b.id_plot
        #             {self.get_trees_sql_where()}
        #             ORDER BY {ls_columns[0]}
        #     """
        sql_historical = ''
        if self.ui.filter_button_historical.isChecked():
            sql_historical = f"""
                         INNER JOIN 
                            {DBASE_SCHEMA_TREES}_history c 
                        ON 
                            a.id_tree = c.id_tree"""
        
        sql_select = f"""SELECT 
                            a.id_tree, 
                            a.id_plot, 
                            a.{', a.'.join(ls_columns)} 
                        FROM 
                            {DBASE_SCHEMA_TREES} a
                        INNER JOIN 
                            {DBASE_SCHEMA_PLOTS} b 
                        ON a.id_plot = b.id_plot
                        {sql_historical}
                        {self.get_trees_sql_where()}
                        ORDER BY 
                            {ls_columns[0]}
            """
        sql_select = sql_select.replace("a.plot", "b.plot")


        #load the query and fill the model
        query = self.db.exec(sql_select)
        selected_index = None
        #data = []
        while query.next():
            # get value from query
            tab_tree = []
            for column in ls_columns:
                item = query.value(column)
                tab_tree.append(item)
            #append item to the model
            if tab_tree:
                item = self.tableview_trees_add_item (model_trees, query.value("id_tree"), query.value("id_plot"), tab_tree)
                
                if id_tree == query.value("id_tree"):
                    selected_index = item.index()
        #set the model to the list view
        self.ui.tableView_trees.setModel(proxy_model)
        
        model_trees.setHorizontalHeaderLabels(ls_columns)
        #self.ui.tableView_trees.setModel(proxy_model)
        selection_model = self.ui.tableView_trees.selectionModel()
        selection_model.selectionChanged.connect(self.create_dict_user)
        
        #resize to content except taxa column (= stretch)
        self.ui.tableView_trees.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        self.ui.tableView_trees.resizeColumnsToContents()
        header = self.ui.tableView_trees.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        
        #load the taxa if model is Null
        if not self.ui.tblView_resolution.model():
            self.load_taxa()        
        #select the first row (and trigger the function create_dict_user()), if empty force create_dict_user
        if selected_index:
            proxy_index = proxy_model.mapFromSource(selected_index)
            self.ui.tableView_trees.setCurrentIndex(proxy_index)
            self.ui.tableView_trees.scrollTo(proxy_index, QtWidgets.QAbstractItemView.PositionAtCenter)
        elif model_trees.rowCount() > 0:
            self.ui.tableView_trees.setCurrentIndex(proxy_model.index(0, 0))
        else: #no trees, force create_dict_user() to set new tree
            self.create_dict_user()


    def load_taxa(self):
        #print ("load_taxa")
        #get the list of unique taxa in the tableView_trees
        model_trees = self.ui.tableView_trees.model()
        unique_taxa = set()
        compte_taxa = {}
        compte_trees = 0
        for row in range(model_trees.rowCount()):
            taxaname = model_trees.index(row, 0).data()
            if taxaname :
                compte_trees += 1
                unique_taxa.add(taxaname)
                compte_taxa[taxaname] = compte_taxa.get(taxaname, 0) + 1

        # simpson = 0
        # p_count = compte_trees * (compte_trees -1)
        # if p_count > 0:
        #     for taxa, count in compte_taxa.items():
        #         simpson += (count * (count - 1)) / p_count
        # self.dict_user_plot["simpson"]["value"] = simpson

        
        #create a PN_taxa_resolution_model from the list of unique_taxa
        self.ui.tblView_resolution.setModel(PN_taxa_resolution_model())
        #create sql statement from unique_taxa
        items_sql = ', '.join([f"'{item}'" for item in unique_taxa])
        sql_query = f"""
                    SELECT 
                        * 
                    FROM 
                        {DBASE_SCHEMA_TAXONOMY}.pn_taxa_searchnames(array[{items_sql}]) a
                    WHERE 
                        original_name IS NOT NULL 
                    ORDER BY 
                        original_name
                    """
        #sql_query += "\nWHERE original_name IS NOT NULL ORDER BY original_name"
        data = []
        query = self.db.exec (sql_query)
        #add item as a PNsynonym class
        #set_family = set()
        while query.next():
            newRow = PNSynonym(
                            query.value("original_name"), 
                            query.value("taxonref"),
                            query.value("id_taxonref") 
                            )
            data.append(newRow)
            #set_family.add(query.value("id_family"))
        if len(data) > 0:
            #reset the model and repaint the tblView_resolution
            self.ui.tblView_resolution.hideColumn(1)
            self.ui.tblView_resolution.resizeColumnsToContents()
            header = self.ui.tblView_resolution.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            selection = self.ui.tblView_resolution.selectionModel()
            selection.selectionChanged.connect(self.set_treeview_searchtaxa_text)
            self.ui.tblView_resolution.model().resetdata(data)
            self.ui.tblView_resolution.doubleClicked.connect(self.tableview_trees_filter)

    def fill_trview_resume(self):
        #fill the trview_resume, only if model is None and current tab is 'tab_resume' (to avoid query)
        tab_name = self.ui.tabWidget_tree.currentWidget().objectName()
        if tab_name != 'tab_resume':
            return
        if self.PN_trview_identity.model(): #set to None self.tableview_plots_selectionChanged
            return
        self.PN_trview_identity.setData (self.get_properties_json())

    def set_treeview_searchtaxa_text(self, item):
        #reset the potential filter
        self.ui.tableView_trees.model().setFilterFixedString(None)
        #and set the text value to the treeview_searchtaxa
        try:
            self.treeview_searchtaxa.setText(item.indexes()[0].data())
        except Exception:
            self.treeview_searchtaxa.setText('')
            pass
    
    def create_dict_user(self, refresh = True):
    #function to fill the properties pannel (plot and tree) from the selected item
        #call by slot on tableview_trees selectionChanged
        index = self.ui.tableView_trees.currentIndex()
        id_tree = index.siblingAtColumn(0).data(Qt.UserRole)
        # model = self.ui.tableView_trees.model()
        # source_index = model.mapToSource(index)
        # id_tree = model.sourceModel().get_idtree (source_index.row())

        id_plot = self.get_current_id_plot()
        if id_plot != dict_db_plot["id_plot"]["value"]:
            self.set_dict_dbase(id_plot, 'plots')
        #if no id_trees set a new trees
        if id_tree != dict_db_tree["id_tree"]["value"]:
            self.set_dict_dbase(id_tree, 'trees')
            self.tableview_resolution_selectedItem(dict_db_tree["taxaname"]["value"])
        if refresh:
            self.show_dict_user()


    def show_dict_user(self):
    #fill the the two tableViews (tree and plot) with the two dict_user (dict_user_plot and dict_user_tree)
        def fill_model(dict):
            is_changed = False
            model = QtGui.QStandardItemModel()
            for field_name, field_def in dict.items():
                visible = field_def.get("visible", True)
                if not visible:
                    continue
                item = QtGui.QStandardItem()
                item1 = QtGui.QStandardItem()            
                field_name = str(field_name).capitalize()
                value = field_def["value"]
                type = field_def.get("type", 'text')
                item.setData(field_name, Qt.DisplayRole)
                if type == 'date'and value:
                    value = value.toString("d MMMM yyyy")
                if type == 'boolean':
                    #add checkbox item for boolean
                    item1.setCheckable(True)
                    if value:
                        item1.setCheckState(Qt.Checked)
                    #manage enabled for checkbox
                    _enabled = field_def.get("enabled", True) and is_editable and is_alive
                    if field_name.lower() == "dead" and is_editable and not is_alive:
                        _enabled = True
                    item1.setEnabled(_enabled)
                elif field_def.get("items", None): 
                    if isinstance(value, int):
                        value = field_def["items"][value]
                    item1.setData(value, Qt.DisplayRole)
                else:
                    item1.setData(value, Qt.DisplayRole)
                if field_def.get("changed", False):
                    font = QtGui.QFont()
                    font.setUnderline(True) 
                    item.setFont(font)
                    is_changed = True

                model.appendRow([item, item1])
                model.itemFromIndex(model.index(0,0)).setData(is_changed, Qt.UserRole)
                model.itemChanged.connect(self.checkbox_changed)
                #set the changed flag as a data role on the cell (0,0)
            return model, is_changed
        
    #update the dict_user according to type (calculate area and manage visibility of rows)
    #check for plot
        is_alive = True
        is_editable = True
        area = None
        nb_plots = self.ui.tableView_plots.model().rowCount()
        nb_trees = self.ui.tableView_trees.model().rowCount()
        nb_plot_selected = len(self.ui.tableView_plots.selectionModel().selectedRows())
        nb_trees_selected = len(self.ui.tableView_trees.selectionModel().selectedRows())
        msg = f"{nb_plots} Plot(s), {nb_plot_selected} selected - {nb_trees} Tree(s)"

        _suffix = "Taxon"
        if nb_trees > 0:
            nb_taxa =  self.ui.tblView_resolution.model().rowCount()
            nb_unresolved_taxa =  self.ui.tblView_resolution.model().unresolvedCount()
            if nb_taxa > 1:
                _suffix = "Taxa"
            msg += f", {nb_trees_selected} selected, {nb_taxa} {_suffix}"
            #if nb_unresolved_taxa > 0:
            msg += f" ({nb_unresolved_taxa} unresolved)"


        self.statusLabel.setText(msg)

        _type = self.dict_user_plot["type"]["value"]
        if _type:
            _type = _type.lower()
        _width = self.dict_user_plot["width"]["value"]
        _radius = self.dict_user_plot["radius"]["value"]
        _length = self.dict_user_plot["length"]["value"]
        is_rectangle = (_type == 'rectangle')
        is_circle = (_type == 'circle')
        #check for width and length to define type, area and width name
        if is_rectangle:
            try:
                area = _width * _length
            except Exception:
                area = '<< error >>'
        elif is_circle:
            try:
                area = 3.141592654 * (_radius ** 2)
            except Exception:
               area = '<< error >>'
        self.dict_user_plot["area"]["value"] = area        
        #set the visibility of some rows according to type
        self.dict_user_plot["width"]["visible"] = is_rectangle
        self.dict_user_plot["length"]["visible"] = is_rectangle
        self.dict_user_plot["radius"]["visible"] = is_circle
        self.dict_user_plot["area"]["visible"] = (is_rectangle or is_circle)
        #self.dict_user_plot["plot"]["visible"] = (is_rectangle or is_circle)
        #set the enabled of edit buttons for plot
        id_plot = dict_db_plot["id_plot"]["value"]
        is_plot = isinstance(id_plot, int)
        self.button_delete_plot.setEnabled(is_plot)
        self.ui.button_import_trees.setEnabled(is_plot)
        #fill the model with dict_user_plot values
        model_plot,is_plot_changed = fill_model(self.dict_user_plot)
        #get the flag for plot changed (data.index(0,0), QT.userrole)
        #is_plot_changed = self.model_changed (model_plot)
        self.button_apply_plot.setEnabled(is_plot_changed)
        self.button_cancel_plot.setEnabled(is_plot_changed)
        #set the model and resize columns
        self.ui.tableView_plot.setModel(model_plot)
        self.ui.tableView_plot.resizeColumnsToContents()
        header = self.ui.tableView_plot.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)

    # for trees, manage visibility of rows according to _type
        self.dict_user_tree["x"]["visible"] = is_rectangle
        self.dict_user_tree["y"]["visible"] = is_rectangle
        is_current = dict_db_tree["history"]["value"] == 0
        is_alive = not dict_db_tree["dead"]["value"]
        is_editable = (is_plot and is_current)
        #check for new tree (if not plot) and multiple selection
        if not is_plot:
        #set to new tree if no plot
            self.set_dict_dbase(None, 'trees')
        elif nb_trees_selected > 1:
            #Set visibility of rows if multiple selection on self.ui.tableView_trees
            for key in self.dict_user_tree:
                if key.lower() not in ['id_tree','taxaname', 'month', 'year', 'strata', 'flower', 'fruit']:
                    self.dict_user_tree[key]["visible"] = False
        #fill the model
        model_tree, is_tree_changed = fill_model(self.dict_user_tree)
        #is_tree_changed = self.model_changed (model_tree)

        #set the edit triggers
        if is_editable and is_alive:
            self.ui.tableView_tree.setEditTriggers(QtWidgets.QTableView.CurrentChanged | QtWidgets.QTableView.SelectedClicked)
        elif not is_alive: #mode read only if dead
            self.ui.tableView_tree.setEditTriggers(QtWidgets.QTableView.NoEditTriggers)
        else: #mode read only if history or not id_plot
            self.ui.tableView_tree.setEditTriggers(QtWidgets.QTableView.NoEditTriggers)
            is_tree_changed = False
        
        #set the enabled of edit buttons for tree            
        id_tree = self.dict_user_tree["id_tree"]["value"]
        is_tree = isinstance(id_tree, int)
        self.button_delete_tree.setEnabled(is_tree)
        self.button_apply_tree.setEnabled(is_tree_changed) # and is_plot)
        self.button_cancel_tree.setEnabled(is_tree_changed)
        self.button_new_tree.setEnabled(is_plot)
        self.ui.frame_history_slider.setVisible(False)
        # set model to tableView_tree
        self.ui.tableView_tree.setModel(model_tree)
        
        # resize columns
        self.ui.tableView_tree.resizeColumnsToContents()
        header = self.ui.tableView_tree.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)         

        #set the default height and  default height (4 rows visible) for memo field
        default_height = self.ui.tableView_tree.verticalHeader().defaultSectionSize()
        for row in range(model_tree.rowCount()):
            item = model_tree.item(row, 0)
            self.ui.tableView_tree.setRowHeight(row, default_height)
            if dict_db_tree[item.text().lower()]["type"] == 'memo':
                self.ui.tableView_tree.verticalHeader().resizeSection(row, 4*default_height)
        
        #set the history slider
        if not is_tree:
             return        
        try:
            self.ui.slider_history.valueChanged.disconnect(self.slider_history_seturrentIndex)
            list_db_tree_history = dict_db_tree["history"]["items"]
            self.ui.history_year_max.setText(str(dict_db_tree["time_updated"]["value"].date().year()))
            self.ui.history_year_min.setText(str(list_db_tree_history[-1]["time_updated"]["value"].date().year()))
            self.ui.slider_history.setMaximum(len (list_db_tree_history)) 
            self.ui.slider_history.setValue(dict_db_tree["history"]["value"])
            self.ui.frame_history_slider.setVisible(True)
        except Exception:
            self.ui.frame_history_slider.setVisible(False)
        self.ui.slider_history.valueChanged.connect(self.slider_history_seturrentIndex)
        #switch the text of the new button
        if is_current:
            self.button_new_tree.setText("New")
        else:
            self.button_new_tree.setText("Restore")

    def get_current_id_plot(self):
    #get the current id_plot, first from a tree if selected and from the treeView_collections (selected item or first item) if no tree selected 
        try:
            index = self.ui.tableView_trees.currentIndex()
            id_plot = index.siblingAtColumn(1).data(Qt.UserRole)
            #id_plot = self.ui.tableView_trees.model().sourceModel().get_idplot(index.row())
            if not id_plot: #search for plot selection in tableview_plots
                index = self.ui.tableView_plots.currentIndex()
                id_plot = index.siblingAtColumn(0).data(role=Qt.UserRole)
            return id_plot
        except Exception:
            return
     
#manage changes in data coming from signals (checkbox and delegate)
    def checkbox_changed(self, itemcheckable):
    #only managed checkbox
        model= self.ui.tableView_tree.model()
        header = model.indexFromItem(itemcheckable).siblingAtColumn(0).data().lower()
        if dict_db_ncpippn[header]["type"] != 'boolean':
            return
        value = None
        if itemcheckable.checkState() == 2:
            value = True
        self.data_changed (header, value)

    def text_changed(self, header, new_value):
    #signal when a text is currently changed
        if header != "taxaname":
            return
        self.treeview_searchtaxa.setText(new_value)

    def data_changed(self, header, new_value):
    #manage all data update througth delegate
        dict_user = self.dict_user_plot | self.dict_user_tree
        dict_header = dict_user[header]
        dict_header["value"] = new_value
        dict_header["changed"] = (new_value !=  dict_db_ncpippn[header]["value"])      
        self.show_dict_user()

    def set_buttons_taxa_enabled(self):
    #set the buttons Replace/synonym to enabled according to the selected taxa in resolution and treeview_score_taxa
        selecteditem = self.ui.tblView_resolution.currentIndex()
        selectedtaxa = self.treeview_searchtaxa.currentIndex()
        # print (selectedtaxa)

        is_enabled = selecteditem.isValid() and selectedtaxa.isValid()
        self.ui.button_replace_taxa.setEnabled (is_enabled)
        self.ui.button_add_synonym.setEnabled (is_enabled)

        #check for other constraints
        if is_enabled:
            selecteditem = self.ui.tblView_resolution.model().data(selecteditem, Qt.UserRole)
            if selectedtaxa.parent().isValid():
                selectedtaxa = selectedtaxa.parent()
            is_resolved = selecteditem.resolved
            is_different = (selecteditem.id_taxonref != selectedtaxa.data(Qt.UserRole))
       
        self.ui.button_replace_taxa.setEnabled (is_enabled and is_different)
        self.ui.button_add_synonym.setEnabled (is_enabled and not is_resolved)

    def replace_taxanames(self):
        index = self.treeview_searchtaxa.currentIndex()
        self.treeview_searchtaxa_dbleClicked(index)
        

    def add_synonym(self):
        #function calls by button signals
        def on_cancel_clicked():
            ui_syno.close()
        def on_ok_clicked():
            synonym_type = ui_syno.comboBox.currentText()
            sql_query = f"SELECT {DBASE_SCHEMA_TAXONOMY}.pn_names_add ('{selecteditem.synonym}','{synonym_type}',{str_idtaxonref})"
            ui_syno.close()
            if not database_execute_query(sql_query):
                print ("Error edit synonyms:", sql_query)
            self.load_taxa()
            
    #main function defition
        index = self.ui.tblView_resolution.currentIndex()
        selecteditem = self.ui.tblView_resolution.model().data(index, Qt.UserRole)
        selectedtaxa = self.treeview_searchtaxa.currentIndex()
        selectedtaxa = self.treeview_searchtaxa.selectedTaxonRef()
        str_idtaxonref = self.treeview_searchtaxa.selectedTaxaId()
        if selectedtaxa is None:
            return
        if not selecteditem:
            return
        if selecteditem.resolved:
            return
        ui_syno = uic.loadUi("ui/pn_editname.ui")
        ui_syno.setMaximumHeight(1)
        ui_syno.label_tip.setText('Add synonym...')
        ui_syno.taxaLineEdit.setText(selectedtaxa)
        ui_syno.name_linedit.setText(selecteditem.synonym)
        ui_syno.name_linedit.setEnabled(False)
        ui_syno.buttonBox.accepted.connect(on_ok_clicked)
        ui_syno.buttonBox.rejected.connect(on_cancel_clicked)
        ui_syno.exec_()

    def close(self):
        self.ui.close()

    def show(self):
        self.ui.show()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    with open("ui/Diffnes.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)

    window = MainWindow()
    window.show()
    app.exec()

