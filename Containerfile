# Multi-stage container build for ESBMC-AI on Ubuntu 24.04 LTS
# Builder stage: Compiles ESBMC-AI wheel using hatch
# Main stage: Installs ESBMC, Python 3.12, minimal headers for C/C++ parsing, and ESBMC-AI via pipx
#
# Build args: ESBMC_VERSION (default: "latest"), EXTRA_PIP_PACKAGES (optional build-time packages)
# Runtime: Mount config.toml via ESBMCAI_CONFIG_FILE to auto-inject [extras.packages]; set API keys as env vars
# Default CMD: esbmc-ai --help (override with any command, including bash for shell access)

# Builder stage to run hatch build and produce the wheel
FROM docker.io/library/ubuntu:24.04 AS builder

# Label this as an intermediate build stage
LABEL stage="builder" \
      description="ESBMC-AI intermediate build stage - contains hatch and build artifacts" \
      maintainer="ESBMC-AI Team" \
      safe-to-remove="true"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and pipx for isolated tool installation
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 pipx \
    && rm -rf /var/lib/apt/lists/*

# Add pipx binaries to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy the project source code into the builder
COPY . /src

# Set working directory to source
WORKDIR /src

# Install Hatch via pipx and build the project (produces dist/ with wheel)
RUN pipx install hatch && hatch build

# Main stage for the runtime image
FROM docker.io/library/ubuntu:24.04

# Quay.io expiration configuration
ARG quay_expiration=1m

# Label this as the runtime image
LABEL stage="runtime" \
      description="ESBMC-AI runtime image - includes ESBMC, Python, and esbmc-ai tool" \
      maintainer="ESBMC-AI Team" \
      quay.expires-after=${quay_expiration}

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python runtime, essential tools, and minimal C/C++ headers for ESBMC parsing
# Note: ESBMC is statically linked but needs system headers to parse user code
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3-pip \
        pipx \
        git \
        wget \
        unzip \
        curl \
        libc6-dev \
        libstdc++-13-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and install ESBMC
ARG ESBMC_VERSION="latest"
RUN if [ "$ESBMC_VERSION" = "latest" ]; then \
        wget https://github.com/esbmc/esbmc/releases/latest/download/esbmc-linux.zip -O esbmc-linux.zip; \
    else \
        wget https://github.com/esbmc/esbmc/releases/download/"$ESBMC_VERSION"/esbmc-linux.zip -O esbmc-linux.zip; \
    fi \
    && unzip esbmc-linux.zip -d esbmc-linux \
    && mv esbmc-linux/bin/esbmc /bin/esbmc \
    && rm -rf esbmc-linux esbmc-linux.zip \
    && chmod +x /bin/esbmc

# Add pipx binaries to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy the built wheel from the builder stage
COPY --from=builder /src/dist/*.whl /tmp/

# Install ESBMC-AI using pipx from the copied wheel with CPU-only torch
RUN WHEEL=$(ls /tmp/*.whl) \
    && pipx install "$WHEEL" --pip-args='--extra-index-url https://download.pytorch.org/whl/cpu' \
    && rm "$WHEEL" \
    && rm -rf /root/.cache/pip

# Accept build-time extra pip packages (pass --build-arg EXTRA_PIP_PACKAGES="pkg1 pkg2" if needed)
ARG EXTRA_PIP_PACKAGES=""
# Inject any additional pip packages into the esbmc-ai environment and clean pip cache
RUN if [ -n "$EXTRA_PIP_PACKAGES" ]; then \
        pipx inject esbmc-ai $EXTRA_PIP_PACKAGES && rm -rf /root/.cache/pip; \
    fi

# Copy entrypoint script
COPY scripts/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set container-specific defaults via environment variables
ENV ESBMCAI_VERIFIER__ESBMC__PATH=/bin/esbmc

# Declare API key environment variables to be set at runtime
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV GOOGLE_API_KEY=""

# Set working directory inside the container
WORKDIR /workspace

# Set entrypoint for runtime configuration (handles package injection)
ENTRYPOINT ["/entrypoint.sh"]

# Default command: show help (users can override with any command)
CMD ["esbmc-ai"]