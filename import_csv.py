import sys
from PyQt5 import  QtGui, uic
from PyQt5.QtWidgets import QItemDelegate, QApplication, QMessageBox, QLineEdit, QDialogButtonBox, QHeaderView, QFileDialog, QGroupBox, QComboBox, QDialog
# import psycopg2
# import csv
from PyQt5.QtCore import Qt #, pyqtSignal, QObject
#from PyQt5 import QtWidgets
#from PyQt5.QtCore import *
from core.functions import list_db_fields, get_reference_field, list_db_traits, get_column_type

class NonEditableModel(QtGui.QStandardItemModel):
#a special class derived from QStandardItemModel to allow some cells to be edited
    def flags(self, index):
        exclude_list = [0, 2, 3, 4]
        if  index.siblingAtColumn(2).data() not in ['integer', 'numeric']:
            exclude_list += [5,6] 
        if index.column() in exclude_list:
            return super().flags(index) & ~Qt.ItemIsEditable
        return super().flags(index)

class ComboBoxDelegate(QItemDelegate):
# a special class delegate to manage the Qtableview of the CSVTranslate class
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colored_column = 1
        self.combox_column = 1
        self.type_column = 2
        self.parent = parent

    def createEditor(self, parent, option, index):
        # Create a QComboBox when cell is edited
        if index.column() == self.combox_column:
            editor = QComboBox(parent)
            self.updateComboBox(editor, index)
            if editor.count() > 0:
                return editor
        else:
            return QLineEdit(parent)

    def updateComboBox(self, comboBox, index):
        # update cell from combobox value
        _type = index.siblingAtColumn(self.type_column).data()
        field_types = [""]
        for fieldref, properties in list_db_fields.items():
            if fieldref != 'id' and properties["type"] == _type:
                field_types.append(fieldref)
        if len(field_types) > 1:
            comboBox.addItems(field_types)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() == self.colored_column:
            painter.fillRect(option.rect, QtGui.QColor(128, 128, 128, 50))

    def setModelData(self, editor, model, index):
        # Called when the editor has finished and the data needs to be saved to the model
        # if index.column() == self.combox_column:
        #     # Add your control logic here before saving the data to the model
        #     selected_item = editor.currentText()
            # Perform additional checks or actions based on the selected_item
            # ...
        super().setModelData(editor, model, index)
    
class CSVTranslate(QDialog):
#The main class of the dialog
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = uic.loadUi('pn_import.ui')
        self.headers = None
        self.window.pushButton_import.clicked.connect(self.load)

    def show_modal(self):
        self.window.exec_()
        
    def close(self):
        self.close()        
            
    def load(self, filename = None):
        import os
        import pandas as pd
        self.headers = {}
        #type_transpose = {'int64': 'integer', 'bool': 'boolean', 'float64': 'numeric'}
        
        if not isinstance(filename, str):
            filename = None
            
        try:
            os.path.exists(filename)
        except Exception:
            filename = None

        if filename is None:
        #set parameters to QfileDialog
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            file_dialog = QFileDialog()
            file_dialog.setNameFilter("Fichiers CSV (*.csv)")
            file_dialog.setDefaultSuffix("csv")
            filename, file_type = file_dialog.getOpenFileName(None, "Import a CSV File", "", "CSV Files (*.csv);;All files (*)", options=options)
            if not filename: 
                return 

        #open csv file
        # db_name = os.path.basename (filename)
        # db_name, extension = os.path.splitext(db_name)

        # #get a valid name derivated from the file_name
        # db_name = get_postgres_name(db_name)
        self.window.txt_postgresql_name.setText (filename)
        delimiter = ","
        #read the csv file and set the rows and columns
        troc = pd.read_csv(filename, sep = delimiter, encoding='utf-8', low_memory=False)
        _summary = str(troc.shape[0]) + ' rows, ' + str(troc.shape[1]) + ' columns'
        self.window.label_summary.setText(_summary)
       
        #check for primary types excluding null-values
        type_columns = troc.dropna().dtypes

        #checks for fieldref, types and values of any input fields
        for header, _type in type_columns.items():
            no_nullvalue = troc [header].dropna()
            _type = _type.name
            #object come from mixed or text columns (check for boolean first)
            if _type == 'object':
                if all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
                    _type = 'boolean'
                else:
                    _type = "text"
                type_columns[header] = _type
            #float64 come from numeric and even integer if some null values
            if _type == 'float64':
                try:
                    if no_nullvalue.apply(lambda x: float(x).is_integer()).all():
                        _type = 'integer'
                except Exception:
                    if pd.api.types.is_string_dtype(no_nullvalue):
                        _type = "numeric"
                type_columns[header] = _type
            #transpose types names to standard ones (synonyms)
            try:
                _type = get_column_type (_type)
            except Exception:
                pass
            #add a field definition
            fieldref = None
            fieldref = get_reference_field (header)
            if fieldref == 'id':
                fieldref = None
            duplicated_value = False
            duplicated_value = no_nullvalue.duplicated().any()
            # size "size": troc [header].size 
            self.headers[header] = {"type" : _type, "fieldref" : fieldref,  "non null": troc [header].count(), "duplicated" : duplicated_value, "min" : no_nullvalue.min(), "max" : no_nullvalue.max()}


        if 'longitude' in self.headers and 'latitude' in self.headers:
            self.headers['location'] = {'longitude': self.headers['longitude'], 'latitude':self.headers['latitude']}
            self.headers.pop('longitude')
            self.headers.pop('latitude')

        if ('flower' in self.headers or 'fruit' in self.headers) and 'month' in self.headers:
            dict_phenology = {}
            if 'flower' in self.headers:
                dict_phenology['flower'] = self.headers['flower']
            if 'fruit' in self.headers:
                dict_phenology['fruit'] = self.headers['fruit']
            dict_phenology['month'] = self.headers['month']
            self.headers['phenology'] = dict_phenology
            self.headers.pop('flower')
            self.headers.pop('fruit')

        if ('leaf_dry_weight' in self.headers):
            if 'leaf_area' in self.headers:
                self.headers['leaf_sla'] = {"type": 'numeric',  "fieldref" :{'leaf_area': self.headers['leaf_area'], 'leaf_dry_weight':self.headers['leaf_dry_weight']}}
            if ('leaf_fresh_weight' in self.headers):
                self.headers['leaf_ldmc'] = {"type": 'numeric',  "fieldref" :{'leaf_fresh_weight':self.headers['leaf_fresh_weight'], 'leaf_dry_weight': self.headers['leaf_dry_weight']}}
                self.headers.pop('leaf_fresh_weight')
            self.headers.pop('leaf_dry_weight')

        if ('core_diameter' in self.headers and 'core_length' in self.headers and 'core_dry_weight' in self.headers):
            self.headers['wood_density'] = {"type": 'numeric',  "fieldref" :{'core_length': self.headers['core_length'], 'core_dry_weight':self.headers['core_dry_weight'], 'core_diameter':self.headers['core_diameter']}}
            self.headers.pop('core_diameter')
            self.headers.pop('core_length')
            self.headers.pop('core_dry_weight')



        #fill the Qtreeview
        model = NonEditableModel()
        # Add header for columns
        model.setHorizontalHeaderItem(0, QtGui.QStandardItem("Column"))
        for index, subkey in enumerate(self.headers[next(iter(self.headers))]):
            model.setHorizontalHeaderItem(index + 1, QtGui.QStandardItem(subkey))
        # Fill cells with self.headers
        self.populate_model_recursively (model,None, self.headers)


        # for key, value in self.headers.items():
        #     if isinstance(self.headers["fieldref"], dict):

            
        #     # Vérifier si le champ a plusieurs sous-champs
        #     if all(isinstance(v, dict) for v in value.values()):
        #         # Champ multiple avec sous-champs : ajouter un parent
        #         parent_item = QtGui.QStandardItem(key)
        #         parent_item.setCheckable(True)
        #         model.appendRow([parent_item] + [QtGui.QStandardItem("") for _ in range(6)])  # Colonnes vides pour le parent
                
        #         for sub_key, sub_value in value.items():
        #             # Ajouter chaque sous-champ comme enfant avec ses colonnes
        #             row = [QtGui.QStandardItem(sub_key)]
        #             row.extend(QtGui.QStandardItem(str(sub_value.get(col, ""))) for col in ["type", "fieldref", "non null", "duplicated", "min", "max"])
        #             parent_item.appendRow(row)
        #     else:
        #         # Champ simple (pas de sous-champs) : ajouter directement comme ligne
        #         parent_item = QtGui.QStandardItem(key)
        #         parent_item.setCheckable(True)
        #         row = [parent_item]
        #         row.extend(QtGui.QStandardItem(str(value.get(col, ""))) for col in ["type", "fieldref", "non null", "duplicated", "min", "max"])
        #         model.appendRow(row)

        # Set the model to the tblview_columns
        self.window.tblview_columns.setModel(model) 
        # header = self.window.tblview_columns.horizontalHeader()
        # header.setSectionResizeMode(0, QHeaderView.Stretch)

        # Apply a delegate to change color and edit options
        combo_delegate = ComboBoxDelegate()
        self.window.tblview_columns.setItemDelegate(combo_delegate)
        self.window.buttonbox_import.button(QDialogButtonBox.Ok).clicked.connect(self.validate)
        combo_delegate.closeEditor.connect(self.handleEditingFinished)
        return

    def populate_model_recursively(self, model, parent, data):
        """
        Parcourt un dictionnaire pour remplir un QStandardItemModel.
        Les colonnes sont remplies dans l'ordre des valeurs du dictionnaire.

        :param model: Le QStandardItemModel utilisé pour remplir les données.
        :param parent: Le QStandardItem parent ou None (au niveau racine).
        :param data: Le dictionnaire contenant les données à insérer.
        """
        for key, value in data.items():
            if isinstance(value, dict):
                # Crée une ligne avec toutes les valeurs du dictionnaire, dans l'ordre
                # fieldref = value.get('fieldref')
                # if isinstance(fieldref, dict):
                #     value['fieldref'] = key
                row = [QtGui.QStandardItem(str(key))]
                for v in value.values():
                    if isinstance(v, dict):
                        row.append(QtGui.QStandardItem(str(key)))
                    else:
                        row.append(QtGui.QStandardItem(str(v)))
                
                if parent is None:
                    # Ajout au niveau racine si parent est None
                    model.appendRow(row)
                else:
                    # Ajout sous le parent existant
                    parent.appendRow(row)
                
                # Si un champ contient un sous-dictionnaire, on le traite comme un enfant
                fieldref = value.get('fieldref')
                if isinstance(fieldref, dict):
                    self.populate_model_recursively(model, row[0], fieldref)




    def handleEditingFinished(self, editor, index):
        # Slot to handle the editing finished event
        if isinstance(editor, QComboBox):
            selected_item = editor.currentText()
            model = self.window.tblview_columns.model()
            c_row = self.window.tblview_columns.currentIndex().row()
            #Check that there is only one reference to a fieldref
            for row in range(model.rowCount()):
                index = model.index(row, 2)
                fieldref = model.data(index)
                if row != c_row and fieldref == selected_item:
                    model.setData (model.index(row,2),'')
        elif isinstance(editor, QLineEdit):
            selected_item = editor.text()



    def validate (self):
        headers_traits = {'id' : list_db_fields['id']}
        #headers = []
        is_valid = True
        msg = ""
        model = self.window.tblview_columns.model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            fieldcsv = index.siblingAtColumn(0).data()
            fieldref = index.siblingAtColumn(2).data()
            self.headers[fieldcsv]['fieldref'] = fieldref
            self.headers[fieldcsv]['min'] = index.siblingAtColumn(5).data()
            self.headers[fieldcsv]['max'] = index.siblingAtColumn(6).data()

            item = model.data(index, Qt.CheckStateRole)
            if item == Qt.Checked:                
                if fieldref is not None:
                    if fieldref in headers_traits:
                        msg = "The < " + fieldref + " > column is used more than once"
                        QMessageBox.critical(None, "Invalid Datasource", msg, QMessageBox.Cancel)
                        return
                    if self.headers[fieldcsv]['type'] != list_db_fields[fieldref]['type']:
                        msg = "The column < " + fieldcsv + " > contains data incompatible with < " + self.headers[fieldcsv]['fieldref'] + " >"
                        QMessageBox.critical(None, "Invalid Datasource", msg, QMessageBox.Cancel)
                        return
                    #add the column if test are OK
                    headers_traits[fieldref] = self.headers[fieldcsv]

        #test the validity of headers (at least id, taxaname and one functional traits)
        is_valid, msg = self.is_headersValid(headers_traits)
        if not is_valid:
            QMessageBox.critical(None, "Invalid Datasource", msg, QMessageBox.Cancel)
            return                    




        #test to be sure than any field is used only once
        # is_valid = False
        # msg = ""
        # is_valid = len(headers) == len(set(headers))
        # if not is_valid:
        #     for item in headers:
        #         if headers.count(item) > 1:

                        
        #test the unicity of the identifier
        # field_id = self.ls_cbtraits["id"].currentText()
        # if self.headers[field_id]["duplicated"]:
        #     msg = "The column < " + field_id + " > contains duplicated values \n Identifier must be unique"
        #     QMessageBox.critical(None, "Invalid Datasource", msg, QMessageBox.Cancel)
        #     return

        #test the type of field values to be linked to fieldref
        # for trait, cb in self.ls_cbtraits.items():
        #     field = cb.currentText()
        #     if len(field) > 0:
        #         self.headers[field]['fieldref'] = trait
        #         if self.headers[field]['type'] != list_db_fields[trait]['type']:
        #             is_valid = False
        #             # msg = "The column < " + field + "> contains data incompatible with the type " + list_db_fields[trait]['type'].upper()
        #             # msg += " required by < " + self.headers[field]['fieldref'] + " >"
        #             msg = "The column < " + field + " > contains data incompatible with < " + self.headers[field]['fieldref'] + " >"
        #             QMessageBox.critical(None, "Invalid Datasource", msg, QMessageBox.Cancel)
        #             return
        #         headers.append(field)
        #         headers_traits.append(trait)


        
        #test for the unicity of fieldref = id
        #field_id = headers_traits["id"]




    
    # def setting_ui (self):
    #     ls_traits = list(list_db_fields.keys())
    #     for trait in ls_traits[1:]:
    #         label = QLabel()
    #         combo = QComboBox()
    #         label.setText(trait)
    #         self.window.formLayout.layout().addRow(label,combo)
    #         self.ls_cbtraits[trait] = combo

        



    # def create_dot_pixmap(self, color):
    #     pixmap = QtGui.QPixmap(16, 16)
    #     pixmap.fill(Qt.transparent)
    #     painter = QtGui.QPainter(pixmap)
    #     painter.setRenderHint(QtGui.QPainter.Antialiasing)
    #     dot_radius = 5
    #     dot_center = pixmap.rect().center()
    #     painter.setBrush(color)
    #     painter.drawEllipse(dot_center, dot_radius, dot_radius)
    #     painter.end()
    #     return pixmap




    def is_headersValid(self, headers):
        valid = False    
        msg = "Invalid datasource"
        if len(headers) < 3: 
            return (valid, msg)
        #translate the original headers with dictionnaries of header synonyms
        fieldnames = []
        # for fieldname in headers:
        #     t = None
        #     t = self.search_field(fieldname)
        #     if t is None:
        #         t = fieldname
        #     fieldnames.append(t)
        
        fieldnames = headers
        #check if headers gather necessary fields (id, taxaname and one traits among (GPS, phenology or functional))

        msg = "Unable to find an identifier column"
        if "id" in fieldnames :
            msg = "Unable to find a taxaname column"
            if "taxaname" in fieldnames:
                msg = "Unable to find at least one property (Location, Phenology, Functionnal trait)"
                #a table is valid if GPS coordinates, phenology or functional traits
                if "longitude" in fieldnames and "latitude" in fieldnames:
                    valid = True
                if "phenology" in fieldnames and "month" in fieldnames:
                    valid = True   
                if len(set(list_db_traits) & set(fieldnames))>0 :                                
                    valid = True
        if valid: 
            msg = "Valid datasource"
        return (valid, msg)            





        #add input fields to the model for ANY combo
        # model = QStringListModel()
        # filtered_data = {key: value for key, value in self.headers.items() if value.get('type') == 'numeric'}
        # model.setStringList([""]+list(self.headers))
        # for trait, cb in self.ls_cbtraits.items():
        #     cb.setModel(model)
        #     cb.setCurrentIndex(-1)

        # for field in self.headers:
        #     fieldref = self.headers[field]["fieldref"]
        #     if fieldref is not None:
        #         try:
        #             cb = self.ls_cbtraits[fieldref]
        #             cb.setCurrentText(field)
        #         except:
        #             pass
        
        # return
    







        #db_name = get_postgres_name(db_name)
    


        # #add the tables of the schema into the treeview (self.schema)
        # model = QtGui.QStandardItemModel()
        # model.setColumnCount(2)
        # model.setHorizontalHeaderLabels(['Column', 'Translate'])
        # self.window.lsview_fields.setModel(model)
        # # Ajout du delegate pour la deuxième colonne
        # delegate = ComboBoxDelegate()
        # self.window.lsview_fields.setItemDelegateForColumn(1, delegate)
        #         # Définir le déclencheur d'édition sur un simple clic pour la colonne 2 uniquement
        # self.window.lsview_fields.clicked.connect(self.handle_item_clicked)  

        # for field in headers:
        #     item = QtGui.QStandardItem(field)
        #     item1 = QtGui.QStandardItem()
        #     fieldref = get_reference_field (field)
        #     if fieldref is not None:
        #         try:
        #             item1 = QtGui.QStandardItem(fieldref)
        #         except:
        #             pass
        #     # italic_font = QtGui.QFont()
        #     # italic_font.setItalic(self.isTableFiltered (table))
        #     # item.setFont(italic_font)
        #     # item.setCheckable(checkable)
        #     model.appendRow([item, item1])
            
        # self.window.lsview_fields.resizeColumnsToContents()

        # self.headers = headers
        # #combobox = self.window.findChildren(QComboBox)
        # model = QStringListModel()
        # model.setStringList([""]+list(headers))
    
        # for trait, cb in self.ls_cbtraits.items():
        #     cb.setModel(model)
        #     cb.setCurrentIndex(-1)

        # for field in headers:
        #     fieldref = None
        #     fieldref = get_reference_field (field)
        #     if fieldref is not None:
        #         try:
        #             cb = self.ls_cbtraits[fieldref]
        #             cb.setCurrentText(field)
        #             # index_to_disable = cb.currentIndex()
        #             # item_to_disable = model.index(index_to_disable, 0)
        #             # model.item(item_to_disable).setEnabled(False)
        #             #model.setItemData(item_to_disable, {Qt.ItemIsEnabled: False})
        #         except:
        #             pass
        # self.window.buttonbox_import.button(QDialogButtonBox.Ok).clicked.connect(self.validate)
        # return
    
    
        # for trait, cb in self.ls_cbtraits.items():
        #     cb.addItems(headers)
        #     fieldref = None
        #     fieldref = get_reference_field (trait)
        #     if fieldref is None:
        #         cb.setCurrentIndex(-1)
        #     else:
        #         cb.setCurrentText(fieldref)
        # return





    def get_table_headers(self, headers, reader, rows = 1000): 
    #generate the script to create a new table after read data and adjust data type
        create_table_query = ""
        #most critic type is integer
        header_types =['INTEGER'] * len(headers)
        header_hits =[0] * len(headers)
        header_totest = headers.copy()

        #i = 0
        for row in reader:
            for header in header_totest:
                index = header_totest.index(header)
                value = row[index]
                if header_hits[index] >= rows:
                    header_totest.remove(header)
                    continue
                elif len(value) == 0: 
                    continue
                elif header_types[index]!='TEXT':
                    try:
                        value = float(value)
                        if not value.is_integer():
                            header_types[index] = "NUMERIC"
                    except ValueError:
                        header_types[index] = "TEXT"
                header_hits[index] += 1


        for header in headers:
            column_type = header_types[headers.index(header)]
            create_table_query += f"{header} {column_type}, "

        create_table_query = create_table_query.rstrip(', ') + ');'
        return create_table_query
    


        all_comboboxes = [] #self.window.findChildren(QComboBox)
        nested_comboboxes = [combo for widget in self.window.findChildren(QGroupBox) for combo in widget.findChildren(QComboBox)]
        all_comboboxes.extend(nested_comboboxes)
        form_layout = self.window.group_traits.layout()        
        for cb in all_comboboxes:
            cb.addItems(headers)
            label = form_layout.labelForField(cb)
            #print (label)
            if label is not None:
                #print (label.text())
                cb.setCurrentText(label.text())

















# class CSVImporter(QObject):
#     import_inprogress = pyqtSignal(float)

#     def __init__(self, db_name):
#         super().__init__()
#         self.rowvalues = []
#         self.db_name = db_name

#     def import_csv(self, file_name):        
#         if file_name:
#             # Connection à la base de données PostgreSQL
#             connection = psycopg2.connect(
#                 host='localhost',
#                 database='test',
#                 user='postgres',
#                 password='postgres'
#             )
#             self.rowvalues = []
#             # Création d'un curseur
#             cursor = connection.cursor()

            
#             # Ouverture du fichier CSV et lecture des données
#             with open(file_name, 'r', newline='', encoding='utf-8') as file:
#                 reader = csv.reader(file, delimiter=';', skipinitialspace = True, quotechar='"')
                
#                 total_rows = len(list(reader))
#                 file.seek(0)
#                 headers = next(reader)

#                 # Création de la requête SQL pour la création de la table
#                 create_table_query = self.create_table_query(headers, reader)
#                 cursor.execute(create_table_query)

#                 # Création de la requête SQL pour l'insertion des données
#                 # insert_data_query = f"INSERT INTO " + self.db_name + " ({', '.join(headers)}) VALUES ({', '.join(['%s']*len(headers))})"
                
#                 # Insertion des données dans la table
#                 sql = "INSERT INTO " + self.db_name + " (" + ', '.join(headers) +") VALUES (__values__);"
#                 i = 1
#                 a = 1
#                 for row in self.rowvalues:
#                     if a > total_rows/100:
#                         self.import_inprogress.emit(i/total_rows)
#                         a = 1
#                     row = ', '.join(f"'{element.replace(chr(39),chr(39)+chr(39))}'" if isinstance(element, str) else str(element) for element in row) 
#                     row = row.replace("None", "NULL")
#                     row = row.replace("()", "NULL")
#                     row = row.strip("[")
#                     row = row.strip("]")
#                     t = sql.replace("__values__", row)
#                     cursor.execute(t)
#                     i += 1
#                     a += 1

#             # Validation des changements et fermeture de la connexion
#             connection.commit()
#             cursor.close()
#             connection.close()
#             return True
        


#     def create_table_query(self, headers, reader):
#     #generate the script to create a new table after read data and adjust data type
#         create_table_query = "CREATE TABLE IF NOT EXISTS " + self.db_name + " ("
#         #most critic type is integer
#         header_types =['INTEGER'] * len(headers)
        
#         for row in reader:
#             _rowvalue = [None] * len(headers)
#             for header in headers:
#                 index = headers.index(header)
#                 value = row[index]
#                 _rowvalue[headers.index(header)] = value
#                 if len(value) == 0: #if null value do not change type
#                     _rowvalue[index] = None
#                     continue
#                 elif header_types[index]=='TEXT': #if type = text, no change
#                     continue
#                 else: #numeric or integer
#                     try:
#                         value = float(value)
#                         if not value.is_integer():
#                             header_types[index] = "NUMERIC"
#                         else:
#                             _rowvalue[index] = int(value)
#                     except ValueError:
#                         header_types[index] = "TEXT"
#             self.rowvalues.append(_rowvalue)
#         for header in headers:
#             column_type = header_types[headers.index(header)]
#             create_table_query += f"{header} {column_type}, "

#         create_table_query = create_table_query.rstrip(', ') + ');'
#         return create_table_query


# def test_import_csv():
#     options = QFileDialog.Options()
#     options |= QFileDialog.DontUseNativeDialog
#     file_name, _ = QFileDialog.getOpenFileName(window, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
#     if file_name:
#         file_label.setText(f'Selected File: {file_name}')
#         window.repaint()
#         test = CSVImporter("test_import_csv")
#         test.import_csv (file_name)
        

if __name__ == '__main__':
    app = QApplication(sys.argv)

    with open("ui/Diffnes.qss", "r") as f:
        #with open("Photoxo.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)
    fenetre = CSVTranslate()
    fenetre.load("/home/birnbaum/Téléchargements/DATA-Tchingou-1HA - Data.csv")
    fenetre.show_modal()

    #sys.exit(app.exec_())
    

    # window = QtWidgets.QMainWindow()
    # #window = CSVImporter()
    # window.setWindowTitle('Import CSV to PostgreSQL')
    # window.setGeometry(100, 100, 400, 200)

    # # Créer le widget central
    # central_widget = QWidget()
    # window.setCentralWidget(central_widget)


    # file_label = QLabel('Selected File: No file selected')
    # import_button = QPushButton('Import CSV')
    # import_button.clicked.connect(test_import_csv)

    # layout = QVBoxLayout(central_widget)
    # layout.addWidget(file_label)
    # layout.addWidget(import_button)

    # #window.setLayout(layout)
    # fenetre.show()
    # sys.exit(app.exec_())