import argparse

import streamlit as st

from emuses.tools.visualisation import load_umap_tabs


def main():
    # Parse command-line arguments (if any)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder", type=str, default="output", help="Folder containing UMAP HTML files"
    )
    parser.add_argument(
        "--prefix", type=str, default="umap", help="Prefix for UMAP files"
    )
    args, _ = parser.parse_known_args()

    # Configure the Streamlit page
    st.set_page_config(page_title="UMAP Explorer", layout="wide")
    st.title("UMAP Explorer")

    # Use the command-line arguments as defaults for the text inputs
    folder = st.text_input("Folder containing UMAP HTML files", value=args.folder)
    prefix = st.text_input("Prefix for UMAP files", value=args.prefix)

    if folder and prefix:
        load_umap_tabs(folder, prefix)


if __name__ == "__main__":
    main()
