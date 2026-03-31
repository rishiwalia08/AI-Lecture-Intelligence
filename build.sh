#!/usr/bin/env bash
set -e

echo "🔨 Installing Python dependencies..."
pip install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  echo "🎨 Building React frontend..."
  cd frontend
  if [ -f "package-lock.json" ]; then
    npm ci
  else
    npm install
  fi
  npm run build
  cd ..
else
  echo "⚠️ npm not available in this build environment."
  echo "Skipping frontend build and continuing with backend-only deploy."
fi

echo "✅ Build complete!"
