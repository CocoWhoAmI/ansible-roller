FROM ubuntu:22.04

RUN apt-get update && apt-get install -y openssh-server python3 sudo

RUN useradd -m -s /bin/bash ansible \
    && echo "ansible:ansible" | chpasswd \
    && usermod -aG sudo ansible \
    && echo "ansible ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ansible

RUN mkdir /run/sshd

CMD ["/usr/sbin/sshd", "-D"]