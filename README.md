# Anova Precision Oven for Home Assistant

Token-based Home Assistant integration for the Anova Precision Oven (`oven_v1`), built on the
reverse-engineered Anova cloud websocket API (`wss://devices.anovaculinary.io`).

Every oven paired to the account shows up as its own device, driven by one shared websocket
connection with automatic reconnect.

## Installation

1. HACS → three-dot menu → Custom repositories → add this repository as type **Integration**.
2. Install **Anova Precision Oven** and restart Home Assistant.
3. Settings → Devices & services → Add integration → **Anova Precision Oven**.
4. Paste the access token (the string starting with `anova-`).

## Entities per oven

| Platform | Entities |
|---|---|
| `climate` | Oven: current cavity temperature, setpoint, heat/off, fan mode, cook context attributes |
| `sensor` | Mode, cavity temp + setpoint, wet bulb temp + setpoint, top/bottom cavity temp, probe temp + target, relative humidity, steam mode, steam percentage setpoint, evaporator temp/power, boiler temp/power, fan speed, timer mode/remaining/initial, per-element power, firmware, last connected, state updated |
| `binary_sensor` | Online, door, water tank empty, probe connected, lamp, vent, per-element running, descale required, boiler/evaporator/element/fan/triac/UI/dosing faults, cavity overheated |
| `number` | Target temperature, steam percentage, target humidity, fan speed, timer, probe target, rack position (settings for the next cook) |
| `select` | Bulb mode (dry/wet), steam mode, heating element preset |
| `button` | Start cook, Stop cook |

The `number` and `select` entities are the recipe for the next cook; `button.start_cook`,
`climate.set_temperature` and the `start_cook` service apply them.

## Services

- `anova_apo.start_cook` — temperature, bulb mode, steam mode + percentage/humidity, fan speed,
  heating elements, vent, rack position, timer **or** probe target.
- `anova_apo.start_custom_cook` — raw multi-stage list, for anything the simple service cannot express.
- `anova_apo.stop_cook` — stop the running cook.

## Events

- `anova_apo_target_reached` — fired with `cooker_id` and `reason` (`probe` or `timer`).

## Known limits of the cloud API

- The API only accepts whole cooks. Changing temperature mid-cook restarts the cook with the new
  stage list; the oven keeps heating, but the timer restarts.
- Timer and probe target are mutually exclusive in one stage.
- Lamp, vent and door are readable but not separately controllable.
- Fan speed is accepted in the stage payload, but ovens have been observed reporting 100% regardless.
- Unofficial API. Anova can break it at any time.

## Credits

Protocol documentation: [bogd/anova-oven-api](https://github.com/bogd/anova-oven-api)
and [andr83/hacs-anova-oven](https://github.com/andr83/hacs-anova-oven).
