# Changelog

## v1.3.0 — 2026-10-03

### Fixed

- **The nose and the flight direction disagreed.** The attitude matrix and the
  velocity formula used opposite sign conventions for yaw, so the aircraft flew
  at up to 180° to where its nose pointed — holding **D** banked right and moved
  right while the nose swung left. Both now use the same convention, verified to
  a dot product of 1.000 across every heading.
- **You could not slow down.** There was no airbrake, so pushing the nose down
  always gained speed (gravity) and closing the throttle alone was slow.
  **B** now works as a speed brake in the air as well as a wheel brake on the
  ground — with it open, even full throttle decelerates (274 → 244 km/h in 5 s).
- **Spawn was too close to the runway end.** The aircraft started 50 m from the
  south threshold, so the nose-over view had almost no runway ahead of it.
  It now starts 140 m in, with 1260 m of runway ahead.

### Added

- **Ground shadow** under the aircraft, so it reads as sitting on the surface
  rather than floating.
- **BRAKE / FLAPS indicators** on the instrument panel.
- Reduced the chance of misreading the aircraft's bank against the runway.

### Verified

- 10/10 flight-physics checks, 4/4 end-to-end flight sequence, smoke test,
  key-binding test, fullscreen/version/compass test, and spawn/gear check.

---

## v1.2.2 — 2026-10-03

### Fixed

- **Extra rotation on the aircraft model matrix.** A 180° Y-axis flip mirrored
  the wings while leaving the nose pointing the same way, so the aircraft
  banked the opposite way to the turn. Removed.
- **Heading readout.** The window title now shows heading and bank angle.

---

## v1.2.1 — 2026-10-03

### Changed

- Simplified the documentation; the user guide is now a 350-character quick
  reference in English, with technical notes split into `NOTES.md`.

---

## v1.2.0 — 2026-10-03

### Added

- **Procedural scenery**: forests (~3000–4000 trees, instanced), six lakes with
  sky reflection and sun glint, and small houses near the airport.
- **Two-layer terrain**: fine detail within 2.4 km, mountains out to 17 km.
- **Distance haze** so mountains fade into the sky instead of ending abruptly.
- **Colour by altitude**: grass green → dry yellow → rock grey → snow.
- Vectorised scenery generation: 4 s down to 0.02 s.

---

## v1.1.0 — 2026-10-02

### Added

- **Fullscreen** (F11 / Alt+Enter / `--fullscreen`), restoring the previous
  window position on exit.
- **Version number** in the window title, the on-screen display and the console
  banner.
- **Compass tape** at the top of the display.

### Fixed

- **Launch script crashed instantly.** The `.bat` contained Chinese text; cmd.exe
  parses batch files with the local code page, so the text became garbage and was
  run as commands. The launchers are now pure ASCII.
- **`glViewport` was never set**, so after switching to fullscreen the 3D scene
  only covered a corner of the window.
- **Digits `0` and `1` rendered as nothing** because a bulk edit had corrupted
  their glyphs in the bitmap font.

---

## v1.0.0 — 2026-10-02

First working version.

- Angle-of-attack flight model: lift, induced drag, stall above 16°, auto-trim,
  speed-dependent control authority, banked turns produce yaw.
- Ground handling: gear support, rolling friction, brakes, rotation, crash
  detection.
- 1400 m runway with centreline, edge markings, lights and threshold numbers;
  tower and hangar.
- Sky with gradient, sun disc/glow and volumetric-looking clouds.
- Glass cockpit: airspeed, altitude, throttle, vertical speed, attitude
  indicator, AOA, G-load and warnings.
- Three cameras (cockpit / chase / orbit), keyboard and mouse control.
