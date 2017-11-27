#!/usr/bin/env python3

from bottle import route, run, get, post, request, redirect

from thermoboard import ThermoBoard

board_paths = [ "/dev/tty.usbmodem1452" ]

device_name_map = { 3: {1: "Living room",
                        2: "Bedroom 1",
                        3: "Playroom",
                        4: None,
                        5: "Kitchen",
                        8: None }
                    }

def build_zone_list(boards):
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

def state_for_id(i):
    board, index, name = zone_list[i]
    r = {"ID":i,
         "board_id":board.ID,
         "index": index,
         "name": name}
    r.update(board.get_state(index))
    return r

@route('/')
def root():
    redirect("/index.html")

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
    r = state_for_id(i)
    if errs:
        r['errs'] = errs
    return r

boards = [ThermoBoard(p) for p in board_paths]
zone_list = build_zone_list(boards)
    
run(host='0.0.0.0', port=27315, debug=True, reloader=True)
