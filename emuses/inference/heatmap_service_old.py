# emuses/inference/heatmap_service.py
"""
Heatmap Service Layer for EMUSES Inference API

This module provides heatmap generation capabilities including:
- Prediction heatmaps for embeddings
- Feature importance visualization
- Uncertainty heatmaps
- Integration with existing EMUSES components
- Multiple output formats (array, image, both)
"""

import numpy as np
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import time
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import io

# Import EMUSES components
from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.inference.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class HeatmapService:
    """
    Service for generating prediction heatmaps using EMUSES models.
    
    Integrates with the existing HeatmapStage and PredictionService to provide
    comprehensive heatmap generation capabilities.
    """
    
    def __init__(self, models_base_path: Union[str, Path], prediction_service: Optional[PredictionService] = None):
        """
        Initialize the heatmap service.
        
        Args:
            models_base_path: Base path where models are stored
            prediction_service: Optional prediction service (creates new if None)
        """
        self.models_base_path = Path(models_base_path)
        self.prediction_service = prediction_service or PredictionService(models_base_path)
        
    def generate_heatmap(
        self, 
        request: HeatmapRequest,
        output_folder: Optional[str] = None
    ) -> HeatmapResponse:
        """
        Generate a prediction heatmap for the given embeddings.
        
        Args:
            request: Heatmap generation request
            output_folder: Override default models path
            
        Returns:
            HeatmapResponse with generated heatmap data
        """
        start_time = time.time()
        
        try:
            # Validate request
            errors = self._validate_request(request)
            if errors:
                raise ValueError(f"Invalid request: {'; '.join(errors)}")
            
            # Create grid for heatmap
            grid_coords, x_range, y_range = self._create_grid(request.embeddings, request.grid_size)
            
            # Get predictions for grid points
            pred_request = PredictionRequest(
                data=grid_coords,
                target_tag=request.target_tag,
                use_ensemble=(request.prediction_method == "ensemble"),
                return_uncertainty=True
            )
            
            pred_response = self.prediction_service.predict_batch(pred_request, output_folder)
            
            if pred_response.metadata and "error" in pred_response.metadata:
                raise ValueError(f"Prediction failed: {pred_response.metadata['error']}")
            
            # Reshape predictions to grid
            heatmap_array = pred_response.predictions.reshape(request.grid_size, request.grid_size)
            
            # Generate visualization if requested
            heatmap_image = None
            save_path = None
            
            if request.output_format in ["image", "both"]:
                heatmap_image, save_path = self._generate_image(
                    heatmap_array, 
                    x_range, 
                    y_range,
                    request
                )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Prepare metadata
            metadata = None
            if request.return_metadata:
                metadata = {
                    "grid_size": request.grid_size,
                    "prediction_method": request.prediction_method,
                    "target_tag": request.target_tag,
                    "prediction_range": (float(np.min(pred_response.predictions)), 
                                       float(np.max(pred_response.predictions))),
                    "model_versions": pred_response.model_versions,
                    "ensemble_confidence": pred_response.ensemble_confidence,
                    "num_models": len(pred_response.model_versions) if pred_response.model_versions else 0,
                    "embeddings_shape": request.embeddings.shape,
                    "x_range": x_range,
                    "y_range": y_range,
                }
            
            return HeatmapResponse(
                heatmap_array=heatmap_array if request.output_format in ["array", "both"] else None,
                heatmap_image=heatmap_image,
                grid_coordinates=grid_coords.reshape(request.grid_size, request.grid_size, 2),
                prediction_range=(float(np.min(pred_response.predictions)), 
                                float(np.max(pred_response.predictions))),
                processing_time_ms=processing_time,
                metadata=metadata,
                save_path=save_path
            )
            
        except Exception as e:
            logger.error(f"Heatmap generation failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return HeatmapResponse(
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )
    
    def generate_feature_importance_heatmap(
        self,
        features: np.ndarray,
        target_tag: str,
        feature_names: Optional[List[str]] = None,
        output_folder: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> HeatmapResponse:
        """
        Generate a feature importance heatmap.
        
        Args:
            features: Feature matrix (n_samples, n_features)
            target_tag: Target variable tag
            feature_names: Optional feature names for labeling
            output_folder: Override default models path
            save_path: Path to save the heatmap image
            
        Returns:
            HeatmapResponse with feature importance heatmap
        """
        start_time = time.time()
        
        try:
            # Load models to get feature importance
            models = self.prediction_service._load_models(
                str(output_folder or self.models_base_path), 
                target_tag
            )
            
            if not models:
                raise ValueError(f"No models found for target {target_tag}")
            
            # Collect feature importances from models that support it
            importances = []
            model_names = []
            
            for model_data in models:
                model = model_data["artifact"].model
                if hasattr(model, "feature_importances_"):
                    importances.append(model.feature_importances_)
                    model_names.append(f"fold_{model_data['fold_index']}")
                elif hasattr(model, "coef_"):
                    # For linear models, use absolute coefficients
                    coef = model.coef_
                    if len(coef.shape) > 1:
                        coef = np.mean(np.abs(coef), axis=0)
                    else:
                        coef = np.abs(coef)
                    importances.append(coef)
                    model_names.append(f"fold_{model_data['fold_index']}")
            
            if not importances:
                raise ValueError("No models with feature importance information found")
            
            # Average importances across models
            importance_matrix = np.array(importances)
            mean_importance = np.mean(importance_matrix, axis=0)
            std_importance = np.std(importance_matrix, axis=0)
            
            # Create feature names if not provided
            if feature_names is None:
                feature_names = [f"Feature_{i}" for i in range(len(mean_importance))]
            
            # Create heatmap visualization
            plt.figure(figsize=(12, 8))
            
            # Create a matrix for visualization (features x models)
            heatmap_data = importance_matrix.T  # Transpose for better visualization
            
            # Create heatmap
            sns.heatmap(
                heatmap_data,
                xticklabels=model_names,
                yticklabels=feature_names,
                annot=False,
                cmap="viridis",
                cbar_kws={"label": "Feature Importance"}
            )
            
            plt.title(f"Feature Importance Heatmap - {target_tag}")
            plt.xlabel("Model Folds")
            plt.ylabel("Features")
            plt.tight_layout()
            
            # Save image if path provided
            heatmap_image = None
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                with open(save_path, 'rb') as f:
                    heatmap_image = f.read()
            
            # Convert to bytes for response
            if heatmap_image is None:
                import io
                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                buf.seek(0)
                heatmap_image = buf.read()
                buf.close()
            
            plt.close()
            
            processing_time = (time.time() - start_time) * 1000
            
            return HeatmapResponse(
                heatmap_array=heatmap_data,
                heatmap_image=heatmap_image,
                processing_time_ms=processing_time,
                save_path=save_path,
                metadata={
                    "type": "feature_importance",
                    "target_tag": target_tag,
                    "num_features": len(mean_importance),
                    "num_models": len(importances),
                    "mean_importance": mean_importance.tolist(),
                    "std_importance": std_importance.tolist(),
                    "feature_names": feature_names,
                    "model_names": model_names,
                }
            )
            
        except Exception as e:
            logger.error(f"Feature importance heatmap generation failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return HeatmapResponse(
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )
    
    def generate_uncertainty_heatmap(
        self,
        request: HeatmapRequest,
        output_folder: Optional[str] = None
    ) -> HeatmapResponse:
        """
        Generate an uncertainty heatmap showing prediction uncertainty across the embedding space.
        
        Args:
            request: Heatmap generation request
            output_folder: Override default models path
            
        Returns:
            HeatmapResponse with uncertainty heatmap
        """
        start_time = time.time()
        
        try:
            # Force ensemble prediction for uncertainty calculation
            request.prediction_method = "ensemble"
            
            # Validate request
            errors = self._validate_request(request)
            if errors:
                raise ValueError(f"Invalid request: {'; '.join(errors)}")
            
            # Create grid for heatmap
            grid_coords, x_range, y_range = self._create_grid(request.embeddings, request.grid_size)
            
            # Get predictions with uncertainty for grid points
            pred_request = PredictionRequest(
                data=grid_coords,
                target_tag=request.target_tag,
                use_ensemble=True,
                return_uncertainty=True
            )
            
            pred_response = self.prediction_service.predict_batch(pred_request, output_folder)
            
            if pred_response.metadata and "error" in pred_response.metadata:
                raise ValueError(f"Prediction failed: {pred_response.metadata['error']}")
            
            if pred_response.uncertainty is None:
                raise ValueError("Uncertainty information not available")
            
            # Reshape uncertainty to grid
            uncertainty_array = pred_response.uncertainty.reshape(request.grid_size, request.grid_size)
            
            # Generate visualization
            heatmap_image = None
            save_path = None
            
            if request.output_format in ["image", "both"]:
                # Create custom request for uncertainty visualization
                uncertainty_request = HeatmapRequest(
                    embeddings=request.embeddings,
                    target_tag=request.target_tag,
                    grid_size=request.grid_size,
                    colormap="plasma",  # Good colormap for uncertainty
                    title=f"Prediction Uncertainty - {request.target_tag}",
                    save_path=request.save_path
                )
                
                heatmap_image, save_path = self._generate_image(
                    uncertainty_array,
                    x_range,
                    y_range,
                    uncertainty_request,
                    value_label="Uncertainty"
                )
            
            processing_time = (time.time() - start_time) * 1000
            
            return HeatmapResponse(
                heatmap_array=uncertainty_array if request.output_format in ["array", "both"] else None,
                heatmap_image=heatmap_image,
                grid_coordinates=grid_coords.reshape(request.grid_size, request.grid_size, 2),
                prediction_range=(float(np.min(pred_response.uncertainty)), 
                                float(np.max(pred_response.uncertainty))),
                processing_time_ms=processing_time,
                metadata={
                    "type": "uncertainty",
                    "grid_size": request.grid_size,
                    "target_tag": request.target_tag,
                    "uncertainty_range": (float(np.min(pred_response.uncertainty)), 
                                        float(np.max(pred_response.uncertainty))),
                    "model_versions": pred_response.model_versions,
                    "ensemble_confidence": pred_response.ensemble_confidence,
                    "embeddings_shape": request.embeddings.shape,
                },
                save_path=save_path
            )
            
        except Exception as e:
            logger.error(f"Uncertainty heatmap generation failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return HeatmapResponse(
                processing_time_ms=processing_time,
                metadata={"error": str(e)}
            )
    
    def _validate_request(self, request: HeatmapRequest) -> List[str]:
        """Validate heatmap request parameters."""
        errors = []
        
        # Check embeddings
        if request.embeddings is None:
            errors.append("Embeddings are required")
        else:
            if len(request.embeddings.shape) != 2:
                errors.append("Embeddings must be a 2D array")
            elif request.embeddings.shape[1] < 2:
                errors.append("Embeddings must have at least 2 dimensions")
            elif request.embeddings.shape[0] < 3:
                errors.append("Need at least 3 embedding points to create grid")
        
        # Check grid size
        if request.grid_size < 10 or request.grid_size > 1000:
            errors.append("Grid size must be between 10 and 1000")
        
        # Check target tag
        if not request.target_tag or not isinstance(request.target_tag, str):
            errors.append("Target tag must be a non-empty string")
        
        # Check prediction method
        if request.prediction_method not in ["ensemble", "single", "best"]:
            errors.append("Prediction method must be 'ensemble', 'single', or 'best'")
        
        # Check output format
        if request.output_format not in ["array", "image", "both"]:
            errors.append("Output format must be 'array', 'image', or 'both'")
        
        return errors
    
    def _create_grid(self, embeddings: np.ndarray, grid_size: int) -> Tuple[np.ndarray, Tuple[float, float], Tuple[float, float]]:
        """Create a regular grid covering the embedding space."""
        # Use first two dimensions for grid
        x_coords = embeddings[:, 0]
        y_coords = embeddings[:, 1]
        
        # Add small margin around the data
        x_margin = (np.max(x_coords) - np.min(x_coords)) * 0.05
        y_margin = (np.max(y_coords) - np.min(y_coords)) * 0.05
        
        x_min, x_max = np.min(x_coords) - x_margin, np.max(x_coords) + x_margin
        y_min, y_max = np.min(y_coords) - y_margin, np.max(y_coords) + y_margin
        
        # Create grid
        x_grid = np.linspace(x_min, x_max, grid_size)
        y_grid = np.linspace(y_min, y_max, grid_size)
        xx, yy = np.meshgrid(x_grid, y_grid)
        
        # For higher-dimensional embeddings, use mean values for other dimensions
        if embeddings.shape[1] > 2:
            other_dims = np.mean(embeddings[:, 2:], axis=0)
            # Repeat other dimensions for each grid point
            other_dims_repeated = np.tile(other_dims, (grid_size * grid_size, 1))
            grid_coords = np.column_stack([
                xx.ravel(), 
                yy.ravel(), 
                other_dims_repeated
            ])
        else:
            grid_coords = np.column_stack([xx.ravel(), yy.ravel()])
        
        return grid_coords, (x_min, x_max), (y_min, y_max)
    
    def _generate_image(
        self, 
        heatmap_array: np.ndarray, 
        x_range: Tuple[float, float], 
        y_range: Tuple[float, float],
        request: HeatmapRequest,
        value_label: str = "Prediction"
    ) -> Tuple[bytes, Optional[str]]:
        """Generate heatmap image."""
        plt.figure(figsize=(10, 8))
        
        # Create heatmap
        im = plt.imshow(
            heatmap_array,
            extent=[x_range[0], x_range[1], y_range[0], y_range[1]],
            origin='lower',
            aspect='auto',
            cmap=request.colormap,
            interpolation='bilinear'
        )
        
        # Add colorbar
        cbar = plt.colorbar(im)
        cbar.set_label(value_label)
        
        # Set labels and title
        plt.xlabel("Embedding Dimension 1")
        plt.ylabel("Embedding Dimension 2")
        
        title = request.title or f"{value_label} Heatmap - {request.target_tag}"
        plt.title(title)
        
        plt.tight_layout()
        
        # Save or convert to bytes
        save_path = None
        heatmap_image = None
        
        if request.save_path:
            plt.savefig(request.save_path, dpi=300, bbox_inches='tight')
            save_path = request.save_path
            with open(request.save_path, 'rb') as f:
                heatmap_image = f.read()
        else:
            import io
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            heatmap_image = buf.read()
            buf.close()
        
        plt.close()
        
        return heatmap_image, save_path
