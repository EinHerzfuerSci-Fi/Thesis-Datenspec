# Changelog

## 1.0.0

More than one dark capture per cycle. A dark reference subtracts exactly only at the
gain and integration of the capture it serves, so a cycle that measures NIR scatter at a
long integration and blue/vis at a short one needs one dark per setting. Schema `v3`
changed in place: no device has written `v3` yet (the firmware for 0.6.0 is
unreleased), so `v` stays 3. Every record and profile file valid under 0.6.0 is valid
under 1.0.0; the reverse holds for cycles with one dark.

- `run` start and the profile file: `cfg.capture.captures` needs at least one `dark`
  step instead of exactly one. Gated steps still never count as dark; every `dark`
  step keeps `settle_ms`, `delay_ms` and `on_ms` 0.
- `data`: `m.tcs3448` needs at least one `dark` capture instead of exactly one. Every
  `dark` capture has all LED duty cycles 0 and `gated` false, as before.
- `cfg.capture.gain_control.mode` `dark` reworded: the gain of each lit capture is
  predicted from the most recent dark capture before it in the cycle.
- Examples: run 10 (`scatter_split`) with a dark before `nir` at a long integration and
  a second dark before `blue` and `vis` at a short one, and one of its data records.
  The invalid cases "two dark steps in captures" and "two dark captures in cycle" are
  removed; the cases without a dark capture stay.
- Pico constants: unchanged apart from the version header.

## 0.6.0

Timing per capture, dark gaps and gated integration. Light lingers after an LED
switches off (delayed chlorophyll fluorescence, phosphor afterglow, LED driver tails),
so one run-wide `settle_ms` and `on_ms` could not describe what the device measured,
and integration could only start while the LED was on. Now every capture of the cycle
carries its own timing, a dark gap may precede it, and a capture may integrate in the
dark after its pulse (gated capture).

**Schema `v3`.** Firmware 1.0.0 has written `v2` records to device_1, so `v2` can no
longer change in place. The README's rule applies: a field is removed
(`cfg.capture.sequence`, `settle_ms`, `on_ms`) and a required field is added
(`m.tcs3448[].gated`), both breaking, so `v` increases to 3. The firmware writes
`v: 3` in every record (`SCHEMA_VERSION = 3`). Only `data` and `run` start records
changed shape, so only they require `v: 3`; every other kind, `run` end included,
accepts `v: 2` and `v: 3`, and its records from firmware 1.0.0 stay valid. `v2` `data`
and `run` start records are rejected at `v`; read them with package 0.5.5.

- `run` start and the profile file: `cfg.capture.sequence`, `cfg.capture.settle_ms` and
  `cfg.capture.on_ms` removed. New required field `cfg.capture.captures`, a list of
  steps in acquisition order, each with `ill` (`dark`, `nir`, `blue`, `vis`) and, in
  the time order of its phases, `gap_ms` (all LEDs off), `settle_ms` (LED on),
  `delay_ms` (LED off before the integration; `> 0` is a gated capture) and `on_ms`
  (LED on after the integration starts), all integer ms ≥ 0. Exactly one `dark` step,
  as before; gated steps do not count as dark. A `dark` step has `settle_ms`,
  `delay_ms` and `on_ms` 0; a lit step with `delay_ms` 0 has `on_ms > 0`; a gated
  step has `settle_ms > 0` and `on_ms` 0, so the LED never switches during an
  integration. `gain_control` is unchanged. `CaptureConfig.sequence` remains as a
  derived property (the `ill` of every step), not serialised. Profile files and start
  records written under 0.5.x are rejected.
- `data`: new required field `m.tcs3448[].gated`, true when the LEDs were off during the
  integration (the step's `delay_ms > 0`). A `dark` capture is never gated. `ill`
  reworded to "LED of this capture; dark means none", `led` to the duty setpoint of
  this capture's pulse; `m.tcs3448` states that its captures are in the order of
  `cfg.capture.captures`. `dt` is unchanged: start of integration relative to `up`.
  Data records written under 0.5.x lack `gated` and are rejected.
- `data`, `run` start: `v` must be 3. Header and all other kinds: `v` is 2 or 3.
- New model `CaptureStep`, exported from `datenspec.models`; new constant
  `CAPTURE_TIMING_VERSION = 3`, also exported.
- Pico constants: `F_SEQUENCE` removed; `F_CAPTURES`, `F_GAP_MS`, `F_DELAY_MS`,
  `F_GATED` added; `SCHEMA_VERSION = 3`.

## 0.5.5

Version bump only. Schema, models and examples are unchanged from 0.5.0; `v` stays 2.

## 0.5.0

Alarms outside runs, and gain control per run. The device watches its alarms all the time, not only while a run
measures, so an alert can be raised or cleared when there is no data record to refer
to. A profile now also says how the TCS3448 gain is chosen, so runs measured with
different gain strategies can be told apart and compared. Schema `v2` changed in
place: no device or SD card has written `v2` yet, so `v` stays 2. Every alert valid
under 0.4.0 is valid under 0.5.0; run start records are not.

- `alert`: `ref_seq` may be `null`, and is `null` exactly when `run` is `null`. Inside a
  run it still names the data record that triggered the transition.
- `run` start and the profile file: new required group `cfg.capture.gain_control` with
  `mode` (`fixed`, `ams`, `dark`) and `stages` (gain indices the run may choose from,
  strictly ascending, at least two; `null` exactly when `mode` is `fixed`). Every
  capture `gain` of a regulated run is one of its stages. Runs written under 0.4.0
  lack the group and are rejected.
- `info`: `tcs3448.agc` now says whether the active run regulates the gain (`mode` is
  not `fixed`), and is `false` outside a run.

## 0.4.0

Measurement profiles, so the laptop can start runs that measure differently. Schema
`v2` changed in place again: no device or SD card has written `v2` yet, so `v` stays 2.
Messages valid under 0.3.0 may be rejected by 0.4.0 and vice versa.

- `cmd`: new required field `profile`: a profile name (`^[a-z0-9_]+$`) or `null` for
  the device's default on `start`, always `null` on `stop`.
- `run` start: new required fields `profile` (the name actually used, never `null`) and
  `cfg` with the resolved settings: `sample_interval_ms` and `capture` (`sequence`,
  `settle_ms`, `on_ms`). `cfg.capture.sequence` needs exactly one `dark`.
- `info`: `sys.sample_interval_ms` and the `capture` group removed; they change per run
  now and live in the run's `cfg`. New required group `profiles` with `names` and
  `default`.
- New `schemas/profiles.schema.json` and model `ProfileFile` for the device's profile
  file (name -> `RunConfig`). It is not a message and has no topic.

## 0.3.0

Schema `v2` changed in place: no device or SD card has written `v2` yet, so `v` stays 2.
Messages valid under 0.2.0 may be rejected by 0.3.0 and vice versa.

- New laptop message `tag` on `thesis/laptop/tag`: sets (`value`) or deletes
  (`value: null`) a key/value tag on a run (`dev`, `run`); `key` matches
  `^[a-z0-9_]+$`. The newest `ts` per key is the current value.
- `session`: new required field `variety` (`normal`, `calibration`, `functional`,
  `flowrate`); `desc`, `setup` and `by` removed.
- `info`: `sd.free` must not exceed `sd.total`.
- `tele`: `ntp.last_up` must not exceed `up`.
- `run`: documented that start and end record are sent in the same boot, so the end's
  `up` and `seq` are not below the start's.
