"""Emerging-properties Mapping via UMAP Spatial Exploration: EMUSE

"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from bcblib.tools.general_utils import open_json, parse_file_list_argument
from joblib import __version__ as joblib_version

from tools.UMAP_utils import train_and_save_umap_and_embeddings
from tools.emuse_utils import DiscreteLatentSpace
from tools.inputs_utils import create_heatmap_data, detect_dataset_type, load_and_preprocess_mnist_dataset, \
    process_images, nifti_dataset_to_matrix, mnist_features_to_input_matrix
from tools.data_preproc import find_min_resolution


def main():
    parser = argparse.ArgumentParser(description='EMUSE pipeline')
    subparsers = parser.add_subparsers(dest='command')

    # Command for the full pipeline
    full_parser = subparsers.add_parser('full', help='Run the full pipeline')
    full_parser.add_argument('input_dataset', help='Input dataset of either images (jpg) or niftis')
    full_parser.add_argument('output_folder', help='Output folder')
    full_parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                             help='Search for files recursively in the input dataset folder')
    full_parser.add_argument('--input_file_types', nargs='+', default=None,
                             help='File types to search for in the input dataset folder')
    full_parser.add_argument('--arg_separator', default=',',
                             help='Separator for the input dataset list')
    full_parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    full_parser.add_argument('--max_overlap', type=float, default=0.1,
                             help='Maximum overlap value for the discrete space')
    full_parser.add_argument('--stat_function', default='mean', help='Statistical function name for the heatmaps')
    full_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    full_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')

    # Command for training the UMAP and getting the embeddings
    umap_parser = subparsers.add_parser('umap', help='Train the UMAP and get the embeddings')
    umap_parser.add_argument('input_dataset', type=str,
                             help='Input dataset of either images (jpg) or niftis')
    umap_parser.add_argument('output_folder', help='Output folder')
    umap_parser.add_argument('-rs', '--recursive_input_file_search', action='store_true',
                             help='Search for files recursively in the input dataset folder')
    umap_parser.add_argument('--input_file_types', nargs='+', default=None,
                             help='File types to search for in the input dataset folder')
    umap_parser.add_argument('--arg_separator', default=',',
                             help='Separator for the input dataset list')
    umap_parser.add_argument('--prefix', default='', help='Prefix for the output path names')

    # Command for creating the DiscreteLatentSpace
    dls_parser = subparsers.add_parser('dls', help='Create the DiscreteLatentSpace')
    dls_parser.add_argument('embeddings', help='Embeddings from the UMAP')
    dls_parser.add_argument('--max_overlap', type=float, default=0.5,
                            help='Maximum overlap value for the discrete space')
    # add a prefix argument to the dls command
    dls_parser.add_argument('--prefix', default='', help='Prefix for the output path names')

    # Command for creating the heatmaps
    heatmap_parser = subparsers.add_parser('heatmap', help='Create a heatmap')
    heatmap_parser.add_argument('discrete_space', help='Discrete space from the DiscreteLatentSpace')
    # add a group of arguments for the smoothing (mutually exclusive). Either the user gives the sigma or the fwhm
    smoothing_group = heatmap_parser.add_mutually_exclusive_group()
    smoothing_group.add_argument('--sigma', type=float, help='Sigma value for the smoothing')
    smoothing_group.add_argument('--fwhm', type=float,
                                 help='Full width at half maximum value for the smoothing')
    heatmap_parser.add_argument('--stat_function', default='mean',
                                help='Statistical function name for the heatmaps')
    heatmap_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    heatmap_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')

    args = parser.parse_args()
    # check if the input dataset and output folder are valid paths
    args.input_dataset = Path(args.input_dataset).resolve()
    if not args.input_dataset.is_dir() or not args.input_dataset.exists():
        raise ValueError(f"Input dataset {args.input_dataset} is not a valid path")

    args.output_folder = Path(args.output_folder).resolve()
    # if the output folder does not exist, create it
    Path(args.output_folder).mkdir(parents=True, exist_ok=True)
    if not args.output_folder.is_dir():
        raise ValueError(f"Output folder {args.output_folder} is not a valid path")

    if args.command == 'full':
        paths_list = parse_file_list_argument(args.input_dataset,
                                              recursive_file_search=args.recursive_input_file_search,
                                              file_types=args.input_file_types,
                                              arg_separator=args.arg_separator)
    elif args.command == 'umap':
        if args.input_dataset != 'mnist':
            paths_list = parse_file_list_argument(args.input_dataset,
                                                  recursive_file_search=args.recursive_input_file_search,
                                                  file_types=args.input_file_types,
                                                  arg_separator=args.arg_separator)
            dataset_type = detect_dataset_type(paths_list)
            if dataset_type == 'image':
                min_res = find_min_resolution(paths_list)
                input_matrix = process_images(paths_list, min_res)
            elif dataset_type == 'nifti':
                input_matrix = nifti_dataset_to_matrix(paths_list)
            else:
                raise ValueError(f"Unsupported dataset type: {dataset_type}")
        else:
            mnist_features_normalized, mnist_labels = load_and_preprocess_mnist_dataset()
            # save the labels in the output_folder as a csv
            pd.DataFrame(mnist_labels).to_csv(Path(args.output_folder) / 'mnist_labels.csv', index=False)
            input_matrix = mnist_features_to_input_matrix(mnist_features_normalized)
        # paths_list is not the right input to the function, we need to transform them into an input matrix using
        # inputs_utils.
        train_and_save_umap_and_embeddings(input_matrix, args.output_folder, pref=args.prefix)
    elif args.command == 'dls':
        embeddings_path = Path(args.embeddings)
        if embeddings_path.suffix == '.npy' and embeddings_path.exists():
            embeddings = np.load(embeddings_path)
        else:
            raise ValueError(f'Embeddings file {embeddings_path} does not exist or is not a .npy file')
        max_overlap = args.max_overlap
        dls = DiscreteLatentSpace(embeddings, max_overlap)
        # create the discrete space
        dls.create_discrete_space(dls.raw_embeddings, args.max_overlap)
        # save the dls with the joblib version in the name
        actual_prefix = f"{args.prefix}_" if args.prefix else ""
        output_path = embeddings_path.parent / f'{actual_prefix}dls_joblib{joblib_version}.joblib'
        dls.save(output_path)
    elif args.command == 'heatmap':
        # To create a heatmap, we need a DLS and a new dataset
        dls_path = Path(args.discrete_space)
        if dls_path.suffix == '.joblib' and dls_path.exists():
            dls = DiscreteLatentSpace.load(dls_path)
        else:
            raise ValueError(f'DLS file {dls_path} does not exist or is not a .joblib file')
        # Prepare the DataFrame
        embeddings, scores = create_heatmap_data(dls, args.new_dataset, args.scores[0] if args.scores else None)
        # create the dataframe with the embeddings and scores
        df = pd.DataFrame(embeddings, columns=['embedding'])
        df['scores'] = scores

        # Create the heatmap spaces in the DLS
        dls.create_heatmap_spaces(df, args.prefix, smoothing_fwhm=args.fwhm, smoothing_sigma=args.sigma)
        # TODO add BIDS data loading as well


if __name__ == '__main__':
    main()
