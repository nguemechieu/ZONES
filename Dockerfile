# Use a base image with Python and Tkinter pre-installed
FROM python:latest

# Set the working directory in the container
# Set the working directory in the container


WORKDIR ./zones
COPY ./zones.py  ./zones.py
COPY . .
# Install required packages
RUN apt-get update && \
    apt-get install -y default-libmysqlclient-dev && \
    pip install mysqlclient
# Run the Python script
# Copy your Python script and other necessary files

# Install cnhrequired packages
RUN  apt-get install -y mysql-server && \

    apt-get install -y xvfb && \
    apt-get install -y x11-xkb-utils && \
    apt-get install -y xfonts-100dpi xfonts-75dpi xfonts-scalable xfonts-cyrillic && \
    apt-get install -y x11-apps 
    RUN apt update
   RUN apt clean
RUN apt update
 RUN    apt install firefox




# Set up Xvfb
ENV DISPLAY=:99



# Run Xvfb and your Python script in the background
CMD Xvfb :99 -screen 0 1024x768x16 & service mysql start & python ./zones.py
