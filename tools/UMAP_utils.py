import joblib
from joblib import dump, load
from pathlib import Path
import numpy as np
import umap
import warnings
from joblib import __version__ as joblib_version


def train_and_save_umap_and_embeddings(input_matrix, output_folder, pref=None, **kwargs):
    """
    Train a UMAP model on the input matrix and save the model, embeddings, and input matrix to disk using joblib for serialization.
    Parameters:
    - input_matrix : np.ndarray or scipy.sparse.csr_matrix
        The input matrix to be used for training.
    - output_folder : str
        The directory where the model, embeddings, and input matrix will be saved.
    - pref : str, optional
        A prefix to add to the output filenames. If not provided, no prefix is added.
    - kwargs : dict
        Additional keyword arguments to pass to the UMAP constructor.
    """
    output_folder = Path(output_folder)
    Path.mkdir(output_folder, exist_ok=True)

    # Check if the input matrix has valid dimensions
    if input_matrix.shape[0] == 0 or input_matrix.shape[1] == 0:
        raise ValueError("Input matrix must have at least one sample and one feature.")

    # Check if the input matrix has only one sample or one feature
    if input_matrix.shape[0] == 1:
        warnings.warn("The input matrix has only one sample. UMAP may not perform optimally.")
    if input_matrix.shape[1] == 1:
        warnings.warn("The input matrix has only one feature. UMAP may not perform optimally.")

    # Train the UMAP model
    umap_model = umap.UMAP(**kwargs)
    embeddings = umap_model.fit_transform(input_matrix)

    # Ensure prefix ends correctly
    prefix = f"{pref}_" if pref else ""
    model_filename = f"{prefix}umap_model_joblib{joblib_version}.joblib"
    embeddings_filename = f"{prefix}embeddings.npy"
    input_matrix_filename = f"{prefix}input_matrix.npy"

    # Save the UMAP model, embeddings, and input matrix
    dump(umap_model, output_folder / model_filename)
    np.save(output_folder / embeddings_filename, embeddings)
    np.save(output_folder / input_matrix_filename, input_matrix)

    return (umap_model, embeddings, output_folder / model_filename,
            output_folder / embeddings_filename, output_folder / input_matrix_filename)


def is_umap_file(umap_path):
    return str(umap_path).endswith('.joblib')


def load_umap_model(base_path, prefix='', model_name='umap_model', joblib_version=None, max_attempts=10):
    """
    Load a UMAP model based on the filename convention and system joblib version.

    Parameters:
    base_path (Path or str): The directory where UMAP models are saved.
    prefix (str): Prefix for the UMAP model filename.
    model_name (str): Base name of the model.
    joblib_version (str, optional): Version of joblib used in the saved file. If None, the current system joblib version is used.
    max_attempts (int): Maximum number of attempts to load different versions of the model.

    Returns:
    loaded_umap (object or None): Loaded UMAP model or None if loading failed.
    filepath (Path): Path of the loaded or next available filename.
    """
    base_path = Path(base_path)
    if joblib_version is None or not joblib_version:
        joblib_version = joblib.__version__
    current_joblib_version = joblib.__version__
    if prefix:
        filename_pattern = f"{prefix}_{model_name}_joblib{joblib_version}.joblib"
    else:
        filename_pattern = f"{model_name}_joblib{joblib_version}.joblib"
    filepath = base_path / filename_pattern

    # Try to load the file with the given filename convention
    if filepath.exists() and is_umap_file(filepath):
        try:
            loaded_umap = joblib.load(filepath)
            print(f"Successfully loaded UMAP model from: {filepath}")
            return loaded_umap, filepath
        except Exception as e:
            print(f"Failed to load UMAP model from: {filepath}, due to: {e}")

    # If the initial file cannot be loaded, try numbered variations
    counter = 1
    while counter <= max_attempts:
        if prefix:
            numbered_filename = f"{prefix}_{model_name}_joblib{joblib_version}_{counter}.joblib"
        else:
            numbered_filename = f"{model_name}_joblib{joblib_version}_{counter}.joblib"
        numbered_filepath = base_path / numbered_filename
        if numbered_filepath.exists() and is_umap_file(numbered_filepath):
            try:
                loaded_umap = joblib.load(numbered_filepath)
                print(f"Successfully loaded UMAP model from: {numbered_filepath}")
                return loaded_umap, numbered_filepath
            except Exception as e:
                print(f"Failed to load UMAP model from: {numbered_filepath}, due to: {e}")
                counter += 1
        else:
            break

    if counter > max_attempts:
        raise RuntimeError(f"Failed to load UMAP model after {max_attempts} attempts. Either there are too many versions or another issue is preventing loading.")

    # Return None and the next available filename if all attempts fail
    if prefix:
        next_available_filename = f"{prefix}_{model_name}_joblib{current_joblib_version}_{counter}.joblib"
    else:
        next_available_filename = f"{model_name}_joblib{current_joblib_version}_{counter}.joblib"
    next_filepath = base_path / next_available_filename
    print(f"Returning next available filename: {next_filepath}")
    return None, next_filepath
