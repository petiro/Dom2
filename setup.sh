#!/bin/bash
# Quick Setup Script for SuperAgent

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║         🚀  SuperAgent - Quick Setup  🚀                      ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
echo "📋 Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium
if [ $? -ne 0 ]; then
    echo "⚠️ Failed to install Playwright browsers (optional)"
fi
echo "✅ Playwright ready"
echo ""

# Create directories
echo "📁 Creating directories..."
mkdir -p data logs config
echo "✅ Directories created"
echo ""

# Check config
echo "⚙️ Checking configuration..."
if [ ! -f "config/config.yaml" ]; then
    echo "⚠️ config/config.yaml not found"
    echo "Please create it or copy from config.yaml.example"
else
    echo "✅ Configuration found"
fi
echo ""

# Final instructions
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 Setup Complete! 🎉                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. Get free API key: https://openrouter.ai/keys"
echo "2. Add key to config/config.yaml"
echo "3. Run: python main.py"
echo ""
echo "📚 See README.md for full documentation"
echo ""
