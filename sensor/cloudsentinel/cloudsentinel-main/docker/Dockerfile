# SPDX-FileCopyrightText: 2021-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

# This Dockerfile contains two CloudSentinel images, `builder` and `runtime`.
# `builder` contains all necessary code to build
# `runtime` is stripped down.

ARG SOURCE_DATE_EPOCH
FROM debian:trixie-slim AS builder

WORKDIR /

ENV CLOUDSENTINEL_GROUP=cloudsentinel \
    CLOUDSENTINEL_USER=cloudsentinel \
    CLOUDSENTINEL_HOME=/cloudsentinel

# Set locale to UTF-8, otherwise upstream libraries have bytes/string conversion issues
ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

RUN groupadd -r ${CLOUDSENTINEL_GROUP} && \
    useradd -r -d ${CLOUDSENTINEL_HOME} -m -g ${CLOUDSENTINEL_GROUP} ${CLOUDSENTINEL_USER}

# Set up Debian prereqs
RUN export DEBIAN_FRONTEND=noninteractive; \
    apt-get -qq update && \
    apt-get -qq install -y \
        -o APT::Install-Suggests=false \
        -o APT::Install-Recommends=false \
        -o Dpkg::Use-Pty="0" \
      build-essential \
      ca-certificates \
      cargo \
      libffi-dev \
      libsnappy-dev \
      libssl-dev \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv \
      rustc && \
    rm -rf /var/lib/apt/lists/*

USER ${CLOUDSENTINEL_USER}
WORKDIR ${CLOUDSENTINEL_HOME}

# Copy requirements first to use Docker caching better
RUN mkdir -p ${CLOUDSENTINEL_HOME}/cloudsentinel-git
COPY --chown=${CLOUDSENTINEL_USER}:${CLOUDSENTINEL_GROUP} requirements.txt requirements-output.txt ${CLOUDSENTINEL_HOME}/cloudsentinel-git/

RUN python3 -m venv cloudsentinel-env && \
    . cloudsentinel-env/bin/activate && \
    pip install -q --no-cache-dir --upgrade pip setuptools wheel && \
    pip install -q --no-cache-dir --upgrade cffi && \
    pip install -q --no-cache-dir --upgrade -r ${CLOUDSENTINEL_HOME}/cloudsentinel-git/requirements.txt && \
    pip install -q --no-cache-dir --upgrade -r ${CLOUDSENTINEL_HOME}/cloudsentinel-git/requirements-output.txt

COPY --chown=${CLOUDSENTINEL_USER}:${CLOUDSENTINEL_GROUP} . ${CLOUDSENTINEL_HOME}/cloudsentinel-git

# RUN . cloudsentinel-env/bin/activate && \
#     pip install -e ${CLOUDSENTINEL_HOME}/cloudsentinel-git

FROM gcr.io/distroless/python3-debian13:latest AS runtime
#FROM gcr.io/distroless/python3-debian13:debug AS runtime

LABEL org.opencontainers.image.authors="Michel Oosterhof <michel@oosterhof.net>"
LABEL org.opencontainers.image.url="https://cloudsentinel.local/"
LABEL org.opencontainers.image.documentation="https://cloudsentinel.local/docs"
LABEL org.opencontainers.image.source="https://cloudsentinel.local/source"
LABEL org.opencontainers.image.revision="Source control revision identifier for the packaged software."
LABEL org.opencontainers.image.vendor="CloudSentinel"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"
LABEL org.opencontainers.image.title="CloudSentinel SSH/Telnet Defense Sensor"
LABEL org.opencontainers.image.description="CloudSentinel active deception and SOAR sensor"
#LABEL org.opencontainers.image.base.digest="7beb0248fd81"
LABEL org.opencontainers.image.base.name="gcr.io/distroless/python3-debian13"

ENV CLOUDSENTINEL_GROUP=cloudsentinel \
    CLOUDSENTINEL_USER=cloudsentinel \
    CLOUDSENTINEL_HOME=/cloudsentinel

#RUN groupadd -r ${CLOUDSENTINEL_GROUP} && \
#    useradd -r -d ${CLOUDSENTINEL_HOME} -m -g ${CLOUDSENTINEL_GROUP} ${CLOUDSENTINEL_USER}
COPY --from=builder --chown=0:0 /etc/passwd /etc/group /etc/

#RUN export DEBIAN_FRONTEND=noninteractive; \
#    apt-get update && \
#    apt-get install -y \
#        -o APT::Install-Suggests=false \
#        -o APT::Install-Recommends=false \
#        -o Dpkg::Use-Pty="0" \
#      libssl1.1 \
#      ca-certificates \
#      libffi7 \
#      procps \
#      python3 \
#      python3-distutils && \
#    rm -rf /var/lib/apt/lists/* && \
#    ln -s /usr/bin/python3 /usr/local/bin/python

COPY --from=builder --chown=${CLOUDSENTINEL_USER}:${CLOUDSENTINEL_GROUP} ${CLOUDSENTINEL_HOME} ${CLOUDSENTINEL_HOME}

RUN [ "python3", "-m", "compileall", "-q", "/cloudsentinel/cloudsentinel-git/src", "/cloudsentinel/cloudsentinel-env/", "/usr/lib/python3.13"]

VOLUME [ "/cloudsentinel/cloudsentinel-git/var", "/cloudsentinel/cloudsentinel-git/etc" ]

USER ${CLOUDSENTINEL_USER}
WORKDIR ${CLOUDSENTINEL_HOME}/cloudsentinel-git

ENV PATH=${CLOUDSENTINEL_HOME}/cloudsentinel-env/bin:${PATH}
ENV PYTHONPATH=${CLOUDSENTINEL_HOME}/cloudsentinel-git/src
ENV PYTHONUNBUFFERED=1

RUN [ "python3", "/cloudsentinel/cloudsentinel-git/bin/regen-dropin.cache" ]

EXPOSE 2222 2223

ENTRYPOINT [ "/cloudsentinel/cloudsentinel-env/bin/python3" ]
CMD [ "/cloudsentinel/cloudsentinel-env/bin/twistd", "-n", "--umask=0022", "--pidfile=", "cloudsentinel" ]
