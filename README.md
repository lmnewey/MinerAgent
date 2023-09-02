# MinerAgent
A docker agent to monitor a mining rig


This is a simple agent that starts and stops a mining rig, it takes a json message to start the miner, i had heaps of problems trying to spwan the miner and be non blocking then actually terminate the process after the fact.

So there is a second script that runs that supervises the operation, its a mess atm as its just a first pass


Example Payload, some of it gets ignored atm as i disabled some feature during troubleshooting

 {
    "state": "run",
    "wallet": "bc1qay45a4h87druu7pjup3n5wxyrg8wn8uaud3yqt",
    "rig": "esx2",
    "URL": "stratum+tcp://rvn.2miners.com:6060",
    "algorithm": "kawpow"
}

Example of some of the docker environment variables

DEFAULT_MQTT_BROKER_HOST = "192.168.1.210"
DEFAULT_MQTT_BROKER_PORT = 1883
DEFAULT_MINER_LOCATION = "/app/nbminer"
DEFAULT_MINER_ALGO = "kapow"
DEFAULT_MINER_RIGID = "NeweyMining.Co" // Im a huge TTD fan so... 


Docker Run:
sudo docker run --name miningrig -d --gpus device=0 -e MINER_RIGID=esx4 --network bridge docker2.newey.id.au/miner/nbminermqtt:alpha /app/app.py
