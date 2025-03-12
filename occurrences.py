#import os
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QStandardItem
from PyQt5 import QtGui, QtSql, QtCore
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QItemSelectionModel, pyqtSignal

from occ_model import PN_taxa_resolution_model, PN_occ_model, PN_occ_tables, PN_occ_explore
from taxa_model import PN_edit_synonym, PNSynonym
from class_properties import Qtreeview_Json
from commons import get_str_value, list_db_fields, list_db_traits,postgres_error, PN_database_widget
from import_csv import NonEditableModel, ComboBoxDelegate, CSVTranslate

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
#import pandas as pd
import re



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
        # Execute the long task to fill a model with data from a query (QtSql.QSqlQuery)
        self.stopped = False  
        record = self.query.record()
        i = 1
        while not self.stopped and self.query.next():
            _data = []
            for x in range(record.count()):
                _data.append(self.query.value(record.fieldName(x)))
            self.data.append(_data)
            i += 1            
            #stop process if statut =0
            if i == self.limit + self.offset:
                self.model.resetdata(self.data)
                i = 0
                break
        self.model.resetdata(self.data)


class CenterDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.displayAlignment = Qt.AlignCenter
        super().paint(painter, option, index)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # load the GUI
        self.window = uic.loadUi("pn_occurrences.ui")
        self.suggested_id_taxonref = 0
        self.suggested_name_taxon_ref  = None
    #setting the widget Qtreeview_Json
        header = ['Category', 'Taxa', 'Occurrences']
        self.PN_trview_traits = Qtreeview_Json (True, True, header)
        layout = self.window.tview_properties_layout.layout()
        layout.addWidget(self.PN_trview_traits)

    # #setting the tableView_resolution
        self.tblView_resolution = self.window.tableView_resolution

    #setting the self.tblView_data
        self.tblView_data = self.window.tableView_data

    #setting the self.tblView_explore
        self.tblView_explore = self.window.trview_explore_traits

    #set the occurrences treeview
        self.trView_occ = PN_occ_tables ('occurrences')
        self.window.trView_occ_VLayout.insertWidget(1, self.trView_occ)
        self.trView_occ.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)



    #setting the menu action connector slots
        # self.window.actionExport_data.triggered.connect(export_data)
        # self.window.actionWrite_id_taxaref.triggered.connect(write_data)
        self.window.actionQuit.triggered.connect(sys.exit)
    #set the thread 
        self.myDataThread = DataThread()
    #fill the cb_operators
        self.window.cb_operators.addItems(['equal', 'different', 'contains', 'superior', 'inferior', 'greater', 'less'])
    #set the enabled and visible widgets
        self.window.frame_toolbar_figure.setVisible(False)
    #set the tooltips
        self.window.button_taxa_clear.setToolTip("Unchecked all selected properties")
        self.window.button_taxa_categories.setToolTip("All categories must be satisfied")


        self.myPlotClass = PN_occ_explore()
        self.myFigure = FigureCanvas(plt.figure())
        self.myFigure.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.window.figure_vlayout.addWidget(self.myFigure)
        self.similarity_widget_setVisible(False)



#manage statusbar
#add widget to the statusbar
    #label
        self.label_rows = QtWidgets.QLabel()
        self.label_rows.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding)
        self.window.statusBar().addWidget(self.label_rows)        
    #progress bar       
        self.myprogressBar = QtWidgets.QProgressBar()
        self.myprogressBar.setGeometry(100, 40, 30, 25)
        self.myprogressBar.setVisible(False)
        self.myprogressBar.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding)
        self.window.statusBar().addPermanentWidget(self.myprogressBar)
    #button export
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
        self.window.statusBar().addPermanentWidget(frame)
    #connect to the database
        connected_indicator = PN_database_widget()
        self.window.statusBar().addPermanentWidget(connected_indicator)
        connected_indicator.open()
        #return if not open
        if not connected_indicator.dbopen:
            return
        self.db = connected_indicator.db

    #set the slots
        self.trView_occ.keyPressEvent = lambda event: self.trView_occ_keyPress(event.key()) if event.key() in [Qt.Key_F2, Qt.Key_Delete] else None
        self.trView_occ.pressed.connect(self.trView_occ_clicked)

        self.tblView_data.clicked.connect(self.tblView_data_clickitem)
        self.tblView_explore.clicked.connect(self.figure_plot)
        self.tblView_data.verticalScrollBar().valueChanged.connect(self.tblView_data_verticalScroll)
        self.window.slider_similarity.valueChanged.connect (self.set_similarity)    
        self.window.tabWidget_data.currentChanged.connect(self.tabWidget_data_select)
        self.window.button_similarity.toggled.connect (self.button_similarity_clicked)
        self.window.button_unresolved.toggled.connect(self.button_unresolved_click)
        self.window.buttonbox_filter.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.buttonbox_apply_click)
        self.window.button_sel_reset.clicked.connect(self.buttonbox_reset_click)
        self.window.button_sel_all.clicked.connect(self.buttonbox_selall_click)
        self.window.button_sel_inverse.clicked.connect(self.buttonbox_inverse_click)
        self.window.button_figure_apply.clicked.connect(self.figure_plot)
        self.window.button_figure_reset.clicked.connect(self.figure_reset)
        self.window.button_taxa_categories.toggled.connect(self.trview_explore_traits_fill)
        self.window.button_save_dataset.clicked.connect(self.button_save_dataset_click)
        self.window.button_import_dataset.clicked.connect(self.button_import_dataset_click)
        self.window.button_taxa_clear.clicked.connect(self.trview_taxa_deselectedItems)
        self.window.button_union_dataset.toggled.connect(self.set_union_query)
        
        #self.window.button_export_data.clicked.connect(self.export_to_csv)
        
        self.window.button_save_figure.clicked.connect(self.export_to_image)
        self.window.cb_operators.currentIndexChanged.connect(self.set_filters_enabled)
        self.window.cb_figures.currentIndexChanged.connect(self.figure_reset)
        self.window.cb_figure_rank.currentIndexChanged.connect(self.trview_explore_traits_fill)
        self.window.cb_figure_function.currentIndexChanged.connect(self.trview_explore_traits_fill)
        self.window.cb_figure_taxa.currentIndexChanged.connect(self.trview_explore_traits_fill)
        self.PN_trview_traits.clicked.connect(self.trview_explore_traits_fill)
        self.window.tblview_traits_dataset.clicked.connect(self.tblview_traits_dataset_clicked)
        self.window.tblview_user_dataset.clicked.connect(self.tblview_user_dataset_clicked)
        self.window.tblview_user_dataset.keyPressEvent = lambda event: self.tblview_user_dataset_keyPress(event.key()) if event.key() in [Qt.Key_F2, Qt.Key_Delete] else None
       
        self.window.tblview_traits_dataset.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.window.tblview_user_dataset.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.window.toolBox.setItemIcon(0, self.window.style().standardIcon(51))
        self.window.toolBox.setItemIcon(1, self.window.style().standardIcon(53))
        self.window.toolBox.setItemIcon(2, self.window.style().standardIcon(53))
        
#Load the class trView_occ through the database connection QtSql
        self.trView_occ.load()
        index = self.trView_occ.model().index(0, 0)
        self.trView_occ.selectionModel().setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

        #window.tblview_user_dataset.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.load_dbdataset()
        #window.tblview_user_dataset
        self.window.tblview_user_dataset.hideColumn(1)
        self.window.tblview_user_dataset.hideColumn(2)
        self.window.tblview_user_dataset.model().dataChanged.connect(self.tblview_user_dataset_updateItem)
        # selection_model = self.trView_occ.selectionModel()
        # selection_model.selectionChanged.connect(self.set_button_union_enabled)

    def export_menu(self, item):
    #export any of the three main lists to csv files (self.tblView_resolution, self.tblView_data, self.tblView_explore)
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
        tab_name = self.window.tabWidget_data.currentWidget().objectName()
        if tab_name == 'tab_data':
            data = self.tblView_data.model().sourceModel().getdata(True)
            i = len(data)
            if i < self.myDataThread.query.size():
                self.myDataThread.query.seek(i-1)
                record = self.myDataThread.query.record()
                while self.myDataThread.query.next():
                    _data = []
                    for x in range(record.count()-1):
                        _value = get_str_value(self.myDataThread.query.value(record.fieldName(x)))
                        _data.append(_value)
                    data.append(_data)
                self.myDataThread.query.seek(i-1)
        elif tab_name == 'tab_taxa':
            data = self.tblView_resolution.model().sourceModel().getdata(True)
        elif tab_name == 'tab_explore':
            data = qtableview_to_list(self.tblView_explore, True)

        #set parameters to QfileDialog
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.ReadOnly
        #options |= QFileDialog.DontUseNativeDialog
        file_dialog = QtWidgets.QFileDialog()
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



    def close(self):
        self.window.close()

    def show(self):
        self.window.show()

    def load_dbdataset(self):
    #load the dataset config stored into the sqlite file config.db
        #dbconfig = QtSql.QSqlDatabase.addDatabase("QSQLITE", "config1")
        dbconfig = QtSql.QSqlDatabase.addDatabase("QSQLITE", "config")
        dbconfig.setConnectOptions('QSQLITE_OPEN_READWRITE')
        dbconfig.setDatabaseName("config.db")
        dbconfig = QtSql.QSqlDatabase.database("config")
        if not dbconfig.open():
            QtWidgets.QMessageBox.critical(None, "Cannot open database", "Unable to open database, check for connection parameters", QtWidgets.QMessageBox.Cancel)
            sys.exit("error")

        #load the shortcut traits dataset
        model = QtGui.QStandardItemModel()
        model.setColumnCount(1)
        self.window.tblview_traits_dataset.setModel(model)
        ls_traits = ['location', 'phenology'] + list(list_db_traits.keys())
        for traits in ls_traits:
            item = QtGui.QStandardItem(traits)
            model.appendRow([item])
        #load the users dataset from dbconfig
        model = QtGui.QStandardItemModel()
        model.setColumnCount(3)
        sql_query = "SELECT name, parameter2, uuid FROM config_start WHERE key = 'dbdataset' AND parameter1 = '" + self.trView_occ.schema + "'"
        query = dbconfig.exec_(sql_query)
        while query.next():
            item =  QtGui.QStandardItem(str(query.value("name")))
            item1 = QtGui.QStandardItem(str(query.value("parameter2")))
            item2 = QtGui.QStandardItem(str(query.value("uuid")))
            model.appendRow([item, item1, item2])           
        query.finish()
        dbconfig.close()
        QtSql.QSqlDatabase.close(dbconfig)
        self.window.tblview_user_dataset.setModel(model)        
        return

 
    def trview_explore_traits_fill(self):
    #fill the trview_explore list by taxa
        try:
            _rankname = self.window.cb_figure_rank.currentText().lower()
            model = self.PN_trview_traits.model()
            root_item = model.invisibleRootItem()
        except Exception:
            return
        try:
            self.tblView_explore.selectionModel().clearSelection()
        except Exception:
            pass
        #navigate through the treeview with recursive function trview_taxa_selectedItems
        tab_queries = []
        for tab_query in self.trview_taxa_selectedItems(root_item):
            tab_queries.append(tab_query)

        #check for exclusive or not search (and between categories)
        isAND = False
        if self.window.button_taxa_categories.isChecked():
            isAND = True
        #set the filter on taxa properties (isAND for exclusive search = all categories must be found)
        self.myPlotClass.set_propertiesfilter(tab_queries, isAND)
        self.myPlotClass._sql_taxaFilter = ''

    #create the list, set the self.tblView_explore as Treeview  
        #alltaxas  = self.window.button_taxa_exclusive.isChecked()
        alltaxas  = self.window.cb_figure_taxa.currentIndex() == 1
        #get the traits from self.myPlotClass
        
        _function = self.window.cb_figure_function.currentText().lower()
        _sql_traits = self.myPlotClass.get_sql_traits(_rankname, _function, alltaxas)
        #set the result to PN_trview_traits
        model = QtGui.QStandardItemModel()
        self.tblView_explore.setModel(model)
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
            self.tblView_explore.setItemDelegateForColumn(column, delegate)
        model = self.tblView_explore.model()    
        self.label_rows.setText (str(model.rowCount()) + " row(s)")
        #self.set_union_query()
        self.figure_reset()

        

    def trview_taxa_deselectedItems(self):
        def recursively_deselect(item):
            if item is not None:
                if item.isCheckable():
                    item.setCheckState(Qt.Unchecked)
                for row in range(item.rowCount()):
                    child_item = item.child(row)
                    recursively_deselect(child_item)
        model = self.PN_trview_traits.model()
        root_item = model.invisibleRootItem()
        recursively_deselect(root_item)
        self.trview_explore_traits_fill()

    def trview_taxa_selectedItems(self, root):
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


    def figure_reset(self):
    #reset the min, max value and draw the plot
        self.window.figure_min.setText('')
        self.window.figure_max.setText('')
        self.window.figure_mean.setText('')
        self.window.figure_max.setText('')
        self.figure_plot()


    def figure_plot(self):
    #get and draw the figure corresponding to the selected_field 
        self.window.frame_toolbar_figure.setVisible (False)   
        #self.window.frame_toolbar_table.setVisible (False)
        #self.window.result_self.trView_occ.setVisible(False)
        fieldPlot = self.window.cb_figures.currentText()
        self.myFigure.setVisible(False)
        
        #get selected taxa
        _rankname = self.window.cb_figure_rank.currentText().lower()
        selected_items = []
        selected_indexes = self.tblView_explore.selectedIndexes()
        for index in selected_indexes:
            if index.column() == 0:
                item = index.data()
                selected_items.append(item)
        self.myPlotClass.set_taxafilter(_rankname,selected_items)

        #get the min/max value
        fmin = None 
        fmax = None
        if  len(self.window.figure_min.text().strip())>0:
            fmin = float (self.window.figure_min.text().strip())
        if  len(self.window.figure_max.text().strip())>0:
            fmax = float (self.window.figure_max.text().strip())

        #get the figure related to the fieldPlot
        self.myFigure.setVisible(True)  
        figure_canvas = self.myPlotClass.get_figure (self.myFigure.figure, fieldPlot, fmin, fmax)
        if figure_canvas is None :
            self.myFigure.figure.text(0.35, 0.5, 'no data in the selection...', style = 'italic', fontsize = 14, color = "grey")
            self.myFigure.draw()
            return
        self.myFigure.figure.subplots_adjust(bottom = 0.2, left = 0.2, right = 0.9, top = 0.85)

        #set the return min/max/median/mean values from the self.trView_occ
        fmin = None
        fmax = None
        if self.myPlotClass.figure_min is not None:
            fmin = round(self.myPlotClass.figure_min, 5)
            self.window.figure_min.setText(str(fmin))
        if self.myPlotClass.figure_mean is not None:
            fmean = round(self.myPlotClass.figure_mean, 3)
            self.window.figure_mean.setText(str(fmean))
        if self.myPlotClass.figure_median is not None:
            fmedian = round(self.myPlotClass.figure_median, 5)
            self.window.figure_median.setText(str(fmedian))
        if self.myPlotClass.figure_max is not None:
            fmax = round(self.myPlotClass.figure_max, 5)
            self.window.figure_max.setText(str(fmax))

        #set the visibility of the statistic filter frame
        self.window.frame_toolbar_figure.setVisible (not (fmin is None and fmax is None))
        #self.window.figure_vlayout.addWidget(figure_canvas)
        self.myFigure.draw()



############# self.tblView_data and FILTER (tab "Data Source" of the GUI) ###########
    def buttonbox_selall_click(self):
        #select all the item in the tableView_item
        model = self.window.tableView_item.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            item.setCheckState(2)

    def buttonbox_inverse_click(self):
        #inverse selection of items in the tableView_item
        model = self.window.tableView_item.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item.checkState() == 2:
                item.setCheckState(0)
            else:
                item.setCheckState(2)

    def buttonbox_reset_click(self):
        #delete the filter for the selected field (search for a synonyms names)
        table = self.trView_occ.currentIndex().data()
        field = self.window.cb_fields.currentText()
        field = self.trView_occ.get_field(table,field)
        fieldname = field["field_name"]
        #set the field to none value
        self.trView_occ.delFieldFilter(table,fieldname)
        self.tblView_data.setModel(None)
        self.tabWidget_data_select()
    
    def buttonbox_apply_click(self, item):
        #apply filter to the table, save into self.trView_occ definition dictionnary
        isfilter = not self.window.tableView_item.isEnabled()
        operator = ''
        value = ''
        #translate operator from text to SQL symbol
        ls_operators = {"equal": 'IN', "different" : 'NOT IN', 'contains' : 'LIKE', 'superior': '>', 'inferior': '<', 'greater': '>=', 'less' : '<='}
        operator = ls_operators[self.window.cb_operators.currentText()]
        #get the table name and the true field name    
        #table = self.trView_occ.currentIndex().data() 
        table = self.trView_occ.currentTable
        field = self.trView_occ.get_field(table, self.window.cb_fields.currentText())

        if field is None: 
            return
        fieldname = field["field_name"]
        #separate treatment according to isfilter (from lineEdit_filter or tableView_item)
        if isfilter:
            value = self.window.lineEdit_filter.text().strip()
            if len(value) == 0 : 
                return
            if operator =='LIKE':
                value = '%' + value + '%'
            #value = "'" + value + "'"
        else:
            #manage the check list
            ls_checked = []
            ls_unchecked = []
            model = self.window.tableView_item.model()
            for row in range(model.rowCount()):
                item = model.item(row)
                if item.checkState() == 2:
                    ls_checked.append(item.text())
                else:
                    ls_unchecked.append(item.text())
            
            #don't save where all or nothing are selected
            if len(ls_unchecked) * len(ls_checked) == 0: 
                return

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
        self.trView_occ.addFieldfFilter (table, fieldname, operator, value)

        #reload data and enabled widgets
        self.tblView_data_fill()
        self.set_filters_enabled()


    def tblView_data_clickitem(self, item):
        #when user click on a cell into self.tblView_data, select field into cb_fields
        current_column = self.tblView_data.currentIndex().column()
        field_name = self.tblView_data.model().sourceModel().header_labels[current_column]
        self.window.cb_fields.setCurrentText(field_name)

    def set_filters_enabled(self):
        #manage enabled of widgets related to filters according to options
        field_name = self.window.cb_fields.currentText()
        table = self.trView_occ.currentIndex().data()
        #field = self.trView_occ.get_field(table,field_name)
        #enabled the reset button if a filter is active
        try:  
            enabled = self.trView_occ.isFieldFiltered (table,field_name)
        except Exception:
            enabled = False
        self.window.button_sel_reset.setEnabled(enabled)

        #enabled the tableView_item/lineEdit_filter according to operator and length of tableView_item
        try:
            first_value = self.window.tableView_item.model().item(0,0).data(0)
            if first_value.startswith('Error'):
                ls_enabled = False
            else:
                ls_enabled = (self.window.cb_operators.currentIndex() < 2)
        except Exception:
            ls_enabled = False
        self.window.tableView_item.setEnabled(ls_enabled)
        self.window.lineEdit_filter.setEnabled(not ls_enabled)
    
    def cb_fields_selectionchange(self):
        #on the dataSource tab
        #load the list of group (unique) value for filtering
        field_name = self.window.cb_fields.currentText()
        table = self.trView_occ.currentTable
        if table is None : 
            return

        self.window.cb_operators.setCurrentIndex(0)
        #create the sql statement
        sql_query = "SELECT _fieldname_ FROM ("
        sql_query += self.trView_occ.sql_table_data(table) +") a"
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
                except Exception:
                    pass
        self.window.tableView_item.setModel(model2)
        self.set_filters_enabled()

    def button_unresolved_click(self):
    #click on the unresolved button
        #clear models
        self.tblView_data.setModel(None)
        self.tblView_resolution.setModel(None)
        self.tabWidget_data_select()

    def tblview_user_dataset_clicked(self, index):
    #click on one user dataset
        #clear models
        self.tblView_data.setModel(None)
        self.tblView_resolution.setModel(None)
        self.tblView_explore.setModel(None)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))

        #set the tabledef of saved dataset (hidden in the column1 of tblview_user_dataset)
        row = index.row()
        
        #saveTabledefkey = index.model().index(row,2).data()
        tabledef = eval(index.model().index(row,1).data())
        #add a new dataset
        table = self.trView_occ.add_dataset(tabledef)
        self.trView_occ.currentTable = table
        self.tabWidget_data_select()

    def tblview_user_dataset_updateItem(self, index):
    #set the new name for the dataset into the config sqlite dbase and in the list self.window.tblview_user_dataset
        new_name = index.data()
        key_uuid = index.sibling(index.row(), 2).data()
        sql_query = "UPDATE config_start SET name = '" + new_name + "' WHERE uuid = '" + key_uuid + "';"
        dbconfig = QtSql.QSqlDatabase.database("config")
        query = dbconfig.exec_(sql_query)
        if query.isActive():
            return
        
        msg = "The dataset <" + new_name + "> already exists "
        QtWidgets.QMessageBox.information(None, "Rename a dataset", msg)
        sql_query = "SELECT name FROM config_start WHERE uuid = '" + key_uuid + "';"
        query = dbconfig.exec_(sql_query)
        query.next()
        db_text = query.value("name")
        #self.window.tblview_user_dataset.clearSelection()
        model = self.window.tblview_user_dataset.model()
        model.setData(index, db_text, Qt.DisplayRole)


    def trView_occ_keyPress(self, value):
    #to delete a datasource
        index = self.trView_occ.currentIndex()
        row = index.row()
        datasource_name = self.trView_occ.schema + "." + index.data()
        sql_query = "DROP TABLE " + datasource_name
        msg = "Are you sure to deleted the selected datasource < " + datasource_name + " > ?"
        if value == Qt.Key_Delete:
            result = QtWidgets.QMessageBox.question(None, "Delete DataSource", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.No: 
                return
            #OK to delete
            query = QtSql.QSqlQuery(sql_query)
            #the table is deleted
            if query.isActive():
                self.trView_occ.model().removeRow(row)
                index = self.trView_occ.currentIndex()
                self.trView_occ_clicked (index)

    def tblview_user_dataset_keyPress(self, value):
    #to delete or rename a dataset
        index = self.window.tblview_user_dataset.currentIndex()
        if value == Qt.Key_F2:
            self.window.tblview_user_dataset.edit(index)
        elif value == Qt.Key_Delete:
            row = index.row()
            dataset_name = self.window.tblview_user_dataset.model().item(row,0).text()
            msg = "Are you sure to deleted the dataset < " + dataset_name + " > ?"
            result = QtWidgets.QMessageBox.question(None, "Delete DataSet", msg, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if result == QtWidgets.QMessageBox.No: 
                return
            model = self.window.tblview_user_dataset.model()
            dbconfig = QtSql.QSqlDatabase.database("config")
            key_uuid = self.window.tblview_user_dataset.model().item(row,2).text()
            sql_query = "DELETE FROM config_start WHERE uuid = '" + key_uuid + "';"
            query = dbconfig.exec_(sql_query)
            if query.isActive():
                model.removeRow(row)
                index = self.window.tblview_user_dataset.currentIndex()
                self.tblview_user_dataset_clicked (index)        

    def button_import_dataset_click(self):
        

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

    def set_progressBar_value (self, value):
        self.myprogressBar.setValue(int(100*value))
    
    def button_save_dataset_click(self):
    #save the selected datasource to a new dataset    
        tab_key = []
        model = self.window.tblview_user_dataset.model()
        #get the list of existing user dataset
        for row in range(model.rowCount()):
            tab_key.append(model.item(row, 0).text())
        #loop while the name already exist or user press cancel
        loop = True
        while loop:
            dataset_name, ok = QtWidgets.QInputDialog.getText(None, "Dataset Name", "Please enter the dataset name")
            if not ok: 
                return
            if dataset_name in tab_key:
                msg = "The dataset <" + dataset_name + "> already exists "
                QtWidgets.QMessageBox.information(None, "Add a dataset", msg)
            else:
            #save the new dataset
                loop = False
                dbconfig = QtSql.QSqlDatabase.database("config")
                data_value = str(self.trView_occ.tab_stacked_datasource())
                import uuid
                key_uuid = str(uuid.uuid4())
                sql_query = "INSERT INTO config_start(key, name, parameter1, parameter2, uuid) "
                sql_query +="VALUES ('dbdataset', '" + dataset_name +"','" + self.trView_occ.schema + "'," + chr(34) + data_value + chr(34) +",'" + key_uuid + "');"
                query = dbconfig.exec_(sql_query)
                if query.isActive():
                    item =  QtGui.QStandardItem(dataset_name)
                    item1 = QtGui.QStandardItem(data_value)
                    item2 = QtGui.QStandardItem(key_uuid)
                    model.appendRow([item, item1, item2])
                    self.window.toolBox.setCurrentIndex(2)
                    self.window.toolBox.repaint()
                    self.window.tblview_user_dataset.selectionModel().setCurrentIndex(item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                    self.window.tblview_user_dataset.repaint()
                    self.tblview_user_dataset_clicked (item.index())
        return     

    def tblview_traits_dataset_clicked(self, index):
    #click on one trait dataset    
        #clear models
        self.tblView_data.setModel(None)
        self.tblView_resolution.setModel(None)
        self.tblView_explore.setModel(None)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

        #create and add a standardized table from query
        row = index.row()
        trait = index.model().index(row,0).data()
        # #get a tabledef from a trait
        tabledef = self.trView_occ.tab_staked_traits(trait)
        # #add a new dataset
        table = self.trView_occ.add_dataset(tabledef)
        self.trView_occ.currentTable = table
        self.tabWidget_data_select()

    # def set_button_union_enabled(self):
    #     self.window.button_union_dataset.setEnabled(
    #         len (self.trView_occ.selectionModel().selectedRows()) > 1)

    def trView_occ_clicked(self, value = False):
    #click on one datasource    
        #clear models    
        
        self.tblView_data.setModel(None)
        self.tblView_resolution.setModel(None)
        self.tblView_explore.setModel(None)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        table = self.trView_occ.currentIndex().data()
        self.trView_occ.currentTable = table
        self.tabWidget_data_select()

    def cb_figures_fill(self):
        #get and fill the list of figure types
        self.window.cb_figures.currentIndexChanged.disconnect(self.figure_reset)
        self.window.cb_figures.clear()
        selected_text = self.window.cb_figures.currentText()
        # include = self.window.button_union_dataset.isChecked()
        # fields_toinclude = self.trView_occ.fieldstoUse(union=include)
        for fieldPlot in self.myPlotClass.graphTypes:
            try:
                # if fieldPlot in list_db_traits :
                #     if fieldPlot in fields_toinclude:
                #         self.window.cb_figures.addItem(fieldPlot)
                # else:
                self.window.cb_figures.addItem(fieldPlot)
            except Exception:
                pass
        self.window.cb_figures.setCurrentText(selected_text)
        self.window.cb_figures.currentIndexChanged.connect(self.figure_reset)

    def trView_occ_checkedchange(self, dataset = None):
    #create and explore a dataset
        table = self.trView_occ.currentTable
        #create the dataset if table is a datasource
        if self.trView_occ.is_datasource(table):
            self.trView_occ.add_dataset()
        #get the temp table name
        table = self.trView_occ.tmp_table_name
        self.myPlotClass.load(table)

    #load the accepted figure list
        #happen when user check or uncheck a occurrence database
        #selected_text = self.window.cb_figures.currentText()

        self.cb_figures_fill()

    #load the taxa traits with density (Lists in Rows)
        _data = self.myPlotClass.get_taxa_properties()
        self.PN_trview_traits.setData(_data)
    #load the list of taxa/traits
        self.trview_explore_traits_fill()
        return

    def tblview_import_fill(self):
        
        headers = {}

        #create the query
        table = self.trView_occ.currentIndex().data()
        # sql = "SELECT * FROM " + self.trView_occ.schema + '.' + table + ' LIMIT 1'
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

        table_def = self.trView_occ.get_fields(table)
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
            _query += " FROM " + self.trView_occ.schema + '.' + table
            tab_query.append(_query)
            i+=1
        sql_query = '\nUNION '.join(tab_query)
        sql_query += '\nORDER BY index'
        
        query = QtSql.QSqlQuery (sql_query)
        rows = 0
        while query.next():
            rows = max(rows, query.value('total'))
            header = query.value("header")
            field_def = self.trView_occ.get_field (table, header)        
            _type = field_def["field_type"]
            non_null_value = rows - query.value("null_value")
            unique_value = query.value("unique_value")
            duplicated_value = (unique_value < rows)
            min_value = query.value("min")
            max_value = query.value("max")
            fieldref = query.value("fieldref")
            if fieldref not in list_db_fields:
                fieldref = None
            # add the result into the headers dictionnary
            headers[header] = {"fieldref" : fieldref, "type" : _type,   "non null": non_null_value, "duplicated" : duplicated_value, "min" : min_value, "max" : max_value}

        _summary = str(rows) + ' rows, ' + str(query.size()) + ' columns'
        self.window.label_summary.setText(_summary)

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
        self.window.tblview_import.setModel(model) 
        header = self.window.tblview_import.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        # Apply a delegate to change color and edit options
        combo_delegate = ComboBoxDelegate()
        self.window.tblview_import.setItemDelegate(combo_delegate)
        combo_delegate.closeEditor.connect(self.handleEditingFinished)    

    def handleEditingFinished(self, editor, index):
        # Slot to handle the editing finished event
        if isinstance(editor, QtWidgets.QComboBox):
            selected_item = editor.currentText()
            model = self.window.tblview_import.model()
            c_row = self.window.tblview_import.currentIndex().row()
            #Check that there is only one reference to a fieldref
            for row in range(model.rowCount()):
                index = model.index(row, 1)
                fieldref = model.data(index)
                if row != c_row and fieldref == selected_item:
                    model.setData (model.index(row,1),'')
        elif isinstance(editor, QtWidgets.QLineEdit):
            selected_item = editor.text()

    def tabWidget_data_select(self, value = False):
    #main function to manage the three main tab (resolution, datasource, explore)
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        tab_name = self.window.tabWidget_data.currentWidget().objectName()
        state = True
        rows = 0
        # self.myDataThread.stop()
        # print (self.myDataThread.stop())
        self.similarity_widget_setVisible(False)
        if tab_name == 'tab_data':
            if self.tblView_data.model() is None:
                self.myDataThread.offset = 0
                self.tblView_data_fill()
                self.cb_fields_selectionchange()
            rows = self.myDataThread.query.size()
        elif tab_name == 'tab_taxa':
            if self.tblView_resolution.model() is None:
                self.tblView_resolution_fill()
            rows = self.tblView_resolution.model().rowCount()         
        elif tab_name == 'tab_explore':
            state = False
            if self.tblView_explore.model() is None:
                self.trView_occ_checkedchange()
            rows = self.tblView_explore.model().rowCount()
        elif tab_name == 'tab_import':
            state = False
            self.tblview_import_fill()

        self.window.button_unresolved.setVisible(state)
        #self.label_rows.setVisible(True)
        self.label_rows.setText (str(rows) + " row(s)")

        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()
    def set_union_query(self, isChecked = None):
        if not isChecked:
            isChecked = self.window.button_union_dataset.isChecked()
        columns = self.trView_occ.fieldstoUse(union = isChecked)
        if self.window.tabWidget_data.currentWidget().objectName() == 'tab_data':
            i = 1
            for col in range(self.tblView_data.model().columnCount()):
                #header =  self.tblView_data.horizontalHeader()
                header = self.tblView_data.model().headerData(col, Qt.Horizontal)
                i += 1
                if header in list_db_fields:
                    self.tblView_data.setColumnHidden(col, header not in columns)
            
        return
        # elif self.window.tabWidget_data.currentWidget().objectName() == 'tab_explore':
        #     #columns2 = ['dataset', 'occurrences', 'location']
        #     for col in range(1, self.tblView_explore.model().columnCount()):
        #         header = self.tblView_explore.model().headerData(col, Qt.Horizontal)
        #         if header in list_db_fields:
        #             self.tblView_explore.setColumnHidden(col, header not in columns)
        #     self.cb_figures_fill()
        #     self.figure_reset()
        # return

        # self.trView_occ.set_union_fields = isChecked
        # self.tblView_data.setModel(None)
        # #self.tblView_resolution.setModel(None)
        # self.tblView_explore.setModel(None)
        # QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        # table = self.trView_occ.currentIndex().data()
        # self.trView_occ.currentTable = table

        # if self.window.tabWidget_data.currentWidget().objectName() == 'tab_explore':
        #     self.trView_occ.add_dataset()
        #     #self.trView_occ.fieldstoUse(union = False)
        # self.tabWidget_data_select()

    def tblView_data_fill(self):
    # fill data according to the selected occurrences
        if self.window.tabWidget_data.currentWidget().objectName() != 'tab_data': 
            return
        
        #stop the thread if in progress
        # while self.myDataThread.isRunning():
        #     self.myDataThread.stop()
            # self.myDataThread.terminate()
            # self.myDataThread.wait()
            #self.myDataThread.exit()
            
                
        #load variables
        #table = self.trView_occ.currentIndex().data()
        table = self.trView_occ.currentTable
        if table is None: 
            return

        #clean the self.tblView_data
        proxyModel =  QSortFilterProxyModel()
        proxyModel.setSourceModel(PN_occ_model())
        self.tblView_data.setModel(proxyModel)
        model = self.tblView_data.model().sourceModel()
        model.header_labels = []
        
        #create the query (depending on the selected table)
        _table = table
        if len(self.trView_occ.selectedTables()) > 1:
            #self.trView_occ.set_union_fields = self.window.button_union_dataset.isChecked()
        # #add a new dataset
            table = self.trView_occ.add_dataset()
            _table = None
        #create the query
        sql_query = "SELECT * FROM (" + str(self.trView_occ.sql_table_data(_table)) + ") z"

        if self.window.button_unresolved.isChecked():
            sql_query += "\nWHERE NOT valid"
        #sql_query += "\nORDER BY id_source"
        #print (sql_query)

        #execute the query
        query = QtSql.QSqlQuery (sql_query)
        record = query.record()

        #display the number of rows
        self.label_rows.setText (str(query.size()) + " row(s)")

        #add fields to the cb_fields combobox, to the model header
        #and check for filtered fields (to be highlight see headerData in occ_model)
        field = self.window.cb_fields.currentText()
        try:
            self.window.cb_fields.currentIndexChanged.disconnect(self.cb_fields_selectionchange)
        except Exception:
            pass
        self.window.cb_fields.clear()
        tab_header = [] #tab of the header fields
        tab_filtered = [] #tab of the header fields with an active filter (for rendering)
        for i in range(record.count()):
            try:
                _field = str(record.fieldName(i))
                item = QStandardItem(_field)
                #item.setCheckable(True)  # Rendre l'item checkable
                self.window.cb_fields.model().appendRow(item)
                #self.window.cb_fields.addItem(_field)
                tab_header.append(_field)
                if self.trView_occ.isFieldFiltered(table, _field):
                    tab_filtered.append(i)
            except Exception:
                pass
        self.window.cb_fields.setCurrentText(field)
        self.window.cb_fields.currentIndexChanged.connect(self.cb_fields_selectionchange)   
        model.header_labels = tab_header
        model.header_filtered = tab_filtered
        #send query to thread fill data
        self.myDataThread.query = query
        self.myDataThread.model = model
        #self.myDataThread.data_ready.connect(self.tblView_data_update_model)
        self.myDataThread.start()
        self.set_union_query()
   

    def tblView_data_verticalScroll(self, value):
    #move in the database with the vertical scroll bar
        if self.tblView_data.model().rowCount() == self.myDataThread.query.size():
            return
        if value == self.tblView_data.verticalScrollBar().maximum():
            self.myDataThread.offset = self.tblView_data.model().rowCount() -1
            self.myDataThread.next(self.tblView_data.model().rowCount() -1)
 




    ############# self.tblView_resolution (tab "Taxonomic Resolution" of the GUI) ###########
    def similarity_widget_setVisible(self, visible = True):
        self.window.slider_similarity.setVisible (visible)
        self.window.button_similarity.setVisible (visible)
        self.window.label_similarity.setVisible (visible)

    def button_similarity_clicked(self, toggled):
        #toggled  = self.window.button_similarity.isChecked()
        self.tblView_resolution_fill(toggled)

    def tblView_resolution_fill(self, similarity = False):
    #Taxonomic resolution list, i.e. translate original_name to taxonref according to synonyms dictionnary
        unresolved_mode = self.window.button_unresolved.isChecked()
        if not unresolved_mode:
            self.window.button_similarity.toggled.disconnect (self.button_similarity_clicked)
            self.window.button_similarity.setChecked(False)
            self.window.button_similarity.toggled.connect (self.button_similarity_clicked)

        self.similarity_widget_setVisible(unresolved_mode)
        #drop the content of the tableview (self.tblView_resolution)
        self.label_rows.setText ("0 row(s)")
    #setting the tableView_resolution
        proxyModel =  QSortFilterProxyModel()
        proxyModel.setSourceModel(PN_taxa_resolution_model())
        self.tblView_resolution = self.window.tableView_resolution
        self.tblView_resolution.setModel(proxyModel)
        self.tblView_resolution.sortByColumn(0, Qt.AscendingOrder)
        self.tblView_resolution.setColumnWidth(0,500)
        self.tblView_resolution.horizontalHeader().setStretchLastSection(True)
        selection = self.tblView_resolution.selectionModel()
        selection.selectionChanged.connect(self.tblView_resolution_clickitem)
        selection.currentChanged.connect(self.tblView_resolution_before_clickitem)

        try:
            self.tblView_resolution.model().sourceModel().resetdata(None)
            self.tblView_resolution.repaint()
        except Exception:
            pass

        #get the parameters (schema, table, fieldname of the fieldref 'taxaname')
        #schema = self.trView_occ.schema
        table = self.trView_occ.currentTable # self.trView_occ.currentIndex().data()

        if table is None : 
            return
        tables = self.trView_occ.selectedTables()
        tab_query = []
        for table in tables:
            tab_query.append(self.trView_occ.sql_taxa_resolution(table, unresolved_mode))
        sql_query = '\nUNION '.join(tab_query)    
        #sql_query = self.trView_occ.sql_taxa_resolution(table, unresolved_mode)

        sql_query += "\nORDER by original_name"
        #query the sql and fill the self.tblView_resolution model
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
            #newRow.keyname = query.value("keyname")
            if similarity:
                QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
                self.myprogressBar.setVisible(True)
                self.myprogressBar.setValue(0)
                pvalue +=1
                self.myprogressBar.setValue(int(100*pvalue/query_size))

                id_taxonref, taxonref, score = self.tblView_resolution_fillsimilarity(query.value("original_name"))
                if taxonref is not None:
                    newRow.taxon_ref = taxonref + " (" + str(score) + " %)"
                    self.tblView_resolution.model().sourceModel().additem (newRow)
                    self.tblView_resolution.repaint()
                    rows = self.tblView_resolution.model().sourceModel().rowCount()
                    self.label_rows.setText (str(rows) + " row(s) - Taxonomic resolution")
            else:
                data.append(newRow)
        self.myprogressBar.setVisible(False)
        # self.window.button_similarity.toggled.disconnect (self.button_similarity_clicked)
        # self.window.button_similarity.setChecked(False)
        # self.window.button_similarity.toggled.connect (self.button_similarity_clicked)
        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()
        if len(data) > 0:
        #reset the model and repaint the self.tblView_resolution
            #self.label_rows.setText (str(query.size()) + " row(s)")
            self.tblView_resolution.model().sourceModel().resetdata(data)   
            self.tblView_resolution.repaint()
        rows = self.tblView_resolution.model().sourceModel().rowCount()
        self.label_rows.setText (str(rows) + " row(s)")
            # else:
            #     self.tblView_resolution.model().sourceModel().additem (newRow)
            # self.tblView_resolution.repaint()
            #
        #set_enabled_buttons()


    def tblView_resolution_fillsimilarity(self, search_name):
            threshold = self.window.slider_similarity.value()/100
            threshold = str(min(threshold, 0.99))
            #sql_query = "SELECT taxonref, score, id_taxonref FROM taxonomy.pn_taxa_searchname('" + selecteditem.synonym +"', " + threshold + ") LIMIT 1"

            sql_txt = "SELECT id_taxonref, taxonref, score FROM taxonomy.pn_taxa_searchname('" + search_name +"', "+ threshold +") LIMIT 1"
            query = QtSql.QSqlQuery (sql_txt)
            if query.next() :
                    return query.value("id_taxonref"), query.value("taxonref"), query.value("score")
            return None, None, None

            # imax = 100
            # for synonym in self.tblView_resolution.model().sourceModel()._data:
            #     taxonref = ''
            #     category =''
            #     sql_txt = "SELECT taxonref FROM taxonomy.pn_taxa_searchname('" + synonym.synonym +"', 0.6)"
                

            #     txt = synonym.synonym + ';' + category + ';' + taxonref
            #     i +=1
            #     ivalue= int(100*i/imax)
            #     self.myprogressBar.setValue(ivalue)
            #     self.window.statusbar.showMessage ("Export in progress, " + str(i) + " of "  +str(imax) + " rows")
            #     f.write(txt +'\n')
            #     self.myprogressBar.setVisible(False)


    def set_similarity(self, value):
        #slot for the slider of similarity threshold
        value = (value // 10) * 10
        value = max(20, value)
        self.window.slider_similarity.setSliderPosition(value)
        self.window.label_similarity.setText(str(value) + ' %')

    def tblView_resolution_before_clickitem(self, current_index, previous_index):
        # unreference the associated button_shortcut on previous_index (before clicking a new item)
        if previous_index.row() < 0:
            return
        elif previous_index.row() == current_index.row():
            return
        column2_index = self.tblView_resolution.model().index(previous_index.row(),1)
        self.tblView_resolution.setIndexWidget(column2_index, None)

    def tblView_resolution_clickitem(self):
        #get the current selectedItem
        selecteditem = self.tblView_resolution.model().data(self.tblView_resolution.currentIndex(), Qt.UserRole)
        #id_taxon_ref = selecteditem.idtaxonref
        column2_index = self.tblView_resolution.model().index(self.tblView_resolution.currentIndex().row(),1)
        #manage the shortcut button over the second column of the main listview
        if not selecteditem.resolved:
            #button_txt = selecteditem.taxaname
            button_shortcut = QtWidgets.QPushButton("button")
            font = QtGui.QFont()
            font.setPointSize(10)
            button_shortcut.setFont
            button_shortcut.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
            stylesheet = "QPushButton {border-style: outset;border-width: 2px; border-radius: 10px;}"
            button_shortcut.setStyleSheet(stylesheet)
            
            button_shortcut.clicked.connect(self.button_sortcut_click)
            threshold = str(self.window.slider_similarity.value()/100)
            sql_query = "SELECT taxonref, score, id_taxonref FROM taxonomy.pn_taxa_searchname('" + selecteditem.synonym +"', " + threshold + ") LIMIT 1"
            query = QtSql.QSqlQuery (sql_query)
            self.suggested_id_taxonref = 0
            self.suggested_name_taxon_ref = None
            if query.next() :
                button_txt = str(query.value("taxonref")) + ' - (' +str(query.value("score")) +' %)'
                self.suggested_id_taxonref = int(query.value("id_taxonref"))
                self.suggested_name_taxon_ref = str(query.value("taxonref"))
            else:
                button_txt = 'Unresolved Taxaname'
            button_shortcut.setText (button_txt)
            self.tblView_resolution.setIndexWidget(column2_index, button_shortcut)
        else:
            pass
    
    def button_sortcut_click(self):
        #manage the mobile button that cover the self.tblView_resolution for the unresolved taxanames
        #add synonym when click with shift key pressed
        selecteditem = self.tblView_resolution.model().data(self.tblView_resolution.currentIndex(), Qt.UserRole)
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == Qt.ShiftModifier:
            new_idtaxonref = self.suggested_id_taxonref
            new_synonym = selecteditem.synonym
            new_category = 'Orthographic'
            taxa_name = self.suggested_name_taxon_ref
            sql_query = f"SELECT taxonomy.pn_names_add ('{new_synonym}','{new_category}',{new_idtaxonref})"
            result = QtSql.QSqlQuery (sql_query)
            if len(result.lastError().nativeErrorCode ()) == 0:
                selecteditem.id_taxonref = new_idtaxonref
                selecteditem.taxon_ref = taxa_name
            else:
                msg = postgres_error(result.lastError())
                QtWidgets.QtWidgets.QMessageBox.critical(self.ui_addname, "Database error", msg, QtWidgets.QtWidgets.QMessageBox.Ok)
        else:
            class_newname = PN_edit_synonym (selecteditem)
            class_newname.show()
        self.tblView_resolution.repaint()
        column2_index = self.tblView_resolution.model().index(self.tblView_resolution.currentIndex().row(),1)
        self.tblView_resolution.setIndexWidget(column2_index, None)
        self.tblView_resolution_clickitem()

    def export_to_image(self):
    #export figure to file
        #set parameters to QfileDialog
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.ReadOnly
        #options |= QFileDialog.DontUseNativeDialog
        file_dialog = QtWidgets.QFileDialog()
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
            self.myFigure.figure.savefig(file_name, dpi = 600, format = ext)




if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    #set the style
    with open("Diffnes.qss", "r") as f:
        #with open("Photoxo.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)

    #open the mainwindow
    window = MainWindow()
    window.show()
    app.exec()







############# figure to plot (tab "Explore DataSet" of the GUI) ###########
# def trView_taxa_fill():
#     #load the treeview list of taxa
#     model = QtGui.QStandardItemModel()
#     root = QtGui.QStandardItem("All Taxa")
#     model.appendRow([root],)
#     ls_taxas = self.trView_occ.get_taxas()
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
#     self.window.trView_properties.setModel(model)
#     self.window.trView_properties.clicked.connect(self.figure_plot)

# def trView_taxa_selectitem():
#     self.figure_plot()
#     return
#     #fill the list result_self.trView_occ with the trait datas
#     try:
#         taxa = self.window.trView_properties.currentIndex().data()
#     except:
#         taxa = ''
#     if taxa == "All Taxa":
#         taxa = ''
#     elif taxa is None:
#         taxa = ''
#     self.myPlotClass.searchtaxa = taxa
#     if self.window.cb_figures.currentIndex() == 0:
#         PN_trview_traits = PN_taxa_identity (self.window.result_self.trView_occ)
#         PN_trview_traits.setData(self.myPlotClass.get_traits_occurrences())
#         tab_header = ['Category', 'Species', 'Occurrences']
#         model = self.window.result_self.trView_occ.model()
#         model.setHorizontalHeaderLabels(tab_header)
#         self.window.result_self.trView_occ.header().setSectionResizeMode(0,QHeaderView.Stretch)
#         self.window.result_self.trView_occ.header().setDefaultAlignment(Qt.AlignLeft|Qt.AlignVCenter)
#     else:
#         self.figure_plot()




# def fill_fields():
#     table = self.trView_occ.currentIndex().data()
#     sql_query = "SELECT column_name, data_type"
#     sql_query += "\n FROM information_schema.columns 
#     sql_query += "\n WHERE table_schema = '_schema_' AND table_name =  '_tablename_'"
#     sql_query += "\n ORDER BY ordnal_position
#     sql_query = sql_query.replace('_tablename_', table)
#     sql_query = sql_query.replace('_schema_', 'occurrences')
#     #print (sql_query)
#     query = QtSql.QSqlQuery (sql_query)
#     self.window.cb_fields.clear()
#     while query.next():
#         field = query.value("column_name")
#         self.window.cb_fields.addItem(field)

 
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
#     selecteditem = self.tblView_resolution.model().data(self.tblView_resolution.currentIndex(), Qt.UserRole)
#     if selecteditem == None:
#         return
#     if selecteditem.resolved == False:
#         return
#     new_synonym = PNSynonym (None, selecteditem.taxon_ref, selecteditem.idtaxonref)
#     class_newname = PN_edit_synonym (new_synonym)
#     class_newname.show()
#     if new_synonym.idsynonym > 0:
#         #refresh self.tblView_resolution model (add synonym reference, NOT PERSISTENT IN DATABASE)
#         self.tblView_resolution.model().sourceModel().refresh (new_synonym)        
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
#         #refresh self.tblView_resolution model (add and delete synonym reference, NOT PERSISTENT IN DATABASE)
#         self.tblView_resolution.model().sourceModel().refresh (old_synonym)
#         self.tblView_resolution.model().sourceModel().refresh (selecteditem)

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
#         #refresh self.tblView_resolution model (delete synonym reference, NOT PERSISTENT IN DATABASE)
#         deleted_synonym = PNSynonym(selecteditem.synonym,'', 0)
#         self.tblView_resolution.model().sourceModel().refresh (deleted_synonym)
#         fill_listsimilarname (selecteditem.idtaxonref)

# def set_enabled_buttons():
#     #manage the availability of the three edit buttons
#     button_add.setEnabled (False)
#     button_edit.setEnabled(False)
#     button_del.setEnabled(False)
#     data_msg.setText('No selection')
#     selected_taxa = self.tblView_resolution.model().data(self.tblView_resolution.currentIndex(), Qt.UserRole)
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
#     # table = self.window.occ_tables_treeView.currentIndex().data(0) 
#     # field_name = CL_tables_occurrences.fieldName (schema, table, 'taxaname')
#     schema, table, field_name = selected_Field()
#     if len(schema)*len(field_name)*len(table) == 0 :return
#     schema_table = schema+'.' + table

#     #field_name = self.window.cb_field.currentText()
#     sql_query = "SELECT * FROM taxonomy.pn_taxa_setresolvedname('" + schema_table + "','" +field_name +"')"
#     query = QtSql.QSqlQuery (sql_query)
#     if query.next():
#         self.window.statusbar.showMessage (str(query.value(0)) + " row(s) updated")


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
#     self.myprogressBar.setVisible(True)
#     self.myprogressBar.setValue(0)
#     i = 0
#     ivalue = 0
#     imax = self.tblView_resolution.model().sourceModel().rowCount()
#     for synonym in self.tblView_resolution.model().sourceModel()._data:
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
#             self.myprogressBar.setValue(ivalue)
#             self.window.statusbar.showMessage ("Export in progress, " + str(i) + " of "  +str(imax) + " rows")
#             f.write(txt +'\n')
#     self.myprogressBar.setVisible(False)
#     self.window.statusbar.showMessage ("Export terminate")
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
    # self.window.occ_tables_treeView.setModel(model)
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
#         table = self.window.occ_tables_treeView.currentIndex().data() 
#         field_name = CL_tables_occurrences.fieldName (schema, table, field)
#     except:
#         pass
#     return schema, table, field_name

# def occ_tables_treeView_checkedchange2(item):
#     model = self.window.occ_tables_treeView.model()
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
    # table_view2 = self.window.tableview_names    
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
    #self.window.radio_unresolved.clicked.connect (occ_tables_treeView_selectionchange)
    # button_add = self.window.pushButtonAdd
    # button_add.clicked.connect(button_add_synonym)

    # button_edit = self.window.pushButtonEdit
    # button_edit.clicked.connect(button_edit_synonym)
    
    # button_del = self.window.pushButtonDel
    # button_del.clicked.connect(button_delete_synonym)

    # cb_table.currentIndexChanged.connect(cb_table_selectionchange)
    # cb_schema.currentIndexChanged.connect(cb_schema_selectionchange)
    

