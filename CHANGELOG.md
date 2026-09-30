# Changelog

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
