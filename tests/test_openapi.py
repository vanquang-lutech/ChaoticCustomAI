"""The generated schema has to describe uploads in a way Swagger UI can render."""


def test_upload_files_are_declared_as_binary(client):
    """Both spellings must be present.

    ``contentMediaType`` is the OpenAPI 3.1 form FastAPI emits; ``format: binary`` is what
    Swagger UI reads to draw a file picker instead of a text box.
    """
    schema = client.get("/openapi.json").json()
    body = schema["components"]["schemas"]["Body_upload_images_api_v1_upload_post"]
    files = body["properties"]["files"]

    assert files["type"] == "array"
    assert files["items"]["contentMediaType"] == "application/octet-stream"
    assert files["items"]["format"] == "binary"
    assert body["required"] == ["files"]
    assert body["properties"]["remove_background"]["default"] is False


def test_the_docs_page_is_served(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
