# virpil-led-helper
Control VPC LEDs using this Joystick Gremlin script collection.

Files:
- `bms_virpil_leds_autostart_jg13x.py` - python plugin entry point for Joystick Gremlin (configured and tested for v13.3)
- `virpil_bms_leds.json` - configurable device information and flightdata.h -> LED mappings.
- `virpil_led_helper.exe` - compiled python, communicates between BMS shared memory area and VPC_LED_Control.exe
- `virpil_led_helper.py` - source
- `VPC_LED_Control.exe` - Supplied by Virpil, uses VID/PID/mappings from .json, talks to device.

Instructions (this is all you get!):
- I recommend placing the entire extracted virpil-led-helper folder in ```Users\[username]\joystick gremlin``` folder, if it exists, or other suitable default.
- Use the plugins tab in JG to add the entry point script, `bms_virpil_leds_autostart_jg13x.py`
- Edit the .json file with your PID/VID (you can get this from the VPC Configuration Tool) and desired bindings. Bit masks are available from flightdata.h in your ```[BMS dir]\Tools\SharedMem``` folder
- The small compiled python exe should run at profile activation and dismiss itself when the profile is unloaded - worst case it stays running in the background and you can kill it with Task Manager.

In the JSON file:

```
"virpil": {
    "vid" - Set for your desired device
    "pid" - Set for your desired device
  },
```

```
  "mappings": [
    {
      "name" - whatever you want
      "word" - Word containing desired bit - in this case "LightBits"
      "mask" - Bit Mask
      "cmd" - Command sent to the VPC device. Sorry, you'll probably have to get these by trial and error.
      "on" - Color when bit is active
      "off" - Color when bit is off
    },
```


If you are using the latest JG version (14.x I believe) you'll probably have to edit the entry point script. I haven't tried it. Good luck!
