# MIDI Generation with Frequent Patterns and a Markov Chain

This project generates a new MIDI sequence from an input MIDI file. For each
non-empty instrument track, it extracts note events, mines frequent maximal
patterns, builds a first-order Markov chain over those patterns, and samples
transitions to generate a new sequence.

## Requirements

- Python 3.9 or newer
- The Python package `pretty_midi`

The remaining imports (`random`, `sys`, and `collections`) are part of Python's
standard library.

## Usage

Run the script with five positional arguments:

```bash
python3 markov_music.py <input.mid> <output.mid> <number_of_notes> <k> <t>
```

Example:

```bash
python3 markov_music.py input.mid generated.mid 120 3 12
```

Arguments:

| Argument | Meaning |
| --- | --- |
| `input.mid` | Path to the source MIDI file. |
| `output.mid` | Destination path for the generated MIDI file. |
| `number_of_notes` | Approximate minimum number of generated note events per non-empty track. Pattern tokens can contain multiple events, so the result may exceed this number. |
| `k` | Minimum number of occurrences required for a pattern to be considered frequent. |
| `t` | Maximum length of a mined pattern, measured in note events. |

For example, increasing `k` makes the pattern-frequency requirement stricter.
Increasing `t` allows the mining step to consider longer patterns. The script
uses a minimum pattern length of two events.

## How it works

### 1. Extract note events

Each MIDI note is represented by a tuple:

```text
(pitch, start_offset, duration)
```

- `pitch`: MIDI pitch number.
- `start_offset`: time between the previous note's end and this note's start.
- `duration`: note duration.

Time values are quantized to a grid of `0.125` seconds. Note durations are
kept at least one grid step long, while start offsets can be zero. The current
representation is best suited to monophonic or non-overlapping note sequences;
it does not faithfully model arbitrary polyphonic overlap.

### 2. Mine frequent maximal patterns

The algorithm counts contiguous subsequences whose lengths are between two and
`t` events. A pattern is frequent when it occurs at least `k` times. A frequent
pattern is considered maximal if no one-event left or right extension is also
frequent.

The sequence is then segmented greedily using the discovered maximal patterns.
Events not covered by a selected pattern become single-event tokens.

### 3. Build a Markov chain

Each token (a pattern, possibly containing several note events) is a state.
The algorithm counts transitions between adjacent tokens in the segmented
training sequence. During generation, the next token is sampled with a
probability proportional to its observed transition count.

### 4. Generate a MIDI file

The generated tokens are expanded back into note events. The output preserves
each source track's instrument program, drum flag, and name. Note velocity is
set to `100` for generated notes.

## Batch Processing

The `batch_generate.py` script allows you to process multiple MIDI files automatically using the Markov music generation algorithm.

### Usage

Place `batch_generate.py` in the same directory as `markov_music.py`. Then, run the following command from the project directory:

```bash
python3 batch_generate.py <input_folder>
```

Replace `<input_folder>` with the path to the directory containing the MIDI files you want to process.

For example:

```bash
python3 batch_generate.py midis
```

The script processes all `.mid` files directly inside the specified directory and saves the generated files in an `output` subdirectory. Each output file is named `generated_<original_filename>.mid`.

### Optional Parameters

You can customize the generation parameters using the following options:

```bash
python3 batch_generate.py midis --notes 200 --k 4 --t 10
```

- `--notes`: Target number of generated note events per track (default: `120`).
- `--k`: Minimum number of occurrences required for a pattern to be considered frequent (default: `3`).
- `--t`: Maximum pattern length, measured in note events (default: `12`).

The output directory is created automatically if it does not exist. If a file fails to process, the script reports the error and continues with the remaining files.
