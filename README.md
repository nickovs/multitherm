# MultiTherm

MultiTherm is a multi-channel, controllable thermostat system based on
the [MicroPython](https://micropython.org)
[pyBoard](https://store.micropython.org/#/features).

This code is designed to support up to eight channels; each channel
uses a thermistor and a fixed resistor on an analogue input to measure
the temperature and a relay connected to a digital output to control an
existing heating circuit. Details of a suitable hardware configuration
can be found in the the [hardware](hardware/Hardware.md) subdirectory.

To make use of this code it should be loaded into the root of the file
system on the MicroPython board and the `main.py` file should be
updated to include the lines:

```
import multitherm
multitherm.main()
```

The `multitherm` code communicates over the USB port as a serial
device. Details of the commands and their responses can be found in
the [Commands.md] file.

