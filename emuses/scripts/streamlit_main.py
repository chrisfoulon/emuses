# streamlit_app.py
import queue
import sys
import threading
import time

import plotly
import streamlit as st
import logging
import argparse
from pathlib import Path
import numpy as np

from matplotlib import pyplot as plt

# Import pipeline classes
from emuses.pipelines.emuses_pipeline import EMUSESPipeline
from emuses.pipelines.umap_stage import UMAPStage
from emuses.pipelines.clustering_stage import ClusteringStage
from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.pipelines.prediction_stage import PredictionStage


def main():
    st.title("EMUSES Pipeline Web Interface")

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Sidebar for configuration
    st.sidebar.header("Pipeline Configuration")
    command = st.sidebar.selectbox("Select Command", ["full", "umap", "clustering", "heatmap", "prediction"])

    # Common inputs
    output_folder = st.sidebar.text_input("Output Folder", value="output")

    # Initialize args namespace
    args = argparse.Namespace()
    args.command = command
    args.output_folder = output_folder

    # Collect inputs based on command
    if command in ["full", "heatmap", "umap", "prediction"]:
        input_dataset = st.sidebar.text_input("Input Dataset (path or 'mnist')")
        args.input_dataset = input_dataset

        recursive_input_file_search = st.sidebar.checkbox("Recursive Input File Search", value=False)
        args.recursive_input_file_search = recursive_input_file_search

        input_file_types = st.sidebar.text_input("Input File Types (comma-separated)", value="")
        args.input_file_types = input_file_types.split(",") if input_file_types else None

        arg_separator = st.sidebar.text_input("Argument Separator", value=",")
        args.arg_separator = arg_separator

        test_size = st.sidebar.slider("Test Size", min_value=0.0, max_value=1.0, value=0.2)
        args.test_size = test_size

        # UMAP options
        load_umap = st.sidebar.text_input("Load UMAP Model (optional)")
        args.load_umap = load_umap if load_umap else None

        load_embeddings = st.sidebar.text_input("Load Embeddings (optional)")
        args.load_embeddings = load_embeddings if load_embeddings else None

        prefix = st.sidebar.text_input("Prefix for Output Names", value="")
        args.prefix = prefix

    if command in ["full", "heatmap", "prediction"]:
        # Scores options
        scores = st.sidebar.text_input("Scores File (optional)")
        args.scores = scores if scores else None

        scores_header = st.sidebar.text_input("Scores Header (optional)")
        args.scores_header = scores_header if scores_header else None

        scores_index_column = st.sidebar.text_input("Scores Index Column (optional)")
        args.scores_index_column = scores_index_column if scores_index_column else None

        scores_are_columns = st.sidebar.checkbox("Scores are Columns", value=False)
        args.scores_are_columns = scores_are_columns

        scores_column = st.sidebar.text_input("Scores Column(s) (comma-separated)", value="")
        args.scores_column = scores_column.split(",") if scores_column else None

        classification = st.sidebar.checkbox("Classification Problem", value=False)
        args.classification = classification

    if command in ["full", "clustering", "heatmap"]:
        # Clustering options
        load_hdbscan = st.sidebar.text_input("Load HDBSCAN Model (optional)")
        args.load_hdbscan = load_hdbscan if load_hdbscan else None

        min_cluster_size = st.sidebar.number_input("Minimum Cluster Size", min_value=2, value=5)
        args.min_cluster_size = min_cluster_size

        interactive_plot = st.sidebar.checkbox("Interactive Plot", value=False)
        args.interactive_plot = interactive_plot

    if command in ["full", "heatmap"]:
        # Smoothing options
        smoothing_option = st.sidebar.radio("Smoothing Option", ["Default", "Sigma", "FWHM"])
        if smoothing_option == "Sigma":
            sigma = st.sidebar.number_input("Sigma Value", min_value=0.0, value=1.0)
            args.sigma = sigma
            args.fwhm = None
        elif smoothing_option == "FWHM":
            fwhm = st.sidebar.number_input("FWHM Value", min_value=0.0, value=1.0)
            args.fwhm = fwhm
            args.sigma = None
        else:
            args.sigma = None
            args.fwhm = None

    if command == "clustering":
        load_embeddings = st.sidebar.text_input("Load Embeddings")
        args.load_embeddings = load_embeddings if load_embeddings else None

    if command == "heatmap":
        embeddings = st.sidebar.text_input("Embeddings File")
        print(f'Is embeddings None? {embeddings is None}')
        args.embeddings = embeddings if embeddings else None

        output_format_info = st.sidebar.text_input("Output Format Info (optional)")
        args.output_format_info = output_format_info if output_format_info else None

        load_hdbscan = st.sidebar.text_input("Load HDBSCAN Model")
        args.load_hdbscan = load_hdbscan if load_hdbscan else None

    # Option to show plots
    show_plots = st.sidebar.checkbox("Display Plots", value=True)
    args.show_plots = True

    # Create a queue to communicate between the pipeline thread and the main thread
    if 'pipeline_queue' not in st.session_state:
        st.session_state.pipeline_queue = queue.Queue()
    pipeline_queue = st.session_state.pipeline_queue

    # Create placeholders for progress bars and messages
    stage_progress_bar = st.progress(0)
    stage_placeholder = st.empty()

    # Define the progress callback function
    def progress_callback(stage_name, progress):
        # Put a tuple into the queue
        pipeline_queue.put(('stage_progress', stage_name, progress))

    # Function to run the pipeline in a separate thread
    def run_pipeline():
        try:
            # Run the pipeline with the progress_callback and progress_queue
            pipeline.run(progress_callback=progress_callback, progress_queue=pipeline_queue)
            # After completion, put a success message in the queue
            pipeline_queue.put("Pipeline execution completed.")
        except Exception as e:
            # If there's an error, put the error message in the queue
            pipeline_queue.put(f"An error occurred: {e}")
            logger.exception("Exception during pipeline execution")

    # Run Pipeline Button
    if st.sidebar.button("Run Pipeline", key="run_pipeline"):
        try:
            # Create the output folder if it doesn't exist
            output_folder_path = Path(args.output_folder).resolve()
            output_folder_path.mkdir(parents=True, exist_ok=True)

            # Create the pipeline instance
            pipeline = EMUSESPipeline(args)

            # Determine which stages to add based on the command
            stages_to_add = []

            if command in ['umap', 'full', 'prediction']:
                stages_to_add.append(UMAPStage(pipeline.config))

            if command in ['clustering', 'full']:
                stages_to_add.append(ClusteringStage(pipeline.config))

            if command in ['heatmap', 'full']:
                if args.load_embeddings is not None:
                    pipeline.context['embeddings'] = np.load(args.load_embeddings)
                stages_to_add.append(HeatmapStage(
                    pipeline.config,
                    output_format_info=pipeline.context.get('output_format_info')
                ))

            if command in ['prediction', 'full']:
                stages_to_add.append(PredictionStage(pipeline.config))

            # Add the stages to the pipeline
            for stage in stages_to_add:
                pipeline.add_stage(stage)

            # Start the pipeline thread
            pipeline_thread = threading.Thread(target=run_pipeline)
            pipeline_thread.start()

            # Create placeholders for status and results
            status_placeholder = st.empty()

            # Create placeholders for progress bars and messages
            status_placeholder = st.empty()
            stage_progress_bar = st.progress(0)
            stage_placeholder = st.empty()

            # Create a placeholder for displaying plots in real-time
            plot_placeholder = st.empty()

            # While the pipeline is running, check the queue for messages
            while pipeline_thread.is_alive():
                time.sleep(0.1)  # Avoid busy waiting
                try:
                    while True:
                        # Retrieve message from the pipeline queue
                        message = pipeline_queue.get_nowait()

                        if isinstance(message, tuple):
                            # Handle plot messages
                            if message[0] == 'plot':
                                plot_title, plot_obj = message[1], message[2]
                                with plot_placeholder.container():
                                    st.subheader(plot_title)
                                    st.plotly_chart(plot_obj)  # Display the new plot immediately

                            # Handle stage progress messages
                            elif message[0] == 'stage_progress':
                                stage_name, progress = message[1], message[2]
                                stage_placeholder.text(f"Running stage: {stage_name}")
                                stage_progress_bar.progress(int(progress * 100))

                        elif "Pipeline execution completed." in message:
                            status_placeholder.success(message)
                            break  # Exit loop after pipeline completion

                        elif "An error occurred" in message:
                            status_placeholder.error(message)
                            break

                        else:
                            status_placeholder.info(message)

                except queue.Empty:
                    pass  # Continue loop if no message is available in the queue

            # After the pipeline finishes, complete the progress bar and status
            stage_progress_bar.progress(100)
            stage_placeholder.text("Pipeline execution completed.")

            # After the pipeline finishes

            # Retrieve and display the clustering plot
            clustering_plot = pipeline.context.get('clustering_plot', None)
            if clustering_plot:
                st.subheader("Clustering Plot:")
                st.plotly_chart(clustering_plot)

            try:
                message = pipeline_queue.get_nowait()
                status_placeholder.info(message)
            except queue.Empty:
                pass

            # Retrieve and display plots
            heatmap_plots = pipeline.context.get('heatmap_plots', {})

            if heatmap_plots:
                # Create tabs for each score_tag
                score_tags = list(heatmap_plots.keys())
                tabs = st.tabs(score_tags)

                for tab, score_tag in zip(tabs, score_tags):
                    with tab:
                        st.header(f"Results for Score {score_tag}")
                        # Get the plots dictionary for this score_tag
                        score_tag_plots = heatmap_plots[score_tag]
                        # Display clustering plot
                        clustering_plot = score_tag_plots.get('clustering_plot', None)
                        print(f'Is clustering plot None? {clustering_plot is None}')
                        if clustering_plot:
                            st.subheader("Clustering Plot:")
                            st.pyplot(clustering_plot)
                        else:
                            st.write("No clustering plot available.")

                        # Display representative data per cluster
                        clusters_labels = [clu for clu in score_tag_plots if clu != 'clustering_plot']
                        if clusters_labels:
                            cluster_tabs = st.tabs([f"Cluster {cluster}" for cluster in clusters_labels])
                            for cluster_tab, cluster in zip(cluster_tabs, clusters_labels):
                                with cluster_tab:
                                    st.subheader(f"Data for Cluster {cluster}")
                                    cluster_data = score_tag_plots[cluster]
                                    # Display cluster data as needed
                                    st.write("Representative Cluster:")
                                    if isinstance(cluster_data, plt.Figure):
                                        st.pyplot(cluster_data)
                                    elif isinstance(cluster_data, plotly.graph_objects.Figure):
                                        st.plotly_chart(cluster_data)
                                    else:
                                        st.write("No plot available for this cluster.")
                        else:
                            st.write("No representative cluster data available.")
            else:
                st.write("No heatmap plots available.")

            # Display interactive Plotly plots if available
            interactive_plot = pipeline.context.get('interactive_plot', None)
            if interactive_plot:
                st.plotly_chart(interactive_plot, use_container_width=True)

        except Exception as e:
            st.error(f"An error occurred: {e}")
            logger.exception("Exception during pipeline setup")

    # Exit logic (this needs to be outside the pipeline execution loop to avoid interference)
    if "confirm_exit" not in st.session_state:
        st.session_state.confirm_exit = False

    if not st.session_state.confirm_exit:
        if st.sidebar.button("Exit App", key="exit_button"):
            st.warning("Are you sure you want to exit? Click 'Confirm Exit' to proceed.")
            st.session_state.confirm_exit = True
    else:
        if st.sidebar.button("Confirm Exit", key="confirm_exit_button"):
            st.write("Exiting the app...")
            sys.exit()
        elif st.sidebar.button("Cancel", key="cancel_exit_button"):
            st.session_state.confirm_exit = False
            st.write("Exit canceled.")


if __name__ == '__main__':
    main()