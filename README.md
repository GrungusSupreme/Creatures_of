# Creatures of Catan

A modular Python core inspired by Settlers of Catan, including:
- board graph (hexes, vertices, edges, ports),
- player/resources/development cards,
- turn phases, robber, trading, roads/settlements/cities,
- longest road / largest army,
- save/load,
- CLI play loop and bot simulation.

## Run the Game (CLI)

### Option A: Double-click launcher
1. Double-click `Launch_Creatures_of_Catan.bat`.

### Option B: Run from terminal
```powershell
C:/Users/cella/Games/Creatures_of_Catan/.venv/Scripts/python.exe play_cli.py
```

## Run the Game (GUI)

Install pygame if needed:
```powershell
C:/Users/cella/Games/Creatures_of_Catan/.venv/Scripts/python.exe -m pip install pygame-ce
```

Launch GUI:
```powershell
C:/Users/cella/Games/Creatures_of_Catan/.venv/Scripts/python.exe play_gui.py
```

## Create Desktop Shortcut (Windows)
Run this once:
```powershell
powershell -ExecutionPolicy Bypass -File .\Create_Desktop_Shortcut.ps1
```
This creates `Creatures of Catan.lnk` on your desktop.

## Quick CLI Commands
- Main menu: `new`, `load <file>`, `quit`
- In game: `roll`, `trade <give> <receive> [rate]`, `done`, `road <edge_id>`, `settlement <vertex_id>`, `city <vertex_id>`, `dev buy`, `dev play <index>`, `save <file>`, `autoplay <turns>`, `end`

## Publish to GitHub

1. Create a new empty GitHub repository (no README/license/gitignore), e.g. `creatures-of-catan`.
2. In this folder, run:
```powershell
git init
git add .
git commit -m "Initial Catan core + CLI"
git branch -M main
git remote add origin https://github.com/<your-username>/creatures-of-catan.git
git push -u origin main
```
3. If prompted, authenticate with GitHub (browser or token).

## Optional pygame board viewer
`catan_core/render_pygame.py` contains a lightweight renderer.
Install pygame-ce first if you want to use it:
```powershell
C:/Users/cella/Games/Creatures_of_Catan/.venv/Scripts/python.exe -m pip install pygame-ce
```
