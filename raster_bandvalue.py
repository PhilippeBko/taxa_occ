import os
from osgeo import gdal
gdal.UseExceptions()




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
        :return: for any points a list of dictionaries with values of each band.
        """
        if not self.geo_transform:
            raise RuntimeError("Raster not properly loaded.")

        # Extract geo-transformation parameters
        x_origin, pixel_width, _, y_origin, _, pixel_height = self.geo_transform

        # Convert geographic coordinates to pixel indices
        results = []  
        valid_points = []
        
        for lon, lat in points:
            px = int((lon - x_origin) / pixel_width)
            py = int((lat - y_origin) / pixel_height)
            if 0 <= px < self.raster_width and 0 <= py < self.raster_height:
                valid_points.append((px, py))
                results.append({"longitude": lon, "latitude": lat})

        # No valid points found
        if not valid_points:
            return []  

        # Read pixel values from each band and store results
        for band_name, band in self.bands.items():
            arr = band.ReadAsArray()  # Read raster data
            for i, (px, py) in enumerate(valid_points):
                results[i][band_name] = int(arr[py, px]) if arr is not None else None

        return results


""" 
# example
raster_loader = RasterLoader("PATH/raster_fusion_wgs84.tif")
print (raster_loader.get_value([(165.1116333, -21.13367271), (165.00839233, -20.85251427)]))

 """