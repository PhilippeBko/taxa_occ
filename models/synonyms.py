from PyQt5 import QtWidgets, QtSql, uic, QtCore
from core.widgets import PN_TaxaSearch
import core.functions as commons

class PNSynonym(object):
    def __init__(self, synonym = None, taxonref = None, idtaxonref = 0, category = 'Orthographic'):
        self.synonym = synonym
        self.category = category
        self.taxon_ref = taxonref
        self.id_taxonref = idtaxonref
        self.keyname =''

    @property
    def idtaxonref(self):
        try:
            return int(self.id_taxonref)
        except Exception:
            return 0

    @property
    def resolved(self):
        #return True if idtaxonref>0 
        return self.idtaxonref > 0  
    
#####################
#Class to edit(New or update) synonym
# add/update a new synonym to a idtaxonref or search for a idtaxonref (PN_TaxaSearch) according to a synonym 
class PN_edit_synonym (QtWidgets.QWidget):
    button_click = QtCore.pyqtSignal(object, int)
    def __init__(self, myPNSynonym):

        super().__init__()
        self.ui_addname = uic.loadUi("ui/pn_editname.ui")
        self.Qline_name = self.ui_addname.name_linedit
        self.Qline_ref = self.ui_addname.taxaLineEdit
        self.Qcombobox = self.ui_addname.comboBox
        buttonbox = self.ui_addname.buttonBox
        self.button_cancel = buttonbox.button(QtWidgets.QDialogButtonBox.Cancel)
        self.button_ok = buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        self.myPNSynonym = myPNSynonym
        self.treeview_searchtaxa = PN_TaxaSearch()
        self.is_new = (self.myPNSynonym.synonym is None or self.myPNSynonym.idtaxonref == 0)


    def setting_ui(self):
        self.updated = False
        self.Qline_name.setReadOnly(not self.myPNSynonym.resolved)
        self.Qline_name.setText('') 
        self.ui_addname.setMaximumHeight(500)
        self.ui_addname.resize(500,500)
        self.Qcombobox.setCurrentText(str(self.myPNSynonym.category))
        self.Qline_name.setText(self.myPNSynonym.synonym)
        #resolved depends if idtaxonref is Null
        if not self.myPNSynonym.resolved:
            self.ui_addname.label_tip.setText('Select Reference...')
            #add the treeview_searchtaxa = Class PN_TaxaSearch() (cf. taxa_model.py)
            layout = self.ui_addname.QTreeViewSearch_layout
            layout.addWidget(self.treeview_searchtaxa)
            self.treeview_searchtaxa.setText(self.myPNSynonym.synonym)
            self.treeview_searchtaxa.selectionChanged.connect(self.valid_newname)
        else: #idtaxonref is not Null
            if self.is_new:
                self.ui_addname.label_tip.setText('New Synonym...')
            else:
                self.ui_addname.label_tip.setText('Edit Synonym...')
            self.Qline_ref.setText(self.myPNSynonym.taxon_ref)
            self.ui_addname.setMaximumHeight(1)
            self.Qline_name.setFocus()
        self.Qline_name.textChanged.connect (self.valid_newname)
        self.Qcombobox.activated.connect(self.valid_newname)
        self.button_ok.clicked.connect (self.accept) 
        self.button_cancel.clicked.connect (self.close)
        self.valid_newname()

    def show(self):
        self.setting_ui()
        self.ui_addname.show()
        self.ui_addname.exec()
        
    def close(self):
        self.ui_addname.close()

    def valid_newname(self):
        txt_item = self.Qline_name.text().strip()
        txt_category = self.Qcombobox.currentText().strip()         
        flag = False
        if len(txt_item)>3:
            if self.myPNSynonym.resolved:
                flag = not (self.myPNSynonym.synonym == txt_item and self.myPNSynonym.category == txt_category)
            else:
                new_taxonref = self.treeview_searchtaxa.selectedTaxonRef()
                flag = new_taxonref is not None
                self.Qline_ref.setText(new_taxonref)
        self.button_ok.setEnabled(flag)

    def accept(self):
        self.updated = False
        new_synonym = self.Qline_name.text().strip()
        new_category = self.Qcombobox.currentText()
        new_taxonref = self.Qline_ref.text().strip()
        #is_new = True
        if self.myPNSynonym.resolved:
            idtaxonref = self.myPNSynonym.idtaxonref
            #is_new = (self.myPNSynonym.synonym is None)
        else:
            try :
                idtaxonref = int(self.treeview_searchtaxa.selectedTaxaId())
            except Exception:
                idtaxonref = 0
        if idtaxonref == 0:
            return
        if self.is_new:
            #add mode
            sql_query = f"SELECT taxonomy.pn_names_add ('{new_synonym}','{new_category}', '{idtaxonref}')"
        else:
            #edit mode
            #return if nothing has changed
            if new_synonym == self.myPNSynonym.synonym and new_category == self.myPNSynonym.category:
                self.ui_addname.close()
                return True
            sql_query = f"SELECT taxonomy.pn_names_update ('{self.myPNSynonym.synonym}','{new_synonym}', '{new_category}')"
        #execute query
        result = QtSql.QSqlQuery (sql_query)
        #check for errors code (cf. postgresql function taxonomy.pn_taxa_edit_synonym)
        code_error = result.lastError().nativeErrorCode ()
        msg = ''
        if len(code_error) == 0:
            self.myPNSynonym.synonym = new_synonym
            self.myPNSynonym.category = new_category
            self.myPNSynonym.taxon_ref = new_taxonref                                    
            self.myPNSynonym.id_taxonref = idtaxonref
            self.ui_addname.close()
            self.updated = True
            return True
        else:
            msg = commons.postgres_error(result.lastError())
        QtWidgets.QMessageBox.critical(self.ui_addname, "Database error", msg, QtWidgets.QMessageBox.Ok)
        return False


