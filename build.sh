#!/bin/bash
set -e

echo "🔨 Installing Python dependencies..."
pip install -r requirements.txt

echo "📦 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

echo "🎨 Building React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "✅ Build complete!"
