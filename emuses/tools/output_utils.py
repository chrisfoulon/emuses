from pathlib import Path
import nibabel as nib
import pandas as pd
import matplotlib.pyplot as plt
from nilearn.plotting import plot_stat_map
import plotly.express as px

from emuses.tools.visualisation import plot_statistical_map, plot_spreadsheet_stat_map


def save_statistical_maps(
    stat_maps, output_folder, input_type, output_format_info,
    filename_prefix='stat_map', save_output=True, generate_plots=False
):
    """
    Save statistical maps in the format matching the input type, and optionally generate plots.

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
    - save_output: bool, optional
        Whether to save the output files. Default is True.
    - generate_plots: bool, optional
        Whether to generate and return plots of the statistical maps. Default is False.

    Returns:
    - plots: dict
        A dictionary containing plots for each cluster (only if generate_plots is True).
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    plots = {} if generate_plots else None

    for cluster, stat_map in stat_maps.items():
        if input_type == 'nifti':
            # For NIfTI, output_format_info is a tuple of (output_shape, affine)
            output_shape, affine = output_format_info
            stat_image = stat_map.reshape(output_shape)
            nifti_img = nib.Nifti1Image(stat_image, affine)

            # Generate the plot once
            display = plot_stat_map(nifti_img, title=f'Effect Size Map for Cluster {cluster}')
            fig = display.figure

            if save_output:
                # Save the NIfTI file
                nifti_filename = output_folder / f"{filename_prefix}_cluster_{cluster}.nii.gz"
                nib.save(nifti_img, nifti_filename)
                # Save the plot as PNG
                png_filename = output_folder / f"{filename_prefix}_cluster_{cluster}.png"
                fig.savefig(png_filename)
                print(f"Saved NIfTI image and plot for cluster {cluster}.")

            if generate_plots:
                plots[cluster] = fig

            # Close the figure to free memory
            plt.close(fig)

        elif input_type == 'image' or input_type == 'mnist':
            # For images, output_format_info is the output shape
            output_shape = output_format_info
            stat_image = stat_map.reshape(output_shape)

            # Use the provided plot_statistical_map function
            plot_title = f'Effect Size Map for Cluster {cluster}'
            save_path = None
            if save_output:
                save_path = output_folder / f"{filename_prefix}_cluster_{cluster}.png"

            fig = plot_statistical_map(
                data=stat_image,
                title=plot_title,
                save_path=save_path,
                show_plot=False,
                return_plot=generate_plots
            )

            if generate_plots:
                plots[cluster] = fig



        elif input_type == 'spreadsheet':

            # For spreadsheets, output_format_info is the list of column names

            columns = output_format_info

            df = pd.DataFrame([stat_map], columns=columns)

            # Save the DataFrame to CSV

            if save_output:
                csv_filename = output_folder / f"{filename_prefix}_cluster_{cluster}.csv"

                df.to_csv(csv_filename, index=False)

                print(f"Saved CSV for cluster {cluster}.")

            # Convert to long format for bar chart

            df_long = df.melt(var_name='Feature', value_name='Effect Size')

            # For demonstration, let's pick orientation='h' and interactive=False by default

            # or you can parametrize these choices.

            bar_output_path = None

            if save_output:
                # We'll produce a static PNG in this example

                bar_output_path = output_folder / f"{filename_prefix}_cluster_{cluster}.png"

            fig = plot_spreadsheet_stat_map(

                df_long=df_long,

                cluster=cluster,

                output_path=bar_output_path,

                orientation='h',  # horizontal

                interactive=True,

                width=1200,

                height=None,  # auto-based on number of features

                title=f'Effect Size Map for Cluster {cluster}',

                show_plot=False,  # or True if you want to see it pop up

                return_plot=generate_plots

            )

            if generate_plots and fig is not None:
                plots[cluster] = fig

            # No need to close Plotly figures

        else:
            raise ValueError(f"Unsupported input type: {input_type}")

    if save_output:
        print(f"Statistical maps saved in {output_folder}")

    if generate_plots:
        return plots
    else:
        return None
