#!/bin/bash

echo "Building GoogleFlowTool for macOS..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "Error: Failed to upgrade pip"
    exit 1
fi

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements"
    exit 1
fi

# Install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller
if [ $? -ne 0 ]; then
    echo "Error: Failed to install PyInstaller"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist
rm -rf build

# Build executable
echo "Building executable..."
pyinstaller --clean --noconfirm GoogleFlowTool.spec
if [ $? -ne 0 ]; then
    echo "Error: Build failed"
    exit 1
fi

echo ""
echo "Build completed successfully!"
echo "Executable location: dist/GoogleFlowTool/GoogleFlowTool.app"
echo ""
