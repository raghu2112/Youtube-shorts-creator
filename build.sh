#!/usr/bin/env bash
set -e

echo "=== Checking FFmpeg (pre-installed on Render) ==="
ffmpeg -version | head -1
ffprobe -version | head -1

echo "=== Installing Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Creating required directories ==="
mkdir -p /tmp/shorts-output
mkdir -p static
mkdir -p music

echo "=== Build complete ==="
