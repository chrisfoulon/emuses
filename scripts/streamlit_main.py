# Streamlit web interface for EMUSES pipeline
import streamlit as st
import os
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime

from bcblib.tools.general_utils import save_json, parse_file_list_argument
from bcblib.tools.nifti_utils import load_nifti

from tools.UMAP_utils import train_and_save_umap_and_embeddings, load_umap_model
from tools.clustering_utils import load_hdbscan_model, save_hdbscan_model, cluster_coordinates
from tools.inputs_utils import detect_dataset_type, process_images, nifti_dataset_to_matrix, load_and_preprocess_digits_dataset, prepare_scores, spreadsheet_to_input_df, is_bids_dataset, handle_bids_dataset
from tools.data_preproc import find_min_resolution
from tools.visualisation import plot_clustering_interactive_with_hover
from tools.correlation_maps_utils import run_heatmap_analysis
from tools.stats_utils import train_and_test_model_per_label
from sklearn.model_selection import train_test_split
from tools.emuses_utils import rescale_embedding


def main():
    st.title('EMUSE Pipeline Web Interface')

    output_folder = st.text_input('Output Folder', value='./output')
    prefix = st.text_input('Prefix for Output Files', value='')
    os.makedirs(output_folder, exist_ok=True)
    st.write('Output folder will be created if it does not exist.')

    # Command selection
    command = st.selectbox('Choose Command', ['full', 'umap', 'heatmap', 'clustering', 'prediction'])

    # Load common arguments
    input_dataset = st.text_input('Input Dataset Path')
    test_size = st.slider('Test Size for Splitting Dataset', min_value=0.0, max_value=1.0, value=0.2)

    # Additional arguments for each command
    if command in ['full', 'umap', 'prediction']:
        recursive_search = st.checkbox('Recursive File Search in Input Dataset', value=False)
        input_file_types = st.text_area('Input File Types (comma-separated)', value='').split(',') if st.text_area('Input File Types (comma-separated)', value='') else None
        arg_separator = st.text_input('Argument Separator', value=',')

    load_umap = None
    if command in ['full', 'heatmap', 'clustering', 'prediction']:
        load_umap = st.text_input('Load Pre-trained UMAP Model Path', value='')

    load_hdbscan = None
    if command in ['full', 'clustering', 'heatmap']:
        load_hdbscan = st.text_input('Load Pre-trained HDBSCAN Model Path', value='')

    load_embeddings = None
    if command in ['full', 'clustering', 'heatmap', 'prediction']:
        load_embeddings = st.text_input('Load Precomputed Embeddings Path', value='')

    interactive_plot = st.checkbox('Create Interactive Clustering Plots', value=False) if command in ['full', 'clustering'] else False

    if st.button('Run Pipeline'):
        if not os.path.isdir(output_folder):
            st.error(f"Output folder {output_folder} is not a valid path")
            return

        # Save arguments to a log file
        os.makedirs(Path(output_folder) / 'log', exist_ok=True)
        dict_args = {
            'command': command,
            'output_folder': output_folder,
            'prefix': prefix,
            'input_dataset': input_dataset,
            'test_size': test_size,
            'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(Path(output_folder) / 'log' / f'arguments_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json', dict_args)

        # Detect dataset type
        if str(input_dataset).lower() == 'mnist':
            dataset_type = 'mnist'
            paths_list = None
        else:
            input_dataset_path = Path(input_dataset).resolve()
            if not input_dataset_path.exists():
                st.error(f"Input dataset {input_dataset} is not a valid path")
                return

            if not is_bids_dataset(input_dataset_path):
                paths_list = parse_file_list_argument(input_dataset_path,
                                                      recursive_file_search=recursive_search,
                                                      file_types=input_file_types,
                                                      arg_separator=arg_separator)
                dataset_type = detect_dataset_type(paths_list)
            else:
                paths_list = handle_bids_dataset(input_dataset_path, verbose=True)
                dataset_type = 'nifti'

        # Process input dataset
        if dataset_type == 'image':
            min_res = find_min_resolution(paths_list)
            input_matrix = process_images(paths_list, min_res)
            output_format_info = min_res
        elif dataset_type == 'nifti':
            input_matrix = nifti_dataset_to_matrix(paths_list)
            output_format_info = load_nifti(paths_list[0]).affine
        elif dataset_type == 'mnist':
            mnist_features_normalized, mnist_labels = load_and_preprocess_digits_dataset()
            input_matrix = mnist_features_normalized.to_numpy() if not isinstance(mnist_features_normalized, np.ndarray) else mnist_features_normalized
            mnist_labels = mnist_labels.astype(int).to_numpy() if not isinstance(mnist_labels, np.ndarray) else mnist_labels
            output_format_info = mnist_features_normalized[0].shape
        else:
            st.error(f"Unsupported dataset type: {dataset_type}")
            return

        # Splitting dataset
        train_features, test_features, train_labels, test_labels = train_test_split(
            input_matrix, mnist_labels if dataset_type == 'mnist' else None, test_size=test_size, random_state=42)

        # Train or load UMAP
        if load_umap:
            trained_umap, _ = load_umap_model(Path(load_umap).resolve())
        else:
            trained_umap, embeddings, _, _, _ = train_and_save_umap_and_embeddings(
                train_features, output_folder, pref=prefix)
            st.success(f"UMAP model trained and saved.")

        # Load or transform embeddings
        if load_embeddings:
            embeddings = np.load(load_embeddings)
        else:
            embeddings = trained_umap.transform(train_features)

        # Clustering
        if command in ['full', 'clustering']:
            if load_hdbscan:
                clusterer = load_hdbscan_model(load_hdbscan)
                cluster_labels = clusterer.labels_
            else:
                clusterer, cluster_labels = cluster_coordinates(embeddings, min_cluster_size=5)
                save_hdbscan_model(clusterer, output_folder, prefix=prefix)
                st.success("Clustering completed and saved.")

            if interactive_plot:
                plot_clustering_interactive_with_hover(embeddings, cluster_labels,
                                                       output_path=Path(output_folder) / 'clustering_plot.html')

        # Heatmap Analysis
        if command in ['full', 'heatmap']:
            if clusterer is None:
                st.error("Clustering is required for heatmap analysis.")
                return

            run_heatmap_analysis(
                embeddings=embeddings,
                scores_vectors_dict={label: (train_labels == label).astype(int) for label in np.unique(train_labels)},
                input_matrix=train_features,
                output_folder=output_folder,
                clusterer=clusterer,
                cluster_labels=cluster_labels,
                output_format_info=output_format_info,
                grid_size=100,
                sigma=None,
                correlation_threshold=0.3,
                highlight_points=True
            )
            st.success("Heatmap analysis completed.")

        # Prediction
        if command in ['full', 'prediction']:
            train_and_test_model_per_label(
                train_embeddings=embeddings,
                train_labels=train_labels,
                test_embeddings=embeddings if test_features is None else trained_umap.transform(test_features),
                test_labels=test_labels,
                output_folder=Path(output_folder) / 'prediction_models'
            )
            st.success("Prediction model trained and saved.")


if __name__ == '__main__':
    main()
