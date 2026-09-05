#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

STOP_WORDS = {
    "eng": {"the", "and", "to", "of", "a", "in", "that", "is", "i", "it", "you", "this", "for", "on", "are", "with", "as", "but", "we", "they", "was", "have", "me", "my", "not"},
    "nld": {"de", "en", "van", "ik", "te", "dat", "die", "in", "een", "hij", "het", "niet", "zijn", "is", "was", "op", "aan", "met", "als", "voor", "mij", "je", "wat", "maar", "ze"},
    "nor": {"og", "i", "jeg", "det", "at", "en", "et", "den", "til", "er", "som", "på", "de", "med", "han", "av", "ikke", "for", "der", "var", "meg", "vi", "har", "kan", "så"},
    "nob": {"og", "i", "jeg", "det", "at", "en", "et", "den", "til", "er", "som", "på", "de", "med", "han", "av", "ikke", "for", "der", "var", "meg", "vi", "har", "kan", "så"},
    "nno": {"og", "i", "eg", "det", "at", "ein", "den", "til", "er", "som", "på", "dei", "med", "han", "av", "ikkje", "for", "der", "var", "meg", "vi", "har", "kan", "så"},
    "fra": {"le", "la", "les", "et", "de", "des", "je", "il", "elle", "ce", "qui", "que", "dans", "pour", "pas", "un", "une", "sur", "est", "avec", "vous", "tu", "ne", "me"},
    "spa": {"el", "la", "los", "las", "y", "de", "que", "en", "a", "un", "una", "por", "con", "no", "es", "su", "para", "como", "me", "te", "lo", "pero", "si", "qué", "mi"},
    "deu": {"der", "die", "das", "und", "in", "zu", "den", "auf", "für", "ist", "von", "mit", "sich", "des", "ein", "eine", "nicht", "dem", "es", "ich", "sie", "er", "wir", "du"},
    "swe": {"och", "i", "att", "det", "som", "en", "på", "är", "av", "för", "med", "till", "den", "har", "de", "inte", "om", "ett", "han", "men", "jag", "vi", "du", "mig", "kan"},
    "dan": {"og", "i", "jeg", "det", "at", "en", "den", "til", "er", "som", "på", "de", "med", "han", "af", "for", "ikke", "der", "hvad", "mig", "har", "vi", "kan", "du"},
    "fin": {"ja", "on", "ei", "niin", "se", "että", "hän", "mutta", "ovat", "kuin", "myös", "kun", "tai", "jotka", "mitä", "jo", "sen", "lisäksi", "vaan", "minä", "sinä", "me", "te"},
    "ita": {"il", "la", "i", "le", "di", "e", "che", "in", "a", "un", "una", "per", "con", "non", "è", "su", "come", "mi", "ti", "lo", "ma", "se", "ho", "ha", "o"},
    "por": {"o", "a", "os", "as", "e", "de", "que", "em", "um", "uma", "por", "com", "não", "é", "seu", "para", "como", "me", "te", "se", "mas", "na", "no", "eu", "ele"},
    "tur": {"ve", "bir", "bu", "da", "de", "için", "çok", "ile", "o", "en", "daha", "ben", "sen", "ama", "var", "yok", "gibi", "kadar", "mı", "mi", "ki", "ne", "sonra"},
    "pol": {"w", "i", "z", "na", "nie", "do", "że", "o", "to", "się", "jak", "jest", "co", "od", "za", "ale", "po", "dla", "tym", "czy", "tak", "ja", "ty", "mnie"},
}

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

def detect_language_from_srt(srt_path):
    try:
        with open(srt_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            text = f.read()
    except OSError:
        return None
        
    text = re.sub(r'<[^>]+>', '', text)
    words = re.findall(r'\b[a-zåæøæöäüß]+\b', text.lower())
    
    word_counts = {}
    for w in words:
        word_counts[w] = word_counts.get(w, 0) + 1
        
    scores = {}
    for lang, stopwords in STOP_WORDS.items():
        score = sum(word_counts.get(w, 0) for w in stopwords)
        if score > 0:
            scores[lang] = score
            
    if not scores:
        return None
        
    best_lang = max(scores, key=scores.get)
    if scores[best_lang] >= 5:
        return best_lang, scores
    return None


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
        help="List of MKV language codes to process (if omitted, all PGS subtitles are converted)",
    )
    parser.add_argument(
        "--map-lang",
        nargs=2,
        action="append",
        metavar=("MKV_LANG", "TESS_LANG"),
        help="Override a specific MKV language code with a different language for both OCR and the final video (e.g., --map-lang nor eng)",
    )
    parser.add_argument(
        "--map-stream",
        nargs=2,
        action="append",
        metavar=("STREAM_INDEX", "TARGET_LANG"),
        help="Override the language for a specific stream index, useful if only one specific track is mislabeled (e.g., --map-stream 8 eng)",
    )
    parser.add_argument(
        "--force-ocr-lang",
        metavar="LANG",
        help="Force a specific Tesseract language model for ALL converted streams, ignoring their MKV tags",
    )
    parser.add_argument(
        "--replace-original",
        action="store_true",
        help="Remove the original file and replace it with the new one if successful",
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

    if output_path.resolve() == input_path.resolve():
        print("Error: Output file cannot be the same as the input file.", file=sys.stderr)
        sys.exit(1)

    try:
        streams = get_streams(input_path)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}", file=sys.stderr)
        sys.exit(1)

    # Identify streams to replace
    replace_streams = {}  # orig_stream_index -> dict
    for stream in streams:
        if (
            stream.get("codec_type") == "subtitle"
            and stream.get("codec_name") == "hdmv_pgs_subtitle"
        ):
            tags = stream.get("tags", {})
            orig_lang = tags.get("language", "").lower()

            final_mkv_lang = orig_lang
            auto_detect = True

            stream_overridden = False
            if args.map_stream:
                for m_idx, m_lang in args.map_stream:
                    if str(stream["index"]) == str(m_idx):
                        final_mkv_lang = m_lang.lower()
                        stream_overridden = True
                        auto_detect = False
                        break

            if not stream_overridden and args.map_lang:
                for m_orig, m_new in args.map_lang:
                    if orig_lang == m_orig.lower():
                        final_mkv_lang = m_new.lower()
                        auto_detect = False
                        break

            if not final_mkv_lang or final_mkv_lang == "und":
                print(
                    f"Skipping stream {stream['index']} because language is undefined."
                )
                continue

            tess_lang = LANG_MAP.get(final_mkv_lang, final_mkv_lang)

            if args.force_ocr_lang:
                tess_lang = args.force_ocr_lang.lower()
                auto_detect = False

            if args.langs is None or orig_lang in args.langs or final_mkv_lang in args.langs:
                replace_streams[stream["index"]] = {
                    "mkv_lang": final_mkv_lang,
                    "tess_lang": tess_lang,
                    "auto_detect": auto_detect
                }

    if not replace_streams:
        print("No matching PGS subtitles found to convert.")
        sys.exit(0)

    print(f"Found {len(replace_streams)} PGS subtitle(s) to convert:")
    for idx, info in replace_streams.items():
        print(f"  - Stream {idx}: {info['mkv_lang']} (Tesseract: {info['tess_lang']})")

    script_dir = Path(__file__).parent.resolve()
    pgstosrt_bin = script_dir / "pgstosrt.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        srt_files = {}  # stream_index -> path to srt

        # Extract and convert
        for idx, info in replace_streams.items():
            orig_lang = info["mkv_lang"]
            tess_lang = info["tess_lang"]
            auto_detect = info["auto_detect"]
            
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

            success = False
            try:
                subprocess.run(pgs_cmd, check=True)
                success = True
            except subprocess.CalledProcessError:
                pass
                
            discovery_mode = False
            
            # If the OCR container failed, try falling back to the "eng" model to rescue it
            # This handles cases where Tesseract refuses to run because we mapped to a language
            # that isn't actually installed in the container!
            if not success:
                if tess_lang != "eng":
                    print(f"\n[Stream {idx}] OCR failed with model '{tess_lang}'. It may be missing from the container.")
                    print(f"[Stream {idx}] Running discovery pass with the 'eng' model...")
                    
                    pgs_cmd_eng = [
                        sys.executable,
                        str(pgstosrt_bin),
                        "-l",
                        "eng",
                    ]
                    if args.image:
                        pgs_cmd_eng.extend(["-i", args.image])
                    pgs_cmd_eng.append(str(sup_file))
                    
                    try:
                        subprocess.run(pgs_cmd_eng, check=True)
                        success = True
                        discovery_mode = True
                    except subprocess.CalledProcessError:
                        print(f"Error: Discovery pass failed for stream {idx}.", file=sys.stderr)
                
                if not success:
                    print(f"Error: Could not convert stream {idx}. Skipping...", file=sys.stderr)
                    continue

            if not srt_file.is_file():
                print(
                    f"Error: Conversion succeeded but expected output {srt_file} was not found.",
                    file=sys.stderr,
                )
                continue

            if auto_detect:
                detected = detect_language_from_srt(srt_file)
                if detected:
                    best_lang, scores = detected
                    current_score = scores.get(tess_lang, 0)
                    best_score = scores[best_lang]
                    
                    if discovery_mode:
                        if best_lang == "eng":
                            print(f"\n[Stream {idx}] DISCOVERY SUCCESS: Detected text is 'eng'. Rescuing stream!")
                            replace_streams[idx]["mkv_lang"] = "eng"
                            replace_streams[idx]["tess_lang"] = "eng"
                            srt_files[idx] = srt_file
                            continue
                        else:
                            # The fallback was able to OCR the text using the english alphabet, and the text
                            # looks like another language. But since we are here, we know the correct language
                            # model was missing. Let's try to re-run it anyway in case it works.
                            pass

                    # Only override if the best detected language severely outscores the current one
                    # e.g., if it's more than double the score. This prevents oscillating 
                    # between extremely similar languages like dan/nor unless the difference is massive.
                    if best_lang != tess_lang and best_score > (current_score * 2):
                        print(f"\n[Stream {idx}] AUTO-CORRECTION: Detected text is highly likely '{best_lang}' (scored {best_score} vs {current_score} for metadata '{tess_lang}').")
                        print(f"[Stream {idx}] Re-running OCR with the corrected '{best_lang}' model...")
                        
                        # Re-run OCR with the correct model
                        pgs_cmd_rerun = [
                            sys.executable,
                            str(pgstosrt_bin),
                            "-l",
                            best_lang,
                        ]
                        if args.image:
                            pgs_cmd_rerun.extend(["-i", args.image])
                        pgs_cmd_rerun.append(str(sup_file))
                        
                        try:
                            subprocess.run(pgs_cmd_rerun, check=True)
                            
                            # Update our dictionary so remuxing applies the newly corrected language tag
                            replace_streams[idx]["mkv_lang"] = best_lang
                            replace_streams[idx]["tess_lang"] = best_lang
                        except subprocess.CalledProcessError:
                            if discovery_mode:
                                print(f"Error: Could not convert stream {idx}. Missing language model '{best_lang}'. Skipping...", file=sys.stderr)
                                continue
                            else:
                                print(f"Error: Auto-correction re-run failed for stream {idx}. Keeping original result.", file=sys.stderr)

            srt_files[idx] = srt_file

        print("\nAll target subtitles converted successfully. Remuxing video...")

        def get_executable_path(name):
            path_env = os.environ.get("PATH", os.defpath)
            for path_dir in path_env.split(os.pathsep):
                path_dir = path_dir.strip('"')
                exe_file = Path(path_dir) / name
                if exe_file.is_file() and os.access(exe_file, os.X_OK):
                    return str(exe_file)
            return None

        if output_path.suffix.lower() == ".mkv" and get_executable_path("mkvmerge"):
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
                    orig_lang = replace_streams[orig_idx]["mkv_lang"]
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

                    orig_lang = replace_streams[orig_idx]["mkv_lang"]
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

    if args.replace_original:
        print(f"Replacing original file {input_path}...")
        try:
            os.replace(output_path, input_path)
            print("Successfully replaced original file.")
        except OSError as e:
            print(f"Error replacing original file: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
