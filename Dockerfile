FROM ubuntu:jammy

ARG USER
ARG UID

ENV USER=${USER}
ENV UID=${UID}
ENV GUID=${UID}


# For some reason, new Ubuntu containers create this user by default
# and it's goofing all of my stuff up...
# RUN userdel -r ubuntu

# Add user w/ sudo privileges; helps to resolve annoyances
# with building/modifying files inside and outside of container
RUN groupadd --gid ${GUID} ${USER} \
    && useradd --uid ${UID} --gid ${GUID} -ms /bin/bash -m ${USER} \
    && adduser ${USER} sudo \
    && echo "${USER} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

RUN apt update && \
    apt install -y \
        python3-pip \
        freeglut3-dev \
        libosmesa6-dev
