#!/bin/bash
# Install dev_skel to ~/dev

set -e

SKEL_DIR="/home/beret/dev_skel"
TARGET_DIR="$HOME/dev"

echo "Installing dev skeleton to $TARGET_DIR..."

# Create target directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Copy all files and directories from skel to target
rsync -av --progress "$SKEL_DIR/" "$TARGET_DIR/" \
    --exclude 'install.sh' \
    --exclude 'update.sh' \
    --exclude '_test_projects'

echo "Installation complete!"
echo "Dev skeleton has been installed to $TARGET_DIR"
