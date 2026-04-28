"""
SHAP and LIME based explainability for anomaly detection models.

Provides functions to generate model explanations and feature importance scores.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import shap
import lime
import lime.lime_tabular
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger("anomali.explainers")


class ExplainerConfig:
    """Configuration for SHAP/LIME explainers."""

    def __init__(self, method: str = "shap", sample_size: int = 100, background_sample_size: int = 50):
        """
        Args:
            method: 'shap' or 'lime'
            sample_size: Number of instances to explain
            background_sample_size: SHAP background sample size
        """
        self.method = method
        self.sample_size = sample_size
        self.background_sample_size = background_sample_size


def calculate_shap_values(
    model: Any,
    X: pd.DataFrame,
    algorithm: str,
    outlier_indices: List[int],
    config: ExplainerConfig = None,
) -> Dict[str, Any]:
    """
    Calculate SHAP values for model predictions.

    Args:
        model: Trained sklearn model
        X: Feature matrix (pd.DataFrame)
        algorithm: Algorithm name (IsolationForest, LOF, DBSCAN, etc.)
        outlier_indices: List of detected outlier indices
        config: ExplainerConfig instance

    Returns:
        Dictionary with SHAP analysis results:
        {
            'method': 'shap',
            'shap_values': shape (n_samples, n_features),
            'base_value': float,
            'feature_names': list,
            'top_features_per_instance': dict of instance_idx -> list of (feature, value),
            'feature_importance': dict of feature -> mean absolute SHAP value,
            'outlier_explanations': dict of instance_idx -> explanation
        }
    """
    if config is None:
        config = ExplainerConfig()

    try:
        X_array = X.values if isinstance(X, pd.DataFrame) else X
        feature_names = list(X.columns) if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]

        # Select background data for SHAP (randomly sample if needed)
        bg_size = min(config.background_sample_size, len(X_array))
        bg_indices = np.random.choice(len(X_array), size=bg_size, replace=False)
        X_background = X_array[bg_indices]

        # Choose SHAP explainer based on algorithm
        if algorithm == "IsolationForest":
            # TreeExplainer for tree-based models
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_array)
            if isinstance(shap_values, list):
                # For binary classification-like outputs
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            base_value = explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = base_value[1] if len(base_value) > 1 else base_value[0]
        else:
            # KernelExplainer for other models
            explainer = shap.KernelExplainer(lambda x: model.decision_function(x) if hasattr(model, 'decision_function') else model.predict(x), 
                                             X_background)
            shap_values = explainer.shap_values(X_array[:min(config.sample_size, len(X_array))])
            base_value = explainer.expected_value

        # Ensure shap_values is 2D
        if len(shap_values.shape) == 1:
            shap_values = shap_values.reshape(-1, 1)

        # Calculate feature importance (mean absolute SHAP value)
        feature_importance = np.abs(shap_values).mean(axis=0)
        feature_importance_dict = {name: float(val) for name, val in zip(feature_names, feature_importance)}
        feature_importance_dict = dict(sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True))

        # Prepare top features explanation for each outlier
        outlier_explanations = {}
        for idx in outlier_indices[:min(config.sample_size, len(outlier_indices))]:
            if idx < len(shap_values):
                top_k = 5
                top_indices = np.argsort(np.abs(shap_values[idx]))[-top_k:][::-1]
                top_features = [
                    {
                        "feature": feature_names[i],
                        "shap_value": float(shap_values[idx, i]),
                        "abs_shap_value": float(np.abs(shap_values[idx, i])),
                    }
                    for i in top_indices
                ]
                outlier_explanations[int(idx)] = top_features

        result = {
            "method": "shap",
            "algorithm": algorithm,
            "shap_values": shap_values.tolist() if len(shap_values) <= 100 else f"Shape: {shap_values.shape}",  # Limit size for serialization
            "base_value": float(base_value) if isinstance(base_value, (int, float, np.number)) else str(base_value),
            "feature_names": feature_names,
            "feature_importance": feature_importance_dict,
            "outlier_explanations": outlier_explanations,
            "n_samples_analyzed": len(X_array),
            "n_outliers_analyzed": len(outlier_indices),
        }

        logger.info(f"SHAP analysis completed for {algorithm}: {len(feature_importance_dict)} features, {len(outlier_explanations)} outliers explained")
        return result

    except Exception as e:
        logger.error(f"SHAP calculation failed for {algorithm}: {str(e)}")
        return {
            "method": "shap",
            "algorithm": algorithm,
            "error": str(e),
            "status": "failed",
        }


def calculate_lime_explanation(
    model: Any,
    X: pd.DataFrame,
    algorithm: str,
    outlier_indices: List[int],
    instance_indices: Optional[List[int]] = None,
    config: ExplainerConfig = None,
) -> Dict[str, Any]:
    """
    Calculate LIME explanations for specific instances.

    Args:
        model: Trained sklearn model
        X: Feature matrix (pd.DataFrame)
        algorithm: Algorithm name
        outlier_indices: List of detected outlier indices
        instance_indices: List of specific instance indices to explain (defaults to first few outliers)
        config: ExplainerConfig instance

    Returns:
        Dictionary with LIME explanation results
    """
    if config is None:
        config = ExplainerConfig()

    try:
        X_array = X.values if isinstance(X, pd.DataFrame) else X
        feature_names = list(X.columns) if isinstance(X, pd.DataFrame) else [f"feature_{i}" for i in range(X.shape[1])]

        # Determine prediction function
        if hasattr(model, 'decision_function'):
            predict_fn = lambda x: model.decision_function(x)
        elif hasattr(model, 'predict_proba'):
            predict_fn = lambda x: model.predict_proba(x)[:, 1]
        else:
            predict_fn = lambda x: model.predict(x).astype(float)

        # Create LIME explainer
        explainer = lime.lime_tabular.LimeTabularExplainer(
            X_array,
            feature_names=feature_names,
            mode='regression',
            verbose=False,
        )

        # Default: explain first few outliers
        if instance_indices is None:
            instance_indices = outlier_indices[:min(config.sample_size, len(outlier_indices))]

        explanations = {}
        for idx in instance_indices:
            if idx < len(X_array):
                exp = explainer.explain_instance(X_array[idx], predict_fn, num_features=len(feature_names))
                # Extract feature weights
                feature_weights = {}
                for feature_idx, weight in exp.as_list():
                    feature_weights[str(feature_idx)] = float(weight)
                explanations[int(idx)] = {
                    "instance_index": int(idx),
                    "prediction": float(predict_fn(X_array[idx : idx + 1])[0]),
                    "feature_weights": feature_weights,
                }

        result = {
            "method": "lime",
            "algorithm": algorithm,
            "feature_names": feature_names,
            "explanations": explanations,
            "n_samples_analyzed": len(X_array),
            "n_outliers_analyzed": len(outlier_indices),
            "n_instances_explained": len(explanations),
        }

        logger.info(f"LIME analysis completed for {algorithm}: explained {len(explanations)} instances")
        return result

    except Exception as e:
        logger.error(f"LIME calculation failed for {algorithm}: {str(e)}")
        return {
            "method": "lime",
            "algorithm": algorithm,
            "error": str(e),
            "status": "failed",
        }


def generate_explanation_report(
    model: Any,
    X: pd.DataFrame,
    algorithm: str,
    outlier_indices: List[int],
    methods: List[str] = None,
    config: ExplainerConfig = None,
) -> Dict[str, Any]:
    """
    Generate comprehensive explanation report using specified methods.

    Args:
        model: Trained sklearn model
        X: Feature matrix
        algorithm: Algorithm name
        outlier_indices: List of outlier indices
        methods: List of methods ('shap', 'lime') - defaults to ['shap']
        config: ExplainerConfig instance

    Returns:
        Dictionary with complete explanation report
    """
    if methods is None:
        methods = ["shap"]

    if config is None:
        config = ExplainerConfig()

    report = {
        "algorithm": algorithm,
        "n_samples": len(X),
        "n_outliers": len(outlier_indices),
        "methods": methods,
        "explanations": {},
    }

    if "shap" in methods:
        report["explanations"]["shap"] = calculate_shap_values(model, X, algorithm, outlier_indices, config)

    if "lime" in methods:
        report["explanations"]["lime"] = calculate_lime_explanation(model, X, algorithm, outlier_indices, config=config)

    return report
