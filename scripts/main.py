"""Emerging-properties Mapping via UMAP Spatial Exploration: EMUSE

"""
import argparse
from pathlib import Path

import numpy as np
from bcblib.tools.general_utils import open_json, parse_file_list_argument
from joblib import __version__ as joblib_version

from tools.UMAP_utils import train_and_save_umap_and_embeddings
from tools.emuse_utils import DiscreteLatentSpace


def main():
    parser = argparse.ArgumentParser(description='EMUSE pipeline')
    subparsers = parser.add_subparsers(dest='command')

    # Command for the full pipeline
    full_parser = subparsers.add_parser('full', help='Run the full pipeline')
    full_parser.add_argument('input_dataset', help='Input dataset of either images (jpg) or niftis')
    full_parser.add_argument('output_folder', help='Output folder')
    full_parser.add_argument('--prefix', default='', help='Prefix for the output path names')
    full_parser.add_argument('--max_overlap', type=float, default=0.5,
                             help='Maximum overlap value for the discrete space')
    full_parser.add_argument('--stat_function', default='mean', help='Statistical function name for the heatmaps')
    full_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    full_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')

    # Command for training the UMAP and getting the embeddings
    umap_parser = subparsers.add_parser('umap', help='Train the UMAP and get the embeddings')
    umap_parser.add_argument('input_dataset', type=str,
                             help='Input dataset of either images (jpg) or niftis')
    umap_parser.add_argument('output_folder', help='Output folder')
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
    heatmap_parser.add_argument('--stat_function', default='mean', help='Statistical function name for the heatmaps')
    heatmap_parser.add_argument('--new_dataset', help='New dataset for creating the heatmaps')
    heatmap_parser.add_argument('--scores', nargs='+', help='Scores associated with the new dataset')

    args = parser.parse_args()

    if args.command == 'full':
        paths_list = parse_file_list_argument(args.input_dataset,
                                              recursive_file_search=args.recursive_input_file_search,
                                              file_types=args.input_file_types,
                                              arg_separator=args.arg_separator)
    elif args.command == 'umap':
        paths_list = parse_file_list_argument(args.input_dataset,
                                              recursive_file_search=args.recursive_input_file_search,
                                              file_types=args.input_file_types,
                                              arg_separator=args.arg_separator)
        train_and_save_umap_and_embeddings(paths_list, args.output_folder, pref=args.prefix)
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
        # TODO get the scores in the right format and then create the heatmap


if __name__ == '__main__':
    main()
