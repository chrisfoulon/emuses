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

# Copy requirements and install Python dependencies with pip-tools
COPY requirements.txt requirements-prod.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel pip-tools && \
    pip-sync requirements-prod.txt

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