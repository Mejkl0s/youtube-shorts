"""Shared, normalized action cues for animation, captions and speech."""
ACTIONS = {'notice_stop': .38, 'pickup': .45, 'handoff': .65, 'depart': .8}


def beat_plan(duration, story='parcel'):
    # Caption boundaries follow the actual choreography, not equal-length blocks.
    starts = [0, .2, .4, ACTIONS['handoff'], ACTIONS['depart']]
    speech = [.012, .212, ACTIONS['pickup'], ACTIONS['handoff'], .812]
    if story == 'reunion':
        speech[2] = .412  # Recognition comes before the greeting gesture.
    return [{'start': start * duration,
             'end': (starts[i + 1] if i < 4 else 1) * duration,
             'speech_start': speech[i] * duration,
             'action': ['arrive', 'notice', 'recognize' if story == 'reunion' else 'pickup', 'greet' if story == 'reunion' else 'handoff', 'leave'][i]}
            for i, start in enumerate(starts)]
