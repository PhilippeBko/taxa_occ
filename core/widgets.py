###########################################
#imports
import webbrowser
from PyQt5 import QtGui, QtSql, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QItemSelectionModel
from core import functions
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
        else:
            # Restore the default cursor
            QtWidgets.QApplication.restoreOverrideCursor()
        return super().editorEvent(event, model, option, index)

#Class Qtreeview_Json to fill a QTreeView with a json 
class PN_JsonQTreeView(QtWidgets.QTreeView):
    """
    A custom QTreeView widget that displays data from a JSON object.
    ex: json_data = {'identity': {'name': 'acacia', 'authors': 'Mill.', 'published': 'True'}, 'habit': {'epiphyte': '' ....and so on

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
        _validate(): Compares the original data with the current data in the tree view and emits a signal if they are different.
    """
    changed_signal  = pyqtSignal(bool)
    def __init__(self, checkable = False, list_inRows = False, header = None):
        super().__init__()
        self.tab_header = header
        if header is None:
            self.header().hide()
        self.dict_db_properties = {}
        self.id = None
        self.checkable = checkable
        link_delegate = LinkDelegate()
        self.setItemDelegate(link_delegate)
        self.list_inRows = list_inRows
        self.header().setDefaultAlignment(Qt.AlignCenter)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
               
    def refresh(self):
        self.setData(self.dict_db_properties)

    def setData(self, json_data):
    #set the json_data into the treeview model
        def _set_dict_properties (item_base, _dict_item):
        #internal function to set recursively the data into the treeview model
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


    #get the data from database to set the treeview widget model values
        if json_data is None : 
            return
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        self.dict_db_properties = json_data
        try:
            #disconnect the changed event to avoid multiple validation processes
            self.model().dataChanged.disconnect(self._validate)
        except Exception:
            pass
        _set_dict_properties (self.model(), self.dict_db_properties)
        ##validate (and emit signal changed = false in theory !)
        self._validate()
        self.expandAll()

        #ajust header
        header = self.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        if self.tab_header:
            model.setHorizontalHeaderLabels(self.tab_header)
            for col in range(1, self.model().columnCount()):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
        self.model().dataChanged.connect(self._validate)

    def dict_user_properties(self, item_base = None):
    #get the json_data from the treeview model
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

#class to display a search widget composed of a search text and and treeview result with  matched taxa and score
class PN_TaxaSearch(QtWidgets.QWidget):
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
class PN_TaxaQTreeView(QtWidgets.QTreeView):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def setdata(self, myPNTaxa):
# Get the hierarchy for the selected taxa
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
        self.setModel(model)
        self.setColumnWidth(0, 250)
        try:
            if myPNTaxa.idtaxonref * myPNTaxa.id_rank == 0:
                return
        except Exception:
            return
        str_idtaxonref = str(myPNTaxa.idtaxonref)
        # extend to genus where id_rank >= genus (e.g. for species return all sibling species in the genus instead of only the species taxa)
        if myPNTaxa.id_rank >= 14:
            str_idtaxonref = "(SELECT * FROM taxonomy.pn_taxa_getparent(" + str_idtaxonref + ",14))"
        # construct the Query statement, based on the Union betweens parents and childs
        sql_query = "SELECT id_taxonref, id_rank, id_parent, taxaname,  coalesce(authors,'')::text authors, published FROM"
        sql_query += "\n(SELECT id_taxonref, id_rank, id_parent, taxaname,  authors, published"
        sql_query += "\nFROM taxonomy.pn_taxa_parents(" + str_idtaxonref + ", True)"
        sql_query += "\nUNION SELECT id_taxonref, id_rank, id_parent, taxaname,  authors, published"
        sql_query += "\nFROM taxonomy.pn_taxa_childs(" + str_idtaxonref + ", False)) a"
        
        # add a sqlwhere statement according to rank to limit the child deepth avoiding a mega-tree long to load for upper taxonomic rank (class, order,...)
        if myPNTaxa.id_rank < 10:
            sql_query += "\nWHERE a.id_rank <=10"
        #add ordering
        sql_query += "\nORDER BY a.id_rank, a.taxaname"
        #print (sql_query)
        model = self.model()
        # model.setRowCount(0)
        model.setColumnCount(4)
        # execute the Query and fill the treeview standarditemmodel based on search id_parent into the third column containing id_taxonref
        query = QtSql.QSqlQuery(sql_query)
        #set the taxon to the hierarchical model rank = taxon
        key_index = None
        while query.next():
            ls_item_taxonref = []
            ls_item_taxonref = model.findItems(str(query.value('id_parent')), Qt.MatchRecursive, 2)  # MatchExactly
            _rankname = functions.get_dict_rank_value(query.value('id_rank'),'rank_name')
            ##query.value('rank_name'))
            _taxonref = str(query.value('taxaname'))
            _authors = str(query.value('authors')).strip()
            if len(_authors) > 0 and not query.value('published'):
                _authors = _authors + ' ined.' 
            #if not _authors in (['', 'null']):
            _taxonref = _taxonref.strip() + ' ' + _authors #str(query.value('authors'))
            _taxonref = _taxonref.strip()

            item = QtGui.QStandardItem(_rankname)
            item1 = QtGui.QStandardItem(_taxonref) ##query.value('taxonref'))
            item2 = QtGui.QStandardItem(str(query.value('id_taxonref')))
            item4 = QtGui.QStandardItem(str(query.value('taxaname')))

            if ls_item_taxonref:
                # get the first col of the QStandardItem
                row = ls_item_taxonref[0].row()
                index = ls_item_taxonref[0].index()
                index0 = index.sibling(row, 0)
                # append a child to the item
                model.itemFromIndex(index0).appendRow([item, item1, item2, item4],) #, item3, item4, item5, item6, item7],)
                # get a reference to the last append item
                key_row = model.itemFromIndex(index0).rowCount()-1
                key_item = model.itemFromIndex(index0).child(key_row, 0)
            else:
                # append as a new line if item not found (or first item)
                model.appendRow([item, item1, item2, item4],) #, item3, item4, item5, item6, item7],)
                key_item = model.item(model.rowCount()-1)
            # set bold the current id_taxonref line (2 first cells)
            if not query.value('published'):
                font = QtGui.QFont()
                font.setItalic(True)
                key_index = key_item.index()
                key_row = key_item.row()
                #model.setData(key_index, font, Qt.FontRole)
                key_index = key_index.sibling(key_row, 1)
                model.setData(key_index, font, Qt.FontRole)

            if query.value('id_taxonref') == myPNTaxa.idtaxonref:
                font = QtGui.QFont()
                font.setBold(True)
                key_index = key_item.index()
                key_row = key_item.row()
                model.setData(key_index, font, Qt.FontRole)
                key_index = key_index.sibling(key_row, 1)
                model.setData(key_index, font, Qt.FontRole)
        if key_index:
            self.selectionModel().setCurrentIndex(key_index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self.setHeaderHidden(True)
        self.hideColumn(2)
        self.hideColumn(3)
        self.expandAll()

    def selecteditem(self):
        #return a PNTaxa for the selected item into the hierarchical model
        try:
            parentname = self.currentIndex().parent().siblingAtColumn(3).data()
        except Exception:
            parentname =''
        try:
            id_taxonref = int(self.currentIndex().siblingAtColumn(2).data())
            sql = f"SELECT id_rank, taxaname, authors, published FROM taxonomy.taxa_names WHERE id_taxonref ={id_taxonref}"

            query = QtSql.QSqlQuery(sql)
            query.next()
            idrank = query.value('id_rank')
            taxaname = query.value('taxaname')
            authors = query.value('authors')
            published = query.value('published')
            dict_item = {'idtaxonref': id_taxonref, 'taxaname': taxaname, 'authors': authors, 'published': published, 'idrank': idrank, 'parent': parentname}
            #item = PNTaxa(id_taxonref, taxaname, authors, idrank, published)
            #item.parent_name = parentname
            return dict_item
        except Exception:
            return
