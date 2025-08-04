import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.observability import track_scientific_operation, get_logger
from emuses.tools.stats_utils import (
    compute_gwd_summary_test,
    train_and_test_model_per_label,
    optuna_model_selection,
)
from emuses.tools.stats_utils import compute_gwd_summary
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import cross_val_score
from sklearn.kernel_ridge import KernelRidge

from bcblib.tools.general_utils import save_json

import concurrent.futures
from joblib import dump

# Import new model I/O system
from ..tools.model_io import ModelIOManager


class PredictionStage(PipelineStage):
    """
    Stage to train models for predicting target variables from embeddings,
    optionally including Gaussian weighted distances (GWD) features.
    """

    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        logger = get_logger(__name__)
        
        # Get user context for observability
        user_id = context.get("user_id")
        dataset_name = context.get("dataset_name", "unknown")
        
        with track_scientific_operation(
            "prediction_modeling",
            user_id=user_id,
            additional_attributes={"dataset": dataset_name}
        ) as obs_ctx:
            logger.info("Running Prediction Stage (Test Evaluation)", user_id=user_id)

            # Get component-specific seeds from context
        random_seeds = context.get("random_seeds", {})
        prediction_seed = random_seeds.get("prediction_seed", 42)
        cv_seed = random_seeds.get("cv_seed", 42)
        optuna_seed = random_seeds.get("optuna_seed", 42)
        logger.info(
            f"Using random seeds - Prediction: {prediction_seed}, CV: {cv_seed}, Optuna: {optuna_seed}"
        )

        # Extract embeddings and labels from context using new naming convention only
        train_embeddings = context.get("prediction_train_coords")
        test_embeddings = context.get("prediction_test_coords")
        train_labels = context.get("prediction_train_labels")
        test_labels = context.get("prediction_test_labels")

        if train_embeddings is None:
            raise ValueError("prediction_train_coords is required for prediction.")
        if train_labels is None:
            raise ValueError("prediction_train_labels is required for prediction.")

        # Determine if we use enhanced pipeline with Optuna
        use_enhanced_pipeline = getattr(self.config, "use_enhanced_pipeline", False)
        n_jobs = getattr(self.config, "n_jobs", -1)
        optuna_trials = getattr(self.config, "optuna_trials", 50)
        parallel_models = getattr(self.config, "parallel_models", False)
        model_selection = getattr(self.config, "model_selection", None)

        # Setup output folder
        output_folder = self.config.output_folder / "prediction_models"
        output_folder.mkdir(parents=True, exist_ok=True)

        if use_enhanced_pipeline:
            logger.info(
                f"Using enhanced pipeline with Optuna optimization (trials: {optuna_trials}, n_jobs: {n_jobs})"
            )

            # Extract GWD features from embeddings
            # Get sigma value from context or compute default
            sigma = context.get("prediction_train_sigma")
            if sigma is None:
                # Use a default heuristic if no specific sigma is provided
                sigma = np.sqrt(train_embeddings.shape[1]) * 0.5
                logger.info(f"No sigma value found in context. Using default: {sigma}")
                # Store the computed sigma in context with standardized name
                context["prediction_train_sigma"] = sigma

            # Compute GWD features for train and test sets
            logger.info("Computing GWD features for enhanced predictions...")
            train_gwd_features = compute_gwd_summary(
                train_embeddings, sigma, mode="extended"
            )

            # Only compute test GWD features if we have test embeddings
            if test_embeddings is not None:
                # Use the fixed function for test GWD features that references training data
                test_gwd_features = compute_gwd_summary_test(
                    test_embeddings, train_embeddings, sigma, mode="extended"
                )

                # Create multiple feature sets to try
                feature_sets = {
                    "embeddings_only": (train_embeddings, test_embeddings),
                    "gwd_only": (train_gwd_features, test_gwd_features),
                    "combined": (
                        np.hstack((train_embeddings, train_gwd_features)),
                        np.hstack((test_embeddings, test_gwd_features)),
                    ),
                }
            else:
                # Create feature sets without test data
                feature_sets = {
                    "embeddings_only": (train_embeddings, None),
                    "gwd_only": (train_gwd_features, None),
                    "combined": (
                        np.hstack((train_embeddings, train_gwd_features)),
                        None,
                    ),
                }

            # Determine if we're training models per label in parallel or sequentially
            results_list = []

            # Convert train_labels and test_labels to np.array if they are not already
            # This ensures consistent handling regardless of input type
            train_labels_array = (
                train_labels.values if hasattr(train_labels, "values") else train_labels
            )
            test_labels_array = (
                test_labels.values if hasattr(test_labels, "values") else test_labels
            )

            # Handle case where labels might be 1D array
            if train_labels_array.ndim == 1:
                train_labels_array = train_labels_array.reshape(-1, 1)
            if test_labels_array is not None and test_labels_array.ndim == 1:
                test_labels_array = test_labels_array.reshape(-1, 1)

            # Get column names if available, otherwise use generic names
            if hasattr(train_labels, "columns"):
                column_names = train_labels.columns
            else:
                column_names = [
                    f"Target_{i}" for i in range(train_labels_array.shape[1])
                ]

            # For each target variable
            for label_idx in range(train_labels_array.shape[1]):
                label_name = column_names[label_idx]
                y_train = train_labels_array[:, label_idx]
                y_test = (
                    test_labels_array[:, label_idx]
                    if test_labels_array is not None
                    else None
                )

                logger.info(f"Training models for label: {label_name}")

                # If parallel_models is True, we train models for different feature sets in parallel
                # Otherwise, we train them sequentially
                if parallel_models:
                    feature_set_results = {}

                    # Function to train a model on a feature set and return results
                    def train_feature_set(feature_name, features):
                        logger.info(f"Training on feature set: {feature_name}")
                        X_train, X_test = features
                        # Use Optuna for model selection
                        label_output_folder = output_folder / label_name / feature_name
                        label_output_folder.mkdir(parents=True, exist_ok=True)
                        results = optuna_model_selection(
                            X=X_train,
                            y=y_train,
                            n_trials=optuna_trials,
                            n_jobs=1,  # Use 1 here because we're already parallelizing at the feature set level
                            output_folder=label_output_folder,
                            feature_set_name=feature_name,
                            models=model_selection,
                            random_state=cv_seed,
                            optuna_seed=optuna_seed,
                        )

                        # Get the best model and evaluate on test set if available
                        best_model = results["best_model"]
                        if X_test is not None and y_test is not None:
                            y_pred = best_model.predict(X_test)

                            # Calculate metrics
                            r2 = r2_score(y_test, y_pred)
                            mse = mean_squared_error(y_test, y_pred)
                            mae = mean_absolute_error(y_test, y_pred)

                            results.update(
                                {
                                    "test_r2": r2,
                                    "test_mse": mse,
                                    "test_mae": mae,
                                    "y_pred": y_pred,
                                    "y_test": y_test,
                                }
                            )
                        else:
                            # No test data available, use validation metrics instead
                            results.update(
                                {
                                    "test_r2": results.get("val_r2", 0),
                                    "test_mse": results.get("val_mse", 0),
                                    "test_mae": results.get("val_mae", 0),
                                }
                            )

                        results["label_name"] = label_name
                        return results

                    # Use multiprocessing to train models in parallel across feature sets
                    with concurrent.futures.ProcessPoolExecutor(
                        max_workers=min(n_jobs, len(feature_sets))
                    ) as executor:
                        future_to_feature = {
                            executor.submit(
                                train_feature_set, feature_name, features
                            ): feature_name
                            for feature_name, features in feature_sets.items()
                        }

                        for future in concurrent.futures.as_completed(
                            future_to_feature
                        ):
                            feature_name = future_to_feature[future]
                            try:
                                feature_set_results[feature_name] = future.result()
                            except Exception as e:
                                logger.error(
                                    f"Error training models for feature set {feature_name}: {e}"
                                )

                    # Find the best feature set based on R2 score
                    best_feature_set = max(
                        feature_set_results.items(), key=lambda x: x[1]["test_r2"]
                    )
                    best_feature_name, best_result = best_feature_set

                    logger.info(
                        f"Best feature set for {label_name}: {best_feature_name} "
                        f"(R2: {best_result['test_r2']:.4f})"
                    )

                    # Add to results list
                    results_list.append(
                        {
                            "label_name": label_name,
                            "best_feature_set": best_feature_name,
                            "best_model": best_result["best_model_name"],
                            "test_r2": best_result["test_r2"],
                            "test_mse": best_result["test_mse"],
                            "test_mae": best_result["test_mae"],
                            "model_params": best_result["best_params"],
                        }
                    )

                else:
                    # Train sequentially
                    best_r2 = -float("inf")
                    best_result = None
                    best_feature_name = None

                    for feature_name, features in feature_sets.items():
                        logger.info(f"Training on feature set: {feature_name}")
                        X_train, X_test = features
                        # Use Optuna for model selection
                        label_output_folder = output_folder / label_name / feature_name
                        label_output_folder.mkdir(parents=True, exist_ok=True)
                        results = optuna_model_selection(
                            X=X_train,
                            y=y_train,
                            n_trials=optuna_trials,
                            n_jobs=n_jobs,  # Use all available jobs since we're not parallelizing feature sets
                            output_folder=label_output_folder,
                            feature_set_name=feature_name,
                            models=model_selection,
                            random_state=cv_seed,
                            optuna_seed=optuna_seed,
                        )

                        # Get the best model and evaluate on test set if available
                        best_model = results["best_model"]

                        if X_test is not None and y_test is not None:
                            y_pred = best_model.predict(X_test)

                            # Calculate metrics
                            r2 = r2_score(y_test, y_pred)
                            mse = mean_squared_error(y_test, y_pred)
                            mae = mean_absolute_error(y_test, y_pred)
                        else:
                            # No test data available, use validation metrics instead
                            r2 = results.get("val_r2", 0)
                            mse = results.get("val_mse", 0)
                            mae = results.get("val_mae", 0)

                        if r2 > best_r2:
                            best_r2 = r2
                            best_result = {
                                "label_name": label_name,
                                "best_feature_set": feature_name,
                                "best_model": results["best_model_name"],
                                "test_r2": r2,
                                "test_mse": mse,
                                "test_mae": mae,
                                "model_params": results["best_params"],
                            }
                            best_feature_name = feature_name

                    logger.info(
                        f"Best feature set for {label_name}: {best_feature_name} "
                        f"(R2: {best_result['test_r2']:.4f})"
                    )

                    # Add to results list
                    results_list.append(best_result)
        else:
            # Use original pipeline
            logger.info("Using original prediction pipeline")

            # Check if we have test data
            if test_embeddings is not None and test_labels is not None:
                # Train and test a prediction model for each score
                results_list = train_and_test_model_per_label(
                    train_embeddings=train_embeddings,
                    train_labels=train_labels,
                    test_embeddings=test_embeddings,
                    test_labels=test_labels,
                    output_folder=output_folder,
                    categorical=getattr(self.config, "classification", False),
                    show_plot=getattr(self.config, "show_plots", False),
                )
            else:
                # No test data, use cross-validation only

                # Basic cross-validation with KernelRidge
                results_list = []

                logger.info("No test data available, using cross-validation only")

                # Convert train_labels to numpy array if needed
                train_labels_array = (
                    train_labels.values
                    if hasattr(train_labels, "values")
                    else train_labels
                )

                # Handle case where labels might be 1D array
                if train_labels_array.ndim == 1:
                    train_labels_array = train_labels_array.reshape(-1, 1)

                # Get column names if available, otherwise use generic names
                if hasattr(train_labels, "columns"):
                    column_names = train_labels.columns
                else:
                    column_names = [
                        f"Target_{i}" for i in range(train_labels_array.shape[1])
                    ]

                # For each target variable
                for label_idx in range(train_labels_array.shape[1]):
                    label_name = column_names[label_idx]
                    y_train = train_labels_array[:, label_idx]

                    logger.info(f"Cross-validating model for label: {label_name}")

                    # Simple KernelRidge regression with cross-validation
                    model = KernelRidge(alpha=0.1, kernel="rbf")
                    cv_scores = cross_val_score(
                        model, train_embeddings, y_train, cv=5, scoring="r2"
                    )
                    # Train final model on all data
                    model.fit(train_embeddings, y_train)

                    # Save model using new I/O system
                    label_output_folder = output_folder / label_name
                    label_output_folder.mkdir(parents=True, exist_ok=True)

                    model_manager = ModelIOManager(label_output_folder)
                    model_manager.save_model(
                        model=model,
                        model_name="final_model",
                        model_type="kernel_ridge",
                        description=f"KernelRidge model for {label_name} prediction",
                        tags=["prediction", "kernel_ridge", label_name],
                        config={"alpha": 0.1, "kernel": "rbf"},
                    )

                    # Add to results list
                    results_list.append(
                        {
                            "label_name": label_name,
                            "best_feature_set": "embeddings_only",
                            "best_model": "KernelRidge",
                            "test_r2": cv_scores.mean(),  # Use mean CV score
                            "model_params": {"alpha": 0.1, "kernel": "rbf"},
                        }
                    )

        # Save results in a CSV and in a json file for easy parsing
        performance_df = pd.DataFrame(results_list)
        output_folder_perf = Path(self.config.output_folder) / "prediction_performance"
        output_folder_perf.mkdir(parents=True, exist_ok=True)
        perf_csv_file = output_folder_perf / "prediction_performance.csv"
        performance_df.to_csv(perf_csv_file, index=False)
        logger.info(f"Saved test performance metrics to {perf_csv_file}")

        # Save as JSON
        perf_json_file = output_folder_perf / "prediction_performance.json"
        save_json(perf_json_file, results_list)

        return context
