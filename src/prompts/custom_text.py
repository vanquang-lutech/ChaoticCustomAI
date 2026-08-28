def build_custom_text_prompt(text: str, style_name: str) -> str:
    return f"""
    Render the given text as lettering artwork, imitating the visual style of the provided
    reference image.

    Text to render, exactly and completely:
    "{text}"

    Style requirements:
    - Follow the reference image's style named "{style_name}".
    - Copy its typography, letterforms, weight, color palette, gradients, textures, outlines,
      highlights, and finishing effects.
    - Reproduce the reference's material treatment, so the result reads as the same style
      family.
    - Do NOT copy the words that appear in the reference image. Only its style is relevant.

    Text accuracy requirements:
    - Spell the requested text exactly, with the same characters, casing, spacing and
      punctuation.
    - Render every character; do not truncate, abbreviate, translate, or invent extra words.
    - Keep the lettering fully legible and completely inside the frame with generous padding.

    Output constraints:
    - The lettering must be isolated on a fully transparent alpha background.
    - No background, scenery, panel, frame, rectangle, platform, cast shadow, or watermark.
    - Return only the lettering as a clean transparent PNG cutout.
    """.strip()
