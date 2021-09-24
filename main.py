#!/usr/bin/env python3
'''
Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
'''
import json, time, yaml, webbrowser
import paho.mqtt.client as mqtt
from csv import DictReader
import xmpp
import requests
import pathlib, os


#Meraki and Jabber credentials from credentials YAML file
cred = yaml.safe_load(open("credentials.yml"))
MERAKI_KEY = cred['MERAKI_KEY']
MERAKI_NETWORK_ID = cred['MERAKI_NETWORK_ID']
JABBER_ID = cred["JABBER_ID"]
JABBER_PASS = cred["JABBER_PASS"]
JABBER_RECEIVER = cred["JABBER_RECEIVER"]

# Room Data, from csv file
MerakiCamera_to_JabberRoom = []
with open('MerakiCameras_to_JabberRoom.csv', 'r') as read_obj:
    csv_dict_reader = DictReader(read_obj)
    for row in csv_dict_reader:
        print(row)
        row['Room_Name'] = row.pop('Room_Name')
        MerakiCamera_to_JabberRoom.append(row)
# note the use case is developed with only one patient room available, requires iterations if multiple rooms are listed in MerakiCameras_to_WebexRoomKitMini_Pairing.csv
ROOM_NAME = MerakiCamera_to_JabberRoom[0]['Room_Name']
MERAKI_SN = MerakiCamera_to_JabberRoom[0]['Meraki_SN']
JABBER_ROOM_SIP = MerakiCamera_to_JabberRoom[0]['Jabber_Room_SIP']



# MQTT
MQTT_SERVER = cred['MQTT_SERVER']
MQTT_PORT = cred['MQTT_PORT']
MQTT_TOPIC = "/merakimv/" + MERAKI_SN + "/raw_detections"



# motion trigger settings
MOTION_SENSITIVITY = 0.05 #a smaller number means the motion detection is more sensitive
MOTION_ALERT_PAUSE_TIME = 30 #how many seconds to pause the motion detection after motion is detected
_PERSON_IDS = {} #this will hold the location information about each person detected by the camera



def collect_information(client, people):

    # detect motion
    global _PERSON_IDS, MOTION_SENSITIVITY, MOTION_ALERT_PAUSE_TIME

    # if motion monitoring triggered
    for person in people:
        oid = person["oid"] #unique identifier of person detected by camera
        x0 = person["x0"] #x coordinate of the lower right corner of the person
        y0 = person["y0"] #y coordinate of the lower right corner of the person
        x1 = person["x1"] #x coordinate of the upper left corner of the person
        y1 = person["y1"] #y coordinate of the upper left corner of the person


        #check if the person has been detected by camera yet
        if oid not in _PERSON_IDS.keys():
            #if not, add them to person ids
            _PERSON_IDS[oid] = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
        else:
            #if they have been, check to see how much they have moved
            x0_diff = abs(_PERSON_IDS[oid]["x0"] - x0)
            y0_diff = abs(_PERSON_IDS[oid]["y0"] - y0)
            x1_diff = abs(_PERSON_IDS[oid]["x1"] - x1)
            y1_diff = abs(_PERSON_IDS[oid]["y1"] - y1)

            diff_set = {x0_diff, y0_diff, x1_diff, y1_diff}

            _PERSON_IDS[oid]["x0"] = x0
            _PERSON_IDS[oid]["y0"] = y0
            _PERSON_IDS[oid]["x1"] = x1
            _PERSON_IDS[oid]["y1"] = y1

            #if any of their coordinates have shifted by more than the set motion sensitivity, take snapshot, open web popup, and send Jabber message
            if any(diff >= MOTION_SENSITIVITY for diff in diff_set):
                print("Motion detected!")
                snapshot()
                alert()
                send_message()

                time.sleep(MOTION_ALERT_PAUSE_TIME) #pause the motion detection for the set time
                client.disconnect() #reset MQTT connection to clear queue

def alert():
    # open URL
    webbrowser.open_new('http://127.0.0.1:5000')


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe(MQTT_TOPIC)


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode("utf-8"))

    #if people are detected by the camera, add them to a list to be sent to the collect_information function
    if payload["objects"]:
        people = []
        for obj in payload["objects"]:
            if obj["type"] == "person":
                people.append(obj)

        print(people)
        collect_information(client, people)


def send_message():
    global JABBER_ID, JABBER_PASS, JABBER_RECEIVER, JABBER_CLIENT, JABBER_SERVER,ROOM_NAME, JABBER_ROOM_SIP

    jabberid = JABBER_ID #who the Jabber message is sending from
    password = JABBER_PASS #Jabber password associated with above ID
    receiver = JABBER_RECEIVER #who the message is being sent to
    jabberclient = JABBER_CLIENT #the hostname for your Jabber ID
    jabberserver = JABBER_SERVER #the hostname for your Jabber server for your Jabber ID
    message = "Movement detected! Call room " + ROOM_NAME + ": SIP:" + JABBER_ROOM_SIP #the SIP address of the Jabber endpoint in the room

    client = xmpp.Client(jabberclient)
    client.connect(server=(jabberserver, 5222))
    client.auth(jabberid, password)
    client.sendInitPresence()
    message = xmpp.Message(receiver, message)
    message.setAttr('type', 'chat')
    client.send(message)


def snapshot():
    #take snapshot of the camera view when movement is detected
    global MERAKI_NETWORK_ID, MERAKI_SN, MERAKI_KEY
    snapshot_url = "https://api.meraki.com/api/v0/networks/{}/cameras/{}/snapshot".format(MERAKI_NETWORK_ID, MERAKI_SN)

    headers = {
        'X-Cisco-Meraki-API-Key': MERAKI_KEY,
        "Content-Type": "application/json"
    }
    resp = requests.post(snapshot_url, headers=headers, json={})
    r = resp.json()
    snapshot = str(r["url"])
    snapshot_url = snapshot.replace(" ", "")

    filename = "snapshot.jpg" #snapshot saved as file named "snapshot.jpg"
    app_path = pathlib.Path(__file__).parent.resolve()
    resource_path = os.path.join(app_path, 'static/img/', filename) #that file is saved in the img directory in the static directory

    resp = requests.get(snapshot_url, verify=False)
    print(resp.status_code)

    #try to open url of snapshot - sometimes it takes a few tries for the program to open the url
    while resp.status_code != 200:
        time.sleep(2)
        resp = requests.get(snapshot_url, verify=False)
        print(resp.status_code)

    with open(resource_path, 'wb') as f:
        f.write(resp.content)
        f.close()

    print("Image successfully downloaded!")


if __name__ == "__main__":
    try:
        while True:
            try:
                client = mqtt.Client()
                client.on_connect = on_connect
                client.on_message = on_message
                client.connect(MQTT_SERVER, MQTT_PORT, 60)
                client.loop_forever()

            except Exception as ex:
                print("[MQTT] failed to connect or receive msg from mqtt, due to: \n {0}".format(ex))

    except KeyboardInterrupt:
        print("Interrupted!")
