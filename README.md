# Thesis-Datenspec

Shared specification of the data format between the measurement device (Raspberry Pi
Pico 2 W, MicroPython) and the analysis software on the laptop (CPython). The device
writes records as JSON Lines to an SD card and publishes them via MQTT.

The Pydantic v2 models in `src/datenspec/models/` are the **single source of truth**.
Everything else is generated from them and checked in:

| Artefact | Path | Consumer |
|---|---|---|
| Pydantic models, helpers | `src/datenspec/` | analysis software (`pip install`) |
| JSON Schemas (header, one per record kind, the profile file) | `schemas/*.schema.json` | any tooling |
| MicroPython constants | `pico/datenspec_const.py` | firmware (submodule or copy) |
| AsyncAPI 3.0 | `asyncapi/asyncapi.yaml` | documentation, tooling |
| Field and topic reference | this README | humans |
| Example records | `examples/valid`, `examples/invalid` | tests, firmware developers |

## Use

Analysis software, pinned to a release tag:

```bash
pip install "datenspec @ git+https://github.com/EinHerzfuerSci-Fi/Thesis-Datenspec@v0.3.0"
```

```python
from datenspec.models import parse_laptop_message, parse_record
from datenspec.dedup import deduplicate
from datenspec.timestamps import fill_missing_ts
from datenspec.tcs3448 import capture_flags, full_scale, integration_time_ms

record = parse_record(
    line
)  # one JSON line from the Pico -> DataRecord | RunStartRecord | ...
message = parse_laptop_message(
    line
)  # from the laptop -> CmdStart | CmdStop | SessionMessage | ...
```

Reading the SD card files and the calibrated TCS3448 analysis (basic counts, gain
correction, dark subtraction, XYZ) live in the analysis software, not here.

Firmware: copy `pico/datenspec_const.py` or include this repository as a submodule. The
file contains only `NAME = literal` constants; nothing else is imported on the Pico.

## Development

Requires Python ≥ 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m datenspec.codegen
```

```bash
uv run python -m datenspec.codegen --check
```

```bash
uv run pytest
```

The first command regenerates every derived file, including the reference section of
this README. `--check` only compares and exits with 1 if anything is stale; the tests do
the same, so a model change without regenerating fails. PyCharm run configurations for
both are in `.run/`.

## Versioning

- **`v` (schema version)** is an integer in every record. It increases only on
  breaking changes: removing or renaming a field, changing a type or unit, making an
  optional field required.
- **Non-breaking** and without a new `v`: a new optional field, a new optional group,
  a new sensor under `m`. Such additions get `default=None`, so records from older
  firmware stay valid, and `Since v` in the reference records when they appeared.
- **The package** is versioned with SemVer and released via Git tags (`v0.1.0`). The
  generated files carry both versions in their header.
- **v2** added runs (`run` in the header, the `run` kind), per-kind `seq`, and the kinds
  `log`, `ack`, `cmd`, `session`, `annotation` and `tag`. v1 was never deployed, so the
  models accept only `v: 2` and there is no v1 reader. v2 itself was changed before
  first deployment (package 0.3.0, see the changelog).

A new record kind (a new value of `k`) is not backwards compatible: older readers reject
the whole line. Prefer a new optional group in an existing record.

## Conventions

- **Units** are fixed per field in the schema (`x-unit`), never sent in the record:
  temperature °C, relative humidity and duty cycle as fraction 0…1 (not percent),
  voltage V, time s, fields ending in `_ms` / `_hz` / `_nm` in ms / Hz / nm, RSSI dBm,
  memory and storage in bytes.
- **Short names on the wire.** Where it helps readability, the Python attribute has a
  descriptive name and the wire name is its alias (`rh` ↔ `relative_humidity`). The
  schemas, the Pico constants and this reference always use the wire name.
- **Failed sensor = `null`.** The key stays in the record; a missing key is an error.
  The same holds for groups whose subsystem has nothing to report (`tele.wlan` while not
  associated, `tele.ntp` before the first sync, `info.sd` without a card). Groups whose
  state is itself the information (`tele.mqtt`, `tele.sd`) are never `null`.
- **Unknown fields are ignored at runtime**, so an older analysis version can read
  records from newer firmware with additional optional fields. The tests in this repo
  validate with `forbid_extra=True` instead, so a typo in an example fails:

  ```python
  parse_record(line)  # runtime: unknown fields ignored
  parse_record(line, forbid_extra=True)  # tests: unknown fields rejected
  ```

- **Strict types.** No coercion: `"1.5"` is not a number, `1.0` is not an integer.
- **Record identity.** `seq` counts per record kind: for `data` per run, restarting at
  0 with every run; for all other kinds per boot. The unique key is `(dev, run, seq)`
  for `data` and `(dev, boot, k, seq)` otherwise, so a loss shows up as a gap in its own
  kind, and a kind sent only over MQTT or only to SD causes no false gaps elsewhere.
  Duplicates from QoS 1 or SD replay are expected; `datenspec.dedup.deduplicate` keeps
  the first and reports conflicting content.
- **Two senders.** Records come from the Pico and carry the full header. `cmd`,
  `session`, `annotation` and `tag` come from the laptop and carry only `v` and `k`;
  they are parsed with `parse_laptop_message`.

## Runs and commands

- **A run** (measurement series) is decided by the firmware. It sends a `run` record
  with `ev: "start"` before the first `data` record and one with `ev: "end"` after the
  last. Every Pico record carries `run`, `null` outside a run; `data` only exists
  within a run.
- **Run IDs** come from a counter on flash, like `boot`. The firmware increments and
  writes it before sending the start record, so a power loss can skip an ID but never
  reuse one. `(dev, run)` identifies a run.
- **One boot per run.** Start and end record are sent in the same boot; a run
  interrupted by a reboot is not resumed. So `up` and `seq` of the end record are
  greater than those of the start record (`up` may be equal).
- **Missing end.** A run whose end record never arrives (power loss, crash) is marked
  `aborted` by the pipeline. The device never sends that reason. `n_data` in the end
  record gives the number of `data` records, so losses within a run can be counted.
- **Commands.** The laptop publishes `cmd` on `thesis/<device_id>/cmd` or
  `thesis/all/cmd`; the target is the topic, not the payload. Every device that gets a
  command answers with an `ack` carrying the command's `id` as `cmd_id`. `stop` names
  the run to stop; a device ignores it (`res: "rejected"`) if that is not its active
  run, so a late or repeated stop cannot end the next run.
- **Profiles** say how a run measures (sample interval, capture sequence and timing);
  the run says when. The device keeps them in a profile file, a map from name to
  settings (`schemas/profiles.schema.json`, model `ProfileFile`). `cmd start` names
  one in `profile`, or `null` for the device's default; an unknown name is answered
  with `res: "rejected"`. `info.profiles` lists the names and the default, so the
  laptop can check a name before sending. The run's start record carries the profile
  name and its resolved settings as `cfg`, which apply for the whole run: read the
  settings there, not from the profile file, which may have changed since.
- **Sessions, annotations and tags** go from the laptop to the pipeline only, on
  `thesis/laptop/session`, `thesis/laptop/annotation` and `thesis/laptop/tag`. They are
  named after the sender because they belong to no single device. All carry an `id`
  generated by the CLI, so the pipeline can drop QoS 1 duplicates. Devices neither
  publish nor subscribe there, so the Pico constants leave these topics out.
- **Tags** are key/value pairs on a run (`dev`, `run`). Every `tag` message is kept as
  history; the current value of a key is the one with the newest `ts`, and `value:
  null` deletes it. A tag may arrive before the run's start record.


## Time: `up` and `ts`

Every record carries `up` (seconds since boot, monotonic, millisecond resolution) and
`ts` (Unix seconds UTC, `null` until NTP has synced), captured at the same moment:
the time of the measurement or event, not of sending.

- **Missing `ts` can be reconstructed within a boot.** For any synced record, `ts − up`
  is the boot's clock offset; apply it to unsynced records of the same boot.
  `datenspec.timestamps.fill_missing_ts` uses the offset of the nearest synced record
  (in `up`) and reports which values were reconstructed. Offsets never carry over to
  another boot, because `up` restarts at 0.
- **Compute intervals from `up`, not `ts`.** `ts` can jump when NTP re-syncs;
  `up` cannot.
- **The firmware must protect `up` against tick counter overflow.** MicroPython's
  `time.ticks_ms()` wraps after about 12.4 days; `up` has to be accumulated with
  `ticks_diff` so it keeps increasing across the wrap.

## Sensors

- **DS18B20** (1-Wire): exactly one per device, identified by its ROM ID, which `info`
  reports as `ds18b20.rom` and `data` uses as the only key of `m.ds18b20`. 85.0 °C is
  the power-on default; the firmware should report it as `null`. If it is sent anyway,
  it is accepted and `Measurements.ds18b20_suspect()` lists the affected ROM IDs.
- **DHT22**: `t` in °C, `rh` as fraction 0…1.
- **TCS3448** (18-slot SMUX): the 13 spectral channels are sent, not the slots;
  `vis_2` and `vis_3` (VIS from the 2nd and 3rd SMUX cycle) are optional and reveal
  light changes during a measurement. Flicker slots (5, 11, 17) are not sent. Each
  cycle has exactly one `dark` capture (all LEDs off) for ambient subtraction.
  - Integration time = (atime + 1) × (astep + 1) × 2.78 µs
  - Full scale = min(65535, (atime + 1) × (astep + 1)); computed, not sent
  - `gain` is an index 0…12 for the factors 0.5, 1, 2, …, 2048; with AGC it is the
    gain actually used, read back after the measurement.
  - `lux`, `cct`, `cie_x`, `cie_y` are derived on the device with the vendor library;
    the raw counts are authoritative.
  - `datenspec.tcs3448.capture_flags` flags saturated captures and channels at or
    above 90 % of full scale.
- **LEDs** `nir`, `blue`, `vis`: driven by PIO in sync with the TCS3448, dimmed by
  PWM, never switched during an integration. The duty cycle in `led` is a setpoint;
  light output is neither linear in duty cycle nor independent of LED temperature.

## Limits of the JSON Schemas

Some rules exist only as validators in the Pydantic models and are **not** in the
exported JSON Schemas. A consumer that validates with the schemas alone (e.g. AsyncAPI
tooling) accepts records that break them:

- `data`: exactly one `dark` capture per cycle; all LED duty cycles 0 in the `dark`
  capture
- `tele`: `buf.fill` ≤ `buf.cap`; `ntp.last_up` ≤ `up`
- `info`: the `vis` LED has `peak_nm: null`; `ds18b20.rom` is set exactly when
  `sensors.ds18b20` is true; `sd.free` ≤ `sd.total`; `profiles.names` has no
  duplicates and contains `profiles.default`
- `run` and the profile file: `cfg.capture.sequence` has exactly one `dark`;
  `cfg.capture.gain_control.stages` is `null` exactly when `mode` is `fixed`, and
  otherwise holds at least two strictly ascending gain indices
- `alert`: `thr` is required when `val` is set (this one is in the schema as
  `dependentRequired` and in the model); `ref_seq` is `null` exactly when `run` is
  `null` (in the schema as `if`/`then`/`else` and in the model)
- `annotation`: `run` requires `dev` (in the schema as `if`/`then` and in the model)

Rules across two records (the end of a run after its start, the captures of a
`data` record matching its run's `cfg.capture.sequence`, every capture `gain` of a
regulated run being one of its `cfg.capture.gain_control.stages`) are in neither.

The AsyncAPI file declares the payload schema format as JSON Schema 2020-12, which
AsyncAPI tools are not required to support (only draft-07 is mandatory).

## Examples

`examples/valid/<kind>.jsonl` holds wire records, one per line, as written to the SD
card (Pico kinds) or published by the laptop (`cmd`, `session`, `annotation`, `tag`). `examples/invalid/<kind>.jsonl` holds one test case per line:

```json
{"case": "rh in percent instead of fraction", "loc": ["data", "m", "dht22", "rh"], "record": {...}}
```

`loc` is where validation must fail; every error has to lie below it.
`"strict_only": true` marks cases that fail only with `forbid_extra` and are accepted
at runtime.

<!-- BEGIN GENERATED: reference (python -m datenspec.codegen) -->

## MQTT topics

| Topic | From → to | QoS | Retain | Payload | Description |
|---|---|---|---|---|---|
| `thesis/{device_id}/data` | pico → pipeline | 1 | no | `data` | One measurement cycle per message. |
| `thesis/{device_id}/tele` | pico → pipeline | 1 | no | `tele` | Periodic health snapshot, about every 60 s. |
| `thesis/{device_id}/alert/{alarm_id}` | pico → pipeline | 1 | yes | `alert` | Sent on raised/cleared transitions only. |
| `thesis/{device_id}/err` | pico → pipeline | 1 | no | `err` | Module errors. |
| `thesis/{device_id}/log` | pico → pipeline | 1 | no | `log` | Firmware log messages. |
| `thesis/{device_id}/info` | pico → pipeline | 1 | yes | `info` | Boot-time configuration, once per boot. |
| `thesis/{device_id}/run` | pico → pipeline | 1 | no | `run` | Start and end of a run. |
| `thesis/{device_id}/status` | pico → pipeline | 1 | yes | text/plain | Plain text "online" \| "offline"; also the MQTT Last Will. |
| `thesis/{device_id}/cmd` | laptop → pico | 1 | no | `cmd` | Command to one device. |
| `thesis/all/cmd` | laptop → pico | 1 | no | `cmd` | Command to all devices; each answers with its own ack. |
| `thesis/{device_id}/cmd/ack` | pico → pipeline | 1 | no | `ack` | Answer to a cmd. |
| `thesis/laptop/session` | laptop → pipeline | 1 | no | `session` | Creates a session. |
| `thesis/laptop/annotation` | laptop → pipeline | 1 | no | `annotation` | Time-stamped note. |
| `thesis/laptop/tag` | laptop → pipeline | 1 | no | `tag` | Sets or deletes a key/value tag on a run. |

## Field reference

Nested fields use dotted paths; `[]` marks list elements. `Since v` is the schema version that introduced the field.

### Header (every record from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `v` | integer (2…2) |  | required | Version of the schema. Increased only on breaking changes. | 1 |
| `k` | "data" \| "alert" \| "tele" \| "err" \| "info" \| "log" \| "run" \| "ack" |  | required | Record kind. | 1 |
| `dev` | string `^[0-9a-f]{16}$` |  | required | Hardware ID of the microcontroller | 1 |
| `fw` | string (SemVer) |  | required | Firmware version (optionally containing the git commit hash) | 1 |
| `boot` | integer (≥ 0) |  | required | Boot counter, stored on flash memory of the microcontroller. | 1 |
| `run` | integer (≥ 0) \| null |  | required | ID of the run (measurement series) this record belongs to; null outside a run. Unique per device: a counter stored on flash like boot, incremented and written before the run's start record, so a power loss can skip an ID but never reuse one. (dev, run) identifies a run. | 2 |
| `seq` | integer (≥ 0) |  | required | Sequence number per record kind, for dedup (QoS 1, SD replay) and gap detection per kind. For data it counts per run and restarts at 0 with every run; for all other kinds it counts per boot. Unique key: (dev, run, seq) for data, (dev, boot, k, seq) for all other kinds. | 1 |
| `up` | number (≥ 0.0) | s | required | Monotonic seconds since boot, ms resolution. Time of measurement/event, not of sending. Use for intervals: ts may jump on re-sync. | 1 |
| `ts` | integer (≥ 0) \| null | s | required | Unix seconds UTC after NTP sync, captured together with up. null while unsynced; key is mandatory. | 1 |

### `data` (`"k": "data"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `run` | integer (≥ 0) |  | required | ID of the run this cycle belongs to; data exists only within a run. | 2 |
| `m` | object |  | required | One key per sensor; null means the sensor did not respond. Sensors added later are optional (default null). | 1 |
| `m.ds18b20` | map `^[0-9a-f]{16}$` → (number (-55.0…125.0) \| null) \| null | °C | required | Temperature keyed by ROM ID. Each device has exactly one DS18B20, so the map holds exactly this one key (info.ds18b20.rom). null if the bus does not respond. Firmware should send a failed conversion as null value; 85.0 (power-on default) is accepted but flagged as suspect. | 1 |
| `m.dht22` | object \| null |  | required | Temperature and humidity; null as a whole if the sensor does not respond. | 1 |
| `m.dht22.t` | number (-40.0…80.0) \| null | °C | required | Air temperature. | 1 |
| `m.dht22.rh` | number (0.0…1.0) \| null | 1 | required | Relative humidity as fraction, not percent. | 1 |
| `m.tcs3448` | array of object \| null |  | required | Captures in acquisition order, each under different illumination. | 1 |
| `m.tcs3448[].ill` | "dark" \| "nir" \| "blue" \| "vis" |  | required | Illumination during this capture; dark means all LEDs off. | 1 |
| `m.tcs3448[].led` | object |  | required | Duty-cycle setpoint per LED. Model, not dict, so all three LEDs are required. | 1 |
| `m.tcs3448[].led.nir` | number (0.0…1.0) | 1 | required | PWM duty-cycle setpoint. Light output is neither linear in duty cycle nor independent of LED temperature. | 1 |
| `m.tcs3448[].led.blue` | number (0.0…1.0) | 1 | required | PWM duty-cycle setpoint. Light output is neither linear in duty cycle nor independent of LED temperature. | 1 |
| `m.tcs3448[].led.vis` | number (0.0…1.0) | 1 | required | PWM duty-cycle setpoint. Light output is neither linear in duty cycle nor independent of LED temperature. | 1 |
| `m.tcs3448[].dt` | integer | ms | required | Start of integration relative to the record's up. | 1 |
| `m.tcs3448[].gain` | integer (0…12) |  | required | Gain index 0..12 (factor 0.5..2048) actually used; read back from the status register when AGC is active. | 1 |
| `m.tcs3448[].atime` | integer (0…255) |  | required | Integration time = (atime+1)*(astep+1)*2.78 us. | 1 |
| `m.tcs3448[].astep` | integer (0…65534) |  | required | See atime. Full scale = min(65535, (atime+1)*(astep+1)), computed, not sent. | 1 |
| `m.tcs3448[].raw` | object |  | required | Raw 16-bit counts per spectral channel. Flicker slots (5, 11, 17) are not sent. | 1 |
| `m.tcs3448[].raw.f1` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f2` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f3` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f4` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f5` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f6` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f7` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.f8` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.fz` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.fy` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.fxl` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.nir` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.vis` | integer (0…65535) | counts | required | Raw count of this spectral channel. | 1 |
| `m.tcs3448[].raw.vis_2` | integer (0…65535) \| null | counts | optional | VIS from the 2nd SMUX cycle; differs from vis if light changed mid-measurement. | 1 |
| `m.tcs3448[].raw.vis_3` | integer (0…65535) \| null | counts | optional | VIS from the 3rd SMUX cycle. | 1 |
| `m.tcs3448[].sat` | boolean |  | required | Analog or digital saturation. | 1 |
| `m.tcs3448[].lux` | number \| null | lx | optional | Illuminance. | 1 |
| `m.tcs3448[].cct` | number \| null | K | optional | Correlated colour temperature. | 1 |
| `m.tcs3448[].cie_x` | number \| null | 1 | optional | CIE chromaticity x. | 1 |
| `m.tcs3448[].cie_y` | number \| null | 1 | optional | CIE chromaticity y. | 1 |

### `alert` (`"k": "alert"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | "temp_high" \| "temp_low" \| "humidity_high" |  | required | Alarm that changed state; also the last topic level. | 1 |
| `state` | "raised" \| "cleared" |  | required | New state. Sent only on transitions, with hysteresis in firmware. | 1 |
| `src` | string |  | required | Source of the alert. | 1 |
| `val` | number \| null |  | optional | Value that triggered the transition, in the unit of the monitored quantity. | 1 |
| `thr` | number \| null |  | optional | Threshold that was crossed, same unit as val. | 1 |
| `sev` | "warn" \| "crit" |  | required | Severity of the alarm. | 1 |
| `ref_seq` | integer (≥ 0) \| null |  | required | seq of the data record that triggered the transition, in the run given by run: the record's key is (dev, run, ref_seq). null exactly when run is null: alarms are watched outside runs too, where there is no data record. | 1 |

### `tele` (`"k": "tele"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `sys` | object |  | required | Microcontroller health. | 1 |
| `sys.mem_free` | integer (≥ 0) | B | required | Free heap memory. | 1 |
| `sys.cpu_temp` | number | °C | required | Chip temperature. | 1 |
| `sys.vsys` | number \| null | V | required | null if not measurable on this board. | 1 |
| `wlan` | object \| null |  | required | null while not associated with an access point. | 1 |
| `wlan.rssi` | integer | dBm | required | Signal strength of the access point. | 1 |
| `wlan.ssid` | string |  | required | SSID of the access point. | 1 |
| `mqtt` | object |  | required | MQTT client state and counters. | 1 |
| `mqtt.state` | "DISCONNECTED" \| "CONNECTED" \| "DEGRADED" |  | required | Connection state of the MQTT client. | 1 |
| `mqtt.reconnects` | integer (≥ 0) |  | required | Number of reconnects to the broker. | 1 |
| `mqtt.pub_ok` | integer (≥ 0) |  | required | Successful publishes. | 1 |
| `mqtt.pub_fail` | integer (≥ 0) |  | required | Failed publishes. | 1 |
| `sd` | object |  | required | SD card storage. | 1 |
| `sd.state` | "DISCONNECTED" \| "CONNECTED" \| "DEGRADED" |  | required | State of the SD card storage. | 1 |
| `buf` | object |  | required | RAM buffer of records. | 1 |
| `buf.fill` | integer (≥ 0) |  | required | Records currently held in the RAM buffer. | 1 |
| `buf.cap` | integer (≥ 0) |  | required | RAM buffer capacity in records. | 1 |
| `ntp` | object \| null |  | required | null until the first successful NTP sync of this boot. | 1 |
| `ntp.last_up` | number (≥ 0.0) | s | required | up at the last successful NTP sync. | 1 |
| `ntp.last_corr` | number | s | required | Clock correction applied at the last NTP sync. | 1 |

### `err` (`"k": "err"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `module` | string |  | required | Module of the firmware the error originates from. | 1 |
| `reason` | string |  | required | Human-readable error description. | 1 |
| `code` | integer |  | required | Error code; its meaning depends on the module. | 1 |
| `state` | "DISCONNECTED" \| "CONNECTED" \| "DEGRADED" \| null |  | optional | State of the module at the time of the error. Only applicable if the module has a state. | 1 |

### `info` (`"k": "info"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `sys` | object |  | required | Device identity. | 1 |
| `sys.device_name` | string |  | required | Configurable device name used for better readability | 1 |
| `sys.reset_cause` | string |  | required | Cause of the last reset. | 1 |
| `sensors` | object |  | required | Sensors detected at boot. Firmware does not rescan, so this is not updated during the boot; data records show which sensors actually respond. Sensor configuration is in the per-sensor groups regardless of detection. | 1 |
| `sensors.ds18b20` | boolean |  | required | The DS18B20 was found on the bus. | 1 |
| `sensors.dht22` | boolean |  | required | DHT22 responded. | 1 |
| `sensors.tcs3448` | boolean |  | required | TCS3448 responded. | 1 |
| `ds18b20` | object |  | required | DS18B20 configuration. | 1 |
| `ds18b20.resolution_bits` | integer (9…12) |  | required | Configured conversion resolution. | 1 |
| `ds18b20.rom` | string `^[0-9a-f]{16}$` \| null |  | required | ROM ID of the device's only DS18B20; also the key in data m.ds18b20. null if none was found. | 2 |
| `tcs3448` | object |  | required | TCS3448 configuration. | 1 |
| `tcs3448.smux_mode` | integer |  | required | SMUX mode of the TCS3448. | 1 |
| `tcs3448.agc` | boolean |  | required | Whether the active run regulates the TCS3448 gain, i.e. its cfg.capture.gain_control.mode is not fixed; false outside a run. | 1 |
| `leds` | array of object |  | required | Illumination LEDs fitted to the device. | 1 |
| `leds[].id` | "nir" \| "blue" \| "vis" |  | required | LED ID; also the key in data led. | 1 |
| `leds[].peak_nm` | integer (> 0) \| null | nm | required | Peak wavelength; null for the broadband 'vis' LED. | 1 |
| `leds[].pin` | integer (≥ 0) |  | required | GPIO number. | 1 |
| `profiles` | object |  | required | Measurement profiles on the device. Their settings are not repeated here: they can change per run, so each run's start record carries them as cfg. | 2 |
| `profiles.names` | array of string `^[a-z0-9_]+$` |  | required | Profiles a start command can name, without duplicates. | 2 |
| `profiles.default` | string `^[a-z0-9_]+$` |  | required | Profile used when the start command names none, or the run is started on the device; one of names. | 2 |
| `pio` | object |  | required | PIO program that drives the LEDs in sync with the TCS3448. | 1 |
| `pio.hz` | integer (> 0) | Hz | required | PIO state machine clock. | 1 |
| `pio.prog` | string |  | required | PIO program version. | 1 |
| `pwm` | object |  | required | PWM dimming of the LEDs. | 1 |
| `pwm.hz` | integer (> 0) | Hz | required | LED dimming PWM frequency. | 1 |
| `pwm.sync` | boolean |  | required | Whether integration and PWM are phase-locked. | 1 |
| `sd` | object \| null |  | required | null if no SD card is mounted. | 1 |
| `sd.total` | integer (≥ 0) | B | required | Card capacity. | 1 |
| `sd.free` | integer (≥ 0) | B | required | Free space. | 1 |

### `log` (`"k": "log"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `lvl` | "debug" \| "info" \| "warn" \| "error" |  | required | Log level. | 2 |
| `module` | string |  | required | Module of the firmware the message originates from. | 2 |
| `msg` | string |  | required | Human-readable message. | 2 |
| `ctx` | object \| null |  | optional | Structured context as key/value pairs; not validated. | 2 |

### `run` (`"k": "run"`, from the Pico)

#### `"ev": "start"`

Start of a run; sent before its first data record.

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `run` | integer (≥ 0) |  | required | ID of the run that starts or ends. | 2 |
| `ev` | "start" |  | required | Run event. | 2 |
| `dur` | integer (> 0) \| null | s | required | Planned duration; null = unlimited, runs until stopped. | 2 |
| `session` | string (UUID) \| null |  | required | Session this run belongs to, taken from the start command; null if none. | 2 |
| `cmd_id` | string (UUID) \| null |  | required | id of the cmd that started the run; null if started on the device. | 2 |
| `profile` | string `^[a-z0-9_]+$` |  | required | Profile the run measures with: the one named in the start command, or the device's default profile if the command named none or the run was started on the device. | 2 |
| `cfg` | object |  | required | Settings of profile as resolved at the start, fixed for the whole run. Read these instead of the profile file, which may have changed since. | 2 |
| `cfg.sample_interval_ms` | integer (> 0) | ms | required | Interval between measurement cycles. | 2 |
| `cfg.capture` | object |  | required | Timing of one TCS3448 capture cycle. | 2 |
| `cfg.capture.sequence` | array of "dark" \| "nir" \| "blue" \| "vis" |  | required | illumination values in capture order; exactly one dark, as in data m.tcs3448. | 2 |
| `cfg.capture.settle_ms` | integer (≥ 0) | ms | required | LED settling time before integration starts. | 2 |
| `cfg.capture.on_ms` | integer (≥ 0) | ms | required | LED on-time per capture. | 2 |
| `cfg.capture.gain_control` | object |  | required | How the run picks the gain of each capture. | 2 |
| `cfg.capture.gain_control.mode` | "fixed" \| "ams" \| "dark" |  | required | fixed: every capture uses the gain its profile names. ams: the auto-gain search of ams AN001051, per illumination from one cycle to the next. dark: the gain of each lit capture predicted from the cycle's dark capture and the LED's share in the previous cycle. | 2 |
| `cfg.capture.gain_control.stages` | array of integer (0…12) \| null |  | required | Gain indices the regulation may choose from, ascending; every capture gain of the run is one of them. null exactly when mode is fixed. | 2 |

#### `"ev": "end"`

End of a run; sent after its last data record, in the same boot as the start record. Its up is greater than or equal to, and its seq greater than, those of the start record. This relates two records, so the models cannot check it.

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `run` | integer (≥ 0) |  | required | ID of the run that starts or ends. | 2 |
| `ev` | "end" |  | required | Run event. | 2 |
| `cmd_id` | string (UUID) \| null |  | required | id of the cmd that stopped the run; null if not ended by a command. | 2 |
| `reason` | "duration" \| "manual" \| "error" |  | required | Why the run ended: duration elapsed, manual stop (command or on the device), or error in the firmware. A run without an end record is marked aborted by the pipeline; the device never sends that. | 2 |
| `n_data` | integer (≥ 0) |  | required | Number of data records produced in this run. data seq starts at 0, so the run's data seq values are 0 to n_data - 1. | 2 |

### `ack` (`"k": "ack"`, from the Pico)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `cmd_id` | string (UUID) |  | required | id of the acknowledged cmd. | 2 |
| `res` | "ok" \| "rejected" \| "error" |  | required | ok: executed; rejected: not applicable in the current state (e.g. start while a run is active, stop with a non-matching run); error: failed while executing. | 2 |
| `msg` | string \| null |  | required | Human-readable detail for rejected or error; null if none. | 2 |

### Messages from the laptop

They carry only `v` and `k` as header, no `dev`, `boot` or `up`. `v` is as in the Pico header.

### `cmd` (`"k": "cmd"`, from the laptop)

#### `"act": "start"`

Start a run.

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | string (UUID) |  | required | Command ID; echoed as cmd_id in ack and run. | 2 |
| `act` | "start" |  | required | Action to perform. | 2 |
| `dur` | integer (> 0) \| null | s | required | Planned duration of the run; null = the device's configured default duration. | 2 |
| `session` | string (UUID) \| null |  | required | Session the run belongs to; null if none. | 2 |
| `profile` | string `^[a-z0-9_]+$` \| null |  | required | Profile to measure with; null = the device's default profile. A name the device does not have is answered with ack rejected. | 2 |
| `run` | null |  | required | Always null for start: the device assigns the run ID. | 2 |
| `ts` | number (≥ 0.0) | s | required | Send time on the laptop, Unix seconds UTC. | 2 |

#### `"act": "stop"`

Stop a run. The device ignores it (ack rejected) unless run is its active run.

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | string (UUID) |  | required | Command ID; echoed as cmd_id in ack and run. | 2 |
| `act` | "stop" |  | required | Action to perform. | 2 |
| `dur` | null |  | required | Always null for stop. | 2 |
| `session` | null |  | required | Always null for stop. | 2 |
| `profile` | null |  | required | Always null for stop. | 2 |
| `run` | integer (≥ 0) |  | required | Run to stop. | 2 |
| `ts` | number (≥ 0.0) | s | required | Send time on the laptop, Unix seconds UTC. | 2 |

### `session` (`"k": "session"`, from the laptop)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | string (UUID) |  | required | Session ID, generated by the CLI; referenced as session in cmd and run. | 2 |
| `title` | string |  | required | Short title. | 2 |
| `variety` | "normal" \| "calibration" \| "functional" \| "flowrate" |  | required | Kind of session; applies to all of its runs. | 2 |
| `ts` | number (≥ 0.0) | s | required | Creation time on the laptop, Unix seconds UTC. | 2 |

### `annotation` (`"k": "annotation"`, from the laptop)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | string (UUID) |  | required | Annotation ID, generated by the CLI; lets the pipeline drop duplicates from QoS 1. | 2 |
| `ts` | number (≥ 0.0) | s | required | Time the note refers to, Unix seconds UTC. | 2 |
| `text` | string |  | required | Note text. | 2 |
| `dev` | string `^[0-9a-f]{16}$` \| null |  | required | Device the note refers to; null if none. | 2 |
| `run` | integer (≥ 0) \| null |  | required | Run of dev the note refers to; requires dev. null if none. | 2 |
| `session` | string (UUID) \| null |  | required | Session the note refers to; null if none. | 2 |

### `tag` (`"k": "tag"`, from the laptop)

| Field | Type | Unit | Required | Description | Since v |
|---|---|---|---|---|---|
| `id` | string (UUID) |  | required | Tag message ID, generated by the CLI; lets the pipeline drop duplicates from QoS 1. | 2 |
| `dev` | string `^[0-9a-f]{16}$` |  | required | Device of the run. | 2 |
| `run` | integer (≥ 0) |  | required | Run of dev the tag belongs to. May arrive before the run's start record. | 2 |
| `key` | string `^[a-z0-9_]+$` |  | required | Tag name: lower case letters, digits and _. | 2 |
| `value` | string \| null |  | required | Tag value; null deletes the tag. | 2 |
| `ts` | number (≥ 0.0) | s | required | Time on the laptop, Unix seconds UTC; the newest ts per key is the current value. | 2 |

<!-- END GENERATED: reference -->
