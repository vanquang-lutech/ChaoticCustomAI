import base64
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY before running this script.")

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

client = OpenAI()

run_id = time.strftime("%Y%m%d_%H%M%S")
asset_dir = (
    Path("storage")
    / time.strftime("%Y_%m")
    / time.strftime("%Y_%m_%d")
    / "upload"
    / run_id
    / "output"
)
asset_dir.mkdir(parents=True, exist_ok=True)


def build_remove_background_prompt() -> str:
    return """
    Remove ONLY the background from the provided image.

    Strict preservation requirements:
    - Preserve the foreground subject exactly as it appears in the original image.
    - Do not redesign, regenerate, redraw, retouch, enhance, beautify, or reinterpret the subject.
    - Do not change the subject's shape, proportions, position, pose, composition, colors, brightness, contrast, saturation, texture, patterns, or materials.
    - Preserve all original text, letters, logos, symbols, graphics, and fine details exactly as they appear.
    - Preserve all small and delicate details.
    - Preserve fine edges such as hair, fur, feathers, fabric fibers, thin lines, and small protrusions.
    - Preserve natural semi-transparent and translucent regions such as glass, smoke, sheer fabric, soft hair edges, reflections, and transparent materials.
    - Do not remove any part of the foreground subject.
    - Do not add any new elements.
    - Do not add shadows, outlines, borders, glow, or artificial edge effects.

    Background removal:
    - Remove only pixels belonging to the background.
    - Replace the entire background with true transparency.
    - Produce a clean and accurate alpha matte around the original foreground.
    - Avoid white halos, dark halos, jagged edges, color bleeding, or background remnants.

    Output:
    - Return the foreground subject isolated on a fully transparent alpha background.
    - Output as a transparent PNG.
    """.strip()


def remove_background(
    input_path: Path,
    output_path: Path,
) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    start_time = time.time()

    with input_path.open("rb") as image_file:
        result = client.images.edit(
            model=IMAGE_MODEL,
            image=image_file,
            prompt=build_remove_background_prompt(),
            background="transparent",
            size="auto",
            quality="medium",
            output_format="png",
        )

    if not result.data or not result.data[0].b64_json:
        raise RuntimeError("OpenAI did not return image data.")

    image_bytes = base64.b64decode(result.data[0].b64_json)
    output_path.write_bytes(image_bytes)

    # Verify PNG contains an alpha channel
    with Image.open(output_path) as image:
        if image.mode not in ("RGBA", "LA"):
            raise RuntimeError(
                f"Output image does not contain an alpha channel. Image mode: {image.mode}"
            )

        print(f"Output size: {image.size}")
        print(f"Output mode: {image.mode}")

    elapsed = time.time() - start_time

    print(f"Remove background time: {elapsed:.2f} seconds")
    print(f"Saved to: {output_path}")

    return output_path


if __name__ == "__main__":
    input_path = Path("assets/samples/mascot.png")

    output_path = asset_dir / "result.png"

    remove_background(
        input_path=input_path,
        output_path=output_path,
    )
