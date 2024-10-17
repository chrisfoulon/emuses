from pathlib import Path
import nibabel as nib
import pandas as pd
import matplotlib.pyplot as plt

from tools.visualisation import plot_statistical_map


def save_statistical_maps(stat_maps, output_folder, input_type, output_format_info, filename_prefix='stat_map'):
    """
    Save statistical maps in the format matching the input type.

    Parameters:
    - stat_maps: dict
        A dictionary containing statistical maps for each cluster.
    - output_folder: str or Path
        The folder where the statistical maps will be saved.
    - input_type: str
        The type of input data. Options are 'nifti', 'image', 'spreadsheet'.
    - output_format_info: various
        Information needed to format the output. Could be an affine matrix (for NIfTI),
        an output shape (for images), or a list of column names (for spreadsheets).
    - filename_prefix: str, optional
        The prefix for the output filenames. Default is 'stat_map'.

    Returns:
    None
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    for cluster, stat_map in stat_maps.items():
        if input_type == 'nifti':
            # Extract shape from affine matrix
            output_shape = nib.aff2axcodes(output_format_info)
            # Save as NIfTI file
            stat_image = stat_map.reshape(output_shape)
            nifti_img = nib.Nifti1Image(stat_image, output_format_info)
            filename = output_folder / f"{filename_prefix}_cluster_{cluster}.nii.gz"
            nib.save(nifti_img, filename)
        elif input_type == 'image':
            # Save as image file (e.g., PNG)
            output_shape = output_format_info
            stat_image = stat_map.reshape(output_shape)
            filename = output_folder / f"{filename_prefix}_cluster_{cluster}.png"
            plot_statistical_map(stat_image, title=f'Effect Size Map for Cluster {cluster}', save_path=filename)
        elif input_type == 'spreadsheet':
            # Save as CSV file
            columns = output_format_info
            num_rows = len(stat_map) // len(columns)
            df = pd.DataFrame(stat_map.reshape((num_rows, len(columns))), columns=columns)
            filename = output_folder / f"{filename_prefix}_cluster_{cluster}.csv"
            df.to_csv(filename, index=False)
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

    print(f"Statistical maps saved in {output_folder}/{filename_prefix}_cluster_*.{input_type}")