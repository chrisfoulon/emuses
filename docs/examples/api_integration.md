# API Integration Example

Using EMUSES programmatically through Python API and REST API integration for batch processing workflows and service-based deployments.

## Overview

This example demonstrates how to integrate EMUSES into your existing workflows using both the Python API and REST API interfaces. Perfect for batch processing, automated pipelines, and service-based deployments.

## Python API Integration

### Basic Analysis with Python API

```python
import pandas as pd
from emuses.core.pipeline import EMUSESPipeline
from emuses.config.pipeline_config import PipelineConfig

# Load your data
features = pd.read_csv("docs/examples/sample_data/hcp_input_data.csv", index_col=0)
labels = pd.read_csv("docs/examples/sample_data/hcp_labels.csv", index_col=0)

# Configure the pipeline
config = PipelineConfig(
    normalization="robust",
    umap_trials=5,
    hdbscan_trials=3,
    prediction_model="ridge",
    cross_validation_folds=5
)

# Run the analysis
pipeline = EMUSESPipeline(config)
results = pipeline.run(
    features=features,
    labels=labels,
    output_dir="./results/api_example"
)

# Access results
print(f"UMAP embedding shape: {results['umap'].embeddings.shape}")
print(f"Prediction R²: {results['prediction'].r2_score:.3f}")
print(f"Number of clusters: {results['clustering'].n_clusters}")
```

### Batch Processing Multiple Datasets

```python
import os
import glob
from pathlib import Path
from emuses.core.batch_processor import BatchProcessor

# Setup batch processing
batch_config = {
    "normalization": "robust",
    "umap_trials": 3,
    "hdbscan_trials": 2,
    "prediction_model": "ridge"
}

processor = BatchProcessor(batch_config)

# Process multiple datasets
data_directory = "/path/to/your/datasets"
pattern = "study_*_features.csv"

batch_results = processor.process_directory(
    data_dir=data_directory,
    feature_pattern=pattern,
    label_pattern="study_*_labels.csv",
    output_dir="./batch_results"
)

# Generate summary report
summary = processor.generate_summary_report(batch_results)
summary.save("./batch_results/summary_report.html")
```

## REST API Integration

### Starting the EMUSES Service

```bash
# Start the EMUSES FastAPI service
uvicorn emuses.api.main:app --host 0.0.0.0 --port 8000

# Or using the CLI
python -m emuses.cli serve --port 8000
```

### Basic REST API Usage

#### **Upload and Analyze Data**

```python
import requests
import json

# API endpoint
base_url = "http://localhost:8000"

# Upload feature data
with open("docs/examples/sample_data/hcp_input_data.csv", "rb") as f:
    features_response = requests.post(
        f"{base_url}/upload/features",
        files={"file": f}
    )
features_id = features_response.json()["file_id"]

# Upload label data
with open("docs/examples/sample_data/hcp_labels.csv", "rb") as f:
    labels_response = requests.post(
        f"{base_url}/upload/labels",
        files={"file": f}
    )
labels_id = labels_response.json()["file_id"]

# Configure analysis
analysis_config = {
    "features_file_id": features_id,
    "labels_file_id": labels_id,
    "normalization": "robust",
    "umap_trials": 5,
    "hdbscan_trials": 3,
    "prediction_model": "ridge"
}

# Submit analysis job
job_response = requests.post(
    f"{base_url}/analysis/submit",
    json=analysis_config
)
job_id = job_response.json()["job_id"]

print(f"Analysis job submitted: {job_id}")
```

#### **Monitor Analysis Progress**

```python
import time

# Check job status
while True:
    status_response = requests.get(f"{base_url}/analysis/status/{job_id}")
    status = status_response.json()
    
    print(f"Status: {status['status']}")
    print(f"Progress: {status['progress']}%")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(10)  # Check every 10 seconds

# Download results
if status["status"] == "completed":
    results_response = requests.get(f"{base_url}/analysis/results/{job_id}")
    results = results_response.json()
    
    print(f"Analysis completed!")
    print(f"R² Score: {results['prediction']['r2_score']:.3f}")
    print(f"Clusters found: {results['clustering']['n_clusters']}")
```

### Advanced API Usage

#### **Custom Pipeline Stages**

```python
# Run individual pipeline stages via API
stage_configs = {
    "umap": {
        "file_id": features_id,
        "n_neighbors": 15,
        "min_dist": 0.1,
        "n_components": 2,
        "metric": "euclidean"
    }
}

# Submit UMAP stage only
umap_response = requests.post(
    f"{base_url}/pipeline/umap",
    json=stage_configs["umap"]
)
umap_job_id = umap_response.json()["job_id"]

# Get UMAP results
umap_results = requests.get(f"{base_url}/pipeline/results/{umap_job_id}")
embedding_data = umap_results.json()["embedding"]
```

#### **Real-time Processing with WebSockets**

```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"Stage: {data['stage']}, Progress: {data['progress']}%")

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws):
    print("WebSocket connection closed")

# Connect to real-time updates
ws_url = "ws://localhost:8000/analysis/stream/{job_id}"
ws = websocket.WebSocketApp(
    ws_url,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close
)

ws.run_forever()
```

## Service-Based Deployment

### Docker Integration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install EMUSES
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install emuses

# Setup service
COPY api_config.json .
EXPOSE 8000

CMD ["uvicorn", "emuses.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emuses-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: emuses-api
  template:
    metadata:
      labels:
        app: emuses-api
    spec:
      containers:
      - name: emuses-api
        image: emuses/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: EMUSES_CONFIG_PATH
          value: "/config/emuses.yaml"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
---
apiVersion: v1
kind: Service
metadata:
  name: emuses-api-service
spec:
  selector:
    app: emuses-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

### Integration with Workflow Managers

#### **Nextflow Integration**

```groovy
process EMUSES_ANALYSIS {
    container 'emuses/api:latest'
    
    input:
    path features_file
    path labels_file
    val analysis_params
    
    output:
    path "results/*"
    
    script:
    """
    curl -X POST http://emuses-api:8000/analysis/submit \
         -H "Content-Type: application/json" \
         -d '${analysis_params}' \
         -F "features=@${features_file}" \
         -F "labels=@${labels_file}"
    """
}
```

#### **Snakemake Integration**

```python
rule emuses_analysis:
    input:
        features="data/{sample}_features.csv",
        labels="data/{sample}_labels.csv"
    output:
        results="results/{sample}/analysis_results.json"
    params:
        api_url="http://emuses-api:8000"
    shell:
        """
        python scripts/submit_emuses_analysis.py \
            --features {input.features} \
            --labels {input.labels} \
            --output {output.results} \
            --api-url {params.api_url}
        """
```

## Performance Considerations

### Optimal Batch Sizes

```python
# For batch processing, optimize based on available resources
batch_processor = BatchProcessor({
    "max_concurrent_jobs": 4,  # Based on CPU cores
    "memory_limit_gb": 16,     # Available RAM
    "chunk_size": 1000,        # Subjects per batch
    "cache_intermediate": True  # Reuse computations
})
```

### Caching and Performance

```python
# Enable caching for repeated analyses
from emuses.core.cache import AnalysisCache

cache = AnalysisCache(
    backend="redis",  # or "memory", "disk"
    ttl=3600,        # 1 hour cache
    max_size_mb=1024  # 1GB cache limit
)

pipeline = EMUSESPipeline(config, cache=cache)
```

## Error Handling and Monitoring

### Robust API Integration

```python
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def submit_analysis_with_retry(config):
    try:
        response = requests.post(
            f"{base_url}/analysis/submit",
            json=config,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Analysis submission failed: {e}")
        raise

# Usage
try:
    job_info = submit_analysis_with_retry(analysis_config)
    logging.info(f"Job submitted successfully: {job_info['job_id']}")
except Exception as e:
    logging.error(f"Failed after retries: {e}")
```

## Next Steps

1. **Start Simple**: Begin with the basic Python API examples
2. **Scale Up**: Move to REST API for distributed processing
3. **Deploy Services**: Use Docker/Kubernetes for production
4. **Monitor Performance**: Implement logging and monitoring
5. **Customize Integration**: Adapt patterns for your specific workflow

For more examples:
- [HCP Dataset Analysis](hcp_analysis.md) - Complete analysis workflow
- [Custom Pipeline](custom_pipeline.md) - Building custom analysis stages
- [API Reference](../API_REFERENCE.md) - Complete API documentation