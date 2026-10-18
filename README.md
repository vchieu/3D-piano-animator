# Hand-thesia

Real-time falling-notes piano playback: give it a MIDI file and watch glowing notes fall onto the
88-key keyboard while a pair of animated hands plays them with a planned fingering. Includes a
fingering editor and the "Pianists & hands" editor (hand anatomy, colour and technique).

> **Built on [Hand-thesia](https://github.com/V9011N/pygame-piano-animator) by [V9011N](https://github.com/V9011N).**
> Their 2D app does the hard musical part: it reads the MIDI, splits it between the hands, works out the
> fingering and animates the hands.

## Requirements

- **Windows** (the main target; other systems may work with some path tweaks)
- **Python 3.10+**

## Setup

```bash
git clone https://github.com/mrbobbrick/3D-piano-animator.git
cd 3D-piano-animator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python main.py song.mid          # real-time falling notes with animated hands
python main.py song.mid --edit   # fingering editor
```

## How it works

The original Hand-thesia code splits the MIDI between the hands, plans the fingering and animates
both hands as the notes fall; see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the details.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Credits and license

- **2D Hand-thesia** (MIDI loading, hand split, fingering planner, hand animation, editors) by
  [V9011N](https://github.com/V9011N/pygame-piano-animator). The original project doesn't include a license,
  so all rights to that code stay with its author.
- **3D renderer and Fallboard** (`export3d.py`, `render_video.py`, `video_style.py`, `video_studio.py`,
  `blender/`, `studio/`) by [mrbobbrick](https://github.com/mrbobbrick).
- Sculpted hands from Blender Studio's Human Base Meshes (CC0). MakeHuman/MPFB assets (CC0).

Made with a lot of help from Claude. It's a vibe-coded hobby project, so expect rough edges.
