import serial
import threading
import select
import time

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
        self.state_list = [None] * 8
        self._async_running = False
        self._async_thread = None
        self.async_callback = None
        
    def _drain(self):
        while True:
            _ = self._s.read(1024)
            if not _:
                break

    def _handle_async_message(self, m):
        ll = m.decode("ASCII").strip().split()
        if ll[0][0] != "*":
            if ll[0] != "OK":
                print("Received non-async message asynchronously: {}".format(ll))
        else:
            if ll[0] == "*ASYNC" or ll[0] == "*MONITOR":
                # print("ASYNC message: {}".format(ll))
                state = self._parse_and_cache_state(ll[1:])
                if self.async_callback:
                    try:
                        self.async_callback(self, state["chan"], state)
                    except Exception as e:
                        print("Async calback raised exception: {}: {}".format(e.__class__.__name__, e))
            else:
                print("Received unknown async message: {}".format(ll))

    def _async_loop(self):
        # print("Async thread starting: {} {}".format(self._async_running, self._s.is_open))
        while self._async_running and self._s.is_open:
            rl, wl, xl = select.select([self._s], [], [], 1)
            if rl and self._s.is_open:
                with self._cmd_lock:
                    l = self._s.readline().strip()
                    if l:
                        self._handle_async_message(l)
        # print("Async thread exiting: {} {}".format(self._async_running, self._s.is_open))
                
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
            # print("Sending: {}".format(c))
            s.write(c.encode("ASCII"))
            while e:
                l = s.readline().strip()
                if not l:
                    break
                if l[0] == ord("*"):
                    self._handle_async_message(l)
                else:
                    ll = l.decode("ASCII").strip().split()
                    # print("Recieved: {}".format(ll))
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
        return rr[0][1]

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

    def _parse_and_cache_state(self, s):
        state = self._parse_state(s)
        self.state_list[state['chan']-1] = state
        return state
    
    def get_state(self, channel):
        rr = self._run_command("STATE", channel, expect ="*")
        return chan_unpack(channel, [self._parse_and_cache_state(i[1:]) for i in rr])

    def get_cached_state(self, channel):
        if not self._async_running:
            print("ASYNC thread not started, using uncached state")
            return self.get_state(channel)
        if channel == "*":
            return [i.copy() for i in self.state_list]
        else:
            i = int(channel)
            if i<1 or i>8:
                raise ValueError("Channel number must be between 1 and 8")
            return self.state_list[i-1].copy()

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

    def reset(self, hard=False):
        if not hard:
            self._run_command("RESET")
            time.sleep(1)
            self._drain()
            return self.get_version()
        else:
            raise NotImplemented("Hard reset not currently supported")
            
    def close(self):
        self._s.close()

    def start_async(self, cb=None):
        if self._async_running:
            raise Exception("Async thread already running")
        if cb:
            self.async_callback = cb
        self._async_thread = threading.Thread(target=self._async_loop)
        self._async_running = True
        self._run_command("ASYNC", "1")
        self.get_state("*")
        self._async_thread.start()

    def stop_async(self):
        self._async_running = False
        with self._cmd_lock:
            self._s.write(b"\r\n")
        self._async_thread.join()
        self._async_thread = None

