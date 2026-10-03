# SkyFlight — Technical Notes

For anyone modifying the code. The user-facing guide is in
[README.md](README.md).

## Layout

```
skyflight/
  app.py        window, render loop, cameras, input
  flight.py     flight dynamics (angle-of-attack state model)
  terrain.py    procedural terrain (fractal noise, two layers)
  scenery.py    forests, lakes, houses
  sky.py        sky and cloud shader
  plane.py      aircraft / runway / tower / hangar geometry
  hud.py        instruments (5x7 bitmap font + attitude indicator + compass)
  gfx.py        OpenGL helpers (shaders, meshes, matrices, instancing)
  shaders.py    object, terrain, instanced and water shaders
  version.py    version number
```

Built with Python 3.12 + PyOpenGL + GLFW. The bundled interpreter is in
`runtime\`.

## Tests

```
runtime\python.exe tests\flight_check.py     # 10 flight-physics checks
runtime\python.exe tests\smoke_test.py       # terrain / physics / geometry / GL
runtime\python.exe tests\full_flight.py      # takeoff -> climb -> cruise -> turn
runtime\python.exe tests\keytest.py          # every key binding, simulated
runtime\python.exe tests\turn_sheet.py       # renders wing-direction control images
runtime\python.exe tests\fullscreen_test.py  # fullscreen + version + compass
runtime\python.exe tests\spawn_diag.py       # gear height on the runway
runtime\python.exe tests\model_check.py      # aircraft model bounds
runtime\python.exe tests\ndc_vs_matrix.py    # matrix transpose correctness
runtime\python.exe tests\verify_projection.py
runtime\python.exe tests\final_check.py
runtime\python.exe tests\auto_smoke.py       # opens a window for 150 frames
```

## Gotchas

1. **Matrix transpose.** numpy is row-major, OpenGL reads column-major.
   `glUniformMatrix4fv` must be called with `GL_TRUE`. Passing `GL_FALSE`
   makes every object the wrong size and position (4–6× too large).
   Very hard to spot, because `glGetUniformfv` reads back the *transposed*
   matrix so it looks correct.
   **Reliable check**: draw the same vertices once directly as NDC and once
   through the matrix, and compare screen sizes (`tests/ndc_vs_matrix.py`).

2. **`gfx.Mesh` expects 9 floats per vertex** (position 3 + normal 3 +
   colour 3). The wrong count silently turns N vertices into 1 and nothing
   is drawn.

3. **Do not add an extra rotation to the aircraft model matrix.** The model's
   local axes already match world axes (nose −Z, right wing +X). An extra
   Y-axis 180° flip mirrors the wings while leaving the nose pointing the
   same way, so the aircraft banks the wrong way — and it is invisible at a
   glance because the aircraft is nearly symmetric.

4. **Instanced shaders need instance attributes.** Drawing a plain mesh with
   the instanced vertex shader leaves attributes 3–6 at their default
   `(0,0,0,1)`, collapsing every vertex to the origin. Use a dedicated vertex
   shader (see `WATER_VS`).

5. **Keep the perspective `near` plane at ≥ 0.25**, otherwise geometry close
   to the camera degenerates.

6. **Clouds**: do not project onto a fixed cloud-height plane — the divisor
   goes to zero as the camera approaches that height and you get radial
   streaks. Sample by ray direction instead.

7. **Flight feel**: integrating angle of attack as its own state
   (`α̇ = q − γ̇`) is far more stable than pushing on the velocity vector.

8. **`.bat` files must be pure ASCII on Chinese Windows.** cmd.exe parses the
   file using the local code page, so Chinese text becomes garbage and is
   executed as commands. `chcp 65001` does not help — it only affects output
   after the file is already parsed.

9. **Runway surface height.** The runway top is at y = 0.24, not 0. Collision
   must use `plane.surface_height()` (terrain vs runway, whichever is higher)
   or the aircraft sinks into the tarmac. The aircraft origin also sits
   `Aircraft.GEAR_HEIGHT` (1.07 m) above the wheels.
