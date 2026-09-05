# Multi-stage build for EMUSES API service
FROM python:3.11-slim as builder

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install the pinned production set.
#
# requirements-prod.txt starts with `-r requirements.txt`, so both files are
# needed here and pip reads them as one set.
#
# --no-deps is deliberate, and matches what all three workflows do. It is not a
# shortcut: the lockfile is the complete pinned set, and re-resolving it fails on
# purpose-built overrides. gpy 1.13.2 declares scipy<=1.12.0 while the pipeline is
# pinned to scipy 1.17.1 -- the version every regression baseline was validated
# against -- and that bound is conservative rather than real (GPRegression and
# SparseGPClassification both verified against 1.17.1). It cannot be resolved
# away either: gpy 1.14.2 drops the bound but requires paramz>0.9.6, and the only
# such paramz (0.10.0) requires numpy>=2, which would invalidate every baseline.
#
# `pip-sync` was used here before and had never once worked. It resolves rather
# than installing the pinned set, so it died on that override with
# ResolutionImpossible -- see ci.yml, which abandoned pip-sync for a second
# reason (pip-tools imports stdlib_pkgs from pip._internal.utils.compat, which
# current pip no longer provides).
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-deps -r requirements-prod.txt

# Production stage
FROM python:3.11-slim

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r emuses && useradd -r -g emuses emuses

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/storage /app/logs && \
    chown -R emuses:emuses /app

# Copy startup and health check scripts
COPY docker/startup.sh /app/startup.sh
COPY docker/health_check.sh /app/health_check.sh
RUN chmod +x /app/startup.sh /app/health_check.sh

# Switch to non-root user
USER emuses

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/app/health_check.sh"]

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV EMUSES_DEPLOYMENT_MODE=production
ENV EMUSES_SERVICE_HOST=0.0.0.0
ENV EMUSES_SERVICE_PORT=8000

# Startup command
CMD ["/app/startup.sh"]