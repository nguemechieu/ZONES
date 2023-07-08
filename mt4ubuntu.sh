#!/bin/bash

# Copyright 2022, MetaQuotes Ltd.
# MetaTrader download url
URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt4/mt4oldsetup.exe"
#https://download.mql5.com/cdn/web/metaquotes.software.corp/mt4/mt4ubuntu.sh
# Wine version to install: stable or devel
WINE_VERSION="stable"

# Prepare: switch to 32 bit and add Wine key
dpkg --add-architecture i386
wget -nc https://dl.winehq.org/wine-builds/winehq.key
mv winehq.key /usr/share/keyrings/winehq-archive.key

# Get Ubuntu version and trim to major only
OS_VER=$(lsb_release -r |cut -f2 |cut -d "." -f1)
# Choose repository based on Ubuntu version
# shellcheck disable=SC2004
if (( $OS_VER >= 22)); then
  wget -nc https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources
   mv winehq-jammy.sources /etc/apt/sources.list.d/
elif (( $OS_VER < 22 )) && (( $OS_VER >= 21 )); then
  wget -nc https://dl.winehq.org/wine-builds/ubuntu/dists/impish/winehq-impish.sources
   mv winehq-impish.sources /etc/apt/sources.list.d/
elif (( $OS_VER < 21 )) && (( $OS_VER >=20 )); then
  wget -nc https://dl.winehq.org/wine-builds/ubuntu/dists/focal/winehq-focal.sources
  mv winehq-focal.sources /etc/apt/sources.list.d/
elif (( $OS_VER < 20 )); then
  wget -nc https://dl.winehq.org/wine-builds/ubuntu/dists/bionic/winehq-bionic.sources
   mv winehq-bionic.sources /etc/apt/sources.list.d/
fi

# Update package and install Wine
apt update
apt upgrade -y
apt install --install-recommends winehq-$WINE_VERSION

# Download MetaTrader
wget $URL -O mt4setup.exe

# Set environment to Windows 10
WINEPREFIX=~/.mt4 WINEARCH=win32 winecfg -v=win10
# Start MetaTrader installer in 32 bit environment
WINEPREFIX=~/.mt4 WINEARCH=win32 wine mt4setup.exe
