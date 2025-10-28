# Multi-stage container build for ESBMC-AI on Ubuntu 24.04 LTS
# Builder stage: Compiles ESBMC-AI wheel using hatch
# Main stage: Installs ESBMC, Python 3.12, dependencies (Clang 14, Boost, Z3), and ESBMC-AI via pipx
#
# Build args: ESBMC_VERSION (default: "latest"), EXTRA_PIP_PACKAGES (optional build-time packages)
# Runtime: Mount config.toml via ESBMCAI_CONFIG_FILE to auto-inject [extras.packages]; set API keys as env vars
# Default CMD: esbmc-ai (override with custom commands)

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

# Label this as the runtime image
LABEL stage="runtime" \
      description="ESBMC-AI runtime image - includes ESBMC, Python, and esbmc-ai tool" \
      maintainer="ESBMC-AI Team"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core system utilities and development libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 python3.12-venv python3-pip \
        pipx \
        git \
        ccache \
        unzip \
        wget \
        curl \
        bison \
        flex \
        g++-multilib \
        linux-libc-dev \
        libboost-all-dev \
        libz3-dev \
        cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Clang/LLVM 14 and related tooling (specific version chosen for compatibility)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        clang-14 \
        llvm-14 \
        clang-tidy-14 \
        libclang-14-dev \
        libclang-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure default clang/clang++ to use version 14
RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-14 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-14 100

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

# Install ESBMC-AI using pipx from the copied wheel
RUN WHEEL=$(ls /tmp/*.whl) \
    && pipx install "$WHEEL" \
    && rm "$WHEEL"

# Accept build-time extra pip packages (pass --build-arg EXTRA_PIP_PACKAGES="pkg1 pkg2" if needed)
ARG EXTRA_PIP_PACKAGES=""
# Inject any additional pip packages into the esbmc-ai environment
RUN if [ -n "$EXTRA_PIP_PACKAGES" ]; then pipx inject esbmc-ai $EXTRA_PIP_PACKAGES; fi

# Copy entrypoint script
COPY scripts/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Declare environment variables to be set at runtime
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV GOOGLE_API_KEY=""

# Set working directory inside the container
WORKDIR /workspace

# Set entrypoint for runtime configuration
ENTRYPOINT ["/entrypoint.sh"]

# Launch into esbmc-ai by default
CMD ["esbmc-ai"]