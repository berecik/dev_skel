#!/bin/bash
# Update ~/dev with changes from dev_skel

set -e

SKEL_DIR="/home/beret/dev_skel"
TARGET_DIR="$HOME/dev"

echo "Updating $TARGET_DIR from dev_skel..."

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: $TARGET_DIR does not exist."
    echo "Run install.sh first to set up the dev directory."
    exit 1
fi

# Sync changes from skel to target
rsync -av --progress "$SKEL_DIR/" "$TARGET_DIR/" \
    --exclude 'install.sh' \
    --exclude 'update.sh' \
    --exclude '_test_projects'

echo "Update complete!"
echo "$TARGET_DIR has been synchronized with dev_skel"
