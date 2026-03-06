#!/usr/bin/env bash
set -e   # exit immediately on any error

echo "=== Installing FFmpeg ==="
sudo apt-get update -qq
sudo apt-get install -y ffmpeg

echo "=== FFmpeg version ==="
ffmpeg -version | head -1

echo "=== Installing Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Creating required directories ==="
mkdir -p /tmp/shorts-output
mkdir -p static
mkdir -p music

echo "=== Build complete ==="
