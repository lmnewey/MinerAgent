# Use an official Python runtime as a parent image
#FROM python:3.8-slim
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Set environment variables to avoid any interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Add the deadsnakes repository
RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa

# Update package list and install Python 3.8
RUN apt-get update && apt-get install -y python3.8 python3.8-dev python3.8-venv python3-pip
RUN apt install -y net-tools
# Set up a working directory
WORKDIR /app
# Copy the current directory contents into the container at /app
COPY nbminer.sha256 /app
COPY nbminer /app
COPY app.py /app
COPY supervisor.py /app

RUN chmod +x /app/app.py
RUN chmod +x /app/supervisor.py
# Install any needed packages specified in requirements.txt
RUN pip install paho-mqtt
RUN pip install psutil
RUN pip install docker


# Run app.py when the container launches
CMD ["./app/app.py"]