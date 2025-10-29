---
title: Building ESBMC-AI
type: docs
weight: 7
prev: /docs/contributing
next: /docs/architecture
---

This guide covers building ESBMC-AI locally and as a container image.

## Local Build

ESBMC-AI uses [Hatch](https://hatch.pypa.io/) as its build backend and project manager.

### Building a Wheel

```sh
# Build the wheel package
hatch build

# Output: dist/esbmc_ai-<version>-py3-none-any.whl
```

### Development Environment

```sh
# Run without installing (uses hatch environment)
hatch run esbmc-ai <command>

# Enter development shell
hatch shell

# Run tests
hatch test
```

The build process is defined in `pyproject.toml:41-43` using the `hatchling` build backend.

## Container Build

ESBMC-AI uses a multi-stage Containerfile for efficient image builds.

### Build Commands

```sh
# Using hatch scripts (recommended)
hatch run podman-build [extra_packages] [esbmc_version]
hatch run docker-build [extra_packages] [esbmc_version]

# Examples
hatch run podman-build                           # Default: latest ESBMC
hatch run podman-build "langchain-google-genai"  # With extra packages
hatch run podman-build "" "v7.4"                 # Specific ESBMC version
```

### Build Script

The `scripts/container/build.sh` script:
- Accepts runtime (docker/podman), optional extra packages, and ESBMC version
- Extracts version from `esbmc_ai/__about__.py`
- Tags images as `esbmc-ai:latest`, `esbmc-ai:<version>`, and `esbmc-ai:<git-commit>`
- Passes build arguments to the Containerfile

## Containerfile Architecture

The Containerfile uses a two-stage build process (Containerfile:1-118):

### Stage 1: Builder

- Base: Ubuntu 24.04
- Installs Python 3.12 and pipx
- Installs Hatch via pipx
- Runs `hatch build` to create the wheel
- Output: `/src/dist/*.whl`

### Stage 2: Runtime

**System Setup:**
- Base: Ubuntu 24.04
- Installs Python 3.12, pipx, git, wget, and C/C++ development headers
- Downloads and installs ESBMC binary from GitHub releases (lines 68-78)

**ESBMC-AI Installation:**
- Copies wheel from builder stage (line 84)
- Installs via pipx with CPU-only PyTorch (lines 87-90)
- Optionally injects extra packages via `EXTRA_PIP_PACKAGES` build arg (lines 93-97)

**Runtime Configuration:**
- Sets `ESBMCAI_VERIFIER__ESBMC__PATH=/bin/esbmc` (line 104)
- Declares API key environment variables (lines 107-109)
- Sets working directory to `/workspace` (line 112)
- Copies and sets entrypoint script (lines 100-115)
- Default command: `esbmc-ai` (shows help)

### Build Arguments

- `ESBMC_VERSION`: ESBMC version to install (default: "latest")
- `EXTRA_PIP_PACKAGES`: Space-separated list of additional pip packages
- `quay_expiration`: Image expiration for Quay.io (default: "4w")

## Container Entrypoint

The `scripts/container/entrypoint.sh` script (lines 1-24):

1. Checks if `ESBMCAI_CONFIG_FILE` is set and exists
2. Parses `[extras.packages]` from config.toml using Python's tomllib
3. Injects extra packages into esbmc-ai environment via `pipx inject` (idempotent)
4. Executes the user's command

This allows runtime package injection by mounting a config file:

```sh
podman run --rm \
  --env ESBMCAI_CONFIG_FILE=/config/config.toml \
  -v ./config.toml:/config/config.toml:z \
  esbmc-ai:latest \
  fix-code file.c
```

## Working Directory

The container uses `/workspace` as the default working directory (line 112). Mount your source code here:

```sh
podman run --rm -v my-src-folder:/workspace:z -e OPENAI_API_KEY esbmc-ai:latest fix-code file.c
```

## Why Multi-Stage Build?

The multi-stage approach reduces final image size by:
- Excluding Hatch and build tools from runtime image
- Only copying the built wheel, not source code
- Keeping build artifacts in the builder stage (marked safe-to-remove)

Runtime image contains only: ESBMC, Python, pipx, esbmc-ai wheel, and minimal C/C++ headers.
