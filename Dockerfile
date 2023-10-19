# Use a base image with Python and Tkinter pre-installed
FROM python:latest

# Set the working directory in the container
WORKDIR /zones

# Copy your Python script and other necessary files
COPY ./zones.py ./
COPY . .

# Install required packages
RUN apt-get update && \
    apt-get install -y default-libmysqlclient-dev && \
    pip install mysqlclient && \
    apt-get install -y mysql-server xvfb x11-xkb-utils xfonts-100dpi xfonts-75dpi xfonts-scalable xfonts-cyrillic x11-apps firefox && \
    apt-get clean

# Set up Xvfb
ENV DISPLAY=:99

# Run Xvfb and your Python script in the background
CMD Xvfb :99 -screen 0 1024x768x16 & service mysql start & python ./zones.py
