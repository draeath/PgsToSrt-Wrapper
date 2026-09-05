#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import srt
except ImportError:
    srt = None


def main():
    parser = argparse.ArgumentParser(
        description="Wrapper for PgsToSrt running via podman/docker.",
        epilog='Example: ./pgstosrt.py -l eng "video.sup"',
    )
    parser.add_argument(
        "input", help="Input file name (with or without the .sup extension)"
    )
    parser.add_argument(
        "-l", "--language", default="eng", help="Tesseract language code (default: eng)"
    )
    parser.add_argument(
        "--replace",
        nargs=2,
        metavar=("REGEX", "REPLACEMENT"),
        action="append",
        help="Regular expression and replacement string to apply to the subtitle text (can be used multiple times). Example: --replace 'O' '0'",
    )
    parser.add_argument(
        "-i",
        "--image",
        default="localhost/tentacule/pgstosrt:latest",
        help="Container image to use (default: localhost/tentacule/pgstosrt:latest)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    # If the user didn't provide the .sup extension, append it automatically
    if input_path.suffix.lower() != ".sup":
        input_path = Path(str(input_path) + ".sup")

    # The output is always .srt
    output_path = input_path.with_suffix(".srt")

    if not input_path.is_file():
        print(f"Error: Input file '{input_path}' not found!", file=sys.stderr)
        sys.exit(1)

    # The output SRT file must be touched before running the container
    # so podman mounts it as a file rather than creating a directory.
    try:
        output_path.touch(exist_ok=True)
    except OSError as e:
        print(
            f"Error: Could not touch output file '{output_path}': {e}", file=sys.stderr
        )
        sys.exit(1)

    # Podman volume mounts require absolute paths
    input_abs = input_path.resolve()
    output_abs = output_path.resolve()

    image_name = args.image

    def get_executable_path(name):
        path_env = os.environ.get("PATH", os.defpath)
        for path_dir in path_env.split(os.pathsep):
            path_dir = path_dir.strip('"')
            exe_file = Path(path_dir) / name
            if exe_file.is_file() and os.access(exe_file, os.X_OK):
                return str(exe_file)
        return None

    container_engine = get_executable_path("podman")
    if not container_engine:
        container_engine = get_executable_path("docker")

    if not container_engine:
        print(
            "Error: Neither 'podman' nor 'docker' executable found on PATH.",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        container_engine,
        "run",
        "-it",
        "--rm",
        "-v",
        f"{input_abs}:/input.sup:ro",
        "-v",
        f"{output_abs}:/output.srt:rw",
        "-e",
        f"LANGUAGE={args.language}",
        image_name,
    ]

    print(f"Language: {args.language}")
    print(f"Input:    {input_abs}")
    print(f"Output:   {output_abs}")
    print(f"Image:    {image_name}")
    print("-" * 50)

    try:
        # subprocess.run with a list naturally handles safe quoting/escaping of arguments
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(
            f"\nError: {container_engine} command failed with exit code {e.returncode}",
            file=sys.stderr,
        )
        sys.exit(e.returncode)

    # Post-process the SRT file if --replace arguments were provided
    if args.replace and output_path.is_file():
        if srt is None:
            print(
                "Error: The 'srt' module is required for text replacement.",
                file=sys.stderr,
            )
            print("Please install it by running: pip install srt", file=sys.stderr)
            sys.exit(1)

        print("Applying regular expression replacements to subtitle text...")
        try:
            with open(output_path, "r", encoding="utf-8-sig") as f:
                srt_content = f.read()

            subs = list(srt.parse(srt_content))

            for sub in subs:
                for pattern, repl in args.replace:
                    sub.content = re.sub(pattern, repl, sub.content)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt.compose(subs))

            print("Replacements applied successfully.")
        except OSError as e:
            print(f"Error reading or writing SRT file: {e}", file=sys.stderr)
            sys.exit(1)
        except srt.SRTParseError as e:
            print(f"Error parsing SRT file: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
