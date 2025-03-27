#!/bin/bash

# Display script usage
usage() {
  echo "Usage: $0 <requirements_file> [output_filename]"
  echo ""
  echo "Creates an AWS Lambda layer zip file from Python dependencies."
  echo ""
  echo "Arguments:"
  echo "  requirements_file    Path to the requirements.txt file"
  echo "  output_filename      Name of the output zip file (default: layer)"
  echo "                       (.zip extension will be added automatically if missing)"
  echo ""
  echo "Example:"
  echo "  $0 requirements.txt"
  echo "  $0 requirements.txt my-layer"
  exit 1
}

# Check if requirements file is provided
if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  usage
fi

REQ_FILE=$1
OUTPUT_NAME=${2:-layer}  # Use second argument if provided, otherwise default to "layer"

# Create layer_outputs directory if it doesn't exist
mkdir -p layer_outputs

# Add .zip extension if it doesn't exist
if [[ "$OUTPUT_NAME" != *".zip" ]]; then
  OUTPUT_FILE="layer_outputs/${OUTPUT_NAME}.zip"
else
  OUTPUT_FILE="layer_outputs/$OUTPUT_NAME"
fi

# Check if the requirements file exists
if [ ! -f "$REQ_FILE" ]; then
    echo "Error: Requirements file $REQ_FILE not found"
    usage
fi

echo "Using requirements file: $REQ_FILE"
echo "Output will be saved as: $OUTPUT_FILE"

# Create python directory if it doesn't exist
mkdir -p python

# Install requirements to the python directory
pip install -r "$REQ_FILE" -t python/

# Create zip file including the python directory itself
zip -r9 "$OUTPUT_FILE" python -x "*.pyc" -x "python/*.dist-info/*" -x "python/*.egg-info/*"

# Clean up
rm -rf python/
echo "Layer zip file $OUTPUT_FILE created successfully and python directory cleaned up"