FROM nvidia/cuda:12.9.1-devel-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# Added ninja-build for faster builds
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    curl \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libglvnd-dev \
    libgl1-mesa-glx \
    libegl1-mesa \
    freeglut3-dev \
    zlib1g-dev \
    x11-apps \
    cmake \
    xvfb \
    build-essential \
    libx11-dev \
    libxcursor-dev \
    libxi-dev \
    libxinerama-dev \
    libxrandr-dev \
    libxss-dev \
    libxxf86vm-dev \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libfreetype6-dev \
    libportmidi-dev \
    libjpeg-dev \
    ninja-build \
    ffmpeg

# Clean up
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Bash as the default shell
SHELL ["/bin/bash", "-c"]
# Install Python 3.10
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.10 python3.10-dev python3.10-distutils && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    update-alternatives --set python3 /usr/bin/python3.10

# Install pip for Python 3.10
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10

# Install Habitat-Sim
RUN git clone https://github.com/facebookresearch/habitat-sim.git
WORKDIR /habitat-sim

# Patch dependencies.cmake to force MAGNUM_TARGET_EGL to OFF
# This ensures that when we build in Headless mode, it picks GLX instead of EGL
RUN sed -i 's/set(MAGNUM_TARGET_EGL .*/set(MAGNUM_TARGET_EGL OFF CACHE BOOL "" FORCE)/' src/cmake/dependencies.cmake

# Build with TARGET_HEADLESS=ON (Default).
# Since EGL is disabled above, this forces the build to use Windowless GLX.
RUN CMAKE_ARGS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DTARGET_HEADLESS=ON" pip install . -v

# Install Habitat-Lab
WORKDIR /
RUN git clone https://github.com/facebookresearch/habitat-lab.git
WORKDIR /habitat-lab
RUN pip install -e habitat-lab
RUN pip install pybullet==3.0.4 pygame==2.1.2


WORKDIR /app
CMD ["/bin/bash"]