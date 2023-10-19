# Use Ubuntu as the base image
FROM ubuntu:latest

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Update package list and install necessary dependencies
RUN apt-get update -y && \
    apt-get install -y python3-pip firefox xvfb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Flask and Selenium
RUN pip3 install flask selenium

# Copy your Python app into the container
COPY ./ZONES /ZONES

# Set up display for running Firefox headlessly
ENV DISPLAY=:99

# Start Xvfb and run the Flask app
CMD Xvfb :99 -screen 0 1024x768x16 & python3 /ZONES/zones.py
