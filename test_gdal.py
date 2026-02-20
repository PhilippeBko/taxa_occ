import sys

from osgeo import gdal
import numpy as np
from osgeo import gdal, ogr
from osgeo.gdalconst import GA_ReadOnly

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import * 
from PyQt5 import QtGui, QtSql
from PyQt5.QtCore import *
import os





from osgeo import gdal
import numpy as np

def createConnection(db):
    db.setHostName("localhost")
    db.setDatabaseName("amapiac") 
    db.setUserName("postgres")
    db.setPassword("postgres")
    #app2 = QApplication([])
    if not db.open():
        QMessageBox.critical(None, "Cannot open database",
                             "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        return False
    return True

# Fonction pour lire un raster et retourner un tableau NumPy
def read_raster(file_path):
    dataset = gdal.Open(file_path)
    band = dataset.GetRasterBand(1)
    raster_array = band.ReadAsArray()
    nodata_value = band.GetNoDataValue()
    if nodata_value is not None:
        raster_array = raster_array[raster_array != nodata_value]
        #raster_array = np.ma.masked_equal(raster_array, nodata_value)  # Mask nodata values
    return raster_array
print (read_raster ("/home/birnbaum/Documents/Calédonie/Carto/MNT/strm90/mnt_srtm90_wgs84.tif"))
def raster_value(table_name):
    # Connexion à la base de données PostGIS
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"

    # Spécifiez la table et la colonne contenant le raster
    #table_name = "ssdm_forest_mid_elevation"
    raster_column = "rast"
    #where_clause = "id = 1"  # Optionnel, pour sélectionner un raster spécifique si nécessaire

    # Construire la chaîne de connexion complète
    gdal_dataset_path = f"{postgis_connection_string} table={table_name} column={raster_column} "

    # Ouvrir le raster depuis PostGIS
    dataset = gdal.Open(gdal_dataset_path)
    # Vérifier que le dataset a été ouvert correctement
    if not dataset:
        raise RuntimeError("Impossible d'ouvrir le dataset")

    # Lire la première bande (adapté si plusieurs bandes)
    band = dataset.GetRasterBand(1)
    raster_array = band.ReadAsArray()
    nodata_value = band.GetNoDataValue()
    if nodata_value is not None:
        raster_array = raster_array[raster_array != nodata_value]
    
    transformed_array = raster_array * 0.2552 + 30.4065
    pixel_values = transformed_array.flatten().tolist()
    from collections import Counter 
    pixel_values_int = np.round(pixel_values).astype(int)
    value_counts = Counter(pixel_values_int)

    output_file_path = '/home/birnbaum/Téléchargements/pixel_values.txt'
    with open(output_file_path, 'w') as f:
        for value, count in sorted(value_counts.items()):
            f.write(f"{value}: {count}\n")

    print(pixel_values[:10])
#raster_value("ssdm_forest_high_elevation")


def raster_quantile(table_name):
    # Connexion à la base de données PostGIS
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"

    # Spécifiez la table et la colonne contenant le raster
    #table_name = "ssdm_forest_mid_elevation"
    raster_column = "rast"
    #where_clause = "id = 1"  # Optionnel, pour sélectionner un raster spécifique si nécessaire

    # Construire la chaîne de connexion complète
    gdal_dataset_path = f"{postgis_connection_string} table={table_name} column={raster_column} "

    # Ouvrir le raster depuis PostGIS
    dataset = gdal.Open(gdal_dataset_path)
    # Vérifier que le dataset a été ouvert correctement
    if not dataset:
        raise RuntimeError("Impossible d'ouvrir le dataset")

    # Lire la première bande (adapté si plusieurs bandes)
    band = dataset.GetRasterBand(1)
    raster_array = band.ReadAsArray()
    nodata_value = band.GetNoDataValue()
    if nodata_value is not None:
        raster_array = raster_array[raster_array != nodata_value]
    raster_array = raster_array[raster_array >0]
    #calcul quantiles
    q75 = np.percentile(raster_array, 75)
    q80 = np.percentile(raster_array, 80)
    print (table_name, "q80:", q80, "q75:", q75)

#raster_quantile("ssdm_forest_dry_holdridge")


""" 
raster_quantile("ssdm_forest_low_elevation")
raster_quantile("ssdm_forest_mid_elevation")
raster_quantile("ssdm_forest_high_elevation")

 """
# def rasterize_from_dbshape():
#     # Paramètres de connexion à la base de données PostgreSQL
#     db_params = {
#         'dbname': 'amapiac',
#         'user': 'postgres',
#         'password': 'postgres',
#         'host': 'localhost',
#         'port': '5432'
#     }

#     # Requête SQL pour extraire la géométrie depuis la base de données
#     sql_query = "SELECT geom FROM amap_carto_forest3k_wgs84"

#     # Connexion à la base de données et récupération des données géospatiales
#     conn = ogr.Open("PG:dbname='amapiac' user='postgres' password='postgres' host='localhost' port='5432'")
#     layer = conn.ExecuteSQL(sql_query)
 
 
#     # Créer une couche mémoire pour stocker toutes les géométries
#     mem_driver = ogr.GetDriverByName('Memory')
#     mem_ds = mem_driver.CreateDataSource('')
#     mem_layer = mem_ds.CreateLayer('mem_layer', geom_type=ogr.wkbPolygon)

#     # Ajouter toutes les géométries à la couche mémoire
#     for feature in layer:
#         mem_layer.CreateFeature(feature)

#     # Sélectionner toutes les géométries de la couche mémoire
#     mem_layer.ResetReading()


#     # Sélectionner la géométrie
#     geometrie = feature.GetGeometryRef()

#     # Fermer la connexion à la base de données
#     #conn = None

#     extent = mem_layer.GetExtent()

#     # Ajuster la résolution souhaitée
#     resolution = 30  # en mètres
#     pixel_size = resolution / 111120.0  # Approximation de la conversion de degrés en mètres

#     # Calculer la largeur et la hauteur en fonction de l'étendue totale
#     xmin, ymin, xmax, ymax = extent
#     width = int((xmax - xmin) / pixel_size)
#     height = int((ymax - ymin) / pixel_size)


#     # # Récupérer les métadonnées du raster à partir de la géométrie
#     # xmin, xmax, ymin, ymax = geometrie.GetEnvelope()
#     # width, height = 5000, 5000  # ajustez selon vos besoins

#  # Chemin du fichier raster
#     raster_path = '/home/birnbaum/Documents/Calédonie/Carto'
#     raster_name = 'raster.tif'
#     full_raster_path = os.path.join(raster_path, raster_name)

#     # Vérifier si le dossier existe, sinon le créer
#     if not os.path.exists(raster_path):
#         os.makedirs(raster_path)

# # Créer le raster avec GDAL
#     driver = gdal.GetDriverByName('GTiff')
#     output_raster = driver.Create(full_raster_path, width, height, 1, gdal.GDT_Byte)
#     output_raster.SetProjection(mem_layer.GetSpatialRef().ExportToWkt())

#     # Calculer la nouvelle géotransformation
#     output_raster.SetGeoTransform((xmin, pixel_size, 0, ymax, 0, -pixel_size))

#     # Convertir toutes les géométries en masque
#     raster_mask = gdal.RasterizeLayer(output_raster, [1], mem_layer, burn_values=[1])

#     # Vérifier si la rasterization a réussi
#     if raster_mask != 0:
#         raise Exception("Erreur lors de la rasterization")

#     # Fermer le raster
#     output_raster = None

    
# rasterize_from_dbshape()







def clip_raster_from_query(raster_path, postgis_connection_string, sql_query):
    # input dataset
    # dataset = gdal.OpenShared(raster_path, GA_ReadOnly)
    # geo_transform = dataset.GetGeoTransform()
    # pixel_size_x = geo_transform[1]
    # pixel_size_y = geo_transform[5]
    # dataset = None
    
    #raster = dataset.GetRasterBand(1)
    warp_opts = gdal.WarpOptions(
        format="MEM",
    # format="GTiff",
        cutlineDSName=postgis_connection_string,
        cutlineSQL=sql_query,
        cropToCutline=True,
    )

    res = gdal.Warp("",
                    raster_path,
                    options=warp_opts,
                )
    # if res is None: return

    # raster_band = res.GetRasterBand(1)
    
    #     # Lire les données du raster
    # raster_data = raster_band.ReadAsArray()

    #     
    # pixel_count = (raster_data != 0).sum()
    # pixel_count = np.count_nonzero(raster_data != 0)
    # pixel_count = np.count_nonzero(raster_data == 93)
    # pixel_total= (raster_data).sum()
    return res
def get_area_ha():
    gdal_uri = (
        "PG:host=localhost dbname=amapiac user=postgres password=postgres "
        "schema=public table=ssdm_forest_high_elevation column=rast mode=2"
    )

# Ouvrir le raster depuis PostgreSQL
    raster = gdal.Open(gdal_uri)
    raster_band = raster.GetRasterBand(1)
    raster_data = raster_band.ReadAsArray()
    pixel_total= 55493 #np.count_nonzero(raster_data > 0)
    pixel_nonull = np.count_nonzero((raster_data > 0)) #& (raster_data >900))
    ratio = round(100*pixel_nonull/pixel_total,2)
    print (ratio, pixel_nonull, pixel_total)

get_area_ha()


def get_deforestation(year = 2050):
    raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/amap_forest_deforestation2050_wgs84.tif"
    if not year == 2050:
        raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/amap_forest_deforestation2100_wgs84.tif"

    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"
    #raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/amap_forest_deforestation2100_wgs84.tif"
    
    sql_query = "SELECT id_buffer FROM amap_hotspots_forest_nc"
    query = QtSql.QSqlQuery (sql_query)
    while query.next():
        id_buffer = query.value("id_buffer")
        sql_clip = "SELECT id_buffer, st_transform(geom, 4326) geom FROM amap_hotspots_forest_nc where id_buffer = " + str(id_buffer)
        clip_raster = clip_raster_from_query(raster_path, postgis_connection_string, sql_clip)
        raster_band = clip_raster.GetRasterBand(1)
        raster_data = raster_band.ReadAsArray()
        pixel_total= np.count_nonzero(raster_data >= 0)
        pixel_deforestation = np.count_nonzero(raster_data == 0)
        ratio = round(100*pixel_deforestation/pixel_total,2)
        sql_update = f"UPDATE amap_hotspots_forest_nc SET defor_{year} = {ratio} WHERE id_buffer = {id_buffer}"
        query_update = QtSql.QSqlQuery()
        query_update.exec(sql_update)

""" 

get_deforestation(2050)
get_deforestation(2100)

 """

def get_forest_eth_grid():
#extract les paramètres statistiques de la hauetur de la canopée (ETH) des polygones de forêts et affecte les valeurs à la grid
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"
    raster_path1 = "/home/birnbaum/Téléchargements/raster_forest_eth.tif"

    sql_insert = "INSERT INTO carto.check_grid_tmf (id_grid, h_quantile1, h_median, h_mean, h_min, h_max, pixels) VALUES (__id__, __h_quantile1__, __h_median__, __h_mean__, __h_min__, __h_max__, __pixels__)"
    sql_query = "SELECT id, geom FROM carroyage_dfci_2km " #WHERE id in (2347, 2305, 2361, 4606)"   
    query = QtSql.QSqlQuery (sql_query)
#boucle sur chaque carré de la grille !    
    while query.next():
#get the clipped raster with a postgresql query
        str_id = str(query.value("id"))
        sql_grid = "SELECT geom FROM carroyage_dfci_2km WHERE id =" + str_id
        clip_raster = clip_raster_from_query(raster_path1, postgis_connection_string, sql_grid)
        raster_band = clip_raster.GetRasterBand(1)
        raster_data = raster_band.ReadAsArray()
        mask = (raster_data >= 0)
        if len(raster_data[mask]) > 0:
            h_quantile1 = np.quantile(raster_data[mask], 0.25)
            h_median = np.median(raster_data[mask])
            h_mean = raster_data[mask].mean()
            t_pixels = raster_data[mask].size
            h_min = raster_data[mask].min()
            h_max = raster_data[mask].max()

            _query_insert = sql_insert.replace ("__id__", str_id)
            _query_insert = _query_insert.replace ("__h_quantile1__", str(h_quantile1))
            _query_insert = _query_insert.replace ("__h_median__", str(h_median))
            _query_insert = _query_insert.replace ("__h_mean__", str(h_mean))
            _query_insert = _query_insert.replace ("__h_min__", str(h_min))
            _query_insert = _query_insert.replace ("__h_max__", str(h_max))
            _query_insert = _query_insert.replace ("__pixels__", str(t_pixels))
            #_query_insert = _query_insert.replace ("__geom__", query.value("geom"))


            query_insert = QtSql.QSqlQuery()
            query_insert.exec(_query_insert)
            print (str_id, h_min, h_quantile1, h_median, h_mean, h_max, t_pixels)
        # h_median = np.median(raster_data[mask])
        # if h_median < 15:
        #     print (str_id, h_median)

        pixel_count1 = (raster_data >= 15).sum()*10*10
#get_forest_eth_grid()



def get_tmf_grid():
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    # raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/holdrige/holdridge_3classes_wgs84.tif"
    # raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/TMF-TransitionMap-NCL.tif"
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"
   # sql_query = "SELECT geom FROM georep_limites_provinciales_wgs84 WHERE gid =1"
    raster_path1 = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/amap_forest_deforestation123_wgs84.tif"
    raster_path1 = "/home/birnbaum/Documents/Calédonie/Carto/raster_tmf_eth_compress.tif"
    raster_path2 = "/home/birnbaum/Documents/Calédonie/Carto/raster_wgs84.tif"




    #sql_query = "SELECT geom FROM amap_carto_forest3k_wgs84 WHERE id = 8136"    
    sql_query = "SELECT id, geom FROM carroyage_dfci_2km" # WHERE id in (8136, 8140, 8746, 8128)"

    query = QtSql.QSqlQuery (sql_query)
    sql_insert = "INSERT INTO carto.check_grid_tmf (id_grid, forest_area, tmf_area) VALUES (__id__, __forest_area__, __raster_area__ )"
    while query.next():
#get the clipped raster with a postgresql query
        sql_raster = "SELECT geom FROM carroyage_dfci_2km WHERE id =" +str(query.value("id"))
        clip_raster = clip_raster_from_query(raster_path1, postgis_connection_string, sql_raster)
        raster_band = clip_raster.GetRasterBand(1)
        raster_data = raster_band.ReadAsArray()
        # pixel count for values
        pixel_count1 = (raster_data >= 15).sum()*10*10

        clip_raster = clip_raster_from_query(raster_path2, postgis_connection_string, sql_raster)
        raster_band = clip_raster.GetRasterBand(1)
        raster_data = raster_band.ReadAsArray()
        # pixel count for values
        pixel_count2 = (raster_data == 1).sum()*30*30


        if pixel_count1 + pixel_count2 > 0 :
            _query_insert = sql_insert.replace ("__id__", str(query.value("id")))
            _query_insert = _query_insert.replace ("__raster_area__", str(pixel_count1))
            _query_insert = _query_insert.replace ("__forest_area__", str(pixel_count2))
            #QtSql.QSqlQuery (sql_query)
            query_insert = QtSql.QSqlQuery()
            query_insert.exec(_query_insert)
        #print (100*pixel_count1 / query.value("area_m"))
            print (query.value("id"), pixel_count1, pixel_count2)
#get_tmf_grid()







def check_errors_map():
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db):
        sys.exit("error")
    # raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/holdrige/holdridge_3classes_wgs84.tif"
    # raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/TMF-TransitionMap-NCL.tif"
    postgis_connection_string = "PG: dbname=amapiac user='postgres' password='postgres' host=localhost port=5432"
    sql_query = "SELECT geom FROM georep_limites_provinciales_wgs84 WHERE gid =1"
    raster_path = "/home/birnbaum/Documents/Calédonie/Carto/height/ETH_Global_Sentinel2_10m_Canopy_Height.tif"
    #sql_query = "SELECT geom FROM amap_carto_forest3k_wgs84 WHERE id = 8136"    
    sql_query = "SELECT id, geom, st_area(st_transform(geom, 32758)) area_m FROM amap_carto_forest3k_wgs84" # WHERE id in (8136, 8140, 8746, 8128)"
    query = QtSql.QSqlQuery (sql_query)
    sql_insert = "INSERT INTO carto.check_canopy_eth (id_carto, geom_area, low_eth_area) VALUES (__id__, __geom__area, __raster_area__ )"
    while query.next():
#get the clipped raster with a postgresql query
        sql_raster = "SELECT geom FROM amap_carto_forest3k_wgs84 WHERE id =" +str(query.value("id"))
        clip_raster = clip_raster_from_query(raster_path, postgis_connection_string, sql_raster)
        raster_band = clip_raster.GetRasterBand(1)
        raster_data = raster_band.ReadAsArray()
        # pixel count for values
        pixel_count1 = (raster_data <= 6).sum()*8.33*8.33
        if pixel_count1 > 0 :
            _query_insert = sql_insert.replace ("__id__", str(query.value("id")))
            _query_insert = _query_insert.replace ("__geom__area", str(query.value("area_m")))
            _query_insert = _query_insert.replace ("__raster_area__", str(pixel_count1))
            QtSql.QSqlQuery (sql_query)
            query_insert = QtSql.QSqlQuery()
            query_insert.exec(_query_insert)
        #print (100*pixel_count1 / query.value("area_m"))
            print (query.value("id"), query.value("area_m"), pixel_count1, 100*pixel_count1 / query.value("area_m") )









""" 
#get the clipped raster with a postgresql query
clip_raster = clip_raster_from_query(raster_path, postgis_connection_string, sql_query)
#read raster data in Band1
raster_band = clip_raster.GetRasterBand(1)
raster_data = raster_band.ReadAsArray()
# pixel count for values
pixel_count1 = (raster_data <= 6).sum()
# pixel_count2 = (raster_data == 93).sum()
# pixel_count3 = (raster_data == 3).sum()

#pixel_total = (raster_data).sum()
print (pixel_count1*10*10)
 """
# pixel_count, pixel_total = count_pixels_in_clip(raster_path, postgis_connection_string, sql_query)
# print (pixel_count, pixel_total)

""" 
for i in range(1,18):
    sql_query = "SELECT geom FROM georep_limites_communales_wgs84 WHERE gid = " + str(i) #id_province = 1"
    clip_raster = clip_raster_from_query(raster_path, postgis_connection_string, sql_query)
    raster_band = clip_raster.GetRasterBand(1)
    raster_data = raster_band.ReadAsArray()
    pixel_count92 = (raster_data == 92).sum() #np.count_nonzero(raster_data == 92)
    pixel_count93 = (raster_data == 93).sum() #np.count_nonzero(raster_data == 93)
    pixel_total = (raster_data).sum()
    print (i, pixel_count92, pixel_count93, pixel_total)

 """



def raster_filtered(input_raster_path, output_raster_path, values_to_keep):
    #to create a raster from another one filtered on a list of values
    # Exemple d'utilisation
        # input_raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/tmf_transition_pn.tif"
        # output_raster_path = "/home/birnbaum/Documents/Calédonie/Carto/analyse/deforestation/tmf_regeneration2_pn.tif"
        # values_to_keep = [92, 93]
        # raster_filtered(input_raster_path, output_raster_path, values_to_keep)
    # Ouvrir le raster d'entrée
    input_ds = gdal.Open(input_raster_path, gdal.GA_ReadOnly)
    if input_ds is None:
        print("Impossible d'ouvrir le raster d'entrée.")
        return

    # Lire les données du raster
    input_band = input_ds.GetRasterBand(1)
    input_data = input_band.ReadAsArray()

    # Créer un masque pour les valeurs à conserver
    mask = np.isin(input_data, values_to_keep)

    # Appliquer le masque
    output_data = np.where(mask, input_data, 0)

    # Créer un nouveau raster avec les valeurs filtrées
    driver = gdal.GetDriverByName('GTiff')
    output_ds = driver.Create(output_raster_path, input_ds.RasterXSize, input_ds.RasterYSize, 1, input_band.DataType)
    output_ds.SetProjection(input_ds.GetProjection())
    output_ds.SetGeoTransform(input_ds.GetGeoTransform())

    # Écrire les données dans la nouvelle bande
    output_band = output_ds.GetRasterBand(1)
    output_band.WriteArray(output_data)
    output_band.SetNoDataValue(0)

    # Fermer les datasets
    input_ds = None
    output_ds = None


