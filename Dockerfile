FROM ubuntu:jammy

# Linux user ID
ARG UID=1000
ENV USER="ubuntu"

RUN apt update && \
    apt install -y \
        python3-pip 

RUN useradd -u ${UID} -ms /bin/bash ${USER} \
    && echo "${USER}:${USER}" | chpasswd \
    && adduser ${USER} sudo \
    && echo "ubuntu ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
