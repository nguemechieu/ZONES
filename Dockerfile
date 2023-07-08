FROM ubuntu:latest

RUN apt-get update
RUN  apt install -y wget
RUN apt-get install -y  apt-utils
RUN wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources