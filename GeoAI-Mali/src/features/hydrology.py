"""Hydrologie du terrain : accumulation d'écoulement et indice d'humidité topographique (TWI).

Objectif : mesurer OÙ L'EAU CONVERGE, ce que ne voient ni la distance au fleuve, ni la hauteur,
ni la pente. Une cuvette recevant le ruissellement de quartiers plus hauts a une forte
accumulation même si elle est loin du fleuve.

Étapes (algorithmes classiques, implémentés ici en NumPy) :
1. Remplissage des dépressions (Priority-Flood avec epsilon, Barnes et al. 2014) : les creux
   fermés du DEM sont comblés pour que l'eau puisse toujours s'écouler vers la sortie.
2. Direction d'écoulement D8 : chaque pixel s'écoule vers son voisin (8 directions) de plus
   forte pente descendante.
3. Accumulation : nombre de pixels (lui compris) qui s'écoulent à travers chaque pixel.
4. TWI = ln( a / tan(pente) ), avec a = accumulation x résolution (aire drainée par unité de
   largeur de contour). Plus le TWI est élevé, plus l'eau a tendance à s'accumuler et à stagner.

Entrées : data/processed/dem_bamako_utm.tif   (python -m src.features.terrain)
Lancement depuis la racine du projet :
    python -m src.features.hydrology
Résultats :
    data/processed/flow_accumulation_utm.tif   (nombre de pixels drainés)
    data/processed/twi_utm.tif
    outputs/figures/hydrology_bamako.png

Limites à rappeler dans le mémoire :
- Le Copernicus DEM est un modèle de SURFACE : bâtiments, arbres et ponts créent de faux
  barrages et de faux creux. Le remplissage en comble beaucoup en ville, et l'écoulement D8
  peut dévier le long de rues ou de bâtiments qui n'existent pas pour l'eau réelle.
- La fenêtre d'étude est coupée : l'eau qui entre par l'amont n'est pas comptée (le Niger arrive
  de l'ouest), donc l'accumulation le long du fleuve ne compte que les apports locaux.
- Aucun réseau de drainage artificiel (caniveaux, collecteurs) n'est modélisé.
- La pente est bornée à 0,5° pour éviter des TWI infinis sur les zones plates.
"""

import heapq
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
DEM_UTM = ROOT / "data" / "processed" / "dem_bamako_utm.tif"
ACC_OUT = ROOT / "data" / "processed" / "flow_accumulation_utm.tif"
TWI_OUT = ROOT / "data" / "processed" / "twi_utm.tif"
FIGURE = ROOT / "outputs" / "figures" / "hydrology_bamako.png"

# 8 voisins : N, NE, E, SE, S, SO, O, NO (décalage ligne, colonne)
D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
D8_DIST = [1.0, 2**0.5, 1.0, 2**0.5, 1.0, 2**0.5, 1.0, 2**0.5]
MIN_SLOPE_DEG = 0.5


def fill_depressions(dem, epsilon=1e-3):
    """Priority-Flood + epsilon : comble les creux fermés et rend chaque pixel drainable.

    Les pixels de bord (bord de l'image ou voisins d'un pixel sans donnée) sont les exutoires.
    Après remplissage, chaque pixel a un voisin strictement plus bas, sauf les exutoires.
    """
    h, w = dem.shape
    z = dem.astype("float64")
    valid = ~np.isnan(z)

    interior = ndimage.binary_erosion(valid, structure=np.ones((3, 3), bool), border_value=0)
    seeds = valid & ~interior

    zl = np.nan_to_num(z, nan=0.0).ravel().tolist()
    filled = list(zl)
    closed = bytearray((~valid).ravel().astype("uint8").tolist())
    heap = []
    for i in np.flatnonzero(seeds.ravel()).tolist():
        closed[i] = 1
        heap.append((zl[i], i))
    heapq.heapify(heap)

    pop, push = heapq.heappop, heapq.heappush
    while heap:
        zc, i = pop(heap)
        r, c = divmod(i, w)
        for dr, dc in D8:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                j = rr * w + cc
                if not closed[j]:
                    closed[j] = 1
                    zn = zl[j]
                    if zn <= zc:
                        zn = zc + epsilon
                    filled[j] = zn
                    push(heap, (zn, j))

    out = np.array(filled, dtype="float64").reshape(h, w)
    out[~valid] = np.nan
    return out


def flow_direction(filled, res):
    """Direction D8 (indice 0 à 7 dans la liste D8) ; -1 pour un exutoire ou une cellule vide."""
    h, w = filled.shape
    padded = np.pad(filled, 1, constant_values=np.nan)
    best = np.zeros(filled.shape)
    code = np.full(filled.shape, -1, dtype="int8")
    for k, (dr, dc) in enumerate(D8):
        neighbour = padded[1 + dr : 1 + dr + h, 1 + dc : 1 + dc + w]
        with np.errstate(invalid="ignore"):
            drop = (filled - neighbour) / (res * D8_DIST[k])
            better = drop > best
        code[better] = k
        best[better] = drop[better]
    code[np.isnan(filled)] = -1
    return code


def flow_accumulation(direction, filled):
    """Nombre de pixels (lui compris) qui s'écoulent à travers chaque pixel."""
    h, w = direction.shape
    valid = ~np.isnan(filled)

    rows, cols = np.indices(direction.shape)
    dr = np.array([0] + [d[0] for d in D8])[direction + 1]
    dc = np.array([0] + [d[1] for d in D8])[direction + 1]
    down = np.where(direction >= 0, (rows + dr) * w + (cols + dc), -1).ravel().tolist()

    # On traite les pixels du plus haut au plus bas : l'aval est toujours plus bas (epsilon).
    order = np.argsort(-np.nan_to_num(filled, nan=-np.inf).ravel(), kind="stable").tolist()
    acc = valid.astype("float64").ravel().tolist()
    for i in order:
        d = down[i]
        if d >= 0:
            acc[d] += acc[i]
    out = np.array(acc, dtype="float64").reshape(h, w)
    out[~valid] = np.nan
    return out


def twi(acc, slope_deg, res, min_slope_deg=MIN_SLOPE_DEG):
    """TWI = ln(a / tan(pente)) ; a = accumulation x résolution (m)."""
    tan_beta = np.tan(np.radians(np.maximum(slope_deg, min_slope_deg)))
    return np.log((acc * res) / tan_beta).astype("float32")


def run():
    from src.features.terrain import slope_degrees  # importé ici : terrain.py a ses propres dépendances

    with rasterio.open(DEM_UTM) as src:
        dem = src.read(1)
        profile = src.profile.copy()
        res = abs(src.transform.a)

    print("Remplissage des dépressions (peut prendre 20 à 60 s)…")
    filled = fill_depressions(dem)
    raised = filled - dem
    print(f"Pixels relevés de plus de 0,5 m par le remplissage : {100 * np.nanmean(raised > 0.5):.1f} % "
          f"(max {np.nanmax(raised):.1f} m)")

    direction = flow_direction(filled, res)
    print("Calcul de l'accumulation…")
    acc = flow_accumulation(direction, filled)
    slope = slope_degrees(dem, res)
    wetness = twi(acc, slope, res)

    profile.update(dtype="float32", nodata=np.nan)
    for path, arr in ((ACC_OUT, acc.astype("float32")), (TWI_OUT, wetness)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(arr, 1)

    print(f"Accumulation : médiane {np.nanmedian(acc):.0f} pixels | max {np.nanmax(acc):.0f} pixels "
          f"(= {np.nanmax(acc) * res**2 / 1e6:.0f} km²)")
    print(f"TWI : médiane {np.nanmedian(wetness):.1f} | percentiles 5/95 : "
          f"{np.nanpercentile(wetness, 5):.1f} / {np.nanpercentile(wetness, 95):.1f}")

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    im0 = axes[0].imshow(np.log10(acc), cmap="Blues")
    axes[0].set_title("Accumulation d'écoulement (log10 du nombre de pixels)")
    fig.colorbar(im0, ax=axes[0], shrink=0.8)
    lo, hi = np.nanpercentile(wetness, [2, 98])
    im1 = axes[1].imshow(wetness, cmap="YlGnBu", vmin=lo, vmax=hi)
    axes[1].set_title("Indice d'humidité topographique (TWI)")
    fig.colorbar(im1, ax=axes[1], shrink=0.8)
    for ax in axes:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    print(f"Figure enregistrée : {FIGURE}")


if __name__ == "__main__":
    run()
