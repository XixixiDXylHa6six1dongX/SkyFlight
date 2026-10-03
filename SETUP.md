# Running from source

This repository contains the **source code only**. The full game also ships
with a bundled 185 MB Python runtime, which is not committed here.

## Requirements

- Python **3.10+** (developed on 3.12)
- A GPU with **OpenGL 3.3** support

## Install

```
pip install PyOpenGL glfw numpy Pillow
```

## Run

From this folder:

```
python -m skyflight
```

Fullscreen:

```
python -m skyflight --fullscreen
```

## Verify the install

```
python tests/flight_check.py     # 10 flight-physics checks, no window needed
python tests/smoke_test.py       # terrain, physics, geometry, OpenGL render
python tests/full_flight.py      # takeoff -> climb -> cruise -> turn
```

`flight_check.py` and `full_flight.py` run headless and should pass on any
machine. `smoke_test.py` opens a hidden window and needs OpenGL 3.3.

## Notes

- On Windows, run the `.bat` launchers from this folder. They expect a
  `runtime\python.exe`; without it they will print an error. Use
  `python -m skyflight` instead, or drop a Python installation into
  `runtime\`.
- The `.bat` files are intentionally plain ASCII. `cmd.exe` parses batch
  files using the local code page, so non-ASCII text in a `.bat` gets
  mangled and executed as commands.
