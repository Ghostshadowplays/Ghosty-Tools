#!/bin/bash

# Ghosty Tools Linux Build Script
# This script installs dependencies and builds the standalone binary using PyInstaller

# Exit on error
set -e

echo "Starting Ghosty Tools build process for Linux..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed."
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller

# Build the application
echo "Building the application using PyInstaller..."
pyinstaller ghosty_tools.spec --clean --noconfirm

echo "-------------------------------------------------------"
echo "Build finished successfully!"
echo "The Linux binary can be found in the 'dist' directory."
echo "Note: Users will need xclip or xsel for clipboard support."
echo "-------------------------------------------------------"
