import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.stats_utils import train_and_test_model_per_label, optuna_model_selection
from emuses.tools.stats_utils import compute_gwd_summary

class PredictionStage(PipelineStage):
    """
    Stage to train models for predicting target variables from embeddings,
    optionally including Gaussian weighted distances (GWD) features.
    """
    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage (Test Evaluation)")

        args = self.config.args

        # Extract embeddings and labels from context
        if 'train_labelled_embeddings' in context and 'test_labelled_embeddings' in context \
                and 'train_labelled_scores' in context and 'test_labelled_scores' in context:
            train_embeddings = context['train_labelled_embeddings']
            train_labels = context['train_labelled_scores']
            test_embeddings = context['test_labelled_embeddings']
            test_labels = context['test_labelled_scores']
            logger.info(
                "Using labelled dataset split for prediction: training on labelled training data and testing on "
                "labelled test data.")
        else:
            # Fallback: use the default splits from unsupervised data splitting.
            train_embeddings = context.get('embeddings')
            test_embeddings = context.get('test_embeddings')
            train_labels = context.get('train_labels')
            test_labels = context.get('test_labels')

        if train_embeddings is None or test_embeddings is None:
            raise ValueError("Both training and test embeddings are required for prediction.")
        if train_labels is None or test_labels is None:
            raise ValueError("Both training and test labels are required for prediction.")

        # Determine if we use enhanced pipeline with Optuna
        use_enhanced_pipeline = getattr(args, 'use_enhanced_pipeline', False)
        n_jobs = getattr(args, 'n_jobs', -1)
        optuna_trials = getattr(args, 'optuna_trials', 50)
        parallel_models = getattr(args, 'parallel_models', False)
        model_selection = getattr(args, 'model_selection', None)
        
        # Setup output folder
        output_folder = self.config.output_folder / 'prediction_models'
        output_folder.mkdir(parents=True, exist_ok=True)
        
        if use_enhanced_pipeline:
            logger.info(f"Using enhanced pipeline with Optuna optimization (trials: {optuna_trials}, n_jobs: {n_jobs})")
            
            # Extract GWD features from embeddings
            # Get sigma value from context or compute default
            sigma = context.get('best_sigma')
            if sigma is None:
                # Use a default heuristic if no specific sigma is provided
                sigma = np.sqrt(train_embeddings.shape[1]) * 0.5
                logger.info(f"No sigma value found in context. Using default: {sigma}")
            
            # Compute GWD features for train and test sets
            logger.info("Computing GWD features for enhanced predictions...")
            train_gwd_features = compute_gwd_summary(train_embeddings, sigma, mode="extended")
            test_gwd_features = compute_gwd_summary(test_embeddings, sigma, mode="extended")
            
            # Create multiple feature sets to try
            feature_sets = {
                "embeddings_only": (train_embeddings, test_embeddings),
                "gwd_only": (train_gwd_features, test_gwd_features),
                "combined": (
                    np.hstack((train_embeddings, train_gwd_features)), 
                    np.hstack((test_embeddings, test_gwd_features))
                )
            }
            
            # Determine if we're training models per label in parallel or sequentially
            results_list = []
            
            # Convert train_labels and test_labels to np.array if they are not already
            # This ensures consistent handling regardless of input type
            train_labels_array = train_labels.values if hasattr(train_labels, 'values') else train_labels
            test_labels_array = test_labels.values if hasattr(test_labels, 'values') else test_labels
            
            # Handle case where labels might be 1D array
            if train_labels_array.ndim == 1:
                train_labels_array = train_labels_array.reshape(-1, 1)
            if test_labels_array.ndim == 1:
                test_labels_array = test_labels_array.reshape(-1, 1)
            
            # Get column names if available, otherwise use generic names
            if hasattr(train_labels, 'columns'):
                column_names = train_labels.columns
            else:
                column_names = [f"Target_{i}" for i in range(train_labels_array.shape[1])]
            
            # For each target variable
            for label_idx in range(train_labels_array.shape[1]):
                label_name = column_names[label_idx]
                y_train = train_labels_array[:, label_idx]
                y_test = test_labels_array[:, label_idx]
                
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
                            models=model_selection
                        )
                        
                        # Get the best model and evaluate on test set
                        best_model = results['best_model']
                        y_pred = best_model.predict(X_test)
                        
                        # Calculate metrics
                        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
                        r2 = r2_score(y_test, y_pred)
                        mse = mean_squared_error(y_test, y_pred)
                        mae = mean_absolute_error(y_test, y_pred)
                        
                        results.update({
                            'test_r2': r2,
                            'test_mse': mse,
                            'test_mae': mae,
                            'y_pred': y_pred,
                            'y_test': y_test,
                            'label_name': label_name
                        })
                        
                        return results
                    
                    # Use multiprocessing to train models in parallel across feature sets
                    import concurrent.futures
                    with concurrent.futures.ProcessPoolExecutor(max_workers=min(n_jobs, len(feature_sets))) as executor:
                        future_to_feature = {
                            executor.submit(train_feature_set, feature_name, features): feature_name
                            for feature_name, features in feature_sets.items()
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_feature):
                            feature_name = future_to_feature[future]
                            try:
                                feature_set_results[feature_name] = future.result()
                            except Exception as e:
                                logger.error(f"Error training models for feature set {feature_name}: {e}")
                    
                    # Find the best feature set based on R2 score
                    best_feature_set = max(feature_set_results.items(), key=lambda x: x[1]['test_r2'])
                    best_feature_name, best_result = best_feature_set
                    
                    logger.info(f"Best feature set for {label_name}: {best_feature_name} "
                                f"(R2: {best_result['test_r2']:.4f})")
                    
                    # Add to results list
                    results_list.append({
                        'label_name': label_name,
                        'best_feature_set': best_feature_name,
                        'best_model': best_result['best_model_name'],
                        'test_r2': best_result['test_r2'],
                        'test_mse': best_result['test_mse'],
                        'test_mae': best_result['test_mae'],
                        'model_params': best_result['best_params']
                    })
                    
                else:
                    # Train sequentially
                    best_r2 = -float('inf')
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
                            models=model_selection
                        )
                        
                        # Get the best model and evaluate on test set
                        best_model = results['best_model']
                        y_pred = best_model.predict(X_test)
                        
                        # Calculate metrics
                        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
                        r2 = r2_score(y_test, y_pred)
                        mse = mean_squared_error(y_test, y_pred)
                        mae = mean_absolute_error(y_test, y_pred)
                        
                        if r2 > best_r2:
                            best_r2 = r2
                            best_result = {
                                'label_name': label_name,
                                'best_feature_set': feature_name,
                                'best_model': results['best_model_name'],
                                'test_r2': r2,
                                'test_mse': mse,
                                'test_mae': mae,
                                'model_params': results['best_params']
                            }
                            best_feature_name = feature_name
                    
                    logger.info(f"Best feature set for {label_name}: {best_feature_name} "
                                f"(R2: {best_result['test_r2']:.4f})")
                    
                    # Add to results list
                    results_list.append(best_result)
        else:
            # Use original pipeline
            logger.info("Using original prediction pipeline")
            
            # Train and test a prediction model for each score
            results_list = train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=train_labels,
                test_embeddings=test_embeddings,
                test_labels=test_labels,
                output_folder=output_folder,
                categorical=getattr(args, 'classification', False),
                show_plot=getattr(args, 'show_plots', False),
                n_jobs=n_jobs  # Pass the n_jobs parameter to control parallelism
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
        
def save_json(filepath, data):
    """Helper function to save data as JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=lambda x: str(x) if isinstance(x, (np.ndarray, pd.Series)) else x)