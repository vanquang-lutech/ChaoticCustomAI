"""Try the product-customisation prompts against the real API.

Unlike the older scripts, this one imports the prompt builders from ``src.prompts`` instead of
carrying its own copy, so what is tried here is exactly what the service sends.

    python scripts/custom_product.py            run every case against the API
    python scripts/custom_product.py --dump     print the prompts, spend nothing

Edit the run list at the bottom. Each run writes its result and the exact prompt that produced
it next to each other, so a bad output can be read against its own instructions.
"""

import base64
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.prompts.custom_product import (  # noqa: E402
    build_custom_product_note_prompt,
    build_custom_product_note_with_reference_prompt,
    build_custom_product_remove_prompt,
    build_custom_product_replace_and_remove_prompt,
    build_custom_product_replace_prompt,
)

load_dotenv()

DUMP_ONLY = "--dump" in sys.argv

if not DUMP_ONLY and not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY before running this script.")

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
QUALITY = os.getenv("IMAGE_QUALITY", "medium")

client = None if DUMP_ONLY else OpenAI()

run_id = time.strftime("%Y%m%d_%H%M%S")
asset_dir = (
    Path("storage") / time.strftime("%Y_%m") / time.strftime("%Y_%m_%d") / "custom_product" / run_id
)


def customize(
    label: str,
    template_path: Path,
    prompt: str,
    reference_path: Path | None = None,
) -> Path:
    if not template_path.exists():
        raise FileNotFoundError(f"Template image not found: {template_path}")

    output_dir = asset_dir / label
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    paths = [template_path] + ([reference_path] if reference_path else [])
    handles = [path.open("rb") for path in paths]
    start_time = time.time()
    try:
        result = client.images.edit(
            model=IMAGE_MODEL,
            image=handles[0] if len(handles) == 1 else handles,
            prompt=prompt,
            # Both pinned on purpose: "auto" size keeps a two-view mock-up from being cropped
            # or squashed, and "auto" background leaves the product photo's own backdrop alone.
            size="auto",
            background="auto",
            quality=QUALITY,
            output_format="png",
        )
    finally:
        for handle in handles:
            handle.close()

    if not result.data or not result.data[0].b64_json:
        raise RuntimeError("OpenAI did not return image data.")

    output_path = output_dir / "result.png"
    output_path.write_bytes(base64.b64decode(result.data[0].b64_json))

    usage = getattr(result, "usage", None)
    print(f"[{label}] {time.time() - start_time:.2f}s -> {output_path}")
    if usage is not None:
        print(f"[{label}] total_tokens={getattr(usage, 'total_tokens', 0)}")
    return output_path


NAME = "MRS. JOHNSON"
DERIVED_NOTE = "Instead of Principal please add Director"

CASES = {
    # One entry per prompt. The label is also the output folder name.
    "fields_replace": build_custom_product_replace_prompt({"name": NAME, "number": "01"}),
    # The Follow tier is most visible here: the new word is much longer than "KINDER GARTEN",
    # so the doodles around it have to make room and the per-letter colour run has to continue.
    # Check that the doodles moved a little rather than being redrawn or dropped.
    "fields_replace_longer": build_custom_product_replace_prompt({"grade_level": "FOURTH GRADE"}),
    # A colourway change has to reach the stripes, trim, collar and the fills of the motifs --
    # recolouring only the body leaves a shirt whose doodles are the wrong palette.
    "fields_replace_colour": build_custom_product_replace_prompt({"color": "teal and lime"}),
    # The hardest of the five: the fabric under the number has to be rebuilt. Check the result
    # for a ghost of the old digits, a blurred patch, or stripes that lost their rhythm.
    "fields_remove": build_custom_product_remove_prompt(["number"]),
    "fields_replace_remove": build_custom_product_replace_and_remove_prompt(
        {"name": NAME}, ["number"]
    ),
    # What a customer actually types.
    "note": build_custom_product_note_prompt(
        "Can you put MRS. JOHNSON on the back please, and take the number off? "
        "Keep everything else the same."
    ),
    "note_reference": build_custom_product_note_with_reference_prompt(
        "Put the logo from the picture I attached on the front, where the apple is."
    ),
    # A real customer note that failed in production: the back word changed but the front
    # monogram taken from it did not. ChatGPT, given the same photo and the same sentence,
    # changed both. Check that the front "P" now reads "D" as well.
    "note_derived": build_custom_product_note_prompt(DERIVED_NOTE),
    # The control. This is roughly all ChatGPT was given, and it got the case right, while the
    # prompt above -- around 3000 characters, most of them prohibitions -- got it wrong. If the
    # control keeps winning, the scaffolding is costing more than it buys and the preservation
    # rules need cutting back rather than extending.
    "note_minimal": f"""Edit the provided product photo. Keep the same garment, the same views, the same camera angle and the same background.

{DERIVED_NOTE}""",
}


if __name__ == "__main__":
    template = Path("assets/samples/mascot.png")
    reference = Path("assets/samples/mascot.png")

    if DUMP_ONLY:
        for label, prompt in CASES.items():
            print("=" * 100)
            print(label)
            print("=" * 100)
            print(prompt)
            print()
        raise SystemExit(0)

    for label, prompt in CASES.items():
        customize(
            label,
            template,
            prompt,
            reference_path=reference if label == "note_reference" else None,
        )
