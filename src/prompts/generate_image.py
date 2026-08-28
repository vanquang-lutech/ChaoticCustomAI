def build_generate_image_prompt(user_request: str) -> str:
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
