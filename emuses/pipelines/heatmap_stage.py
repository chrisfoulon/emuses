import numpy as np
import logging
from pathlib import Path
import pandas as pd
import hdbscan

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.stats_utils import fwhm_to_sigma
from emuses.tools.kernel_regression_utils import run_kernel_heatmap_analysis, ensemble_predict, nested_cv_kernel_regression
from emuses.tools.visualisation import plot_clustering_interactive_with_hover


class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage (kernel regression version)")

        # Use the new naming convention only
        
        # Get prediction coordinates (UMAP embeddings for labeled data)
        prediction_train_coords = context.get('prediction_train_coords')
        
        # Get prediction labels (scores for prediction)
        prediction_train_labels = context.get('prediction_train_labels')
        
        # Get embedding coordinates (UMAP embeddings for unlabelled data used for UMAP training)
        embedding_train_coords = context.get('embedding_train_coords')
        
        # Get feature data for input matrices
        embedding_train_features = context.get('embedding_train_features')
        prediction_train_features = context.get('prediction_train_features')

        # Determine which data to use for the heatmap stage
        if prediction_train_coords is not None and prediction_train_labels is not None:
            # Use labeled data coordinates and labels for heatmap analysis
            embeddings_labelled = prediction_train_coords
            train_labels = prediction_train_labels
            logger.info("Using prediction training data for heatmap analysis.")
            
            # Combine original features for statistical maps
            if embedding_train_features is not None and prediction_train_features is not None:
                combined_input_matrix = np.concatenate([embedding_train_features, prediction_train_features], axis=0)
            else:
                combined_input_matrix = prediction_train_features
                logger.warning("Could not combine input matrices; using only prediction training features.")
        else:
            # Fall back to full embeddings and labels (classic mode)
            embeddings_labelled = embedding_train_coords
            train_labels = prediction_train_labels  # Should be the same in classic mode
            combined_input_matrix = embedding_train_features
            logger.info("Using classic mode data for heatmap analysis.")

        # In label_dataset mode, also get the full UMAP training embeddings
        full_embeddings = None
        
        # Use the standardized naming only
        clusterer = context.get('embedding_train_clusterer')
        
        # If we're in the label_dataset mode, we have both embedding and prediction data
        if prediction_train_coords is not None and embedding_train_coords is not None:
            full_embeddings = embedding_train_coords
            # Compute clustering on the labelled embeddings if not already done
            if 'prediction_train_cluster_labels' not in context:
                # Compute clustering on the combined embeddings of full and labelled data
                combined = np.concatenate([full_embeddings, embeddings_labelled], axis=0)
                context['prediction_train_cluster_labels'] = clusterer.fit_predict(combined)
                context['prediction_train_clusterer'] = clusterer
            cluster_labels = context.get('prediction_train_cluster_labels')
        else:
            cluster_labels = context.get('embedding_train_cluster_labels')

        dataset_type = context.get('dataset_type', 'image')

        if combined_input_matrix is None:
            raise ValueError("Input matrix is required for heatmap analysis.")

        # Prepare scores vectors dictionary
        if getattr(self.config, 'classification', False):
            unique_labels = np.unique(train_labels)
            scores_vectors_dict = {
                str(score_tag): (train_labels == score_tag).astype(int)
                for score_tag in unique_labels
            }
        else:
            if train_labels.ndim == 1:
                scores_vectors_dict = {'score': train_labels}
            else:
                scores_vectors_dict = {
                    f"score_{i}": train_labels[:, i]
                    for i in range(train_labels.shape[1])
                }
        context['score_vectors_dict'] = scores_vectors_dict

        # Set candidate sigma values for the kernel regressor.
        sigma = self.config.heatmap_params.get('sigma', None)
        if sigma is None:
            sigma = np.linspace(0.01, 0.2, num=8)
        else:
            if not isinstance(sigma, (list, np.ndarray)):
                sigma = np.array([sigma])

        fwhm = self.config.heatmap_params.get('fwhm', None)
        if sigma is None and fwhm is not None:
            sigma = fwhm_to_sigma(fwhm)
            logger.info(f"Converted FWHM {fwhm} to sigma {sigma}")
        elif sigma is None and fwhm is None:
            sigma = None
            logger.info("No sigma or FWHM provided; proceeding without smoothing.")

        show_plots = getattr(self.config, 'show_plots', False)
        context['show_plots'] = show_plots
        generate_plots = True

        # Interactive clustering plot: display clustering labels (rather than data labels)
        if getattr(self.config, 'interactive_plot', False):
            interactive_folder = Path(self.config.output_folder) / "interactive_plots"
            interactive_folder.mkdir(exist_ok=True)
            if full_embeddings is not None:
                interactive_path = interactive_folder / "interactive_clustering_labelled_full.html"
                # Combine full embeddings (unlabelled) and labelled embeddings
                combined_embeddings = np.concatenate([full_embeddings, embeddings_labelled], axis=0)
                # combined_cluster_labels = np.concatenate([np.full(full_embeddings.shape[0], -2), cluster_labels], axis=0)
                fig = plot_clustering_interactive_with_hover(
                    combined_embeddings, cluster_labels,
                    output_path=interactive_path,
                    show_plot=False,
                    return_plot=True
                )
                logger.info(f"Interactive clustering plot for labelled & full embeddings saved at: {interactive_path}")
                # Use standardized naming for interactive plots
                context['embedding_and_prediction_clustering_plot'] = fig
            else:
                if getattr(self.config, 'classification', False):
                    interactive_path = interactive_folder / "interactive_clustering_classification.html"
                    fig = plot_clustering_interactive_with_hover(
                        embeddings_labelled, cluster_labels,
                        output_path=interactive_path,
                        show_plot=False,
                        return_plot=True
                    )
                    logger.info(f"Interactive clustering plot (classification) saved at: {interactive_path}")
                    # Use standardized naming for interactive plots
                    context['prediction_train_clustering_plot'] = fig
                else:
                    interactive_plots = {}
                    for key, score_vec in scores_vectors_dict.items():
                        interactive_path = interactive_folder / f"interactive_clustering_{key}.html"
                        fig = plot_clustering_interactive_with_hover(
                            embeddings_labelled, score_vec,
                            output_path=interactive_path,
                            show_plot=False,
                            return_plot=True
                        )
                        logger.info(f"Interactive clustering plot for score {key} saved at: {interactive_path}")
                        interactive_plots[key] = fig
                    
                    # Use standardized naming for interactive plots by score
                    context['prediction_train_score_clustering_plots'] = interactive_plots

        # Use our robust OOD evaluation function instead of new_pipeline_test
        results = robust_ood_evaluation(
            context=context,
            output_folder=self.config.output_folder,
            classification=getattr(self.config, 'classification', False)
        )

        # Store results in context
        context.update(results)


def robust_ood_evaluation(context, output_folder, classification=True):
    """
    Performs a robust out-of-distribution (OOD) evaluation using kernel logistic regression
    with nested cross-validation. This ensures a proper evaluation where the model 
    predicts on truly unseen data.
    
    For digits_label_dataset specifically, this function:
    1. Takes the full digits dataset (1797 samples)
    2. Identifies the 400 labeled samples subset
    3. Trains a new UMAP model using only the remaining ~1397 samples
    4. Projects the 400 samples through this new UMAP to ensure true OOD evaluation
    
    Parameters:
    -----------
    context : dict
        The pipeline context containing all required data
    output_folder : str or Path
        Directory where results will be saved
    classification : bool
        Whether to treat this as a classification or regression problem
        
    Returns:
    --------
    dict
        Dictionary containing evaluation results
    """
    logger = logging.getLogger(__name__)
    logger.info("Running robust OOD evaluation")
    
    from pathlib import Path
    from sklearn.model_selection import StratifiedKFold, KFold
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, r2_score, mean_squared_error
    import matplotlib.pyplot as plt
    import umap
    import joblib
    
    # Ensure output folder exists
    output_folder = Path(output_folder) / "ood_evaluation"
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Debug: print key context variables to help with debugging
    logger.info(f"Context keys: {list(context.keys())}")
    
    # Check if we're in digits_label_dataset mode by looking for 'labeled_indices' in context
    # or if we're processing the digits_label_dataset by checking the dataset_type
    is_digits_label_dataset = 'labeled_indices' in context or context.get('dataset_type') == 'digits'
    
    if is_digits_label_dataset:
        logger.info("Detected digits_label_dataset mode - setting up true OOD evaluation")
        
        # 1. Get the original data and indices of the 400 labeled samples
        from emuses.tools.inputs_utils import load_and_preprocess_digits_dataset
        all_features, all_labels, labeled_indices = load_and_preprocess_digits_dataset('digits_label_dataset')
        
        # 2. Create mask for the training set (everything except the 400 labeled samples)
        mask = np.ones(len(all_features), dtype=bool)
        mask[labeled_indices] = False
        
        # 3. Train a new UMAP model using only the unlabeled portion (~1397 samples)
        logger.info(f"Training new UMAP model on {np.sum(mask)} samples (excluding labeled subset)")
        
        # Try different ways to get the original UMAP model parameters
        original_umap = None
        umap_model_paths = [
            Path(output_folder).parent / "best_umap_model.joblib",
            Path(output_folder).parent / "umap" / "best_umap_model.joblib"
        ]
        
        for path in umap_model_paths:
            if path.exists():
                try:
                    original_umap = joblib.load(path)
                    logger.info(f"Loaded UMAP model from: {path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load UMAP model from {path}: {e}")
        
        if original_umap is None:
            # Only check for the new naming standard
            original_umap = context.get('embedding_train_umap_model')
            
        if original_umap is not None:
            logger.info("Using parameters from existing UMAP model")
            n_components = original_umap.n_components
            n_neighbors = original_umap.n_neighbors
            min_dist = original_umap.min_dist
            metric = original_umap.metric
        else:
            # Default parameters if original model not available
            logger.info("No existing UMAP model found, using default parameters")
            n_components = 2
            n_neighbors = 15
            min_dist = 0.1
            metric = 'euclidean'
        
        # Create and train the new UMAP model
        true_ood_umap = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            metric=metric,
            random_state=42
        )
        unlabeled_embeddings = true_ood_umap.fit_transform(all_features[mask])
        
        # 4. Get the labeled data (400 samples) and transform through the new UMAP
        labeled_data = all_features[labeled_indices]
        labeled_scores = all_labels[labeled_indices]
        
        # Transform labeled data through the new UMAP model to get true OOD embeddings
        labeled_embeddings = true_ood_umap.transform(labeled_data)
        
        logger.info(f"Successfully created true OOD embeddings for {len(labeled_indices)} labeled samples")
        
        # Save the new UMAP model and embeddings for reference
        joblib.dump(true_ood_umap, output_folder / "true_ood_umap_model.joblib")
        np.save(output_folder / "unlabeled_embeddings.npy", unlabeled_embeddings)
        np.save(output_folder / "labeled_ood_embeddings.npy", labeled_embeddings)
    else:
        # For non-digits_label_dataset mode, use the standard approach
        logger.info("Using standard evaluation approach (not digits_label_dataset mode)")
        
        # Get required data from context - use only the new naming
        umap_model = context.get('embedding_train_umap_model')
        if umap_model is None:
            # Try loading from file if not in context
            umap_path = Path(output_folder).parent / "best_umap_model.joblib"
            if umap_path.exists():
                try:
                    umap_model = joblib.load(umap_path)
                    logger.info(f"Loaded UMAP model from file: {umap_path}")
                except Exception as e:
                    raise ValueError(f"Failed to load UMAP model from {umap_path}: {e}")
            else:
                raise ValueError("embedding_train_umap_model is required for OOD evaluation")
        
        # Use only new naming convention
        labeled_data = context.get('prediction_train_features')
        labeled_scores = context.get('prediction_train_labels')
        
        if labeled_data is None or labeled_scores is None:
            raise ValueError(f"prediction_train_features and prediction_train_labels are required for OOD evaluation. Available keys: {list(context.keys())}")
        
        # Project labeled data through the UMAP model to get embeddings
        labeled_embeddings = umap_model.transform(labeled_data)
        
        # Use already-computed embeddings if available
        precomputed_embeddings = context.get('prediction_train_coords')
        
        if precomputed_embeddings is not None:
            # Verify that our newly computed embeddings match the precomputed ones
            # Small differences are expected due to floating point, but large differences indicate a problem
            if len(precomputed_embeddings) == len(labeled_embeddings):
                embedding_diff = np.mean(np.abs(labeled_embeddings - precomputed_embeddings))
                logger.info(f"Mean absolute difference between computed and precomputed embeddings: {embedding_diff}")
                
                # Use precomputed for consistency with rest of pipeline
                labeled_embeddings = precomputed_embeddings
            else:
                logger.warning("Precomputed embeddings found but length doesn't match labeled data")
    
    # Define CV strategy
    n_splits = 5
    random_state = 42
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state) if classification \
        else KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    results = {}
    
    if classification:
        # Handle multi-class classification by training one-vs-rest models
        unique_labels = np.unique(labeled_scores)
        
        # Store all class probabilities for later ROC analysis
        all_true_labels = []
        all_predicted_probs = {label: [] for label in unique_labels}
        
        # Overall tracking
        all_true = []
        all_pred = []
        
        # For each class, create a binary classification problem
        for label in unique_labels:
            logger.info(f"Training OOD model for class {label}")
            
            # Create binary labels (1 for current class, 0 for others)
            binary_labels = (labeled_scores == label).astype(int)
            
            # Nested CV results for this class
            fold_metrics = []
            
            # Outer CV loop
            for fold, (train_idx, test_idx) in enumerate(cv.split(labeled_embeddings, binary_labels)):
                X_train, X_test = labeled_embeddings[train_idx], labeled_embeddings[test_idx]
                y_train, y_test = binary_labels[train_idx], binary_labels[test_idx]
                
                # Inner CV to find best sigma
                best_sigma, best_score = None, -np.inf
                for sigma in np.logspace(-2, 0, 10):  # Try various sigma values
                    from emuses.tools.kernel_regression_utils import KernelLogisticRegressor
                    inner_cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=random_state)
                    scores = []
                    
                    for inner_train_idx, inner_val_idx in inner_cv.split(X_train, y_train):
                        X_inner_train, X_inner_val = X_train[inner_train_idx], X_train[inner_val_idx]
                        y_inner_train, y_inner_val = y_train[inner_train_idx], y_inner_val[inner_val_idx]
                        
                        klr = KernelLogisticRegressor(sigma=sigma)  # Remove 'kernel' parameter
                        klr.fit(X_inner_train, y_inner_train)
                        y_inner_pred = klr.predict(X_inner_val)
                        scores.append(balanced_accuracy_score(y_inner_val, y_inner_pred))
                    
                    mean_score = np.mean(scores)
                    if mean_score > best_score:
                        best_score = mean_score
                        best_sigma = sigma
                
                # Train model on full training fold with best sigma
                klr = KernelLogisticRegressor(sigma=best_sigma)  # Remove 'kernel' parameter
                
                klr.fit(X_train, y_train)
                
                # Predict on test fold
                y_pred = klr.predict(X_test)
                y_pred_proba = klr.predict_proba(X_test)
                
                # Store true labels and predictions for overall evaluation
                all_true.extend(y_test)
                all_pred.extend(y_pred)
                
                # Store true labels and probabilities for ROC analysis
                all_true_labels.extend(y_test)
                all_predicted_probs[label].extend(y_pred_proba)
                
                # Calculate metrics
                acc = accuracy_score(y_test, y_pred)
                bal_acc = balanced_accuracy_score(y_test, y_pred)
                
                # Store results for this fold
                fold_metrics.append({
                    'fold': fold,
                    'accuracy': acc,
                    'balanced_accuracy': bal_acc,
                    'best_sigma': best_sigma
                })
                
                logger.info(f"  Class {label} - Fold {fold}: Accuracy={acc:.4f}, Balanced Accuracy={bal_acc:.4f}")
            
            # Calculate average metrics across folds
            avg_metrics = {
                'accuracy': np.mean([m['accuracy'] for m in fold_metrics]),
                'balanced_accuracy': np.mean([m['balanced_accuracy'] for m in fold_metrics]),
                'fold_metrics': fold_metrics
            }
            
            # Store results for this class
            results[f'class_{label}'] = avg_metrics
            
            logger.info(f"  Class {label} - Average: Accuracy={avg_metrics['accuracy']:.4f}, "
                       f"Balanced Accuracy={avg_metrics['balanced_accuracy']:.4f}")
        
        # Calculate overall multi-class accuracy
        from sklearn.metrics import confusion_matrix
        
        # Convert to array for easier processing
        all_true = np.array(all_true)
        all_pred = np.array(all_pred)
        
        # Get all unique classes in true/pred
        all_classes = np.unique(np.concatenate([unique_labels, np.unique(all_pred)]))
        
        # Create a confusion matrix to compare one-vs-rest predictions
        # For each sample, pick the class with highest probability
        true_multiclass = labeled_scores.copy()
        pred_multiclass = np.zeros_like(true_multiclass)
        
        # For each sample, find the class with highest probability
        for i in range(len(labeled_embeddings)):
            probs = [all_predicted_probs[label][i] if i < len(all_predicted_probs[label]) else 0 
                    for label in unique_labels]
            pred_multiclass[i] = unique_labels[np.argmax(probs)]
        
        overall_acc = accuracy_score(true_multiclass, pred_multiclass)
        overall_bal_acc = balanced_accuracy_score(true_multiclass, pred_multiclass)
        
        # Create a confusion matrix
        cm = confusion_matrix(true_multiclass, pred_multiclass, labels=all_classes)
        
        # Plot and save confusion matrix
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('OOD Confusion Matrix')
        plt.colorbar()
        tick_marks = np.arange(len(all_classes))
        plt.xticks(tick_marks, all_classes, rotation=45)
        plt.yticks(tick_marks, all_classes)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        plt.tight_layout()
        plt.ylabel('True label')
        plt.xlabel('Predicted label')
        plt.savefig(output_folder / "confusion_matrix.png")
        plt.close()
        
        # Store overall results
        results['overall'] = {
            'accuracy': overall_acc,
            'balanced_accuracy': overall_bal_acc,
            'confusion_matrix': cm.tolist()
        }
        
        logger.info(f"Overall multi-class accuracy: {overall_acc:.4f}")
        logger.info(f"Overall multi-class balanced accuracy: {overall_bal_acc:.4f}")
        
    else:
        # For regression, use a single model
        logger.info("Training OOD regression model")
        
        # Nested CV for regression
        fold_metrics = []
        
        all_true = []
        all_pred = []
        
        for fold, (train_idx, test_idx) in enumerate(cv.split(labeled_embeddings)):
            X_train, X_test = labeled_embeddings[train_idx], labeled_embeddings[test_idx]
            y_train, y_test = labeled_scores[train_idx], labeled_scores[test_idx]
            
            # Inner CV to find best sigma
            best_sigma, best_score = None, -np.inf
            for sigma in np.logspace(-2, 0, 10):
                from emuses.tools.kernel_regression_utils import KernelRegressor
                inner_cv = KFold(n_splits=3, shuffle=True, random_state=random_state)
                scores = []
                
                for inner_train_idx, inner_val_idx in inner_cv.split(X_train):
                    X_inner_train, X_inner_val = X_train[inner_train_idx], X_train[inner_val_idx]
                    y_inner_train, y_inner_val = y_train[inner_train_idx], y_inner_val[inner_val_idx]
                    
                    kr = KernelRegressor(kernel='rbf', sigma=sigma)
                    kr.fit(X_inner_train, y_inner_train)
                    y_inner_pred = kr.predict(X_inner_val)
                    scores.append(r2_score(y_inner_val, y_inner_pred))
                
                mean_score = np.mean(scores)
                if mean_score > best_score:
                    best_score = mean_score
                    best_sigma = sigma
            
            # Train model on full training fold with best sigma
            from emuses.tools.kernel_regression_utils import KernelRegressor
            kr = KernelRegressor(kernel='rbf', sigma=best_sigma)
            kr.fit(X_train, y_train)
            
            # Predict on test fold
            y_pred = kr.predict(X_test)
            
            # Store for overall evaluation
            all_true.extend(y_test)
            all_pred.extend(y_pred)
            
            # Calculate metrics
            r2 = r2_score(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            
            # Store results for this fold
            fold_metrics.append({
                'fold': fold,
                'r2_score': r2,
                'mse': mse,
                'best_sigma': best_sigma
            })
            
            logger.info(f"  Fold {fold}: R² Score={r2:.4f}, MSE={mse:.4f}")
        
        # Calculate average metrics across folds
        avg_metrics = {
            'r2_score': np.mean([m['r2_score'] for m in fold_metrics]),
            'mse': np.mean([m['mse'] for m in fold_metrics]),
            'fold_metrics': fold_metrics
        }
        
        # Store overall results
        results['overall'] = avg_metrics
        
        # Plot predicted vs true values
        plt.figure(figsize=(10, 8))
        plt.scatter(all_true, all_pred, alpha=0.5)
        plt.plot([min(all_true), max(all_true)], [min(all_true), max(all_true)], 'r--')
        plt.title('OOD Predicted vs True Values')
        plt.xlabel('True Values')
        plt.ylabel('Predicted Values')
        plt.savefig(output_folder / "pred_vs_true.png")
        plt.close()
        
        logger.info(f"Overall R² Score: {avg_metrics['r2_score']:.4f}")
        logger.info(f"Overall MSE: {avg_metrics['mse']:.4f}")
    
    # Save results to file
    import json
    
    # Convert NumPy arrays to lists for JSON serialization
    for key in results:
        if isinstance(results[key], dict):
            for subkey in results[key]:
                if isinstance(results[key][subkey], np.ndarray):
                    results[key][subkey] = results[key][subkey].tolist()
    
    with open(output_folder / "ood_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("OOD evaluation complete. Results saved to JSON file.")
    
    return {
        'ood_evaluation_results': results,
        'ood_evaluation_output_folder': str(output_folder)
    }
