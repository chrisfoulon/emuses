# 📦 EMUSES Installation Guide

**Complete installation instructions for different environments and use cases**

## 🎯 Quick Navigation

- [🚀 **Quick Installation**](#quick-installation) - Get started in 2 minutes
- [🔬 **Research Environment Setup**](#research-environment-setup) - Recommended for scientific work
- [🏛️ **Lab/Team Setup**](#lab-team-setup) - Multi-user environments  
- [🐳 **Production Deployment**](#production-deployment) - Docker and cloud deployment
- [🔧 **Troubleshooting**](#troubleshooting) - Common issues and solutions

---

## 🚀 Quick Installation

**For getting started quickly (testing/evaluation only):**

```bash
# Verify Python version
python --version  # Should be 3.11+

# Install EMUSES directly
pip install git+https://github.com/chrisfoulon/emuses.git

# Verify installation
python -m emuses.cli --help
```

**⚠️ Note**: This installs system-wide and may conflict with other packages. Use virtual environments for serious work.

---

## 🔬 Research Environment Setup

**Recommended for all scientific research work to ensure reproducibility and avoid conflicts.**

### Option A: Using `venv` (Built-in, Lightweight)

**Best for**: Individual researchers, simple setups, CI/CD pipelines

```bash
# Create project directory
mkdir my-emuses-project
cd my-emuses-project

# Create virtual environment
python -m venv emuses-env

# Activate environment
source emuses-env/bin/activate    # Linux/macOS
# emuses-env\Scripts\activate     # Windows

# Upgrade pip (recommended)
pip install --upgrade pip

# macOS ONLY: Install OpenMP via Homebrew (required for XGBoost)
# brew install libomp  # Run this outside Python, then continue

# Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git

# Optional: Install with additional features
# pip install "git+https://github.com/chrisfoulon/emuses.git[cloud]"          # Cloud storage (AWS S3, Azure Blob, Google Cloud)
# pip install "git+https://github.com/chrisfoulon/emuses.git[cache]"          # Caching support (Redis, Memcache)
# pip install "git+https://github.com/chrisfoulon/emuses.git[enterprise]"     # Enterprise features (Vault integration)
# pip install "git+https://github.com/chrisfoulon/emuses.git[all]"            # All optional features

# Create requirements file for reproducibility
pip freeze > requirements.txt

# Verify installation
emuses --version
emuses --help
```

**Reactivating your environment** (for future work sessions):
```bash
cd my-emuses-project
source emuses-env/bin/activate    # Linux/macOS
# emuses-env\Scripts\activate     # Windows
```

### Option B: Using `conda` (Recommended for Scientific Computing)

**Best for**: Research with heavy scientific dependencies, GPU computing, complex environments, **macOS users**

```bash
# Create conda environment with specific Python version
conda create -n emuses-research python=3.11

# Activate environment
conda activate emuses-research

# macOS ONLY: Install OpenMP (required for XGBoost and ML libraries)
conda install -c conda-forge libomp  # macOS only - one-time setup

# Install EMUSES via pip (recommended even in conda)
pip install git+https://github.com/chrisfoulon/emuses.git

# Optional: Install additional scientific tools
conda install jupyter notebook matplotlib seaborn

# Optional: Install GPU PyTorch if you have CUDA GPUs
# conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia

# Export environment for reproducibility
conda env export > environment.yml

# Verify installation
emuses --version
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
```

**Reactivating your environment**:
```bash
conda activate emuses-research
```

**Sharing your environment** with collaborators:
```bash
# Export environment
conda env export > emuses-environment.yml

# Others can recreate it with:
# conda env create -f emuses-environment.yml
```

---

## 🏛️ Lab/Team Setup

**For shared research environments and multi-user setups.**

### Shared Conda Environment

```bash
# Create shared environment (adjust path for your system)
sudo mkdir -p /opt/emuses
sudo chown $USER:research-group /opt/emuses  # Adjust group name

# Create environment in shared location
conda create -p /opt/emuses/env python=3.11

# Activate for installation
conda activate /opt/emuses/env

# Install EMUSES and common tools
pip install git+https://github.com/chrisfoulon/emuses.git
conda install jupyter matplotlib seaborn pandas numpy

# Create activation script for lab members
cat << 'EOF' > /opt/emuses/activate-emuses.sh
#!/bin/bash
echo "🔬 Activating EMUSES Lab Environment"
conda activate /opt/emuses/env
echo "✅ EMUSES activated. Type 'emuses --help' to get started."
EOF

chmod +x /opt/emuses/activate-emuses.sh

# Lab members can then use:
# source /opt/emuses/activate-emuses.sh
```

### Lab Usage Instructions

Create a README for lab members:

```bash
cat << 'EOF' > /opt/emuses/README.md
# Lab EMUSES Environment

## Activation
```bash
source /opt/emuses/activate-emuses.sh
```

## Usage
```bash
# Check environment
emuses --version

# Run analysis
emuses full output_dir/ data.csv --scores scores.csv

# Deactivate when done
conda deactivate
```

## Updating
Contact lab admin to update the shared environment.
EOF
```

---

## 🐳 Production Deployment

### Docker Installation

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Install EMUSES
RUN pip install --user git+https://github.com/chrisfoulon/emuses.git

# Add pip install location to PATH
ENV PATH="/home/app/.local/bin:${PATH}"

# Verify installation
RUN emuses --help

CMD ["emuses", "--help"]
```

Build and run:
```bash
# Build image
docker build -t emuses:latest .

# Run container
docker run -it --rm emuses:latest

# Run with volume mounting for data
docker run -it --rm -v $(pwd)/data:/data emuses:latest \
    emuses full /data/output /data/input.csv --scores /data/scores.csv
```

---

## 🔧 Troubleshooting

### Common Installation Issues

#### macOS: XGBoost/OpenMP Error

**Error**: `XGBoost Library (libxgboost.dylib) could not be loaded` or `libomp.dylib missing`

**Cause**: macOS doesn't include OpenMP by default, required by XGBoost and other ML libraries

**Solution**:
```bash
# For conda users (recommended):
conda install -c conda-forge libomp

# For pip/venv users:
brew install libomp

# Then restart your Python environment
```

**Why needed?** OpenMP enables multi-threading for XGBoost, LightGBM, and other ML libraries. This is a one-time macOS system setup, not an EMUSES issue.

#### Memory Errors During Installation
```bash
# Use pip cache to reduce memory usage
pip install --no-cache-dir git+https://github.com/chrisfoulon/emuses.git

# Or install dependencies separately
pip install numpy pandas scipy
pip install git+https://github.com/chrisfoulon/emuses.git
```

#### PyTorch/CUDA Issues
```bash
# Install specific PyTorch version
pip install torch --index-url https://download.pytorch.org/whl/cu118

# For CPU-only PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Verify CUDA availability
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

#### Import Errors
```bash
# Verify you're in the correct environment
which python
which pip

# Check EMUSES installation
python -c "import emuses; print('EMUSES installed at:', emuses.__file__)"

# Check key dependencies
python -c "import torch, pandas, numpy, sklearn; print('✅ Core dependencies available')"
```

#### Permission Errors
```bash
# Never use sudo with pip - use virtual environments instead
# If you must install system-wide (not recommended):
pip install --user git+https://github.com/chrisfoulon/emuses.git
```

### Environment Verification

Complete installation check:
```bash
#!/bin/bash
echo "🔍 EMUSES Installation Verification"
echo "=================================="

# Python version
echo "Python version: $(python --version)"

# Virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected (not recommended)"
fi

# EMUSES version
echo "EMUSES version: $(emuses --version 2>/dev/null || echo 'Not installed')"

# Core dependencies
python -c "
try:
    import torch; print('✅ PyTorch:', torch.__version__)
except ImportError: print('❌ PyTorch not available')

try:
    import pandas; print('✅ Pandas:', pandas.__version__)
except ImportError: print('❌ Pandas not available')

try:
    import nibabel; print('✅ Neuroimaging support available')
except ImportError: print('⚠️  Neuroimaging libraries not available')
"

echo ""
echo "🚀 Try: emuses --help"
```

### OS-Specific Considerations

#### Linux (Ubuntu/Debian)
```bash
# Install system dependencies for scientific computing
sudo apt-get update
sudo apt-get install -y build-essential python3-dev

# For neuroimaging libraries (optional)
sudo apt-get install -y libfreetype6-dev libpng-dev

# Then install EMUSES in virtual environment
python -m venv emuses-env
source emuses-env/bin/activate
pip install git+https://github.com/chrisfoulon/emuses.git
```

#### macOS
```bash
# Install Xcode command line tools (if not already installed)
xcode-select --install

# Using Homebrew (recommended for Python)
brew install python@3.11

# Create virtual environment
python3.11 -m venv emuses-env
source emuses-env/bin/activate
pip install git+https://github.com/chrisfoulon/emuses.git
```

#### Windows
```powershell
# Using PowerShell
# Ensure Python 3.11+ is installed from python.org

# Create virtual environment
python -m venv emuses-env

# Activate environment
.\emuses-env\Scripts\Activate.ps1

# Install EMUSES
pip install git+https://github.com/chrisfoulon/emuses.git
```

#### High-Performance Computing (HPC) Systems
```bash
# Load Python module (system-specific)
module load python/3.11  # or similar

# Create environment in your scratch space
python -m venv $SCRATCH/emuses-env
source $SCRATCH/emuses-env/bin/activate

# Install with no cache to avoid quota issues
pip install --no-cache-dir git+https://github.com/chrisfoulon/emuses.git

# For Slurm systems, you might need:
pip install --no-deps git+https://github.com/chrisfoulon/emuses.git
pip install -r requirements.txt  # Install dependencies separately
```

### Getting Help

If you encounter issues not covered here:

1. **Check the environment**: Make sure you're in the correct virtual environment
2. **Update pip**: `pip install --upgrade pip`
3. **Check dependencies**: Run the verification script above
4. **Clear pip cache**: `pip cache purge`
5. **GitHub Issues**: Report bugs at https://github.com/chrisfoulon/emuses/issues

---

## 📚 Next Steps

After installation:

- 📖 **[Quick Start Guide](QUICK_START.md)** - Your first analysis in 5 minutes
- 🔬 **[User Guide](USER_GUIDE.md)** - Comprehensive research workflows  
- 📊 **[Examples](examples/)** - Sample data and analysis scripts
- 🔧 **[API Reference](API_REFERENCE.md)** - Integration and automation
