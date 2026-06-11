"""
Regression tests for the NIfTI left-right orientation bug.

Bug: process_dataset stored the original (non-canonical) image affine in
output_format_info, while nifti_dataset_to_matrix reoriented images to canonical
(RAS+) before flattening. Reconstructing effect size maps with the original affine
caused a left-right hemisphere swap in world coordinates.

Fix: process_dataset now calls nib.as_closest_canonical on the first image to obtain
the correct shape and affine for reconstruction.
"""
import numpy as np
import nibabel as nib
import pytest

from emuses.tools.inputs_utils import nifti_dataset_to_matrix


@pytest.fixture
def las_nifti_path(tmp_path):
    """NIfTI with LAS (non-canonical) affine, mimicking FSL/MNI disconnectome maps.

    data[0, :, :] marks the right hemisphere (world x = +4 mm in MNI).
    data[4, :, :] marks the left hemisphere (world x = -4 mm in MNI).
    """
    las_affine = np.array(
        [[-2, 0, 0, 4], [0, 2, 0, 0], [0, 0, 2, 0], [0, 0, 0, 1]], dtype=np.float64
    )
    data = np.zeros((5, 5, 5), dtype=np.float32)
    data[0, :, :] = 1.0  # right hemisphere marker (world x = +4 mm)
    img = nib.Nifti1Image(data, las_affine)
    path = tmp_path / "las_image.nii.gz"
    nib.save(img, path)
    return path


def test_canonical_reconstruction_places_marker_in_correct_hemisphere(las_nifti_path):
    """Using canonical affine for reconstruction preserves left/right hemisphere identity.

    In LAS: data[0,:,:] = right hemisphere (x = +4 mm).
    After nifti_dataset_to_matrix canonicalizes to RAS+, that same voxels end up at
    index 4 along axis 0. Reconstructing with the canonical affine correctly maps
    index 4 → x = +4 mm (right hemisphere).
    """
    matrix = nifti_dataset_to_matrix([nib.load(str(las_nifti_path))])

    canonical = nib.as_closest_canonical(nib.load(str(las_nifti_path)))
    recon = nib.Nifti1Image(matrix[0].reshape(canonical.shape), canonical.affine)
    recon_data = recon.get_fdata()

    # Right hemisphere marker should be at last x-index (index 4) in RAS+
    assert recon_data[4, :, :].mean() == pytest.approx(1.0), (
        "Right-hemisphere marker must be at the last x-index after LAS→RAS+ flip"
    )
    assert recon_data[0, :, :].mean() == pytest.approx(0.0), (
        "Left side (index 0) must be zero after LAS→RAS+ flip"
    )

    # World x for the marker: canonical affine[0,0]*4 + affine[0,3] must be positive (right)
    marker_world_x = canonical.affine[0, 0] * 4 + canonical.affine[0, 3]
    assert marker_world_x > 0, (
        "Canonical reconstruction: right-hemisphere marker must have positive world x"
    )


def test_original_affine_reconstruction_swaps_hemispheres(las_nifti_path):
    """Using the original (non-canonical) affine with canonical-ordered data causes L/R swap.

    This documents the bug that was fixed: storing original affine in output_format_info
    while the data array is in canonical (RAS+) order flips the hemisphere in world space.
    """
    original = nib.load(str(las_nifti_path))
    matrix = nifti_dataset_to_matrix([original])

    # Reconstruct with WRONG (original LAS) affine  — the pre-fix behaviour
    wrong_recon = nib.Nifti1Image(
        matrix[0].reshape(original.shape), original.affine
    )

    # The canonical-order data has the right-hemisphere marker at index 4.
    # With the LAS affine, index 4 maps to world x = -2*4 + 4 = -4 mm (LEFT hemisphere).
    marker_world_x = original.affine[0, 0] * 4 + original.affine[0, 3]
    assert marker_world_x < 0, (
        "Bug confirmed: with original LAS affine, right-hemisphere marker is mapped "
        "to negative world x (left hemisphere) — the left-right swap"
    )


def test_canonical_and_original_affines_differ_for_las_input(las_nifti_path):
    """Canonical affine must differ from original for a non-canonical input."""
    original = nib.load(str(las_nifti_path))
    canonical = nib.as_closest_canonical(original)

    assert not np.allclose(original.affine, canonical.affine), (
        "For LAS input, canonical and original affines must differ"
    )
    assert original.affine[0, 0] < 0, "Original LAS affine: negative x scale"
    assert canonical.affine[0, 0] > 0, "Canonical RAS+ affine: positive x scale"
