"""
Run the Markov music generation algorithm on every MIDI file in a folder.

Generated files are saved in an "output" subfolder and named
"generated_<original_filename>.mid".
"""

from pathlib import Path
import argparse

from markov_music import run_markov


def process_folder(input_folder, target_notes=120, k=3, t=12):
    """Process all MIDI files in the input folder."""
    input_path = Path(input_folder)

    if not input_path.is_dir():
        raise NotADirectoryError(f"Input folder not found: {input_path}")

    # Create the output folder if it does not already exist.
    output_path = Path.cwd() / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    # Find MIDI files directly inside the input folder.
    midi_files = sorted(
        path for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() == ".mid"
    )

    if not midi_files:
        print(f"No MIDI files found in '{input_path}'.")
        return

    print(f"Found {len(midi_files)} MIDI file(s).")

    for midi_file in midi_files:
        # Prefix the original filename with "generated_".
        output_file = output_path / f"generated_{midi_file.name}"

        print(f"\nProcessing: {midi_file.name}")

        try:
            run_markov(
                input_midi=str(midi_file),
                output_midi=str(output_file),
                target_notes=target_notes,
                k=k,
                t=t,
            )
        except Exception as error:
            # Continue processing the remaining files if one file fails.
            print(f"Failed to process '{midi_file.name}': {error}")

    print(f"\nBatch processing finished. Output folder: '{output_path}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate MIDI files in batch using a Markov chain."
    )
    parser.add_argument("input_folder", help="Folder containing MIDI files.")
    parser.add_argument(
        "--notes", type=int, default=120,
        help="Target number of generated note events (default: 120)."
    )
    parser.add_argument(
        "--k", type=int, default=3,
        help="Minimum pattern frequency (default: 3)."
    )
    parser.add_argument(
        "--t", type=int, default=12,
        help="Maximum pattern length (default: 12)."
    )

    args = parser.parse_args()

    process_folder(
        input_folder=args.input_folder,
        target_notes=args.notes,
        k=args.k,
        t=args.t,
    )
