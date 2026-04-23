# Use a base image with Python and Tkinter pre-installed
FROM python:latest

# Set the working directory in the container
WORKDIR /zones

# Copy the Python script and other necessary files
COPY  zones.py ./
COPY . .



# Expose port for the web server (assuming your Python script serves on port 80)
EXPOSE 8787

# Run the Python script and start a simple web server
CMD ["python", "zones.py"]

