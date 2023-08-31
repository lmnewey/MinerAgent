#!/usr/bin/env python3
#import subprocess
import paho.mqtt.client as mqtt
import os
import signal
import time
import psutil
import json
import docker
import subprocess
import platform


DEFAULT_MQTT_BROKER_HOST = "192.168.1.210"
DEFAULT_MQTT_BROKER_PORT = 1883
DEFAULT_MINER_LOCATION = "/app/nbminer"
DEFAULT_MINER_ALGO = "kapow"
DEFAULT_MINER_RIGID = "NeweyMining.Co"

MQTT_BROKER_HOST = os.environ.get("MQTTBroker", DEFAULT_MQTT_BROKER_HOST)
MQTT_BROKER_PORT = int(os.environ.get("MQTTBrokerPort", DEFAULT_MQTT_BROKER_PORT))
MINER_LOCATION = os.environ.get("MINER_LOCATION", DEFAULT_MINER_LOCATION)
MINER_ALGO = os.environ.get("MINER_ALGO", DEFAULT_MINER_ALGO)
MINER_RIGID= os.environ.get("MINER_RIGID", DEFAULT_MINER_RIGID)

MQTT_BROKER_HOST = os.environ.get("MQTTBroker", DEFAULT_MQTT_BROKER_HOST)
MQTT_BROKER_PORT = int(os.environ.get("MQTTBrokerPort", DEFAULT_MQTT_BROKER_PORT))
UNIQUE_ID = os.environ.get("MINER_RIGID", DEFAULT_MINER_RIGID)

# Create an instance of the MQTT client
client = mqtt.Client()

# Global variable to store the process ID
app_pid = None
process_name = None

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
        return json.dumps(gpu_info)

    except subprocess.CalledProcessError as e:
        print("Error running nvidia-smi:", e)
        return None
    
def restart_container(container_name):
    client = docker.from_env()
    container = client.containers.get(container_name)
    
    if container:
        container.restart()
        print(f"Container '{container_name}' restarted.")
    else:
        print(f"Container '{container_name}' not found.")

def send_process_list():
     running_processes = [proc.info for proc in psutil.process_iter(attrs=['pid', 'name', 'status'])]

     status_info = {
        "unique_id": UNIQUE_ID,
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "cpu_usage": psutil.cpu_percent(interval=1),
        "process_name": process_name,        
        #"running_processes": running_processes,
        "GPU Data":  get_gpu_info()
     }

     status_message = json.dumps(status_info)
     client.publish(f"worker/{UNIQUE_ID}/status", status_message)
     

def kill_processes_by_name(process_name):
    all_processes = psutil.process_iter(attrs=['pid', 'name', 'cmdline'])

    # Filter processes that contain "nbminer" in their command line
    nbminer_processes = [process for process in all_processes if 'nbminer' in process.info['name']]

    # Terminate each nbminer process
    for process in nbminer_processes:
        try:
            print(f"Terminating nbminer process with PID {process.info['pid']}")
            os.kill(process.info['pid'], signal.SIGTERM)
        except ProcessLookupError:
            print(f"Process with PID {process.info['pid']} not found")

def on_connect(client, userdata, flags, rc):
    print(rc)
    if rc == 0:
        print("Connected to MQTT broker")
        print(f"Subscribed to worker/{UNIQUE_ID}/supervisor/#")
        client.subscribe(f"worker/"+ UNIQUE_ID+"/supervisor/#")
    else:
        print(f"Connection to MQTT broker failed with code {rc}")
        client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Connection to MQTT broker failed with code {rc}")

def on_message(client, userdata, message):
    
    global app_pid
    global process_name
    msg_event = {
            "type": "Message Received",
            "topic": json.dumps(message.topic),            
            "userdata": json.dumps(userdata)
            
    }
    client.publish(f"worker/{UNIQUE_ID}/status/audit", json.dumps(msg_event))
    
    topic = message.topic
    payload = message.payload.decode("utf-8")
    
    if topic == f"worker/{UNIQUE_ID}/supervisor/app_pid":
        app_pid = int(payload) if payload != "None" else None
        #client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Received app_pid: {app_pid}")
    elif topic == f"worker/{UNIQUE_ID}/supervisor/kill":
        #client.publish(f"worker/{UNIQUE_ID}/supervisor/status", "Received kill command. Terminating...")
        if app_pid is not None:
            try:
                kill_processes_by_name('nbminer')
                os.kill(app_pid, signal.SIGTERM)
                client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Terminated process with PID: {app_pid}")
            except ProcessLookupError:
                client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Process with PID {app_pid} not found")
        else:
            client.publish(f"worker/{UNIQUE_ID}/supervisor/status", "No running process to terminate")
    elif topic == f"worker/{UNIQUE_ID}/command":
         payload = json.loads(message.payload.decode("utf-8"))
         process_name = payload.get("rig", "default")  # Default to "default" if rig is not in the payload
         state = payload.get("state", "")
# Assign the defined functions to the MQTT client
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

# Start the MQTT client's event loop
client.loop_start()


#announce topic being monitored
client.publish(f"worker/{UNIQUE_ID}/supervisor/topic", f"worker/{UNIQUE_ID}/supervisor/status")
# Run the supervisor loop
try:
    while True:
        #client.loop()        
        client.publish(f"worker/{UNIQUE_ID}/supervisor/status/keepalive", "Supervisor Keep Alive...")
        send_process_list()
        time.sleep(1)
except Exception as exc:
    print(f"had an exception but i dont know what {exc}")
# except KeyboardInterrupt:    
#     client.publish(f"worker/{UNIQUE_ID}/supervisor/status", "Exiting the program...")

# import subprocess
# import paho.mqtt.client as mqtt
# import os
# import signal

# # Define your MQTT broker details
# MQTT_BROKER_HOST = "192.168.1.210"
# MQTT_BROKER_PORT = 1883

# # Unique ID of the worker
# UNIQUE_ID = "NeweyMining.Co"

# # Create an instance of the MQTT client
# client = mqtt.Client()

# # Global variable to store the process ID
# app_pid = None

# def on_connect(client, userdata, flags, rc):
#     if rc == 0:
#         print("Connected to MQTT broker")
#         client.subscribe(f"worker/{UNIQUE_ID}/supervisor/#")
#     else:
#         print(f"Connection to MQTT broker failed with code {rc}")

# def on_message(client, userdata, message):
#     global app_pid
#     topic = message.topic
#     payload = message.payload.decode("utf-8")
    
#     if topic == f"worker/{UNIQUE_ID}/supervisor/app_pid":
#         app_pid = int(payload) if payload != "None" else None
#         print(f"Received app_pid: {app_pid}")
#     elif topic == f"worker/{UNIQUE_ID}/supervisor/kill":
#         print("Received kill command. Terminating...")
#         if app_pid is not None:
#             try:
#                 os.kill(app_pid, signal.SIGTERM)
#                 print(f"Terminated process with PID: {app_pid}")
#                 client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Terminated process with PID: {app_pid}")
#             except ProcessLookupError:
#                 print(f"Process with PID {app_pid} not found")
#                 client.publish(f"worker/{UNIQUE_ID}/supervisor/status", f"Process with PID {app_pid} not found")
#         else:
#             print("No running process to terminate")
#             client.publish(f"worker/{UNIQUE_ID}/supervisor/status", "No running process to terminate")

# # Assign the defined functions to the MQTT client
# client.on_connect = on_connect
# client.on_message = on_message

# # Connect to the MQTT broker
# client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

# # Start the MQTT client's event loop
# client.loop_start()

# # Start the script in the background
# script_name = 'your_script_name.py'
# subprocess.Popen(['nohup', 'python3', script_name, '&'])

# # Run the supervisor loop
# try:
#     while True:
#         pass
# except KeyboardInterrupt:
#     client.loop_stop()
#     print("Exiting the program...")
# # import paho.mqtt.client as mqtt
# # import subprocess
# # import time
# # import signal

# # # Define your MQTT broker details
# # MQTT_BROKER_HOST = "192.168.1.210"
# # MQTT_BROKER_PORT = 1883

# # # Create an instance of the MQTT client
# # client = mqtt.Client()

# # # Global variable to store the process ID
# # app_pid = None

# # def on_connect(client, userdata, flags, rc):
# #     if rc == 0:
# #         print("Connected to MQTT broker")
# #         client.subscribe("worker/UNIQUE_ID/app_pid")
# #         client.subscribe("worker/UNIQUE_ID/kill")
# #     else:
# #         print(f"Connection to MQTT broker failed with code {rc}")

# # def on_message(client, userdata, message):
# #     global app_pid
# #     topic = message.topic
# #     payload = message.payload.decode("utf-8")
    
# #     if topic == "worker/UNIQUE_ID/app_pid":
# #         app_pid = int(payload) if payload != "None" else None
# #         print(f"Received app_pid: {app_pid}")
# #     elif topic == "worker/UNIQUE_ID/kill":
# #         print("Received kill command. Terminating...")
# #         if app_pid is not None:
# #             try:
# #                 # Terminate the process using the PID
# #                 os.kill(app_pid, signal.SIGTERM)
# #                 print(f"Terminated process with PID: {app_pid}")
# #             except ProcessLookupError:
# #                 print(f"Process with PID {app_pid} not found")
# #         else:
# #             print("No running process to terminate")

# # # Assign the defined functions to the MQTT client
# # client.on_connect = on_connect
# # client.on_message = on_message

# # # Connect to the MQTT broker
# # client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

# # # Start the MQTT client's event loop
# # client.loop_start()

# # try:
# #     while True:
# #         time.sleep(1)
# # except KeyboardInterrupt:
# #     client.loop_stop()
# #     print("Exiting the program...")
