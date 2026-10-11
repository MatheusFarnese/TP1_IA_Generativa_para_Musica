"""
Generate a MIDI composition using frequent maximal patterns and a Markov chain.

Each musical event is represented as (pitch, start_offset, duration), where
start_offset is the silence between the previous note's end and this note's
start. The generated MIDI therefore models rests as part of each event.
"""

import random
import sys
from collections import Counter, defaultdict

import pretty_midi


# Time values are rounded to multiples of this many seconds.
GRID_STEP = 0.125


def quantize(value, grid=GRID_STEP):
    """Round a positive time value to the nearest grid step, with a minimum of one step."""
    return max(grid, round(value / grid) * grid)


def quantize_offset(value, grid=GRID_STEP):
    """Quantize a gap while allowing zero; negative gaps are clamped to zero."""
    return max(0.0, round(value / grid) * grid)


# ---------------------------------------------------------------------------
# 1. MIDI parsing
# ---------------------------------------------------------------------------

def extract_sequence_with_rests(instrument):
    """
    Convert an instrument's MIDI notes into a chronological event sequence.

    Each event is a tuple:
        (pitch, start_offset, duration)

    start_offset is the time from the previous note's end to this note's start.
    Negative gaps caused by overlapping notes are clamped to zero, so this
    representation is intended primarily for monophonic or non-overlapping
    note sequences.
    """
    if not instrument.notes:
        return []

    sequence = []
    sorted_notes = sorted(instrument.notes, key=lambda note: note.start)

    # Track the end of the previous note to measure the following gap.
    last_end_time = 0.0

    for note in sorted_notes:
        start_offset = quantize_offset(note.start - last_end_time)
        duration = quantize(note.end - note.start)
        sequence.append((note.pitch, start_offset, duration))
        last_end_time = note.end

    return sequence


# ---------------------------------------------------------------------------
# 2. Frequent maximal-pattern mining
# ---------------------------------------------------------------------------

def frequent_patterns(sequence, k=3, max_length=12, min_length=2):
    """
    Find frequent maximal contiguous patterns and segment the sequence.

    Args:
        sequence: Sequence of musical-event tuples.
        k: Minimum number of occurrences required for a pattern to be frequent.
        max_length: Maximum pattern length, measured in musical events.
        min_length: Minimum pattern length, measured in musical events.

    Returns:
        A pair:
          1. A token sequence, where each token is a pattern tuple. Events that
             are not included in a selected pattern become one-event tokens.
          2. A list of (pattern, occurrence_count) pairs for maximal patterns.

    A pattern is considered maximal when it is frequent and neither a
    one-event left extension nor a one-event right extension is frequent.
    During segmentation, longer and more frequent patterns are considered first.
    """
    sequence = list(sequence)

    if k < 1:
        raise ValueError("k must be >= 1.")
    if min_length < 2:
        raise ValueError("min_length must be >= 2.")
    if max_length < min_length:
        raise ValueError("max_length must be >= min_length.")

    n = len(sequence)
    max_length = min(max_length, n)

    # Count every contiguous subsequence within the requested length bounds.
    counts = Counter()
    for length in range(min_length, max_length + 1):
        for i in range(n - length + 1):
            counts[tuple(sequence[i:i + length])] += 1

    # Keep patterns that meet the minimum occurrence threshold.
    frequent = {
        pattern
        for pattern, count in counts.items()
        if count >= k
    }

    maximal_patterns = []

    for pattern in frequent:
        # A frequent pattern is left-extendable if adding the preceding event
        # produces another frequent pattern of length len(pattern) + 1.
        left_extension = (
            len(pattern) < max_length
            and any(
                (sequence[i - 1],) + pattern in frequent
                for i in range(1, n)
                if tuple(sequence[i:i + len(pattern)]) == pattern
            )
        )

        # A frequent pattern is right-extendable if adding the following event
        # produces another frequent pattern of length len(pattern) + 1.
        right_extension = (
            len(pattern) < max_length
            and any(
                pattern + (sequence[i + len(pattern)],) in frequent
                for i in range(n - len(pattern))
                if tuple(sequence[i:i + len(pattern)]) == pattern
            )
        )

        if not left_extension and not right_extension:
            maximal_patterns.append((pattern, counts[pattern]))

    # Prefer longer patterns, breaking ties by higher occurrence count.
    maximal_patterns.sort(key=lambda item: (-len(item[0]), -item[1]))
    patterns_only = [pattern for pattern, _ in maximal_patterns]

    # Segment the original sequence greedily, using the first matching pattern.
    # Any event not covered by a maximal pattern is kept as a one-event token.
    result = []
    i = 0

    while i < n:
        match = next(
            (
                pattern
                for pattern in patterns_only
                if tuple(sequence[i:i + len(pattern)]) == pattern
            ),
            None,
        )

        if match is not None:
            result.append(match)
            i += len(match)
        else:
            result.append((sequence[i],))
            i += 1

    return result, maximal_patterns


# ---------------------------------------------------------------------------
# 3. Markov-chain construction and sequence generation
# ---------------------------------------------------------------------------

def build_state_machine(tokens):
    """
    Build a first-order Markov chain over pattern tokens.

    Each token is a state. The counter for a state records how often each
    following token appeared immediately after it in the training sequence.
    These counts are used as transition weights during generation.
    """
    chain = defaultdict(Counter)

    for i in range(len(tokens) - 1):
        current_token = tokens[i]
        next_token = tokens[i + 1]
        chain[current_token][next_token] += 1

    return chain


def generate_music(chain, target_note_count=100):
    """
    Generate a sequence of musical events by sampling Markov transitions.

    Transition probabilities are proportional to the observed transition
    counts. Since tokens can contain multiple events, the generated sequence
    may contain more than target_note_count events when the final token is
    appended.
    """
    if not chain:
        raise ValueError(
            "Cannot generate music: the Markov chain has no transitions. "
            "Use a longer input sequence or adjust the pattern parameters."
        )

    # Start from a state that has at least one observed outgoing transition.
    current_token = random.choice(list(chain.keys()))
    generated_sequence = list(current_token)

    while len(generated_sequence) < target_note_count:
        if current_token in chain and chain[current_token]:
            candidates, weights = zip(*chain[current_token].items())
            next_token = random.choices(candidates, weights=weights, k=1)[0]
        else:
            # Restart from a known state if the current token has no transition.
            next_token = random.choice(list(chain.keys()))

        generated_sequence.extend(next_token)
        current_token = next_token

    return generated_sequence


# ---------------------------------------------------------------------------
# 4. MIDI generation
# ---------------------------------------------------------------------------

def run_markov(
    input_midi,
    output_midi="output_rested.mid",
    target_notes=120,
    k=3,
    t=12,
):
    """
    Process each non-empty MIDI instrument and write a generated MIDI file.

    Args:
        input_midi: Path to the source MIDI file.
        output_midi: Path where the generated MIDI file will be saved.
        target_notes: Approximate minimum number of generated note events.
        k: Minimum occurrence count for a pattern to be considered frequent.
        t: Maximum length of a mined pattern, in musical events.
    """
    # Load the source MIDI and estimate its tempo for the output file.
    midi = pretty_midi.PrettyMIDI(input_midi)
    tempo = midi.estimate_tempo() if midi.instruments else 120.0
    output = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    for track_index, instrument in enumerate(midi.instruments):
        if not instrument.notes:
            continue

        # Convert notes to events, mine patterns, and treat each resulting
        # pattern as one state in the Markov chain.
        raw_sequence = extract_sequence_with_rests(instrument)
        if not raw_sequence:
            continue

        tokens, patterns = frequent_patterns(
            raw_sequence,
            k=k,
            max_length=t,
        )

        chain = build_state_machine(tokens)
        generated_events = generate_music(chain, target_note_count=target_notes)

        # Preserve the source instrument's program, drum flag, and track name.
        new_instrument = pretty_midi.Instrument(
            program=instrument.program,
            is_drum=instrument.is_drum,
            name=instrument.name,
        )

        current_time = 0.0

        for pitch, start_offset, duration in generated_events:
            # Advance by the gap before the note, then create the note.
            current_time += start_offset
            note = pretty_midi.Note(
                velocity=100,
                pitch=pitch,
                start=current_time,
                end=current_time + duration,
            )
            new_instrument.notes.append(note)

            # Advance to the end of the note before processing the next event.
            current_time += duration

        output.instruments.append(new_instrument)
        print(
            f"Track {track_index + 1} ('{instrument.name}'): "
            "processed successfully with rests represented."
        )

    # Write the generated composition to disk.
    output.write(output_midi)
    print(f"\nGenerated MIDI file saved to '{output_midi}'.")


# ---------------------------------------------------------------------------
# 5. Command-line entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Expected arguments: input MIDI, output MIDI, target event count,
    # minimum pattern frequency (k), and maximum pattern length (t).
    if len(sys.argv) != 6:
        print(
            f"Usage: python3 {sys.argv[0]} "
            "<input.mid> <output.mid> <number_of_notes> <k> <t>"
        )
        sys.exit(1)

    try:
        run_markov(
            input_midi=sys.argv[1],
            output_midi=sys.argv[2],
            target_notes=int(sys.argv[3]),
            k=int(sys.argv[4]),
            t=int(sys.argv[5]),
        )
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
