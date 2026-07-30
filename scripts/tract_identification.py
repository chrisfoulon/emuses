#!/usr/bin/env python3
"""
Tract identification from effect size maps using the Rojkova WM atlas.

For each effect size map NIfTI in an input folder:
  1. Threshold to positive voxels → binary mask
  2. Compute overlap with each Rojkova tract (probability maps)
  3. Report: % of mask covered by tract AND % of tract covered by mask

Usage:
    python scripts/tract_identification.py <effects_folder> [options]

Example:
    python scripts/tract_identification.py \\
        /home/chrisfoulon/remote_folders/bastion/target_4/correlation-effects \\
        --output /home/chrisfoulon/remote_folders/bastion/target_4/tract_identification
"""

import argparse
import csv
from pathlib import Path

import nibabel as nib
import numpy as np
from nilearn.image import resample_to_img

ROJKOVA_DIR = Path("/home/chrisfoulon/.bcblib/atlases/rojkova/Tracts")


def load_positive_mask(nii_path: Path, effect_threshold: float = 0.0) -> tuple:
    """Return (binary mask array, reference NIfTI image)."""
    img = nib.load(nii_path)
    data = img.get_fdata()
    mask = np.isfinite(data) & (data > effect_threshold)
    return mask, img


def tract_name_from_path(path: Path) -> str:
    return path.stem.replace(".nii", "").replace("_", " ")


def compute_rojkova_overlaps(
    mask: np.ndarray,
    ref_img: nib.Nifti1Image,
    tract_dir: Path,
    min_mask_pct: float = 1.0,
    tract_prob_threshold: float = 0.1,
) -> list[dict]:
    """
    Compute overlap between binary mask and each Rojkova tract.

    For each tract:
    - mask_pct: % of mask voxels that fall within the tract
    - tract_pct: % of the tract volume (above prob threshold) covered by mask

    Returns list of dicts sorted by mask_pct descending.
    """
    n_mask = mask.sum()
    if n_mask == 0:
        return []

    results = []
    tract_files = sorted(tract_dir.glob("*.nii.gz"))

    for tract_path in tract_files:
        # Resample tract probability map to effect size map space
        tract_img = nib.load(tract_path)
        tract_r = resample_to_img(
            tract_img, ref_img, interpolation="linear",
            force_resample=True, copy_header=True
        )
        tract_data = tract_r.get_fdata()

        # Binary tract mask at probability threshold
        tract_bin = tract_data >= tract_prob_threshold
        n_tract = tract_bin.sum()
        if n_tract == 0:
            continue

        # Overlap
        overlap = mask & tract_bin
        n_overlap = overlap.sum()

        mask_pct = 100.0 * n_overlap / n_mask
        tract_pct = 100.0 * n_overlap / n_tract

        if mask_pct >= min_mask_pct:
            results.append({
                "tract": tract_name_from_path(tract_path),
                "mask_pct": round(mask_pct, 2),
                "tract_pct": round(tract_pct, 2),
                "overlap_voxels": int(n_overlap),
                "tract_voxels": int(n_tract),
            })

    results.sort(key=lambda x: x["mask_pct"], reverse=True)
    return results


def analyse_folder(
    effects_folder: Path,
    output_dir: Path,
    min_mask_pct: float = 1.0,
    effect_threshold: float = 0.0,
    tract_prob_threshold: float = 0.1,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    masks_dir = output_dir / "positive_masks"
    masks_dir.mkdir(exist_ok=True)

    nii_files = sorted(effects_folder.glob("effect_size_map*.nii.gz"))
    if not nii_files:
        print(f"No effect_size_map*.nii.gz files in {effects_folder}")
        return

    all_rows = []

    for nii_path in nii_files:
        mask, ref_img = load_positive_mask(nii_path, effect_threshold)
        n_positive = mask.sum()

        if n_positive == 0:
            print(f"[SKIP] {nii_path.name}: no voxels above {effect_threshold}")
            continue

        # Save binary mask
        mask_img = nib.Nifti1Image(mask.astype(np.uint8), ref_img.affine, ref_img.header)
        nib.save(mask_img, masks_dir / nii_path.name.replace(".nii.gz", "_mask.nii.gz"))

        results = compute_rojkova_overlaps(
            mask, ref_img, ROJKOVA_DIR,
            min_mask_pct=min_mask_pct,
            tract_prob_threshold=tract_prob_threshold,
        )

        print(f"\n{'='*72}")
        print(f"  {nii_path.name}  [positive voxels: {n_positive}]")
        print(f"{'='*72}")
        if results:
            print(f"  {'Tract':<52} {'Mask%':>6}  {'Tract%':>6}  {'Voxels':>7}")
            print(f"  {'-'*52} {'-'*6}  {'-'*6}  {'-'*7}")
            for r in results:
                print(f"  {r['tract']:<52} {r['mask_pct']:>5.1f}%  {r['tract_pct']:>5.1f}%  {r['overlap_voxels']:>7}")
        else:
            print("  No Rojkova tracts above threshold.")

        for r in results:
            all_rows.append({
                "map": nii_path.name,
                "positive_voxels": n_positive,
                **r,
            })

    csv_path = output_dir / "rojkova_tract_overlaps.csv"
    if all_rows:
        fieldnames = ["map", "positive_voxels", "tract", "mask_pct",
                      "tract_pct", "overlap_voxels", "tract_voxels"]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nResults saved to {csv_path}")
        print(f"Binary masks saved to {masks_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("effects_folder", type=Path,
                        help="Folder with effect_size_map*.nii.gz files")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output dir (default: <effects_folder>/../tract_identification)")
    parser.add_argument("--min-mask-pct", type=float, default=1.0,
                        help="Min %% of mask covered by tract to show (default: 1.0)")
    parser.add_argument("--effect-threshold", type=float, default=0.0,
                        help="Effect size threshold for positive mask (default: 0)")
    parser.add_argument("--tract-prob-threshold", type=float, default=0.1,
                        help="Probability threshold for Rojkova tracts (default: 0.1)")
    args = parser.parse_args()

    effects_folder = args.effects_folder.resolve()
    output_dir = args.output or effects_folder.parent / "tract_identification"

    print(f"Input:  {effects_folder}")
    print(f"Output: {output_dir}")
    print(f"Effect threshold: {args.effect_threshold}")
    print(f"Min mask coverage: {args.min_mask_pct}%")

    analyse_folder(
        effects_folder, output_dir,
        min_mask_pct=args.min_mask_pct,
        effect_threshold=args.effect_threshold,
        tract_prob_threshold=args.tract_prob_threshold,
    )


if __name__ == "__main__":
    main()
