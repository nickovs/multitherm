import machine
import pyb
import math
import time
import sys
import json
import gc

__version__ = "0.3.0"

zeroCK = 273.15

# Default setting for the thermstats
DEFAULT_SET_POINT=20.0
DEFAULT_DEAD_ZONE = 1.0
DEFAULT_MONITOR = 0

# Default values for the thermistors and reference resistors
DEFAULT_R_REF = 10000
DEFAULT_BETA = 3844.0507496971973
DEFAULT_R_INF = 0.02525047617366118

def debug(s):
    # pyb.USB_VCP().write("DEBUG {}\r\n".format(s))
    pass
    
def calibrate_termistor(t0, r0, t1, r1):
    # Return constants for termistor based on two reference readings
    # Input temperatures are in Celsius
    t0 += zeroCK
    t1 += zeroCK
    beta = math.log(r1/r0) / (1/t1 - 1/t0)
    r_inf = r0 * math.exp(-beta/t0)
    return beta, r_inf

class Thermistor:
    def __init__(self, adc, ref_R, beta, r_inf):
        self._adc = adc
        self._ref_R = ref_R
        self._beta = beta
        self._r_inf = r_inf

    def _RtoT(self, r):
        # Convert resistance into temperature in Kelvin
        return self._beta/math.log(r/self._r_inf)

    def _read_R(self):
        # Read ADC and compute termistor resistance
        v = self._adc.read() / 4096.0
        return v*self._ref_R/(1-v) if v else (self._ref_R/10000.0)

    def read_T(self):
        """Read temperature and return it in Celsius"""
        r = self._read_R()
        return self._RtoT(r) - zeroCK

class Thermostat:
    def __init__(self, t, r, index, set_point=20.0, dead_zone=1.0, override=None, adjust=0.0, **extra_args):
        self._t = t
        self._r = r
        self._r.value(0)
        self.index = index
        self._set = set_point
        self._dead = dead_zone/2
        self._override = None if (override == -1) else override
        self.adjust = adjust
        if extra_args:
            debug("Extra args provided: {}".format(extra_args))
        
    @property
    def temp(self):
        return self._t.read_T() + self.adjust

    def check(self):
        if self._override != None:
            self._r.value(self._override)
        else:
            if self._r.value():
                if self.temp > self._set + self._dead:
                    self._r.value(0)
            else:
                if self.temp < self._set - self._dead:
                    self._r.value(1)

    @property
    def set_point(self):
        return self._set

    @set_point.setter
    def set_point(self, set_temp):
        self._set = set_temp
        self.check()

    @property
    def override(self):
        return self._override

    @override.setter
    def override(self, v):
        if v not in [None, 0, 1, True, False]:
            raise ValueError
        self._override = v
        self.check()        

    @property
    def state(self):
        self.check()
        return self._r.value()

    def write_state(self, serial_port):
        x = "STATE CHAN={} T={:.1f} SET={:.1f} OUT={} ADJ={:.1f} OVERRIDE={}\r\n".format(self.index, self.temp, self.set_point, self.state, self.adjust, self.override)
        serial_port.write(x)

    @property
    def config(self):
        return {
            "set_point":self._set,
            "dead_zone":self._dead*2,
            "override": -1 if (self._override is None) else (1 if self._override else 0),
            "adjust": self.adjust
        }

    @config.setter
    def config(self, config):
        self._set = config["set_point"]
        self._dead = config["dead_zone"]/2
        self._override = None if config["override"] == -1 else config["override"]
        self.adjust = config["adjust"]
        self.check()
        k = set(config.keys()) - {"set_point", "dead_zone", "override", "adjust"}
        if k:
            debug("Extra keys in config being set: {}".format(k))
        
mon_countdown = 0
mon_report = False

class ActivityLED:
    def __init__(self, led_number=1, timer_number=1):
        self._led = pyb.LED(led_number)
        self._timer = pyb.Timer(timer_number)

    def activity(self, on_time=0.2):
        self._led.on()
        self._timer.callback(None)
        self._timer.init(freq=1.0/on_time)
        self._timer.callback(self._cb)

    def _cb(self, t):
        self._led.off()
        self._timer.deinit()

class CommandLine:       
    def __init__(self, serial_port, t_list, monitor_period=30, exit_allowed=False, wdt_timeout=None):
        debug("Constructing command line object")
        self.port = serial_port
        self.t_list = t_list
        self.monitor_period = monitor_period
        self.exit_allowed = exit_allowed
        self.wdt_to = wdt_timeout
        self.mon_report = False
        self.mon_countdown = monitor_period
        self.mon_timer = pyb.Timer(5)

        self.mon_timer.init(freq=1)
        self.mon_timer.callback(self._mon_callback)

        self.EXIT_flag = False

        self.pulse_LED = pyb.LED(2)
        self.activity = ActivityLED()

    def _mon_callback(self, t):
        self.mon_countdown -= 1
        if self.mon_countdown == 0:
            self.mon_report = True

    def command_loop(self):
        if self.wdt_to:
            wdt = machine.WDT(timeout = int(self.wdt_to*1000))
        else:
            wdt = None
    
        serial_port = self.port
        cmd_line = ""

        while True:
            # Clean up memory
            gc.collect()
            # Feed the (watch)dog
            if wdt:
                wdt.feed()
            # Check if we are marked to quit
            if self.EXIT_flag:
                break
            # Sleep a little
            time.sleep(0.1)
            # Blink the green light at 1Hz
            self.pulse_LED.on() if (time.time() & 1) else self.pulse_LED.off()

            # Check all the thermostats
            for t in self.t_list:
                t.check()
        
            # debug("Monitor: countdown={}, report={}, period={}".format(mon_countdown, mon_report, monitor_period))
            if self.mon_report:
                # Clear the report flag
                self.mon_report = False
                # If monitoring is on then reset the countdown
                if self.monitor_period:
                    self.mon_countdown = (self.mon_countdown % self.monitor_period) if self.mon_countdown else self.monitor_period
                for tt in self.t_list:
                    tt.write_state(serial_port)

            # Process input
            while True:
                try:
                    if serial_port.any():
                        cmd_line += str(serial_port.read(), "UTF8")
                        self.activity.activity(0.1)
                except KeyboardInterrupt as k:
                    serial_port.write("INTERRUPT: Use EXIT command rather than control-C\r\n")

                # If we have exhausted input and there is no line break then drop out of the input loop
                if "\r" not in cmd_line:
                    break

                # Extract the first line
                l, cmd_line = cmd_line.split("\r", 1)    
                l = l.strip()

                # Process the command
                if not l:
                    serial_port.write("OK\r\n")
                else:
                    try:
                        self._process_command(l)
                    except Exception as e:
                        self.port.write("ERR EXCEPTION trying to process command line {}: {}\r\n".format(e.__class__.__name__, e))
                        # sys.print_exception(e)                        


    # Each command is represented by a dictionary entry:
    #   <command name> : ( <needs thermostat index>, <min arg count>, <max arg count>)
    _command_table = {
        "VERSION": (False, 0, 0, "Print the current firmware version"),
        "TEMP": (True, 0, 0, "Print the current channel temperature"),
        "SET": (True, 1, 1, "Set the channel set-point"),
        "OVERRIDE": (True, 1, 1, "Override channel output"),
        "STATE": (True, 0, 0, "Print channel state information"),
        "MONITOR": (False, 0, 1, "Set period for automatic channel state monitoring"),
        "SAVECONFIG": (False, 0, 0, "Write current settings to config storage"),
        "LOADCONFIG": (False, 0, 0, "Load stored configuration"),
        "EXIT": (False, 0, 0, "Exit command loop"),
        "RESET": (False, 0, 0, "Reboot thermostate software"),
        "HELP": (False, 0, 1, "Print help messages"),
        "ADJUST": (True, 1, 1, "Set offset to be added to thermistor reading"),
    }

    def _process_command(self, l):
        verb, *args = l.split()
        verb = verb.upper()
        debug("verb={}, args={}\r\n".format(verb, args))
        if verb not in self._command_table:
            self.port.write("ERR unknown command {}\r\n".format(verb))
            return

        c_therm, c_min, c_max, c_help = self._command_table[verb]
        n_args = len(args)
        if c_therm:
            if n_args == 0:
                self.port.write("ERR command {} requires thermostat number or *\r\n".format(verb))
                return
            else:
                therm_no = args.pop(0)
                n_args -= 1
                if therm_no == "*":
                    tl = range(len(self.t_list))
                else:
                    try:
                        i = int(therm_no)
                    except ValueError:
                        self.port.write("ERR can not parse channel number {}\r\n".format(therm_no))
                        return
                    if i < 0 or i >= len(self.t_list):
                        self.port.write("ERR channel number must be in range 0 to {}\r\n".format(len(self.t_list)))
                        return
                    tl = [i]

        if n_args < c_min:
            self.port.write("ERR command {} requires at least {} arguments\r\n".format(verb, c_min))
            return
        
        if n_args > c_max:
            self.port.write("ERR command {} accepts at most {} arguments\r\n".format(verb, c_max))
            return
        
        c_fn = getattr(self, "_do_"+verb.lower())
        try:
            if c_therm:
                for t in tl:
                    c_fn(self.t_list[t], *args)
            else:
                c_fn(*args)
        except Exception as e:
            self.port.write("ERR EXCEPTION while executing command {}: {}: {}\r\n".format(verb, e.__class__.__name__, e))
            # sys.print_exception(e)

    def _do_version(self):
        self.port.write("VERSION {}\r\n".format(__version__))

    def _do_temp(self, therm):
        self.port.write("TEMP {} {}\r\n".format(therm.index, therm.temp))

    def _do_set(self, therm, temp):
        t = float(temp)
        if t < 5 or t > 40:
            raise ValueError("Temp must be between 5 and 40 C")
        therm.set_point = t
        self.port.write("SET {} {} OK\r\n".format(therm.index, t))

    def _do_override(self, therm, state):
        opts = {"NONE": None,
                "NO": None,
                "-1": None,
                "ON": 1,
                "1": 1,
                "OFF": 0,
                "0": 0 }
        state = state.upper()
        if state not in opts:
            self.port.write("ERR OVERRIDE invalid setting {} for thermostat {}\r\n".format(state, therm.index))
        else:
            therm.override = opts[state]
            self.port.write("OVERRIDE {} {} OK\r\n".format(therm.index, state))


    def _do_adjust(self, therm, offset):
        offset = float(offset)
        if abs(offset) > 5.0:
            self.port.write("ERR ADJUST offset limited to +/- 5 celcius, value {:.1f} out of range for thermostat {}\r\n".format(offset, therm.index))
        else:
            therm.adjust = offset
            self.port.write("ADJUST {} {:.1f} OK\r\n".format(therm.index, offset))
        
    def _do_state(self, therm):
        therm.write_state(self.port)

    def _do_monitor(self, *value):
        if len(value):
            if value[0].upper() == "OFF":
                period = 0
            else:
                period = int(value[0])
                self.monitor_period = period
                self.mon_countdown = period
            self.port.write("MONITOR {} OK\r\n".format(period))
        else:
            self.port.write("MONITOR {}\r\n".format(self.monitor_period))

    def _do_saveconfig(self):
        conf = {"monitor": self.monitor_period,
                "therms": [t.config for t in self.t_list] }
        with open("/flash/config.json", "w") as fh:
            fh.write(json.dumps(conf))
        self.port.write("SAVECONFIG OK\r\n")

    def _do_loadconfig(self):
        conf = load_config(len(self.t_list))
        self.monitor_period = conf["monitor"]
        for c, t in zip(conf["therms"], self.t_list):
            t.config = c
        self.port.write("LOADCONFIG OK\r\n")

    def _do_exit(self):
        if self.exit_allowed:
            self.EXIT_flag = True
            self.port.write("EXIT OK\r\n")
        else:
            self.port.write("ERR EXIT disallowed\r\n")
            
    def _do_reset(self):
        self.port.write("RESET OK\r\n")
        machine.reset()

    def _do_help(self, cmd=None):
        if cmd:
            cmd = cmd.upper()
            if cmd not in self._command_table:
                self.port.write("ERR HELP unknown command {}\r\n".format(cmd))
                return
            c_list = [cmd]
        else:
            c_list = sorted(self._command_table.keys())

        for c_name in c_list:
            if c_name == "EXIT" and not self.exit_allowed:
                continue
            c_therm, c_min, c_max, c_help = self._command_table[c_name]
            l = "HELP " + c_name
            if c_therm:
                l += " <therm number>"
            for i in range(c_min):
                l += " <arg>"
            for i in range(c_min, c_max):
                l += " [<arg>]"
            l += "\r\n"
            self.port.write(l)
            self.port.write("HELP     {}\r\n".format(c_help))

def load_config(n):
    t_defs = {"set_point":DEFAULT_SET_POINT, "dead_zone":DEFAULT_DEAD_ZONE}
    config = {}
    try:
        config = json.load(open("/flash/config.json"))
    except OSError:
        debug("Could not load config file")

    if "monitor" not in config:
        config["monitor"] = DEFAULT_MONITOR
    if "therms" not in config:
        config["therms"] = [t_defs] * n
    else:
        tt = config["therms"]
        if len(tt) > n:
            del tt[n:]
        elif len(tt) < n:
            tt.extend([t_defs] * (n - len(tt)))
    return config

def run(n=8, exit_allowed=True, wdt_timeout=None):
    # Use the USB port
    serial_port = pyb.USB_VCP()

    beta = DEFAULT_BETA
    ref_r = DEFAULT_R_REF
    r_inf = DEFAULT_R_INF

    adc_pin_names = ["X{}".format(i+1) for i in range(n)]
    relay_pin_names = ["Y{}".format(i+1) for i in range(n)]
    
    config = load_config(n)
    
    adc_list = [pyb.ADC(pyb.Pin(p)) for p in adc_pin_names]
    relay_list = [pyb.Pin(p, pyb.Pin.OUT_PP) for p in relay_pin_names]
    tr_list = [Thermistor(adc, ref_r, beta, r_inf) for adc in adc_list]
    t_list = [Thermostat(tr, relay, i, **config["therms"][i]) for i,(tr, relay) in enumerate(zip(tr_list, relay_list))]

    serial_port.write("STARTING pyboard multi-thermostat version {}\r\n".format(__version__))
    
    cmd_proc = CommandLine(serial_port, t_list, exit_allowed=exit_allowed, monitor_period=config["monitor"], wdt_timeout=wdt_timeout)
    cmd_proc.command_loop()

