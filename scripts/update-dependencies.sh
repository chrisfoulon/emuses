#!/bin/bash
# update-dependencies.sh - EMUSES Dependency Update Script

set -e  # Exit on any error

echo "🔄 Updating EMUSES dependencies..."

# Check if pip-tools is installed
if ! command -v pip-compile &> /dev/null; then
    echo "❌ pip-tools not found. Installing..."
    pip install pip-tools
fi

echo "📦 Updating base requirements..."
pip-compile --upgrade requirements.in

echo "🧪 Updating development requirements..."
pip-compile --upgrade requirements-dev.in

echo "🚀 Updating production requirements..."
pip-compile --upgrade requirements-prod.in

echo "🔍 Running security scan..."
if command -v safety &> /dev/null; then
    safety scan --policy-file .safety-policy.yml || echo "⚠️  Security scan completed with warnings"
else
    echo "⚠️  Safety not installed - skipping security scan"
fi

echo ""
echo "✅ Dependencies updated successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Review changes: git diff requirements*.txt"
echo "   2. Test installation: pip-sync requirements-dev.txt"
echo "   3. Run tests to ensure compatibility"
echo "   4. Commit changes if everything works"