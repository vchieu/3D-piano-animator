"""The scrolling grand-staff strip in the 2D player (score.py + Visualizer)."""
import pygame
import pytest

from conftest import midi_path

import main
from common import TOP_BAR_H, bottom_layout, load_fonts
from midi_loader import LEFT, RIGHT, MidiSong, Note, load_song
from score import (EDGE_R, FUTURE_SECS, PAPER, PAST_SECS, SCORE_STRIP_H,
                   _fit_stem, beat_len, draw_score, layout_score_rect,
                   note_kind, playhead_x, staff_of, stem_up, x_for_time,
                   y_for_pitch)


def _note(pitch, hand=None):
    return Note(pitch, 0.0, 1.0, 64, 0, hand)


def test_treble_bottom_line_is_e4():
    assert y_for_pitch(64, "treble", 100, 12) == 100 + 4 * 12


def test_c4_has_one_ledger_line_each_staff():
    # One diatonic step (= half spacing) below the treble staff...
    assert y_for_pitch(60, "treble", 100, 12) == 100 + 5 * 12
    # ...and one above the bass staff.
    assert y_for_pitch(60, "bass", 200, 12) == 200 - 12


def test_staff_of_prefers_hand_then_pitch():
    assert staff_of(_note(40, RIGHT)) == "treble"
    assert staff_of(_note(80, LEFT)) == "bass"
    assert staff_of(_note(60, None)) == "treble"
    assert staff_of(_note(59, None)) == "bass"


def test_strip_aligns_with_keyboard_and_future_is_right_of_playhead():
    kb_rect, _ = bottom_layout((1400, 860))
    rect = layout_score_rect(kb_rect, TOP_BAR_H)
    assert (rect.x, rect.w) == (kb_rect.x, kb_rect.w)
    assert rect.h == SCORE_STRIP_H
    t = 5.0
    # The playhead sits ~25% across the note area (past the clefs)...
    frac = (playhead_x(rect) - (rect.x + 56)) / (rect.w - 56 - EDGE_R)
    assert frac == pytest.approx(PAST_SECS / (PAST_SECS + FUTURE_SECS))
    # ...the past is left of it, the future right of it.
    assert x_for_time(t - 1.0, t, rect) < playhead_x(rect) < x_for_time(t + 1.0, t, rect)
    assert x_for_time(t, t, rect) == playhead_x(rect)


def test_s_key_toggles_score(screen):
    viz = main.Visualizer(screen)
    assert viz.show_score is True
    viz.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
    assert viz.show_score is False
    viz.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
    assert viz.show_score is True


def test_render_with_and_without_score_smoke(screen):
    viz = main.Visualizer(screen, song=load_song(midi_path("demo_song.mid")))
    viz.seek(5.0)
    viz.show_score = True
    viz.layout(screen.get_size())
    viz.render()
    with_score = pygame.image.tostring(screen, "RGB")
    viz.show_score = False
    viz.layout(screen.get_size())
    viz.render()
    without_score = pygame.image.tostring(screen, "RGB")
    assert with_score != without_score


def test_beat_len_from_beats_then_bars_then_default():
    assert beat_len(load_song(midi_path("demo_song.mid"))) == pytest.approx(0.6)
    notes = [Note(60, 0.0, 1.0, 64, 0, RIGHT)]
    barred = MidiSong(notes, [], 8.0, [0.0, 2.0, 4.0, 6.0], [], None)
    assert beat_len(barred) == pytest.approx(0.5)
    bare = MidiSong(notes, [], 8.0, [], [], None)
    assert beat_len(bare) == pytest.approx(0.5)


def test_note_kind_follows_duration_in_beats():
    beat = 0.6
    assert note_kind(4 * beat, beat) == "whole"
    assert note_kind(2 * beat, beat) == "half"
    assert note_kind(1 * beat, beat) == "quarter"
    assert note_kind(0.5 * beat, beat) == "eighth"
    assert note_kind(0.25 * beat, beat) == "16th"


def test_strip_is_white_paper(screen):
    song = load_song(midi_path("demo_song.mid"))
    kb_rect, _ = bottom_layout(screen.get_size())
    rect = layout_score_rect(kb_rect, TOP_BAR_H)
    draw_score(screen, song, 5.0, rect, load_fonts(), set())
    # Top-right corner: inside the strip, clear of staves and notes.
    assert screen.get_at((rect.right - 3, rect.y + 3))[:3] == PAPER


def test_keyboard_keeps_proportions_but_sits_lower(screen):
    viz = main.Visualizer(screen, song=load_song(midi_path("demo_song.mid")))
    kb_rect, hand_rect = bottom_layout(screen.get_size())
    kb = viz.keyboard.rect
    assert (kb.x, kb.w, kb.h) == (kb_rect.x, kb_rect.w, kb_rect.h)
    assert kb.y > kb_rect.y                       # shifted toward the bottom...
    assert viz.hand_rect.bottom == screen.get_height()
    assert viz.hand_rect.h <= hand_rect.h         # ...by a compact hand area
    viz.render()


def test_stem_direction_follows_the_middle_line():
    top, spacing = 100, 10
    # Treble middle line is B4 (71): at/above it stems go down...
    assert stem_up(71, "treble", top, spacing) is False
    assert stem_up(72, "treble", top, spacing) is False   # C5, above
    assert stem_up(69, "treble", top, spacing) is True    # A4, below
    # ...and the same rule holds on the bass staff (middle line D3 = 50).
    assert stem_up(50, "bass", top, spacing) is False
    assert stem_up(48, "bass", top, spacing) is True     # C3, below


def test_fit_stem_never_touches_the_strip_edges():
    lo, hi, spacing = 0, 150, 10
    # Mid-strip eighth: full stem and its flag survive.
    stem, flags = _fit_stem(75, True, "eighth", spacing, lo, hi)
    assert stem == pytest.approx(2.2 * spacing) and flags == 1
    # Crowded at the top: an up-stem shortens so its tip stays inside...
    stem, flags = _fit_stem(12, True, "16th", spacing, lo, hi)
    assert stem == pytest.approx(10) and stem < 2.2 * spacing
    assert flags < 2
    # ...and with no room at all even the stem is dropped, never crossing.
    stem, flags = _fit_stem(3, True, "quarter", spacing, lo, hi)
    assert (stem, flags) == (0, 0)
    # Same mirrored at the bottom edge for down-stems.
    stem, flags = _fit_stem(138, False, "eighth", spacing, lo, hi)
    assert stem == pytest.approx(10) and flags == 0
