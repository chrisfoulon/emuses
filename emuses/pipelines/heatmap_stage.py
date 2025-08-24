import logging
from datetime import datetime
from pathlib import Path

import hdbscan
import joblib
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import optuna
import pandas as pd
import umap
from bcblib.tools.general_utils import save_json
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, mean_squared_error, r2_score)
from sklearn.model_selection import KFold, StratifiedKFold

from emuses.config.optim_configs_predict import (load_optim_dict_predict,
                                                 optim_dict_predict)
from emuses.observability import get_logger, track_scientific_operation
from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.ae_optuna import optimize_ae_pretraining
from emuses.tools.data_preproc import filter_nan_rows
from emuses.tools.inputs_utils import (get_array_info,
                                       load_and_preprocess_digits_dataset)
from emuses.tools.kernel_regression_utils import (KernelLogisticRegressor,
                                                  KernelRegressor,
                                                  ensemble_predict,
                                                  nested_cv_kernel_regression,
                                                  run_kernel_heatmap_analysis)
from emuses.tools.optim_utils import suggest_parameters_conditional
from emuses.tools.optuna_cv import nested_optuna_cv
from emuses.tools.visualisation import plot_clustering_interactive_with_hover

# Import new model I/O system
from ..tools.model_io import ModelIOManager


def _optimise_target(
    col_idx,
    X,
    Y,
    task,
    cfg,
    out_dir,
    logger_name,
    optim_dict,
    pretrained_ae=None,
    n_jobs=-1,
):
    """
    Runs nested Optuna-CV for one target column and returns artefacts.
    Executed in a forked process by joblib → must be picklable.
    """
    logger = logging.getLogger(logger_name)

    tag = f"target_{col_idx}"
    Xi, yi, keep_mask = filter_nan_rows(X, Y[:, col_idx])

    if len(yi) < 10:  # arbitrary sanity threshold
        logger.warning("%s skipped – only %d non-NaN rows", tag, len(yi))
        return tag, np.array([]), []  # skip optimisation

    scores, pipes = nested_optuna_cv(
        Xi,
        yi,
        task=task,
        n_outer=cfg.outer_folds,
        n_trials=cfg.optuna_trials,
        target_tag=tag,
        output_folder=out_dir,
        optim_dict=optim_dict,
        pretrained_ae=pretrained_ae,
        n_jobs=n_jobs,
    )
    logger.info(
        "%s  kept %d / %d rows  -  mean=%.3f", tag, len(yi), len(Y), scores.mean()
    )

    return tag, scores, pipes


class HeatmapStage(PipelineStage):
    def __init__(self, config, output_format_info):
        super().__init__(config)
        self.output_format_info = output_format_info

    def run(self, context, progress_queue=None):
        logger = logging.getLogger(__name__)
        logger.info("Running Heatmap Stage (kernel regression version)")

        # Use the new naming convention only

        # Get prediction coordinates (UMAP embeddings for labeled data)
        prediction_train_coords = context.get("prediction_train_coords")

        # Get prediction labels (scores for prediction)
        prediction_train_labels = context.get("prediction_train_labels")

        # Get embedding coordinates (UMAP embeddings for unlabelled data used for UMAP training)
        # embedding_train_coords = context.get("embedding_train_coords")  # Unused

        # Get feature data for input matrices
        # embedding_train_features = context.get("embedding_train_features")  # Unused
        # prediction_train_features = context.get("prediction_train_features")  # Unused

        # Decide whether we are in regression or classification mode
        task = "clf" if getattr(self.config, "classification", False) else "reg"

        # ------------------------------------------------------------------
        # Load or generate the prediction optimization dictionary.
        # ------------------------------------------------------------------
        if "optim_dict_predict" in context and context["optim_dict_predict"]:
            optim_dict_predict_selected = context["optim_dict_predict"]
        elif "cli_args" in context and "prediction_optim_dict" in context["cli_args"]:
            prediction_optim_dict_name = context["cli_args"]["prediction_optim_dict"]
            try:
                optim_dict_predict_selected = load_optim_dict_predict(
                    prediction_optim_dict_name
                )
                logger.info(
                    f"Loaded prediction optimization dictionary: '{prediction_optim_dict_name}'"
                )
            except Exception as e:
                logger.error(
                    f"Error loading prediction optim_dict '{prediction_optim_dict_name}': {e}. Falling back to default."
                )
                optim_dict_predict_selected = optim_dict_predict
        else:
            optim_dict_predict_selected = optim_dict_predict

        # ------------------------------------------------------------------
        # 1 ─ Assemble the design matrix (X) and targets (y) for Optuna
        #     You can later replace `prediction_train_coords` by any feature
        #     stack you build (e.g. RawCoords ⊕ GWD, polynomial terms, …)
        # ------------------------------------------------------------------
        X = prediction_train_coords  # shape (n_samples, 2)
        y = prediction_train_labels  # shape (n_samples,) or (n_samples, p)

        # Store everything in context for the next step (nested CV / training)
        context.update(
            {
                "prediction_X": X,
                "prediction_y": y,
                "prediction_task": task,
                "optim_dict_predict": optim_dict_predict_selected,
            }
        )

        # ------------------------------------------------------------------
        # 2 ─ Sanity-check the search space: grab ONE random draw
        #     This lets you inspect what Optuna will actually see.
        # ------------------------------------------------------------------
        _tmp_study = optuna.create_study()  # direction irrelevant here
        _tmp_trial = _tmp_study.ask()  # empty trial, no objective yet
        sample_params = suggest_parameters_conditional(
            _tmp_trial, optim_dict_predict_selected
        )
        logger.info("[Optuna-check] example sampled hyper-parameters ↓")
        logger.info(sample_params)
        _tmp_study.tell(_tmp_trial, 0.0)  # close the trial cleanly
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # 2.5 ─ AE/VAE Pretraining (if needed)
        #       Check if the optimization space includes AE features and run
        #       pretraining if enabled in config
        # ------------------------------------------------------------------
        ae_results = None

        # Check if AE pretraining should be enabled
        use_ae_pretrain = getattr(self.config, "use_ae_pretrain", False)
        feat_choices = optim_dict_predict_selected["param"]["features"]["feat_type"][
            "choices"
        ]
        has_ae_choice = "ae" in feat_choices

        # Auto-enable AE pretraining if optimization dictionary includes AE features
        # This ensures AE pretraining runs whenever "ae" is in the feature choices
        if not use_ae_pretrain and has_ae_choice:
            use_ae_pretrain = True
            logger.info(
                "Auto-enabling AE pretraining: optim dict contains 'ae' features"
            )

        logger.info("=== AE PRETRAINING STATUS ===")
        logger.info(f"use_ae_pretrain (final): {use_ae_pretrain}")
        logger.info(f"feat_type choices: {feat_choices}")
        logger.info(f"'ae' in choices: {has_ae_choice}")
        logger.info(f"Will run AE pretraining: {use_ae_pretrain and has_ae_choice}")

        # Log which optim dict is being used
        if "cli_args" in context and "prediction_optim_dict" in context["cli_args"]:
            logger.info(
                f"Using optim dict from CLI: {context['cli_args']['prediction_optim_dict']}"
            )
        elif "optim_dict_predict" in context:
            logger.info("Using optim dict from context")
        else:
            logger.info("Using default optim_dict_predict")

        if use_ae_pretrain and has_ae_choice:

            logger.info("=== AUTOENCODER PRETRAINING ===")

            # Use prediction coordinates as input for AE pretraining
            ae_input_data = prediction_train_coords

            # First try to load a pretrained AE model
            ae_results = None
            try:
                from emuses.tools.ae_optuna import load_pretrained_ae

                logger.info("Checking for existing pretrained AE model...")
                saved_ae = load_pretrained_ae(self.config.output_folder)

                if saved_ae:
                    logger.info(
                        f"Found pretrained AE model with reconstruction error: {saved_ae['best_score']:.4f}"
                    )
                    logger.info(f"Using saved AE parameters: {saved_ae['best_params']}")

                    # Check if we need to validate the model on current data
                    if getattr(self.config, "validate_loaded_ae", True):
                        # Compute reconstruction error on current data
                        fitted_ae = saved_ae["fitted_ae"]
                        recon_error = np.mean(
                            fitted_ae.get_reconstruction_error(ae_input_data)
                        )
                        logger.info(
                            f"Validation reconstruction error on current data: {recon_error:.4f}"
                        )

                        # Decide whether to use the loaded model based on validation
                        max_diff = getattr(self.config, "max_ae_error_diff", 0.2)
                        if abs(recon_error - saved_ae["best_score"]) > max_diff:
                            logger.warning(
                                f"Reconstruction error on current data ({recon_error:.4f}) "
                                f"differs significantly from saved model ({saved_ae['best_score']:.4f}). "
                                f"Training a new model instead."
                            )
                            saved_ae = None

                    if saved_ae:
                        ae_results = saved_ae
                        # Store AE results in context for reuse
                        context["ae_pretraining_results"] = ae_results
                        context["ae_loaded_from_disk"] = True

            except Exception as e:
                logger.warning(f"Error while loading pretrained AE model: {e}")

            # If no saved model was found or it was invalid, train a new one
            if ae_results is None:
                logger.info(
                    "Running AE/VAE pretraining optimization to create a new model..."
                )
                logger.info(
                    "This step will find optimal autoencoder parameters for feature extraction."
                )

                # Get AE optimization parameters from config
                from emuses.config.optim_configs_ae import optim_dict_ae

                ae_trials = optim_dict_ae.get("meta", {}).get("n_trials", 30)

                try:
                    # Use a timestamp in the model name to allow multiple runs
                    import time

                    timestamp = int(time.time())
                    model_name = f"best_ae_model_{timestamp}"

                    ae_results = optimize_ae_pretraining(
                        X=ae_input_data,
                        n_trials=ae_trials,
                        output_folder=self.config.output_folder,
                        random_state=42,
                        model_name=model_name,
                    )

                    logger.info(
                        f"AE pretraining completed. Best reconstruction error: {ae_results['best_score']:.4f}"
                    )
                    logger.info(f"Best AE parameters: {ae_results['best_params']}")

                    # Save a symlink or copy to "best_ae_model" for easy loading in future runs
                    if "model_path" in ae_results and ae_results["model_path"]:
                        try:
                            from pathlib import Path

                            from emuses.tools.model_io import ModelIOManager

                            # Initialize model I/O manager and save as "best_ae_model" too
                            model_manager = ModelIOManager(self.config.output_folder)
                            model_manager.save_model(
                                model=ae_results["fitted_ae"],
                                model_name="best_ae_model",
                                model_type="autoencoder",
                                description=f"Latest pretrained {ae_results['best_params']['ae_type']} model (copy of {model_name})",
                                tags=[
                                    "autoencoder",
                                    ae_results["best_params"]["ae_type"],
                                    "pretrained",
                                    "latest",
                                ],
                                config=ae_results["best_params"],
                                optuna_study=ae_results["study"],
                                optuna_trial=ae_results["study"].best_trial,
                                cv_score=ae_results["best_score"],
                            )
                            logger.info(
                                "Saved additional copy of AE model as 'best_ae_model'"
                            )
                        except Exception as e:
                            logger.warning(f"Could not save additional model copy: {e}")

                    # Store AE results in context for potential reuse
                    context["ae_pretraining_results"] = ae_results
                    context["ae_loaded_from_disk"] = False

                except Exception as e:
                    logger.warning(
                        f"AE pretraining failed: {e}. Continuing without AE pretraining."
                    )
                    ae_results = None
        # ------------------------------------------------------------------

        # --------------  LOOP OVER TARGET COLUMNS  ------------------------
        X = prediction_train_coords  # design matrix
        Y = prediction_train_labels  # 1-D or 2-D

        if Y.ndim == 1:  # ensure 2-D for uniform loop
            Y = Y[:, None]

        task = "clf" if getattr(self.config, "classification", False) else "reg"

        # For multi-class classification, convert to one-vs-rest binary targets
        if task == "clf" and Y.shape[1] == 1:
            unique_classes = np.unique(Y[:, 0])
            n_classes = len(unique_classes)

            if n_classes > 2:
                # Convert multi-class to multiple binary classification targets
                logger.info(
                    "HeatmapStage: converting %d-class problem to %d binary classification targets (one-vs-rest)",
                    n_classes,
                    n_classes,
                )

                # Create binary target matrix: each column is one class vs rest
                Y_binary = np.zeros((Y.shape[0], n_classes), dtype=int)
                for i, class_label in enumerate(unique_classes):
                    Y_binary[:, i] = (Y[:, 0] == class_label).astype(int)

                Y = Y_binary
                logger.info(
                    "HeatmapStage: optimising %d binary classification targets",
                    Y.shape[1],
                )
            else:
                # Binary classification - keep as is
                logger.info("HeatmapStage: optimising 1 binary classification target")
        else:
            # Regression or already multi-target
            if task == "clf":
                logger.info(
                    "HeatmapStage: optimising %d classification targets", Y.shape[1]
                )
            else:
                logger.info(
                    "HeatmapStage: optimising %d regression target(s)", Y.shape[1]
                )

        # Extract the fitted AE if available for use in parallel jobs
        fitted_ae = None
        if ae_results is not None:
            fitted_ae = ae_results.get("fitted_ae")

        n_jobs = getattr(self.config, "n_jobs", -1)
        from joblib import delayed

        from emuses.tools.parallelism_utils import create_safe_parallel

        parallel = create_safe_parallel(n_jobs)
        results = parallel(
            delayed(_optimise_target)(
                col_idx,
                X,
                Y,
                task,
                self.config,
                self.config.output_folder,
                logger.name,  # pass logger name so child can log
                optim_dict_predict_selected,  # pass selected optimization dictionary
                fitted_ae,  # pass pre-fitted AE if available
                n_jobs,  # pass n_jobs parameter
            )
            for col_idx in range(Y.shape[1])
        )

        for tag, scores, pipes in results:
            context.setdefault("prediction_results", {})[tag] = {
                "cv_scores": scores,
                "best_pipelines": pipes,
            }
        
        # Collect trained models for InferenceStage context (performance optimization)
        prediction_models = []
        for tag, result_data in context.get("prediction_results", {}).items():
            best_pipelines = result_data.get("best_pipelines", [])
            for i, pipeline in enumerate(best_pipelines):
                prediction_models.append({
                    'model': pipeline,
                    'target': tag,
                    'fold_info': f"fold_{i}",
                    'name': f"{tag}_fold_{i}"
                })
        
        # Store prediction models in context for InferenceStage performance optimization
        context["prediction_models"] = prediction_models
        logger.info(f"Stored {len(prediction_models)} prediction models in context for inference stage")

        # ------------------------------------------------------------------
        # Generate performance measures CSV files
        # ------------------------------------------------------------------
        self._generate_performance_csv_files(context, task, Y.shape[1], logger)

        # ------------------------------------------------------------------

        # # Determine which data to use for the heatmap stage
        # if prediction_train_coords is not None and prediction_train_labels is not None:
        #     # Use labeled data coordinates and labels for heatmap analysis
        #     embeddings_labelled = prediction_train_coords
        #     train_labels = prediction_train_labels
        #     logger.info("Using prediction training data for heatmap analysis.")

        #     # Combine original features for statistical maps
        #     if (
        #         embedding_train_features is not None
        #         and prediction_train_features is not None
        #     ):
        #         combined_input_matrix = np.concatenate(
        #             [embedding_train_features, prediction_train_features], axis=0
        #         )
        #     else:
        #         combined_input_matrix = prediction_train_features
        #         logger.warning(
        #             "Could not combine input matrices; using only prediction training features."
        #         )
        # else:
        #     # Fall back to full embeddings and labels (classic mode)
        #     embeddings_labelled = embedding_train_coords
        #     train_labels = prediction_train_labels  # Should be the same in classic mode
        #     combined_input_matrix = embedding_train_features
        #     logger.info("Using classic mode data for heatmap analysis.")

        # # In label_dataset mode, also get the full UMAP training embeddings
        # full_embeddings = None

        # # Use the standardized naming only
        # clusterer = context.get("embedding_train_clusterer")

        # # If we're in the label_dataset mode, we have both embedding and prediction data
        # if prediction_train_coords is not None and embedding_train_coords is not None:
        #     full_embeddings = embedding_train_coords
        #     # Compute clustering on the labelled embeddings if not already done
        #     if "prediction_train_cluster_labels" not in context:
        #         # Compute clustering on the combined embeddings of full and labelled data
        #         combined = np.concatenate(
        #             [full_embeddings, embeddings_labelled], axis=0
        #         )
        #         context["prediction_train_cluster_labels"] = clusterer.fit_predict(
        #             combined
        #         )
        #         context["prediction_train_clusterer"] = clusterer
        #     cluster_labels = context.get("prediction_train_cluster_labels")
        # else:
        #     cluster_labels = context.get("embedding_train_cluster_labels")

        # dataset_type = context.get("dataset_type", "image")

        # if combined_input_matrix is None:
        #     raise ValueError("Input matrix is required for heatmap analysis.")

        # # Prepare scores vectors dictionary
        # if getattr(self.config, "classification", False):
        #     unique_labels = np.unique(train_labels)
        #     scores_vectors_dict = {
        #         str(score_tag): (train_labels == score_tag).astype(int)
        #         for score_tag in unique_labels
        #     }
        # else:
        #     if train_labels.ndim == 1:
        #         scores_vectors_dict = {"score": train_labels}
        #     else:
        #         scores_vectors_dict = {
        #             f"score_{i}": train_labels[:, i]
        #             for i in range(train_labels.shape[1])
        #         }
        #         context["score_vectors_dict"] = scores_vectors_dict

        # # Kernel regression will use its internal optimization for sigma values
        # show_plots = getattr(self.config, "show_plots", False)
        # context["show_plots"] = show_plots
        # generate_plots = True

        # # Interactive clustering plot: display clustering labels (rather than data labels)
        # if getattr(self.config, "interactive_plot", False):
        #     interactive_folder = Path(self.config.output_folder) / "interactive_plots"
        #     interactive_folder.mkdir(exist_ok=True)
        #     if full_embeddings is not None:
        #         interactive_path = (
        #             interactive_folder / "interactive_clustering_labelled_full.html"
        #         )
        #         # Combine full embeddings (unlabelled) and labelled embeddings
        #         combined_embeddings = np.concatenate(
        #             [full_embeddings, embeddings_labelled], axis=0
        #         )
        #         # combined_cluster_labels = np.concatenate([np.full(full_embeddings.shape[0], -2), cluster_labels], axis=0)
        #         fig = plot_clustering_interactive_with_hover(
        #             combined_embeddings,
        #             cluster_labels,
        #             output_path=interactive_path,
        #             show_plot=False,
        #             return_plot=True,
        #         )
        #         logger.info(
        #             f"Interactive clustering plot for labelled & full embeddings saved at: {interactive_path}"
        #         )
        #         # Use standardized naming for interactive plots
        #         context["embedding_and_prediction_clustering_plot"] = fig
        #     else:
        #         if getattr(self.config, "classification", False):
        #             interactive_path = (
        #                 interactive_folder
        #                 / "interactive_clustering_classification.html"
        #             )
        #             fig = plot_clustering_interactive_with_hover(
        #                 embeddings_labelled,
        #                 cluster_labels,
        #                 output_path=interactive_path,
        #                 show_plot=False,
        #                 return_plot=True,
        #             )
        #             logger.info(
        #                 f"Interactive clustering plot (classification) saved at: {interactive_path}"
        #             )
        #             # Use standardized naming for interactive plots
        #             context["prediction_train_clustering_plot"] = fig
        #         else:
        #             interactive_plots = {}
        #             for key, score_vec in scores_vectors_dict.items():
        #                 interactive_path = (
        #                     interactive_folder / f"interactive_clustering_{key}.html"
        #                 )
        #                 fig = plot_clustering_interactive_with_hover(
        #                     embeddings_labelled,
        #                     score_vec,
        #                     output_path=interactive_path,
        #                     show_plot=False,
        #                     return_plot=True,
        #                 )
        #                 logger.info(
        #                     f"Interactive clustering plot for score {key} saved at: {interactive_path}"
        #                 )
        #                 interactive_plots[key] = fig

        #             # Use standardized naming for interactive plots by score
        #             context["prediction_train_score_clustering_plots"] = (
        #                 interactive_plots
        #             )
        #             # ==================== DATA PREPARATION COMPLETE ====================
        # # At this point all data has been collected and preprocessed.
        # # The next step would be to call robust_ood_evaluation for model training.

        # # Log the state of the data for inspection
        # logger.info("===== DATA STATE BEFORE MODEL TRAINING =====")
        # logger.info(
        #     f"embeddings_labelled shape: {embeddings_labelled.shape if embeddings_labelled is not None else None}"
        # )
        # logger.info(
        #     f"train_labels shape: {train_labels.shape if train_labels is not None else None}"
        # )
        # logger.info(
        #     f"combined_input_matrix shape: {combined_input_matrix.shape if combined_input_matrix is not None else None}"
        # )
        # logger.info(
        #     f"full_embeddings shape: {full_embeddings.shape if full_embeddings is not None else None}"
        # )
        # logger.info(
        #     f"cluster_labels shape: {cluster_labels.shape if cluster_labels is not None else None}"
        # )
        # logger.info(f"scores_vectors_dict keys: {list(scores_vectors_dict.keys())}")
        # for key, val in scores_vectors_dict.items():
        #     logger.info(
        #         f"  scores_vector '{key}' shape: {val.shape if val is not None else None}"
        #     )
        # logger.info(f"classification: {getattr(self.config, 'classification', False)}")

        # # Create a data inspection directory
        # inspect_dir = Path(self.config.output_folder) / "data_inspection"
        # inspect_dir.mkdir(parents=True, exist_ok=True)

        # # Save basic data summary
        # data_summary = {
        #     "embeddings_labelled_shape": (
        #         embeddings_labelled.shape if embeddings_labelled is not None else None
        #     ),
        #     "train_labels_shape": (
        #         train_labels.shape if train_labels is not None else None
        #     ),
        #     "train_labels_unique": (
        #         np.unique(train_labels).tolist() if train_labels is not None else None
        #     ),
        #     "combined_input_matrix_shape": (
        #         combined_input_matrix.shape
        #         if combined_input_matrix is not None
        #         else None
        #     ),
        #     "full_embeddings_shape": (
        #         full_embeddings.shape if full_embeddings is not None else None
        #     ),
        #     "cluster_labels_shape": (
        #         cluster_labels.shape if cluster_labels is not None else None
        #     ),
        #     "classification": getattr(self.config, "classification", False),
        # }
        # save_json(inspect_dir / "data_summary.json", data_summary)

        # # Create a visualization of the embeddings with labels
        # if embeddings_labelled is not None and embeddings_labelled.shape[1] >= 2:
        #     plt.figure(figsize=(10, 8))
        #     if getattr(self.config, "classification", False):
        #         # For classification, use categorical colors
        #         # Check if train_labels is 2D (contains multiple scores)
        #         if train_labels.ndim > 1 and train_labels.shape[1] > 1:
        #             # For visualization, just use the first score
        #             first_score = train_labels[:, 0]
        #             scatter = plt.scatter(
        #                 embeddings_labelled[:, 0],
        #                 embeddings_labelled[:, 1],
        #                 c=first_score,
        #                 cmap="viridis",
        #                 alpha=0.7,
        #             )
        #             plt.title("UMAP Embeddings Colored by First Class")
        #         else:
        #             # Use the 1D label array directly
        #             scatter = plt.scatter(
        #                 embeddings_labelled[:, 0],
        #                 embeddings_labelled[:, 1],
        #                 c=train_labels,
        #                 cmap="viridis",
        #                 alpha=0.7,
        #             )
        #         plt.colorbar(scatter, label="Class")
        #     else:
        #         # For regression, use continuous colormap
        #         if train_labels.ndim > 1 and train_labels.shape[1] > 1:
        #             # For visualization, just use the first score
        #             first_score = train_labels[:, 0]
        #             scatter = plt.scatter(
        #                 embeddings_labelled[:, 0],
        #                 embeddings_labelled[:, 1],
        #                 c=first_score,
        #                 cmap="coolwarm",
        #                 alpha=0.7,
        #             )
        #             plt.title("UMAP Embeddings Colored by First Score")
        #         else:
        #             scatter = plt.scatter(
        #                 embeddings_labelled[:, 0],
        #                 embeddings_labelled[:, 1],
        #                 c=train_labels,
        #                 cmap="coolwarm",
        #                 alpha=0.7,
        #             )
        #         plt.colorbar(scatter, label="Score")
        #     plt.title("UMAP Embeddings Colored by Target")
        #     plt.xlabel("UMAP Dimension 1")
        #     plt.ylabel("UMAP Dimension 2")
        #     plt.tight_layout()
        #     plt.savefig(inspect_dir / "embeddings_with_labels.png")
        #     plt.close()
        # exit()
        # # Continue with the regular pipeline
        # results = robust_ood_evaluation(
        #     context=context,
        #     output_folder=self.config.output_folder,
        #     classification=getattr(self.config, "classification", False),
        # )

        # Prepare context for InferenceStage (required for pipeline completion)
        prediction_test_features = context.get("prediction_test_features")
        prediction_test_labels = context.get("prediction_test_labels")
        prediction_train_features = context.get("prediction_train_features")
        prediction_train_labels = context.get("prediction_train_labels")

        if prediction_test_features is not None:
            # Use test data for inference (preferred for validation)
            context["inference_features"] = prediction_test_features
            if prediction_test_labels is not None:
                context["inference_labels"] = prediction_test_labels
            logger.info(
                "Prepared prediction test data for inference stage."
            )
        elif prediction_train_features is not None:
            # Fallback to train data if no test data available
            context["inference_features"] = prediction_train_features
            if prediction_train_labels is not None:
                context["inference_labels"] = prediction_train_labels
            logger.info(
                "Prepared prediction training data for inference stage (fallback)."
            )
        else:
            logger.warning("No prediction features found - inference stage may fail")

    def _generate_performance_csv_files(self, context, task, n_targets, logger):
        """
        Generate performance measures CSV files after the parallel optimization loop.

        Creates separate CSV files for each target in target-specific directories,
        plus aggregated summary files for cross-target comparison.

        Parameters
        ----------
        context : dict
            Pipeline context containing prediction_results
        task : str
            "clf" for classification, "reg" for regression
        n_targets : int
            Number of targets that were optimized
        logger : logging.Logger
            Logger instance for status messages
        """
        logger.info("Generating performance measures CSV files...")

        try:
            prediction_results = context.get("prediction_results", {})

            if not prediction_results:
                logger.warning("No prediction results found - skipping CSV generation")
                return

            # Generate timestamp for unique filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = Path(self.config.output_folder)

            # Create summary folder for aggregated files
            summary_folder = output_folder / "performance_summary"
            summary_folder.mkdir(parents=True, exist_ok=True)

            # Prepare data for aggregated CSVs and create per-target files
            summary_data = []
            individual_fold_data = []
            per_target_files_created = []

            for target_tag, result_data in prediction_results.items():
                cv_scores = result_data.get("cv_scores", [])

                if len(cv_scores) == 0:
                    logger.warning(f"No CV scores found for {target_tag}")
                    continue

                # Create target-specific directory (same as model saving)
                target_dir = output_folder / target_tag
                target_dir.mkdir(parents=True, exist_ok=True)

                # Create performance subdirectory within target directory
                target_perf_dir = target_dir / "performance"
                target_perf_dir.mkdir(parents=True, exist_ok=True)

                # ===== PER-TARGET FILES =====

                # Target-specific summary statistics
                target_summary = {
                    "Target": target_tag,
                    "Task": task.upper(),
                    "N_Folds": len(cv_scores),
                    "Mean_Score": np.mean(cv_scores),
                    "Std_Score": np.std(cv_scores),
                    "Min_Score": np.min(cv_scores),
                    "Max_Score": np.max(cv_scores),
                    "Median_Score": np.median(cv_scores),
                    "Q1_Score": np.percentile(cv_scores, 25),
                    "Q3_Score": np.percentile(cv_scores, 75),
                    "Range_Score": np.max(cv_scores) - np.min(cv_scores),
                }

                # Save per-target summary
                target_summary_df = pd.DataFrame([target_summary])
                target_summary_df = target_summary_df.round(4)
                target_summary_filename = f"performance_summary_{target_tag}.csv"
                target_summary_path = target_perf_dir / target_summary_filename
                target_summary_df.to_csv(target_summary_path, index=False)

                # Target-specific individual fold scores
                target_fold_data = []
                for i, score in enumerate(cv_scores):
                    fold_row = {
                        "Target": target_tag,
                        "Task": task.upper(),
                        "Fold": i + 1,
                        "Score": round(score, 4),
                    }
                    target_fold_data.append(fold_row)

                target_folds_df = pd.DataFrame(target_fold_data)
                target_folds_filename = f"performance_individual_folds_{target_tag}.csv"
                target_folds_path = target_perf_dir / target_folds_filename
                target_folds_df.to_csv(target_folds_path, index=False)

                logger.info(
                    f"Created performance files for {target_tag} in {target_perf_dir}"
                )
                per_target_files_created.extend(
                    [str(target_summary_path), str(target_folds_path)]
                )

                # Collect data for aggregated files
                summary_data.append(target_summary)
                individual_fold_data.extend(target_fold_data)

            if not summary_data:
                logger.warning("No valid data for CSV generation")
                return

            # ===== AGGREGATED SUMMARY FILES =====

            # File 1: Performance Summary Statistics (all targets)
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values("Target")
            numeric_columns = summary_df.select_dtypes(include=[np.number]).columns
            summary_df[numeric_columns] = summary_df[numeric_columns].round(4)

            summary_filename = f"performance_summary_statistics_{task}_{timestamp}.csv"
            summary_path = summary_folder / summary_filename
            summary_df.to_csv(summary_path, index=False)
            logger.info(f"Aggregated performance summary saved: {summary_filename}")

            # File 2: Individual Fold Scores (all targets)
            aggregated_csv_files = [str(summary_path)]
            if individual_fold_data:
                folds_df = pd.DataFrame(individual_fold_data)
                folds_df = folds_df.sort_values(["Target", "Fold"])
                folds_df["Score"] = folds_df["Score"].round(4)

                folds_filename = f"performance_individual_folds_{task}_{timestamp}.csv"
                folds_path = summary_folder / folds_filename
                folds_df.to_csv(folds_path, index=False)
                logger.info(
                    f"Aggregated individual fold scores saved: {folds_filename}"
                )
                aggregated_csv_files.append(str(folds_path))

            # File 3: Overall Statistics (if multiple targets)
            if len(summary_data) > 1:
                overall_stats = {
                    "Metric": [
                        "Overall_Mean_Performance",
                        "Overall_Std_Performance",
                        "Best_Performing_Target",
                        "Best_Target_Score",
                        "Worst_Performing_Target",
                        "Worst_Target_Score",
                        "Total_Targets_Optimized",
                        "Task_Type",
                    ],
                    "Value": [
                        round(summary_df["Mean_Score"].mean(), 4),
                        round(summary_df["Mean_Score"].std(), 4),
                        summary_df.loc[summary_df["Mean_Score"].idxmax(), "Target"],
                        round(summary_df["Mean_Score"].max(), 4),
                        summary_df.loc[summary_df["Mean_Score"].idxmin(), "Target"],
                        round(summary_df["Mean_Score"].min(), 4),
                        len(summary_data),
                        task.upper(),
                    ],
                }
                overall_df = pd.DataFrame(overall_stats)

                overall_filename = (
                    f"performance_overall_statistics_{task}_{timestamp}.csv"
                )
                overall_path = summary_folder / overall_filename
                overall_df.to_csv(overall_path, index=False)
                logger.info(f"Overall statistics saved: {overall_filename}")
                aggregated_csv_files.append(str(overall_path))

                # File 4: Target Rankings by Performance
                ranking_df = summary_df[["Target", "Mean_Score", "Std_Score"]].copy()
                ranking_df = ranking_df.sort_values("Mean_Score", ascending=False)
                ranking_df["Rank"] = range(1, len(ranking_df) + 1)
                ranking_df = ranking_df[["Rank", "Target", "Mean_Score", "Std_Score"]]

                ranking_filename = f"performance_target_rankings_{task}_{timestamp}.csv"
                ranking_path = summary_folder / ranking_filename
                ranking_df.to_csv(ranking_path, index=False)
                logger.info(f"Target rankings saved: {ranking_filename}")
                aggregated_csv_files.append(str(ranking_path))

            # Log performance summary statistics
            mean_performance = summary_df["Mean_Score"].mean()
            std_performance = summary_df["Mean_Score"].std()
            best_target = summary_df.loc[summary_df["Mean_Score"].idxmax(), "Target"]
            best_score = summary_df["Mean_Score"].max()

            logger.info("Performance Summary Statistics:")
            logger.info(f"  Task: {task.upper()}")
            logger.info(f"  Targets optimized: {len(summary_data)}")
            logger.info(f"  Per-target files created: {len(per_target_files_created)}")
            logger.info(f"  Aggregated files created: {len(aggregated_csv_files)}")
            logger.info(f"  Overall mean performance: {mean_performance:.4f}")
            logger.info(f"  Overall std performance: {std_performance:.4f}")
            logger.info(f"  Best target: {best_target} (score: {best_score:.4f})")

            # Store summary in context for potential later use
            context["performance_summary"] = {
                "summary_dataframe": summary_df,
                "per_target_files_created": per_target_files_created,
                "aggregated_csv_files_created": aggregated_csv_files,
                "summary_csv_path": str(summary_path),
                "summary_folder_path": str(summary_folder),
                "overall_stats": {
                    "mean_performance": float(mean_performance),
                    "std_performance": float(std_performance),
                    "best_target": best_target,
                    "best_score": float(best_score),
                    "n_targets": len(summary_data),
                    "task": task,
                },
            }

        except Exception as e:
            logger.error(f"Error generating performance CSV files: {e}")


# TODO check if we still need this function or if we should put it somewhere else as a reference for unittest or something
def inspect_data_state(
    context,
    embeddings_labelled,
    train_labels,
    combined_input_matrix,
    full_embeddings,
    cluster_labels,
    scores_vectors_dict,
    classification,
    output_folder,
):
    """
    Inspects and reports on the state of data just before model training would begin.
    This function creates detailed reports about each data component to help understand
    what's available for model training and in what format.

    Parameters
    ----------
    context : dict
        The pipeline context containing all available data
    embeddings_labelled : np.ndarray
        The 2D embeddings for labeled data used for training
    train_labels : np.ndarray
        The target labels/scores corresponding to embeddings_labelled
    combined_input_matrix : np.ndarray
        The original high-dimensional input features
    full_embeddings : np.ndarray or None
        In label_dataset mode, the unlabelled embeddings used for UMAP training
    cluster_labels : np.ndarray or None
        The cluster assignments for data points    scores_vectors_dict : dict
        Dictionary mapping score tags to score vectors
    classification : bool
        Whether this is a classification or regression task
    output_folder : str or Path
        Directory where inspection results will be saved
    """
    logger = logging.getLogger(__name__)
    logger.info("Inspecting data state before model training")

    # Create output directory
    output_folder = Path(output_folder) / "data_inspection"
    output_folder.mkdir(parents=True, exist_ok=True)

    # Basic data summary
    data_summary = {
        "embeddings_labelled": get_array_info(embeddings_labelled),
        "train_labels": get_array_info(train_labels),
        "combined_input_matrix": get_array_info(combined_input_matrix),
        "full_embeddings": get_array_info(full_embeddings),
        "cluster_labels": get_array_info(cluster_labels),
        "classification": classification,
    }

    # Score vectors summary
    score_vectors_summary = {}
    for key, vec in scores_vectors_dict.items():
        score_vectors_summary[key] = {
            "shape": vec.shape,
            "dtype": str(vec.dtype),
            "min": float(np.min(vec)),
            "max": float(np.max(vec)),
            "mean": float(np.mean(vec)),
            "unique_values": int(len(np.unique(vec))),
        }
        if classification:
            # For classification, count classes
            unique, counts = np.unique(vec, return_counts=True)
            score_vectors_summary[key]["class_counts"] = {
                str(int(u)): int(c) for u, c in zip(unique, counts)
            }

    # Context keys summary
    context_keys = list(context.keys())
    context_key_types = {k: str(type(context[k])) for k in context_keys}

    # Save all info to JSON
    inspection_data = {
        "data_summary": data_summary,
        "score_vectors_summary": score_vectors_summary,
        "context_keys": context_keys,
        "context_key_types": context_key_types,
    }
    save_json(output_folder / "data_inspection.json", inspection_data)

    # Create some basic visualizations

    # 1. Scatter plot of embeddings (colored by cluster if available)
    if embeddings_labelled is not None and embeddings_labelled.shape[1] >= 2:
        plt.figure(figsize=(10, 8))
        if cluster_labels is not None:
            plt.scatter(
                embeddings_labelled[:, 0],
                embeddings_labelled[:, 1],
                c=cluster_labels,
                cmap="viridis",
                alpha=0.7,
            )
            plt.colorbar(label="Cluster")
        else:
            plt.scatter(embeddings_labelled[:, 0], embeddings_labelled[:, 1], alpha=0.7)
        plt.title("Labeled Embeddings")
        plt.xlabel("UMAP Dimension 1")
        plt.ylabel("UMAP Dimension 2")
        plt.tight_layout()
        plt.savefig(output_folder / "labeled_embeddings.png")
        plt.close()

    # 2. For each score in scores_vectors_dict, plot a heatmap on the embeddings
    for key, vec in scores_vectors_dict.items():
        if embeddings_labelled is not None and embeddings_labelled.shape[1] >= 2:
            plt.figure(figsize=(10, 8))
            scatter = plt.scatter(
                embeddings_labelled[:, 0],
                embeddings_labelled[:, 1],
                c=vec,
                cmap="coolwarm",
                alpha=0.7,
            )
            plt.colorbar(scatter, label=f"Score: {key}")
            plt.title(f"Embeddings colored by {key}")
            plt.xlabel("UMAP Dimension 1")
            plt.ylabel("UMAP Dimension 2")
            plt.tight_layout()
            plt.savefig(output_folder / f"embeddings_by_{key}.png")
            plt.close()

    # 3. If we have both full and labeled embeddings, plot to show their relationship
    if full_embeddings is not None and embeddings_labelled is not None:
        plt.figure(figsize=(10, 8))
        plt.scatter(
            full_embeddings[:, 0],
            full_embeddings[:, 1],
            color="lightgray",
            alpha=0.5,
            label="Unlabeled",
        )
        plt.scatter(
            embeddings_labelled[:, 0],
            embeddings_labelled[:, 1],
            color="red",
            alpha=0.7,
            label="Labeled",
        )
        plt.title("Full vs. Labeled Embeddings")
        plt.xlabel("UMAP Dimension 1")
        plt.ylabel("UMAP Dimension 2")
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_folder / "full_vs_labeled_embeddings.png")
        plt.close()

    # Output detailed statistics

    # Distances between points in embedding space
    if embeddings_labelled is not None and len(embeddings_labelled) > 1:
        from scipy.spatial.distance import pdist

        distances = pdist(embeddings_labelled)
        distance_stats = {
            "min": float(np.min(distances)),
            "max": float(np.max(distances)),
            "mean": float(np.mean(distances)),
            "median": float(np.median(distances)),
            "std": float(np.std(distances)),
        }
        save_json(output_folder / "embedding_distances.json", distance_stats)

    logger.info(f"Data inspection report saved to {output_folder}")
    return inspection_data


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
    # Get random seeds from context
    random_seeds = context.get("random_seeds", {})
    random_state = random_seeds.get(
        "prediction_seed", 42
    )  # Use prediction_seed or fall back to 42
    logger = logging.getLogger(__name__)
    logger.info("Running robust OOD evaluation")

    # Ensure output folder exists
    output_folder = Path(output_folder) / "ood_evaluation"
    output_folder.mkdir(parents=True, exist_ok=True)

    # Debug: print key context variables to help with debugging
    logger.info(f"Context keys: {list(context.keys())}")

    # Check if we're in digits_label_dataset mode by looking for 'labeled_indices' in context
    # or if we're processing the digits_label_dataset by checking the dataset_type
    is_digits_label_dataset = (
        "labeled_indices" in context or context.get("dataset_type") == "digits"
    )

    if is_digits_label_dataset:
        logger.info(
            "Detected digits_label_dataset mode - setting up true OOD evaluation"
        )
        # 1. Get the original data and indices of the 400 labeled samples
        all_features, all_labels, labeled_indices = load_and_preprocess_digits_dataset(
            "digits_label_dataset"
        )

        # 2. Create mask for the training set (everything except the 400 labeled samples)
        mask = np.ones(len(all_features), dtype=bool)
        mask[labeled_indices] = False

        # 3. Train a new UMAP model using only the unlabeled portion (~1397 samples)
        logger.info(
            f"Training new UMAP model on {np.sum(mask)} samples (excluding labeled subset)"
        )

        # Try different ways to get the original UMAP model parameters
        original_umap = None

        # Initialize model I/O manager for loading UMAP models
        umap_manager = ModelIOManager(Path(output_folder).parent)

        # Try to load UMAP model using the enhanced I/O system
        umap_artifact = umap_manager.load_model(
            model_name="best_umap_model",
            model_type="umap",
        )

        if umap_artifact:
            original_umap = umap_artifact.model
            logger.info(f"Loaded UMAP model from: {umap_artifact.filepath}")
            logger.debug(f"UMAP model metadata: {umap_artifact.metadata}")
        else:
            logger.warning("Failed to load UMAP model using model I/O system")

        if original_umap is None:
            # Only check for the new naming standard
            original_umap = context.get("embedding_train_umap_model")

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
            metric = "euclidean"

        #  This is completely incorrect, we NEVER train a new UMAP model on the labeled data, this is the whole point of the OOD evaluation....
        # Create and train the new UMAP model
        true_ood_umap = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            metric=metric,
            random_state=random_state,
        )
        unlabeled_embeddings = true_ood_umap.fit_transform(all_features[mask])

        # 4. Get the labeled data (400 samples) and transform through the new UMAP
        labeled_data = all_features[labeled_indices]
        labeled_scores = all_labels[labeled_indices]

        # Transform labeled data through the new UMAP model to get true OOD embeddings
        labeled_embeddings = true_ood_umap.transform(labeled_data)

        logger.info(
            f"Successfully created true OOD embeddings for {len(labeled_indices)} labeled samples"
        )

        # Save the new UMAP model and embeddings for reference
        ood_umap_manager = ModelIOManager(output_folder)
        ood_umap_manager.save_model(
            model=true_ood_umap,
            model_name="true_ood_umap_model",
            model_type="umap",
            description="UMAP model trained excluding labeled samples for true OOD evaluation",
            tags=["ood", "evaluation", "true_ood"],
        )
        np.save(output_folder / "unlabeled_embeddings.npy", unlabeled_embeddings)
        np.save(output_folder / "labeled_ood_embeddings.npy", labeled_embeddings)
    else:
        # For non-digits_label_dataset mode, use the standard approach
        logger.info(
            "Using standard evaluation approach (not digits_label_dataset mode)"
        )

        # Get required data from context - use only the new naming
        umap_model = context.get("embedding_train_umap_model")
        if umap_model is None:
            # Try loading from file if not in context using enhanced I/O system
            fallback_manager = ModelIOManager(Path(output_folder).parent)
            umap_artifact = fallback_manager.load_model(
                model_name="best_umap_model",
                model_type="umap",
            )
            if umap_artifact:
                umap_model = umap_artifact.model
                logger.info(f"Loaded UMAP model from file: {umap_artifact.filepath}")
            else:
                raise ValueError(
                    "embedding_train_umap_model is required for OOD evaluation - failed to load from file"
                )

        # Use only new naming convention
        labeled_data = context.get("prediction_train_features")
        labeled_scores = context.get("prediction_train_labels")

        if labeled_data is None or labeled_scores is None:
            raise ValueError(
                f"prediction_train_features and prediction_train_labels are required for OOD evaluation. Available keys: {list(context.keys())}"
            )

        # Project labeled data through the UMAP model to get embeddings
        labeled_embeddings = umap_model.transform(labeled_data)

        # Use already-computed embeddings if available
        precomputed_embeddings = context.get("prediction_train_coords")

        if precomputed_embeddings is not None:
            # Verify that our newly computed embeddings match the precomputed ones
            # Small differences are expected due to floating point, but large differences indicate a problem
            if len(precomputed_embeddings) == len(labeled_embeddings):
                embedding_diff = np.mean(
                    np.abs(labeled_embeddings - precomputed_embeddings)
                )
                logger.info(
                    f"Mean absolute difference between computed and precomputed embeddings: {embedding_diff}"
                )

                # Use precomputed for consistency with rest of pipeline
                labeled_embeddings = precomputed_embeddings
            else:
                logger.warning(
                    "Precomputed embeddings found but length doesn't match labeled data"
                )
    # Define CV strategy
    n_splits = 5
    cv_seed = random_seeds.get(
        "cv_seed", random_state
    )  # Use cv_seed from context or fall back to random_state
    cv = (
        StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=cv_seed)
        if classification
        else KFold(n_splits=n_splits, shuffle=True, random_state=cv_seed)
    )

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
            for fold, (train_idx, test_idx) in enumerate(
                cv.split(labeled_embeddings, binary_labels)
            ):
                X_train, X_test = (
                    labeled_embeddings[train_idx],
                    labeled_embeddings[test_idx],
                )
                y_train, y_test = binary_labels[train_idx], binary_labels[test_idx]
                # Inner CV to find best sigma
                best_sigma, best_score = None, -np.inf
                for sigma in np.logspace(-2, 0, 10):  # Try various sigma values
                    inner_cv = StratifiedKFold(
                        n_splits=3, shuffle=True, random_state=cv_seed
                    )
                    scores = []

                    for inner_train_idx, inner_val_idx in inner_cv.split(
                        X_train, y_train
                    ):
                        X_inner_train, X_inner_val = (
                            X_train[inner_train_idx],
                            X_train[inner_val_idx],
                        )
                        y_inner_train, y_inner_val = (
                            y_train[inner_train_idx],
                            y_train[inner_val_idx],
                        )

                        klr = KernelLogisticRegressor(
                            sigma=sigma
                        )  # Remove 'kernel' parameter
                        klr.fit(X_inner_train, y_inner_train)
                        y_inner_pred = klr.predict(X_inner_val)
                        scores.append(
                            balanced_accuracy_score(y_inner_val, y_inner_pred)
                        )

                    mean_score = np.mean(scores)
                    if mean_score > best_score:
                        best_score = mean_score
                        best_sigma = sigma

                # Train model on full training fold with best sigma
                klr = KernelLogisticRegressor(
                    sigma=best_sigma
                )  # Remove 'kernel' parameter

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
                fold_metrics.append(
                    {
                        "fold": fold,
                        "accuracy": acc,
                        "balanced_accuracy": bal_acc,
                        "best_sigma": best_sigma,
                    }
                )

                logger.info(
                    f"  Class {label} - Fold {fold}: Accuracy={acc:.4f}, Balanced Accuracy={bal_acc:.4f}"
                )

            # Calculate average metrics across folds
            avg_metrics = {
                "accuracy": np.mean([m["accuracy"] for m in fold_metrics]),
                "balanced_accuracy": np.mean(
                    [m["balanced_accuracy"] for m in fold_metrics]
                ),
                "fold_metrics": fold_metrics,
            }

            # Store results for this class
            results[f"class_{label}"] = avg_metrics

            logger.info(
                f"  Class {label} - Average: Accuracy={avg_metrics['accuracy']:.4f}, "
                f"Balanced Accuracy={avg_metrics['balanced_accuracy']:.4f}"
            )
        # Calculate overall multi-class accuracy

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
            probs = [
                (
                    all_predicted_probs[label][i]
                    if i < len(all_predicted_probs[label])
                    else 0
                )
                for label in unique_labels
            ]
            pred_multiclass[i] = unique_labels[np.argmax(probs)]

        overall_acc = accuracy_score(true_multiclass, pred_multiclass)
        overall_bal_acc = balanced_accuracy_score(true_multiclass, pred_multiclass)

        # Create a confusion matrix
        cm = confusion_matrix(true_multiclass, pred_multiclass, labels=all_classes)

        # Plot and save confusion matrix
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
        plt.title("OOD Confusion Matrix")
        plt.colorbar()
        tick_marks = np.arange(len(all_classes))
        plt.xticks(tick_marks, all_classes, rotation=45)
        plt.yticks(tick_marks, all_classes)

        # Add text annotations
        thresh = cm.max() / 2.0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(
                    j,
                    i,
                    format(cm[i, j], "d"),
                    ha="center",
                    va="center",
                    color="white" if cm[i, j] > thresh else "black",
                )

        plt.tight_layout()
        plt.ylabel("True label")
        plt.xlabel("Predicted label")
        plt.savefig(output_folder / "confusion_matrix.png")
        plt.close()

        # Store overall results
        results["overall"] = {
            "accuracy": overall_acc,
            "balanced_accuracy": overall_bal_acc,
            "confusion_matrix": cm.tolist(),
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
            y_train, y_test = labeled_scores[train_idx], labeled_scores[test_idx]

            # Inner CV to find best sigma
            best_sigma, best_score = None, -np.inf
            for sigma in np.logspace(-2, 0, 10):
                inner_cv = KFold(n_splits=3, shuffle=True, random_state=cv_seed)
                scores = []
                for inner_train_idx, inner_val_idx in inner_cv.split(X_train):
                    X_inner_train, X_inner_val = (
                        X_train[inner_train_idx],
                        X_train[inner_val_idx],
                    )
                    y_inner_train, y_inner_val = (
                        y_train[inner_train_idx],
                        y_train[inner_val_idx],
                    )

                    kr = KernelRegressor(kernel="rbf", sigma=sigma)
                    kr.fit(X_inner_train, y_inner_train)
                    y_inner_pred = kr.predict(X_inner_val)
                    scores.append(r2_score(y_inner_val, y_inner_pred))

                mean_score = np.mean(scores)
                if mean_score > best_score:
                    best_score = mean_score
                    best_sigma = sigma
            # Train model on full training fold with best sigma
            kr = KernelRegressor(kernel="rbf", sigma=best_sigma)
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
            fold_metrics.append(
                {"fold": fold, "r2_score": r2, "mse": mse, "best_sigma": best_sigma}
            )

            logger.info(f"  Fold {fold}: R² Score={r2:.4f}, MSE={mse:.4f}")

        # Calculate average metrics across folds
        avg_metrics = {
            "r2_score": np.mean([m["r2_score"] for m in fold_metrics]),
            "mse": np.mean([m["mse"] for m in fold_metrics]),
            "fold_metrics": fold_metrics,
        }

        # Store overall results
        results["overall"] = avg_metrics

        # Plot predicted vs true values
        plt.figure(figsize=(10, 8))
        plt.scatter(all_true, all_pred, alpha=0.5)
        plt.plot([min(all_true), max(all_true)], [min(all_true), max(all_true)], "r--")
        plt.title("OOD Predicted vs True Values")
        plt.xlabel("True Values")
        plt.ylabel("Predicted Values")
        plt.savefig(output_folder / "pred_vs_true.png")
        plt.close()

        logger.info(f"Overall R² Score: {avg_metrics['r2_score']:.4f}")
        logger.info(f"Overall MSE: {avg_metrics['mse']:.4f}")
    # Save results to file

    # Convert NumPy arrays to lists for JSON serialization
    for key in results:
        if isinstance(results[key], dict):
            for subkey in results[key]:
                if isinstance(results[key][subkey], np.ndarray):
                    results[key][subkey] = results[key][subkey].tolist()

    # save with save_json function
    save_json(output_folder / "ood_results.json", results)

    logger.info("OOD evaluation complete. Results saved to JSON file.")

    return {
        "ood_evaluation_results": results,
        "ood_evaluation_output_folder": str(output_folder),
    }
