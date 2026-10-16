"""
score.py - A scrolling grand-staff strip for the 2D falling-notes player.

A sheet-music band drawn right under the top bar, as wide as the keyboard
and centred on it. White paper, black staves/clefs/notes; the playhead
stands still (~25% of the strip, past the clef area) while the notes drift
past it: the past 1.5 s on the left, the next 4 s on the right.

Note heads follow their duration against the beat: whole/half notes are
hollow, quarter notes and shorter are filled; everything but whole notes
has a stem, eighths carry one flag and sixteenths two. Notes sounding right
now are highlighted in their hand's colour.

Only the player (main.py's Visualizer) uses this; nothing else imports it.
"""
from __future__ import annotations

import statistics

import pygame

from common import HAND_COLORS
from midi_loader import LEFT, MIDDLE_C, RIGHT

SCORE_STRIP_H = 150   # fixed strip height: two 5-line staves + gap + margins
PAST_SECS = 1.5       # history shown left of the playhead
FUTURE_SECS = 4.0     # lookahead shown right of the playhead
CLEF_W = 56           # left area kept free of notes (stylised clefs live here)
EDGE_R = 8            # right margin
STAFF_SPACING = 10.0  # staff line gap: the inner content stays compact
HEAD_HW, HEAD_HH = 4.0, 3.0       # normal note-head half-size
WHOLE_HW, WHOLE_HH = 5.5, 3.5     # whole-note heads run a little wider

TREBLE_BOTTOM = 64    # E4: bottom line of the treble staff
BASS_TOP = 57         # A3: top line of the bass staff

PAPER = (255, 255, 255)
INK = (25, 25, 25)
PLAYHEAD = (200, 40, 40)

_STEP = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 11: 6}


def _diatonic(pitch: int) -> int:
    """Pitch -> diatonic step number (C=0, D=1, ... B=6, per octave)."""
    return (pitch // 12) * 7 + _STEP[pitch % 12]


def staff_of(note, hand=None) -> str:
    """'treble' or 'bass' for a Note (or a raw pitch with an optional hand).

    The note's hand wins (right -> treble, left -> bass); a note with no
    known hand goes by pitch, middle C and up on the treble staff.
    """
    pitch = note.pitch if hasattr(note, "pitch") else note
    h = note.hand if hasattr(note, "hand") else hand
    if h == RIGHT:
        return "treble"
    if h == LEFT:
        return "bass"
    return "treble" if pitch >= MIDDLE_C else "bass"


def y_for_pitch(pitch: int, staff: str, top: float, spacing: float) -> float:
    """Y of a note head: `top` is the staff's top line, `spacing` one line gap.

    Every diatonic step is half a spacing, measured from the treble bottom
    line (E4 = 64) or the bass top line (A3 = 57).
    """
    if staff == "treble":
        steps_above_bottom = _diatonic(pitch) - _diatonic(TREBLE_BOTTOM)
        return top + 4 * spacing - steps_above_bottom * spacing / 2
    steps_below_top = _diatonic(BASS_TOP) - _diatonic(pitch)
    return top + steps_below_top * spacing / 2


def beat_len(song) -> float:
    """One beat in seconds: median gap of `song.beat_times`.

    Falls back to a quarter of the median bar length, then to 0.5 s
    (a 120 bpm beat) when the file carries no usable tempo map.
    """
    diffs = [b - a for a, b in zip(song.beat_times, song.beat_times[1:]) if b > a]
    if len(diffs) >= 2:
        return float(statistics.median(diffs))
    bars = [b - a for a, b in zip(song.bar_times, song.bar_times[1:]) if b > a]
    if len(bars) >= 2:
        return float(statistics.median(bars)) / 4
    return 0.5


def note_kind(duration: float, beat: float) -> str:
    """'whole' | 'half' | 'quarter' | 'eighth' | '16th' by duration in beats."""
    r = duration / beat if beat > 0 else 0
    if r >= 3.5:
        return "whole"
    if r >= 1.5:
        return "half"
    if r >= 0.75:
        return "quarter"
    if r >= 0.375:
        return "eighth"
    return "16th"


def layout_score_rect(kb_rect: pygame.Rect, top: int, height: int = SCORE_STRIP_H) -> pygame.Rect:
    """Strip rect: same x/width as the keyboard, hanging from `top`."""
    return pygame.Rect(kb_rect.x, top, kb_rect.w, height)


def playhead_x(rect: pygame.Rect) -> float:
    """Screen x of the stationary playhead (~25% across the strip)."""
    left = rect.x + CLEF_W
    w = rect.w - CLEF_W - EDGE_R
    return left + PAST_SECS / (PAST_SECS + FUTURE_SECS) * w


def x_for_time(ts: float, t: float, rect: pygame.Rect) -> float:
    """Screen x of song-time `ts` when now is `t` (playhead stands still)."""
    left = rect.x + CLEF_W
    w = rect.w - CLEF_W - EDGE_R
    return left + (ts - (t - PAST_SECS)) / (PAST_SECS + FUTURE_SECS) * w


def _staff_geometry(rect: pygame.Rect):
    """(spacing, treble_top, bass_top): two 5-line staves fitted into `rect`."""
    pad, gap = 14, 18
    spacing = max(6.0, min(STAFF_SPACING, (rect.h - 2 * pad - gap) / 8))
    total = 8 * spacing + gap
    top0 = rect.y + (rect.h - total) / 2
    return spacing, top0, top0 + 4 * spacing + gap


def stem_up(pitch: int, staff: str, top: float, spacing: float) -> bool:
    """Standard stem direction: down at/above the middle line, up below it."""
    return y_for_pitch(pitch, staff, top, spacing) > top + 2 * spacing


def _fit_stem(y: float, up: bool, kind: str, spacing: float, lo: float, hi: float):
    """(stem_len, flags) shortened so the tip and hooks stay inside [lo, hi].

    Flags reach back toward the head (~6 px per extra flag plus a 13 px
    hook), so a cramped stem sheds its flags first, then the stem itself.
    """
    want = 2.2 * spacing
    stem = min(want, y - (lo + 2) if up else (hi - 2) - y)
    if stem < 1.0 * spacing:
        return 0, 0
    flags = {"eighth": 1, "16th": 2}.get(kind, 0)
    while flags and stem < 6 * (flags - 1) + 13:
        flags -= 1
    return stem, flags


def _draw_clefs(surf, x0: float, treble_top: float, bass_top: float, spacing: float):
    """Small stylised clefs (arcs + dots); no music font needed."""
    cx = x0 + 14
    # Treble: a vertical stroke with a curl around the G line (2nd line up).
    g_line = treble_top + 3 * spacing
    pygame.draw.line(surf, INK, (cx + 4, treble_top - spacing),
                     (cx + 4, treble_top + 5 * spacing), 2)
    pygame.draw.arc(surf, INK,
                    (cx - 6, g_line - spacing, 20, 2 * spacing), 0.6, 5.8, 2)
    pygame.draw.circle(surf, INK, (int(cx + 4), int(g_line + spacing)), 3)
    # Bass: a backward-C arc around the F line (2nd line down) + two dots.
    f_line = bass_top + spacing
    pygame.draw.arc(surf, INK,
                    (cx - 8, f_line - spacing, 22, 2 * spacing), 1.2, 5.0, 2)
    for dy in (-1, 1):
        pygame.draw.circle(surf, INK,
                           (int(cx + 14), int(f_line + dy * spacing / 2)), 2)


def _ledger_lines(surf, x: float, pitch: int, staff: str, top: float, spacing: float, color):
    """Short ledger lines for a note outside its staff (none when inside)."""
    ref = _diatonic(TREBLE_BOTTOM if staff == "treble" else BASS_TOP)
    off = _diatonic(pitch) - ref
    # Line offsets from the reference line: treble bottom line E4 (staff
    # lines at 0..8), bass top line A3 (staff lines at -8..0).
    lo, hi = (0, 8) if staff == "treble" else (-8, 0)
    if off < lo - 1 or off > hi + 1:
        k = lo - 2 if off < lo else hi + 2
        while (k >= off if off < lo else k <= off):
            y = (top + (8 - k) * spacing / 2 if staff == "treble"
                 else top - k * spacing / 2)
            pygame.draw.line(surf, color, (x - 6, y), (x + 6, y), 1)
            k += -2 if off < lo else 2


def _draw_flag(surf, sx: float, tip: float, up: bool, color, count: int):
    """Little hooks at the stem tip: one for eighths, two for sixteenths."""
    for i in range(count):
        y0 = tip + (i * 6 if up else -i * 6)
        y1 = y0 + (9 if up else -9)
        if up:      # stem tip at the top, hook curving right and down
            pygame.draw.lines(surf, color, False,
                              [(sx, y0), (sx + 8, y1 - 3), (sx + 6, y1 + 4)], 1)
        else:       # stem tip at the bottom, mirrored to the left
            pygame.draw.lines(surf, color, False,
                              [(sx, y0), (sx - 8, y1 + 3), (sx - 6, y1 - 4)], 1)


def draw_score(surf, song, t: float, rect: pygame.Rect, fonts, held_ids=None,
               window: tuple = (PAST_SECS, FUTURE_SECS)):
    """Draw the scrolling grand staff for `song` at time `t` into `rect`.

    `held_ids`: {id(note)} sounding right now (drawn in the hand's colour);
    `window`: (past, future) seconds around `t`.
    """
    past, future = window
    held = held_ids or set()
    beat = beat_len(song)
    pygame.draw.rect(surf, PAPER, rect)
    clip = surf.get_clip()
    surf.set_clip(rect)

    spacing, treble_top, bass_top = _staff_geometry(rect)
    for top in (treble_top, bass_top):
        for i in range(5):
            y = top + i * spacing
            pygame.draw.line(surf, INK, (rect.x + 6, y), (rect.right - 6, y), 1)
    _draw_clefs(surf, rect.x + 6, treble_top, bass_top, spacing)

    # Bar lines spanning both staves.
    span = rect.w - CLEF_W - EDGE_R

    def _x(ts):
        return rect.x + CLEF_W + (ts - (t - past)) / (past + future) * span

    for bt in song.bar_times:
        if t - past <= bt <= t + future:
            x = _x(bt)
            pygame.draw.line(surf, INK, (x, treble_top),
                             (x, bass_top + 4 * spacing), 1)

    px = rect.x + CLEF_W + past / (past + future) * span
    for n in song.notes_between(t - past, t + future):
        staff = staff_of(n)
        top = treble_top if staff == "treble" else bass_top
        kind = note_kind(n.end - n.start, beat)
        color = HAND_COLORS[n.hand][0] if id(n) in held else INK
        _ledger_lines(surf, _x(n.start), n.pitch, staff, top, spacing, color)
        # Head: hollow for whole/half notes, filled below that; whole-note
        # heads run a little wider and never take a stem.
        hw, hh = (WHOLE_HW, WHOLE_HH) if kind == "whole" else (HEAD_HW, HEAD_HH)
        head = pygame.Rect(0, 0, int(hw * 2), int(hh * 2))
        # Clamp freak-range heads just inside the strip so notation never
        # touches its edges (the staff positions themselves don't move).
        y = min(max(y_for_pitch(n.pitch, staff, top, spacing),
                    rect.y + hh + 1), rect.bottom - hh - 1)
        x = _x(n.start)
        head.center = (int(x), int(y))
        if kind in ("whole", "half"):
            pygame.draw.ellipse(surf, PAPER, head)
            pygame.draw.ellipse(surf, color, head, 2)
        else:
            pygame.draw.ellipse(surf, color, head)
        if kind == "whole":
            continue
        # Standard stem direction (down at/above the middle line), shortened
        # near the strip edges so tip and flags stay inside.
        up = stem_up(n.pitch, staff, top, spacing)
        stem, flags = _fit_stem(y, up, kind, spacing, rect.y, rect.bottom)
        if stem <= 0:
            continue
        if up:
            sx, tip = head.right - 1, y - stem
            pygame.draw.line(surf, color, (sx, y - 1), (sx, tip), 1)
            _draw_flag(surf, sx, tip, True, color, flags)
        else:
            sx, tip = head.left + 1, y + stem
            pygame.draw.line(surf, color, (sx, y + 1), (sx, tip), 1)
            _draw_flag(surf, sx, tip, False, color, flags)

    pygame.draw.line(surf, PLAYHEAD, (px, rect.y + 4), (px, rect.bottom - 4), 2)
    pygame.draw.line(surf, INK, rect.bottomleft, rect.bottomright)
    surf.set_clip(clip)
