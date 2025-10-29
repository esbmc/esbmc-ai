#!/bin/bash
# Container build script for ESBMC-AI
# Supports both Docker and Podman runtimes
# Usage: build.sh <runtime> [extra_packages] [esbmc_version]
#   runtime: "docker" or "podman"
#   extra_packages: optional pip packages to inject (e.g., "pkg1 pkg2")
#   esbmc_version: optional ESBMC version (default: "latest")

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <docker|podman> [extra_packages] [esbmc_version]"
    exit 1
fi

RUNTIME="$1"
EXTRA_PACKAGES="${2:-}"
ESBMC_VERSION="${3:-latest}"

# Validate runtime
if [ "$RUNTIME" != "docker" ] && [ "$RUNTIME" != "podman" ]; then
    echo "Error: Runtime must be 'docker' or 'podman'"
    exit 1
fi

# Check if runtime is installed
if ! command -v "$RUNTIME" &> /dev/null; then
    echo "Error: $RUNTIME is not installed"
    exit 1
fi

# Extract version from __about__.py
VERSION=$(grep -oP '__version__ = "\K[^"]+' esbmc_ai/__about__.py 2>/dev/null)
if [ -z "$VERSION" ]; then
    echo "Warning: Could not extract version from __about__.py"
    VERSION="unknown"
fi

# Get git commit hash (short form)
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "Building ESBMC-AI container image with $RUNTIME..."
echo "  Version: $VERSION"
echo "  Git commit: $GIT_COMMIT"
echo "  ESBMC version: $ESBMC_VERSION"
if [ -n "$EXTRA_PACKAGES" ]; then
    echo "  Extra packages: $EXTRA_PACKAGES"
fi

# Build the image with multiple tags
"$RUNTIME" build \
    --tag "esbmc-ai:$VERSION" \
    --tag "esbmc-ai:$GIT_COMMIT" \
    --tag esbmc-ai:latest \
    --build-arg ESBMC_VERSION="$ESBMC_VERSION" \
    --build-arg EXTRA_PIP_PACKAGES="$EXTRA_PACKAGES" \
    -f Containerfile \
    .

echo "✓ Image built successfully with tags:"
echo "  - esbmc-ai:$VERSION"
echo "  - esbmc-ai:$GIT_COMMIT"
echo "  - esbmc-ai:latest"
