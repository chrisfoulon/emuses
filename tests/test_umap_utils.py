import numpy as np
import pytest
from pathlib import Path
from tools.UMAP_utils import train_and_save_umap_and_embeddings

@pytest.fixture
def input_matrix():
    # Creating a small, synthetic input matrix for testing purposes
    return np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])

@pytest.fixture
def output_folder(tmp_path):
    # Using pytest's tmp_path fixture to create a temporary directory
    return tmp_path

def test_train_and_save_umap_and_embeddings(input_matrix, output_folder):
    # Run the function with the synthetic input matrix and temporary output folder
    umap_model, embeddings, model_path, embeddings_path, input_matrix_path = train_and_save_umap_and_embeddings(
        input_matrix, output_folder, pref="test"
    )

    # Assertions to check if files are correctly saved
    assert model_path.exists(), "UMAP model file was not saved."
    assert embeddings_path.exists(), "Embeddings file was not saved."
    assert input_matrix_path.exists(), "Input matrix file was not saved."

    # Assertions to check if the shapes are correct
    assert embeddings.shape[0] == input_matrix.shape[0], "Number of embeddings does not match number of input samples."
    assert embeddings.shape[1] == 2, "Embeddings should have 2 dimensions (UMAP default)."

    # Additional assertions can be added to verify contents, if needed

if __name__ == "__main__":
    pytest.main()