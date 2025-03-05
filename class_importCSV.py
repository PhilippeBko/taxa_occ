import sys
import pandas as pd
from PyQt5 import QtSql, QtGui,  uic, QtWidgets, QtCore
from commons import flower_reg_pattern, fruit_reg_pattern, list_db_fields
from PyQt5.QtCore import Qt
import math as mt
import re
PLOT_DEFAULT_DECIMAL = 2
DBASE_DATETIME_FORMAT = "yyyy-MM-dd hh:mm:ss.zzz t"
dict_strata = {
    "understorey": [1, "sous-bois", "sotobosque", "understory"], 
    "sub-canopy": [2, "sous-canopée", "sub-cubierta"], 
    "canopy": [3, "canopée", "cubierta"], 
    "emergent": [4, "émergent","emergente"]
}
dict_month = {
    1: ["enero","january","janvier", "janv.", "jan.", "ene."], 
    2: ["febrero","february", "février", "feb.", "fev.", "fév."], 
    3: ["marzo", "march", "mars"],
    4: ["abril", "april", "avril"], 
    5: ["mayo", "may", "mai"], 
    6: ["junio", "june", "juin"],
    7: ["julio", "july", "juillet"], 
    8: ["agosto", "august", "août", "aug.", "ago."], 
    9: ["septiembre", "september", "septembre", "sept.", "sep"],
    10: ["octubre", "october", "octobre", "oct."], 
    11: ["noviembre", "november", "novembre", "nov."], 
    12: ["diciembre", "december", "décembre", "déc.", "dec.", "dic."]
}
dbh_perimeter_synonyms = ["perimeter", "perim.", "périmètre", "périm.", "perimetro", "circumference", 
                      "circonférence", "circonf", "circ.", "girth", "circunferencia", "circ"]

def get_typed_value(field_def, for_sql = False):
#high level function, return the value casted to the right type, raised an error if not possible
    if field_def is None:
        return
    _type = field_def["type"]
    field_value = field_def["value"]
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
        except Exception :
            error_code = 1000
            msg = "Error in type casting..."
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


class HighlightColumnDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        #if index.column() == self.column_value:
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
        self.column_value = 2
        # if not table_def:
        #     table_def = copy.deepcopy(dict_db_ncpippn)
        self.dict_trees_import = table_def
        self.type_columns = None
        self.dataframe = None
        self.buttonOK = False
        self.window = uic.loadUi('pn_ncpippn_import.ui')
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
        

        # selection_model = self.window.tblview_columns.selectionModel()
        # selection_model.selectionChanged.connect(self.tblview_columns_clicked)


        delegate = HighlightColumnDelegate()
        self.window.tblview_columns.setItemDelegateForColumn(self.column_value+1, delegate)
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
        field_name = index.siblingAtColumn(0).data().lower()
        field_def = self.dict_trees_import[field_name]
        column_txt = field_name.upper() + " [" + field_def["type"] + "]"
        self.window.label_db_column.setText(column_txt)
        notice = ''
        sep = ''
        self.window.label_infos_db.setText(notice)
        #create text to display according to field_def tip, unit and details (cf. load_dict_trees_import)
        if "tip" in field_def:
            notice = field_def["tip"]
            sep = " - "
        if "unit" in field_def:
            notice += sep + '(' + field_def["unit"] + ')'
            sep = " - "
        #add combination tip and unit as toolTip
        if notice:
            self.window.tblview_columns.model().itemFromIndex(index).setToolTip(notice)
        #add details (how calculation was done, cf. load_dict_trees_import)
        if "details" in field_def:
            if field_def["details"]:
                notice += "\n" + field_def["details"]
        #add to label_infos_db
        if notice:
            self.window.label_infos_db.setText(notice)

    def load(self, filename = None):
        def is_synonym(fieldref, fieldname):
        #return True if fieldname is equal or a synonym to fieldref
            fieldname = fieldname.strip(' ').lower()
            fieldref = fieldref.strip(' ').lower()
            if fieldref == fieldname:
                return True
            synonym = self.dict_trees_import[fieldref].get("synonyms", None)
            if synonym and fieldname in synonym:
                return True
            return False

        #main function to load a csv file, or to open fileBowser
        import os
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
        import csv
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
        key_header = None
        #clean the import structure
        for key, field_def in self.dict_trees_import.items():
            if field_def.get("import", None):
                del field_def["import"]


        #checks for fieldref, types and values of input fields
        for header, _type in self.type_columns.items():
#TODO: eventually to get details for each colums in csv file
            # no_nullvalue = self.dataframe [header].dropna()
            # _type = _type.name
            # #object come from mixed or text columns (check for boolean first)
            # if _type == 'object':
            #     if all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
            #         _type = 'boolean'
            #     else:
            #         _type = "text"
            #     self.type_columns[header] = _type
            # #float64 come from numeric and even integer if some null values
            # if _type == 'float64':
            #     try:
            #         if no_nullvalue.apply(lambda x: float(x).is_integer()).all():
            #             _type = 'integer'
            #     except Exception:
            #         if pd.api.types.is_string_dtype(no_nullvalue):
            #             _type = "numeric"
            #     self.type_columns[header] = _type
            # #transpose types names to standard ones
            # try:
            #     _type = get_column_type("type")
            # except Exception:
            #     pass
            # #Calculate duplicated value
            # duplicated_value = False
            # duplicated_value = no_nullvalue.duplicated().any()
            # count_non_null = self.dataframe [header].count()
            # minimum_value = no_nullvalue.min()
            # maximum_value = no_nullvalue.max()
            # key_header = {"column": header, "value": None, "type": _type,  "non null": count_non_null, 
            #               "duplicated": duplicated_value, "min" : minimum_value, "max" : maximum_value}
#END TODO
            #check for match betwwen key and header (check for synonyms), add dict import to column defition if found 
            for key, field_def in self.dict_trees_import.items():
                if is_synonym(key, header):
                    key_header = {"column": header, "value": None}
                    field_def["import"] = key_header
        
        #return if no column was imported
        if not key_header:
            return
        
        #to create a dictionnary of identifier in the CSV file that already exists in the table trees (UPDATE)
        # if self.dict_trees_import.get("identifier", None):
        #     if self.dict_trees_import["identifier"].get("import", None):
        #         column = self.dict_trees_import["identifier"]["import"]["column"]
        #         #get a list of unique non null identifier
        #         non_null_identifier = self.dataframe[column].dropna().unique().tolist()
        #         #create the dictionnary of updated identifier
        #         if non_null_identifier:
        #             #clause_in = ", ".join(tab_identifier)
        #             clause_in = ", ".join(["'{}'".format(item) for item in non_null_identifier])
        #             sql_query = f"""SELECT identifier, {DBASE_SCHEMA_TREES}.id_plot, plot 
        #                             FROM {DBASE_SCHEMA_TREES} JOIN {DBASE_SCHEMA_PLOTS} 
        #                             ON {DBASE_SCHEMA_TREES}.id_plot = {DBASE_SCHEMA_PLOTS}.id_plot 
        #                             WHERE identifier IN ({clause_in})""" 
        #             query = QtSql.QSqlQuery(sql_query)
        #             self.dict_identifier_toUpdate = {}
        #             while query.next():
        #                 self.dict_identifier_toUpdate[query.value("identifier")] = [query.value("id_plot"), query.value("plot")]
        #     else:
        #         msg = str(['identifier'] + list_db_fields["identifier"]["synonyms"])
        #         msg = "CSV file must contain one unique identifier column from " + msg

        #         QtWidgets.QMessageBox.critical(None, "No identifier", msg, QtWidgets.QMessageBox.Ok)
        #         model = QtGui.QStandardItemModel()
        #         self.window.tblview_columns.setModel(model)
        #         return

        self.loadValue ()



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
        model = QtGui.QStandardItemModel()

        #load the value into the dict_trees_import
        self.load_dict_trees_import(index-1)

        #fill the model with dict_trees_import values and import dictionnary
        row = 0
        locality = None        #msg = ''
        #self.window.label_db_action.setText("ADD")
        for field_name, field_def in self.dict_trees_import.items():
            # if not field_def.get("enabled", True) or not field_def.get("visible", True):
            #     continue
            #clear value_csv and value_dbase
            model.setItem(row, self.column_value, None)
            model.setItem(row, self.column_value+1, None)
            #set the first column (field name)
            item = QtGui.QStandardItem(field_name.capitalize())
            model.setItem(row, 0, item)

            import_value = None

            #check for import dictionnary
            dict_import = field_def.get("import", None)
            if dict_import:
                #set the second column (CSV column)
                field_csv = dict_import["column"]
                item = QtGui.QStandardItem(field_csv)
                model.setItem(row, 1, item)
                #set the imported CSV value
                import_value = self.dict_trees_import[field_name]["import"]["value"]
                if import_value is not None:
                    newitemValue = QtGui.QStandardItem(str(import_value))
                    #colorize fields with errors
                    # app_style = QtWidgets.QApplication.style()
                    # default_text_color = app_style.standardPalette().color(QtGui.QPalette.Text)
                    # newitem.setForeground(QtGui.QBrush(default_text_color))

                    if field_name == "identifier":
                        self.window.label_db_action.setText("ADD " + str(import_value))
                        self.window.label_db_action.setStyleSheet("color: #28a745;")

                    if dict_import.get("error", 0) > 0:
                        newitemValue.setForeground(QtGui.QBrush(QtGui.QColor(255, 0, 0)))
                    elif field_name == "identifier" and import_value in self.dict_identifier_toUpdate:
                        #updating = True
                        locality = self.dict_identifier_toUpdate[import_value][1]
                        
                    model.setItem(row, self.column_value, newitemValue)
                
            #set the dbase value (column 3)
            dbase_value = self.dict_trees_import[field_name]["value"]
            if dbase_value is not None:
                newitem = QtGui.QStandardItem(str(dbase_value))
                if locality and field_name == "identifier":
                    # newitem = QtGui.QStandardItem(str(dbase_value))
                    # newitem.setForeground(QtGui.QBrush(QtGui.QColor(100, 100, 255)))
                    # newitemValue.setForeground(QtGui.QBrush(QtGui.QColor(100, 100, 255)))
                    self.window.label_db_action.setText("UPDATE "  + import_value)
                    self.window.label_db_action.setStyleSheet("color: #007bff;")
                    self.dict_trees_import["locality"]["value"] = locality
                model.setItem(row, self.column_value+1, newitem)
                                    
            row +=1
            
        # Add header for columns and set the mdoel
        model.setHorizontalHeaderItem(0, QtGui.QStandardItem("DB column"))
        model.setHorizontalHeaderItem(1, QtGui.QStandardItem("CSV column"))
        model.setHorizontalHeaderItem(2, QtGui.QStandardItem("CSV value")) # [" + str(index) + "]"))
        model.setHorizontalHeaderItem(3, QtGui.QStandardItem("DB value"))
        #set the model in tableview_columns and ajust column sizes
        
        self.window.tblview_columns.setModel(model)
        self.window.tblview_columns.resizeColumnsToContents()
        header = self.window.tblview_columns.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(self.column_value+1, QtWidgets.QHeaderView.Stretch)
        self.window.tblview_columns.selectionModel().selectionChanged.connect(self.tblview_columns_clicked)
                  

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
            if field_def["type"] in ['integer', 'numeric']:
                #replace comma by dot (correcting french-english keyboard in string)
                if isinstance(import_value, str):
                    import_value = import_value.replace(",", ".")
                    try:
                        import_value = float(import_value)
                        import_value = int(import_value)
                    except Exception:
                        pass
            #set the import_value (if no import_value, the value is None)
            field_def["value"] = import_value
            
            #return if not import_value in the field_csv
            if import_value is None:
                continue

            #manage special translation (dbh, fruits/flowers and month)
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
                            field_def["details"] = "DBH was calculated by dividing the circumference by pi"
                            float_dbh = float_dbh/mt.pi
                        total_area += mt.pi * (float_dbh/2)**2
                    except Exception:
                        continue
                #compute the resulting DBH from the total area
                field_value = 2*mt.sqrt(total_area/mt.pi)
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
                dict_list = dict_strata if field_name == "strata" else dict_month
                #translate month to integer according to dict_month
                try:
                    import_value = int(float(import_value)) #try to translate as an integer
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

            #delete error code if any
            if "error" in dict_import:
                del dict_import["error"]
            #set the final value
            field_def["value"] = None            
            if field_value:
                #save typed value (as in table, none if not typed and error code add to dict_import definition)
                try:
                    field_def["value"] = get_typed_value(field_def)
                except ValueError as err:
                    field_def["value"] = None
                    dict_import["error"] = err.args[1]
                    no_error = False

    #actions link to the overall dict_trees_import
        #test for longitude/latitude validity, None to location if invalid
        try:
            _test = self.dict_trees_import["longitude"]["value"]  * self.dict_trees_import["latitude"]["value"]
        except Exception:
            self.dict_trees_import["longitude"]["value"] = None
            self.dict_trees_import["latitude"]["value"] = None
            #self.dict_trees_import["locality"]["value"] = None
        # id_plot = self.get_id_plot()
        # if id_plot > 0:
        #     self.dict_trees_import["locality"]["value"] = self.dict_identifier_toUpdate[self.dict_trees_import["identifier"]["value"]][1]
        # elif id_plot < 0:
        #     self.dict_trees_import["locality"]["value"] = dict_db_plot["locality"]["value"]
        #set the stems number according to the len of tab_stems_dbh
        #excepting if 1 stems in tab_stems_dbh and _stems >=0
        if tab_stems_dbh:
            _stems = self.dict_trees_import["stems"]["value"]
            if len(tab_stems_dbh) == 1 and not _stems:
                _stems = 1
                self.dict_trees_import["stems"]["details"] = "Stems number was computed from DBH column "
            elif len(tab_stems_dbh) > 1:
                _stems = len(tab_stems_dbh)
                self.dict_trees_import["stems"]["details"] = "Stems number was computed from DBH column "
            self.dict_trees_import["stems"]["value"] = int(_stems)

        #set to dead if strata = 0
        if fix_dead:
            self.dict_trees_import["dead"]["value"] = True
            self.dict_trees_import["strata"]["value"] = None

        #set auto-calculate columns (leaf_sla, leaf_ldmc, wood_density), if raw data are available in dataline
        #Try to calculate leaf_sla from leaf_area and leaf_dry_weight
        try:
            leaf_area = self.dict_trees_import["leaf_area"]["value"]
            leaf_sla = leaf_area / float(dataline["leaf_dry_weight"])
            decimal = self.dict_trees_import["leaf_sla"].get("decimal", PLOT_DEFAULT_DECIMAL)
            self.dict_trees_import["leaf_sla"]["value"] = round(leaf_sla, decimal)
            self.dict_trees_import["leaf_sla"]["details"] = "Leaf SLA was calculated from leaf_area / leaf_dry_weight"

            # composite_column_name = "leaf_area / leaf_dry_weight"
            # if self.dict_trees_import["leaf_sla"].get("import", None):
            #     self.dict_trees_import["leaf_sla"]["import"]["column"] = composite_column_name
            # else:
            #     self.dict_trees_import["leaf_sla"]["import"] = {"column": composite_column_name, "value": round(leaf_sla, decimal)}
        except Exception:
            pass
        #Try to calculate leaf_ldmc from leaf_fresh_weight and leaf_dry_weight
        # terms_tosearch = ["leaf_fresh_weight", "leaf_dry_weight"]
        # if all(term in self.type_columns for term in terms_tosearch):
        try:
            leaf_ldmc = float(dataline["leaf_dry_weight"])/ float(dataline["leaf_fresh_weight"])
            decimal = self.dict_trees_import["leaf_ldmc"].get("decimal", PLOT_DEFAULT_DECIMAL)
            self.dict_trees_import["leaf_ldmc"]["value"] = round(leaf_ldmc,decimal)
            self.dict_trees_import["leaf_ldmc"]["details"] = "Leaf LDMC was calculated from leaf_dry_weight / leaf_fresh_weight"
        except Exception:
            pass
        #Try to calculate wood_density from core_dry_weight, core_diameter and core_length
        # terms_tosearch = ["core_length", "core_dry_weight", "core_diameter"]
        # if all(term in self.type_columns for term in terms_tosearch):
        try:
            core_volume = mt.pi * ((float(dataline["core_diameter"])/2) ** 2)* float(dataline["core_length"]) * 0.1
            wood_density = float(dataline["core_dry_weight"])/ core_volume
            decimal = self.dict_trees_import["wood_density"].get("decimal", PLOT_DEFAULT_DECIMAL)
            self.dict_trees_import["wood_density"]["value"] = round(wood_density,decimal)
            self.dict_trees_import["wood_density"]["details"] = "Wood density was calculated from core_dry_weight / (0.1 * pi * core_length * ((core_diameter / 2)²))"
        except Exception:
            pass
        return no_error

    def show_modal(self):
        self.window.show()
        #self.window.exec_()
        
    def close(self):
        self.window.close()       
    
    def validate (self):
        print ("validate")


if __name__ == '__main__':
# connection to the database
    # db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    # if not createConnection(db):
    #     sys.exit("error")
    app = QtWidgets.QApplication(sys.argv)

    with open("Diffnes.qss", "r") as f:
        #with open("Photoxo.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)


    window = CSVImporter(list_db_fields)
    window.show_modal()
    app.exec()