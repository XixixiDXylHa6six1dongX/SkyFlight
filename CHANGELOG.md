# Changelog

## v1.4.1 — 2026-10-03

### Fixed

- **The version number and the aircraft name overlapped in the top-left
  corner.** The aircraft name was drawn at a hard-coded `pad + 62`, but
  `V1.4.0` is actually 90.5 px wide, so the two strings ran into each other
  (`V1.4ROP TRAINER`). The layout now accumulates measured text widths with a
  14 px gap, and `tests/hud_layout.py` asserts no overlap, no collision with
  the compass, and that every gear state renders without GL errors.

### Changed

- The gear / engine status block in the top-left now sits on a translucent
  panel, so it stays legible against a bright sky. It reads `GEAR DOWN` /
  `GEAR UP` / `GEAR nn%` plus `TURBOJET` or `PISTON`. `GEAR UP` is now cyan
  rather than grey.

---

## v1.4.0 — 2026-10-03

### Added

- **Three aircraft, one of them piston and two turbojets.** Press **V** to cycle:

  | Aircraft | Engine | Span | Mass | Thrust | Stall | Gear |
  |---|---|---|---|---|---|---|
  | Prop Trainer 螺旋桨教练机 | piston, 3-blade prop | 11.0 m | 1100 kg | 3.6 kN | 16° | fixed |
  | Light Jet 轻型涡喷教练机 | single turbojet, side intakes, exhaust nozzle | 10.7 m | 3200 kg | 16.5 kN | 15° | retractable |
  | Twin Jet 双发涡喷公务机 | two podded turbojets, T-tail | 15.6 m | 9800 kg | 48.0 kN | 16° | retractable |

  Each has its own mass, wing area, thrust, drag, stall angle, control
  authority and landing-gear height. Switching aircraft resets you to the
  runway with the correct sit height for that airframe.

- **Retractable landing gear.** The two jets start with the gear down. Press
  **G** after takeoff to raise it; **G** again before landing. Retraction takes
  about 1.8 s and is animated — the gear scales and tucks into the fuselage.
  - Drag changes with gear position: at the same throttle the light jet gains
    **+164 km/h** and the twin jet **+204 km/h** when the gear comes up.
  - The prop trainer's gear is fixed and refuses to retract.
  - The gear cannot be raised on the ground or below 15 km/h.
  - The instrument panel shows `GEAR DOWN` / `GEAR UP` / `GEAR nn%`.

- `--aircraft=jet_light` command-line option to start in a chosen aircraft.
- `tests/aircraft_check.py`: geometry, performance, per-type test flight,
  gear retraction and gear-drag checks.

### Fixed

- **Jets could be rolled onto their side.** The roll controller was purely
  proportional with no bank limit, so an aircraft with strong roll authority
  (the light jet) would keep rolling past 90° into knife-edge flight. Roll is
  now commanded as a target bank angle (58° at full stick) with a hard angle
  clamp, on top of the existing self-levelling. All three aircraft now hold
  about 63° and can no longer be flipped.
- **Aircraft geometry no longer disagrees with its specification.** The test
  suite measures every model against `specs.py` and fails on any mismatch
  (wing span, length, and the gear bottom relative to the declared sit height).

### Verified

- 10/10 flight-physics checks · 4/4 end-to-end flight sequence · aircraft
  check (geometry, performance, per-type flight, gear) · smoke test · key
  bindings · fullscreen/version/compass · spawn and gear height for all three
  types.

---

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
