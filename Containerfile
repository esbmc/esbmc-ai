FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core system utilities and development libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python-is-python3 \
        python3-pip \
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

# Accept build-time extra pip packages (pass --build-arg EXTRA_PIP_PACKAGES="pkg1 pkg2" if needed)

ARG EXTRA_PIP_PACKAGES=""

# Install ESBMC-AI and any additional pip packages
RUN pip3 install --no-cache-dir esbmc-ai
RUN if [ -n "$EXTRA_PIP_PACKAGES" ]; then pip3 install --no-cache-dir $EXTRA_PIP_PACKAGES; fi

# Declare environment variables to be set at runtime
ENV ESBMCAI_CONFIG_FILE=""
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV GOOGLE_API_KEY=""

# Set working directory inside the container
WORKDIR /workspace

# Launch into bash by default
CMD ["bash"]
