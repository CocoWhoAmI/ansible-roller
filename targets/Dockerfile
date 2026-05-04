FROM ubuntu:22.04

ARG TARGET_USER
ARG TARGET_PASSWORD

RUN apt-get update && apt-get install -y openssh-server python3 sudo

RUN test -n "$TARGET_USER" && test -n "$TARGET_PASSWORD" \
    && useradd -m -s /bin/bash "$TARGET_USER" \
    && echo "$TARGET_USER:$TARGET_PASSWORD" | chpasswd \
    && usermod -aG sudo "$TARGET_USER" \
    && echo "$TARGET_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$TARGET_USER"

RUN mkdir /run/sshd

CMD ["/usr/sbin/sshd", "-D"]