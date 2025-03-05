# tips to load the QPSQL driver run
# sudo apt install libqt5sql5-psql


import sys
import json
import webbrowser

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtSql
from PyQt5.QtCore import *

from taxa_model import *
from occ_model import *
from api_thread import *
from class_synonyms import *
from edit_taxaname import *
from class_identity import *
import re
#import commons
from commons import *


def createConnection(db):
    db.setHostName("localhost")
    db.setDatabaseName("test")
    db.setUserName("postgres")
    db.setPassword("postgres")
    #app2 = QApplication([])
    if not db.open():
        QMessageBox.critical(None, "Cannot open database",
                             "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        return False
    return True


def sql_taxa_delete_synonym(synonym):
    sql_txt = f"SELECT taxonomy.pn_names_delete ('{synonym}')"
    return sql_txt

def sql_taxa_delete_reference(id_taxonref, do_update=False):
    sql_txt = "SELECT * FROM taxonomy.pn_taxa_delete (" + str(
        id_taxonref) + ", " + str(do_update) + ")"
    return sql_txt

def sql_where_taxanames():
#create a filter on taxa according to combo state
    sql_where = ''
    separator = " WHERE "
    
    if combo_rank.currentIndex() > 0:
        sql_where = "\n WHERE a.id_rank = " + \
            str(dict_rank[combo_rank.currentText()])
        separator = " AND "
    # sql_where from the combo_statut
    if combo_statut.currentIndex() > 0:
        key_statut = combo_statut.currentText()
        if key_statut == 'Unknown':
            _prop = "(properties  -> 'new caledonia' ? 'statut') IS  NULL"
        else:
            _prop = "(properties  @> '{%new caledonia%:{%statut%:%Endemic%}}')".replace('%', chr(34))
            _prop = _prop.replace('Endemic', key_statut)
        sql_where = sql_where + separator + _prop
            #dict_statut[combo_statut.currentText()]
        separator = " AND "
    # sql_where from the combo_habit
    if combo_habit.currentIndex() > 0:
        key_habit = combo_habit.currentText().lower()
        if key_habit == 'unknown':
            _prop = "(properties->'habit') IS NULL"
        else:
            _prop = "(properties  @> '{%habit%:{%tree%:%True%}}')".replace('%', chr(34))
            _prop = _prop.replace('tree', key_habit)
        sql_where = sql_where + separator + _prop
            #dict_habit[combo_habit.currentText()]  #.replace("_", '"')
        separator = " AND "
    # sql_where from the lineEdit_search
    txt_search = lineEdit_search.text()
    txt_search = re.sub(r'[\*\%]', '', txt_search)
    if len(txt_search) > 0:
        txt_search = '%' + txt_search + '%'
        #sql_where = sql_where + separator + "taxaname ILIKE '" + txt_search +"%'"
        sql_where = sql_where + separator + \
            "a.id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_searchname('" + \
            txt_search + "') GROUP by id_taxonref)"
    # return the sql_where corresponding to the state of combos and lineEdit_search
    return sql_where


def tlviews_clear():
    # clear the contents of any tblview
    trview_identity.setModel(None) #.model().setRowCount(0)
    trview_traits.setModel(None)
    #trView_childs.model().setRowCount(0)
    trView_childs.setModel(None)
    trview_metadata.setModel(None)
    tlview_occurrences.setModel(None)
    tlview_similar.setModel(None)
    set_enabled_buttons()

def tlview_refresh(idtaxonref=0):
    # record the current selected row
    currentrow = tlview_taxonref.currentIndex().row()
    # refresh the view
    tlview_taxonref.model().sourceModel().refresh()
    # get the row (id_taxonref) in data of the sourceModel
    row = tlview_taxonref.model().sourceModel().row_idtaxonref(
        idtaxonref)  # item.idtaxonref) ##id_taxonref)
    if row == -1:
        row = currentrow
    row = max(0, min(row, tlview_taxonref.model().rowCount() - 1))
    # get the index and obtain the source map index from the model itself
    index = tlview_taxonref.model().sourceModel().index(row, 0)
    index = tlview_taxonref.model().mapFromSource(index)
    tlview_taxonref.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

def combo_taxa_selectedItem(selecteditem):
    # select the selecteditem in the combo_taxa or create if not exist
    index = -1
    for i in range(len(combo_taxa_data)):
        if combo_taxa_data[i].idtaxonref == selecteditem.idtaxonref:
            index = i
    if index == -1:
        combo_taxa_data.append(selecteditem)
        window.combo_taxa.addItem(selecteditem.taxonref)
        index = window.combo_taxa.count() - 1
    window.combo_taxa.setCurrentIndex(index)


def tab_data_changed(index = None):
    selecteditem = tlview_taxonref.model().data( tlview_taxonref.currentIndex(), Qt.UserRole)
    if selecteditem is None:
        return
    if index is None:
        index = tab_data.currentIndex()
    if index == 0 and trView_childs.model() is None :
        #test = PN_taxa_hierarchy (selecteditem)
        trView_childs.setdata (selecteditem)
        #trView_childs_setdata(selecteditem)
    elif index == 2 and tlview_similar.model() is None :
        tlview_similar_setData(selecteditem)
    elif index == 1 and trview_metadata.model() is None :
        trview_metadata_setData(selecteditem)
    elif index == 3 and tlview_occurrences.model() is None:
        tlView_occurences_setdata(selecteditem)




def trview_identity_changed(changed):
    buttonbox_identity.setEnabled(changed)

def trview_identity_apply():
    #apply the current user dictionnary into the database
    id_taxonref = PN_trview_identity.id
    #get the dictionnaries (db = input and user = output)
    dict_user_properties = PN_trview_identity.dict_user_properties()
    dict_db_properties = PN_trview_identity.dict_db_properties

    if dict_db_properties == dict_user_properties: return

    #check that dictionnaries identity are different to proceed to an update in the taxa_reference table
    if dict_db_properties["identity"] != dict_user_properties["identity"]:
        _name = dict_user_properties["identity"]["name"]
        _authors = dict_user_properties["identity"]["authors"]

        _published = dict_user_properties["identity"]["published"]
        #use the internal db function to apply and propage modif to childs
        sql_query = "SELECT id_taxonref, taxaname, coalesce(authors,'') as authors, id_rank"
        sql_query +="\nFROM taxonomy.pn_taxa_edit (" + str(id_taxonref)
        sql_query +=", '" + _name +"', '"+_authors + "',Null, Null," + str(_published) + ", True)"
        result = QtSql.QSqlQuery (sql_query)
        code_error = result.lastError().nativeErrorCode ()
        if len(code_error) == 0:
            tab_updated_datas =[]
        #refresh the taxa model of the tlview_taxonref tableview
            while result.next():
                _ispublished = (dict_user_properties["identity"]["published"]== 'True')                
                item = PNTaxa(result.value("id_taxonref"), result.value("taxaname"), result.value("authors"), 
                                result.value("id_rank"),_ispublished)
                tab_updated_datas.append(item)
            #emit a signal with tab_updated_datas (= tab of changed PNTaxa's)
            tlview_taxonref_refresh(tab_updated_datas)
    #create a sub dictionnaries (a copy without the key identity) to compare json_properties
    sub_dict_db_properties = dict_db_properties.copy()
    del sub_dict_db_properties["identity"]
    sub_dict_user_properties = dict_user_properties.copy()
    del sub_dict_user_properties["identity"]

    #if sub_dictionnaries are different, proceed to update with only non-null values
    if sub_dict_db_properties != sub_dict_user_properties:
        tab_result = {}
        for key, value in sub_dict_user_properties.items():
            tab_tmp = {}
            for _key, _value in value.items():
                if _value !='':
                    tab_tmp[_key]= _value
            if len(tab_tmp) > 0:
                tab_result[key] = tab_tmp
        #query according to the len of the result (= Null if zero length)
        sql_query = "UPDATE taxonomy.taxa_reference SET properties = NULL WHERE id_taxonref =" + str(id_taxonref)
        if len (tab_result) > 0:
            sql_query = sql_query.replace('NULL', "'" +json.dumps(tab_result) +"'")
        result = QtSql.QSqlQuery (sql_query)

    #PN_trview_identity.refresh()
    
        


    
def tlview_taxonref_before_clickitem(current_index, previous_index):
    if buttonbox_identity.isEnabled():
        msg = "Some properties have been changed, save the changes ?"
        result = QMessageBox.question(None, "Cancel properties", msg, QMessageBox.Yes, QMessageBox.No)
        buttonbox_identity.setEnabled(False)
        if result == QMessageBox.No:
            buttonbox_identity.setEnabled(False)
            return
        else:
            trview_identity_apply()
            buttonbox_identity.setEnabled(False) #do not move before PN_trview_identity.apply() (see tlview_taxonref_refresh)
    return



def tlview_taxonref_click():
    tlviews_clear()
    # get the selectedItem
    selecteditem = tlview_taxonref.model().data( tlview_taxonref.currentIndex(), Qt.UserRole)
    if selecteditem is None:
        return
    # set the identity data
    #window.groupBox_identity.setTitle(selecteditem.rank_name)
    #button_box = window.buttonbox_identity_identity

    global PN_trview_identity
    #save the id_taxonref and set the dictionnary (json_data) according to ?
    PN_trview_identity.id = selecteditem.idtaxonref
    PN_trview_identity.setData(get_taxa_identity(selecteditem))
    
    global PN_tlview_traits    
    PN_tlview_traits.setData(get_traits_occurrences(selecteditem))
    tab_data_changed ()

def toolbox_click(index):
    window.toolBox.setItemIcon(0, window.style().standardIcon(53))
    window.toolBox.setItemIcon(1, window.style().standardIcon(53))
    window.toolBox.setItemIcon(index, window.style().standardIcon(51))

def tlview_taxonref_dblclick():
    # Select or insert the selecteditem into the combo_taxa combobox for shortcut
    selecteditem = tlview_taxonref.model().data(
        tlview_taxonref.currentIndex(), Qt.UserRole)
    combo_taxa_selectedItem(selecteditem)
def trView_childs_dblclick():
    selecteditem = trView_childs.selecteditem()
    combo_taxa_selectedItem(selecteditem)
def tlview_taxonref_setData():
    # Fill the main tlview_taxonref with the concacenate sql (cf.sql_reference_names)
    # clean the content and selection of tlview_taxonref
    tlview_taxonref.setCurrentIndex(QModelIndex())
    #tlview_similar.model().sourceModel().resetdata(None)
    tlviews_clear()
    # search for a selected taxonref in combo_taxa
    index = combo_taxa.currentIndex()
    idtaxonref = combo_taxa_data[index].idtaxonref

    sql_query = "WITH taxa_occurrences AS ( SELECT id_taxonref, original_name FROM taxonomy.pn_taxa_searchnames (array(SELECT taxaname FROM ("
    sql_query += "SELECT nom_taxon AS taxaname FROM occurrences.occ_ncpippn UNION SELECT taxon FROM occurrences.occ_botanic) b  GROUP BY taxaname)) )"
    # create sql_query (depend if idtaxonref >0) and concacenate with sql_where
    sql_query += "\nSELECT a.taxaname::text, coalesce(b.original_name,'')::text authors, a.id_rank, a.id_taxonref, published, c.score_api "


    sql_query = "\nSELECT a.taxaname::text, a.authors, a.id_rank, a.id_taxonref, a.published, score_api "
    sql_query +="\nFROM taxonomy.taxa_names a "
    #sql_query +="\nFROM taxa_occurrences b LEFT JOIN taxonomy.taxa_reference a ON a.id_taxonref = b.id_taxonref"
    sql_query +="\nLEFT JOIN (SELECT id_taxonref, count(id_taxonref) as score_api FROM"
    sql_query +="\n(SELECT id_taxonref, jsonb_each(metadata) FROM taxonomy.taxa_reference WHERE metadata IS NOT NULL) z"
    sql_query +="\nGROUP BY id_taxonref ) c"
    sql_query +="\nON a.id_taxonref = c.id_taxonref"





    if idtaxonref > 0:
        sql_query += "\nINNER JOIN taxonomy.pn_taxa_childs (" + str(
            idtaxonref) + ",True) b ON a.id_taxonref = b.id_taxonref"
    sql_query += sql_where_taxanames()
    sql_query += "\nORDER BY a.taxaname"



    print (sql_query)
    # fill tlview with query result
    data = []
    query = QtSql.QSqlQuery(sql_query)
    #print (query.lastError().text())
    i = 0
    while query.next():
        item = PNTaxa(query.value("id_taxonref"), query.value("taxaname"), query.value("authors"), 
                      query.value("id_rank"), query.value("published"))
        item.api_score = query.value("score_api")
        data.append(item)
        i += 1
    # reset the model to the tableview for refresh
    tlview_taxonref.model().sourceModel().resetdata(data)
    tlview_taxonref.resizeColumnsToContents()
    #tlview_taxonref.setColumnWidth(0, 100)
    # Display row count within the statusbar
    window.statusbar.showMessage(str(i) + " row(s)")
    # if combo_taxa is activated, try to select the taxa (depend of the other filters)
    if index > 0:
        try:
            row = tlview_taxonref.model().sourceModel().row_idtaxonref(idtaxonref)
            index = tlview_taxonref.model().index(row, 0)
            tlview_taxonref.selectionModel().setCurrentIndex(
                index, QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        except:
            return

def tlview_taxonref_refresh(tab_items):
    selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
    for item in tab_items:
        tlview_taxonref.model().sourceModel().refresh(item)
    tlview_taxonref.model().sourceModel().refresh()
    #only refresh tlview_taxon when buttonbox_identity is not enabled (no save in progress, see tlview_taxonref_before_clickitem and button_identity_apply_click)
    if buttonbox_identity.isEnabled():return
    tlview_refresh(selecteditem.idtaxonref)








#to display and manage a treeview with hiercharchical taxonomy from a PNtaxaselecteditem
class PN_taxa_hierarchy(QTreeView):
    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.PNTaxa = myPNTaxa
        

    def setdata(self, myPNTaxa):
# Get the hierarchy for the selected taxa
    #exit if the model already exist
    #if trView_childs.model() is not None: return
    #create a model and set the slots connexion
        selecteditem = myPNTaxa

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
        self.setModel(model)
        self.setColumnWidth(0, 250)
        selection = self.selectionModel()
        selection.selectionChanged.connect(set_enabled_buttons)
        try:
            if myPNTaxa.idtaxonref * myPNTaxa.id_rank == 0:
                return
        except:
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
        # elif myPNTaxa.id_rank < 14:
        #     sql_query += "\nWHERE a.id_rank <=14"
        #sql_query += sql_where
        sql_query += "\nORDER BY a.id_rank, a.taxaname"
        #print (sql_query)
        model = self.model()
        # model.setRowCount(0)
        model.setColumnCount(4)
        # execute the Query and fill the treeview standarditemmodel based on search id_parent into the third column containing id_taxonref
        query = QtSql.QSqlQuery(sql_query)
        while query.next():
            ls_item_taxonref = []
            ls_item_taxonref = model.findItems(str(query.value('id_parent')), Qt.MatchRecursive, 2)  # MatchExactly
            _rankname = commons.get_dict_rank_value(query.value('id_rank'),'rank_name')
            ##query.value('rank_name'))
            _taxonref = str(query.value('taxaname'))
            _authors = str(query.value('authors')).strip()
            if len(_authors) > 0 and query.value('published') == False:
                _authors = _authors + ' ined.' 
            #if not _authors in (['', 'null']):
            _taxonref = _taxonref.strip() + ' ' + _authors #str(query.value('authors'))
            _taxonref = _taxonref.strip()

            item = QtGui.QStandardItem(_rankname)
            item1 = QtGui.QStandardItem(_taxonref) ##query.value('taxonref'))
            item2 = QtGui.QStandardItem(str(query.value('id_taxonref')))
            # item3 = QtGui.QStandardItem(str(query.value('id_rank')))
            item4 = QtGui.QStandardItem(str(query.value('taxaname')))
            # item5 = QtGui.QStandardItem(str(query.value('authors')))
            # item6 = QtGui.QStandardItem(str(query.value('published')))        
            # item7 = QtGui.QStandardItem(str(query.value('basename')))


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
            if query.value('published') == False:
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
        self.selectionModel().setCurrentIndex(key_index, QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self.setHeaderHidden(True)
        self.hideColumn(2)
        self.hideColumn(3)
        # self.hideColumn(4)
        # self.hideColumn(5)
        # self.hideColumn(6)
        # self.hideColumn(7)
        self.expandAll()

    def selecteditem(self):
        #get a PNTaxa from the selected trView_childs item
        
        try:
            #idparent = int(trView_childs.currentIndex().parent().siblingAtColumn(2).data())
            parentname = trView_childs.currentIndex().parent().siblingAtColumn(3).data()
        except:
            #idparent = None
            parentname =''
        try:
            id_taxonref = int(trView_childs.currentIndex().siblingAtColumn(2).data())
            sql = f"SELECT id_rank, taxaname, authors, published FROM taxonomy.taxa_names WHERE id_taxonref ={id_taxonref}"

            query = QtSql.QSqlQuery(sql)
            query.next()
            idrank = query.value('id_rank')
            taxaname = query.value('taxaname')
            authors = query.value('authors')
            published = query.value('published')

            # idrank = int(trView_childs.currentIndex().siblingAtColumn(3).data())
            # taxaname = str(trView_childs.currentIndex().siblingAtColumn(4).data())
            # authors = str(trView_childs.currentIndex().siblingAtColumn(5).data())
            # published = (trView_childs.currentIndex().siblingAtColumn(6).data()=='True')
            item = PNTaxa(id_taxonref, taxaname, authors, idrank, published)
            #item.id_parent = idparent
            item.parent_name = parentname
            #item.published = published
            return item
        except:
            return








# def trView_childs_setdata(selecteditem):
# # Get the hierarchy for the selected taxa
#     #exit if the model already exist
#     #if trView_childs.model() is not None: return
#     #create a model and set the slots connexion
#     model = QtGui.QStandardItemModel()
#     model.setHorizontalHeaderLabels(['Rank', 'Taxon'])
#     trView_childs.setModel(model)
#     trView_childs.setColumnWidth(0, 250)
#     selection = trView_childs.selectionModel()
#     selection.selectionChanged.connect(set_enabled_buttons)

#     if selecteditem.idtaxonref * selecteditem.id_rank == 0:
#         return
#     str_idtaxonref = str(selecteditem.idtaxonref)
#     # extend to genus where id_rank >= genus (e.g. for species return all sibling species in the genus instead of only the species taxa)
#     if selecteditem.id_rank >= 14:
#         str_idtaxonref = "(SELECT * from taxonomy.pn_taxa_getparent(" + str_idtaxonref + ",14))"

#     # construct the Query statement, based on the Union betweens parents and childs
#     sql_query = "SELECT id_taxonref, id_rank, id_parent, taxaname, basename, coalesce(authors,'')::text authors, published FROM"
#     sql_query += "\n(SELECT id_taxonref, id_rank, id_parent, taxaname, basename, authors, published"
#     sql_query += "\nFROM taxonomy.pn_taxa_parents(" + str_idtaxonref + ", True)"
#     sql_query += "\nUNION SELECT id_taxonref, id_rank, id_parent, taxaname, basename, authors, published"
#     sql_query += "\nFROM taxonomy.pn_taxa_childs(" + str_idtaxonref + ", False)) a"
    
#     # add a sqlwhere statement according to rank to limit the child deepth avoiding a mega-tree long to load for upper taxonomic rank (class, order,...)
#     if selecteditem.id_rank < 10:
#         sql_query += "\nWHERE a.id_rank <=10"
#     # elif selecteditem.id_rank < 14:
#     #     sql_query += "\nWHERE a.id_rank <=14"
#     #sql_query += sql_where
#     sql_query += "\nORDER BY a.id_rank, a.taxaname"
#     #print (sql_query)
#     model = trView_childs.model()
#     # model.setRowCount(0)
#     model.setColumnCount(8)
#     # execute the Query and fill the treeview standarditemmodel based on search id_parent into the third column containing id_taxonref
#     query = QtSql.QSqlQuery(sql_query)
#     while query.next():
#         ls_item_taxonref = []
#         ls_item_taxonref = model.findItems(str(query.value('id_parent')), Qt.MatchRecursive, 2)  # MatchExactly
#         _rankname = commons.get_dict_rank_value(query.value('id_rank'),'rank_name')
#          ##query.value('rank_name'))
#         _taxonref = str(query.value('taxaname'))
#         _authors = str(query.value('authors')).strip()
#         if len(_authors) > 0 and query.value('published') == False:
#             _authors = _authors + ' ined.' 
#         #if not _authors in (['', 'null']):
#         _taxonref = _taxonref.strip() + ' ' + _authors #str(query.value('authors'))
#         _taxonref = _taxonref.strip()

#         item = QtGui.QStandardItem(_rankname)
#         item1 = QtGui.QStandardItem(_taxonref) ##query.value('taxonref'))
#         item2 = QtGui.QStandardItem(str(query.value('id_taxonref')))
#         item3 = QtGui.QStandardItem(str(query.value('id_rank')))
#         item4 = QtGui.QStandardItem(str(query.value('taxaname')))
#         item5 = QtGui.QStandardItem(str(query.value('authors')))
#         item6 = QtGui.QStandardItem(str(query.value('published')))        
#         item7 = QtGui.QStandardItem(str(query.value('basename')))


#         if ls_item_taxonref:
#             # get the first col of the QStandardItem
#             row = ls_item_taxonref[0].row()
#             index = ls_item_taxonref[0].index()
#             index0 = index.sibling(row, 0)
#             # append a child to the item
#             model.itemFromIndex(index0).appendRow([item, item1, item2, item3, item4, item5, item6, item7],)
#             # get a reference to the last append item
#             key_row = model.itemFromIndex(index0).rowCount()-1
#             key_item = model.itemFromIndex(index0).child(key_row, 0)
#         else:
#             # append as a new line if item not found (or first item)
#             model.appendRow([item, item1, item2, item3, item4, item5, item6, item7],)
#             key_item = model.item(model.rowCount()-1)
#         # set bold the current id_taxonref line (2 first cells)
#         if query.value('published') == False:
#             font = QtGui.QFont()
#             font.setItalic(True)
#             key_index = key_item.index()
#             key_row = key_item.row()
#             #model.setData(key_index, font, Qt.FontRole)
#             key_index = key_index.sibling(key_row, 1)
#             model.setData(key_index, font, Qt.FontRole)

#         if query.value('id_taxonref') == selecteditem.idtaxonref:
#             font = QtGui.QFont()
#             font.setBold(True)
#             key_index = key_item.index()
#             key_row = key_item.row()
#             model.setData(key_index, font, Qt.FontRole)
#             key_index = key_index.sibling(key_row, 1)
#             model.setData(key_index, font, Qt.FontRole)
#     trView_childs.selectionModel().setCurrentIndex(key_index, QtCore.QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
#     trView_childs.hideColumn(2)
#     trView_childs.hideColumn(3)
#     trView_childs.hideColumn(4)
#     trView_childs.hideColumn(5)
#     trView_childs.hideColumn(6)
#     trView_childs.hideColumn(7)
#     trView_childs.expandAll()


# def trView_childs_selecteditem():
#     #get a PNTaxa from the selected trView_childs item
    
#     try:
#         #idparent = int(trView_childs.currentIndex().parent().siblingAtColumn(2).data())
#         parentname = trView_childs.currentIndex().parent().siblingAtColumn(4).data()
#     except:
#         #idparent = None
#         parentname =''
#     try:
#         id_taxonref = int(trView_childs.currentIndex().siblingAtColumn(2).data())
#         idrank = int(trView_childs.currentIndex().siblingAtColumn(3).data())
#         taxaname = str(trView_childs.currentIndex().siblingAtColumn(4).data())
#         authors = str(trView_childs.currentIndex().siblingAtColumn(5).data())
#         published = (trView_childs.currentIndex().siblingAtColumn(6).data()=='True')
#         item = PNTaxa(id_taxonref, taxaname, authors, idrank, published)
#         #item.id_parent = idparent
#         item.parent_name = parentname
#         #item.published = published
#         return item
#     except:
#         return



def button_addNames_click():
    selecteditem = trView_childs.selecteditem()
    if selecteditem is None: 
        return
        #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
    win = PN_add_taxaname(selecteditem)
    win.apply_signal.connect(tlview_taxonref_refresh)
    win.show()

def button_editChilds_click():
    try:
        selecteditem = trView_childs.selecteditem()
        if selecteditem is None:
            return
            #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
        win = PN_edit_taxaname(selecteditem)
        win.apply_signal.connect(tlview_taxonref_refresh)
        win.show()
    except:
        return

def button_DelChilds_click():
    selecteditem = trView_childs.selecteditem()
    if selecteditem is None:
        return
    # message to be display first (question, Yes or Not)

    msg = "The Taxa: " + selecteditem.taxonref
    msg += "\nincluding children and synonyms is about to be permanently deleted"
    msg += "\nAre you sure to proceed ?"
    result = QMessageBox.question(
        None, "Delete a taxa", msg, QMessageBox.Yes, QMessageBox.No)
    if result == QMessageBox.No:
        return
        # execute the suppression
    sql_query = sql_taxa_delete_reference(selecteditem.id_taxonref, True)
    result = QtSql.QSqlQuery(sql_query)
    if len(result.lastError().nativeErrorCode()) == 0:
        # refresh the data after deleting the selected taxa and childs
        while result.next():
            tlview_taxonref.model().sourceModel().delete(result.value("id_taxonref"))
        tlview_refresh(selecteditem.id_taxonref)
    else:
        msg = msg + "Undefined error"
        msg = msg + "\n\n" + result.lastError().text()
        QMessageBox.critical(None, "Database error", msg, QMessageBox.Ok)
    return

def button_MergeChilds_click():
    # get the selectedItem
    try:
        selecteditem = trView_childs.selecteditem()
        win = PN_move_taxaname(selecteditem, True)
        win.show()

        #refresh the tlview_taxonref (win.main_tableView)
        if win.updated:
            # deleted the merge taxa
            tlview_taxonref.model().sourceModel().delete(selecteditem.idtaxonref)
            # update the sub-taxas properties
            for item in win.updated_datas:
                tlview_taxonref.model().sourceModel().refresh(item)
           # refresh the entire view
            tlview_taxonref.model().sourceModel().refresh()
            id_taxonref = win.selecteditem.idtaxonref
            # refresh the view
            tlview_refresh(id_taxonref)
    except:
        return















def tlView_occurences_setdata(selecteditem):
    #if tlview_occurrences.model() is not None: return
    model = QtGui.QStandardItemModel()
    tlview_occurrences.setModel(model)
    tlview_occurrences.horizontalHeader().setHighlightSections(False)
    #tlview_occurrences.model().setRowCount(0)
    sql_query = "SELECT id_source, source, original_name, dbh::numeric dbh_cm,elevation::integer elevation_m, rainfall::integer rainfall_mm,"
    sql_query += "\nCASE WHEN holdridge = 1 THEN 'Dry' WHEN holdridge = 2 THEN 'Moist'"
    sql_query += "\nWHEN holdridge = 3 THEN 'Wet' ELSE NULL END Holdridge,"
    sql_query += "\nprovince, in_forest, in_um::boolean AS um_substrat"
    sql_query += "\nFROM public.amap_data_occurrences"
    #sql_query += "\nWHERE geo_pt IS NOT NULL "
    #sql_query += "\AND id_taxonref = " + str(selecteditem.idtaxonref)
    sql_query += "\nWHERE id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs(" + str(selecteditem.idtaxonref)+ ", True))"
    sql_query += "\nORDER BY source, original_name"
    query = QtSql.QSqlQuery(sql_query)
    tab_header = []
    record = query.record()
    for i in range(record.count()):
        tab_header.append(record.fieldName(i))

    model.setHorizontalHeaderLabels(tab_header)
    # clear the table of similar names
    while query.next():
        tab_txt = []
        for x in tab_header:
            item = QtGui.QStandardItem()
            if query.value(x) is not None:
                item.setData(query.value(x), QtCore.Qt.DisplayRole)
            tab_txt.append(item)
        model.appendRow(tab_txt)
    tlview_occurrences.resizeColumnsToContents()


def tlview_similar_setData(selecteditem):
    #if tlview_similar.model() is not None: return
    model = TableSimilarNameModel()
    #tlview_similar.setModel(model)

    proxyModel = QSortFilterProxyModel()
    proxyModel.setSourceModel(model)
    tlview_similar.setModel(proxyModel)
    header = tlview_similar.horizontalHeader()
    header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch) 

    tlview_similar.setColumnWidth(1, 150)
   # tlview_similar.horizontalHeader().setStretchLastSection(True)
    selection = tlview_similar.selectionModel()
    selection.selectionChanged.connect(set_enabled_buttons)

    sql_query = "SELECT name, category"
    sql_query += f"\nFROM taxonomy.pn_names_items({selecteditem.idtaxonref}) WHERE id_category > 4"

    data = []
    model = tlview_similar.model()
    # clear the table of similar names
    model.sourceModel().resetdata(None)
    query = QtSql.QSqlQuery(sql_query)
    while query.next():
        data.append(PNSynonym(
                    synonym = query.value("name"),
                    idtaxonref = selecteditem.idtaxonref,
                    category = query.value("category")
                    ))
    model.sourceModel().resetdata(data)



def trview_metadata_setData(selecteditem):
    #load metadata json from database to trview_metadata
    model = QtGui.QStandardItemModel()
    model.setColumnCount(3)
    trview_metadata.setModel(model)
    trview_metadata.hideColumn(2)
    trview_metadata.setColumnWidth(0, 250)

    sql_query = "SELECT a.metadata FROM taxonomy.taxa_reference a"
    sql_query += "\nWHERE a.id_taxonref = " + str(selecteditem.idtaxonref)
    query = QtSql.QSqlQuery(sql_query)
    
    query.next()
    if not query.isValid():
        return
    if query.isNull("metadata"):
        return
    try:
        json_data = query.value("metadata")
    except:
        json_data = None
        return
    
    if json_data is None:
        return
    api_json = json.loads(json_data)
    for base, api_item in api_json.items():
        trview_metadata_setItem(base, api_item)


def trview_metadata_setDataAPI(base, api_json):
    # receive the slot from metaworker - save the json into the database when finish (base = 'END')
    selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
    _selecteditem = metadata_worker.PNTaxa_model
    sql_query =''
    _data_list = None

    if base == "END":
        #metadata_worker.PNTaxa_model.json_request = None
        if api_json is None: # when a kill
            return
        tab_synonyms =[]
        #decompose synonyms and metadata
        for taxa in api_json: 
            try:
                tab_synonyms += api_json[taxa]["synonyms"]
            #to suppress synonyms from json before saving (do we save or not ? NOT)
                #api_json[taxa].pop("synonyms")
            except:
                continue
        #manage synonyms, search for duplicate
        _taxaname=''
        _parser=''verticalLayout_3
            _taxaname += _parser +"'" +taxa.strip() +"'"
            _parser=", "
         #get the new names that are not in the taxa namespace (id_taxonref IS NULL)
        sql_query = f"SELECT original_name FROM taxonomy.pn_taxa_searchnames( array[{_taxaname}]) WHERE id_taxonref IS NULL"        
        #sql_query = sql_query.replace('_taxaname', _taxaname)
        query = QtSql.QSqlQuery (sql_query)
        new_unique_taxa = []
        while query.next():
            new_unique_taxa.append (query.value("original_name"))

        #add new synonyms names according to the previous query
        #sql_insert = "SELECT taxonomy.pn_taxa_edit_synonym ('_synonymstr','Nomenclatural'," +str( selecteditem.id_taxonref) + ")" 
        
        sql_insert = f"SELECT taxonomy.pn_names_add ('_synonymstr','Nomenclatural',{selecteditem.id_taxonref})"
        for taxa in new_unique_taxa:
            dict_taxa = commons.get_dict_from_species(taxa)
            for value in dict_taxa["names"]:
                sql_query = sql_insert.replace('_synonymstr', str(value))
                try:
                    query = QtSql.QSqlQuery()
                    query.exec(sql_query)
                    #delete current model to ensure refresh of similar names
                    tlview_similar.setModel(None)
                except:
                    continue

        #manage and save json medata (including or not synonyms depends of the check line above)
        if len(api_json) == 0:
            sql_query = "UPDATE taxonomy.taxa_reference SET metadata = NULL"
        else:
            _data_list = json.dumps(api_json)
            sql_query = "UPDATE taxonomy.taxa_reference SET metadata = '" +  _data_list + "'"
        sql_query += " WHERE id_taxonref = " +  str(_selecteditem.id_taxonref)
        db.exec(sql_query)
        #update the value metadata from the selecteditem
        _selecteditem.api_score = len(api_json)   
        tlview_taxonref.repaint()         
    else:
        #manage json in live ! coming from the metadata_worker api_thread, one by one
        if selecteditem != _selecteditem:
            return        
        if metadata_worker.status == 0:
            return
        #fill the treeview with the dictionnary json
        trview_metadata_setItem(base, api_json)
        # tab_json = {}
        # tab_json[base]=  api_json
        if get_str_value(api_json["name"]) != '':
            _selecteditem.api_score +=1
        tlview_taxonref.repaint()
    return
 

def trview_metadata_setItem(base, api_item):
    # set one api item into the trview_metadata, associated to a base
    model = trview_metadata.model()
    item_base= QtGui.QStandardItem(base.upper())
    item_msg = None
    item_web = None
    #to ensure compatibility with previous api_result (without webpage)
    try:
        if len(api_item["webpage"]) > 0:
            item_web = QtGui.QStandardItem(api_item["webpage"])
    except:
            pass
    try:
        if len(api_item["url"]) == 0:
            item_msg = QtGui.QStandardItem('No or slow internet connection')
        if len(api_item["name"]) == 0:
            item_msg = QtGui.QStandardItem('No data available')
        
        model.appendRow([item_base, item_msg, item_web],)
    except:
        return

    for _key, _value in api_item.items():
        if _key not in ("rank","name","_links","url", "synonyms", "webpage", '_synonyms'):
            _key = _key.title()
            item_value = QtGui.QStandardItem(_value)
            item_key = QtGui.QStandardItem(_key)
           # item_web = QtGui.QStandardItem(api_item["webpage"])
            item_base.appendRow([item_key, item_value],)
            ls_item = trview_identity.model().findItems(str(_key), Qt.MatchExactly | Qt.MatchRecursive, 0)  # MatchExactly
            if ls_item:
                value = ls_item[0].index().siblingAtColumn(1).data()
                if get_str_lower_nospace(_value) != get_str_lower_nospace(value):
                    model.setData(item_value.index(), QtGui.QBrush(QtGui.QColor(255, 0, 0)), Qt.ForegroundRole)
                    trview_identity.model().setData(ls_item[0].index(), QtGui.QBrush(QtGui.QColor(255, 0, 0)), Qt.ForegroundRole)                
        elif _key == "synonyms":
            _key = "Synonyms"
            item_key = QtGui.QStandardItem(_key)
            item_base.appendRow([item_key])
            try:
                for syno in _value:
                    item_value = QtGui.QStandardItem(syno)
                    item_key.appendRow([None, item_value],)
            except:
                pass
    trview_metadata.expand(item_base.index())







### MANAGE buttons
def set_enabled_buttons():
    # manage the availability of the buttons
    button_add.setEnabled(False)
    button_edit.setEnabled(False)
    button_del.setEnabled(False)
   # button_moveChilds.setEnabled(False)
    button_mergeChilds.setEnabled(False)
    button_addNames.setEnabled(False)
    button_editChilds.setEnabled(False)
    button_delChilds.setEnabled(False)
    rank_msg.setText('< no selection >')
    window.toolBox.setItemText(0, rank_msg.text())

    # check if a taxa is selected
    selected_taxa = tlview_taxonref.model().data(
        tlview_taxonref.currentIndex(), Qt.UserRole)
    if selected_taxa is None:
        return
    elif selected_taxa.idtaxonref == 0:
        return
    rank_msg.setText(selected_taxa.rank_name + " : " + selected_taxa.taxonref)
    window.toolBox.setItemText(0, selected_taxa.rank_name)
    button_add.setEnabled(True)

    # check if a synonym is selected
    try:
        value = tlview_similar.model().data(tlview_similar.currentIndex(), Qt.UserRole) is not None
    except Exception:
        value = False
    button_edit.setEnabled(value)
    button_del.setEnabled(value)

    # check if a childs item is selected
    id_taxonref = None
    #id_rank = 0
    try:
        id_taxonref = int(trView_childs.currentIndex().siblingAtColumn(2).data())
        #id_rank = int(trView_childs.currentIndex().siblingAtColumn(3).data())
    except Exception:
        pass
    value = id_taxonref is not None
        #value = (tlview_taxonref.currentIndex().data() != None)
    #button_moveChilds.setEnabled(value and id_rank<=14)  # id_rank < 21)
    button_mergeChilds.setEnabled(value)
    button_addNames.setEnabled(value)
    button_delChilds.setEnabled(value)
    button_editChilds.setEnabled(value)



def button_identity_apply_click():
    buttonbox_identity.setEnabled(False)
    trview_identity_apply()

def button_identity_cancel_click():
# message to be display first (question, Yes or Not)
    msg = "Are you sure you want to undo all changes and restore from the database ?"
    result = QMessageBox.question(
        None, "Cancel properties", msg, QMessageBox.Yes, QMessageBox.No)
    if result == QMessageBox.No:
        return
    PN_trview_identity.refresh()






def button_addSynonyms_click():
    return    
    selecteditem = tlview_taxonref.model().data(
            tlview_taxonref.currentIndex(), Qt.UserRole)
    if selecteditem is None : return
    print (API_ENDEMIA(selecteditem).get_synonyms())


    tab_synonyms = []
    tab_synonyms += API_TAXREF(selecteditem).get_synonyms()
    tab_synonyms += API_FLORICAL(selecteditem).get_synonyms()
    #print (tab_synonyms)
    #manage synonyms
    #tab_synonyms =[]
    sql_insert = "SELECT taxonomy.pn_taxa_edit_synonym ('_synonymstr','Taxinomic'," +str( selecteditem.id_taxonref) + ")"
    tab_syno = []
    for taxa in tab_synonyms:
        for taxon in get_dict_from_species(taxa)["names"]:
            tab_syno.append(taxon)
    #to eliminate duplicate
    tab_syno = list(set(tab_syno))  
    #execute the query to add new synonyms, continue if errors (e.g. duplicate)
    for synonym in tab_syno:
        sql_query = sql_insert.replace('_synonymstr', str(synonym))
        #print (sql_query)
        try:
            query = QtSql.QSqlQuery()
            query.exec(sql_query)
        except:
            continue
    tlview_similar_setData(selecteditem)



def button_MoveChilds_click():
    try:
        selecteditem = trView_childs.selecteditem()
        win = PN_move_taxaname(selecteditem, False)
        win.show()
        if win.updated:
            # update the sub-taxas properties
            for item in win.updated_datas:
                tlview_taxonref.model().sourceModel().refresh(item)
           # refresh the view
            tlview_refresh(selecteditem.idtaxonref)
    except:
        return


def button_addChilds_click():
    #selecteditem = tlview_taxonref.model().data(tlview_taxonref.currentIndex(), Qt.UserRole)
    try:
        row_index = tlview_taxonref.currentIndex()
        selecteditem = tlview_taxonref.model().data(row_index, Qt.UserRole)
        # int(trView_childs.currentIndex().siblingAtColumn(2).data())
        id_taxonref = selecteditem.idtaxonref
        win = PN_edit_taxaname(id_taxonref, 1)
        win.show()

        if win.updated:
            for item in win.updated_datas:
                # refresh the data
                tlview_taxonref.model().sourceModel().refresh(item)

           # refresh the view
            tlview_refresh(id_taxonref)
    except:
        return


def button_clean_click():
    combo_taxa.setCurrentIndex(0)
    combo_rank.setCurrentIndex(0)
    combo_statut.setCurrentIndex(0)
    combo_habit.setCurrentIndex(0)
    lineEdit_search.setText('')
    tlview_taxonref_setData()

def button_WebPage_click():
    item = trview_metadata.currentIndex()
    while item.parent().isValid():
        item = item.parent()
    url = item.siblingAtColumn(2).data()
    try:
        webbrowser.open(url)
    except:
        return


def button_metadata_refresh():
    selecteditem = tlview_taxonref.model().data(
        tlview_taxonref.currentIndex(), Qt.UserRole)
    
    if metadata_worker.status == 1:
        metadata_worker.kill()
        while metadata_worker.isRunning():
            time.sleep(0.5)
    # QApplication.setOverrideCursor(Qt.WaitCursor)
    trview_metadata.model().setRowCount(0)
    #tlview_links.model().setRowCount(0)
    selecteditem.api_score =0
    metadata_worker.PNTaxa_model = selecteditem
    metadata_worker.start()
    tlview_taxonref.repaint()


def button_add_synonym():
    # get the selectedItem
    selecteditem = tlview_taxonref.model().data(
        tlview_taxonref.currentIndex(), Qt.UserRole)
    if selecteditem.idtaxonref == 0:
        return
    new_synonym = PNSynonym('', selecteditem.taxonref, selecteditem.idtaxonref)


    class_newname = PN_edit_synonym(new_synonym)
    class_newname.show()


def button_edit_synonym():
    # get the selectedItem
    selecteditem = tlview_similar.model().data(
        tlview_similar.currentIndex(), Qt.UserRole)
    if tlview_similar.currentIndex().data() is None:
        return
    selecteditem.id_synonym = 1
    class_newname = PN_edit_synonym(selecteditem)
    class_newname.show()


def button_delete_synonym():
    selecteditem = tlview_similar.model().data(
        tlview_similar.currentIndex(), Qt.UserRole)
    if tlview_similar.currentIndex().data() is None:
        return
    # message to be display first (question, Yes or Not)
    msg = "Are you sure to permanently delete this synonym " + selecteditem.synonym + "?"
    result = QMessageBox.question(
        None, "Delete a synonym", msg, QMessageBox.Yes, QMessageBox.No)
    if result == QMessageBox.No:
        return
        # execute the suppression
    sql_query = sql_taxa_delete_synonym(selecteditem.synonym)
    result = QtSql.QSqlQuery(sql_query)
    if len(result.lastError().nativeErrorCode()) == 0:
        tlview_similar_setData(selecteditem)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = uic.loadUi("pn_main.ui")

# connection to the database
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")

    if not createConnection(db):
        sys.exit("error")

# setting the main_tableView
    model_tableview = TableModel()
    proxyModel = QSortFilterProxyModel()
    proxyModel.setSourceModel(model_tableview)
    tlview_taxonref = window.main_tableView
    tlview_taxonref.setModel(proxyModel)
    tlview_taxonref.setSortingEnabled(True)
    tlview_taxonref.sortByColumn(0, Qt.AscendingOrder)
    selection = tlview_taxonref.selectionModel()
    selection.selectionChanged.connect(tlview_taxonref_click)
    tlview_taxonref.doubleClicked.connect(tlview_taxonref_dblclick)
    selection.currentChanged.connect(tlview_taxonref_before_clickitem)
    

# setting the similar tableview
    tlview_similar = window.tableview_names
    model = TableSimilarNameModel()
    proxyModel = QSortFilterProxyModel()
    proxyModel.setSourceModel(model)
    tlview_similar.setModel(proxyModel)

    trview_identity = window.tableview_identity
    trview_traits = window.trview_traits
    
    trView_childs = PN_taxa_hierarchy () ##window.treeView_childs
    trView_childs.doubleClicked.connect(trView_childs_dblclick)
    window.trView_childs_Layout.insertWidget(0,trView_childs)

    #widget.setLayout(layout)

    #window.tabWidget_2.widget(0).layout().addWidget(widget)



    trview_metadata = window.treeView_metadata
    tlview_occurrences = window.tableView_occ

# setting the combo
    combo_taxa = window.combo_taxa
    #ls_statut =['Any status', 'Endemic', 'Autochton','Unknown']
    combo_taxa_data = []
    combo_taxa_data.append(PNTaxa(0, 'Any taxa', '', 0))
    combo_taxa.addItem('Any taxa')
    combo_taxa.setCurrentIndex(0)
    combo_taxa.currentIndexChanged.connect(tlview_taxonref_setData)

    combo_statut = window.combo_statut
    combo_habit = window.combo_habit

    combo_rank = window.combo_rank
    dict_rank = {'Any rank': 0, 'Classis' : 6, 'Subclassis' : 7, 'Order': 8, 'Family': 10, 'Genus': 14,
                 'Species': 21, 'Subspecies': 22, 'Variety': 23, 'Hybrid': 31}
    for x in dict_rank.keys():
        combo_rank.addItem(x)
    combo_rank.activated.connect(tlview_taxonref_setData)

    combo_statut.addItem("Any status")
    for x in dict_nc["statut"]:
        combo_statut.addItem(x)
    combo_statut.addItem("Unknown")
    combo_statut.activated.connect(tlview_taxonref_setData)
    
    combo_habit.addItem("Any habit")
    for x in dict_habit.keys():
        combo_habit.addItem(x.title())
    combo_habit.addItem("Unknown")
    combo_habit.activated.connect(tlview_taxonref_setData)

# setting the buttons
 
    window.pushButtonRefresh.clicked.connect(button_metadata_refresh)
    window.button_clean.clicked.connect(button_clean_click)    
    window.pushButton_view.clicked.connect(button_WebPage_click)
    
   #button_find = window.push_button1
    button_add = window.pushButtonAdd
    button_add.clicked.connect(button_add_synonym)

    button_edit = window.pushButtonEdit
    button_edit.clicked.connect(button_edit_synonym)

    button_del = window.pushButtonDel
    button_del.clicked.connect(button_delete_synonym)

 
    button_addNames = window.pushButtonSearchChilds
    button_addNames.clicked.connect(button_addNames_click)   
    
    button_editChilds = window.pushButtonEditChilds
    button_editChilds.clicked.connect(button_editChilds_click)

    button_delChilds = window.pushButtonDelChilds
    button_delChilds.clicked.connect(button_DelChilds_click)
 
    button_mergeChilds = window.pushButtonMergeChilds
    button_mergeChilds.clicked.connect(button_MergeChilds_click)

    button_moveChilds = window.pushButtonMoveChilds
    button_moveChilds.clicked.connect(button_MoveChilds_click)

    # button_addChilds = window.pushButtonAddChilds
    # button_addChilds.clicked.connect(button_addChilds_click)

    


    # button_addSynonyms = window.pushButtonSearchNames
    # button_addSynonyms
    #window.pushButtonSearchNames.clicked.connect(button_addSynonyms_click)
    
    buttonbox_identity = window.buttonBox_identity
    button_cancel = buttonbox_identity.button(QDialogButtonBox.Cancel)
    button_cancel.clicked.connect (button_identity_cancel_click)
    button_apply = buttonbox_identity.button(QDialogButtonBox.Apply)
    button_apply.clicked.connect(button_identity_apply_click)

    lineEdit_search = window.lineEdit_search
    lineEdit_search.returnPressed.connect(tlview_taxonref_setData)

    tab_data = window.tabWidget_2
    tab_data.currentChanged.connect(tab_data_changed)

    window.toolBox.setItemText(0, "< no selection >")
    window.toolBox.setItemIcon(0, window.style().standardIcon(51))
    window.toolBox.setItemIcon(1, window.style().standardIcon(53))
    window.toolBox.currentChanged.connect(toolbox_click)   
    


    rank_msg = QLabel()
    rank_msg.setGeometry(100, 40, 30, 25)
    rank_msg.setVisible(True)
    window.statusbar.addPermanentWidget(rank_msg)

    tlview_taxonref_setData()
    
    window.show()
#initialise classes 

   # window.toolBox.click.connect(toolbox_click)

    PN_trview_identity = PN_taxa_identity (trview_identity)
    PN_tlview_traits = PN_taxa_identity (trview_traits)
    PN_trview_identity.changed_signal.connect(trview_identity_changed)
    metadata_worker = TaxRefThread(app)
    metadata_worker.Result_Signal.connect(trview_metadata_setDataAPI)   

    
  
    with open("Diffnes.qss", "r") as f:
    #with open("Adaptic.qss", "r") as f:
    #with open("Photoxo.qss", "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)

    sys.exit(app.exec_())

