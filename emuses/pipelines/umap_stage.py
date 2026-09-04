import json
import logging
from pathlib import Path

import hdbscan
import numpy as np

# Import the default optimization dictionary from your configuration module.
from emuses.config.optim_configs import load_optim_dict, optim_dict_default
from emuses.observability import (get_logger, track_optimization_trial,
                                  track_scientific_operation)
from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.clustering_utils import load_hdbscan_model
from emuses.tools.emuses_utils import rescale_embedding
from emuses.tools.UMAP_utils import (
    load_umap_model, train_and_save_umap_optim_with_nested_clustering)


def _as_jobs(value, default=1):
    """Coerce a jobs setting to an int, tolerating what actually arrives.

    ``None`` still reaches here from arg objects built before ``PipelineConfig``
    declared an explicit default, and a ``Mock`` config fabricates the attribute
    as a Mock -- the same trap that hid the broken parallelism detector and broke
    the seed wiring in ``heatmap_stage._seeds_from``. Hence ``isinstance``, not
    truthiness.
    """
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        return default
    return int(value)


def _resolve_search_jobs(cfg, logger):
    """Decide how many Optuna trials run concurrently -- in exactly one place.

    Serial is the default (ADR 2.9c). ``optuna.study.optimize(n_jobs>1)`` runs
    trials concurrently, so TPE's suggestion depends on which trials have
    finished when each one asks: thread timing, which ``--random_state`` does not
    control. Measured 2026-08-23 at 10 of 20 metrics identical against 20 of 20
    serial (``dev-docs/issues/reproducibility_tolerances_2026_08.md``).

    Parallel search stays available. It warns rather than being overridden,
    because forfeiting reproducibility is the caller's decision to make.
    """
    umap_jobs = _as_jobs(getattr(cfg, "umap_jobs", 1))
    hdbscan_jobs = _as_jobs(getattr(cfg, "hdbscan_jobs", 1))

    if umap_jobs != 1:
        logger.warning(
            "umap_jobs=%s runs the UMAP/HDBSCAN search in parallel, which is NOT "
            "reproducible: optuna schedules trials concurrently, so the search "
            "path depends on thread timing and random_state cannot fix it. "
            "Use umap_jobs=1 for a run you intend to publish. See "
            "dev-docs/issues/reproducibility_tolerances_2026_08.md",
            umap_jobs,
        )
    if hdbscan_jobs != 1:
        logger.warning(
            "hdbscan_jobs=%s has no effect: the inner HDBSCAN search always runs "
            "serially under the current parallel_mode ('umap'). The option is "
            "kept declared, not wired.",
            hdbscan_jobs,
        )
    return umap_jobs, hdbscan_jobs


class UMAPStage(PipelineStage):
    def __init__(self, config):
        super().__init__(config)
        self.trained_umap = None
        self.embeddings = None
        self.test_embeddings = None
        self.umap_model_path = None
        self.embeddings_path = None
        self.test_embeddings_path = None
        self.min_embeddings = None
        self.max_embeddings = None
        # Clustering-related attributes:
        self.best_clusterer = None
        self.cluster_labels = None
        self.cluster_model_path = None
        self.cluster_labels_path = None

    def run(self, context, progress_queue=None):
        logger = get_logger(__name__)

        # Get user context for observability
        user_id = context.get("user_id")
        dataset_name = context.get("dataset_name", "unknown")

        with track_scientific_operation(
            "umap_optimization",
            user_id=user_id,
            additional_attributes={"dataset": dataset_name},
        ) as obs_ctx:
            logger.info("Running UMAP Stage", user_id=user_id, dataset=dataset_name)

            # Get component-specific seeds from context
            random_seeds = context.get("random_seeds", {})
            umap_seed = random_seeds.get("umap_seed", 42)
            clustering_seed = random_seeds.get("clustering_seed", 42)
            logger.info(
                f"Using random seeds - UMAP: {umap_seed}, Clustering: {clustering_seed}"
            )

            # Add optimization context to observability
            obs_ctx.set_attribute("umap_seed", umap_seed)
            obs_ctx.set_attribute("clustering_seed", clustering_seed)

            # Use new naming convention only
            train_features = context.get("embedding_train_features")
            test_features = context.get("embedding_test_features")
            # train_indices = context.get("embedding_train_indices")  # Unused variable

            if train_features is not None:
                obs_ctx.set_attribute("train_samples", len(train_features))
            if test_features is not None:
                obs_ctx.set_attribute("test_samples", len(test_features))

        # Determine file paths based on output folder and prefix
        prefix = self.config.prefix if hasattr(self.config, "prefix") else ""
        umap_model_file = self.config.output_folder / f"{prefix}best_umap_model.joblib"
        embeddings_file = self.config.output_folder / f"{prefix}embeddings.npy"
        cluster_model_file = self.config.output_folder / f"{prefix}hdbscan_model.joblib"
        cluster_labels_file = self.config.output_folder / f"{prefix}cluster_labels.npy"

        # An explicitly supplied morphospace wins over both the output-folder
        # detection below and training. --load_umap was declared in
        # cli/pipeline_options.py, stored on PipelineConfig, plumbed through
        # pipeline_runner and named by heatmap_stage.py's error message as the
        # way to reuse a trained morphospace -- but nothing ever read it, so it
        # silently retrained instead. Its three siblings (load_clusterer,
        # load_cluster_labels, load_embeddings) are read further down.
        explicit_umap = getattr(self.config, "load_umap", None)
        if explicit_umap:
            explicit_umap_path = Path(explicit_umap).resolve()
            if not explicit_umap_path.exists():
                raise FileNotFoundError(
                    f"--load_umap points at a file that does not exist: "
                    f"{explicit_umap_path}. Not falling back to training: reusing a "
                    f"specific morphospace and building a new one are different "
                    f"experiments, and silently doing the second is how a run looks "
                    f"successful while answering a different question."
                )
            logger.info(f"Loading pre-trained UMAP model from --load_umap: {explicit_umap_path}")
            self.trained_umap, _ = load_umap_model(explicit_umap_path)
            self.umap_model_path = explicit_umap_path
            # `emuses umap` writes the clusterer beside the UMAP model, so take
            # the sibling unless --load_clusterer overrides it below.
            self.best_clusterer, _ = load_hdbscan_model(
                explicit_umap_path.parent, model_name="hdbscan_model"
            )
            self.cluster_model_path = explicit_umap_path.parent / "hdbscan_model.joblib"
            # Labels are deliberately left unset. The saved cluster_labels.npy
            # describes the subjects the morphospace was BUILT on; this run may
            # have a different cohort, and pairing n_old labels with n_new
            # coordinates is a silent wrong answer. They are assigned from the
            # loaded clusterer once the current subjects' coordinates exist.
            self.cluster_labels = None

        # If output files exist, load them and skip training.
        elif (
            umap_model_file.exists()
            and embeddings_file.exists()
            and cluster_model_file.exists()
            and cluster_labels_file.exists()
        ):
            logger.info(
                f"Found existing output files. Loading UMAP model from: {umap_model_file}"
            )
            self.trained_umap, _ = load_umap_model(umap_model_file)
            self.embeddings = np.load(embeddings_file)
            self.best_clusterer, _ = load_hdbscan_model(
                cluster_model_file.parent, model_name="hdbscan_model"
            )
            self.cluster_labels = np.load(cluster_labels_file)
        else:
            # Load or generate the optimization dictionary.
            if "optim_dict" in context and context["optim_dict"]:
                optim_dict = context["optim_dict"]
            elif "cli_args" in context and "optim_dict" in context["cli_args"]:
                optim_dict_name = context["cli_args"]["optim_dict"]
                try:
                    optim_dict = load_optim_dict(optim_dict_name)
                except Exception as e:
                    logger.error(
                        f"Error loading optim_dict '{optim_dict_name}': {e}. Falling back to default."
                    )
                    optim_dict = optim_dict_default
            else:
                optim_dict = optim_dict_default  # Run nested optimization for UMAP + HDBSCAN.            # Get HDBSCAN reproducibility parameters from config
            approx_min_span_tree = getattr(
                self.config, "hdbscan_approx_min_span_tree", True
            )
            core_dist_n_jobs = getattr(self.config, "hdbscan_core_dist_n_jobs", -1)

            umap_jobs, hdbscan_jobs = _resolve_search_jobs(self.config, logger)

            (
                self.trained_umap,
                embeddings,
                umap_path,
                embeddings_path,
                best_clusterer,
                best_labels,
                cluster_model_path,
                cluster_labels_path,
                input_matrix_path,
            ) = train_and_save_umap_optim_with_nested_clustering(
                input_matrix=train_features,
                output_folder=self.config.output_folder,
                optim_dict=optim_dict,
                n_trials=getattr(self.config, "umap_trials", 50),
                n_inner_trials=getattr(self.config, "hdbscan_trials", 20),
                pref=self.config.prefix,
                n_jobs=umap_jobs,
                inner_n_jobs=hdbscan_jobs,
                random_state=umap_seed,
                clusterer_random_state=clustering_seed,
                approx_min_span_tree=approx_min_span_tree,
                core_dist_n_jobs=core_dist_n_jobs,
            )
            self.embeddings = embeddings
            logger.info(
                f"UMAP model saved at: {umap_path} and embeddings saved at: {embeddings_path}"
            )

            self.umap_model_path = umap_path
            self.embeddings_path = embeddings_path
            self.best_clusterer = best_clusterer
            self.cluster_labels = best_labels
            self.cluster_model_path = cluster_model_path
            self.cluster_labels_path = cluster_labels_path

            logger.info(f"UMAP model saved at: {umap_path}")
            logger.info(f"Embeddings saved at: {embeddings_path}")
            logger.info(f"HDBSCAN model saved at: {cluster_model_path}")
            logger.info(f"Cluster labels saved at: {cluster_labels_path}")

        # Check if a pre-saved clustering result should be loaded.
        if getattr(self.config, "load_clusterer", None):
            self.cluster_model_path = Path(self.config.load_clusterer).resolve()
            try:
                self.best_clusterer, _ = load_hdbscan_model(
                    self.cluster_model_path.parent, model_name="hdbscan_model"
                )
                logger.info(
                    f"Loaded pre-trained clusterer from: {self.cluster_model_path}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load clusterer from {self.cluster_model_path}: {e}"
                )
        if getattr(self.config, "load_cluster_labels", None):
            self.cluster_labels_path = Path(self.config.load_cluster_labels).resolve()
            try:
                self.cluster_labels = np.load(self.cluster_labels_path)
                logger.info(
                    f"Loaded pre-trained cluster labels from: {self.cluster_labels_path}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load cluster labels from {self.cluster_labels_path}: {e}"
                )

        # Load precomputed embeddings if provided.
        if getattr(self.config, "load_embeddings", None):
            self.embeddings = np.load(self.config.load_embeddings)
            logger.info(
                f"Loaded precomputed embeddings from: {self.config.load_embeddings}"
            )
        else:
            self.embeddings = self.trained_umap.transform(train_features)

        # Assign the CURRENT subjects to the loaded clusters.
        #
        # Coordinates above are always re-derived for whoever is in this run, but
        # cluster labels were not: on the reuse paths they came from the file the
        # morphospace was built with. When the cohort differs, that pairs n_old
        # labels with n_new coordinates.
        #
        # Length is the only signal available here, so this closes the case where
        # the cohorts differ in size. Two cohorts of EQUAL size still slip
        # through, because nothing in the context carries subject identity -- the
        # audit had to fingerprint subjects by disconnection load to recover their
        # order. Fixing that properly needs identity in the saved artefacts.
        needs_assignment = (
            self.cluster_labels is None
            or len(self.cluster_labels) != len(self.embeddings)
        )
        if needs_assignment and self.best_clusterer is not None:
            n_labels = None if self.cluster_labels is None else len(self.cluster_labels)
            logger.info(
                f"Assigning cluster labels for the current {len(self.embeddings)} subjects "
                f"from the loaded clusterer (had {n_labels} stored labels)."
            )
            try:
                self.cluster_labels, _ = hdbscan.approximate_predict(
                    self.best_clusterer, self.embeddings
                )
            except AttributeError as e:
                raise RuntimeError(
                    f"The loaded HDBSCAN model cannot label new subjects: {e}. It was "
                    f"fitted without prediction_data=True, so approximate_predict is "
                    f"unavailable. Refit the morphospace, or run without reusing a "
                    f"clusterer. Not falling back to the stored labels: they describe "
                    f"the subjects the morphospace was built on, not this run's."
                ) from e
        elif needs_assignment:
            raise RuntimeError(
                f"Cluster labels are unavailable or do not match this run's "
                f"{len(self.embeddings)} subjects, and no clusterer is loaded to derive "
                f"them from. Pass --load_clusterer alongside --load_umap, or let the "
                f"stage train."
            )

        # Rescale embeddings.
        self.min_embeddings = self.embeddings.min(axis=0)
        self.max_embeddings = self.embeddings.max(axis=0)

        # Save embedding scaling parameters for inference
        embedding_scaling = {
            'min_embeddings': self.min_embeddings.tolist(),
            'max_embeddings': self.max_embeddings.tolist()
        }
        scaling_file = self.config.output_folder / "embedding_scaling.json"
        with open(scaling_file, 'w') as f:
            json.dump(embedding_scaling, f)
        logger.info(f"Saved embedding scaling parameters to {scaling_file}")

        self.embeddings = rescale_embedding(
            self.embeddings,
            preset_min=self.min_embeddings,
            preset_max=self.max_embeddings,
        )

        # Process test embeddings if a test set exists.
        if test_features is not None:
            self.test_embeddings = self.trained_umap.transform(test_features)
            self.test_embeddings = rescale_embedding(
                self.test_embeddings,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            # Save test embeddings.
            self.test_embeddings_path = (
                self.config.output_folder / "test_embeddings.npy"
            )
            np.save(self.test_embeddings_path, self.test_embeddings)
            logger.info(f"Test embeddings saved at: {self.test_embeddings_path}")

        # Process labeled data for prediction if available
        prediction_train_features = context.get("prediction_train_features")
        prediction_test_features = context.get("prediction_test_features")

        # Transform prediction data through UMAP
        if prediction_train_features is not None:
            prediction_train_coords = self.trained_umap.transform(
                prediction_train_features
            )
            prediction_train_coords = rescale_embedding(
                prediction_train_coords,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            logger.info(
                "Transformed and rescaled prediction training data using the UMAP model."
            )
            context["prediction_train_coords"] = prediction_train_coords

        if prediction_test_features is not None:
            prediction_test_coords = self.trained_umap.transform(
                prediction_test_features
            )
            prediction_test_coords = rescale_embedding(
                prediction_test_coords,
                preset_min=self.min_embeddings,
                preset_max=self.max_embeddings,
            )
            logger.info(
                "Transformed and rescaled prediction test data using the UMAP model."
            )
            context["prediction_test_coords"] = prediction_test_coords

        # Update context with UMAP and clustering outputs using new naming convention
        context.update(
            {
                # Standardized naming for embedding data
                "embedding_train_coords": self.embeddings,
                "embedding_test_coords": self.test_embeddings,
                "embedding_train_umap_model": self.trained_umap,
                # Standardized naming for clustering data
                "embedding_train_clusterer": self.best_clusterer,
                "embedding_train_cluster_labels": self.cluster_labels,
                # Standardized naming for scaling information
                "embedding_train_min_coords": self.min_embeddings,
                "embedding_train_max_coords": self.max_embeddings,
                # File paths - keep naming as is since these are implementation details
                "cluster_model_path": self.cluster_model_path,
                "cluster_labels_path": self.cluster_labels_path,
            }
        )
