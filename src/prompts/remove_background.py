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
