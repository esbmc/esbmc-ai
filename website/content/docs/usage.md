---
title: Usage
type: docs
weight: 2
prev: /docs/initial-setup
next: /docs/configuring-esbmc-ai
---

This guide covers how to run ESBMC-AI both locally and in containers.

## Local Usage

After [installing ESBMC-AI](/docs/initial-setup), run commands using:

```sh
# With pip/pipx installation
esbmc-ai <command> [options]

# With hatch (for development)
hatch run esbmc-ai <command> [options]
```

### Examples

```sh
# Fix code
esbmc-ai fix-code path/to/file.c

# Get help
esbmc-ai --help
```

### API Keys

Set your AI provider API key before running commands:

```sh
# In .env file (recommended)
ANTHROPIC_API_KEY=your-key  # Or OPENAI_API_KEY / GOOGLE_API_KEY

# Or export directly
export ANTHROPIC_API_KEY="your-key"
```

For command details and options, see [Commands](/docs/commands) and [Configuration](/docs/configuring-esbmc-ai).

## Container Usage

Run ESBMC-AI in an isolated container environment with all dependencies pre-installed.

> [!NOTE]
> Podman users should add `:z` to volume mounts for SELinux compatibility. Docker users can omit `:z`.

### Building the Container

```sh
# Using Podman (or replace with 'docker-build' for Docker)
hatch run podman-build

# With extra packages and specific ESBMC version
hatch run podman-build "langchain-google-genai" "v7.4"
```

This creates images tagged as `esbmc-ai:latest`, `esbmc-ai:<version>`, and `esbmc-ai:<git-commit>`.

### Running Commands

The container automatically sets sensible defaults (ESBMC path, output directory, AI model) based on your environment. All defaults can be overridden with command-line arguments.

```sh
# Basic usage (replace 'podman' with 'docker' if using Docker)
podman run --rm \
  --env-file .env \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  fix-code /workspace/file.c
# Output saved to: ./samples/output/
```

```sh
# With API key directly
podman run --rm \
  --env ANTHROPIC_API_KEY="your-key" \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  fix-code /workspace/file.c
```

```sh
# With configuration file
podman run --rm \
  --env ESBMCAI_CONFIG_FILE=/config/config.toml \
  --env-file .env \
  -v ./config.toml:/config/config.toml:z \
  -v ./samples:/workspace:z \
  esbmc-ai:latest \
  fix-code /workspace/file.c
```

```sh
# Interactive shell
podman run --rm -it \
  --env-file .env \
  -v ./samples:/workspace:z \
  --entrypoint /bin/bash \
  esbmc-ai:latest
```

For available commands, options, and addon configuration, see:
- [Commands](/docs/commands) - Available commands and their usage
- [Configuration](/docs/configuring-esbmc-ai) - All configuration options
- [Addons](/docs/addons) - Extending ESBMC-AI with addons

## Troubleshooting

- **ESBMC not found (local):** Install ESBMC and set `--verifier.esbmc.path` in your config
- **Permission errors (Podman):** Add `:z` to volume mounts
- **API key errors:** Verify the correct environment variable is set (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`)

For more help, see [Configuration](/docs/configuring-esbmc-ai).
