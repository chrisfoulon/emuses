#!/usr/bin/env python3
"""
Generate workshop figures for language deficit (Langage M12) disconnection profiles.

Output: ~/Téléchargements/language_figure/
  - umap_language_profiles.png : correlation heatmap with 3 cluster overlays
  - effect_map_cluster_X_*.png : one axial slice per cluster, positive only, no title
"""

import json
import sys
import warnings
from pathlib import Path

import nibabel as nib
from sklearn.cluster import HDBSCAN
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from nilearn import plotting as nlplot

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── paths ──────────────────────────────────────────────────────────────────────
BASTION  = Path("/home/chrisfoulon/remote_folders/bastion/DSD_repro/june_2026")
TARGET4  = BASTION / "target_4"
OUT_DIR  = Path("/home/chrisfoulon/Téléchargements/language_figure")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── cluster definitions (re-cluster IDs from high-sig region) ─────────────────
CLUSTERS = {
    0: dict(label="Profile A", short="Arcuate F. + SLF II",     color="#4e79a7", z_cut=34,  threshold=0.15),
    3: dict(label="Profile B", short="IFOF + ILF + Arcuate F.", color="#f28e2b", z_cut=-18, threshold=0.20),
    4: dict(label="Profile C", short="SLF II–III + Arcuate F.", color="#59a14f", z_cut=36,  threshold=0.15),
}

# ── load training embeddings (149 labelled subjects projected into UMAP space) ─
train_emb = np.load("/tmp/train_labelled_embeddings.npy")   # (149, 2), scaled [0,1]

# ── reproduce the high-sig re-clustering (same as region_statistical_analyzer) ──
high_sig_idx = np.load(TARGET4 / "correlation-effects" / "high_significance_regions.npy")
high_sig_coords = train_emb[high_sig_idx]   # (36, 2)

clusterer = HDBSCAN(min_cluster_size=3, min_samples=1)
recluster_labels = clusterer.fit_predict(high_sig_coords)
print(f"Re-cluster labels: {np.unique(recluster_labels)}")

# ── load correlation heatmap ───────────────────────────────────────────────────
pearson = np.load(TARGET4 / "correlation-heatmaps" / "correlation_values_pearson.npy")

# ── 1. UMAP figure with all 3 clusters ────────────────────────────────────────
grid_size = 100
correlation_grid = pearson.reshape(grid_size, grid_size)
vmax = max(abs(pearson.min()), abs(pearson.max()))

fig, ax = plt.subplots(figsize=(10, 8))

im = ax.imshow(
    correlation_grid.T,
    cmap="RdBu_r",
    interpolation="nearest",
    origin="lower",
    extent=[0, 1, 0, 1],
    alpha=0.6,
    vmin=-vmax,
    vmax=vmax,
)
cbar = plt.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label("Pearson Correlation", rotation=270, labelpad=20)

# Grey dots = all 149 labelled training subjects
ax.scatter(train_emb[:, 0], train_emb[:, 1],
           c="lightgrey", s=15, alpha=0.5, zorder=2)

# Coloured dots = re-clustered high-sig subjects
for cid, info in CLUSTERS.items():
    mask = recluster_labels == cid
    if not mask.any():
        print(f"WARNING: no subjects found for re-cluster {cid}")
        continue
    coords = high_sig_coords[mask]
    ax.scatter(
        coords[:, 0], coords[:, 1],
        c=info["color"], s=80, alpha=0.95, zorder=5,
        edgecolors="white", linewidths=0.8,
        label=f"{info['label']}  ({info['short']},  n={mask.sum()})",
    )

ax.set_xlabel("UMAP Dimension 1")
ax.set_ylabel("UMAP Dimension 2")
ax.set_title("Correlation heatmap — Langage M12 (Pearson) with language deficit profiles")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.set_aspect("equal")
ax.legend(loc="upper left", fontsize=9, framealpha=0.7)

umap_out = OUT_DIR / "umap_language_profiles.png"
fig.savefig(umap_out, dpi=200)
plt.close(fig)
print(f"Saved: {umap_out}")

# ── 2. Effect size maps — one axial slice, positive only, no title ─────────────
all_pos = []
for cid in CLUSTERS:
    d = nib.load(
        TARGET4 / "correlation-effects" / f"effect_size_map_target_4_cluster_{cid}_high_{cid}.nii.gz"
    ).get_fdata()
    all_pos.extend(d[np.isfinite(d) & (d > 0)].tolist())
vmax_global = float(np.percentile(all_pos, 98))
print(f"Effect size vmax (98th pct): {vmax_global:.3f}")

for cid, info in CLUSTERS.items():
    nii_path = TARGET4 / "correlation-effects" / f"effect_size_map_target_4_cluster_{cid}_high_{cid}.nii.gz"
    img = nib.load(nii_path)
    d = img.get_fdata().copy()
    d[~np.isfinite(d) | (d <= 0)] = np.nan
    pos_img = nib.Nifti1Image(d, img.affine, img.header)

    display = nlplot.plot_stat_map(
        pos_img,
        threshold=info["threshold"],
        vmax=vmax_global,
        display_mode="z",
        cut_coords=[info["z_cut"]],
        cmap="hot",
        colorbar=True,
        black_bg=True,
        title=None,
    )

    eff_out = OUT_DIR / f"effect_map_cluster_{cid}_{info['label'].replace(' ', '_')}.png"
    display.savefig(str(eff_out), dpi=200)
    plt.close("all")
    print(f"Saved: {eff_out}")

print(f"\nAll figures saved to {OUT_DIR}")
