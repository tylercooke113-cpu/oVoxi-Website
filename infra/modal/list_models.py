"""
One-shot model discovery — run with: modal run infra/modal/list_models.py
CPU only; no GPU, no secrets, no torch. Output goes into stem_worker.py constants.
"""

import modal

app = modal.App("ovoxi-list-models")

_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(["ffmpeg"])
    .pip_install("audio-separator[cpu]==0.31.3")
)


@app.function(image=_image, timeout=120)
def list_models():
    """
    Print the complete audio-separator 0.31.3 downloadable model catalogue.
    Run with: modal run infra/modal/list_models.py
    """
    import json
    from pathlib import Path
    import audio_separator
    from audio_separator.separator import Separator

    pkg_root = Path(audio_separator.__file__).parent

    # --- Full models.json ---
    models_json = pkg_root / "models.json"
    print("=== models.json (full) ===")
    data = json.loads(models_json.read_text())
    for section, entries in data.items():
        print(f"\n[{section}]")
        if isinstance(entries, dict):
            for display_name, checkpoint in entries.items():
                print(f"  {display_name}")
                print(f"    -> {checkpoint}")
        else:
            print(f"  {entries}")

    # --- get_simplified_model_list() ---
    print("\n\n=== get_simplified_model_list() ===")
    sep = Separator()
    try:
        simple = sep.get_simplified_model_list()
        if isinstance(simple, dict):
            for k, v in sorted(simple.items()):
                print(f"  {k}: {v}")
        else:
            for item in simple:
                print(f"  {item}")
    except Exception as e:
        print(f"  (failed: {e})")
