"""The service prompts must not drift from the versions validated in ``scripts/``.

The scripts are what was actually tried against the real API, so they are the reference. They
are read as source and the prompt function is extracted from the text -- importing them would
construct an OpenAI client and demand a key.
"""

import pathlib

from src.prompts.custom_text import build_custom_text_prompt
from src.prompts.generate_image import build_generate_image_prompt
from src.prompts.remove_background import build_remove_background_prompt


def _prompt_function_from_script(path: str, name: str):
    source = pathlib.Path(path).read_text(encoding="utf-8")
    start = source.index("def " + name)
    body = source[start:]
    body = body[: body.index(".strip()") + len(".strip()")]
    namespace: dict = {}
    exec(body, namespace)  # noqa: S102 - reading our own repo, not user input
    return namespace[name]


def test_generate_prompt_matches_the_validated_script():
    reference = _prompt_function_from_script(
        "scripts/generate_transparent_image.py", "build_transparent_prompt"
    )
    assert reference("a small cute cat") == build_generate_image_prompt("a small cute cat")


def test_remove_background_prompt_matches_the_validated_script():
    reference = _prompt_function_from_script(
        "scripts/remove_background.py", "build_remove_background_prompt"
    )
    assert reference() == build_remove_background_prompt()


def test_custom_text_prompt_carries_the_text_and_the_style():
    prompt = build_custom_text_prompt("HELLO WORLD", "y2k-neon")
    assert '"HELLO WORLD"' in prompt
    assert '"y2k-neon"' in prompt
    # The reference image supplies the style only; its own words must not be copied.
    assert "Do NOT copy the words that appear in the reference image" in prompt
    assert "fully transparent alpha background" in prompt
