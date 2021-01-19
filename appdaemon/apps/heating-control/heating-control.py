import appdaemon.plugins.hass.hassapi as hass
from enum import Enum
import voluptuous as vol
import voluptuous_helper as vol_help
from datetime import datetime, time, timedelta

"""
Turns the heating valves on or off according to the temperature sensors in every room.
For the documentation see https://github.com/codingphildotdev/Heating
"""

# Here you can change the modes set in the mode selector (in lower case)
MODE_ON = "on"
MODE_OFF = "off"
MODE_VACATION = "vacation"

HYSTERESIS = 0.3  # Difference between the temperature to turn heating valves on and off (to avoid frequent switching)
LOG_LEVEL = "INFO"

# Other constants - do not change
ATTR_SOMEBODY_HOME = "somebody_home"
ATTR_HEATING_MODE = "heating_mode"
ATTR_TEMPERATURE_VACATION = "temperature_vacation"
ATTR_ROOMS = "rooms"
ATTR_DAYNIGHT = "day_night"
ATTR_TEMPERATURE_DAY = "temperature_day"
ATTR_TEMPERATURE_NIGHT = "temperature_night"
ATTR_SENSOR = "sensor"
ATTR_HEATING_VALVES = "heating_valves"
ATTR_MANUAL_MODE = "manual_mode"
ATTR_ROOM_NAME = "room_name"
ATTR_CURRENT_TEMP = "current_temperature"
ATTR_HVAC_MODE = "hvac_mode"
ATTR_HVAC_MODES = "hvac_modes"
ATTR_TEMPERATURE = "temperature"
ATTR_UNKNOWN = "unknown"
ATTR_UNAVAILABLE = "unavailable"


class HeatingControl(hass.Hass):
    def initialize(self):
        """Read all parameters. Set listeners. Initial run"""

        # Configuration validation schema
        ROOM_SCHEMA = vol.Schema(
            {
                vol.Required(ATTR_SENSOR): vol_help.existing_entity_id(self),
                vol.Required(ATTR_TEMPERATURE_DAY): vol_help.existing_entity_id(self),
                vol.Required(ATTR_TEMPERATURE_NIGHT): vol_help.existing_entity_id(self),
                vol.Required(ATTR_HEATING_VALVES): vol.All(
                    vol_help.ensure_list, [vol_help.existing_entity_id(self)]
                ),
                vol.Required(ATTR_ROOM_NAME): str,
                vol.Optional(ATTR_MANUAL_MODE): vol_help.existing_entity_id(self),
            },
        )
        APP_SCHEMA = vol.Schema(
            {
                vol.Required("module"): str,
                vol.Required("class"): str,
                vol.Required(ATTR_ROOMS): vol.All(vol_help.ensure_list, [ROOM_SCHEMA]),
                vol.Required(ATTR_DAYNIGHT): vol_help.existing_entity_id(self),
                vol.Required(ATTR_SOMEBODY_HOME): vol_help.existing_entity_id(self),
                vol.Required(ATTR_TEMPERATURE_VACATION): vol_help.existing_entity_id(
                    self
                ),
                vol.Required(ATTR_HEATING_MODE): vol_help.existing_entity_id(self),
            },
            extra=vol.ALLOW_EXTRA,
        )
        __version__ = "0.0.2"  # pylint: disable=unused-variable
        self.__log_level = LOG_LEVEL
        try:
            config = APP_SCHEMA(self.args)
        except vol.Invalid as err:
            self.error(f"Invalid format: {err}", level="ERROR")
            return

        # Read and store configuration
        self.__rooms = config.get(ATTR_ROOMS)
        self.__somebody_home = config.get(ATTR_SOMEBODY_HOME)
        self.__heating_mode = config.get(ATTR_HEATING_MODE)
        self.__temperature_vacation = config.get(ATTR_TEMPERATURE_VACATION)
        self.__daynight = config.get(ATTR_DAYNIGHT)

        # Listen to events
        self.listen_state(self.somebody_home_changed, self.__somebody_home)
        self.listen_state(
            self.vacation_temperature_changed, self.__temperature_vacation
        )
        self.listen_state(self.mode_changed, self.__heating_mode)
        self.listen_state(self.daynight_changed, self.__daynight)
        # Listen to events for temperature sensors and heating_valves
        for room in self.__rooms:
            self.listen_state(self.target_changed, room[ATTR_TEMPERATURE_DAY])
            self.listen_state(self.target_changed, room[ATTR_TEMPERATURE_NIGHT])
            self.listen_state(self.temperature_changed, room[ATTR_SENSOR])
            if ATTR_MANUAL_MODE in room:
                self.listen_state(self.manual_mode_changed, room[ATTR_MANUAL_MODE])
            else:
                room[ATTR_MANUAL_MODE] = None

        # Initial update
        self.__update_heating_valves()
        self.log("Ready for action...")

    def mode_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: mode changed on/off/vacation"""
        self.log("Heating changed, updating heating_valves")
        self.__update_heating_valves()

    def vacation_temperature_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: target vacation temperature"""
        if self.get_mode() == MODE_VACATION:
            self.__update_heating_valves()

    def somebody_home_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: house is empty / somebody came home"""
        if new.lower() == "on":
            self.log("Somebody came home.", level=self.__log_level)
        elif new.lower() == "off":
            self.log("Nobody home.", level=self.__log_level)
        self.__update_heating_valves()

    def temperature_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: target temperature changed"""
        self.__update_heating_valves(sensor_entity=entity)

    def daynight_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: day/night changed"""
        self.log("updating daynight")
        self.__update_heating_valves()

    def target_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: target temperature"""
        for room in self.__rooms:
            if (
                room[ATTR_TEMPERATURE_DAY] == entity
                or room[ATTR_TEMPERATURE_NIGHT] == entity
            ):
                self.__update_heating_valves(sensor_entity=room[ATTR_SENSOR])

    def manual_mode_changed(self, entity, attribute, old, new, kwargs):
        """Event handler: manual mode in room changed"""
        self.log(f"Manual mode room {entity} new value: {new}")
        self.__update_heating_valves()

    def is_manual_mode_on(self, room) -> bool:
        """Is manual mode on?"""
        if(room[ATTR_MANUAL_MODE] is not None):
            self.log(f"Manual mode {room[ATTR_MANUAL_MODE]} is {self.get_state(room[ATTR_MANUAL_MODE])}")
            return bool(self.get_state(room[ATTR_MANUAL_MODE]) == "on")
    
    def is_somebody_home(self) -> bool:
        """Is somebody home?"""
        return bool(self.get_state(self.__somebody_home).lower() == "on")

    def get_mode(self) -> str:
        """Get heating mode off/on/auto/eco/vacation"""
        return self.get_state(self.__heating_mode).lower()

    def __set_heating_valves(
        self, entity_id: str, target_temp: float, current_temp: float
    ):
        """Check if Heating is off"""
        if(self.get_mode() == MODE_OFF):
            self.log("Heating mode is OFF")
            self.call_service("switch/turn_off", entity_id=entity_id)
            self.log(f"Turn off: {entity_id}")
            return None
        """Set the thermostat attrubutes and state"""
        if target_temp is None:
            target_temp = self.__get_target_temp(sensor=entity_id)
        if current_temp is None:
            current_temp = self.__get_current_temp(sensor=entity_id)
        self.log(
            f"Updating heating valve {entity_id}: "
            f"temperature {target_temp}, "
            f"current temperature {current_temp}."
        )
        if current_temp is not None and target_temp > (current_temp + HYSTERESIS):
            self.call_service("switch/turn_on", entity_id=entity_id)
            self.log(f"Turn on: {entity_id}")
        if current_temp is not None and target_temp <= current_temp:
            self.call_service("switch/turn_off", entity_id=entity_id)
            self.log(f"Turn off: {entity_id}")
            self.log(" ")

    def __get_target_room_temp(self, room) -> float:
        """Returns target room temparture, based on day/night switch (not considering vacation)"""
        if bool(self.get_state(self.__daynight).lower() == "on"):
            return float(self.get_state(room[ATTR_TEMPERATURE_DAY]))
        else:
            return float(self.get_state(room[ATTR_TEMPERATURE_NIGHT]))

    def __get_target_temp(self, sensor: str = None) -> float:
        """Get target temperature (basd on day/night/vacation)"""
        if self.get_mode() == MODE_VACATION:
            return float(self.get_state(self.__temperature_vacation))
        if sensor is None:
            return None
        for room in self.__rooms:
            if room[ATTR_SENSOR] == sensor:
                return self.__get_target_room_temp(room)
        return None 

    def __get_current_temp(self, sensor: str = None) -> float:
        """Get current temperature (from temperature sensor)"""
        if sensor is not None:
            return float(self.get_state(sensor))
        for room in self.__rooms:
            if sensor in room[ATTR_SENSOR]:
                return float(self.get_state(room[ATTR_SENSOR]))
        return None

    def __update_heating_valves(self, thermostat_entity: str = None, sensor_entity: str = None):
        """Set the thermostats target temperature, current temperature and heating mode"""
        vacation = self.get_mode() == MODE_VACATION
        vacation_temperature = float(self.get_state(self.__temperature_vacation))

        for room in self.__rooms:
            if (
                (thermostat_entity is None and sensor_entity is None)
                or (thermostat_entity in room[ATTR_HEATING_VALVES])
                or (sensor_entity == room[ATTR_SENSOR])
            ):
                self.log(f"Room: {room[ATTR_ROOM_NAME]}")
                if self.is_manual_mode_on(room):
                    continue
                self.log(f"updating sensor {room[ATTR_SENSOR]}")
                temperature = float(self.get_state(room[ATTR_SENSOR]))
                target_temperature = self.__get_target_room_temp(room)
                for heating_valve in room[ATTR_HEATING_VALVES]:
                    if vacation:
                        self.__set_heating_valves(
                            heating_valve, vacation_temperature, temperature
                        )
                    else:
                        self.__set_heating_valves(
                            heating_valve, target_temperature, temperature
                        )
