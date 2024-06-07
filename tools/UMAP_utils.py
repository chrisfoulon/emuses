from joblib import dump, load
from pathlib import Path
import numpy as np
import umap
from joblib import __version__ as joblib_version


def train_and_save_umap_and_embeddings(input_matrix, output_folder, pref=None, **kwargs):
    """
    Train a UMAP model on the input matrix and save the model and the embeddings to disk using joblib for serialization.
    Parameters:
    - input_matrix : np.ndarray or scipy.sparse.csr_matrix
        The input matrix to be used for training.
    - output_folder : str
        The directory where the model and embeddings will be saved.
    - pref : str, optional
        A prefix to add to the output filenames. If not provided, no prefix is added.
    - kwargs : dict
        Additional keyword arguments to pass to the UMAP constructor.
    """
    output_folder = Path(output_folder)
    Path.mkdir(output_folder, exist_ok=True)
    # Train the UMAP model
    umap_model = umap.UMAP(**kwargs)
    embeddings = umap_model.fit_transform(input_matrix)

    # Ensure prefix ends correctly
    prefix = f"{pref}_" if pref else ""
    model_filename = f"{prefix}umap_model_joblib{joblib_version}.joblib"
    embeddings_filename = f"{prefix}embeddings.npy"

    # Save the UMAP model and embeddings
    dump(umap_model, output_folder / model_filename)
    np.save(output_folder / embeddings_filename, embeddings)

    return umap_model, embeddings, output_folder / model_filename, output_folder / embeddings_filename


def is_umap_file(umap_path):
    return str(umap_path).endswith('.joblib')

