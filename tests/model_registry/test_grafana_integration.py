"""Tests for Grafana dashboard integration with model analytics."""

import json
import uuid
from pathlib import Path

import pytest


class TestGrafanaDashboardIntegration:
    """Test Grafana dashboard configuration for model registry analytics."""

    def test_dashboard_json_exists(self):
        """Test that model analytics dashboard JSON file exists."""
        dashboard_path = Path(__file__).parent.parent.parent / "docker" / "observability" / "grafana" / "dashboards" / "emuses-model-analytics.json"
        assert dashboard_path.exists(), f"Dashboard file should exist at {dashboard_path}"

    def test_dashboard_json_valid(self):
        """Test that dashboard JSON is valid and contains required panels."""
        dashboard_path = Path(__file__).parent.parent.parent / "docker" / "observability" / "grafana" / "dashboards" / "emuses-model-analytics.json"
        
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)
        
        # Validate basic structure
        assert "title" in dashboard
        assert "panels" in dashboard
        assert isinstance(dashboard["panels"], list)
        assert len(dashboard["panels"]) > 0
        
        # Check for model registry specific panels
        panel_titles = [panel.get("title", "") for panel in dashboard["panels"]]
        expected_panels = [
            "Model Downloads Over Time",
            "Most Popular Models",
            "Download Methods Distribution", 
            "User Activity",
            "Model Registry Size"
        ]
        
        for expected_panel in expected_panels:
            assert any(expected_panel in title for title in panel_titles), f"Missing panel: {expected_panel}"

    def test_dashboard_prometheus_queries(self):
        """Test that dashboard contains valid Prometheus queries for model metrics."""
        dashboard_path = Path(__file__).parent.parent.parent / "docker" / "observability" / "grafana" / "dashboards" / "emuses-model-analytics.json"
        
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)
        
        # Extract queries from panels
        queries = []
        for panel in dashboard["panels"]:
            if "targets" in panel:
                for target in panel["targets"]:
                    if "expr" in target:
                        queries.append(target["expr"])
        
        # Validate that we use the model registry metrics we defined
        expected_metrics = [
            "emuses_model_downloads_total",
            "emuses_model_registry_size",
            "emuses_model_analytics_operations_total",
            "emuses_model_recommendation_requests_total"
        ]
        
        queries_text = " ".join(queries)
        for metric in expected_metrics:
            assert metric in queries_text, f"Missing metric in dashboard queries: {metric}"

    def test_dashboard_configuration_integration(self):
        """Test that dashboard is properly configured for provisioning."""
        dashboard_path = Path(__file__).parent.parent.parent / "docker" / "observability" / "grafana" / "dashboards" / "emuses-model-analytics.json"
        
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)
        
        # Should have proper dashboard metadata
        assert "uid" in dashboard
        assert "title" in dashboard
        assert dashboard["title"] == "EMUSES Model Analytics"
        
        # Should be configured for proper refresh and time ranges
        assert "refresh" in dashboard
        assert "time" in dashboard


if __name__ == "__main__":
    pytest.main([__file__])