from pathlib import Path
import logging
import pandas as pd
from bcblib.tools.general_utils import save_json

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.kernel_regression_utils import evaluate_ensemble_on_test
from emuses.tools.stats_utils import train_and_test_model_per_label


class PredictionStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Prediction Stage (Test Evaluation)")

        args = self.config.args

        print("WE ARE DEBUGGING RIGHT NOW")
        exit()

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

        # Optional: Run legacy prediction if requested.
        if getattr(args, 'run_old_prediction', False):
            train_and_test_model_per_label(
                train_embeddings=train_embeddings,
                train_labels=train_labels,
                test_embeddings=test_embeddings,
                test_labels=test_labels,
                output_folder=self.config.output_folder / 'prediction_models',
                categorical=getattr(args, 'classification', False),
                show_plot=getattr(args, 'show_plots', False)
            )
            logger.info("Legacy prediction pipeline executed and results saved.")

        # Retrieve the ensemble of kernel regression models from the heatmap stage.
        heatmap_results = context.get('heatmap_plots', {})
        if not heatmap_results:
            raise ValueError("No heatmap results available in context to retrieve kernel regression models.")

        # For classification, iterate over each score tag.
        if getattr(args, 'classification', False):
            results_list = []
            for score_tag in sorted(heatmap_results.keys()):
                models = heatmap_results[score_tag].get('models')
                if models is None:
                    logger.error(f"No kernel regression models found for score tag '{score_tag}'. Skipping.")
                    continue
                try:
                    parts = score_tag.split('_')
                    # If the key is just a number (e.g. "0"), use it directly.
                    if len(parts) == 1:
                        score_index = int(score_tag)
                    else:
                        score_index = int(parts[1])
                except Exception as e:
                    logger.error(f"Failed to extract index from score tag '{score_tag}': {e}. Skipping.")
                    continue

                # If test_labels is multi-column, extract the corresponding column.
                if test_labels.ndim == 1:
                    y_test_column = (test_labels == int(score_tag)).astype(int)
                else:
                    if score_index >= test_labels.shape[1]:
                        logger.error(
                            f"Score index {score_index} out of range for test_labels with shape {test_labels.shape}. "
                            f"Skipping.")
                        continue
                    y_test_column = test_labels[:, score_index]

                performance = evaluate_ensemble_on_test(models, test_embeddings, y_test_column,
                                                        classification=True)
                result = {
                    'score_tag': score_tag,
                    'accuracy': performance.get('accuracy', None),
                    'confusion_matrix': performance.get('confusion_matrix', None),
                    'roc_auc': performance.get('roc_auc', None),
                    'f1_score': performance.get('f1_score', None),
                    'precision': performance.get('precision', None),
                    'recall': performance.get('recall', None)
                }
                results_list.append(result)
                logger.info(f"Test performance for {score_tag}: {result}")

            if not results_list:
                raise ValueError("No test performance results could be computed for classification.")

            # Save results to CSV.
            performance_df = pd.DataFrame(results_list)
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_csv_file = output_folder / "prediction_performance_classification.csv"
            performance_df.to_csv(perf_csv_file, index=False)
            logger.info(f"Saved test performance metrics (classification) to {perf_csv_file}")

            # Save performance as JSON and CSV
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_json_file = output_folder / "prediction_performance.json"
            save_json(perf_json_file, results_list)
            logger.info(f"Saved test performance metrics (classification) to {perf_json_file}")
        else:
            # Regression mode: we expect test_labels to have one column per predicted variable.
            results_list = []
            # Iterate over all score tags; assume they are named 'score_i' where i is the column index.
            for score_tag in sorted(heatmap_results.keys()):
                models = heatmap_results[score_tag].get('models')
                if models is None:
                    logger.error(f"No kernel regression models found for score tag '{score_tag}'. Skipping.")
                    continue
                try:
                    # Extract the index from the score tag, e.g., "score_0" -> 0
                    score_index = int(score_tag.split('_')[1])
                except Exception as e:
                    logger.error(f"Failed to extract index from score tag '{score_tag}': {e}. Skipping.")
                    continue

                if test_labels.ndim == 1:
                    y_test_column = test_labels
                else:
                    if score_index >= test_labels.shape[1]:
                        logger.error(
                            f"Score index {score_index} out of range for test_labels with shape {test_labels.shape}. Skipping.")
                        continue
                    y_test_column = test_labels[:, score_index]

                performance = evaluate_ensemble_on_test(models, test_embeddings, y_test_column,
                                                        classification=False)
                # Extract only the metrics we want to save.
                result = {
                    'score_tag': score_tag,
                    'r2': performance.get('r2', None),
                    'mse': performance.get('mse', None),
                    'mae': performance.get('mae', None),
                    'normalized_mse_%': performance.get('normalized_mse_%', None),
                    'normalized_mae_%': performance.get('normalized_mae_%', None)
                }
                results_list.append(result)
                logger.info(f"Test performance for {score_tag}: {result}")

            if not results_list:
                raise ValueError("No test performance results could be computed.")

            # Convert the results list into a DataFrame and save as CSV.
            performance_df = pd.DataFrame(results_list)
            output_folder = Path(self.config.output_folder) / "prediction_performance"
            output_folder.mkdir(parents=True, exist_ok=True)
            perf_csv_file = output_folder / "prediction_performance.csv"
            performance_df.to_csv(perf_csv_file, index=False)
            logger.info(f"Saved test performance metrics (regression) to {perf_csv_file}")

            # Optionally, also save as JSON.
            perf_json_file = output_folder / "prediction_performance.json"
            save_json(perf_json_file, results_list)
            logger.info(f"Saved test performance JSON to {perf_json_file}")


def train_nested_cv_gp(X, y, test_size=0.2, n_outer_folds=5, n_inner_folds=3, kernel_types=None,
                       noise_var_range=None, optimization_steps=2, max_iters=200, verbose=True):
    """
    Train a Gaussian Process model using nested cross-validation.
    
    Parameters:
    -----------
    X : numpy.ndarray
        The training data features.
    y : numpy.ndarray
        The target values.
    test_size : float, default=0.2
        The proportion of data to use for testing.
    n_outer_folds : int, default=5
        Number of outer CV folds.
    n_inner_folds : int, default=3
        Number of inner CV folds.
    kernel_types : list, default=None
        List of kernel types to try. If None, defaults to ['RBF', 'Matern52'].
    noise_var_range : list, default=None
        Range of noise variance values to try. If None, defaults to [0.001, 0.01, 0.1, 1.0].
    optimization_steps : int, default=2
        Number of refinement steps for noise variance selection.
    max_iters : int, default=200
        Maximum number of iterations for GP model optimization.
    verbose : bool, default=True
        Whether to print progress information.
        
    Returns:
    --------
    best_models : list
        List of best models from each outer fold.
    performance : dict
        Performance metrics.
    """
    import numpy as np
    import GPy
    from sklearn.model_selection import KFold
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
    
    if kernel_types is None:
        kernel_types = ['RBF', 'Matern52']
    
    if noise_var_range is None:
        noise_var_range = [0.001, 0.01, 0.1, 1.0]
    
    # Reshape y if needed
    if len(y.shape) == 1:
        y = y.reshape(-1, 1)
    
    best_models = []
    all_fold_metrics = []
    best_kernel_types = []
    best_noise_vars = []
    
    # Outer CV loop
    kf_outer = KFold(n_splits=n_outer_folds, shuffle=True, random_state=42)
    
    for fold_idx, (train_idx, test_idx) in enumerate(kf_outer.split(X)):
        if verbose:
            print(f"\nOuter Fold {fold_idx+1}/{n_outer_folds}")
        
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        best_kernel = None
        best_noise_var = None
        best_r2 = -np.inf
        
        # Evaluate different kernel types
        for kernel_type in kernel_types:
            if verbose:
                print(f"  Testing kernel: {kernel_type}")
            
            # Two-step noise variance refinement
            for step in range(optimization_steps):
                if step == 0:
                    # Initial testing with the full range
                    current_noise_range = noise_var_range
                else:
                    # Refine around the best noise variance from the previous step
                    best_idx = np.argmax([result['r2'] for result in current_results])
                    best_noise = current_noise_range[best_idx]
                    
                    # Create a refined range around the best noise variance
                    if best_idx == 0:
                        lower = 0.7 * best_noise
                        upper = 2.0 * best_noise
                    elif best_idx == len(current_noise_range) - 1:
                        lower = 0.5 * best_noise
                        upper = 1.4 * best_noise
                    else:
                        lower = 0.7 * best_noise
                        upper = 1.4 * best_noise
                    
                    current_noise_range = np.linspace(lower, upper, num=5)
                
                current_results = []
                
                # Test each noise variance
                for noise_var_idx, noise_var in enumerate(current_noise_range):
                    if verbose:
                        print(f"    Testing noise {noise_var_idx+1}/{len(current_noise_range)}: {noise_var:.6f}")
                    
                    # Inner CV loop
                    inner_scores = []
                    kf_inner = KFold(n_splits=n_inner_folds, shuffle=True, random_state=42)
                    
                    for inner_train_idx, inner_val_idx in kf_inner.split(X_train):
                        X_inner_train, X_inner_val = X_train[inner_train_idx], X_train[inner_val_idx]
                        y_inner_train, y_inner_val = y_train[inner_train_idx], y_train[inner_val_idx]
                        
                        # Create and train GP model
                        if kernel_type == 'RBF':
                            kern = GPy.kern.RBF(input_dim=X.shape[1], ARD=True)
                        elif kernel_type == 'Matern52':
                            kern = GPy.kern.Matern52(input_dim=X.shape[1], ARD=True)
                        else:
                            raise ValueError(f"Unsupported kernel type: {kernel_type}")
                        
                        # Create the GP model with specific noise variance
                        try:
                            inner_fold_start = time.time()
                            if verbose:
                                print(f"      Inner fold {len(inner_scores)+1}/{n_inner_folds}: Starting optimization...")
                            
                            model = GPy.models.GPRegression(X_inner_train, y_inner_train, kern)
                            model.Gaussian_noise.variance = noise_var
                            
                            # Constrain the noise variance to be close to the desired value
                            # but allow some flexibility for better optimization
                            noise_lower = max(1e-6, noise_var * 0.5)
                            noise_upper = min(10.0, noise_var * 2.0)
                            model.Gaussian_noise.variance.constrain_bounded(noise_lower, noise_upper, warning=False)
                            
                            # Add jitter for numerical stability
                            model.kern.add_jitter(1e-8)
                            
                            # Use the custom optimization function with fallback mechanisms
                            model = optimize_gp_model(model, max_iter=max_iters, verbose=False)
                            
                            # Predict on validation set
                            y_pred_mean, _ = model.predict(X_inner_val)
                            
                            # Calculate R² score
                            r2 = r2_score(y_inner_val, y_pred_mean)
                            inner_fold_time = time.time() - inner_fold_start
                            
                            if verbose:
                                print(f"      Inner fold {len(inner_scores)+1}/{n_inner_folds}: Optimization complete in {inner_fold_time:.2f}s")
                                print(f"      Inner fold {len(inner_scores)+1}/{n_inner_folds}: R²={r2:.4f}, Time: {inner_fold_time:.2f}s")
                            
                            inner_scores.append({'r2': r2, 'time': inner_fold_time})
                        except Exception as e:
                            if verbose:
                                print(f"      Inner fold error: {e}")
                            inner_scores.append({'r2': -np.inf, 'time': 0.0})
                    
                    # Calculate mean performance across inner folds
                    mean_r2 = np.mean([score['r2'] for score in inner_scores])
                    mean_time = np.sum([score['time'] for score in inner_scores])
                    
                    if verbose:
                        print(f"    Noise: {noise_var:.6f}, Mean R²: {mean_r2:.4f}, Time: {mean_time:.2f}s")
                    
                    current_results.append({
                        'noise_var': noise_var,
                        'r2': mean_r2,
                        'time': mean_time
                    })
                
                # Find the best noise variance in the current step
                best_step_idx = np.argmax([result['r2'] for result in current_results])
                best_step_noise = current_noise_range[best_step_idx]
                best_step_r2 = current_results[best_step_idx]['r2']
                
                if step > 0:
                    improvement = best_step_r2 - prev_best_r2
                    if verbose:
                        print(f"  Step {step+1} complete - Best noise: {best_step_noise:.6f}, R²: {best_step_r2:.4f}")
                        print(f"  Improvement: {improvement:.6f}, Time: {sum([r['time'] for r in current_results]):.2f}s")
                    
                    # Check for convergence
                    if abs(improvement) < 0.001:
                        if verbose:
                            print("  Refinement converged (improvement < 0.001)")
                        break
                else:
                    if verbose:
                        print(f"  Step {step+1} complete - Best noise: {best_step_noise:.6f}, R²: {best_step_r2:.4f}")
                        print(f"  Improvement: inf, Time: {sum([r['time'] for r in current_results]):.2f}s")
                
                prev_best_r2 = best_step_r2
            
            kernel_time = sum([sum([r['time'] for r in batch]) for batch in [current_results]])
            if verbose:
                print(f"  Kernel {kernel_type} evaluation complete in {kernel_time:.2f}s")
            
            # Update the best kernel and noise if better performance
            if best_step_r2 > best_r2:
                best_r2 = best_step_r2
                best_kernel = kernel_type
                best_noise_var = best_step_noise
        
        # Train final model for outer fold
        if verbose:
            print(f"  Outer fold - Final best kernel: {best_kernel}, Best noise: {best_noise_var}")
            print(f"  Training final model for outer fold...")
        
        # Create final kernel
        if best_kernel == 'RBF':
            final_kern = GPy.kern.RBF(input_dim=X.shape[1], ARD=True)
        elif best_kernel == 'Matern52':
            final_kern = GPy.kern.Matern52(input_dim=X.shape[1], ARD=True)
        
        # Create and train final model
        final_model = GPy.models.GPRegression(X_train, y_train, final_kern)
        final_model.Gaussian_noise.variance = best_noise_var
        
        # Add jitter for numerical stability
        final_model.kern.add_jitter(1e-8)
        
        # Train final model
        start_time = time.time()
        final_model = optimize_gp_model(final_model, max_iter=max_iters, verbose=verbose)
        train_time = time.time() - start_time
        
        if verbose:
            print(f"  Final model training complete in {train_time:.2f}s")
        
        # Evaluate on test set
        start_time = time.time()
        y_pred_mean, _ = final_model.predict(X_test)
        test_time = time.time() - start_time
        
        # Calculate performance metrics
        r2 = r2_score(y_test, y_pred_mean)
        mse = mean_squared_error(y_test, y_pred_mean)
        mae = mean_absolute_error(y_test, y_pred_mean)
        
        if verbose:
            print(f"  Test set evaluation complete in {test_time:.2f}s")
            print(f"  Outer fold test performance - R²: {r2:.4f}, MSE: {mse:.4f}, MAE: {mae:.4f}")
            print(f"  Outer fold {fold_idx+1} complete in {kernel_time + train_time + test_time:.2f}s")
        
        # Store results
        fold_metrics = {
            'fold': fold_idx,
            'r2': r2,
            'mse': mse,
            'mae': mae,
            'best_kernel': best_kernel,
            'best_noise_var': best_noise_var,
            'training_time': train_time,
            'prediction_time': test_time
        }
        all_fold_metrics.append(fold_metrics)
        
        # Store best model and parameters
        best_models.append(final_model)
        best_kernel_types.append(best_kernel)
        best_noise_vars.append(best_noise_var)
    
    # Aggregate results
    avg_r2 = np.mean([metrics['r2'] for metrics in all_fold_metrics])
    
    performance = {
        'gp_r2': np.mean([metrics['r2'] for metrics in all_fold_metrics]),
        'gp_mse': np.mean([metrics['mse'] for metrics in all_fold_metrics]),
        'gp_mae': np.mean([metrics['mae'] for metrics in all_fold_metrics]),
        'avg_cv_r2': avg_r2,
        'best_kernel_types': best_kernel_types,
        'best_noise_vars': best_noise_vars
    }
    
    return best_models, performance