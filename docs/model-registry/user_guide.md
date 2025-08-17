# EMUSES Model Registry User Guide

## Overview

EMUSES provides a model registry system that adapts to different research contexts. The registry supports three deployment modes:

- **Local Mode**: Individual researchers working on personal machines
- **Database Mode**: Research labs with collaborative model sharing  
- **Cloud Mode**: Production environments with community access

This guide walks you through using the model registry with currently available functionality.

## Quick Start

### Installation and Setup

EMUSES automatically detects your deployment mode based on your environment:

```bash
# Check your current setup
python -m emuses.cli models status

# List available models
python -m emuses.cli models list

# Get help for any command
python -m emuses.cli models --help
```

### Basic Model Operations

All deployment modes support these core operations:

```bash
# Install a model
python -m emuses.cli models install /path/to/model.zip

# Search for models
python -m emuses.cli models search "fMRI motor task"

# Get model information
python -m emuses.cli models info my-model

# Use model for inference (with full model path)
python -m emuses.cli inference /path/to/model /path/to/data
```

## Available Commands

The model registry provides these CLI commands:

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Show registry status and statistics | `python -m emuses.cli models status` |
| `list` | List models in the registry | `python -m emuses.cli models list` |
| `search` | Search for models by query | `python -m emuses.cli models search "motor"` |
| `info` | Get detailed model information | `python -m emuses.cli models info model-name` |
| `install` | Install a model into the registry | `python -m emuses.cli models install model.zip` |
| `remove` | Remove a model from the registry | `python -m emuses.cli models remove model-name` |
| `storage` | Show storage usage and thresholds | `python -m emuses.cli models storage` |
| `cleanup` | Clean up orphaned model directories | `python -m emuses.cli models cleanup` |
| `stats` | Show detailed registry statistics | `python -m emuses.cli models stats` |
| `mode-info` | Show deployment mode configuration | `python -m emuses.cli models mode-info` |
| `api-info` | Show API information (database mode) | `python -m emuses.cli models api-info` |

## Deployment Modes

### Local Mode

**Best for**: Individual researchers, offline work, personal model development

In Local Mode, models are stored in your home directory (`~/.emuses/models`) and managed through simple file operations. No authentication or network connectivity is required.

#### Model Storage Structure

```
~/.emuses/
├── model_registry/
│   ├── model-name-v1.0/
│   │   ├── models/
│   │   ├── artifacts/
│   │   ├── metadata/
│   │   └── model_manifest.json
│   └── registry.json
└── config/
```

#### Common Workflows

**Installing Models**:
```bash
# Install from file
python -m emuses.cli models install ~/downloads/brain-classifier.zip

# Install from directory
python -m emuses.cli models install ~/models/my-umap-model

# Install to custom registry location
python -m emuses.cli models install model.zip --registry ~/research/project-models
```

**Discovering Models**:
```bash
# List all models
python -m emuses.cli models list

# Search by keywords
python -m emuses.cli models search "motor cortex"

# Get detailed information
python -m emuses.cli models info brain-classifier
```

**Managing Storage**:
```bash
# Check storage usage
python -m emuses.cli models storage

# Clean up unused models
python -m emuses.cli models cleanup --dry-run
python -m emuses.cli models cleanup  # Remove orphaned files

# Remove specific model
python -m emuses.cli models remove old-model-v1
```

**Status and Statistics**:
```bash
# Check registry status
python -m emuses.cli models status

# View detailed statistics
python -m emuses.cli models stats

# Check deployment mode
python -m emuses.cli models mode-info
```

#### Tips for Local Mode
- Models are portable - you can copy the entire `~/.emuses/model_registry` directory to backup or transfer
- Use the `status` command to see registry location and current state
- The `cleanup` command helps maintain disk space by removing incomplete installations
- Check hidden directories in your file manager to access `~/.emuses` manually if needed

### Database Mode

**Best for**: Research labs, team collaboration, shared computing resources

In Database Mode, EMUSES connects to a PostgreSQL database to manage model metadata while storing model files on shared storage. This enables collaborative model sharing with proper access controls.

#### Configuration

Database Mode requires environment variables:

```bash
# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/emuses"
export EMUSES_DEPLOYMENT_MODE="multi-user"

# Check if database mode is available
python -m emuses.cli models mode-info
```

#### Admin Operations

Database Mode integrates with the multi-user EMUSES service:

```bash
# Check system status
python -m emuses.cli admin system-status

# List users (admin only)
python -m emuses.cli admin list-users

# Add user (admin only)
python -m emuses.cli admin add-user

# Get admin help
python -m emuses.cli admin help
```

#### Working with Database Registry

```bash
# Check database mode status and connection
python -m emuses.cli models mode-info

# View API information for database mode
python -m emuses.cli models api-info

# Install models (automatically stored in database)
python -m emuses.cli models install model.zip

# List models accessible to you
python -m emuses.cli models list

# Search across accessible models
python -m emuses.cli models search "task fMRI"

# Check storage usage in database mode
python -m emuses.cli models storage
```

#### Database Mode Features

- **Multi-user access control**: Models are associated with users and workspaces
- **Centralized storage**: Shared model storage with database metadata
- **API integration**: RESTful API for programmatic access
- **Permission management**: Role-based access to models

### Cloud Mode

**Best for**: Production deployments, community model sharing, public research

Cloud Mode provides full-featured model registry with cloud storage integration and advanced analytics.

#### Configuration

Cloud Mode requires additional environment variables:

```bash
# Set environment variables for cloud mode
export EMUSES_DEPLOYMENT_MODE="production"
export DATABASE_URL="postgresql://user:pass@db.example.com/emuses"

# Cloud storage configuration (if available)
export CLOUD_STORAGE_BACKEND="s3"  # or "azure"

# Check cloud mode status
python -m emuses.cli models mode-info
```

#### Cloud Mode Operations

Cloud Mode uses the same CLI commands as other modes, with additional features handled automatically by the registry factory:

```bash
# Install models (stored in cloud storage)
python -m emuses.cli models install model.zip

# Search models (includes cloud-based indexing)
python -m emuses.cli models search "HCP motor task"

# Get model info (includes usage analytics)
python -m emuses.cli models info model-name

# Check storage (includes cloud storage metrics)
python -m emuses.cli models storage
```

## Advanced Usage

### Custom Registry Paths

```bash
# Use custom registry path
python -m emuses.cli models list --registry /shared/project-models

# Install to custom location
python -m emuses.cli models install model.zip --registry /shared/project-models

# Check status of custom registry
python -m emuses.cli models status --registry /shared/project-models
```

### Integration with Analysis Workflows

```bash
# Use models for inference
python -m emuses.cli inference /path/to/model /path/to/data

# Get model information for reproducibility
python -m emuses.cli models info model-name

# Verify model integrity
python -m emuses.cli verify model-name

# Compare model versions (if available)
python -m emuses.cli compare model-v1 model-v2
```

### Storage Management

```bash
# Monitor storage usage
python -m emuses.cli models storage

# Clean up old or orphaned models
python -m emuses.cli models cleanup --dry-run  # Preview cleanup
python -m emuses.cli models cleanup           # Perform cleanup

# View detailed statistics
python -m emuses.cli models stats
```

## Best Practices

### Model Organization

**Naming Conventions**:
- Use descriptive names: `hcp-motor-task-classifier-v2.1`
- Include version numbers for clarity
- Use consistent naming patterns for related models

**Model Installation**:
- Always verify models have valid `model_manifest.json` files
- Use the `info` command to check model details before use
- Keep models organized with meaningful names and descriptions

### Performance Optimization

**Storage Management**:
```bash
# Regular cleanup to free space
python -m emuses.cli models cleanup

# Monitor storage usage
python -m emuses.cli models storage

# Remove unused models
python -m emuses.cli models remove unused-model
```

**Search Optimization**:
- Use specific keywords rather than generic terms
- Use the `search` command to find models efficiently
- Check `stats` to understand registry contents

## Troubleshooting

### Common Issues

**Model Not Found**:
```bash
# Check if model exists in current registry
python -m emuses.cli models list | grep model-name

# Search for models by name
python -m emuses.cli models search model-name

# Check registry status
python -m emuses.cli models status
```

**Storage Issues**:
```bash
# Check available space and usage
python -m emuses.cli models storage

# Clean up temporary files and orphaned directories
python -m emuses.cli models cleanup

# Verify model integrity
python -m emuses.cli verify model-name
```

**Mode Detection Issues**:
```bash
# Check current deployment mode
python -m emuses.cli models mode-info

# View API information (for database/cloud modes)
python -m emuses.cli models api-info

# Check system status (admin command)
python -m emuses.cli admin system-status
```

### Getting Help

**Built-in Help**:
```bash
# Command-specific help
python -m emuses.cli models install --help

# General model registry help
python -m emuses.cli models --help

# Full CLI help
python -m emuses.cli --help

# Admin commands help
python -m emuses.cli admin help
```

**Diagnostic Information**:
```bash
# Registry status and configuration
python -m emuses.cli models status

# Deployment mode information
python -m emuses.cli models mode-info

# Storage usage details
python -m emuses.cli models storage

# Registry statistics
python -m emuses.cli models stats
```

## Model Integration

### Using Registry Models

Once models are installed in the registry, you can use them with other EMUSES commands:

```bash
# Find the model path
python -m emuses.cli models info model-name

# Use model for inference (requires full path)
python -m emuses.cli inference /path/to/registry/model-name /path/to/data

# Verify model before use
python -m emuses.cli verify model-name

# Compare models
python -m emuses.cli compare model-v1 model-v2
```

### Model Metadata

All models in the registry include:
- **Manifest file**: `model_manifest.json` with metadata
- **Model artifacts**: Trained model files and components
- **Registry metadata**: Installation date, version, description
- **Usage tracking**: Access patterns and statistics (mode-dependent)

### Working with Model Paths

```bash
# List models to see available options
python -m emuses.cli models list

# Get full model information including paths
python -m emuses.cli models info model-name

# Use models by referencing their registry paths
# (paths shown in model info output)
```

This user guide covers the currently implemented functionality of the EMUSES model registry across all deployment modes, with practical examples and troubleshooting guidance.