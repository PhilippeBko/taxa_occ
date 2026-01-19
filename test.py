import matplotlib.pyplot as plt
import contextily as ctx
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate
from matplotlib.patches import Circle, Polygon as MplPolygon

def snapshot_parcelle(
    lat,
    lon,
    mode="point",        # "point" | "circle" | "rectangle"
    radius=None,         # mètres (circle)
    length=None,         # mètres (rectangle)
    width=None,          # mètres (rectangle)
    angle=0,             # degrés depuis le nord
    margin=50,           # marge autour de la parcelle (m)
    output="snapshot.png"
):
    # Projection GPS → mètres
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x, y = to_m.transform(lon, lat)

    fig, ax = plt.subplots(figsize=(6, 6))

    # Définition emprise
    extent = max(
        radius or 0,
        length or 0,
        width or 0
    ) / 2 + margin

    ax.set_xlim(x - extent, x + extent)
    ax.set_ylim(y - extent, y + extent)

    # Fond Esri
    ctx.add_basemap(
        ax,
        source=ctx.providers.Bing.Aerial,
        crs="EPSG:3857"
    )

    # Cas 1 : point
    if mode == "point":
        ax.plot(x, y, "ro", markersize=6)

    # Cas 2 : cercle
    elif mode == "circle":
        circle = Circle((x, y), radius, edgecolor="red", fill=False, linewidth=2)
        ax.add_patch(circle)

    # Cas 3 : rectangle orienté
    elif mode == "rectangle":
        rect = Polygon([
            (-length/2, -width/2),
            ( length/2, -width/2),
            ( length/2,  width/2),
            (-length/2,  width/2)
        ])
        rect = rotate(rect, angle, origin=(0, 0))
        rect = translate(rect, xoff=x, yoff=y)

        mpl_rect = MplPolygon(
            list(rect.exterior.coords),
            edgecolor="blue",
            fill=False,
            linewidth=2
        )
        ax.add_patch(mpl_rect)

    else:
        raise ValueError("mode inconnu")

    ax.set_aspect("equal")
    ax.axis("off")

    plt.savefig(output, dpi=200, bbox_inches="tight")
    plt.close()


#snapshot_parcelle(-21.17780113, 165.27731323, mode="point")
snapshot_parcelle(
    -21.17780113, 165.27731323,
    mode="rectangle",
    length=100,
    width=100,
    angle=30
)
