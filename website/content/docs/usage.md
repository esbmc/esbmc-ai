---
title: Usage
type: docs
weight: 2
prev: /docs/initial-setup
next: /docs/configuring-esbmc-ai
---

This guide covers how to use ESBMC-AI both as a locally installed tool and as a container.

## Local Usage

After [installing ESBMC-AI](/docs/initial-setup), run commands using:

```sh
# With pip/pipx installation
esbmc-ai <command> [options]

# With hatch (for development)
hatch run esbmc-ai <command> [options]
```

### Common Commands

```sh
# Fix code issues
esbmc-ai fix-code path/to/file.c

# Optimize code
esbmc-ai optimize-code path/to/file.c

# Interactive chat about code
esbmc-ai user-chat path/to/file.c

# View help
esbmc-ai --help
esbmc-ai help-config
```

### Setting Up API Keys

Set your AI provider API key using one of these methods:

**Option 1: .env file** (recommended)

```sh
# .env
ANTHROPIC_API_KEY=your-key  # Or OPENAI_API_KEY or GOOGLE_API_KEY
```

**Option 2: Export environment variable**

```sh
export ANTHROPIC_API_KEY="your-key"  # Or OPENAI_API_KEY / GOOGLE_API_KEY
```

## Container Usage

Run ESBMC-AI in an isolated container environment with all dependencies pre-installed.

### Building the Container

```sh
# Using Podman (or replace with 'docker-build' for Docker)
hatch run podman-build

# With extra packages and specific ESBMC version
hatch run podman-build "langchain-google-genai" "v7.4"
```

This creates images tagged as `esbmc-ai:latest`, `esbmc-ai:<version>`, and `esbmc-ai:<git-commit>`.

### Running Commands

**Basic example:**

```sh
# Replace 'podman' with 'docker' if using Docker
# Docker users: remove :z from volume mounts
podman run --rm \
  --env-file .env \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  esbmc-ai fix-code /workspace/file.c \
    --ai_model.ai_model claude-3-5-sonnet-20241022 \
    --verifier.esbmc.path /bin/esbmc
```

**Alternative: Pass API key directly**

```sh
podman run --rm \
  --env ANTHROPIC_API_KEY="your-key" \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  esbmc-ai fix-code /workspace/file.c
```

**With configuration file:**

```sh
podman run --rm \
  --env ESBMCAI_CONFIG_FILE=/config/config.toml \
  --env-file .env \
  -v ./config.toml:/config/config.toml:z \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  esbmc-ai fix-code /workspace/file.c
```

**Interactive shell:**

```sh
podman run --rm -it \
  --env-file .env \
  -v ./samples:/workspace:z \
  --entrypoint /bin/bash \
  esbmc-ai:latest
```

> [!NOTE]
> Podman users should add `:z` to volume mounts for SELinux compatibility.

## Common Options

```sh
# AI Model Selection
--ai_model.ai_model claude-3-5-sonnet-20241022  # Or gpt-4, gemini-pro, etc.

# ESBMC Configuration
--verifier.esbmc.path /path/to/esbmc            # ESBMC binary location (required in containers)
--verifier.esbmc.params "--context-bound 2"     # Additional ESBMC flags
--verifier.esbmc.timeout 300                    # Timeout in seconds

# Output and Logging
--solution.output_dir /path/to/output           # Save repaired code
--generate_patches                              # Create patch files
-v                                              # Verbose logging
--json                                          # JSON output format
```

## Using Addons

Addons extend ESBMC-AI with additional commands and verifiers. To use addons, specify them in your `config.toml`:

```toml
# config.toml
addon_modules = [
    "my_addon_package",
    "another_addon.module"
]
```

The addon modules must be installed in your Python environment (or via `pipx inject` if using pipx):

```sh
# Local installation
pip install my-addon-package

# With pipx
pipx inject esbmc-ai my-addon-package

# In container (at build time)
hatch run podman-build "my-addon-package"
```

Once loaded, addon commands appear alongside built-in commands:

```sh
# List all available commands (including addons)
esbmc-ai --help

# Run an addon command
esbmc-ai custom-command file.c
```

For available addons, see the [Addons page](/docs/addons).

## Troubleshooting

**ESBMC not found (local):** Install ESBMC and set the path in your config file or via `--verifier.esbmc.path`.

**ESBMC not found (container):** Always specify `--verifier.esbmc.path /bin/esbmc` when using the container.

**Permission errors (Podman):** Use `:z` suffix on volume mounts: `-v ./samples:/workspace:z`

**API key errors:** Ensure the correct environment variable is set for your chosen AI model provider.

For detailed configuration options, see [Configuring ESBMC-AI](/docs/configuring-esbmc-ai).
