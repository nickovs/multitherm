#!/usr/bin/env python3
from bottle import route, run, get, post, request, redirect, static_file
import os, re
from os.path import join
import argparse
from collections import defaultdict

from thermoboard import ThermoBoard

static_root = "/home/nicko/multitherm/rest_server/static"

# This should work with most modern Linux systems
def locate_linux_micropython_devs():
    devices_path = "/sys/bus/usb/devices"
    usb_device_re = re.compile(r"^\d+-\d(\.\d)*$")    
    micropython_vid = 'f055'
    def vid_for_device(d):
        return open(join(devices_path, d, "idVendor")).read().strip()
    def tty_for_device(d):
        l = os.listdir(join(devices_path, d, d+":1.1", "tty"))
        return join("/dev", l[0])
    l = [i for i in os.listdir(devices_path) if usb_device_re.match(i)]
    return [tty_for_device(i) for i in l if vid_for_device(i) == micropython_vid]

def parse_room_names(file_name):
    d = defaultdict(dict)
    with open(file_name) as fh:
        for line in fh:
            line = line.strip()
            if not line or line[0] == "#":
                continue
            try:
                b, c, n = line.split(",")
                board = int(b.strip())
                channel = int(c.strip())
                name = n.strip()
                if name.lower() =='none':
                    name = None
            except Exception as e:
                print("Failed to parse room name entry '{}': {}: {}".format(line, e.__class__.__name__, e))
                continue
            d[board][channel] = name
    return d

def build_zone_list(boards, device_name_map):
    boards = list(boards)
    boards.sort(key=lambda x:x.ID)
    l = []
    for b in boards:
        for i in range(1, 9):
            if b.ID in device_name_map and i in device_name_map[b.ID]:
                name = device_name_map[b.ID][i]
                if name is None:
                    continue
            else:
                name = "Zone{},{}".format(b.ID,i)
            l.append((b, i, name))
    return l

def state_for_id(i, cached=True):
    board, index, name = zone_list[i]
    r = {"ID":i,
         "board_id":board.ID,
         "index": index,
         "roomname": name}
    s = board.get_cached_state(index) if cached else board.get_state(index)
    r.update(s)
    return r

@route('/')
def root():
    redirect("/index.html")

@route('/favicon.ico')
def favicon():
    return static_file("T.png", static_root)

@route("/index.html")
def index():
    return static_file("index.html", static_root)

@route("/static/<filepath:path>")
def static_content(filepath):
    return static_file(filepath, static_root)
    
@get("/thermostats")
def thermostats():
    return {"count": len(zone_list),
            "names": [i[2] for i in zone_list] }

@get("/thermostats/all_states")
def thermostats_all_states():
    return {"all_states": [state_for_id(i) for i in range(len(zone_list))]}

@get("/thermostat/<id:int>")
def thermostat_info(id):
    i = int(id)
    return state_for_id(i)

@post("/thermostat/<id:int>")
def thermostat_set(id):
    i = int(id)
    board, index, name = zone_list[i]
    settings = request.json
    errs = []
    for k, v in settings.items():
        print("Setting key {} to value {}".format(k,v))
        if k == "setpoint":
            board.set_set_point(index, v)
        elif k == "override":
            board.set_override(index, v)
        elif k == "adjust":
            board.set_adjust(index, v)
        else:
            errs.append("Unknown setting key: {}".format(k))
    r = state_for_id(i, cached=False)
    if errs:
        r['errs'] = errs
    return r

def parse_args():
    parser = argparse.ArgumentParser(description='Web service for a multi-channel thermostat system')
    parser.add_argument('--device', '-d', metavar="PATH", action='append',
                        help="specify path to thermostat board")
    parser.add_argument('--rooms', '-r', metavar="CVS_FILE",
                        help="specify file of 'board ID, channel, room name' lines")
    parser.add_argument('--private', '-P', action="store_true",
                        help="start the server for localhost only")
    parser.add_argument('--port', '-p', metavar="PORT", type=int, default=27315,
                        help="specify port number on which to open server")
    args = parser.parse_args()
    return args

zone_list = []

def main():
    args = parse_args()
    board_paths = args.device if args.device else locate_linux_micropython_devs()
    name_map = parse_room_names(args.rooms) if args.rooms else {}
    host_address = 'localhost' if args.private else '0.0.0.0'
    
    print("Starting thermostat server for devices: {}".format(board_paths))
    
    boards = [ThermoBoard(p) for p in board_paths]
    global zone_list
    zone_list = build_zone_list(boards, name_map)
    [b.start_async() for b in boards]

    run(server='paste', host=host_address, port=args.port)
    print("Stopping async threads for boards")
    [b.stop_async() for b in boards]

if __name__ == "__main__":
    main()
    
