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
#!/usr/bin/env python3
import requests, yaml, json
from flask import Flask, request, redirect, url_for, render_template
from csv import DictReader


# Room Data, from csv file
MerakiCamera_to_JabberRoom = []
with open('MerakiCameras_to_JabberRoom.csv', 'r') as read_obj:
    csv_dict_reader = DictReader(read_obj)
    for row in csv_dict_reader:
        row['Room_Name'] = row.pop('Room_Name')
        MerakiCamera_to_JabberRoom.append(row)
# note the use case is developed with only one patient room available, requires iterations if multiple rooms are listed in MerakiCameras_to_JabberRoom.csv
    ROOM_NAME = MerakiCameras_to_JabberRoom[0]['Room_Name']
    SIP_URL = MerakiCamera_to_JabberRoom[0]['Jabber_Room_SIP']


app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


@app.route('/')
def pop_up():
    global ROOM_NAME, SIP_URL

    return render_template('popup.html', sip_url=SIP_URL, room=ROOM_NAME)


@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'

    return response


if __name__ == "__main__":
    app.run()
