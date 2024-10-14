import numpy as np
import pytest
from tools.UMAP_utils import train_and_save_umap_and_embeddings


@pytest.fixture
def tmp_output_folder(tmp_path):
    return tmp_path

def test_train_and_save_umap_and_embeddings(tmp_output_folder):
    # Test with a valid input matrix
    input_matrix = np.random.rand(100, 10)
    umap_model, embeddings, model_filename, embeddings_filename, input_matrix_filename = (
        train_and_save_umap_and_embeddings(
        input_matrix, tmp_output_folder, pref="test"
    ))

    # Check if files are saved correctly
    assert model_filename.exists(), "UMAP model file was not saved."
    assert embeddings_filename.exists(), "Embeddings file was not saved."
    assert input_matrix_filename.exists(), "Input matrix file was not saved."

    # Check if embeddings have correct shape
    assert embeddings.shape == (100, 2), "Embeddings shape is incorrect."

    # Test with an input matrix with only one sample
    input_matrix = np.random.rand(1, 10)
    with pytest.warns(UserWarning, match="The input matrix has only one sample. UMAP may not perform optimally."):
        train_and_save_umap_and_embeddings(input_matrix, tmp_output_folder, pref="single_sample")

    # Test with an input matrix with only one feature
    input_matrix = np.random.rand(100, 1)
    with pytest.warns(UserWarning, match="The input matrix has only one feature. UMAP may not perform optimally."):
        train_and_save_umap_and_embeddings(input_matrix, tmp_output_folder, pref="single_feature")

    # Test with an empty input matrix
    input_matrix = np.empty((0, 10))
    with pytest.raises(ValueError, match="Input matrix must have at least one sample and one feature."):
        train_and_save_umap_and_embeddings(input_matrix, tmp_output_folder, pref="empty")

    # Test with an input matrix with only one sample and one feature
    input_matrix = np.random.rand(1, 1)
    with pytest.warns(UserWarning):
        train_and_save_umap_and_embeddings(input_matrix, tmp_output_folder, pref="single_sample_feature")

if __name__ == "__main__":
    pytest.main()