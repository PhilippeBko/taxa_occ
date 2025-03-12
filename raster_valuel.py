import os
import time
import numpy as np
from osgeo import gdal, ogr, gdalconst
from PyQt5 import QtSql, QtWidgets
gdal.UseExceptions()


#resize raster_path with the canevas of reference_raster_path
# do not alter value and resolution of raster_path
def extend_raster_to_match_reference(raster_path, reference_raster_path, output_raster_path):
    # Ouvre les rasters
    raster = gdal.Open(raster_path, gdalconst.GA_ReadOnly)
    reference_raster = gdal.Open(reference_raster_path, gdalconst.GA_ReadOnly)

    # Récupère les géotransformations et projections
    geo_transform = raster.GetGeoTransform()
    ref_geo_transform = reference_raster.GetGeoTransform()
    projection = raster.GetProjection()  # On garde la projection du raster source

    pixel_size_x = geo_transform[1]  # Taille du pixel (on garde celle du raster source)
    pixel_size_y = geo_transform[5]  # Taille du pixel (on garde celle du raster source)

    # Dimensions du raster source
    cols_raster = raster.RasterXSize
    rows_raster = raster.RasterYSize

    # Dimensions du raster de référence
    cols_ref = reference_raster.RasterXSize
    rows_ref = reference_raster.RasterYSize

    # Coordonnées géographiques
    x_min_raster = geo_transform[0]
    y_max_raster = geo_transform[3]
    x_max_raster = x_min_raster + cols_raster * pixel_size_x
    y_min_raster = y_max_raster + rows_raster * pixel_size_y

    x_min_ref = ref_geo_transform[0]
    y_max_ref = ref_geo_transform[3]
    x_max_ref = x_min_ref + cols_ref * ref_geo_transform[1]
    y_min_ref = y_max_ref + rows_ref * ref_geo_transform[5]

    # Nouvelle origine alignée sur le raster de référence
    new_x_min = min(x_min_raster, x_min_ref)
    new_y_max = max(y_max_raster, y_max_ref)
    
    # Nouvelle taille en pixels en conservant la résolution du raster source
    new_cols = int((max(x_max_raster, x_max_ref) - new_x_min) / pixel_size_x)
    new_rows = int((new_y_max - min(y_min_raster, y_min_ref)) / abs(pixel_size_y))

    # Crée un raster vide avec la nouvelle taille
    driver = gdal.GetDriverByName('GTiff')
    out_raster = driver.Create(output_raster_path, new_cols, new_rows, 1, gdal.GDT_Float32)
    out_raster.SetGeoTransform((new_x_min, pixel_size_x, 0, new_y_max, 0, pixel_size_y))
    out_raster.SetProjection(projection)

    # Définit une valeur NoData
    no_data_value = -9999  
    band = out_raster.GetRasterBand(1)
    band.SetNoDataValue(no_data_value)

    # Initialise tout le raster avec NoData
    data = np.full((new_rows, new_cols), no_data_value, dtype=np.float32)

    # Lit les données du raster source
    raster_band = raster.GetRasterBand(1)
    raster_data = raster_band.ReadAsArray()

    # Vérifie si une valeur NoData est définie dans l'original
    original_no_data = raster_band.GetNoDataValue()
    if original_no_data is not None:
        raster_data[raster_data == original_no_data] = no_data_value

    # Convertit les coordonnées du raster source en indices de pixels dans la nouvelle grille
    start_x = int((x_min_raster - new_x_min) / pixel_size_x)
    start_y = int((new_y_max - y_max_raster) / abs(pixel_size_y))

    # Insère le raster source dans le raster étendu
    data[start_y:start_y+rows_raster, start_x:start_x+cols_raster] = raster_data

    # Écrit les données dans le raster de sortie
    band.WriteArray(data)
    band.FlushCache()

    print(f"Raster étendu avec succès : {output_raster_path}")

""" 
extend_raster_to_match_reference ('/home/birnbaum/Documents/Calédonie/Carto/analyse/richesse/SSDM-Richness2/ssdm_prob_range_20000m.tif',
                                   '/home/birnbaum/Documents/Calédonie/Carto/MNT/MNT_10m/mnt_10_wgs84.tif', 
                                   '/home/birnbaum/Téléchargements/tmp_richness_reference.tif')
 """



def resize_raster_to_reference(raster_path, reference_raster_path, output_raster_path):
    # Ouvre les rasters
    raster = gdal.Open(raster_path)
    reference_raster = gdal.Open(reference_raster_path)

    # Récupère la géotransformation et la projection du raster de référence
    geo_transform = reference_raster.GetGeoTransform()
    projection = reference_raster.GetProjection()

    # Récupère les dimensions du raster de référence
    cols = reference_raster.RasterXSize
    rows = reference_raster.RasterYSize

    # Crée un fichier de sortie avec les dimensions du raster de référence
    driver = gdal.GetDriverByName('GTiff')
    out_raster = driver.Create(output_raster_path, cols, rows, 1, gdal.GDT_Float32)
    out_raster.SetGeoTransform(geo_transform)
    out_raster.SetProjection(projection)

    # Utilise gdal.ReprojectImage pour redimensionner le raster en préservant les valeurs
    gdal.ReprojectImage(raster, out_raster, None, None, gdal.GRA_NearestNeighbour)

    print(f"Redimensionnement réussi : {output_raster_path}")
# # Exemple d'utilisation
# resize_raster_to_reference("/home/birnbaum/Documents/Calédonie/Carto/MNT/MNT_10m/mnt_10_wgs84.tif", '/home/birnbaum/Téléchargements/tmp_richness_reference.tif', '/home/birnbaum/Téléchargements/tmp_raster_mnt.tif')
# resize_raster_to_reference("/home/birnbaum/Documents/Calédonie/Carto/rainfall/raster_aurehly_1000m_wgs84.tif", '/home/birnbaum/Téléchargements/tmp_richness_reference.tif', '/home/birnbaum/Téléchargements/tmp_raster_rainfall.tif')
# resize_raster_to_reference("/home/birnbaum/Téléchargements/peridotites_wgs84.tif", '/home/birnbaum/Téléchargements/tmp_richness_reference.tif', '/home/birnbaum/Téléchargements/tmp_raster_um.tif')
# resize_raster_to_reference("/home/birnbaum/Documents/Calédonie/Carto/analyse/holdrige/holdridge_3classes_wgs84.tif", '/home/birnbaum/Téléchargements/tmp_richness_reference.tif', '/home/birnbaum/Téléchargements/tmp_raster_holdridge.tif')
# resize_raster_to_reference("/home/birnbaum/Téléchargements/forest_3k.tif", '/home/birnbaum/Téléchargements/tmp_richness_reference.tif', '/home/birnbaum/Téléchargements/tmp_raster_forest.tif')


def shapefile_to_raster(shapefile_path, output_raster_path, reference_raster_path, field_name="ID"):
    # Ouvre le shapefile avec OGR
    shapefile = ogr.Open(shapefile_path)
    layer = shapefile.GetLayer()

    # Ouvre le raster de référence pour récupérer les dimensions et les propriétés géospatiales
    reference_raster = gdal.Open(reference_raster_path)
    geo_transform = reference_raster.GetGeoTransform()
    projection = reference_raster.GetProjection()
    cols = reference_raster.RasterXSize
    rows = reference_raster.RasterYSize

    # Crée le fichier raster de sortie
    driver = gdal.GetDriverByName("GTiff")
    output_raster = driver.Create(output_raster_path, cols, rows, 1, gdal.GDT_Float32)
    output_raster.SetGeoTransform(geo_transform)
    output_raster.SetProjection(projection)

    # Crée une bande et initialise à NoData (par exemple, -9999)
    out_band = output_raster.GetRasterBand(1)
    out_band.SetNoDataValue(-9999)

    # Remplir le raster avec les données du shapefile
    gdal.RasterizeLayer(output_raster, [1], layer, options=["ATTRIBUTE=" + field_name])

    # Assure-toi que tout est bien écrit dans le fichier
    output_raster.FlushCache()
    print(f"Transformation Shapefile vers Raster réussie : {output_raster_path}")
#shapefile_to_raster("/home/birnbaum/Téléchargements/forest_3k.shp", "/home/birnbaum/Téléchargements/forest_3k.tif", "/home/birnbaum/Téléchargements/tmp_richness_reference.tif", "gid")
#shapefile_to_raster("/home/birnbaum/Téléchargements/peridotites_wgs84.shp", "/home/birnbaum/Téléchargements/peridotites_wgs84.tif", "/home/birnbaum/Téléchargements/tmp_richness_reference.tif", "gid")

def align_and_resample_rasters(raster_paths, output_path, raster_ref, integer=True, compression="DEFLATE"):
    # Ouvre le raster de référence pour obtenir les informations de projection et de géotransformation
    reference_raster = gdal.Open(raster_paths[raster_ref])
    geo_transform = reference_raster.GetGeoTransform()
    reference_proj = reference_raster.GetProjection()

    # Récupère les dimensions du raster de référence
    cols = reference_raster.RasterXSize
    rows = reference_raster.RasterYSize

    # Définition des noms des bandes (à adapter selon tes données)
    #band_names = ["Elevation", "Rainfall", "Peridotite", "Holdridge", "Richness", "Fragmentation_meff"]

    # Choix du type de données de sortie
    output_type = gdal.GDT_Int32 if integer else gdal.GDT_Float32

    # Crée un fichier de sortie compressé avec les options de compression
    driver = gdal.GetDriverByName("GTiff")
    out_raster = driver.Create(output_path, cols, rows, len(raster_paths), output_type
                               ,options=["COMPRESS={}".format(compression), "TILED=YES"])  # Ajout de la compression
    out_raster.SetGeoTransform(geo_transform)
    out_raster.SetProjection(reference_proj)

    # Applique la reprojection et le redimensionnement pour chaque raster
    for i, (band_name, raster_path) in enumerate(raster_paths.items()):
        raster = gdal.Open(raster_path)

        # Redimensionne et aligne le raster avec le raster de référence
        resampled_raster = gdal.Warp('', raster, format='MEM',
                                     width=cols, height=rows,
                                     outputType=output_type,
                                     dstNodata=0,
                                     dstSRS=reference_proj,
                                     outputBounds=(
                                         geo_transform[0],  # xMin
                                         geo_transform[3] + geo_transform[5] * rows,  # yMax
                                         geo_transform[0] + geo_transform[1] * cols,  # xMax
                                         geo_transform[3]  # yMin
                                     ),
                                     resampleAlg=gdal.GRA_NearestNeighbour) #GRA_Average, GRA_NearestNeighbour, GRA_Bilinear

        # Récupère la bande du raster redimensionné
        resampled_band = resampled_raster.GetRasterBand(1)

        # Écrit les données dans la bande correspondante du raster de sortie
        out_band = out_raster.GetRasterBand(i + 1)
        out_band.WriteArray(resampled_band.ReadAsArray())

        # Ajouter un nom à la bande
        #if i < len(band_names):
        out_band.SetDescription(band_name)

    # Sauvegarde et libération du fichier raster
    out_raster.FlushCache()
    out_raster = None  # Fermer correctement le fichier

    print(f"Fusion réussie avec compression {compression} : {output_path}")
""" 
#"fragmentation": "/home/birnbaum/Téléchargements/tmp_raster_meff1000m.tif"
#examples

raster_files = {
    "elevation": "/home/birnbaum/Téléchargements/tmp_raster_mnt.tif",
    "rainfall": "/home/birnbaum/Téléchargements/tmp_raster_rainfall.tif",
    "peridotite": "/home/birnbaum/Téléchargements/tmp_raster_um.tif",
    "holdridge": "/home/birnbaum/Téléchargements/tmp_raster_holdridge.tif",
    "richness": "/home/birnbaum/Téléchargements/tmp_richness_reference.tif",
    "forest": "/home/birnbaum/Téléchargements/tmp_raster_forest.tif"    
    }
output_file = "/home/birnbaum/Documents/Calédonie/Carto/raster_fusion_wgs84.tif"
align_and_resample_rasters(raster_files, output_file, "richness")

""" 


#RasterLoader is a class for loading and processing raster data from a given file path. 
class RasterLoader:
    """ 
        RasterLoader is a class for loading and processing raster data from a given file path. 
        It provides methods to load raster bands, obtain pixel values for specific geographic coordinates, 
        and handle raster transformations. 
        The class efficiently reads raster data by using batch processing for pixel retrieval 
        and supports various raster operations through GDAL.
        code exemple:
        raster_path = path to the raster
        raster_loader = RasterLoader(raster_path)
        values_raster = raster_loader.get_value([(166.4356821,-21.8593617)])
        print (values_raster)
        -->[{'longitude': 166.4356821, 'latitude': -21.8593617, 'elevation': 1036, 'rainfall': 2830, 'peridotite': 1, 'holdridge': 3, 'richness': 199, 'forest': 1}]
    """

    def __init__(self, raster_path):
        # Set path and initialize raster attributes
        self.raster_path = raster_path
        self.raster = None
        self.geo_transform = None
        self.bands = {}
        self.load_raster()

    def load_raster(self):
        """
        Load raster bands into a dictionary (self.bands).
        Set a filter to optimize ReadAsArray calls.
        """
        #Try to open the raster_path, raise error if not found or open failed
        if not os.path.exists(self.raster_path):
            raise FileNotFoundError(f"Raster file {self.raster_path} not found.")
        self.raster = gdal.Open(self.raster_path)
        if not self.raster:
            raise RuntimeError("Failed to load the raster.")

        # Get geographic transformation
        self.geo_transform = self.raster.GetGeoTransform()
        if not self.geo_transform:
            raise RuntimeError("Unable to get geographic transformation.")

        # Get raster dimensions
        self.raster_width = self.raster.RasterXSize
        self.raster_height = self.raster.RasterYSize

        # Load each raster band into self.bands
        for i in range(1, self.raster.RasterCount + 1):  
            band = self.raster.GetRasterBand(i)
            try:
                band_name = band.GetDescription().lower()  # Use band description if available
            except Exception:
                band_name = f"band_{i}"
            self.bands[band_name] = band

        if not self.bands:
            raise RuntimeError("No raster bands found.")

    def get_value(self, points):
        """
        Get pixel values for a list of (longitude, latitude) points.
        Uses batch processing for efficiency.
        :param points: a List of tuples (longitude, latitude)
        :return: for any points a list of dictionnary composed with value of each band.
        """
        if not self.geo_transform:
            raise RuntimeError("Raster not properly loaded.")
        
        # Extract geo-transformation parameters
        x_origin, pixel_width, _, y_origin, _, pixel_height = self.geo_transform
        
        # Convert geographic coordinates to pixel indices
        valid_points = []
        results = []        
        for lon, lat in points:
            px = int((lon - x_origin) / pixel_width)
            py = int((lat - y_origin) / pixel_height)
            if 0 <= px < self.raster_width and 0 <= py < self.raster_height:
                valid_points.append((px, py))
                results.append({"longitude": lon, "latitude": lat})
        
        # No valid points found
        if not valid_points:
            return []  

        # Convert valid points to numpy array
        valid_points = np.array(valid_points, dtype=int)

        # Read pixel values from each band and store results
        for band_name, band in self.bands.items():
            arr = band.ReadAsArray()  # Read raster data
            for i, (px, py) in enumerate(valid_points):
                results[i][band_name] = int(arr[py, px]) if arr is not None else None

        return results

















def createConnection(db, dbasename):
    db.setHostName("localhost")
    db.setDatabaseName(dbasename) 
    db.setUserName("postgres")
    db.setPassword("postgres")
    #app2 = QApplication([])
    if not db.open():
        QtWidgets.QMessageBox.critical(None, "Cannot open database",
                             "Unable to open database, check for connection parameters", QtWidgets.QMessageBox.Cancel)
        return False
    return True

# raster_loader = RasterLoader("/home/birnbaum/Documents/Calédonie/Carto/raster_fusion_wgs84.tif")
# print (raster_loader.get_value(166.4356821,-21.8593617))
def set_value_todabase2(niamoto_table):
    if not niamoto_table:
        return False
# # Exemple d'utilisation
    # Initialisation du loader avec le fichier raster
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    if not createConnection(db, "test"):        
        QtWidgets.QMessageBox.critical(None, "Cannot open database",
            "Unable to open database, check for connection parameters", QtWidgets.QMessageBox.Cancel)
        return False

    # db = QtSql.QSqlDatabase.addDatabase("QPSQL")
    # db.setHostName("localhost")
    # db.setDatabaseName("test") 
    # db.setUserName("postgres")
    # db.setPassword("postgres")
    # #app2 = QApplication([])
    # if not db.open():
    #     QtWidgets.QMessageBox.critical(None, "Cannot open database",
    #                             "Unable to open database, check for connection parameters", QtWidgets.QMessageBox.Cancel)
    #     return False
    raster_loader = RasterLoader("/home/birnbaum/Documents/Calédonie/Carto/raster_fusion_wgs84.tif")

    sql_query = f"SELECT ST_AsText(geo_pt) as geo_text FROM {niamoto_table} WHERE geo_pt IS NOT NULL GROUP BY geo_pt"
    query = QtSql.QSqlQuery (sql_query)
    points = []
    while query.next():
        points.append(query.value(0))  # Récupérer les coordonnées géographiques sous forme de POINT(lon lat)
    values_raster = raster_loader.get_value([(float(pt.split()[0].replace('POINT(', '')), float(pt.split()[1].replace(')', ''))) for pt in points])
    i = 0
    row_count = len (values_raster)
    start_time = time.time()
    for points in values_raster:
        
        i +=1
        lon = points["longitude"]
        lat = points["latitude"]
        geo_pt = f"ST_GeomFromText('POINT({lon} {lat})', 4326)"
        elevation = max(0, points["elevation"])
        rainfall = points["rainfall"]
        holdridge = points["holdridge"]
        peridotites = points["peridotite"]
        if holdridge == 0:
            holdridge = 'NULL'
        sql_update = f"UPDATE {niamoto_table} SET elevation = {elevation}, rainfall = {rainfall}, in_um = {peridotites}::boolean, holdridge = {holdridge} WHERE geo_pt = {geo_pt};"
        print (f"Progression : {i}/{row_count}", end="\r")

        time.sleep(0.001)
        query_update = QtSql.QSqlQuery()
        query_update.exec(sql_update)
        
    execution_time = time.time() - start_time
    hours = int(execution_time // 3600)
    minutes = int((execution_time % 3600) // 60)
    seconds = int(execution_time % 60)

    # Affichage au format 00h00m00s
    formatted_time = f"{hours:02d}h{minutes:02d}m{seconds:02d}s"
    print (f"Execution : {i}/{row_count}; Temps d'execution : {formatted_time}")


#set_value_todabase2("niamoto_occurrences")
set_value_todabase2("niamoto_plots")



    
#     return




#     row_count = query.size()
#     i = 1
#     while query.next():
#         geo_pt = query.value("geo_pt")
#         value_raster = raster_loader.get_value(query.value("longitude"), query.value("latitude"))
#         if value_raster is not None:
#             elevation = max(0, value_raster["elevation"])
#             rainfall = value_raster["rainfall"]
#             if value_raster["peridotite"] == 1:
#                 peridotites = True
#             else:
#                 peridotites = False
#             holdridge = value_raster["holdridge"]
#             if holdridge == 0:
#                 holdridge = 'NULL'

#             sql_update = f"UPDATE niamoto_occurrences SET elevation = {elevation}, rainfall = {rainfall}, in_um = {peridotites}, holdridge = {holdridge} WHERE geo_pt = '{geo_pt}'"
#             i += 1
#             # state = round(100*i/row_count, 2)
#             # print (f"Progression : {state}%", end="\r")
#             print (f"Progression : {i}/{row_count}", end="\r")
#             time.sleep(0.001)
#             query_update = QtSql.QSqlQuery()
#             query_update.exec(sql_update)

# 







# def set_value_todabase():
# # # Exemple d'utilisation
# # Initialisation du loader avec le fichier raster

#     db = QtSql.QSqlDatabase.addDatabase("QPSQL")
#     db.setHostName("localhost")
#     db.setDatabaseName("test") 
#     db.setUserName("postgres")
#     db.setPassword("postgres")
#     #app2 = QApplication([])
#     if not db.open():
#         QtWidgets.QMessageBox.critical(None, "Cannot open database",
#                                 "Unable to open database, check for connection parameters", QtWidgets.QMessageBox.Cancel)
#         return False
#     raster_loader = RasterLoader("/home/birnbaum/Documents/Calédonie/Carto/raster_fusion_wgs84.tif")

#     sql_query = "SELECT ST_X(geo_pt) AS longitude, ST_Y(geo_pt) AS latitude, geo_pt FROM niamoto_occurrences WHERE geo_pt IS NOT NULL GROUP BY geo_pt"
#     query = QtSql.QSqlQuery (sql_query)
#     row_count = query.size()
#     i = 1
#     while query.next():
#         geo_pt = query.value("geo_pt")
#         value_raster = raster_loader.get_value(query.value("longitude"), query.value("latitude"))
#         if value_raster is not None:
#             elevation = max(0, value_raster["elevation"])
#             rainfall = value_raster["rainfall"]
#             if value_raster["peridotite"] == 1:
#                 peridotites = True
#             else:
#                 peridotites = False
#             holdridge = value_raster["holdridge"]
#             if holdridge == 0:
#                 holdridge = 'NULL'

#             sql_update = f"UPDATE niamoto_occurrences SET elevation = {elevation}, rainfall = {rainfall}, in_um = {peridotites}, holdridge = {holdridge} WHERE geo_pt = '{geo_pt}'"
#             i += 1
#             # state = round(100*i/row_count, 2)
#             # print (f"Progression : {state}%", end="\r")
#             print (f"Progression : {i}/{row_count}", end="\r")
#             time.sleep(0.001)
#             query_update = QtSql.QSqlQuery()
#             query_update.exec(sql_update)

# #set_value_todabase()
