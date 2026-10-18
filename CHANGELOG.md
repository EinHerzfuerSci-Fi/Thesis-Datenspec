# Changelog

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
