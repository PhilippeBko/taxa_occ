import sys

from PyQt5 import QtCore, QtGui, QtWidgets, QtSql
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeView, QTableView

import numpy as np
import matplotlib.pyplot as plt
from cartopy import crs as ccrs, feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

from commons import get_str_value, list_db_traits, get_column_type, list_db_fields
#from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class PN_occ_model(QtCore.QAbstractTableModel):
#to manage a specific model for display data as a list
# include red/green dots considering the last field of the list as boolean (green if True)
# include a specific font attributes for columns include in header_filtered
# receive a list (data) 
    def __init__(self, data = None):
        super(PN_occ_model, self).__init__()
        self._data = []
        self._data = data if data is not None else []
        self.header_labels = []
        self.header_filtered = []

    def getdata(self, with_header = False):
    #get data, ingore the last field (= valid)
        data = []
        if with_header:
            data.append(self.header_labels[:-1])
        for row in self._data:
            data.append([get_str_value(item) for item in row[:-1]])
        return data
    
    def resetdata(self, newdata = None):
        self.beginResetModel()
        self._data = newdata if newdata is not None else []
        self.endResetModel()

    def headerData(self, section, orientation = Qt.Horizontal, role = Qt.DisplayRole):
        if len(self.header_labels) == 0:
            return
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return  self.header_labels[section]
        #change font attributes if a field is include in header_filtered
        if role == Qt.FontRole and orientation == Qt.Horizontal:
            if section in self.header_filtered:
                f = QtGui.QFont()
                f.setBold(True)
                f.setUnderline(True)
                f.setItalic(True)
                return f

    def data(self, index, role):
        if not index.isValid():
            return None
        if 0 <= index.row() < self.rowCount():
            item = self._data[index.row()]
            col = index.column()
            if role == Qt.DisplayRole:
                    return self._data[index.row()][index.column()]
            elif role == Qt.UserRole:
                return item
            elif role == Qt.DecorationRole:
                if col == 0:
                    #idtaxonref = getattr(item, 'stid_taxon_ref', 0)
                    colour = QtGui.QColor(255,0,0,255)
                    if self._data[index.row()][self.columnCount()]:
                        colour = QtGui.QColor(0,255,0,255)
                    px = QtGui.QPixmap(13,13)
                    px.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(px)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    px_size = px.rect().adjusted(2,2,-2,-2)
                    painter.setBrush(colour)
                    painter.setPen(QtGui.QPen(QtCore.Qt.black, 1,
                        QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    #painter.drawEllipse(px_size)
                    painter.drawRect(px_size)
                    painter.end()
                    return QtGui.QIcon(px)

    def rowCount(self, index=QtCore.QModelIndex()):
        return len(self._data)

    def columnCount(self, index=QtCore.QModelIndex()):
        try:
            return len(self._data[0])-1
        except Exception:
            return 0
        
    # def addItem (self, clrowtable):
    #     self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
    #     self._data.append(clrowtable)
    #     self.endInsertRows()


#########################################################################################################
class PN_occ_explore():
# a class to explore data through two majors function, get_figures (retunr figure) and get_traits (return JSON)
# work alone from a standardized table produced by a class PN_occ_tables (function sql_staked_data)
 
    def __init__(self):
        super().__init__()
        self.figure_min = None
        self.figure_max = None
        self.figure_mean = None
        self.figure_median = None
        self.tabletoExplore = None   
        self._sql_propertiesFilter = ''
        self._sql_taxaFilter = ''
        self.fieldTraits = None
        self.dbfields = {}
        self.graphTypes = None
        self.sql_traits = ''
        self.fields_toUse = None
        #self.mv_lastupdate = None
        #self.fieldList = None
        #self.searchtaxa = None
        #self.taxas = None
        #self.canvas = FigureCanvas(plt.figure())

            
    def load (self, tabtoexplore):
#load the tabletoexplore, extract the field list, the figure list and the taxas
    #load the fields list
        self.tabletoExplore = tabtoexplore
        sql_query = "SELECT * FROM " + self.tabletoExplore + " LIMIT 1"
        query = QtSql.QSqlQuery (sql_query)
        record = query.record()
    #set the field type        
        self.fieldTraits = []
        self.dbfields = {}
        for i in range(record.count()):
            _field = {}
            if record.field(i).type() in [2,3,6]:
                _field["type"] = 'numeric'
            else:
                _field["type"] = 'text'                
            self.dbfields[record.fieldName(i)] = _field
    #load the available figure_type list
        fields_order = ['summary', 'location', 'phenology', 'family', 'genus', 'species', 'infra', 'taxaname']
        fields_order += list(list_db_traits.keys())
        tab_fields = ['summary', 'family', 'genus', 'species', 'infra', 'taxaname']
        if "longitude" in self.dbfields and "latitude" in self.dbfields :
                tab_fields.append('location')
                self.fieldTraits.append('location')
        if "phenology" in self.dbfields and "month" in self.dbfields :
                tab_fields.append('phenology')
                self.fieldTraits.append('phenology')       
    #add others fields from db_traits
        for field in list_db_traits.keys():
            if field in self.dbfields:
                tab_fields.append(field)
                self.fieldTraits.append(field)
    #sort graphTypes
        self.graphTypes = []
        for field in fields_order:
            if field in tab_fields:
                self.graphTypes.append(field)

    
    
    def set_taxafilter(self, rankname, ls_taxa_filters):
#set the taxa filter according to a list (ex rankname = 'family' and  ls_taxa_filters = ['Sapotaceae', 'Meliaceae'])
        self._sql_taxaFilter = ''
        if len(ls_taxa_filters) > 0:
            sql_idtaxa = "id_" + rankname.lower()
            sql_idtaxa += " IN (SELECT id_taxonref FROM taxonomy.pn_taxa_searchnames(ARRAY __SEARCHTAXA__) WHERE id_taxonref IS NOT NULL)"
            self._sql_taxaFilter = sql_idtaxa.replace ("__SEARCHTAXA__", str(ls_taxa_filters))


    def set_propertiesfilter(self, ls_taxa_properties:list, exclusive = False):
#set the filter on taxa properties according to the list 'ls_taxa_properties', add exclusive search if true (all criteria)
    # ex: ls_taxa_properties = [['Habit', ['Tree']], ['New caledonia', 'Statut', ['Endemic', 'Introduced']]]
        self._sql_propertiesFilter = ''
        ncount = 0
        sql_filter =''
        _tmp =[]
        sql_taxa_properties = ''
    #count the number of filter
        ncount = len(ls_taxa_properties)        
        #return '' if no filter ls_taxa_properties is null
        if ncount == 0:
            return ''

        #create sql criteria from the list
        for tab_query in ls_taxa_properties:
            sql = "lower(cat) = '" + tab_query[0].lower() +"' AND "

            #the last item is a list (transforme list in sql IN)
            items_selected = tab_query[-1]
            items_list_sql = str([x.lower() for x in items_selected])
            items_list_sql = items_list_sql.replace("[", "(")
            items_list_sql = items_list_sql.replace("]", ")")
            
            #the second is either a text or the list
            item = tab_query[1]
            if isinstance(item, str): 
                sql += "lower(key) = '" + item.lower() +"' AND lower(value) IN __list__"
               # sql += f"lower(key) = '{item.lower()}' AND lower(value) IN {items_list_sql}"
            else:
                sql += "lower(key) IN __list__ AND lower(value) = 'true'"
            #finalize the query
            sql = sql.replace("__list__", items_list_sql)
            sql = "(" + sql + ")"
            #add to the tab
            _tmp.append (sql)
        #join by OR any sql criteria 
        op = "\nOR\n"
        sql_taxa_properties = op.join (_tmp)
        sql_taxa_properties = get_str_value(sql_taxa_properties)
        #create the standard sql gabarit to search for properties
        sql_filter = """
        WITH 
            taxa_properties AS (
            SELECT id_taxonref, key AS cat, (jsonb_each_text(value)).*
                FROM (SELECT id_taxonref, (jsonb_each(properties)).* FROM taxonomy.taxa_reference) a
            ),
            selected_taxa AS (
                SELECT id_taxonref 
                FROM (SELECT id_taxonref, count(id_taxonref) AS ncount
                FROM taxa_properties
                WHERE (__TAXAFILTER__)
                GROUP BY id_taxonref) z
                WHERE z.ncount >=1
            )
        """
        #if exclusive (all categories must me satisfied), number of properties must be equal to the number of criteria
        # in theory (z.ncount = ncount) but in practice (z.ncount >= ncount) is quicker
        if exclusive and ncount > 1:
            sql_filter = sql_filter.replace ("WHERE z.ncount >=1", "WHERE z.ncount >=" + str(ncount))
        sql_filter = sql_filter.replace ("__TAXAFILTER__", sql_taxa_properties)
        self._sql_propertiesFilter = sql_filter
        return sql_filter


    def get_sql_traits(self, rankname = 'family', function = 'count', alltaxa = False):
#return the list of traits according to rankname and a function...extend to all data with or without occurrences if alltaxa = True
    #add eventually taxafilter if present
        dict_translate = {'count': 'count', 'median':'median', 'minimum':'min','maximum' : 'max', 'average' : 'avg', 'standard deviation': 'stddev'}
        function = dict_translate[function.lower()]
        
        #create the SQL query gabarit
        self.sql_traits = ''
        sql_gabarit = """
        SELECT 
            __TRAITS__

        FROM taxonomy.taxa_hierarchy a
        __JOINTER_TYPE__ __TABLETOEXPLORE__ b ON a.id_taxonref = b.id_taxonref
        INNER JOIN taxonomy.taxa_names c ON a.id___RANKNAME__ = c.id_taxonref
        __JOINTER_FILTER__

        WHERE c.taxaname IS NOT NULL
        GROUP BY __RANKNAME__
        ORDER BY __RANKNAME__
        """
        
        #create the SELECT for any traits
        _tmp = ["count(DISTINCT dataset)::integer AS dataset", "count(id)::integer AS occurrences"]
        #_tmp = ["count(dataset)::integer AS dataset"]
        for trait in self.fieldTraits:
            _sql =''
            if trait == "location":
                _sql = "count(longitude) FILTER (WHERE latitude IS NOT NULL) ::integer"
            elif trait == "phenology":
                _sql = "count(phenology) FILTER (WHERE month IS NOT NULL) ::integer"
            elif function == "count":
                _sql = "count(" + trait + ")::integer"
            elif self.dbfields[trait]["type"] == 'numeric':
                if function == 'median':
                    _sql = "percentile_cont(0.50) WITHIN GROUP (ORDER BY " + trait +" ASC)::numeric(6,2)"
                else:
                    _sql = function + "(" + trait + ")::numeric (6,2)"
            else:
                _sql = "NULL::integer"
            _sql += " AS " + trait
            _tmp.append(_sql)

        #replace the gabarit terms by value            
        traits2 = "c.taxaname AS " +rankname
        if len(_tmp) > 0:
            traits2 += ",\n\t\t" + ",\n\t\t".join(_tmp)
        sql_gabarit = sql_gabarit.replace ("__TRAITS__", traits2)    
        sql_gabarit = sql_gabarit.replace ("__RANKNAME__", rankname)
        sql_gabarit = sql_gabarit.replace ("__TABLETOEXPLORE__", self.tabletoExplore)

        #alter the jointer according to the tag alltaxa
        if alltaxa:
            sql_gabarit = sql_gabarit.replace ("__JOINTER_TYPE__", "LEFT JOIN")
        else:
            sql_gabarit = sql_gabarit.replace ("__JOINTER_TYPE__", "INNER JOIN")

        #add taxa filter (properties)
        if len(get_str_value(self._sql_propertiesFilter)) == 0:
            sql_gabarit = sql_gabarit.replace ("__JOINTER_FILTER__", "")
        else:
            sql_gabarit = sql_gabarit.replace ("__JOINTER_FILTER__", "INNER JOIN selected_taxa d ON d.id_taxonref = a.id_taxonref")
            sql_gabarit = self._sql_propertiesFilter + sql_gabarit

        #save the sql_gabarit
        self.sql_traits = sql_gabarit
        return (sql_gabarit)
    

    def get_taxa_properties(self):
#return a dictionnary (json) with taxa properties with count by species and by occurrences
        #def _sql_properties ():
        sql_gabarit = f"""
        WITH 
            taxa_properties AS (
            SELECT id_taxonref, key AS cat, (jsonb_each_text(value)).*
                FROM (SELECT id_taxonref, (jsonb_each(properties)).* FROM taxonomy.taxa_reference) a
            ),
            count_properties AS (
                SELECT 
                    cat, key, value,
                    count(a.id_taxonref)::integer as count,
                    count(DISTINCT a.id_taxonref)::integer as count_species
                FROM 
                    {self.tabletoExplore} a 
                INNER JOIN
                    taxa_properties b
                ON a.id_taxonref = b.id_taxonref
                WHERE value <>'False'
                GROUP BY b.cat, b.key, value
                ORDER BY b.cat, b.key, value            
            )
        SELECT * FROM count_properties
        """
        #sql_gabarit = sql_gabarit.replace ("__TABLETOEXPLORE__", self.tabletoExplore)
        tab_traits = {}
        #get table of traits from taxa
        query = QtSql.QSqlQuery (sql_gabarit)
        while query.next():
            tab_trait = {}
            #check for the category
            try:
                tab_trait = tab_traits[query.value("cat")]
            except Exception:
                tab_traits[query.value("cat")] = {}
            #check for the key
            try:
                tab_trait = tab_trait[query.value("key")]
            except Exception:
                tab_traits[query.value("cat")][query.value("key")] = {}
            #case, if value = True then affected to the key
            if query.value("value") == 'True':
                tab_traits[query.value("cat")][query.value("key")] = [query.value("count_species"), query.value("count")]
            else : #else affected a sub category with value
                tab_trait = tab_traits[query.value("cat")][query.value("key")]
                tab_trait[query.value("value")] = [query.value("count_species"), query.value("count")]
                tab_traits[query.value("cat")][query.value("key")] = tab_trait
        return (tab_traits)
    

    def get_figure(self, figure, graphType ='summary', min = None, max = None):
#return the figure related to the table and the selected graphType
    #initialize parameters
        sql_gabarit = ''
        _taxafilter = ''
        self.figure_min = None
        self.figure_max = None
        data = []
        labels = []
        _tmp = []
        table_size = 0
        plt.close('all')
        figure.clear()
        xlabel = ''
        ylabel = ''
        table_size == 0
        ax1_color = 'darkgreen'
        ax2_color = 'royalblue'
        ax1_alpha = 0.8
        ax2_alpha = 0.5
        ax1_fontsize = 8

    #check for validity
        if graphType is None : 
            return
        if len(graphType)==0 : 
            return
        if graphType not in self.graphTypes: 
            return
        if self.tabletoExplore is None:
            return
    
    # create the sql_gabarit
        sql_gabarit =  """ 
            stacked_datas AS (
                SELECT a.id_family, a.id_genus, a.id_species, a.id_infra, a.id_rank, a.taxonref,
                b.*
                FROM taxonomy.taxa_hierarchy a
                INNER JOIN __TABLETOEXPLORE__ b ON a.id_taxonref = b.id_taxonref
                __TAXAFILTER__
            )
        """

    #Check for filters on properties
        if len(get_str_value(self._sql_propertiesFilter)) == 0:
            sql_gabarit = "WITH " + sql_gabarit
        else:
            _taxafilter = "INNER JOIN selected_taxa d ON d.id_taxonref = a.id_taxonref"
            sql_gabarit = self._sql_propertiesFilter + ', ' + sql_gabarit
    #Check for filters on name
        if len(get_str_value(self._sql_taxaFilter)) > 0:
            _taxafilter += "\n\tWHERE " + self._sql_taxaFilter
        #fill the sql_gabarit
        sql_gabarit = sql_gabarit.replace("__TABLETOEXPLORE__", self.tabletoExplore)
        sql_gabarit = sql_gabarit.replace("__TAXAFILTER__", _taxafilter)

    #get with query (prefix)
        sql_query = sql_gabarit
       # print (sql_query)
        #ax = figure.add_subplot(111)
    #select plot type according to the graphType
        if graphType == "location":
            xlabel = "Longitude"
            ylabel = "Latitude"           
            # sql_query += "\nSELECT (location).latitude, (location).longitude FROM stacked_datas WHERE location IS NOT NULL"
            # sql_query += "\n GROUP BY location"
            sql_query += "\nSELECT longitude, latitude FROM stacked_datas WHERE longitude IS NOT NULL and latitude IS NOT NULL"
            sql_query += "\n GROUP BY longitude, latitude"
            #print (sql_query)
            query = QtSql.QSqlQuery (sql_query) 
            while query.next():
                data.append(query.value("latitude"))
                labels.append(query.value("longitude")) 
                        
            table_size = query.size()
            if len(data) == 0 : 
                return

            #draw the plot
            ax = figure.add_subplot(111, projection=ccrs.PlateCarree())
            #ax.set_transform (ccrs.PlateCarree())
            #read a local image
                # img = plt.imread('ressources/color_etopo1_ice_low_resultat.png')
                # img_extent = (-180, 180, -90, 90)           
                # ax.imshow(img, origin='upper', extent=img_extent, transform=ccrs.PlateCarree())
            #OR read costal vectoriel
                #ax.set_global()
                #ax.stock_img()
                #ax.coastlines(color="grey", linewidth=0.3, resolution ='110m')
            #OR read online feature (more accurated)
            ax.add_feature(cfeature.COASTLINE, linewidth = 0.2)
            ax.add_feature(cfeature.LAND,color = "khaki", alpha = ax2_alpha) #color='#acbd48')        
            #plot the data
            ax.scatter(labels,data, color = ax2_color, s=0.6)
            #fix map extent and label frequency
            ax.set_extent([np.min (labels)-1, np.max (labels)+1, np.min (data)-1, np.max (data)+1])
            ax_extent = ax.get_extent()
            ax.set_xticks(np.arange(ax_extent[0], ax_extent[1]+1, (ax_extent[1]-ax_extent[0])/5))
            ax.set_yticks(np.arange(ax_extent[2], ax_extent[3]+1, (ax_extent[3]-ax_extent[2])/5))
            #format the map with grid and axes in Long/lat coordinates
            ax.gridlines(color="black", linestyle='dashed', linewidth=0.1)
            lon_formatter = LongitudeFormatter(number_format='.1f', degree_symbol='°') #, dateline_direction_label=True)
            lat_formatter = LatitudeFormatter(number_format='.1f', degree_symbol='°')                 
            ax.xaxis.set_major_formatter(lon_formatter)
            ax.yaxis.set_major_formatter(lat_formatter)
    #create a horizontal bar with a summary of any data
        elif graphType == 'summary':
            xlabel = 'Occurrences'
        #create the horizontal histogram to synthetize the table contents (% of summary => rate of dbh values)
        #create a query to get rowcount for any traits
            #get the list of display field (via cb_fields)
            #load the data
            # ls_output = ['taxaname','family', 'genus', 'species']
            # ls_output = []
            sql_query += "\nSELECT count(id) ::integer AS count, __TRAITS__ \nFROM stacked_datas"
            ls_traits = '' #list(list_db_traits.keys())
            _tmp = []
            #_tmp.append("count(id_family)::integer AS family")
            for trait in self.graphTypes[1:]:
                if trait == 'location':
                     _tmp.append("count(longitude) FILTER (WHERE latitude IS NOT NULL)::integer AS " + trait)
                elif trait == 'phenology':
                    _tmp.append("count(phenology) FILTER (WHERE month IS NOT NULL) ::integer AS " + trait)
                elif trait in self.fieldTraits:
                    _tmp.append("count(" + trait + ") ::integer AS " + trait)
                else:
                    continue
                #ls_output += [trait]
            if len(_tmp) == 0: 
                return
        #fill the sql_gabarit
            ls_traits = ",\n".join(_tmp)
            sql_query = sql_query.replace("__TRAITS__", ls_traits)
            
        #query the sql, value and record
            query = QtSql.QSqlQuery (sql_query)
            query.next()
            rec = query.record()    

            #get the total number of occurrences
            table_size = query.value("count")
            if table_size == 0 : 
                return

            #create the dataset (data) for any datas and (data_overlap) for any referenced field that will overlap the dataset
            labels = [get_str_value(rec.fieldName(x)).capitalize().replace("_"," ") for x in range(1, rec.count())]
            data =   [query.value(rec.fieldName(x)) for x in range(1, rec.count())]

            # for item in self.fieldTraits:
            #     _value = 0
            #     #to avoid notice (even with err catching), check for the item
            #     if rec.indexOf(item) >=0:
            #         _value = query.value(item)
            #         item = item.capitalize().replace("_"," ")
            #     #data.append(100*_value/ table_size)
            #     data.append(_value)
            #     labels.append (item)
            # if len(data) == 0 : return

            ax = figure.add_subplot(111)
            data_overlap =[]
            data_overlap = np.empty(len(data), dtype = int)
            data_overlap.fill(np.max(data))
            #create the background barh (the resolved value from data_overlap)
            ax.barh(labels, data_overlap, color=ax2_color, edgecolor='grey', alpha = 0.2, linewidth=0.5, linestyle ='dotted')            
            #create the figure
            ax.barh(labels, data, color = ax1_color, edgecolor = 'black', alpha = ax1_alpha, linewidth=0.1)
            #create the second axis
            ax2 = ax.twiny()
            ax2.tick_params(labelsize = ax1_fontsize, pad = 1)
            #set the x limit
            ax.set_xlim(0, np.max(data))
            #add value on the right side  
            pos_x = 1.005*np.max(data)
            for i, v in enumerate(data):
                ax.text(pos_x, i-0.18, int(v), color='brown', fontsize=ax1_fontsize) #, bbox=dict(facecolor=ax2_color, alpha = 0.2, edgecolor='none', boxstyle='round,pad=0.1'))
                #figure.text (0.85, 0.5, int(v))
                
#create a vertical histogram of phenology per month
        elif graphType == 'phenology':
            ylabel = "Frequency (%)"
            #create & execute the query
            sql_query += "\nSELECT to_char(to_date(a::TEXT, 'MM'), 'Mon') as month,"
            sql_query += "\ncount(month) FILTER (WHERE phenology ~* 'fl\.+|bt\.*|boutons?|cauliflore|fertile|fert.|fleurs?|inflorescences?|flowers?|buttons?')::integer as flowers,"
            sql_query += "\ncount(month) FILTER (WHERE phenology ~* 'fr\.+|figues?|fruits?')::integer as fruits,"
            sql_query += "\ncount(month) as count"
            sql_query += "\nFROM generate_series(1,12,1) a"
            sql_query += "\nLEFT JOIN stacked_datas b ON a = b.month"
            sql_query += "\nWHERE phenology IS NOT NULL GROUP BY a order by a"
            
            #execute the sql_query and load data
            query = QtSql.QSqlQuery (sql_query)
            data2 = []
            count_flowers = 0
            count_fruits = 0
            while query.next():
                data.append(query.value("flowers"))
                data2.append(query.value("fruits"))
                labels.append(query.value("month"))
                table_size += query.value("count")
                count_flowers += query.value("flowers")
                count_fruits += query.value("fruits")
            if table_size == 0: 
                return
            
            #create a histogram with two series (fruits & flowers)
            ax = figure.add_subplot(111)
            count_flowers ='Flowers ('+ str(count_flowers) + ')'
            count_fruits ='Fruits ('+ str(count_fruits) + ')'
            data = 100*np.array(data)/np.sum(data)
            data2 = 100*np.array(data2)/np.sum(data2)
            #create a histogram with two series (fruits & flowers)
            ax.bar(labels,data, width = 0.4, color = ax1_color, edgecolor = 'black', alpha = ax1_alpha, linewidth=0.1, label = count_flowers )
            ax.bar(np.arange(len(data2)) + 0.3, data2, width = 0.4, color = ax2_color, edgecolor = 'black', alpha = ax2_alpha, linewidth=0.1, label = count_fruits)
            ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=ax1_fontsize)
            
#create a vertical histogram of stratification
        elif graphType == 'strate':
            xlabel = "Occurrences"
            sql_query += "\nSELECT strate, count(strate) ::integer as count"
            sql_query += "\nFROM stacked_datas WHERE strate IS NOT NULL GROUP BY strate"
            #execute the query and fill the data
            query = QtSql.QSqlQuery (sql_query)
            table_size = 0
            while query.next():
                data.append(query.value("count"))
                labels.append(query.value("strate"))
                table_size += query.value("count")
            if table_size == 0: 
                return

            ax = figure.add_subplot(111)
            ax.barh(labels, data, color= ax1_color, edgecolor='black', alpha = ax1_alpha, linewidth=0.1)

#create Histogram and violon overlaped
        else :
            ylabel = "Frequency"
            if graphType in ['family', 'genus', 'species', 'infra', 'taxaname']:
                xlabel = "Occurrences"
                sql_query += "\nSELECT z.field_toplot FROM"
                sql_query += "\n(SELECT count(id_field_toplot) AS field_toplot FROM stacked_datas GROUP BY id_field_toplot) z"
                sql_query += "\nWHERE z.field_toplot IS NOT NULL"
                if graphType =='taxaname':
                    sql_query = sql_query.replace("id_field_toplot", "taxaname")
            else:
                xlabel = graphType.capitalize().replace("_", " ") + " (Occurrences)"
                try:
                    xlabel = xlabel.replace("Occurrences", list_db_traits[graphType]["unit"])
                except Exception:
                    pass
                sql_query += "\nSELECT field_toplot FROM stacked_datas z"
                sql_query += "\nWHERE z.field_toplot IS NOT NULL"
                
            #add min/Max filter if not None (cf. function variables)
            if min is not None:
                sql_query += "\nAND field_toplot >=" + str(min)
            if max is not None:
                sql_query += "\nAND field_toplot <=" + str(max)

            #set the correct field name and execute the query
            #sql_query = sql_query.replace(" a.*, b.*",  "a." +graphType)
            sql_query = sql_query.replace("field_toplot",  graphType)
            query = QtSql.QSqlQuery (sql_query)           
            table_size = query.size()
            if table_size == 0 : 
                return
            
            #load the data
            while query.next():
                data.append(query.value(0))
                        
            ax = figure.add_subplot(111)
            #add a violon    
            plot_violon = ax.violinplot(data, points=100, widths=1, vert = False, positions = [0],
                            showmeans=True, showextrema=True, showmedians=True)
            #tuning quartiles lines
                        #add a histogram#acbd48
            ax.hist(data, 25, color = ax1_color, edgecolor='black', linewidth=0.1, alpha = ax1_alpha, rwidth = 0.9, weights=np.ones_like(data) / len(data)) #, density=True)
            #plt.gca().xaxis.set_major_formatter(mpl.ticker.FormatStrFormatter('%.1f'))
            #change color, alpha for violon, lines and thick
            violon = plot_violon['bodies'][0]
            violon.set_facecolor(ax2_color)
            violon.set_alpha(ax2_alpha)            

            line_x = plot_violon["cbars"]
            line_x.set_color("blue")
            line_x.set_linewidth(0.5)

            thick_median = plot_violon["cmedians"]
            thick_median.set_color("red")
            thick_median.set_linestyle('dashed')

            thick_average = plot_violon["cmeans"]
            thick_average.set_color("blue")
            thick_average.set_linestyle('dashed')
            
            plot_violon["cmins"].set_color("grey")
            plot_violon["cmaxes"].set_color("grey")

            self.figure_min = float((np.min (data)))
            self.figure_max = float(np.max (data))
            self.figure_mean = float(np.average (data))
            self.figure_median = float(np.median (data))
      
        #add commons parameters
        ax.tick_params(axis='y', labelsize = ax1_fontsize, width = 1)
        ax.tick_params(axis='x', labelsize = ax1_fontsize, rotation = 30, pad = 1, width = 1)
        ax.set_title(graphType.capitalize() + " distribution (n = " + str(table_size) +")",  fontsize = ax1_fontsize, y = 1.1)
        ax.set_xlabel (xlabel, fontsize = ax1_fontsize)
        ax.set_ylabel (ylabel, fontsize = ax1_fontsize)        

        #plt.close()
        #create a marge on left and bottom
        #figure.subplots_adjust(bottom = 0.2, left = 0.2, right = 0.9, top = 0.9)
        #self._figure = figure
        #self.canvas = FigureCanvas(figure)
        #return (FigureCanvas(figure))
        return (figure)











    #load the taxa list
    #return a dictionnary of taxa : {"family1" : {"genus1": [species1, species2, species3,...]}} the list of taxon included into the table
        #create the query               
        # sql_query = "SELECT family, genus, species\nFROM " + self.tabletoExplore
        # sql_query += "\nWHERE genus IS NOT NULL GROUP BY family, genus, species"
        # sql_query += "\nORDER BY family, genus, species"
        # query = QtSql.QSqlQuery (sql_query)
        # self.taxas = {}
        # while query.next():
        #     tab_family = {}
        #     tab_genus = []
        #     #tab_species = []
        #     _family = query.value ("family")
        #     _genus = query.value ("genus")
        #     _species = get_str_value(query.value ("species"))
        #     try:
        #         tab_family = self.taxas[_family]
        #     except:
        #         self.taxas[_family] = tab_family
        #     try:
        #         tab_genus = tab_family[_genus]
        #     except:
        #         tab_family[_genus] = tab_genus
        #     if len(_species) > 0:
        #         tab_family[_genus] = tab_genus + [_species]
        #     self.taxas[_family][_genus] = tab_family[_genus]
            



# def sql_with_stacked_datas (self):
#     #return the with sql (stacked_datas) from the tabletoexplore filter on searchtaxa if not None
#     #only data valid (i.e. with taxaname and at least (GPS, Phenology or Traits))
#     #add a filter on taxaname if self.searchtaxa is not None
#     union_query = "WITH stacked_datas AS (SELECT * FROM " + self.tabletoExplore
#     if len(get_str_value(self.searchtaxa)) > 0:
#             union_query += "\nWHERE id_taxonref IN (" + self.searchtaxa + ")"
#     union_query += '\n)'
#     return union_query
    
# def get_traits_occurrences(self):
#     #return a dictionnary with statistics for any traits
#     # the resulting dictionnary could be view through a class 'class_identity'
#         with_query = self.sql_with_stacked_datas()
#         union_query = ''
#     #get traits from occurrences
#         _tmp=[]        
#         _sqlquery = "SELECT\n _traits_\nFROM stacked_datas WHERE _field_ IS NOT NULL"
#         index = 0
#         _tmpfield_species = []
#         for field, value in list_db_traits.items():
#             if field in self.dbfields:
#                 _tmpfield =[]
#                 ftype = value["type"]
#                 try:
#                     funit = " (" + value["unit"] + ")"
#                 except:
#                     funit = ''
#                 if ftype =="numeric":
#                     _tmpfield_species.append ("avg("+ field + ")::numeric(6,2) AS "+ field)
#                     _tmpfield.append("'"+ field + funit + "'::text AS category")
#                     _tmpfield.append("count(DISTINCT id_taxonref)::integer AS count_species"),
#                     _tmpfield.append("count(id_taxonref)::integer AS count")
#                     _tmpfield.append("avg("+ field + ")::numeric(6,2) AS avg")
#                     _tmpfield.append("min("+ field + ")::numeric(6,2) AS min")
#                     _tmpfield.append("max("+ field + ")::numeric(6,2) AS max")
#                     _tmpfield.append("percentile_cont(0.50) WITHIN GROUP (ORDER BY " +field +" ASC)::numeric(6,2) AS median")
#                     _tmpfield.append("stddev("+ field +")::numeric(6,2) AS stdv"),
#                     _tmpfield.append("(SELECT avg("+ field +")::numeric(6,2) FROM stacked_datas_species) AS avg_species"),
#                     _tmpfield.append("(SELECT min("+ field +")::numeric(6,2) FROM stacked_datas_species) AS min_species"),
#                     _tmpfield.append("(SELECT max("+ field +")::numeric(6,2) FROM stacked_datas_species) AS max_species"),
#                     _tmpfield.append("(SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY " +field +" ASC) FROM stacked_datas_species)::numeric(6,2) AS median_species"),
#                     _tmpfield.append("(SELECT stddev("+ field +")::numeric(6,2) FROM stacked_datas_species) AS stdv_species"),
#                     _tmpfield.append(str(index) + "::integer as pos")
#                     _traits_ = ",\n ".join(_tmpfield)
#                     sql_query = _sqlquery.replace("_traits_",  _traits_)
#                     sql_query = sql_query.replace("_field_",  field)
#                     _tmp.append(sql_query)
#                     index += 1
#         union_query = "\n UNION ALL\n ".join(_tmp)
#         union_query += "\nORDER BY pos"
#         with_query2 = "stacked_datas_species AS (\nSELECT\n" + ",\n ".join(_tmpfield_species)
#         with_query2 += "\nFROM stacked_datas GROUP BY species\n)"
        
#         sql_query = with_query + ",\n"+ with_query2 + "\n" + union_query
#         #print (sql_query)
#         query = QtSql.QSqlQuery (sql_query)
#         tab_traits = {}
#         while query.next():
#             #to ensure order 
#             tab_trait ={"count":'',"min":'', "max":'','avg':'', "median":'', "stdv":''}
#             for _key in tab_trait.keys():
#                 _value_species = get_str_value(query.value(_key +"_species"))
#                 _value = get_str_value(query.value(_key))
#                 tab_trait[_key] = [_value_species, _value]
#             tab_traits[query.value("category")] = tab_trait 
#     #get traits from taxa
#         sql_query = """ 
#             SELECT 
#                 cat, key, value,
#                 count(a.id_taxonref)::integer as count,
#                 count(DISTINCT a.id_taxonref)::integer as count_species
#             FROM 
#                 stacked_datas a 
#                 INNER JOIN 
#                     (SELECT id_taxonref, key AS cat, (jsonb_each_text(value)).*
#                     FROM 
#                         (SELECT id_taxonref, (jsonb_each(properties)).*
#                         FROM taxonomy.taxa_reference) a
#                     ) b
#             ON a.id_taxonref = b.id_taxonref
#             WHERE value <>'False'
#             GROUP BY b.cat, b.KEY, value
#             ORDER BY b.cat, b.KEY, value
#         """
#         sql_query = with_query + "\n" + sql_query
#         #print (with_query)
#         query = QtSql.QSqlQuery (sql_query)
#         while query.next():
#             tab_trait ={}
#             #check for the category
#             try:
#                 tab_trait = tab_traits[query.value("cat")]
#             except:
#                 tab_traits[query.value("cat")] = {}
#             #check for the key
#             try:
#                 tab_trait = tab_trait[query.value("key")]
#             except:
#                 tab_traits[query.value("cat")][query.value("key")] = {}
#             #case, if value = True then affected to the key
#             if query.value("value") == 'True':
#                 tab_traits[query.value("cat")][query.value("key")] = [query.value("count_species"), query.value("count")]
#             else : #else affected a sub category with value
#                 tab_trait = tab_traits[query.value("cat")][query.value("key")]
#                 tab_trait[query.value("value")] = [query.value("count_species"), query.value("count")]
#                 tab_traits[query.value("cat")][query.value("key")] = tab_trait
#         # while query.next():
#         #     data_occurrences.append([get_str_value(query.value(record.fieldName(x))) for x in range(record.count()-1)])
#         return (tab_traits)








#########################################################################################################
class PN_occ_tables(QTableView):
#a treeview to explore data in the open database and schema
#check and included tables containing fields found into the list_db_fields (check for synonyms)
#check and display valid tables (=at least taxaname and (GPS or phenology or traits)
#return sql for rawdata, stackedtable, figures, summary
 
    def __init__(self, schema):
        super().__init__()
        #self.mv_lastupdate = None
        self.schema = schema
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        self.horizontalHeader().setVisible(False)     
        self.verticalHeader().setVisible(False)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.setFont(font)
        self.verticalHeader().setMinimumSectionSize(21)
        self.verticalHeader().setDefaultSectionSize(21)
        #self.set_union_fields = None


        #self.header().hide()
        # style_sheet ="QTreeView{font: 11pt }"
        # style_sheet +="QTreeView::indicator {width: 13px; height: 13px; border: 1px solid grey; background-color: transparent} "
        # style_sheet +="QTreeView::indicator:checked{background: wheat;}"
        # self.setStyleSheet(style_sheet)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.dataset = {}
        self.datasource = {}
        #self.datasetnames = {}
        self.currentTable =''
        import random
        self.tmp_table_name = "tmp_occ" + str(random.randint (0, 1000000))
        
        #is only used by pn_occurrence to stock the table (not suitable)
    # def clear(self):
    #     self.db_accepted_tables = {}

    def load_schema(self):
        sql_query = "SELECT table_name, column_name, column_ref FROM taxonomy.metadata WHERE schema_name = '" + self.schema + "'"
        query = QtSql.QSqlQuery (sql_query)
        dict_translate = {}
        
        while query.next():
            table = query.value("table_name")
            fieldname = query.value("column_name")
            fieldref = query.value("column_ref")
            #value = {fieldname: fieldref} 
            if table in dict_translate:
                dict_translate[table][fieldname] = fieldref
            else:                
                dict_translate[table] = {fieldname: fieldref} 
        return dict_translate

    def load(self):
    #load the tables from the database QtSql included in the self.schema
        #dict_translate = {'double precision':'numeric', 2:'integer', 3:'integer', 4:'numeric', 6:'numeric', 10:'text'}
        self.dataset = {}
        self.datasource = {}
        _db_accepted_tables = {}
        _db_tables = {}
        _db_translate = self.load_schema()
        #run through the information_schema.columns query and add the tables with standard field names found in list_db_fields dictionnary
        sql_query =  "SELECT table_name, column_name, data_type"
        sql_query += "\n FROM information_schema.columns "
        sql_query += "\n WHERE table_schema = '" + self.schema + "'" #AND column_name NOT IN ('id_taxonref', 'dataset')"
        sql_query += "\n ORDER BY table_name, ordinal_position"        
        query = QtSql.QSqlQuery (sql_query)
        _db_tables[self.schema] = {}
        while query.next():
            #schema = query.value("table_schema")
            table = query.value("table_name")
            fieldname = query.value("column_name")
            fieldtype = query.value("data_type")
            fieldtype = get_column_type(fieldtype)
            # try:
            #     fieldtype = get_column_type(fieldtype)
            # except:
            #     pass

            t = None
            if table in _db_translate:
                if fieldname in _db_translate[table]:
                    t = _db_translate[table][fieldname]

            #t = self.search_field(fieldname)
            value = {"field_name": fieldname, "field_type": fieldtype} 
            if t is None:
                t = fieldname
            #OK if the field is found into the predefined list of fields (cf. list_db_fields)
            #if t is None : return

            #get or create the entry for the schema/table
            if table not in _db_tables[self.schema]:
                _db_tables[self.schema][table] = {}
            #set the field properties
            _db_tables[self.schema][table][t] = value
        
        #run through the previous result (_db_tables) and include only the valid tables (= containing a valid combination of fields for an occurrence)
        #i.e.vat least 3 fields (id and taxaname are mandatories)
        # + one functional traits (1 member of list_db_traits), one location (longitude and latitude) or Phenology (phenology + month)
        for schema, tables in _db_tables.items():
            for table, value in tables.items():
                valid = False
                valid, _ = self.is_fieldsValid(value)
                
                # if len(value) >= 3:
                #     try:
                #         if "id" in value and "taxaname" in value: #id and taxaname are mandatories
                #             #value["datasource"] = {"field_name": table , "field_type": 'text'} 
                #             #a table is valid if GPS coordinates, phenology or functional traits
                #             if "longitude" in value and "latitude" in value:
                #                 valid = True
                #             if "phenology" in value and "month" in value:
                #                 valid = True   
                #             if len(set(list_db_traits) & set(value))>0 :                                
                #                 valid = True
                #     except:
                #         pass
                #add to the final db_accepted_tables in the tables is validated
                if valid:
                    if schema not in _db_accepted_tables:
                        _db_accepted_tables[schema] = {}
                    _db_accepted_tables[schema][table] = value
                else:
                    print ('non valid table', table)
        #add the list of accepted table to the treeview in a checkable mode
        self.datasource = _db_accepted_tables[self.schema]
        self.add_tables_list(False)     
        #create a temporary table with the correspondance between the original name and the referenced taxonomy for the whole schema

                    
    def is_fieldsValid(self, headers):
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
                msg = "Unable to find any properties (GPS, Phenology, Functionnal trait,..)"
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



    def add_dataset(self, newtabledef = None):
    #add a new dataset and create the temporary table if not exists
    #first version, to save any tabledef and keep physically any temporary tables (more HD space but quicker for navigate, conserve table, must manage update)
        #import random
        # tmp_table_name =''
        # tmp_table_name = self.get_datasetTable (newdataset)
    #alternative to get only one tmp tables (less HD space, slower load but always update, reload table at each call)
        self.dataset = {}
        #self.datasetnames = {}
        #tmp_table_name = None
        sql_query = "DROP TABLE IF EXISTS " + self.tmp_table_name
        query = QtSql.QSqlQuery (sql_query)
        tabledef = {}
        
        # try:
        #     newtabledef = self.dataset[newdataset]
        # except:
        #     self.dataset[newdataset] = {}
            #tabledef = newtabledef

        #if tmp_table_name is None:
        #tmp_table_name = self.tmp_table_name
        #release in first version
        #tmp_table_name = "tmp_occ" + str(random.randint (0, 1000000)) 
        sql_query = "CREATE TABLE " + self.tmp_table_name + " AS\n" + self.sql_staked_data(newtabledef)
        query = QtSql.QSqlQuery (sql_query)
        if query.isActive():
            #if len(self.dataset[newdataset]) == 0:
            tabledef = self.get_tabledef_fromtable(self.tmp_table_name)
            self.dataset[self.tmp_table_name] = tabledef
            #self.datasetnames[newdataset] = tmp_table_name
        # else:
        #     tmp_table_name = ''
        return self.tmp_table_name
    
    def is_datasource(self, table):
    #return True if the table is a dataset
        return table in self.datasource
        
    # def get_datasetTable(self, datasetname):
    # #return the table from the datasetname
    #     try:
    #         return self.datasetnames[datasetname]
    #     except:
    #         return

    def get_tabledef_fromtable(self, table):
    #get the tabdef from a table
        newtabledef = {}
        # try:
        #     table_def = self.datasource[table]
        #     for field, field_def in table_def.items():
        #         fieldname = field_def['field_name']
        #         fieldtype = field_def['field_type']
        #         _field = {"field_name": field_def['field_name'], "field_type": field_def['field_type'], "field_ref": field}
        #         newtabledef[fieldname] = _field
        # except:
        sql = "SELECT * FROM " + table +" LIMIT 1"
        query = QtSql.QSqlQuery (sql)
        record = query.record()
        
        for i in range(record.count()):
            fieldname = record.field(i).name()
            try:
                fieldtype = get_column_type[record.field(i).type()]
            except Exception:
                fieldtype = record.field(i).type()
            _field = {"field_name": fieldname, "field_type": fieldtype} 
            newtabledef[fieldname] = _field
        return newtabledef


    def add_tables_list(self, checkable = False):
    #add the tables of the schema into the treeview (self.schema)
        model = QtGui.QStandardItemModel()
        self.setModel(model)
        tab_db_fields = self.get_tables()
        for table in tab_db_fields.keys():
            item = QtGui.QStandardItem(table)
            italic_font = QtGui.QFont()
            italic_font.setItalic(self.isTableFiltered (table))
            item.setFont(italic_font)
            item.setCheckable(checkable)
            model.appendRow([item])
        self.resizeColumnToContents(0)
    
    def set_tableItem_color(self):
    #set the item in italic if a filter is apply
        model= self.model()
        for i in range(model.rowCount()):
            table = None
            item = model.item(i,0)
            table = item.data(0)
            italic_font = QtGui.QFont()
            italic_font.setItalic(self.isTableFiltered (table))
            item.setFont(italic_font)
                
    def addFieldfFilter (self, table, fieldname, operator, value):
    #add a filter on a field from the table
        try:
            self.get_field(table, fieldname)['sql_value'] = value
            self.get_field(table, fieldname)['sql_operator'] = operator
        except Exception:
            pass
        self.set_tableItem_color()
    
    def isFieldFiltered(self, table, fieldname):
    #return True/False if the field of the table has a filter
        try:
            return len (self.get_field(table, fieldname)["sql_operator"]) > 0
        except Exception:
            return False
        
    def isTableFiltered(self, table):
    #return True/False if the table has a least one filter
        fields = self.get_fields(table)
        for value in fields.values():
            try:
                if len(value["sql_operator"]) > 0:
                    return True
            except Exception:
                pass
        return False
           
    def delFieldFilter(self, table, fieldname):
    #delete the filter of the field
        try:
            del self.get_field(table,fieldname)['sql_operator'] 
            del self.get_field(table,fieldname)['sql_value']
        except Exception:
            pass
        self.set_tableItem_color()


    
    def selectedTables (self):
    #return a list of the check tables according to the treeview checkbox
        selected_indexes = self.selectionModel().selectedRows()
        ls_tabs = []
        for item in selected_indexes:
            ls_tabs.append(item.data())

        # model = self.model()
        
        # for row in range (model.rowCount()):
        #     item = model.item(row)
        #     if item.checkState() == 2:
        #         ls_tabs.append(item.text())
        if len(ls_tabs) == 0:
            ls_tabs = [self.currentIndex().data(0)]
        return (ls_tabs)

    def fieldUnit(self, fieldref:str):
    #return the field unit related to the field_ref into the schema and table
        try:
            return list_db_fields[fieldref]["unit"]
        except Exception:
            return ''
        
    def fieldName(self, table, fieldref):
    #return the true field_name (= original field) of the table related to the field_ref (= standardized field)
        try:
            return self.get_fields(table)[fieldref]['field_name']
        except Exception:
            return ''  
        
    # def search_field(self, fieldname):
    # #return the field_ref from a fieldname, check in key and synonyms
    #     for key, value in list_db_fields.items():
    #         if key == fieldname:
    #             return key
    #         elif fieldname in value["synonyms"]:
    #             return key
         
    def get_field (self, table, fieldname):
    #returns the field defition, searching first in field_name (original) ou field_ref (standardized)
        try:
            for key, value in self.get_fields(table).items():
                if value["field_name"] == fieldname:
                    return value
                elif key  == fieldname:
                    return value
        except Exception:
            return 
            
    def get_fields (self, table):
    #returns the list of fields for the table
        try:
            return self.get_tables()[table]
        except Exception:
            return None

    def get_tables(self, dataset_included = True):
    #return accepted tables into the schema
        if dataset_included:
            ls_tosearch = self.datasource | self.dataset
        else:
            ls_tosearch = self.datasource
        try:
            return ls_tosearch
        except Exception:
            return self.datasource


    # def get_tables(self, schema = None):
    # #return accepted tables into the schema
    #     try:
    #         return self.db_accepted_tables[schema]
    #     except Exception:
    #         return self.db_accepted_tables


    def tab_staked_traits(self, trait):
        def get_sqlfields(table, trait):
            fields = self.get_field(table, trait)
            if fields:
                field = fields.copy()
                field["sql_operator"] = "IS NOT"
                field["sql_value"] = "NULL"
                return field
            
        tables = {}
        trait2 =''
        if trait == 'location':
            trait = 'longitude'
            trait2 = 'latitude'
        elif trait == 'phenology':
            trait2 = 'month'

        for table in self.get_tables(False):
            valid = False
            fieldef = get_sqlfields(table, trait)
            if len(trait2) > 0:
                fieldef2 = get_sqlfields(table, trait2)
                valid = (fieldef and fieldef2) is not None
            else:
                valid = fieldef is not None
            if valid:
                tables[table] = {}
                tables[table][trait] = fieldef
                if len(trait2) > 0:
                    tables[table][trait2] = fieldef2

            # if trait == 'longitude':
            #     trait = 'latitude'
            #     fieldef = get_sqlfields(table, trait)
            #     if fieldef:
            #         tables[table] = {}
            #         tables[table][trait] = field     

            # fields = self.get_field(table, trait)
            # if fields:
            #     field = fields.copy()
            #     field["sql_operator"] = "IS NOT"
            #     field["sql_value"] = "NULL"

            #     if trait == 'longitude':
            #         trait = 'latitude'
            #         fields = self.get_field(table, trait)
            #         if fields:
            #             field = fields.copy()
            #             field["sql_operator"] = "IS NOT"
            #             field["sql_value"] = "NULL"
            #             tables[table][trait] = field
        return (tables)

    def tab_stacked_datasource(self):
    #get the tabledef for selected tables, including filter
        tab_selecteditems = {}
        #selected_indexes = self.selectedIndexes()
        tables = [index.sibling(index.row(), 0).data() for index in self.selectedIndexes()]
        for table in tables:
                tab_selecteditems[table] = {}
                if self.isTableFiltered(table):
                    fields = self.get_fields(table)
                    _fields = {}
                    for field, value in fields.items():
                        if self.isFieldFiltered (table, field):
                            _fields[field] = value
                    if len(_fields) > 0:
                        tab_selecteditems[table] = _fields
        #tab_selecteditems = tab_selecteditems.replace("'", "\"")
        return (tab_selecteditems)
    
    def fieldstoUse(self, tabledef=None, union = True):
        if tabledef:
            tables = list(tabledef.keys())
        else:
            #ls_output = list_db_fields
            tables = self.selectedTables()
        #list the common fields, used by  all tables
        _usedtraits = {}
        for key, value in list_db_fields.items():
            valid = False
            for table in tables:
                if self.get_field (table, key) is None:
                    valid = False
                    if union:
                        break
                    #break here to used only commons fields
                else:
                    valid = True
                    if not union:
                        break # here to used field found at least one time
            if valid:
                _usedtraits[key] = value
        return _usedtraits

    def sql_staked_data (self, tabledef = None):
#get the sql query for collecting any data (original_name + taxonomy + traits) included in accepted tables of the self.schema
        #the query return a standard query to create a table to be independently explore through the class PN_occ_explore
        sql_gabarit = """
        WITH 
        	occurrences AS
         	(SELECT * --,  (longitude is NOT NULL AND latitude is NOT NULL) AS location
         	 FROM --UNION of occ tables and filter
				(__SQLUNIONTRAITS__
		        ) union_query
		        
		     WHERE
		     	--ADD TESTS VALIDITY
        		(
            	    __SQLWHERETRAITS__
        		)
        	),
            taxa_query AS
            (SELECT a.id_taxonref, b.*
            	FROM taxonomy.pn_taxa_searchnames(ARRAY(
            		SELECT taxaname FROM occurrences WHERE taxaname IS NOT NULL GROUP BY taxaname)) a 
            	INNER JOIN occurrences b ON a.original_name = b.taxaname
             WHERE a.id_taxonref IS NOT NULL 
            )
            SELECT * FROM taxa_query
        """
        #CHECK used traits from selected tables (the field must be at least in one table)
        #ls_output = {}
        if tabledef:
            tables = list(tabledef.keys())
        else:
            #ls_output = list_db_fields
            tables = self.selectedTables()
            
        # #list the common fields, used by  all tables
        # _usedtraits = {}
        # for key, value in list_db_fields.items():
        #     valid = False
        #     for table in tables:
        #         if self.get_field (table, key) is None:
        #             valid = False
        #             if self.set_union_fields:
        #                 break
        #             #break here to used only commons fields
        #         else:
        #             valid = True
        #             if not self.set_union_fields:
        #                 break # here to used field found at least one time
        #     if valid:
        #         _usedtraits[key] = value

        _usedtraits = self.fieldstoUse(tabledef, union = False)   
                
        #ADD traits for selected tables and traits
        _sqltraits = ''
        _sqlquery = "\nSELECT __TRAITS__\nFROM __SCHEMATABLE__"
        _tmp = []
        for table in tables:
            if tabledef:
                fields = tabledef[table]
            else:
                fields = self.get_fields(table)
            
            schema_table = self.schema + '.' + table + " " + self.sql_table_filter(fields)
            #field_taxaname = self.fieldName(table, 'taxaname')
            _tmpfield = []
            _valid = False
            #add dataset origin (name of the table)
            _tmpfield.append("\n\t'" + table + "'::text AS dataset")
            #add db_identity + db_traits
            for field, value in _usedtraits.items():
                ftype = value["type"]
                field_toplot = self.fieldName (table, field)
                if len (field_toplot) > 0:
                    _tmpfield.append(field_toplot + "::" +ftype +" AS " + field)
                    _valid = True
                else:
                    _tmpfield.append("NULL::" +ftype +" AS " + field)
            #delete duplicate
            _tmpfield = list(dict.fromkeys(_tmpfield))
            _traits_ = ",\n\t".join(_tmpfield)
            sql_query = _sqlquery.replace("__TRAITS__",  _traits_)
            sql_query = sql_query.replace("__SCHEMATABLE__",  schema_table)
            #if at least one True field, add the table definition
            if _valid: #at least one traits
                _tmp.append(sql_query)
        
        #return if not at least one table
        if len(_tmp) == 0: 
            return
        _sqltraits = "\n\tUNION ALL ".join(_tmp)

        #FILTER for only valid datas (test for at least one traits including location or phenology)
        _tmptraits = []
        #add used traits
        for field  in list_db_traits.keys():
            if field in _usedtraits:
                _tmptraits.append (field +" IS NOT NULL")
        #add if GPS and Phenology
        _tmp = []
        if 'longitude' in _usedtraits and 'latitude' in _usedtraits:
            _tmp.append ('(longitude is NOT NULL and latitude is NOT NULL)')
        if 'month' in _usedtraits and 'phenology' in _usedtraits:
            _tmp.append ('(phenology IS NOT NULL and month is NOT NULL)')     
        if len(_tmptraits) > 0:
            _tmp.append ("(" + " OR ".join(_tmptraits) +")")
        _sqlwhere = " OR ".join (_tmp)
        
        #REPLACE terms in sql_gabarit
        sql_gabarit = sql_gabarit.replace ('__SQLWHERETRAITS__', _sqlwhere)
        sql_gabarit = sql_gabarit.replace ('__SQLUNIONTRAITS__', _sqltraits)
        #sql_gabarit = sql_gabarit.replace ('::text AS taxaname', '::text AS original_name')

    #create the temporary table
        # sql_query = "CREATE TABLE " + tabletocreate + " AS\n" +sql_gabarit
        # query = QtSql.QSqlQuery (sql_query)
        # query.exec(sql_query)
        return sql_gabarit

    def sql_table_data(self, table = None):
        #return the sql with any fields for the table  + a valid field (valid if fill three conditions)
        #include a sql_filter (if sql_operator and sql_value)
        #sql_query = ''
        _tmp = []
        if table is None: 
            table = self.tmp_table_name
            self.currentTable = table
            #return sql_query
        #gets variables
        fields = self.get_fields(table)
        if fields is None: 
            return
        field_taxaname = fields['taxaname']['field_name']
        if field_taxaname is None: 
            return
        #get schema, depend if dataset or datasource
        schema_table = self.schema + '.' + table
        filter = 'True'
        #set the schema_table, depending if datasoure or dataset
        schema_table = table
        if self.is_datasource(table):
            schema_table = self.schema + '.' + table
            
        #set variable
        schema_table_filter = schema_table + " " + self.sql_table_filter(fields)
        #add any fields
        for field, value in fields.items():
            _tmp.append(value['field_name'])
        fieldtoAdd = ', a.'.join(_tmp)
        fieldtoAdd = "a." + fieldtoAdd
        #fieldtoAdd = 'b.taxonref, ' + fieldtoAdd
        #set gabarit of query
        sql_gabarit =  """
            SELECT c.*,
            (
            __FILTER__
            ) as valid
            FROM (
            SELECT __FIELDS__ 
            FROM (SELECT * FROM __SCHEMATABLEFILTER__) a
            INNER JOIN 
            taxonomy.pn_taxa_searchtable('__SCHEMATABLE__', '__TAXANAME__') b ON a.__TAXANAME__ = b.original_name
            ) c
        """ 
        sql_gabarit =  """
            SELECT c.*,
            (
            __FILTER__
            ) as valid
            FROM (
            SELECT __FIELDS__ 
            FROM (SELECT * FROM __SCHEMATABLEFILTER__) a
            ) c
        """ 


        #if the table is a datasource, add a filter to test for valid flag
        if self.is_datasource(table):
            filter = ''
            #_prefix = ''
            _tmp = []
            #create the filter (gps or phenology or traits)
            #add gps filter if exist
            try :
                _sqlwhere = "(c.latitude IS NOT NULL AND c.longitude is NOT NULL)"
                _sqlwhere = _sqlwhere.replace("latitude",  fields["latitude"]["field_name"])
                _sqlwhere = _sqlwhere.replace("longitude",  fields["longitude"]["field_name"])
                _tmp.append(_sqlwhere)
            except Exception:
                _sqlwhere = ''
            #add phenology filter if exist
            try :
                _sqlwhere = "(c.month IS NOT NULL AND c.phenology IS NOT NULL)"
                _sqlwhere = _sqlwhere.replace("month",  fields["month"]["field_name"])
                _sqlwhere = _sqlwhere.replace("phenology",  fields["phenology"]["field_name"])
                _tmp.append(_sqlwhere)
            except Exception:
                _sqlwhere = ''
            #add traits filter if exist --filter = ' OR '.join(_tmp)
            _tmpfield = []
            for field  in list_db_traits.keys():
                try:
                    field_totest = fields[field]["field_name"]
                    _tmpfield.append ("c." + field_totest +" IS NOT NULL")
                except Exception:
                    pass
            if len (_tmpfield) > 0:
                _tmp.append ("(" + " OR ".join(_tmpfield) + ")")
            #finally join qurey by OR
            if len(_tmp) > 0:
                filter = ' OR '.join(_tmp)

        #fill sql_gabarit
        sql_gabarit = sql_gabarit.replace("__FIELDS__",  fieldtoAdd)
        sql_gabarit = sql_gabarit.replace("__SCHEMATABLEFILTER__",  schema_table_filter)
        sql_gabarit = sql_gabarit.replace("__TAXANAME__",  field_taxaname)
        sql_gabarit = sql_gabarit.replace("__SCHEMATABLE__",  schema_table)
        sql_gabarit = sql_gabarit.replace("__FILTER__",  filter)
        #print (sql_gabarit)
        return sql_gabarit
    

    def sql_table_filter(self, fields, with_where = True):
        #return the sql filter set on the table according to the "sql_operator" and "sql_value" included in fields (optional)
        #return with a prefix WHERE or AND according to the parameter with_where
        sql_query = ''
        tab_query = []
        #fields = self.get_fields(table)

        if fields is None : 
            return sql_query
        for value in fields.values():
            try:
                fieldname = value["field_name"]
                #fieldtype = value["field_type"]
                operator = value["sql_operator"]
                value = value["sql_value"]
                
            except Exception:
                operator = ''
                value = ''
            if len(operator) * len(value)> 0:
                if operator in ["IN", "NOT IN"]:
                    values_list = value.split(',')
                    value = "({})".format(', '.join(["'{}'".format(val) for val in values_list]))

                    #value = '(' + value + ')'
                tab_query.append (fieldname + ' ' + operator + ' ' + value)
        if len(tab_query) > 0:
            if with_where:
                sql_query +="WHERE "
            else:
                sql_query +="AND "
            sql_query += ' AND '.join(tab_query)       
        return sql_query

    def sql_taxa_resolution (self, table, unresolved_only = False):
    #return the sql_query to decode taxaname from a table (or dataset)
        try:
            fields = self.get_fields(table)
            field_name = fields["taxaname"]["field_name"]
        except Exception:
            return
        #get the schema according to data origin  
        schema_table = self.schema + '.' + table
        if not self.is_datasource(table):
            schema_table = table
        #create the sql query using the internal postgresql function taxonomy.pn_taxa_searchtable
         
        sql_query = "SELECT a.__FIELDNAME__ AS original_name, c.taxonref, c.id_taxonref, a.keyname"
        sql_query += "\n FROM (SELECT __FIELDNAME__, taxonomy.pn_taxa_keyname(__FIELDNAME__) AS keyname FROM __SCHEMATABLE__ WHERE __FIELDNAME__ IS NOT NULL _WHERE_ GROUP BY __FIELDNAME__) a"
        sql_query += "\n LEFT JOIN taxonomy.taxa_nameset b ON a.keyname = b._keyname"
        sql_query += "\n LEFT JOIN taxonomy.taxa_names c ON b.id_taxonref = c.id_taxonref"
        if unresolved_only:
            sql_query +=  "\n WHERE c.id_taxonref IS NULL"

        
        sql_query = sql_query.replace("__FIELDNAME__", field_name)
        sql_query = sql_query.replace("__SCHEMATABLE__", schema_table)
        sql_query = sql_query.replace("_WHERE_", "") 

        return sql_query
    
    # def tmp_taxadb(self):
    # #get the temporary table of taxa included into the schema
    #     import random
    #     # if self.mv_lastupdate is None:
    #     #     self.tmp_table_name = None
            
    #     #check if materialized view taxa_keynames2 was updated
    #     sql_query = "SELECT relfilenode FROM pg_class JOIN pg_catalog.pg_namespace n ON n.oid = pg_class.relnamespace"
    #     sql_query += "\nWHERE relname = 'taxa_keynames2' AND nspname = 'taxonomy'"
    #     query = QtSql.QSqlQuery (sql_query)
    #     query.next()
    #     t_stamp = query.value("relfilenode")
    #     if self.mv_lastupdate != t_stamp:
    #         self.tmp_table_name = None
    #         self.mv_lastupdate = t_stamp

    #     if self.tmp_table_name is None:
    #         self.tmp_table_name = "tmp_occ_taxa" + str(random.randint (0, 1000000))
    #         self._create_table_name()
    #     return self.tmp_table_name


    # def set_Checkable(self, ischeckable = False):
    #     self.add_tables_list(ischeckable)
    #     return
    #     #recursive function to uncheck childs
    #     for row in range(0, self.model().rowCount()):
    #         item = self.model().item(row)
    #         #item.setCheckable(ischeckable)
    #         item.setData(ischeckable,Qt.CheckStateRole)
    #         #item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable );
    #     return

 
class PN_taxa_resolution_model(QtCore.QAbstractTableModel):
    header_labels = ['Name', 'Reference Name']
    def __init__(self, data = None):
        super(PN_taxa_resolution_model, self).__init__()
        self._data = []
        self._data = data if data is not None else []
            
    def getdata(self, with_header = False, only_valid = False):
    #return a list of list of data with or without header
        data = []
        #add header if necessary
        if with_header:
            data.append(self.header_labels)
        for row in range(self.rowCount()):
            item = self._data[row]
            valid = True
            #if only_valid then item must be resolved (taxonref is not NULL)
            if only_valid:
                valid = item.resolved
            if valid:
                rowData =[get_str_value(item.synonym), get_str_value(item.taxon_ref)]
                data.append(rowData)
        return data
    
    def resetdata(self, newdata = None):
        self.beginResetModel()
        self._data = newdata if newdata is not None else []
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.header_labels[section]
        #return self.headerData(self, section, orientation, role)

    # def refresh (self, myPNSynonym):
    #     ##refresh model (check all data for a similar cleaned_name and affect the value of the input class, NOT PERSISTENT IN DATABASE)
    #     for synonym in self._data:
    #         if synonym.cleaned_name == myPNSynonym.cleaned_name:
    #             synonym.id_taxonref = myPNSynonym.idtaxonref
    #             synonym.taxon_ref = myPNSynonym.taxon_ref
    #             synonym.id_synonym = myPNSynonym.id_synonym

    def data(self, index, role):
        if not index.isValid():
            return None
        if 0 <= index.row() < self.rowCount():
            item = self._data[index.row()]
            col = index.column() 
            if role == Qt.DisplayRole:
                if col==0:
                    return item.synonym
                # elif col==1:
                #     return item.cleaned_name
                elif col==1:
                    return item.taxon_ref
            elif role == Qt.UserRole:
                return item
            elif role == Qt.DecorationRole:
                if col == 0:
                    #idtaxonref = getattr(item, 'stid_taxon_ref', 0)
                    col = QtGui.QColor(255,0,0,255)
                    if item.resolved:
                        col = QtGui.QColor(0,255,0,255)
                    px = QtGui.QPixmap(12,12)
                    px.fill(QtCore.Qt.transparent)
                    painter = QtGui.QPainter(px)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    px_size = px.rect().adjusted(2,2,-2,-2)
                    painter.setBrush(col)
                    painter.setPen(QtGui.QPen(QtCore.Qt.black, 0,
                        QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
                    painter.drawEllipse(px_size)
                    painter.end()

                    return QtGui.QIcon(px)

    def rowCount(self, index=QtCore.QModelIndex()):
        # The length of the outer list.
        return len(self._data)

    # def unresolvedCount(self):
    #     i = 0
    #     for synonym in self._data:
    #         if synonym.idtaxonref == 0:
    #             i += 1
    #     return i
    
    def columnCount(self, index=QtCore.QModelIndex()):
        return 2

    def additem (self, clrowtable):
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self._data.append(clrowtable)
        self.endInsertRows()
        
    def searchSynonym(self, synonym):
        for item in self._data:
            #print (synonym.idtaxonref)
            if item.synonym == synonym:
                return item
            
    def unresolvedCount(self):
        i = 0
        for synonym in self._data:
            #print (synonym.idtaxonref)
            if synonym.idtaxonref == 0:
                i += 1
        return i






class MainWindow(QtWidgets.QMainWindow):
    
    def __init__(self):
        super().__init__()
        from taxa_model import PNSynonym
        self.table = QtWidgets.QTableView()
        data = [
           PNSynonym(123,'Miconia', 'Miconia DC.'),
           PNSynonym(124,'Miconia calvescens',  'Miconia calvescens')
        #  # PNTaxa(1456,'Sapotaceae', 'L.', 10),
        ]
       
        #self.model = TableModel(data)
        self.model = PN_taxa_resolution_model()
        self.model.resetdata(data)
        self.table.setModel(self.model)
       # self.model.additem(PNSynonym(1456,'Sapotaceae', 'L.', 10, 2))
       # self.model.additem(PNSynonym(1800,'Arecaceae', 'L.', 10, 3))

        self.setCentralWidget(self.table)

if __name__ == '__main__':
    app=QtWidgets.QApplication(sys.argv)

    window=MainWindow()
    window.show()
    app.exec_()

