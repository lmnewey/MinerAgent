#!/usr/bin/env python3

import os
import time
import threading
import paho.mqtt.client as mqtt
import json
from io import StringIO
import sys

import psutil
import subprocess
import multiprocessing
import socket
import platform

# Define your default values or get parameters from environment variables
DEFAULT_MQTT_BROKER_HOST = "mqtt.newey.id.au"
DEFAULT_MQTT_BROKER_PORT = 1883
DEFAULT_MINER_LOCATION = "/app/nbminer"
DEFAULT_MINER_ALGO = "kapow"
DEFAULT_MINER_RIGID = "NeweyMining.Co"

MQTT_BROKER_HOST = os.environ.get("MQTTBroker", DEFAULT_MQTT_BROKER_HOST)
MQTT_BROKER_PORT = int(os.environ.get("MQTTBrokerPort", DEFAULT_MQTT_BROKER_PORT))
MINER_LOCATION = os.environ.get("MINER_LOCATION", DEFAULT_MINER_LOCATION)
MINER_ALGO = os.environ.get("MINER_ALGO", DEFAULT_MINER_ALGO)
MINER_RIGID = os.environ.get("MINER_RIGID", DEFAULT_MINER_RIGID)
       

# Simulated unique ID for the worker
UNIQUE_ID = os.environ.get("UNIQUE_ID", MINER_RIGID)
# Create an instance of the MQTT client
client = mqtt.Client()


# Global variable to hold the application thread
app_thread = None

# Shared flag to signal the application to stop
stop_application = threading.Event()

def get_gpu_info():
    gpu_info = {}

    try:
        # Run the nvidia-smi command to get GPU information
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,power.draw,memory.used", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, text=True, check=True
        )

        # Split the output by lines and extract GPU model, usage, power consumption, and memory usage
        gpu_info_lines = result.stdout.strip().split('\n')
        for idx, line in enumerate(gpu_info_lines):
            model, usage, power, memory = line.split(',')
            gpu_info[idx] = {
                "model": model.strip(),
                "usage": float(usage.strip()),
                "power": float(power.strip()),
                "memory_usage": int(memory.strip())
            }
        #print(gpu_info)
        return gpu_info

    except subprocess.CalledProcessError as e:
        print("Error running nvidia-smi:", e)
        return None
def send_status(client):
    global UNIQUE_ID
    global output_history
     # Create a new MQTT client instance
    status_client = mqtt.Client()

    # Connect to the MQTT broker
    status_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)

    while True:
        gpu = get_gpu_info()

        # Get network information
        network_info = []
        for iface, addrs in psutil.net_if_addrs().items():
            iface_info = {"name": iface, "addresses": []}
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    iface_info["addresses"].append(addr.address)
            network_info.append(iface_info)

        # Define the process name (fallback if not provided as environment variable)
        process_name = "nbminer"

        hardware_info = {
            "unique_id": UNIQUE_ID,
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "cpu_usage": psutil.cpu_percent(interval=1),
            "gpu": gpu,
            "network": network_info,
            "Miner Process State": get_process_state(process_name)
        }

        # Send the status to MQTT
        status_client.publish("worker/"+ MINER_RIGID + "/status", json.dumps(hardware_info), qos=1)

         # Send userdata status to "miner/minerid/process_status" topic
        #client.publish("miner/minerid/process_status", json.dumps(client.user_data), qos=1)
        
        client.publish("worker/"+ MINER_RIGID +"/process_status", json.dumps(output_history), qos=1)

        # Sleep for 2 seconds before sending the next status

def register_worker():
    global UNIQUE_ID
    announcement = {
        "unique_id": UNIQUE_ID,
        "status": "online"
    }
    topic = "worker/"+UNIQUE_ID+"/ANNOUNCE"
    client.publish(topic, json.dumps(announcement))

def announce_worker():        
    topic = f"worker/{UNIQUE_ID}/status"       
    global app_thread
    if app_thread is not None and app_thread.is_alive():
        topic = f"worker/{UNIQUE_ID}/status/state"
        running_state = { "state": "running"} #json.dumps(running_state)
        client.publish(topic, json.dumps(running_state))
    else:
        topic = f"worker/{UNIQUE_ID}/status/state"
        running_state = { "state": "idle"} #json.dumps(running_state)
        client.publish(topic, json.dumps(running_state))

def terminate_program():
    global app_thread
    if app_thread is not None and app_thread.is_alive():
        print("Terminating the application thread...")
        # You can add any additional logic needed to properly terminate the application
        # For example, sending termination signals to the application
        app_thread.join()  # Wait for the thread to finish
    print("Exiting the program...")
    client.disconnect()
    sys.exit(0)

# Define the on_connect function
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        # Subscribe to the "worker/unique_id/kill" and "worker/unique_id/command" topics
        client.subscribe(f"worker/{UNIQUE_ID}/kill")
        client.subscribe(f"worker/{UNIQUE_ID}/command")
        running_state = { "state": "starting"} 
        topic = f"worker/{UNIQUE_ID}/status"
        client.publish(topic, json.dumps(running_state))
    else:
        print(f"Connection to MQTT broker failed with code {rc}")

# Define the on_message function
def on_message(client, userdata, message):
    global stop_application
    if message.topic == "worker/UNIQUE_ID/stop":
        print("Received stop command. Stopping the application...")
        stop_application.set()  # Set the flag to stop the application

    if message.topic == f"worker/{UNIQUE_ID}/kill":
        print("Received kill message. Terminating...")
        # You can add logic here to gracefully terminate your application
        # Disconnect MQTT client
        client.disconnect()
        # Exit the script
    if message.topic == f"worker/{UNIQUE_ID}/command":
        print("Received command message. Working...")
        # You can add logic here to gracefully terminate your application
        # Disconnect MQTT client
        on_command_message(client, userdata, message)
        # Exit the script

# Function to redirect stdout to the output buffer
def redirect_stdout():
    sys.stdout = output_buffer

# Function to restore the original stdout
def restore_stdout():
    sys.stdout = sys.__stdout__

def publish_output(output):
    topic = f"workerNode/{MINER_RIGID}/Process"
    client.publish(topic, output)

# Function to publish the accumulated buffer content to MQTT
def publish_buffer():
    buffer_content = output_buffer.getvalue()
    if buffer_content:
        publish_output(buffer_content)
        output_buffer.seek(0)
        output_buffer.truncate()

# Thread for running the application
def application_thread(wallet, rig, URL, algorithm):
    app_command = f"{MINER_LOCATION} -a {algorithm} -o {URL} -u {wallet}.{rig}"
    redirect_stdout()  # Redirect stdout to the buffer
    app_process = subprocess.Popen(app_command, shell=True)
    app_pid = app_process.pid+1  # Get the PID of the started application
    client.publish(f"worker/{UNIQUE_ID}/supervisor/app_pid", str(app_pid))  # Publish the PID to MQTT
    
    while not stop_application.is_set():
        pass  # Continue running the application
        
    app_process.terminate()  # Terminate the application process
    app_process.wait()  # Wait for the application process to finish
    restore_stdout()  # Restore the original stdout
    client.publish(f"worker/{UNIQUE_ID}/supervisor/app_pid", "None")  # Publish "None"

# def application_thread(wallet, rig, URL, algorithm):
#     app_command = f"{MINER_LOCATION} -a {algorithm} -o {URL} -u {wallet}.{rig}"
#     redirect_stdout()  # Redirect stdout to the buffer
#     app_process = subprocess.Popen(app_command, shell=True)
#     app_pid = app_process.pid  # Get the PID of the started application
#     client.publish(f"worker/{UNIQUE_ID}/app_pid", str(app_pid))  # Publish the PID to MQTT
#     app_process.wait()  # Wait for the application process to finish
#     restore_stdout()  # Restore the original stdout
#     client.publish(f"worker/{UNIQUE_ID}/app_pid", "None")  # Publish "None"
#     # app_command = f"{MINER_LOCATION} -a {algorithm} -o {URL} -u {wallet}.{rig}"
#     # redirect_stdout()  # Redirect stdout to the buffer
#     # os.system(app_command)  # Run the modified application command
#     # restore_stdout()  # Restore the original stdout

# Function to handle messages on the "worker/{unique-id}/command" topic
def on_command_message(client, userdata, message):
    global app_thread  # Reference the global app_thread variable
    if message.topic == f"worker/{UNIQUE_ID}/command":
        payload = json.loads(message.payload.decode('utf-8'))
        state = payload["state"]
        if state == "run":
            wallet = payload["wallet"]
            rig = payload["rig"]
            URL = payload["URL"]
            algorithm = payload["algorithm"]

            # Check if an app_thread is already running
            if app_thread is None or not app_thread.is_alive():
                app_thread = threading.Thread(target=application_thread, args=(wallet, rig, URL, algorithm))
                app_thread.start()

# Assign the defined functions to the MQTT client
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

# Create the output buffer
output_buffer = StringIO()

# Start the MQTT client's event loop
client.loop_start()

# Replace 'your_script_name.py' with the actual name of your Python script
supervisor_name = 'supervisor.py'

# Use the subprocess module to start the script in the background
subprocess.Popen(['nohup', 'python3', supervisor_name, '&'])
register_worker()
while True:
    try:
        publish_buffer()
        announce_worker()
        time.sleep(1)  # Adjust the interval as needed
    except KeyboardInterrupt:
        running_state = { "state": "starting"} 
        topic = f"worker/{UNIQUE_ID}/status"
        terminate_program()