# Heating

This AppDaemon automation is forked from [Vaclav](https://github.com/bruxy70/Heating "https://github.com/bruxy70/Heating") and changed to my needs.
Because I live in an apartement I don't have control over the boiler itself, so I removed this part from the script.
All my heating is underfloor and I have electric valves on a central point for the different rooms.
In each room I have a temperature and humidity sensor and according to those values, the valves for the heating get opened or closed.

# Installation

1. This requires AppDeamon installed and configured (follow the documentation on their web site).
2. Make sure that `voluptuous` and `datetime` are incuded in the `python_packages` option
3. Copy the content of the appdaemon directory from this repository to your home assistant `/config/appdaemon` folder
4. Add configuration to your Home Assistant's `/config/appdaemon/apps/apps.yaml`


# Configuration

This is the configuration that goes into `/config/appdaemon/apps/apps.yaml`

## Example:
```yaml
heating-control:
  module: heating-control
  class: HeatingControl
  somebody_home: input_boolean.jemand_zuhause
  day_night: input_boolean.heizung_tag_nacht
  heating_mode: input_select.heizungs_modus
  temperature_vacation: input_number.heizung_temperatur_ferien
  rooms:
  - sensor: sensor.esszimmer_aqara_temperatursensor_temperature
    temperature_day: input_number.esszimmer_heizung_temperatur_tag
    temperature_night: input_number.esszimmer_heizung_temperatur_nacht
    room_name: Esszimmer
    heating_valves:
    - switch.sonoff_heizung_essen
  - sensor: sensor.dusche_aqara_temperatursensor_temperature
    temperature_day: input_number.dusche_heizung_temperatur_tag
    temperature_night: input_number.dusche_heizung_temperatur_nacht
    manual_mode: input_boolean.dusche_heizung_manuell
    room_name: Dusche
    heating_valves:
    - switch.sonoff_heizung_dusche
```

## Parameters:
|Attribute |Required|Description
|:----------|----------|------------
| `module` | Yes | Always `heating-control`
| `class` | Yes | Always `HeatingControl`
| `somebody_home` | Yes | entity_id of the boolean value that is on when somebody is home and off otherwise
| `day_night` | Yes | entity_id of the boolean switch between high/low (day/night). This is on for 'day', off for 'night'
| `heating_mode` | Yes | entity_id of the input select with heating modes. Can contain the values `On`, `Off` and `Vacation` - these values can be changed - se the bottom of this README. Not all values have to be defined.
| `temperature_vacation` | Yes | entity_id of the input containg the temperature to be used for vacation mode
| `rooms` | Yes | List of rooms - see bellow

## Room parameters
|Attribute |Required|Description
|:----------|----------|------------
| `sensor` | Yes | entity_id of the temperature sensor
| `temperature_day` | Yes | entity_id of the input containg the high (or day) temperature for the given room
| `temperature_night` | Yes | entity_id of the input containg the low (or night) temperature for the given room
| `manual_mode` | No | entity_id of a boolean switch. If 'on' then the script will ignore the current temperature
| `room_name` | Yes | Name or description of the room
| `heating_valves` | Yes | list of thermostat entity_ids


## Other configuration
The `heating-control.py` file uses constants for 3 heating modes. If you'd like to name your modes differently, you can change them there. The values should be in lowercase.
```python
MODE_ON = "on"
MODE_OFF = "off"
MODE_VACATION = "vacation"
```
