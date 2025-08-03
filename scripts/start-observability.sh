#!/bin/bash

# EMUSES Observability Stack Startup Script
# Starts Prometheus, Grafana, and Node Exporter for system monitoring

set -e

echo "🔍 Starting EMUSES Observability Stack..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create network if it doesn't exist
echo "📡 Creating Docker network..."
docker network create emuses-network 2>/dev/null || echo "Network already exists"

# Start the observability stack
echo "🚀 Starting observability services..."
docker-compose -f docker-compose.observability.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."

# Check Prometheus
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is running at http://localhost:9090"
else
    echo "⚠️  Prometheus may not be ready yet. Check logs: docker logs emuses-prometheus"
fi

# Check Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is running at http://localhost:3000 (admin/admin)"
else
    echo "⚠️  Grafana may not be ready yet. Check logs: docker logs emuses-grafana"
fi

# Check Node Exporter
if curl -f http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✅ Node Exporter is running at http://localhost:9100"
else
    echo "⚠️  Node Exporter may not be ready yet. Check logs: docker logs emuses-node-exporter"
fi

echo ""
echo "🎯 Quick Access URLs:"
echo "   📊 Grafana Dashboard: http://localhost:3000"
echo "   📈 Prometheus Metrics: http://localhost:9090"
echo "   💾 Node Exporter: http://localhost:9100"
echo ""
echo "📖 To view logs: docker-compose -f docker-compose.observability.yml logs -f"
echo "🛑 To stop: docker-compose -f docker-compose.observability.yml down"
echo ""
echo "✨ Observability stack is ready! Run your EMUSES API to see metrics."