import serial
import threading

class CommandError(Exception):
    pass

def OneZeroNone(s):
    if s is None or isinstance(s, int):
        return s
    d = {"0": 0,
         "false": 0,
         "off": 0,
         "1": 1,
         "true": 1,
         "on": 1,
         "none": None,
         "-1": None}
    s = s.lower()
    if s not in d:
        raise ValueError("Invalid override value: {}".format(s))
    return d[s]

def chan_unpack(chan, rr):
    return rr if chan == "*" else rr[0]

class ThermoBoard:
    def __init__(self, path):
        self._s = serial.Serial(path)
        self._s.timeout = 0.25
        self._drain()
        self._cmd_lock = threading.Lock()
        self.ID = self.get_ID()

    def _drain(self):
        while True:
            _ = self._s.read(1024)
            if not _:
                break
        
    def _run_command(self, cmd, *args, expect = 1, allow_few=False):
        s = self._s
        c = cmd
        if args:
            c += " "
            c += " ".join(str(i) for i in args)
        c += "\r\n"
        rr = []
        if expect == "*":
            expect = (8 if args[0]=="*" else 1)
        e = expect
        # Serialise the communication on the serial port
        with self._cmd_lock:
            print("Sending: {}".format(c))
            s.write(c.encode("ASCII"))
            while e:
                l = s.readline().strip()
                if not l:
                    break
                ll = l.decode("ASCII").strip().split()
                print("Recieved: {}".format(ll))
                if ll[0] == "ERR":
                    raise CommandError("Command returned error: {}".format(l))
                elif ll[0] != cmd.upper():
                    print("Unexpected response line: {}, ll[0]={}, cmd={}".format(l, ll[0], cmd))
                else:
                    rr.append(ll)
                    e -= 1
        if expect and not rr:
            raise CommandError("No valid response to {} request".format(cmd))
        if len(rr) != expect and not allow_few:
            raise CommandError("Insufficient response lines to {} request".format(cmd))
        return rr

    def get_ID(self):
        rr = self._run_command("ID")
        return int(rr[0][1])

    def get_version(self):
        rr = self._run_command("VERSION")
        return int(rr[0][1])

    def get_temp(self, channel):
        rr = self._run_command("TEMP", channel, expect="*")
        return chan_unpack(channel, [float(i[2]) for i in rr])

    @staticmethod
    def _parse_state(s):
        convert = {"CHAN": int,
                   "T": float,
                   "SET": float,
                   "OUT": int,
                   "ADJ": float,
                   "OVERRIDE": OneZeroNone}
        r = {}
        for part in s:
            k, v = part.split("=")
            if k in convert:
                v = convert[k](v)
            r[k.lower()]=v
        return r

    def get_state(self, channel):
        rr = self._run_command("STATE", channel, expect ="*")
        return chan_unpack(channel, [self._parse_state(i[1:]) for i in rr])

    def set_set_point(self, channel, temperature):
        self._run_command("SET", channel, temperature, expect ="*")

    def set_override(self, channel, override):
        override = OneZeroNone(override)
        self._run_command("OVERRIDE", channel, override, expect ="*")

    def set_adjust(self, channel, offset):
        self._run_command("ADJUST", channel, offset, expect ="*")

    def saveconfig(self):
        self._run_command("SAVECONFIG")

    def loadconfig(self):
        self._run_command("LOADCONFIG")

    def reset(self):
        if not hard:
            self._run_command("RESET")

    def close(self):
        self._s.close()

