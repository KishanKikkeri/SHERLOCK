import { describe, it, expect } from 'vitest';
import { parseVoiceCommand } from '../voice-commands';

describe('parseVoiceCommand — happy paths', () => {
  it('recognizes sticky/note creation', () => {
    expect(parseVoiceCommand('add a sticky note')).toEqual({ type: 'add_sticky' });
    expect(parseVoiceCommand('new note please')).toEqual({ type: 'add_sticky' });
  });

  it('recognizes hypothesis creation', () => {
    expect(parseVoiceCommand('add hypothesis')).toEqual({ type: 'add_hypothesis' });
  });

  it('recognizes link/connect toggling', () => {
    expect(parseVoiceCommand('link these two')).toEqual({ type: 'toggle_link_mode' });
    expect(parseVoiceCommand('connect them')).toEqual({ type: 'toggle_link_mode' });
  });

  it('recognizes undo/redo', () => {
    expect(parseVoiceCommand('undo that')).toEqual({ type: 'undo' });
    expect(parseVoiceCommand('redo it')).toEqual({ type: 'redo' });
  });

  it('recognizes zoom with direction', () => {
    expect(parseVoiceCommand('zoom in')).toEqual({ type: 'zoom', direction: 'in' });
    expect(parseVoiceCommand('zoom out')).toEqual({ type: 'zoom', direction: 'out' });
  });

  it('recognizes pan with direction', () => {
    expect(parseVoiceCommand('pan left')).toEqual({ type: 'pan', direction: 'left' });
    expect(parseVoiceCommand('move right please')).toEqual({ type: 'pan', direction: 'right' });
  });

  it('recognizes reset/center/fit view before treating it as zoom', () => {
    expect(parseVoiceCommand('reset the view')).toEqual({ type: 'reset_view' });
    expect(parseVoiceCommand('zoom to fit')).toEqual({ type: 'reset_view' });
  });

  it('recognizes exit board phrasing', () => {
    expect(parseVoiceCommand('exit board')).toEqual({ type: 'exit_board' });
    expect(parseVoiceCommand('back to workspace')).toEqual({ type: 'exit_board' });
  });

  it('falls back to unrecognized for gibberish', () => {
    expect(parseVoiceCommand('purple elephant banana')).toEqual({
      type: 'unrecognized',
      raw: 'purple elephant banana',
    });
  });
});

describe('parseVoiceCommand — presentation mode ordering', () => {
  it('does not confuse "stop presenting" with starting a presentation', () => {
    expect(parseVoiceCommand('stop presenting now')).toEqual({ type: 'exit_presentation' });
  });

  it('starts presentation mode on a bare "present"', () => {
    expect(parseVoiceCommand('present the board')).toEqual({ type: 'present' });
  });
});

describe('parseVoiceCommand — known bug found during stabilization pass', () => {
  // The exit_presentation rule is:
  //   /\bstop present|exit present|end present\b/
  // Because `\b` only binds to the token immediately next to it in a
  // regex alternation, the middle alternative `exit present` has NO word
  // boundary at all on either side. That means any phrase containing the
  // literal substring "exit present" — including inside a longer word —
  // is misclassified as exit_presentation. Intended fix is something like
  // /\b(stop|exit|end) presenting?\b/. Left as a failing-documented case
  // rather than silently fixed, per the "flag over fix" stabilization pass.
  it('BUG: incorrectly matches "exit present" as a mid-word substring', () => {
    const result = parseVoiceCommand('please dont exit presentmania now');
    // This assertion documents the CURRENT (buggy) behavior.
    expect(result).toEqual({ type: 'exit_presentation' });
    // Desired behavior once fixed would instead be 'unrecognized'.
  });
});
