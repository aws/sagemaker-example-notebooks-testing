FROM public.ecr.aws/lts/ubuntu:20.04

# disable prompts during package installation
ARG DEBIAN_FRONTEND=noninteractive

# install system dependencies
RUN apt-get update \
    && apt-get -y install \
        apt-transport-https \
        build-essential \
        ca-certificates \
        curl \
        default-jdk \
        git \
        jq \
        make \
        openssh-server \
        pigz \
        libbz2-dev \
        libffi-dev \
        liblzma-dev \
        libncurses5-dev \
        libreadline-dev \
        libssl-dev \
        libsqlite3-dev \
        libxml2-dev \
        libxmlsec1-dev \
        llvm \
        software-properties-common \
        tk-dev \
        unzip \
        wget \
        xz-utils \
        zlib1g-dev \
    && mkdir -p /var/run/sshd

# install multiple versions of Python using pyenv
ENV PYENV_ROOT /.pyenv
ENV PATH /.pyenv/bin:/.pyenv/shims:$PATH
RUN curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash \
    && pyenv install 3.8.8 \
    && pyenv global $(pyenv versions --bare) \
    && pyenv rehash

# install Python packages -- ubuntu:18.04 system Python is 3.6, ubuntu:20.04 is 3.8
RUN pip3 install -U pip boto3 awscli requests tox twine fabric

# install Node.js and npm
RUN curl -sL https://deb.nodesource.com/setup_12.x | bash - \
    && apt-get install -y nodejs

# install Node packages
RUN npm install -g jshint

# install Docker Compose
RUN (curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -) \
    && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable" \
    && apt-get update \
    && apt-get -y install docker-ce \
    && curl -L "https://github.com/docker/compose/releases/download/1.23.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# clean up APT
RUN rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# copy files
COPY etc/ssh_config /root/.ssh/config
COPY scripts/* /usr/local/bin/
COPY python/dist/sagemakerci*.tar.gz /tmp

# install sagemakerci
RUN pip3 install /tmp/sagemakerci*.tar.gz && rm /tmp/sagemakerci*.tar.gz

# set environment variables
ENV IS_CODEBUILD_IMAGE=true
