# Changelog

## v1.6.2 — 2026-10-03

### Fixed

- **The instrument panel vanished whenever you crashed, and stayed gone after
  pressing `R`.** The v1.6.1 fix inserted the HUD call in the wrong place: a
  second, duplicate block was left **inside `_draw_particles()`**. That produced
  a bug which only appears in one specific situation:

  | Situation | What happened |
  |---|---|
  | Normal flight | `_draw_particles()` returns immediately (no particles), so the duplicate block never ran. The real HUD call at the end of `draw()` worked, so the panel looked fine |
  | Any crash | particles exist, so execution reached the duplicate block — but `fb_w` / `fb_h` are locals of `draw()` and do not exist there → `NameError` → swallowed by `except: show_hud = False` → **panel gone permanently** |

  So the panel worked until the first crash and never came back — exactly what
  was reported. The duplicate block is removed; `draw_hud()` is now called from
  **exactly one place**, at the end of `draw()`. A comment at that spot records
  why nothing may be added there.

### Added

- `tests/hud_layout.py` now also replays the crash-and-restart sequence: it
  asserts particles actually exist, that `show_hud` survives the crash, that the
  panel is still drawn during the crash (dark pixels in the bottom-left region),
  and that it is still there after pressing `R`. This is the check that would
  have caught the bug, and it fails on the v1.6.1 code.

---

## v1.6.1 — 2026-10-03

### Fixed

- **The entire instrument panel had disappeared.** When the particle pass was
  added to `draw()` in v1.6.0, it replaced the HUD block at the end of the
  method instead of being inserted before it — so `draw_hud()` was **never
  called**. Nothing raised an error and nothing was logged; the panel, compass,
  version number and gear readout were simply gone.
  The HUD call is restored at the end of `draw()`, after the particles (it must
  be last, so it draws on top of the 3D scene).

- **A single HUD error no longer turns the panel off permanently.** The old
  `except` clause set `show_hud = False` on the very first failure, so one
  transient problem would hide the panel for the rest of the session. It now
  prints the reason for the first three failures and only disables the HUD after
  60 consecutive failures.

### Added

- A regression guard in `tests/hud_layout.py` for exactly this class of bug,
  because a missing draw call is invisible to every other test:

  | Check | What it catches |
  |---|---|
  | `draw_hud` appears in the AST of `draw()` | the call being deleted or overwritten |
  | the bottom-left panel region contains > 2000 dark pixels after `draw()` | the call existing but not reaching the screen |
  | `show_hud` is still True afterwards | the panel being silently disabled |

  Both checks fail on the v1.6.0 code and pass after the fix, so the bug cannot
  come back unnoticed.

---

## v1.6.0 — 2026-10-03

### Added

- **Sound.** Every sample is synthesised with numpy at runtime — no audio files
  are bundled. A real mixer (Windows `waveOut` via `winmm`) lets the engine,
  wind, ground roll and one-shot effects play **at the same time** instead of
  cutting each other off. If no audio device is available the game runs silently
  rather than crashing. Press **N** to toggle sound, or start with `--no-sound`.

  | Sound | Behaviour |
  |---|---|
  | Engine | fundamental + harmonics + blade-beat; pitch and brightness follow throttle. Turbojets get a high whine and broadband jet noise, pistons a low rumble |
  | Wind | broadband noise, louder and brighter with airspeed |
  | Ground roll | tyre rumble on the runway, louder when braking |
  | Touchdown | low thump + noise burst, scaled by sink rate |
  | Stall warning | repeated short beep while stalled |
  | Gear | hydraulic motor whine while the gear runs |
  | Explosion | low sweep + noise blast + debris tail |
  | Scrape | metal-on-runway noise when you touch down crooked |

- **Explosion and particle effects** (`skyflight/particles.py`). A 700-particle
  pool updated on the CPU and drawn in **one instanced call** (0.14 ms/frame when
  full). Particles are camera-facing quads expanded in the vertex shader from the
  camera's right/up vectors, with a soft round edge so smoke looks like smoke
  rather than squares.

  | Effect | Trigger |
  |---|---|
  | Explosion | crash — fireball + white-hot core + embers + black smoke + dust (411 particles) |
  | Touchdown dust | wheels meet the runway, scaled by sink rate |
  | Tyre smoke | heavy braking above 60 km/h |
  | Black smoke | the burning wreck keeps smoking after a crash |
  | Contrails | above 900 m and faster than 120 km/h |

- **More scenery**, plus a river/road/field generator (`skyflight/linear.py`):

  | Added | Notes |
  |---|---|
  | Rivers | traced **downhill** from high ground, 8-way steepest descent until they reach water; the ribbon is sampled at every corner so it follows the terrain |
  | Country roads | each village linked to its nearest neighbour, with a bend so they are not straight lines |
  | Farmland | fields around villages in four crop colours, snapped to the terrain |
  | Wind farms, villages, rocks, mixed forest | already present, now denser |

### Changed

- **Fullscreen now explicitly disables the window decoration.**
  `set_window_monitor` alone left a title bar on some Windows builds; the window
  is now created and toggled with `DECORATED` off, so fullscreen is genuinely
  borderless.
- Scenery generation got **3× faster** (0.77 s → 0.25 s) after profiling: river
  tracing, village placement and field placement were each issuing one terrain
  query per point instead of one batched query. River tracing alone went from
  0.389 s to 0.094 s.

### Verified

New suites: `tests/sound_check.py` (every waveform synthesises, loop seams are
continuous, the mixer runs, silent fallback works), `tests/particles_check.py`
(spawn, lifetime, pool overflow, instance format, per-frame cost) and
`tests/fullscreen_border.py` (`DECORATED` off in fullscreen, restored on exit,
native resolution, back buffer still renders). `tests/scenery_check.py` now also
asserts rivers, roads and fields generate. Full suite green: 10/10 flight
physics, aircraft check, spawn fit, i18n, HUD layout, keys, 4/4 end-to-end
flight, smoke test.

---

## v1.5.1 — 2026-10-03

### Fixed

- **The aircraft looked like it was sunk into the runway.** The runway's white
  centre line, edge lines and threshold numbers were built as **raised boxes** —
  60 mm thick with their centres at `RUNWAY_TOP + 0.02`, so their top surface sat
  at **y = 0.310**. The tyres rest at **y = 0.240**, i.e. **70 mm below the
  paint**, so the wheels were buried in the markings. The markings are now thin
  sheets sitting 5 mm proud of the asphalt, drawn as a separate mesh, so they no
  longer swallow the wheels (the 5 mm lift also removes z-fighting against the
  asphalt). The runway lights beside the strip also reached y = 1.025, which made
  the same problem worse when parking next to them.

- **Spawn leaves a visible gap, then settles.** `app.SPAWN_CLEARANCE = 0.25 m`
  puts the wheels 25 cm above the runway at spawn so you can see daylight under
  them; the aircraft settles onto the surface 0.63 s later at about 0.9 m/s —
  far below the 19 m/s crash threshold, so it never damages the aircraft. Three
  separate bugs had to be fixed for that to work:

  1. `_place_on_runway` set `on_ground = True`. The ground-snap code only runs
     when airborne, so the aircraft would have hovered 25 cm up indefinitely.
  2. Once airborne, the ground branch clamps the flight-path angle to
     −0.02..+4°, which pins vertical speed at ~0 — so it still would not
     descend. It now gets an explicit gentle descent while above the surface.
  3. That descent has to change `speed_val`, not just `vel[1]`, because the
     velocity vector is recomputed from `speed_val * sin(gamma)` every frame
     (changing `vel[1]` alone was overwritten on the next frame).

  `surface_height()` now returns the top of the paint rather than the asphalt,
  so the resting height matches what is actually drawn.

### Verified

New `tests/spawn_fit.py` asserts, for all three aircraft: no runway mesh part
sits above `RUNWAY_PAINT_TOP`, runway lights are outside the strip, the aircraft
spawns above the surface, settles onto it to within 1 cm, and never sinks below
it while taxiing. `tests/spawn_check.py` now checks the spawn gap **and** the
settled contact. Full suite still green.

---

## v1.5.0 — 2026-10-03

### Added

- **Switchable interface language (Chinese / English).** Press **L** at any
  time. Everything switches: the instrument panel, the compass, all warnings,
  the window title, the console help text and the aircraft names. Default is
  Chinese; `--lang=en` on the command line starts in English.

  The HUD previously had only a 5x7 ASCII bitmap font, so Chinese could not be
  drawn at all. Non-ASCII characters are now rasterised on demand from a system
  font (Microsoft YaHei / SimHei / Noto Sans CJK, whichever is present) into the
  same bitmap format and cached — so the HUD still needs no font file and no
  pre-baked glyph table. Glyphs are rasterised **at the size they will be
  drawn** and cached per (character, size) — scaling one large bitmap down to
  13-15 px smeared the strokes together (the FPS label rendered as garbage).
  Small sizes get extra rows because CJK strokes are relatively thicker there.
  Below 11 px Chinese is skipped entirely rather than drawn as an ink blob. If
  no CJK font exists the HUD falls back to outline boxes instead of crashing.

- **Much richer scenery** (`skyflight/props.py` is new):

  | Added | Notes |
  |---|---|
  | Mixed forest | conifers *and* broadleaf trees; the conifer share rises with altitude, so low ground is leafy and high ground dark green |
  | Forest patches | density is driven by a large-scale noise field, giving real woodland edges and open meadows instead of uniform scatter |
  | Villages | houses, barns, warehouses, hangars, churches (with spires) and water towers, placed as clusters rather than scattered |
  | Wind farms | 3-blade turbines on ridges and plateaus — **the rotors turn** |
  | Rocks | boulders on steep slopes and at altitude |

  Trees are also 35 % larger and roughly twice as dense, the tree grid went from
  52 m to 40 m, and the "keep clear of the airport" radius dropped from 900 m to
  520 m, so the forest now starts right beside the runway instead of leaving a
  bare plain.

### Fixed

- **`FPS` and `GEAR nn%` rendered as literal placeholders.** The translated
  strings used `%d` with a named keyword argument. `i18n.t()` now accepts both
  styles (`%s`/`%d` positionally, `{name}` by keyword).
- **Nothing grows on the runway** or in the airport core, and nothing is placed
  in water — all three are now asserted by `tests/scenery_check.py` against every
  generated instance rather than a sample.

### Verified

New suites: `tests/i18n_check.py` (both string tables must have identical keys,
every entry must resolve without leftover placeholders, Chinese glyphs must
contain real strokes) and `tests/scenery_check.py` (density, determinism,
runway/water clearance, prop geometry, rotor rotation). Plus the existing suite:
10/10 flight physics, aircraft check, spawn check, key bindings (now covering
G / V / L), 4/4 end-to-end flight, smoke test, HUD layout, fullscreen.

---

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
