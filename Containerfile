FROM docker.io/library/ubuntu:25.10

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core system utilities and development libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python-is-python3 \
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


# Install ESBMC-AI
ARG ESBMCAI_WHEEL
COPY ${ESBMCAI_WHEEL} /tmp/esbmc_ai.whl

# Install ESBMC-AI using pipx from the copied wheel
RUN pipx install /tmp/esbmc_ai.whl \
    && rm /tmp/esbmc_ai.whl # Clean up the copied wheel after installation

# Accept build-time extra pip packages (pass --build-arg EXTRA_PIP_PACKAGES="pkg1 pkg2" if needed)
ARG EXTRA_PIP_PACKAGES=""
# Inject any additional pip packages into the esbmc-ai environment
RUN if [ -n "$EXTRA_PIP_PACKAGES" ]; then pipx inject esbmc-ai $EXTRA_PIP_PACKAGES; fi

# Declare environment variables to be set at runtime
ENV ESBMCAI_CONFIG_FILE=""
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV GOOGLE_API_KEY=""

# Set working directory inside the container
WORKDIR /workspace

# Launch into bash by default
CMD ["bash"]