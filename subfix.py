#!/usr/bin/env python3.12
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESSERACT_LANGS = {
    "afr",
    "amh",
    "ara",
    "asm",
    "aze",
    "aze_cyrl",
    "bel",
    "ben",
    "bod",
    "bos",
    "bre",
    "bul",
    "cat",
    "ceb",
    "ces",
    "chi_sim",
    "chi_sim_vert",
    "chi_tra",
    "chi_tra_vert",
    "chr",
    "cos",
    "cym",
    "dan",
    "deu",
    "deu_latf",
    "div",
    "dzo",
    "ell",
    "eng",
    "enm",
    "epo",
    "equ",
    "est",
    "eus",
    "fao",
    "fas",
    "fil",
    "fin",
    "fra",
    "frm",
    "fry",
    "gla",
    "gle",
    "glg",
    "grc",
    "guj",
    "hat",
    "heb",
    "hin",
    "hrv",
    "hun",
    "hye",
    "iku",
    "ind",
    "isl",
    "ita",
    "ita_old",
    "jav",
    "jpn",
    "jpn_vert",
    "kan",
    "kat",
    "kat_old",
    "kaz",
    "khm",
    "kir",
    "kmr",
    "kor",
    "kor_vert",
    "lao",
    "lat",
    "lav",
    "lit",
    "ltz",
    "mal",
    "mar",
    "mkd",
    "mlt",
    "mon",
    "mri",
    "msa",
    "mya",
    "nep",
    "nld",
    "nor",
    "oci",
    "ori",
    "osd",
    "pan",
    "pol",
    "por",
    "pus",
    "que",
    "ron",
    "rus",
    "san",
    "sin",
    "slk",
    "slv",
    "snd",
    "spa",
    "spa_old",
    "sqi",
    "srp",
    "srp_latn",
    "sun",
    "swa",
    "swe",
    "syr",
    "tam",
    "tat",
    "tel",
    "tgk",
    "tha",
    "tir",
    "ton",
    "tur",
    "uig",
    "ukr",
    "urd",
    "uzb",
    "uzb_cyrl",
    "vie",
    "yid",
    "yor",
}

# MKV heavily utilizes ISO 639-2/B (bibliographic) standard for languages.
# Tesseract requires ISO 639-2/T (terminological) or 3-letter ISO-639-3 standard.
LANG_MAP = {
    "ger": "deu",  # German
    "fre": "fra",  # French
    "dut": "nld",  # Dutch
    "gre": "ell",  # Greek
    "rum": "ron",  # Romanian
    "cze": "ces",  # Czech
    "wel": "cym",  # Welsh
    "mac": "mkd",  # Macedonian
    "ice": "isl",  # Icelandic
    "slo": "slk",  # Slovak
    "tib": "bod",  # Tibetan
    "bur": "mya",  # Burmese
    "arm": "hye",  # Armenian
    "geo": "kat",  # Georgian
    "alb": "sqi",  # Albanian
    "baq": "eus",  # Basque
    "per": "fas",  # Persian
    "may": "msa",  # Malay
    "mao": "mri",  # Maori
    "chi": "chi_sim",  # Chinese (default to simplified for Tesseract)
    "zho": "chi_sim",  # Chinese
}


def get_streams(input_file):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_name,codec_type,disposition",
        "-show_entries",
        "stream_tags=language,title",
        "-of",
        "json",
        str(input_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout).get("streams", [])


def main():
    parser = argparse.ArgumentParser(
        description="Extracts specific PGS subtitles, converts them to SRT, and replaces them in the video."
    )
    parser.add_argument("input", help="Input video file (e.g. .mkv)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output video file (defaults to appending '_fixed' to filename)",
    )
    parser.add_argument(
        "-l",
        "--langs",
        nargs="+",
        help="List of language codes to convert (if omitted, all PGS subtitles are converted)",
    )
    parser.add_argument(
        "-i",
        "--image",
        help="Container image to use for PgsToSrt (passes through to pgstosrt.py)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: Input file '{input_path}' not found", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(
            f"{input_path.stem}_fixed{input_path.suffix}"
        )

    try:
        streams = get_streams(input_path)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}", file=sys.stderr)
        sys.exit(1)

    # Identify streams to replace
    replace_streams = {}  # orig_stream_index -> (orig_lang, tess_lang)
    for stream in streams:
        if (
            stream.get("codec_type") == "subtitle"
            and stream.get("codec_name") == "hdmv_pgs_subtitle"
        ):
            tags = stream.get("tags", {})
            orig_lang = tags.get("language", "").lower()

            if not orig_lang or orig_lang == "und":
                print(
                    f"Skipping stream {stream['index']} because language is undefined."
                )
                continue

            tess_lang = LANG_MAP.get(orig_lang, orig_lang)

            if tess_lang not in TESSERACT_LANGS:
                print(
                    f"Skipping stream {stream['index']} because language '{tess_lang}' (mapped from '{orig_lang}') is not supported by Tesseract."
                )
                continue

            if args.langs is None or tess_lang in args.langs or orig_lang in args.langs:
                replace_streams[stream["index"]] = (orig_lang, tess_lang)

    if not replace_streams:
        print("No matching PGS subtitles found to convert.")
        sys.exit(0)

    print(f"Found {len(replace_streams)} PGS subtitle(s) to convert:")
    for idx, (orig_lang, tess_lang) in replace_streams.items():
        print(f"  - Stream {idx}: {orig_lang} (Tesseract: {tess_lang})")

    script_dir = Path(__file__).parent.resolve()
    pgstosrt_bin = script_dir / "pgstosrt.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        srt_files = {}  # stream_index -> path to srt

        # Extract and convert
        for idx, (orig_lang, tess_lang) in replace_streams.items():
            sup_file = tmp_path / f"track_{idx}.sup"
            srt_file = tmp_path / f"track_{idx}.srt"

            print(f"\n[Stream {idx}] Extracting PGS subtitle...")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(input_path),
                    "-map",
                    f"0:{idx}",
                    "-c",
                    "copy",
                    str(sup_file),
                ],
                check=True,
            )

            print(
                f"[Stream {idx}] Converting to SRT via container (language: {tess_lang})..."
            )
            # Call pgstosrt.py
            pgs_cmd = [
                sys.executable,
                str(pgstosrt_bin),
                "-l",
                tess_lang,
            ]
            if args.image:
                pgs_cmd.extend(["-i", args.image])
            pgs_cmd.append(str(sup_file))

            try:
                subprocess.run(pgs_cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error: Conversion failed for stream {idx}.", file=sys.stderr)
                sys.exit(e.returncode)

            if not srt_file.is_file():
                print(
                    f"Error: Conversion succeeded but expected output {srt_file} was not found.",
                    file=sys.stderr,
                )
                sys.exit(1)

            srt_files[idx] = srt_file

        print("\nAll target subtitles converted successfully. Remuxing video...")

        if output_path.suffix.lower() == ".mkv" and shutil.which("mkvmerge"):
            print("Using mkvmerge for lossless surgical remuxing...")

            # Determine subtitle tracks to KEEP from the original file
            keep_subtitle_ids = []
            for stream in streams:
                if (
                    stream.get("codec_type") == "subtitle"
                    and stream["index"] not in replace_streams
                ):
                    keep_subtitle_ids.append(str(stream["index"]))

            mkvmerge_cmd = ["mkvmerge", "-o", str(output_path)]

            if keep_subtitle_ids:
                mkvmerge_cmd.extend(["--subtitle-tracks", ",".join(keep_subtitle_ids)])
            else:
                mkvmerge_cmd.append("--no-subtitles")

            mkvmerge_cmd.append(str(input_path))

            track_order = []
            srt_file_indices = {}

            # input_path is file index 0
            # Next files (srt) are index 1, 2, ...
            file_idx = 1
            for idx in sorted(srt_files.keys()):
                srt_file_indices[idx] = file_idx
                file_idx += 1

            for stream in streams:
                orig_idx = stream["index"]
                if orig_idx in replace_streams:
                    orig_lang, _tess_lang = replace_streams[orig_idx]
                    f_idx = srt_file_indices[orig_idx]

                    mkvmerge_cmd.extend(["--language", f"0:{orig_lang}"])

                    title = stream.get("tags", {}).get("title")
                    if title:
                        mkvmerge_cmd.extend(["--track-name", f"0:{title}"])

                    disp = stream.get("disposition", {})
                    mkvmerge_cmd.extend(
                        [
                            "--default-track-flag",
                            f"0:{'yes' if disp.get('default') == 1 else 'no'}",
                        ]
                    )
                    mkvmerge_cmd.extend(
                        [
                            "--forced-display-flag",
                            f"0:{'yes' if disp.get('forced') == 1 else 'no'}",
                        ]
                    )

                    mkvmerge_cmd.append(str(srt_files[orig_idx]))
                    track_order.append(f"{f_idx}:0")
                else:
                    track_order.append(f"0:{orig_idx}")

            if track_order:
                mkvmerge_cmd.extend(["--track-order", ",".join(track_order)])

            print(f"Running mkvmerge to generate: {output_path}")
            subprocess.run(mkvmerge_cmd, check=True)

        else:
            print("Using ffmpeg for remuxing...")
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(input_path)]

            # Add all new srt files as inputs to ffmpeg
            srt_inputs = []
            for idx in sorted(srt_files.keys()):
                ffmpeg_cmd.extend(["-i", str(srt_files[idx])])
                srt_inputs.append(idx)

            ffmpeg_cmd.extend(["-map_metadata", "0", "-map_chapters", "0"])

            # Map original streams, swapping the replaced ones
            # and carry over metadata / dispositions manually for swapped streams
            for new_idx, stream in enumerate(streams):
                orig_idx = stream["index"]
                if orig_idx in replace_streams:
                    # Map the newly created SRT input instead
                    # input 0 is original video, input 1..N are the SRT files
                    input_idx = srt_inputs.index(orig_idx) + 1
                    ffmpeg_cmd.extend(["-map", f"{input_idx}:0"])

                    # Convert to appropriate text container format based on output
                    if output_path.suffix.lower() == ".mp4":
                        ffmpeg_cmd.extend([f"-c:{new_idx}", "mov_text"])
                    else:
                        ffmpeg_cmd.extend([f"-c:{new_idx}", "srt"])

                    orig_lang, _tess_lang = replace_streams[orig_idx]
                    ffmpeg_cmd.extend(
                        [f"-metadata:s:{new_idx}", f"language={orig_lang}"]
                    )

                    if "title" in stream.get("tags", {}):
                        ffmpeg_cmd.extend(
                            [
                                f"-metadata:s:{new_idx}",
                                f"title={stream['tags']['title']}",
                            ]
                        )

                    for disp_k, disp_v in stream.get("disposition", {}).items():
                        if disp_v == 1:
                            ffmpeg_cmd.extend(
                                [f"-disposition:s:{new_idx}", f"{disp_k}=1"]
                            )
                        else:
                            # explicitly set to 0 just to avoid default inheritance issues in ffmpeg
                            ffmpeg_cmd.extend(
                                [f"-disposition:s:{new_idx}", f"{disp_k}=0"]
                            )
                else:
                    # Map original stream unmodified
                    ffmpeg_cmd.extend(["-map", f"0:{orig_idx}"])
                    ffmpeg_cmd.extend([f"-c:{new_idx}", "copy"])

            ffmpeg_cmd.append(str(output_path))

            print(f"Running ffmpeg to generate: {output_path}")
            subprocess.run(ffmpeg_cmd, check=True)

    print(f"\nDone! Output saved to: {output_path}")


if __name__ == "__main__":
    main()
