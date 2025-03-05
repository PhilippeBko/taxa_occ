#import os
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import * 
from PyQt5 import QtGui, QtSql
from PyQt5.QtCore import *

from occ_model import *
from class_synonyms import *
from commons import *
from class_identity import *
from import_csv import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


def load_dbconnections():
#load the connection to the database stored into the sqlite file config.db
    dbconfig = QtSql.QSqlDatabase.addDatabase("QSQLITE", "config")
    dbconfig.setConnectOptions('QSQLITE_OPEN_READWRITE')
    dbconfig.setDatabaseName("config.db")
    if not dbconfig.open():
        QMessageBox.critical(None, "Cannot open database", "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        sys.exit("error") 
    sql_query = "SELECT * FROM config_start WHERE key = 'dbconnection'"
    query = dbconfig.exec_(sql_query)
    while query.next():
        window.cb_dbase.addItem(query.value(1))
        ls_parameter = []
        ls_parameter.append (str(query.value(2)))
        ls_parameter.append (str(query.value(3)))
        ls_parameter.append (str(query.value(4)))
        ls_parameter.append (str(query.value(5)))
        LS_dbconnection.append(ls_parameter)
    query.finish()
    dbconfig.close()
    QtSql.QSqlDatabase.close(dbconfig)

def load_dbdataset(schema):
#load the dataset config stored into the sqlite file config.db
    #dbconfig = QtSql.QSqlDatabase.addDatabase("QSQLITE", "config1")
    dbconfig = QtSql.QSqlDatabase.database("config")
    if not dbconfig.open():
        QMessageBox.critical(None, "Cannot open database", "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        sys.exit("error") 
    sql_query = "SELECT * FROM config_start WHERE key = 'dbdataset' AND parameter1 = '" + schema + "'"
    query = dbconfig.exec_(sql_query)
    tab_dataset = []
    while query.next():
        parameters = [str(query.value("name")), str(query.value("parameter2")), str(query.value("uuid"))]
        tab_dataset.append (parameters)
    query.finish()
    dbconfig.close()
    QtSql.QSqlDatabase.close(dbconfig)        
    return tab_dataset

def cb_dbase_selectionchange():
#load dabase parameters from the LS_dbconnection (cf. load_dbconnections())
    index = window.cb_dbase.currentIndex()   
    parameters = LS_dbconnection [index]
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    db.setHostName(parameters[0])
    db.setDatabaseName(parameters[1])
    db.setUserName(parameters[2])
    db.setPassword(parameters[3])

    if not db.open():
        QMessageBox.critical(None, "Cannot open database", "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        return False
    
    #unactive notices from postgresql
    sql = "SET client_min_messages TO warning"

    query = QtSql.QSqlQuery (sql)    
    #Load the class trView_occ through the database connection QtSql
    trView_occ.load()
    index = trView_occ.model().index(0, 0)
    trView_occ.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    #trView_occ.model().itemChanged.connect(trView_occ_checked)
    
    #load the shortcut traits dataset
    model = QtGui.QStandardItemModel()
    model.setColumnCount(1)
    window.tblview_traits_dataset.setModel(model)
    ls_traits = ['location', 'phenology'] + list(list_db_traits.keys())
    for traits in ls_traits:
        item = QtGui.QStandardItem(traits)
        model.appendRow([item])

    #load the shortcut users dataset from dbconfig
    model = QtGui.QStandardItemModel()
    model.setColumnCount(3)
    #window.tblview_user_dataset.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    window.tblview_user_dataset.setModel(model)
    for dataset in load_dbdataset(trView_occ.schema):
        item =  QtGui.QStandardItem(dataset[0])
        item1 = QtGui.QStandardItem(dataset[1])
        item2 = QtGui.QStandardItem(dataset[2])
        model.appendRow([item, item1, item2])
    #window.tblview_user_dataset
    window.tblview_user_dataset.hideColumn(1)
    window.tblview_user_dataset.hideColumn(2)
    model.dataChanged.connect(tblview_user_dataset_updateItem)
    return

  
 
def trview_explore_traits_fill():
#fill the trview_explore list by taxa
    try:
        _rankname = window.cb_figure_rank.currentText().lower()
        model = window.trView_properties.model()
        root_item = model.invisibleRootItem()
    except:
        return
    try:
        tblView_explore.selectionModel().clearSelection()
    except:
        pass
    #navigate through the treeview with recursive function trview_taxa_selectedItems
    tab_queries = []
    for tab_query in trview_taxa_selectedItems(root_item):
        tab_queries.append(tab_query)

    #check for exclusive or not search (and between categories)
    isAND = False
    if window.button_taxa_categories.isChecked():
        isAND = True
    #set the filter on taxa properties (isAND for exclusive search = all categories must be found)
    myPlotClass.set_propertiesfilter(tab_queries, isAND)
    myPlotClass._sql_taxaFilter = ''

#create the list, set the tblView_explore as Treeview  
    #alltaxas  = window.button_taxa_exclusive.isChecked()
    alltaxas  = window.cb_figure_taxa.currentIndex() == 1
    #get the traits from myPlotClass
    
    _function = window.cb_figure_function.currentText().lower()
    tmp = myPlotClass.sql_traits
    _sql_traits = myPlotClass.get_sql_traits(_rankname, _function, alltaxas)
    #set the result to PN_tlview_traits
    model = QtGui.QStandardItemModel()
    tblView_explore.setModel(model)
    query = QtSql.QSqlQuery (_sql_traits)
    record = query.record()
    tab_header = [get_str_value(record.fieldName(x)) for x in range(record.count())]
    verical_header = []
    while query.next():
        row = query.at() # - 1
        verical_header.append(str(query.value(0)))
        for x in range(record.count()):
            item = QtGui.QStandardItem()
            data = query.value(record.fieldName(x))
            item.setData(data, Qt.DisplayRole)
            model.setItem(row, x, item)
    model.setHorizontalHeaderLabels(tab_header)
    delegate = CenterDelegate()
    for column in range(1, model.columnCount()):
        tblView_explore.setItemDelegateForColumn(column, delegate)
    model = tblView_explore.model()    
    window.label_rows.setText (str(model.rowCount()) + " row(s)")
    figure_reset()

def trview_taxa_deselectedItems():
#deselected taxa properties
    def recursively_deselect(item):
        if item is not None:
            if item.isCheckable():
                item.setCheckState(Qt.Unchecked)
            for row in range(item.rowCount()):
                child_item = item.child(row)
                recursively_deselect(child_item)
    model = window.trView_properties.model()
    root_item = model.invisibleRootItem()
    recursively_deselect(root_item)
    trview_explore_traits_fill()

def trview_taxa_selectedItems(root):
#recursive function, return to the called function a list with selected items grouped
    #ex: [parent1, parent 2, [selected_item1, selected_item2]]
    #parents = []
    def _parent_list(item):
        #function to get parent hierarchy of any item
        txt = [item.text()]
        while item.parent():
            item = item.parent()
            txt.append(item.text())
            #txt = item.text() + '-' + txt
        txt.reverse()
        return txt
    
    def recurse(parent):
        checked_tab = []
        
        # if len(parent.text()) > 0:
        #     parents.append(parent.text())
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child.checkState() == 2:
                checked_tab.append (child.text())
        if len (checked_tab) > 0:
            #print (parents)
            checked_tab = _parent_list(parent) + [checked_tab]
            yield checked_tab
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child.rowCount() > 0:
                #parents.append(child.text())
                yield from recurse(child)
    if root is not None:
        yield from recurse(root)


def figure_reset():
#reset the min, max value and draw the plot
    window.figure_min.setText('')
    window.figure_max.setText('')
    window.figure_mean.setText('')
    window.figure_max.setText('')
    figure_plot()


def figure_plot():
#get and draw the figure corresponding to the selected_field 

    window.frame_toolbar_figure.setVisible (False)   
    #window.frame_toolbar_table.setVisible (False)
    #window.result_trView_occ.setVisible(False)
    fieldPlot = window.cb_figures.currentText()
    myFigure.setVisible(False)
    
    #get selected taxa
    _rankname = window.cb_figure_rank.currentText().lower()
    selected_items = []
    selected_indexes = tblView_explore.selectedIndexes()
    for index in selected_indexes:
        if index.column() == 0:
            item = index.data()
            selected_items.append(item)
    if len (selected_items) > 0:
        myPlotClass.set_taxafilter(_rankname,selected_items)

    #get the min/max value
    fmin = None 
    fmax = None
    if  len(window.figure_min.text().strip())>0:
        fmin = float (window.figure_min.text().strip())
    if  len(window.figure_max.text().strip())>0:
        fmax = float (window.figure_max.text().strip())

    #get the figure related to the fieldPlot
    myFigure.setVisible(True)    
    figure_canvas = myPlotClass.get_figure (myFigure.figure, fieldPlot, fmin, fmax)
    if figure_canvas is None :
        myFigure.figure.text(0.35, 0.5, 'no data in the selection...', style = 'italic', fontsize = 14, color = "grey")
        myFigure.draw()
        return
    myFigure.figure.subplots_adjust(bottom = 0.2, left = 0.2, right = 0.9, top = 0.85)

    #set the return min/max/median/mean values from the trView_occ
    fmin = None
    fmax = None
    if myPlotClass.figure_min is not None:
        fmin = round(myPlotClass.figure_min, 5)
        window.figure_min.setText(str(fmin))
    if myPlotClass.figure_mean is not None:
        fmean = round(myPlotClass.figure_mean, 3)
        window.figure_mean.setText(str(fmean))
    if myPlotClass.figure_median is not None:
        fmedian = round(myPlotClass.figure_median, 5)
        window.figure_median.setText(str(fmedian))
    if myPlotClass.figure_max is not None:
        fmax = round(myPlotClass.figure_max, 5)
        window.figure_max.setText(str(fmax))

    #set the visibility of the statistic filter frame
    window.frame_toolbar_figure.setVisible (not (fmin is None and fmax is None))
    #window.figure_vlayout.addWidget(figure_canvas)
    myFigure.draw()



############# tblView_data and FILTER (tab "Data Source" of the GUI) ###########
def buttonbox_selall_click():
    #select all the item in the tableView_item
    model = window.tableView_item.model()
    for row in range(model.rowCount()):
        item = model.item(row)
        item.setCheckState(2)

def buttonbox_inverse_click():
    #inverse selection of items in the tableView_item
    model = window.tableView_item.model()
    for row in range(model.rowCount()):
        item = model.item(row)
        if item.checkState() == 2:
            item.setCheckState(0)
        else:
            item.setCheckState(2)

def buttonbox_reset_click():
    #delete the filter for the selected field (search for a synonyms names)
    table = trView_occ.currentIndex().data()
    field = window.cb_fields.currentText()
    field = trView_occ.get_field(table,field)
    fieldname = field["field_name"]
    #set the field to none value
    trView_occ.delFieldFilter(table,fieldname)
    tblView_data.setModel(None)
    tabWidget_data_select()
    
def buttonbox_apply_click(item):
    #apply filter to the table, save into trView_occ definition dictionnary
    isfilter = not window.tableView_item.isEnabled()
    operator = ''
    value = ''
    #translate operator from text to SQL symbol
    ls_operators = {"equal": 'IN', "different" : 'NOT IN', 'contains' : 'LIKE', 'superior': '>', 'inferior': '<', 'greater': '>=', 'less' : '<='}
    operator = ls_operators[window.cb_operators.currentText()]
    #get the table name and the true field name    
    #table = trView_occ.currentIndex().data() 
    table = trView_occ.currentTable
    field = trView_occ.get_field(table, window.cb_fields.currentText())

    if field is None: return
    fieldname = field["field_name"]
    #separate treatment according to isfilter (from lineEdit_filter or tableView_item)
    if isfilter:
        value = window.lineEdit_filter.text().strip()
        if len(value) == 0 : return
        if operator =='LIKE':
            value = '%' + value + '%'
        #value = "'" + value + "'"
    else:
        #manage the check list
        ls_checked = []
        ls_unchecked = []
        model = window.tableView_item.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item.checkState() == 2:
                ls_checked.append(item.text())
            else:
                ls_unchecked.append(item.text())
        
        #don't save where all or nothing are selected
        if len(ls_unchecked) * len(ls_checked) == 0: return

        #check for in or not according to the length of lists
        if len(ls_unchecked) < len(ls_checked):
            if operator == 'IN':
                operator = 'NOT IN'
            else:
                operator = 'IN'
            #value = "'" + "', '".join(ls_unchecked)  + "'"
            value = ", ".join(ls_unchecked)
        else:
            #value = "'" + "', '".join(ls_checked) + "'"
            value = ", ".join(ls_checked)
    #add the filter to the class
    trView_occ.addFieldfFilter (table, fieldname, operator, value)

    #reload data and enabled widgets
    tblView_data_fill()
    set_filters_enabled()


def tblView_data_clickitem(item):
    #when user click on a cell into tblView_data, select field into cb_fields
    current_column = tblView_data.currentIndex().column()
    field_name = tblView_data.model().sourceModel().header_labels[current_column]
    window.cb_fields.setCurrentText(field_name)

def set_filters_enabled():
    #manage enabled of widgets related to filters according to options
    field_name = window.cb_fields.currentText()
    table = trView_occ.currentIndex().data()
    field = trView_occ.get_field(table,field_name)
    #enabled the reset button if a filter is active
    try:  
        enabled = trView_occ.isFieldFiltered (table,field_name)
    except:
        enabled = False
    window.button_sel_reset.setEnabled(enabled)

    #enabled the tableView_item/lineEdit_filter according to operator and length of tableView_item
    try:
        first_value = window.tableView_item.model().item(0,0).data(0)
        if first_value.startswith('Error'):
            ls_enabled = False
        else:
            ls_enabled = (window.cb_operators.currentIndex() < 2)
    except:
        ls_enabled = False
    window.tableView_item.setEnabled(ls_enabled)
    window.lineEdit_filter.setEnabled(not ls_enabled)
    
def cb_fields_selectionchange():
    #on the dataSource tab
    #load the list of group (unique) value for filtering
    field_name = window.cb_fields.currentText()
    table = trView_occ.currentTable
    if table is None : return

    window.cb_operators.setCurrentIndex(0)
    #create the sql statement
    sql_query = "SELECT _fieldname_ FROM ("
    sql_query += trView_occ.sql_table_data(table) +") a"
    sql_query += "\nWHERE _fieldname_ IS NOT NULL "
    sql_query += "\n GROUP BY _fieldname_"
    sql_query += "\n ORDER BY _fieldname_ LIMIT 1000 "
    sql_query = sql_query.replace('_fieldname_', field_name)
    sql_query = sql_query.replace('_schema_', 'occurrences')
    sql_query = sql_query.replace('_table_name_', table)
    #print (sql_query)

    #execute and fill the query within a QStandardItemModel
    query = QtSql.QSqlQuery (sql_query)
    model2 = QtGui.QStandardItemModel()

    #test the count of distinct data, error if too large (exceed 1000 records)
    if query.size() == 1000:
        item = QtGui.QStandardItem("Error: too much data to apply a filter...")
        model2.appendRow(item)
    else:
        while query.next():
            try:
                item = QtGui.QStandardItem(str(query.value(field_name)))
                item.setCheckable(True)
                item.setCheckState(2)
                model2.appendRow(item)
            except:
                pass
    window.tableView_item.setModel(model2)
    set_filters_enabled()

def button_unresolved_click(value):
#click on the unresolved button
    #clear models
    tblView_data.setModel(None)
    tblView_resolution.setModel(None)
    tabWidget_data_select()











def tblview_user_dataset_clicked(index):
#click on one user dataset
    #clear models
    tblView_data.setModel(None)
    tblView_resolution.setModel(None)
    tblView_explore.setModel(None)
    QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

    #set the tabledef of saved dataset (hidden in the column1 of tblview_user_dataset)
    row = index.row()
    
    saveTabledefkey = index.model().index(row,2).data()
    saveTabledefvalue = eval(index.model().index(row,1).data())
    #add a new dataset
    table = trView_occ.add_dataset(saveTabledefkey, saveTabledefvalue)
    trView_occ.currentTable = trView_occ.tmp_table_name #table
    tabWidget_data_select()

def tblview_user_dataset_updateItem(index):
#set the new name for the dataset into the config sqlite dbase and in the list window.tblview_user_dataset
    new_name = index.data()
    key_uuid = index.sibling(index.row(), 2).data()
    sql_query = "UPDATE config_start SET name = '" + new_name + "' WHERE uuid = '" + key_uuid + "';"
    dbconfig = QtSql.QSqlDatabase.database("config")
    query = dbconfig.exec_(sql_query)
    if query.isActive():return
    
    msg = "The dataset <" + new_name + "> already exists "
    result = QMessageBox.information(None, "Rename a dataset", msg)
    sql_query = "SELECT name FROM config_start WHERE uuid = '" + key_uuid + "';"
    query = dbconfig.exec_(sql_query)
    query.next()
    db_text = query.value("name")
    #window.tblview_user_dataset.clearSelection()
    model = window.tblview_user_dataset.model()
    model.setData(index, db_text, Qt.DisplayRole)


def trView_occ_keyPress(value):
#to delete a datasource
    index = trView_occ.currentIndex()
    row = index.row()
    datasource_name = trView_occ.schema + "." + index.data()
    sql_query = "DROP TABLE " + datasource_name
    msg = "Are you sure to deleted the selected datasource < " + datasource_name + " > ?"
    if value == Qt.Key_Delete:
        result = QMessageBox.question(None, "Delete DataSource", msg, QMessageBox.Yes, QMessageBox.No)
        if result == QMessageBox.No: return
        #OK to delete
        query = QtSql.QSqlQuery(sql_query)
        #the table is deleted
        if query.isActive():
            trView_occ.model().removeRow(row)
            index = trView_occ.currentIndex()
            trView_occ_clicked (index)

def tblview_user_dataset_keyPress(value):
#to delete or rename a dataset
    index = window.tblview_user_dataset.currentIndex()
    if value == Qt.Key_F2:
        window.tblview_user_dataset.edit(index)
    elif value == Qt.Key_Delete:
        row = index.row()
        dataset_name = window.tblview_user_dataset.model().item(row,0).text()
        msg = "Are you sure to deleted the dataset < " + dataset_name + " > ?"
        result = QMessageBox.question(None, "Delete DataSet", msg, QMessageBox.Yes, QMessageBox.No)
        if result == QMessageBox.No: return
        model = window.tblview_user_dataset.model()
        dbconfig = QtSql.QSqlDatabase.database("config")
        key_uuid = window.tblview_user_dataset.model().item(row,2).text()
        sql_query = "DELETE FROM config_start WHERE uuid = '" + key_uuid + "';"
        query = dbconfig.exec_(sql_query)
        if query.isActive():
            model.removeRow(row)
            index = window.tblview_user_dataset.currentIndex()
            tblview_user_dataset_clicked (index)        

def button_import_dataset_click():
    import pandas as pd

    def set_postgres_dbname(db_name):
    #check and correct invalid characters
        db_name = re.sub(r'\W', '_', db_name)
        if db_name[0].isdigit():
            db_name = '_' + db_name
        db_name = db_name [:63]
        return db_name
    test = CSVTranslate()
    test.load()
    
    test.show_modal()
    return

    #set parameters to QfileDialog
    options = QFileDialog.Options()
    options |= QFileDialog.ReadOnly
    file_dialog = QFileDialog()
    file_dialog.setNameFilter("Fichiers CSV (*.csv)")
    file_dialog.setDefaultSuffix("csv")
    file_name, file_type = file_dialog.getOpenFileName(None, "Import a CSV File", "", "CSV Files (*.csv);;All files (*)", options=options)
    if file_name:
        # loop = True
        # db_name = os.path.basename (file_name)
        # db_name, extension = os.path.splitext(db_name)
        test = CSVTranslate()
        test.load()
        
        test.show_modal()
    return


    while loop:
        db_name, ok = QInputDialog.getText(None, "Datasource Name", "Please enter the datasource name", text = db_name)
        if not ok: return
        if db_name in trView_occ.get_tables():
            msg = "The dataset <" + db_name + "> already exists "
            db_name = db_name + "_1"
        elif db_name != set_postgres_dbname(db_name):
            msg = "The name <" + db_name + "> contains invalid characters for database "
            db_name = set_postgres_dbname(db_name)
        else:
            loop = False
            msg = "Unable to open the file <" + file_name + "> !"
            
            troc = pd.read_csv(file_name, sep = ';', encoding='utf-8')


            type_columns = troc.dropna().dtypes
            columns = {}
            type_transpose = {'int64': 'integer', 'bool': 'boolean', 'float64': 'numeric'}
            for header, _type in type_columns.items():
                no_nullvalue = troc [header].dropna()
                _type = _type.name
                
                if _type == 'object':
                    if all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
                        _type = 'boolean'
                    else:
                        _type = "text"
                    type_columns[header] = _type

                if _type == 'float64':
                    try:
                        if no_nullvalue.apply(lambda x: float(x).is_integer()).all():
                            _type = 'integer'
                    except:
                        if pd.api.types.is_string_dtype(no_nullvalue):
                            _type = "numeric"
                    type_columns[header] = _type
                
                try:
                    _type = type_transpose[_type]
                except:
                    pass
                columns[header] = {"fieldref" : None, "type" : _type}

            #print (columns)
            test = CSVTranslate()
            test.load(columns)
            
            test.show_modal()
            return



            # for header in troc.columns:
            #     _type = None
            #     no_nullvalue = troc [header].dropna()
            #     if pd.api.types.is_bool_dtype(no_nullvalue):
            #         _type = "Boolean"
            #     elif all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
            #         _type = 'Boolean' 
            #     elif pd.api.types.is_integer_dtype(no_nullvalue):
            #         _type = "Integer"
            #     # elif no_nullvalue.apply(lambda x: float(x).is_integer()).all():
            #     #     _type = 'Integer'
            #     elif pd.api.types.is_string_dtype(no_nullvalue):
            #         _type = "Text"
            #     elif pd.api.types.is_datetime64_any_dtype(no_nullvalue):
            #         _type = "Date"

                
                #if _type is None:



                # try:
                #     if no_nullvalue.apply(lambda x: float(x).is_integer()).all():
                #         _type = 'Integer'            
                # except:
                #     _type = None


                # if all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
                #     _type = 'Boolean'                   


                #     if all(str(val).lower() in ['true', 'false', 'oui', 'non'] for val in no_nullvalue):
                #         _type = 'Boolean'
                #     elif pd.api.types.is_string_dtype(no_nullvalue):
                #         _type = 'Text'
                #     elif pd.api.types.is_datetime64_any_dtype(no_nullvalue):
                #         _type = 'DateTime'
                #     elif no_nullvalue.apply(lambda x: float(x).is_integer()).all():
                #         _type = 'Integer'
                #     else:
                #         _type = "Numeric"
                # except:
                #     _type = 'Text'
                    
                #print (header, _type)



            # troc['taxaname'] = troc['taxaname'].astype('str')
            # print (troc.dtypes)

            with open(file_name, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter = ';', skipinitialspace = True, quotechar = '"')
                total_rows = len(list(reader))
                file.seek(0)
                headers = next(reader)

                


                #truc = test.get_table_headers (headers, reader, 10)

                


            valid, msg = trView_occ.is_fieldsValid(headers)
            
            test.load(headers)
            
            test.show_modal()
            return

            if valid :
                myprogressBar.setVisible(True)
                myprogressBar.setValue(0)
                db_name = trView_occ.schema + "." + db_name
                test = CSVImporter(db_name)
                test.import_inprogress.connect(set_progressBar_value)
                if test.import_csv (file_name):
                    trView_occ.load()
                    msg = "The dataset <" + db_name + "> was successfully imported"
                else:
                    msg = "Error : the dataset <" + db_name + "> could not be imported"
                myprogressBar.setVisible(False)
        QMessageBox.information(None, "Add a dataset", msg)


def set_progressBar_value (value):
    myprogressBar.setValue(int(100*value))
    
def button_save_dataset_click():
#save the selected datasource to a new dataset    
    tab_key = []
    model = window.tblview_user_dataset.model()
    #get the list of existing user dataset
    for row in range(model.rowCount()):
        tab_key.append(model.item(row, 0).text())
    #loop while the name already exist or user press cancel
    loop = True
    while loop:
        dataset_name, ok = QInputDialog.getText(None, "Dataset Name", "Please enter the dataset name")
        if not ok: return #exit
        if dataset_name in tab_key:
            msg = "The dataset <" + dataset_name + "> already exists "
            result = QMessageBox.information(None, "Add a dataset", msg)
        else:
        #save the new dataset
            loop = False
            dbconfig = QtSql.QSqlDatabase.database("config")
            data_value = str(trView_occ.tab_stacked_datasource())
            import uuid
            key_uuid = str(uuid.uuid4())
            sql_query = "INSERT INTO config_start(key, name, parameter1, parameter2, uuid) "
            sql_query +="VALUES ('dbdataset', '" + dataset_name +"','" + trView_occ.schema + "'," + chr(34) + data_value + chr(34) +",'" + key_uuid + "');"
            query = dbconfig.exec_(sql_query)
            if query.isActive():
                item =  QtGui.QStandardItem(dataset_name)
                item1 = QtGui.QStandardItem(data_value)
                item2 = QtGui.QStandardItem(key_uuid)
                model.appendRow([item, item1, item2])
                window.toolBox.setCurrentIndex(2)
                window.toolBox.repaint()
                window.tblview_user_dataset.selectionModel().setCurrentIndex(item.index(), QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                window.tblview_user_dataset.repaint()
                tblview_user_dataset_clicked (item.index())
    return     

def tblview_traits_dataset_clicked(index):
#click on one trait dataset    
    #clear models
    tblView_data.setModel(None)
    tblView_resolution.setModel(None)
    tblView_explore.setModel(None)
    QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

    #create and add a standardized table from query
    row = index.row()
    trait = index.model().index(row,0).data()
    #get a tabledef from a trait
    tabledef = trView_occ.tab_staked_traits(trait)
    #add a new dataset
    table = trView_occ.add_dataset(trait, tabledef)
    trView_occ.currentTable = trView_occ.tmp_table_name #table
    tabWidget_data_select()

def trView_occ_clicked(value = False):
#click on one datasource    
    #clear models    
    tblView_data.setModel(None)
    tblView_resolution.setModel(None)
    tblView_explore.setModel(None)
    QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
    table = trView_occ.currentIndex().data()
    trView_occ.currentTable = table
    tabWidget_data_select()

def trView_occ_checkedchange(dataset = None):
#create and explore a dataset
    table = trView_occ.currentTable
    #create the dataset if table is a datasource
    if trView_occ.is_datasource(table):
        tabledef = {}
        tabledef[table] = trView_occ.get_fields(table)
        table = trView_occ.add_dataset(table, tabledef)
    #get the temp table name
    table = trView_occ.tmp_table_name #
    myPlotClass.load(table)

#load the accepted figure list
    #happen when user check or uncheck a occurrence database
    selected_text = window.cb_figures.currentText()
    window.cb_figures.currentIndexChanged.disconnect(figure_reset)
    window.cb_figures.clear()
    #get and fill the list of figure types
    for fieldPlot in myPlotClass.graphTypes:
        try:
            window.cb_figures.addItem(fieldPlot)
        except:
            pass
    window.cb_figures.setCurrentText(selected_text)
    window.cb_figures.currentIndexChanged.connect(figure_reset)

#load the taxa traits with density
    PN_tlview_traits = PN_taxa_identity (window.trView_properties, True)
    _data = myPlotClass.get_taxa_properties()
    tab_header = ['Category', 'Species', 'Occurrences']
    PN_tlview_traits.setData(_data)
    model = window.trView_properties.model()
    model.setHorizontalHeaderLabels(tab_header)
    window.trView_properties.resizeColumnToContents(0)
    #window.trView_properties.header().setSectionResizeMode(0,QHeaderView.Stretch)
    window.trView_properties.header().setDefaultAlignment(Qt.AlignCenter)   
#load the list of taxa/traits
    trview_explore_traits_fill()
    return

def tblview_import_fill():
    import pandas as pd
    results = []
    headers = {}

    #create the query
    table = trView_occ.currentIndex().data()
    # sql = "SELECT * FROM " + trView_occ.schema + '.' + table + ' LIMIT 1'
    # query = QtSql.QSqlQuery (sql)
    # record = query.record()

    # Get the column names/type
    # column_names = [query.record().fieldName(i) for i in range(record.count())]
    # column_types = [get_column_type(query.record().field(i).type()) for i in range(record.count())]

    # column_names =[]
    
    



    sql_gabarit =  "SELECT _pos AS index, '_header'::text AS header, min(_header)::text AS min, max(_header)::text AS max"
    sql_gabarit += ", count(*) FILTER (WHERE _header IS NULL)::integer AS null_value"
    sql_gabarit += ", count(DISTINCT _header) AS unique_value"
    sql_gabarit += ", 0::integer AS total"
    sql_gabarit += ", '_fieldref' AS fieldref"
    tab_query = []

    table_def = trView_occ.get_fields(table)
    i = 0
    for fieldref, field_def in table_def.items():
        _query = sql_gabarit.replace('_fieldref', fieldref)



        if field_def["field_type"] == 'boolean':

        


    # for i in range(len(column_names)):
    #     _query = sql_gabarit
    #     if column_types[i] == 'boolean':
            _query = _query.replace('min(_header)', "'False'")
            _query = _query.replace('max(_header)', "'True'")
        #_query = _query.replace ('_header', column_names[i])
        _query = _query.replace ('_header', field_def["field_name"])

        _query = _query.replace ('_pos', str(i))
        if i == 0:
            _query = _query.replace ('0::integer', 'count(*)::integer')
        _query += " FROM " + trView_occ.schema + '.' + table
        tab_query.append(_query)
        i+=1
    sql_query = '\nUNION '.join(tab_query)
    sql_query += '\nORDER BY index'
    
    query = QtSql.QSqlQuery (sql_query)
    rows = 0
    while query.next():
        rows = max(rows, query.value('total'))
        header = query.value("header")
        field_def = trView_occ.get_field (table, header)        
        _type = field_def["field_type"]
        non_null_value = rows - query.value("null_value")
        unique_value = query.value("unique_value")
        duplicated_value = (unique_value < rows)
        min_value = query.value("min")
        max_value = query.value("max")
        fieldref = query.value("fieldref")
        if not fieldref in list_db_fields:
            fieldref = None
        # add the result into the headers dictionnary
        headers[header] = {"fieldref" : fieldref, "type" : _type,   "non null": non_null_value, "duplicated" : duplicated_value, "min" : min_value, "max" : max_value}

    _summary = str(rows) + ' rows, ' + str(query.size()) + ' columns'
    window.label_summary.setText(_summary)

    #fill the QtableView
    model = NonEditableModel()
    # Add header for columns
    model.setHorizontalHeaderItem(0, QtGui.QStandardItem("Column"))
    for index, subkey in enumerate(headers[next(iter(headers))]):
        model.setHorizontalHeaderItem(index + 1, QtGui.QStandardItem(subkey))
    # Fill cells with self.headers
    for row, (key, subdict) in enumerate(headers.items()):
        # Add checkable key to the first column
        item = QtGui.QStandardItem(key)
        item.setCheckable(True)
        item.setCheckState(Qt.Checked)
        model.setItem(row, 0, item)
        # Add values from the sub-dictionnary to other columns
        for col, value in enumerate(subdict.values()):
            if value is not None:
                model.setItem(row, col + 1, QtGui.QStandardItem(str(value)))
        # Set the model to the tblview_columns
    window.tblview_import.setModel(model) 
    header = window.tblview_import.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Stretch)

    # Apply a delegate to change color and edit options
    combo_delegate = ComboBoxDelegate()
    window.tblview_import.setItemDelegate(combo_delegate)
    combo_delegate.closeEditor.connect(handleEditingFinished)    

def handleEditingFinished(editor, index):
    # Slot to handle the editing finished event
    if isinstance(editor, QComboBox):
        selected_item = editor.currentText()
        model = window.tblview_import.model()
        c_row = window.tblview_import.currentIndex().row()
        #Check that there is only one reference to a fieldref
        for row in range(model.rowCount()):
            index = model.index(row, 1)
            fieldref = model.data(index)
            if row != c_row and fieldref == selected_item:
                model.setData (model.index(row,1),'')
    elif isinstance(editor, QLineEdit):
        selected_item = editor.text()

def tabWidget_data_select(value = False):
#main function to manage the three main tab (resolution, datasource, explore)
    QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
    tab_name = window.tabWidget_data.currentWidget().objectName()
    state = True
    model = None
    rows = 0
    # myDataThread.stop()
    # print (myDataThread.stop())
    similarity_widget_setVisible(False)
    if tab_name == 'tab_data':
        if tblView_data.model() is None:
            myDataThread.offset = 0
            tblView_data_fill()
            cb_fields_selectionchange()
        rows = myDataThread.query.size()
    elif tab_name == 'tab_taxa':
        if tblView_resolution.model() is None:
            tblView_resolution_fill()
        rows = tblView_resolution.model().rowCount()         
    elif tab_name == 'tab_explore':
        state = False
        if tblView_explore.model() is None:
            trView_occ_checkedchange()
        rows = tblView_explore.model().rowCount()
    elif tab_name == 'tab_import':
        state = False
        tblview_import_fill()

    window.button_unresolved.setVisible(state)
    #window.label_rows.setVisible(True)
    window.label_rows.setText (str(rows) + " row(s)")

    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()

def tblView_data_fill():
# fill data according to the selected occurrences
    if window.tabWidget_data.currentWidget().objectName() != 'tab_data': return
    
    #stop the thread if in progress
    # while myDataThread.isRunning():
    #     myDataThread.stop()
        # myDataThread.terminate()
        # myDataThread.wait()
        #myDataThread.exit()
        
            
    #load variables
    #table = trView_occ.currentIndex().data()
    table = trView_occ.currentTable
    if table is None: return

    #clean the tblView_data
    proxyModel =  QSortFilterProxyModel()
    proxyModel.setSourceModel(PN_occ_model())
    tblView_data.setModel(proxyModel)
    model = tblView_data.model().sourceModel()
    model.header_labels = []
    
    #create the query
    sql_query = "SELECT * FROM (" + trView_occ.sql_table_data(table) + ") z"
    if window.button_unresolved.isChecked():
        sql_query += "\nWHERE NOT valid"
    #sql_query += "\nORDER BY id_source"
    #print (sql_query)

    #execute the query
    query = QtSql.QSqlQuery (sql_query)
    record = query.record()

    #display the number of rows
    window.label_rows.setText (str(query.size()) + " row(s)")

    #add fields to the cb_fields combobox, to the model header
    #and check for filtered fields (to be highlight see headerData in occ_model)
    field = window.cb_fields.currentText()
    try:
        window.cb_fields.currentIndexChanged.disconnect(cb_fields_selectionchange)
    except:
        pass
    window.cb_fields.clear()
    tab_header = [] #tab of the header fields
    tab_filtered = [] #tab of the header fields with an active filter (for rendering)
    for i in range(record.count()):
        try:
            _field = str(record.fieldName(i))
            window.cb_fields.addItem(_field)
            tab_header.append(_field)
            if trView_occ.isFieldFiltered(table, _field):
                tab_filtered.append(i)
        except:
            pass
    window.cb_fields.setCurrentText(field)
    window.cb_fields.currentIndexChanged.connect(cb_fields_selectionchange)   
    model.header_labels = tab_header
    model.header_filtered = tab_filtered
    #send query to thread fill data
    myDataThread.query = query
    myDataThread.model = model
    #myDataThread.data_ready.connect(tblView_data_update_model)
    myDataThread.start()
    




def tblView_data_verticalScroll(value):
#move in the database with the vertical scroll bar
    if tblView_data.model().rowCount() == myDataThread.query.size():
        return
    if value == tblView_data.verticalScrollBar().maximum():
        myDataThread.offset = tblView_data.model().rowCount() -1
        myDataThread.next(tblView_data.model().rowCount() -1)
 
class DataThread():
    data_ready = pyqtSignal(list)
    def __init__(self, parent=None):
        #super(DataThread, self).__init__(parent)        
        self.query = None
        self.model = None
        self.stopped = False
        self.statut = 0
        self.offset = 0
        self.limit = 500
        self.data = []

    def start(self):
        self.offset = 0
        self.data = []
        self.run()

    def next (self, offset):
        self.offset = offset
        self.query.seek(self.offset)
        self.run()

    def stop(self):
        self.stopped = True

    def run(self):
        #print ("start")
        # Execute the long task to fill a model with data from a query (QtSql.QSqlQuery)
        self.stopped = False  
        record = self.query.record()
        i = 1
        #data = []
        #self.query.seek(self.offset)
        while not self.stopped and self.query.next():
            _data = []
            for x in range(record.count()):
                _data.append(self.query.value(record.fieldName(x)))
            self.data.append(_data)
            i += 1
            
            #stop process if statut =0
            if i == self.limit + self.offset:
                self.model.resetdata(self.data) 
                #time.sleep(0.01)
                i = 0
                break
                #tblView_data.repaint()
                #i = 0
            #exit if more than 10000 rows
            #if i >= 100000:break
        #self.statut == 0
        #self.data_ready.emit(data)
        self.model.resetdata(self.data)
        #print ("end")


















############# tblView_resolution (tab "Taxonomic Resolution" of the GUI) ###########
def similarity_widget_setVisible(visible = True):
    window.slider_similarity.setVisible (visible)
    window.button_similarity.setVisible (visible)
    window.label_similarity.setVisible (visible)

def button_similarity_clicked(toggled):
    #toggled  = window.button_similarity.isChecked()
    tblView_resolution_fill(toggled)

def tblView_resolution_fill(similarity = False):
#Taxonomic resolution list, i.e. translate original_name to taxonref according to synonyms dictionnary
    unresolved_mode = window.button_unresolved.isChecked()
    if not unresolved_mode:
        window.button_similarity.toggled.disconnect (button_similarity_clicked)
        window.button_similarity.setChecked(False)
        window.button_similarity.toggled.connect (button_similarity_clicked)

    similarity_widget_setVisible(unresolved_mode)
    #drop the content of the tableview (tblView_resolution)
    window.label_rows.setText ("0 row(s)")
#setting the tableView_resolution
    proxyModel =  QSortFilterProxyModel()
    proxyModel.setSourceModel(PN_taxa_resolution_model())
    tblView_resolution = window.tableView_resolution
    tblView_resolution.setModel(proxyModel)
    tblView_resolution.sortByColumn(0, Qt.AscendingOrder)
    tblView_resolution.setColumnWidth(0,500)
    tblView_resolution.horizontalHeader().setStretchLastSection(True)
    selection = tblView_resolution.selectionModel()
    selection.selectionChanged.connect(tblView_resolution_clickitem)
    selection.currentChanged.connect(tblView_resolution_before_clickitem)

    try:
        tblView_resolution.model().sourceModel().resetdata(None)
        tblView_resolution.repaint()
    except Exception:
        pass

    #get the parameters (schema, table, fieldname of the fieldref 'taxaname')
    #schema = trView_occ.schema
    table = trView_occ.currentTable # trView_occ.currentIndex().data()

    if table is None : return
    sql_query = trView_occ.sql_taxa_resolution(table, unresolved_mode)
    #query the sql and fill the tblView_resolution model
    #print (sql_query)
    data = []
    query = QtSql.QSqlQuery (sql_query)
    rows = 1
    pvalue = 0
    query_size = query.size()

    while query.next():
        newRow = PNSynonym(
                        query.value("original_name"), 
                        query.value("taxonref"),
                        query.value("id_taxonref") 
                        )
        newRow.keyname = query.value("keyname")
        if similarity:
            QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
            myprogressBar.setVisible(True)
            myprogressBar.setValue(0)
            pvalue +=1
            myprogressBar.setValue(int(100*pvalue/query_size))

            id_taxonref, taxonref, score = tblView_resolution_fillsimilarity(query.value("original_name"))
            if not taxonref is None:
                newRow.taxon_ref = taxonref + " (" + str(score) + " %)"
                tblView_resolution.model().sourceModel().additem (newRow)
                tblView_resolution.repaint()
                rows = tblView_resolution.model().sourceModel().rowCount()
                window.label_rows.setText (str(rows) + " row(s)")
        else:
            data.append(newRow)
    myprogressBar.setVisible(False)
    # window.button_similarity.toggled.disconnect (button_similarity_clicked)
    # window.button_similarity.setChecked(False)
    # window.button_similarity.toggled.connect (button_similarity_clicked)
    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
    if len(data) > 0:
    #reset the model and repaint the tblView_resolution
        #window.label_rows.setText (str(query.size()) + " row(s)")
        tblView_resolution.model().sourceModel().resetdata(data)   
        tblView_resolution.repaint()
    rows = tblView_resolution.model().sourceModel().rowCount()
    window.label_rows.setText (str(rows) + " row(s)")
        # else:
        #     tblView_resolution.model().sourceModel().additem (newRow)
        # tblView_resolution.repaint()
        #
    #set_enabled_buttons()


def tblView_resolution_fillsimilarity(search_name):
        threshold = window.slider_similarity.value()/100
        threshold = str(min(threshold, 0.99))
        #sql_query = "SELECT taxonref, score, id_taxonref FROM taxonomy.pn_taxa_searchname('" + selecteditem.synonym +"', " + threshold + ") LIMIT 1"

        sql_txt = "SELECT id_taxonref, taxonref, score FROM taxonomy.pn_taxa_searchname('" + search_name +"', "+ threshold +") LIMIT 1"
        query = QtSql.QSqlQuery (sql_txt)
        if query.next() :
                return query.value("id_taxonref"), query.value("taxonref"), query.value("score")
        return None, None, None

        # imax = 100
        # for synonym in tblView_resolution.model().sourceModel()._data:
        #     taxonref = ''
        #     category =''
        #     sql_txt = "SELECT taxonref FROM taxonomy.pn_taxa_searchname('" + synonym.synonym +"', 0.6)"
            

        #     txt = synonym.synonym + ';' + category + ';' + taxonref
        #     i +=1
        #     ivalue= int(100*i/imax)
        #     myprogressBar.setValue(ivalue)
        #     window.statusbar.showMessage ("Export in progress, " + str(i) + " of "  +str(imax) + " rows")
        #     f.write(txt +'\n')
        #     myprogressBar.setVisible(False)




def set_similarity(value):
    #slot for the slider of similarity threshold
    value = (value // 10) * 10
    value = max(20, value)
    window.slider_similarity.setSliderPosition(value)
    window.label_similarity.setText(str(value) + ' %')


def tblView_resolution_before_clickitem(current_index, previous_index):
    # unreference the associated button_shortcut on previous_index (before clicking a new item)
    if previous_index.row() < 0:
        return
    elif previous_index.row() == current_index.row():
        return
    column2_index = tblView_resolution.model().index(previous_index.row(),1)
    tblView_resolution.setIndexWidget(column2_index, None)

def tblView_resolution_clickitem():
    #get the current selectedItem
    selecteditem = tblView_resolution.model().data(tblView_resolution.currentIndex(), Qt.UserRole)
    #id_taxon_ref = selecteditem.idtaxonref
    column2_index = tblView_resolution.model().index(tblView_resolution.currentIndex().row(),1)
    #manage the shortcut button over the second column of the main listview
    if not selecteditem.resolved:
        #button_txt = selecteditem.taxaname
        button_shortcut = QtWidgets.QPushButton("button")
        font = QtGui.QFont()
        font.setPointSize(10)
        button_shortcut.setFont
        button_shortcut.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        stylesheet = "QPushButton {border-style: outset;border-width: 2px; border-radius: 10px;}"
        button_shortcut.setStyleSheet(stylesheet)
        
        button_shortcut.clicked.connect(button_sortcut_click)
        threshold = str(window.slider_similarity.value()/100)
        sql_query = "SELECT taxonref, score, id_taxonref FROM taxonomy.pn_taxa_searchname('" + selecteditem.synonym +"', " + threshold + ") LIMIT 1"
        query = QtSql.QSqlQuery (sql_query)
        if query.next() :
            button_txt = str(query.value("taxonref")) + ' - (' +str(query.value("score")) +' %)'
            selecteditem.suggested_id_taxonref = int(query.value("id_taxonref"))
            selecteditem.suggested_name_taxon_ref = str(query.value("taxonref"))
        else:
            button_txt = 'Unresolved Taxaname'
        button_shortcut.setText (button_txt)
        tblView_resolution.setIndexWidget(column2_index, button_shortcut)
    else:
        pass
    
def button_sortcut_click():
    #manage the mobile button that cover the tblView_resolution for the unresolved taxanames
    #add synonym when click with shift key pressed
    selecteditem = tblView_resolution.model().data(tblView_resolution.currentIndex(), Qt.UserRole)
    modifiers = QtWidgets.QApplication.keyboardModifiers()
    if modifiers == QtCore.Qt.ShiftModifier:
        new_idtaxonref = selecteditem.suggested_id_taxonref
        new_synonym = selecteditem.synonym
        new_category = 'Orthographic'
        taxa_name = selecteditem.suggested_name_taxon_ref
        sql_query = "SELECT taxonomy.pn_taxa_edit_synonym ('" +new_synonym + "','" + new_category +"'," + str(new_idtaxonref) +")"
        result = QtSql.QSqlQuery (sql_query)
        if len(result.lastError().nativeErrorCode ()) == 0:
        #if add_newsynonym (new_idtaxonref, new_synonym):
            selecteditem.id_taxonref = new_idtaxonref
            selecteditem.taxon_ref = taxa_name
    else:
        class_newname = PN_edit_synonym (selecteditem)
        #class_newname.button_click.connect(button_addname_click)
        class_newname.show()
    tblView_resolution.repaint()
    column2_index = tblView_resolution.model().index(tblView_resolution.currentIndex().row(),1)
    tblView_resolution.setIndexWidget(column2_index, None)
    tblView_resolution_clickitem()

def export_to_image():
#export figure to file
    #set parameters to QfileDialog
    options = QFileDialog.Options()
    options |= QFileDialog.ReadOnly
    #options |= QFileDialog.DontUseNativeDialog
    file_dialog = QFileDialog()
    file_dialog.setNameFilter("Export Image")
    file_dialog.setDefaultSuffix("png")
    file_name, file_type = file_dialog.getSaveFileName(None, "Export File", "", "Export Files (*.png *.pdf *.jpg);;PNG Files (*.png);;PDF Files (*.pdf);;JPG Files (*.jpg);;All files (*)", options=options)

    #write the data
    if file_name:
        #check for extension in the name
        if file_name.lower()[-4:] in ('.png', '.jpg', '.pdf'):
            ext = file_name.lower()[-4:]        
        elif file_type =='PDF Files (*.pdf)':
            ext = '.pdf'
        elif file_type =='JPG Files (*.jpg)':
            ext = '.jpg'
        else:
            ext = '.png'
        #add extension if not
        if not file_name.lower().endswith(ext):
            file_name += ext
        #write the data
        ext = ext[1:]
        myFigure.figure.savefig(file_name, dpi = 600, format = ext)

def export_to_csv():
#export any of the three main lists to csv files (tblView_resolution, tblView_data, tblView_explore)
#use intern getdata() function for Abstract models and qtableview_to_list for standard models
    def qtableview_to_list(qtableview, with_header = False):
        data = []
        model = qtableview.model()
        if model is not None:
            # Extract header if with_header
            if with_header:
                headers = [model.headerData(col, Qt.Horizontal) for col in range(model.columnCount())]
                data.append(headers)
            # Extract data from any cells
            for row in range(model.rowCount()):
                row_data = [model.item(row, col).text() for col in range(model.columnCount())]
                data.append(row_data)
        return data
    import csv
    #get data according to tabWidget_data
    tab_name = window.tabWidget_data.currentWidget().objectName()
    if tab_name == 'tab_data':
        data = tblView_data.model().sourceModel().getdata(True)
        i = len(data)
        if i < myDataThread.query.size():
            myDataThread.query.seek(i-1)
            record = myDataThread.query.record()
            while myDataThread.query.next():
                _data = []
                for x in range(record.count()-1):
                    _value = get_str_value(myDataThread.query.value(record.fieldName(x)))
                    _data.append(_value)
                data.append(_data)
            myDataThread.query.seek(i-1)
    elif tab_name == 'tab_taxa':
        data = tblView_resolution.model().sourceModel().getdata(True)
    elif tab_name == 'tab_explore':
        data = qtableview_to_list(tblView_explore, True)

    #set parameters to QfileDialog
    options = QFileDialog.Options()
    options |= QFileDialog.ReadOnly
    #options |= QFileDialog.DontUseNativeDialog
    file_dialog = QFileDialog()
    file_dialog.setNameFilter("Fichiers CSV (*.csv)")
    file_dialog.setDefaultSuffix("csv")
    file_name, _ = file_dialog.getSaveFileName(
        None, "Export to CSV File", "", "CSV Files (*.csv);;All files (*)", options=options)
    #write the data
    if file_name:
        #check for csv extension
        if not file_name.lower().endswith(".csv"):
            file_name += ".csv"
        #write the data
        with open(file_name, "w", newline="") as file:
            writer = csv.writer(file, delimiter=';', skipinitialspace = True, quotechar='"')
            for row in data:
                writer.writerow(row)




class CenterDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.displayAlignment = Qt.AlignCenter
        super().paint(painter, option, index)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = uic.loadUi("pn_occurrences.ui")


   #cb_dbase = window.cb_dbase





 #add a progressbar and a label within the statusbar
    myprogressBar = QProgressBar()
    myprogressBar.setGeometry(100, 40, 30, 25)
    myprogressBar.setVisible(False)
    myprogressBar.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding)
    window.statusbar.addPermanentWidget(myprogressBar)
    data_msg = QLabel()
    data_msg.setGeometry(100, 40, 30, 25)
    data_msg.setVisible(True)
    window.statusbar.addPermanentWidget(data_msg)

# #setting the tableView_resolution
    tblView_resolution = window.tableView_resolution
    #tblView_resolution.clicked.connect(tblView_resolution_clickitem)

#setting the tblView_data
    tblView_data = window.tableView_data
    tblView_data.clicked.connect(tblView_data_clickitem)
    tblView_data.verticalScrollBar().valueChanged.connect(tblView_data_verticalScroll)

#setting the tblView_explore
    tblView_explore = window.trview_explore_traits
    tblView_explore.clicked.connect(figure_plot)

#set the occurrences treeview
    trView_occ = PN_occ_tables ('occurrences')
    window.trView_occ_VLayout.insertWidget(1, trView_occ)
    trView_occ.pressed.connect(trView_occ_clicked)
    trView_occ.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


    trView_occ.keyPressEvent = lambda event: trView_occ_keyPress(event.key()) if event.key() in [Qt.Key_F2, Qt.Key_Delete] else None
    

#setting the menu action connector slots
    # window.actionExport_data.triggered.connect(export_data)
    # window.actionWrite_id_taxaref.triggered.connect(write_data)
    window.actionQuit.triggered.connect(sys.exit)


#set the thread 
    myDataThread = DataThread() 
   

#set the slots
    
    window.slider_similarity.valueChanged.connect (set_similarity)    
    window.tabWidget_data.currentChanged.connect(tabWidget_data_select)

    window.button_similarity.toggled.connect (button_similarity_clicked)
    window.button_unresolved.toggled.connect(button_unresolved_click)
    window.buttonbox_filter.button(QDialogButtonBox.Apply).clicked.connect(buttonbox_apply_click)
    window.button_sel_reset.clicked.connect(buttonbox_reset_click)
    window.button_sel_all.clicked.connect(buttonbox_selall_click)
    window.button_sel_inverse.clicked.connect(buttonbox_inverse_click)
    window.button_figure_apply.clicked.connect(figure_plot)
    window.button_figure_reset.clicked.connect(figure_reset)
    window.button_taxa_categories.toggled.connect(trview_explore_traits_fill)
    window.button_save_dataset.clicked.connect(button_save_dataset_click)
    window.button_import_dataset.clicked.connect(button_import_dataset_click)
    window.button_taxa_clear.clicked.connect(trview_taxa_deselectedItems)

    window.button_export_data.clicked.connect(export_to_csv)
    window.button_save_figure.clicked.connect(export_to_image)
    

    window.cb_figures.currentIndexChanged.connect(figure_reset)
    window.cb_operators.addItems(['equal', 'different', 'contains', 'superior', 'inferior', 'greater', 'less'])
    window.cb_operators.currentIndexChanged.connect(set_filters_enabled)
    window.cb_figure_rank.currentIndexChanged.connect(trview_explore_traits_fill)
    window.cb_figure_function.currentIndexChanged.connect(trview_explore_traits_fill)
    window.cb_figure_taxa.currentIndexChanged.connect(trview_explore_traits_fill)
    #window.button_taxa_exclusive.toggled.connect(trview_explore_traits_fill)
      
    window.trView_properties.clicked.connect(trview_explore_traits_fill)
    window.tblview_traits_dataset.clicked.connect(tblview_traits_dataset_clicked)
    window.tblview_user_dataset.clicked.connect(tblview_user_dataset_clicked)
    window.tblview_user_dataset.keyPressEvent = lambda event: tblview_user_dataset_keyPress(event.key()) if event.key() in [Qt.Key_F2, Qt.Key_Delete] else None
    
    window.frame_toolbar_figure.setVisible(False)
    window.tblview_traits_dataset.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    window.tblview_user_dataset.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    window.toolBox.setItemIcon(0, window.style().standardIcon(51))
    window.toolBox.setItemIcon(1, window.style().standardIcon(53))
    window.toolBox.setItemIcon(2, window.style().standardIcon(53))

    window.button_taxa_clear.setToolTip("Unchecked all selected properties")
    window.button_taxa_categories.setToolTip("All categories must be satisfied")

    

    myPlotClass = PN_occ_explore()
    myFigure = FigureCanvas(plt.figure())
    myFigure.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    window.figure_vlayout.addWidget(myFigure)
    similarity_widget_setVisible(False)

    LS_dbconnection = []
    load_dbconnections()    
    window.cb_dbase.currentIndexChanged.connect(cb_dbase_selectionchange)
    window.cb_dbase.setCurrentIndex (2)
    window.show()
   
    with open("Diffnes.qss", "r") as f:
    #with open("Photoxo.qss", "r") as f:
         _style = f.read()
         app.setStyleSheet(_style)

    sys.exit(app.exec_())

'''
this is a multiligne comment
'''
















############# figure to plot (tab "Explore DataSet" of the GUI) ###########
# def trView_taxa_fill():
#     #load the treeview list of taxa
#     model = QtGui.QStandardItemModel()
#     root = QtGui.QStandardItem("All Taxa")
#     model.appendRow([root],)
#     ls_taxas = trView_occ.get_taxas()
#     for _family, _value in ls_taxas.items():
#         family = QtGui.QStandardItem(_family)
#         for _genus, _species in _value.items():
#             try:
#                 subitem = QtGui.QStandardItem(_genus)
#                 family.appendRow([subitem],)
#             except:
#                 _species = None
#             try:
#                 for taxa in _species:
#                     species = QtGui.QStandardItem(taxa)
#                     subitem.appendRow([species],)
#             except:
#                 print ('taxa =', _value)
#                 pass
#         model.appendRow([family],)
#     #     root.appendRow([family],)
#     # model.appendRow([root],)
#     window.trView_properties.setModel(model)
#     window.trView_properties.clicked.connect(figure_plot)

# def trView_taxa_selectitem():
#     figure_plot()
#     return
#     #fill the list result_trView_occ with the trait datas
#     try:
#         taxa = window.trView_properties.currentIndex().data()
#     except:
#         taxa = ''
#     if taxa == "All Taxa":
#         taxa = ''
#     elif taxa is None:
#         taxa = ''
#     myPlotClass.searchtaxa = taxa
#     if window.cb_figures.currentIndex() == 0:
#         PN_tlview_traits = PN_taxa_identity (window.result_trView_occ)
#         PN_tlview_traits.setData(myPlotClass.get_traits_occurrences())
#         tab_header = ['Category', 'Species', 'Occurrences']
#         model = window.result_trView_occ.model()
#         model.setHorizontalHeaderLabels(tab_header)
#         window.result_trView_occ.header().setSectionResizeMode(0,QHeaderView.Stretch)
#         window.result_trView_occ.header().setDefaultAlignment(Qt.AlignLeft|Qt.AlignVCenter)
#     else:
#         figure_plot()




# def fill_fields():
#     table = trView_occ.currentIndex().data()
#     sql_query = "SELECT column_name, data_type"
#     sql_query += "\n FROM information_schema.columns "
#     sql_query += "\n WHERE table_schema = '_schema_' AND table_name =  '_tablename_'"
#     sql_query += "\n ORDER BY ordinal_position"
#     sql_query = sql_query.replace('_tablename_', table)
#     sql_query = sql_query.replace('_schema_', 'occurrences')
#     #print (sql_query)
#     query = QtSql.QSqlQuery (sql_query)
#     window.cb_fields.clear()
#     while query.next():
#         field = query.value("column_name")
#         window.cb_fields.addItem(field)

 
# def fill_listsimilarname(idtaxonref):
#     # fill the table_view2 model with similar names of the input idtaxonref
#     sql_query = "SELECT synonym, category, id_synonym, id_taxonref, taxonref FROM taxonomy.pn_taxa_synonyms("+ str(idtaxonref) +")"
#     data = []
#     model = table_view2.model()
#     #clear the table of similar names
#     model.sourceModel().resetdata(None)
#     query = QtSql.QSqlQuery (sql_query)
#     while query.next():
#         #data.append(PNSynonym(query.value("id_taxon_ref"), query.value("original_name"), query.value("search_name"), query.value("resolved_name")))
#         data.append(PNSynonym(
#                     query.value("synonym"),
#                     query.value("taxonref"),
#                     query.value("id_taxonref"),
#                     query.value("id_synonym"),
#                     query.value("category")
#                     ))
#     model.sourceModel().resetdata(data)
    
#     #model.repaint()


# def button_add_synonym():
#     #get the selectedItem
#     selecteditem = tblView_resolution.model().data(tblView_resolution.currentIndex(), Qt.UserRole)
#     if selecteditem == None:
#         return
#     if selecteditem.resolved == False:
#         return
#     new_synonym = PNSynonym (None, selecteditem.taxon_ref, selecteditem.idtaxonref)
#     class_newname = PN_edit_synonym (new_synonym)
#     class_newname.show()
#     if new_synonym.idsynonym > 0:
#         #refresh tblView_resolution model (add synonym reference, NOT PERSISTENT IN DATABASE)
#         tblView_resolution.model().sourceModel().refresh (new_synonym)        
#         fill_listsimilarname (selecteditem.idtaxonref)

# def button_edit_synonym():
#     #get the selectedItem
#     selecteditem = table_view2.model().data(table_view2.currentIndex(), Qt.UserRole)    
#     if table_view2.currentIndex().data() == None:
#         return
#     class_newname = PN_edit_synonym (selecteditem)
#     old_synonym = PNSynonym(selecteditem.synonym,'', 0) 
#     class_newname.show()
#     if class_newname.updated:
#         #refresh tblView_resolution model (add and delete synonym reference, NOT PERSISTENT IN DATABASE)
#         tblView_resolution.model().sourceModel().refresh (old_synonym)
#         tblView_resolution.model().sourceModel().refresh (selecteditem)

# def button_delete_synonym():
#     selecteditem = table_view2.model().data(table_view2.currentIndex(), Qt.UserRole)    
#     if table_view2.currentIndex().data() == None:
#         return
#     #message to be display first (question, delete Yes or Not ?)
#     msg = "Are you sure to delete the synonym "+ selecteditem.synonym + "?"
#     result = QMessageBox.question(None, "Delete a synonym", msg, QMessageBox.Yes, QMessageBox.No)
#     if result == QMessageBox.No :
#         return
#     #else execute the suppression
#     sql_query = sql_taxa_delete_synonym (selecteditem.idsynonym)
#     result = QtSql.QSqlQuery (sql_query)
#     if len(result.lastError().nativeErrorCode ()) == 0:
#         #refresh tblView_resolution model (delete synonym reference, NOT PERSISTENT IN DATABASE)
#         deleted_synonym = PNSynonym(selecteditem.synonym,'', 0)
#         tblView_resolution.model().sourceModel().refresh (deleted_synonym)
#         fill_listsimilarname (selecteditem.idtaxonref)

# def set_enabled_buttons():
#     #manage the availability of the three edit buttons
#     button_add.setEnabled (False)
#     button_edit.setEnabled(False)
#     button_del.setEnabled(False)
#     data_msg.setText('No selection')
#     selected_taxa = tblView_resolution.model().data(tblView_resolution.currentIndex(), Qt.UserRole)
#     selected_synonym = table_view2.model().data(table_view2.currentIndex(), Qt.UserRole)
#     if selected_taxa == None:
#         table_view_data.model().setRowCount(0)
#         return
#     elif not selected_taxa.idtaxonref>0:
#         return
#     button_add.setEnabled (True)
#     if selected_synonym == None:
#         return
#     button_edit.setEnabled(True)
#     button_del.setEnabled(True)

# def write_data():
#     #write a field 'id_taxaref' into the selected table fill by setresolved pgsql function
#     # schema = cb_schema.currentText()
#     # table = window.occ_tables_treeView.currentIndex().data(0) 
#     # field_name = CL_tables_occurrences.fieldName (schema, table, 'taxaname')
#     schema, table, field_name = selected_Field()
#     if len(schema)*len(field_name)*len(table) == 0 :return
#     schema_table = schema+'.' + table

#     #field_name = window.cb_field.currentText()
#     sql_query = "SELECT * FROM taxonomy.pn_taxa_setresolvedname('" + schema_table + "','" +field_name +"')"
#     query = QtSql.QSqlQuery (sql_query)
#     if query.next():
#         window.statusbar.showMessage (str(query.value(0)) + " row(s) updated")


# def export_data():
#     ##to automatically import into the download directory
#     # text, okPressed = QInputDialog.getText(None, "Save to a CSV File","File name to save in the download directory:", QLineEdit.Normal, "")
#     # if okPressed and text != '':
#     #     download_location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
#     #     text = text + '.csv'
#     #     text = os.path.join(download_location, text)
#     #     print(text)

#     #by using the static function we do not have to manage unload
#     options = QFileDialog.Options()
#     #options |= QFileDialog.DontUseNativeDialog
#     filename, _ = QFileDialog.getSaveFileName(None,"QFileDialog.getSaveFileName()","","CSV files (*.csv);;All files (*.*)", options=options)
#     if not filename:
#        return
    
#     # filedialog = QFileDialog()
#     # #filedialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
#     # filedialog.setWindowTitle('Save to a CSV File')
#     # filedialog.setDefaultSuffix("csv")
#     # filedialog.setNameFilter("CSV files (*.csv);;All files (*.*)")
#     # filedialog.setAcceptMode(QFileDialog.AcceptSave)
#     # selected = filedialog.exec_()
#     # filename = (str(filedialog.selectedFiles()[0]))
#     # if not selected:
#     #     return
    
#     f = open(filename, "w")
#     txt = 'Search_name; Result_category; Taxa_name'
#     f.write(txt +'\n')
#     myprogressBar.setVisible(True)
#     myprogressBar.setValue(0)
#     i = 0
#     ivalue = 0
#     imax = tblView_resolution.model().sourceModel().rowCount()
#     for synonym in tblView_resolution.model().sourceModel()._data:
#             taxonref = ''
#             category =''
#             if synonym.resolved:
#                 taxonref = synonym.taxon_ref
#                 category = synonym.category
#             else:
#                 sql_txt = "SELECT taxonref FROM taxonomy.pn_taxa_search_name('" + synonym.synonym +"', 0.6)"
#                 query = QtSql.QSqlQuery (sql_txt)
#                 if query.next() :
#                     taxonref = str(query.value("taxonref"))
#                     category = 'Suggested'
#             txt = synonym.synonym + ';' + category + ';' + taxonref
#             i +=1
#             ivalue= int(100*i/imax)
#             myprogressBar.setValue(ivalue)
#             window.statusbar.showMessage ("Export in progress, " + str(i) + " of "  +str(imax) + " rows")
#             f.write(txt +'\n')
#     myprogressBar.setVisible(False)
#     window.statusbar.showMessage ("Export terminate")
#     f.close()






# def sql_taxa_delete_synonym(id_synonym):
#     sql_txt = "DELETE FROM taxonomy.taxa_synonym WHERE id_synonym = " + str(id_synonym)
#     return sql_txt

# def cb_schema_selectionchange():
#     #print ("schema change")
#     clear_table_view()
#     figure_clear()
    #change the content of the list of accepted tables (occ_tables_treeView) according to selected schema
    # schema = cb_schema.currentText()
    #clear and fill the list of occurrences tables for the selected schema
    # model = QtGui.QStandardItemModel()
    # window.occ_tables_treeView.setModel(model)
    # tab_db_fields = CL_tables_occurrences.get_tables (schema) 
    # for key in tab_db_fields.keys():
    #     item = QtGui.QStandardItem(key)
    #     item.setCheckable(True)
    #     item.setCheckState(2)
    #     model.appendRow([item],)
    # model.itemChanged.connect(occ_tables_treeView_checkedchange)
    # occ_tables_treeView_checkedchange(True)
    
# def selected_Field(field = 'taxaname'):
#     return
#     #return the three parameters, schema, table and field (optional)
#     schema = ''
#     table = ''
#     field_name =''
#     try:
#         schema = cb_schema.currentText()
#         table = window.occ_tables_treeView.currentIndex().data() 
#         field_name = CL_tables_occurrences.fieldName (schema, table, field)
#     except:
#         pass
#     return schema, table, field_name

# def occ_tables_treeView_checkedchange2(item):
#     model = window.occ_tables_treeView.model()
#     ls_tabs = []
#     for row in range (model.rowCount()):
#         item = model.item(row)
#         if item.checkState() == 2:
#             ls_tabs.append(item.text())
            
#     return (ls_tabs)



#setting the secondary tableview (similar_names)
    # model_tableview = TableSimilarNameModel()
    # proxyModel =  QSortFilterProxyModel()
    # proxyModel.setSourceModel(model_tableview)
    # table_view2 = window.tableview_names    
    # table_view2.setModel(proxyModel)
    # table_view2.setSortingEnabled(True)
    # table_view2.sortByColumn(0, Qt.AscendingOrder)
    # table_view2.horizontalHeader().setHighlightSections(False)
    # table_view2.sortByColumn(0, Qt.AscendingOrder)
    # header = table_view2.horizontalHeader()
    # header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)    
    # table_view2.setColumnWidth(1,200)
    # table_view2.horizontalHeader().setStretchLastSection(True)
    #selection = table_view2.selectionModel()
    #selection.selectionChanged.connect(set_enabled_buttons)
    # selection.selectionChanged.connect(table_view_data_clickitem)
    # selection.currentChanged.connect(table_view_before_clickitem)

#setting the buttons connector slots    
    #window.radio_unresolved.clicked.connect (occ_tables_treeView_selectionchange)
    # button_add = window.pushButtonAdd
    # button_add.clicked.connect(button_add_synonym)

    # button_edit = window.pushButtonEdit
    # button_edit.clicked.connect(button_edit_synonym)
    
    # button_del = window.pushButtonDel
    # button_del.clicked.connect(button_delete_synonym)

    # cb_table.currentIndexChanged.connect(cb_table_selectionchange)
    # cb_schema.currentIndexChanged.connect(cb_schema_selectionchange)
    

