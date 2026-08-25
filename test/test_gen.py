import base64
from fileinput import filename
import os
from pathlib import Path
import time
from dotenv import load_dotenv

from openai import OpenAI
from PIL import Image

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY before running this notebook.")

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL")

client = OpenAI()
asset_dir = Path("images/transparent-image-assets")
asset_dir.mkdir(parents=True, exist_ok=True)

def build_transparent_prompt(user_request: str) -> str:
    return f"""
    Create a high-quality transparent PNG-style image based on the user's request.

    User request:
    "{user_request}"

    Instructions:
    - Generate the requested subject accurately and attractively.
    - Make it visually pleasing, expressive, and high resolution.
    - Use ultra-detailed rendering, clean edges, sharp clarity, and professional-quality finishing.
    - Keep the full subject completely visible and centered with generous padding.
    - Preserve important textures, proportions, and fine details.

    Output constraints:
    - The subject must be isolated on a fully transparent alpha background.
    - No background, scenery, room, outdoor elements, floor, wall, frame, rectangle, platform, cast shadow, watermark, or readable text.
    - Return only the subject as a clean transparent PNG cutout.
    """.strip()

if __name__ == "__main__":
    user_request = "Một chú mèo nhỏ dễ thương, cute."
    output_filename = f"generated_transparent_image_{time.strftime('%Y%m%d_%H%M%S')}"

    start_time = time.time()
    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=build_transparent_prompt(user_request),
        background="transparent",
        size="1024x1024",
        quality="low",
        output_format="png",
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    output_path = asset_dir / f"{output_filename}.png"
    output_path.write_bytes(image_bytes)

    end_time = time.time()
    print(f"Generation time: {end_time - start_time:.2f} seconds")
    print(f"Saved to: {output_path}")




