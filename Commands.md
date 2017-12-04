# Command interface for multi-channel thermostat

The MicroPython board supports a USB client interface and by default
it shows up as both a serial device and a mass storage device. The
*multitherm* software can operate without a controller but it can use
the serial device for communication to a more intelligent host.

## Supported commands

Commands to the thermostat board should be sent terminated with a
carriage return ('\r', 0x0d) character. Successful execution will be
indicated by returning a string which starts with the command name,
optionally followed by requested data. Commands which change settings
will issue a response text ending with "OK". All responses will be
terminated by a carriage return ('\r', 0x0d) and linefeed ('\n',
0x0a).

Several of the commands require a thermostat channel number. This can
either be a value between 1 and 8 (inclusive) or it can be a single
asterisk `*`, in which case the command will be applied to all of the
thermostats on the board. In this case one response line will be sent
for each thermostat.

Some commands (currently MONITOR and ASYNC) can enable the board to
emit messages which are not responses to the most recent
command. These messages can be distinguished from direct responses to
commands by virtue of starting with an asterisk `*` and this will be
immediately followed by the name of the command that enabled these
messages (e.g. `*ASYC` or `*MONITOR`). These messages are not truly
asynchonous as they will never be emitted while the board is in the
process of delivering a multi-line response to another command. As a
result the controlling code can rely on multi-line responses to
commands being returned contiguously.

### `VERSION`

Print the current firmware version. The firmware uses semantic version
numbers of the form `<major>.<minor>.<update>`. Changes in the major
version number may indicate incompatible API changes. The addition of
significant new functions will be indicated by a change of minor
version number. Other updates and bug fixes will change the update
number.

### `ID`

Print the board ID (a number in the range 0 through 15 inclusive) as set by the DIP switches on the card. This allows multiple cards to be distinguished.

### `TEMP <chan>`

Print the current channel temperature as reported by the channel sensor in degrees Celsius, in the form `TEMP <chan> <temperature>`

### `SET <chan> <temperature>`

Set the thermostat channel set-point to the given temperature in
Celsius. This value is preserved if the configuration is saved.

### `OVERRIDE <chan> <On|Off|None>`

Override channel output state to force it either on or off, or disable
any existing override. This value is preserved if the configuration is
saved.

### `ADJUST <chan> <offset>`

Set offset to be added to thermistor reading to allow for
calibration. This value is preserved if the configuration is saved.

### `STATE <chan>`

Print channel state information. In the current version the output is of the form:
```
STATE CHAN=<n> T=<t> SET=<s> OUT=<o> ADJ=<a> OVERRIDE=<r>
```
Where:
* `n` is the channel number
* `t` is the current temperature in Celsius (with adjustment applied)
* `s` is the current thermostat set-point
* `o` is the output relay state
* `a` is the temperature calibration adjustment offset to added to the measured temperature
* `r` is the override state

If any future version of the firmware adds new values to the state output they will be of the form `<key>=<value>` and neither `key` nor `value` will contain whitespace.

### `MONITOR <period>`

Set period for automatic channel state monitoring, in seconds. Each
period the state of each channel will be printed in starting with the
string `*MONITOR` followed by the same state information as issued by
the `STATE` command. This value is preserved if the configuration is
saved.

### `ASYNC [ON|OFF]`

Enable or disable asynchronous notification of changes in either the
state of thermostate channel outputs or changes in sensed channel
temperatures by more than 0.1 Celsius. Each change notification will
take the form of the string `*ASYNC` followed by the same state
information as issued by the `STATE` command.

### `NCHAN [<count>]`

Display or change the number of active channels. While the default for
the hardware is to support 8 channels if fewer channels are needed
then this command allows user to set the number of active
channels. The active channels are always the lower-numbered channels
(i.e. channels 1 through `count` inclusive). The relays for the
inactive channels will be left open. Sending this command without a
parameter will return the current value without changing it. This
value is preserved if the configuration is saved.

### `SAVECONFIG`

Write current settings to the non-volatile configuration storage. The stored configuration includes the set point, override and calibration adjustment.

### `LOADCONFIG`

Load stored configuration. This configuration is also automatically loaded when the device is (re)started.

### `RESET [HARD]`

Reboot thermostat software. This is useful after new firmware was been loaded onto the MicroPython board. If the `HARD` parameter is added then this performs a reset equivalent to pressing the reset button. Note that a hard reset will effectively remove the USB device so it is important to sync file systems and properly "eject" the USB drive before issuing a hard reset.

### `EXIT`

Exit command loop. This command is normally only used for debugging and the command is inaccessible unless a file called `DEBUG` is present in the root directory of the file system on the MicroPython board. Note that after first creating the `DEBUG` file it is necessary to perform a hard reset to ensure that the *watchdog* reboot timer is disabled, otherwise the card will automatically reboot 10 seconds after the command loop is exited.

### `HELP [command]`

Print help messages.
