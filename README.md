# ChaoticCustomAI

FastAPI backend for AI image work on top of the OpenAI image models. Three features:

| Feature | Input | Output |
| --- | --- | --- |
| **Upload image** | 1–3 images, `remove_background` flag | The uploaded images, background stripped if the flag is set |
| **Generate image** | A text description | Generated PNG on a transparent background |
| **Custom text** | A text string + a style preset name | The text rendered in that style, PNG on a transparent background |

There is **no database**. Uploads, generated output, job records and usage records are all
written to disk under `storage/`, and logs under `logs/`.

## How a request flows

Image calls take 10–60s each, so anything that calls OpenAI is asynchronous:

1. `POST` to the feature endpoint → validated, input persisted, a Celery task queued.
   Responds `202` with a `job_id`.
2. The worker calls OpenAI, writes `output/result.png`, appends a token-usage record.
3. Client polls `GET /api/v1/jobs/{job_id}` until `status` is `succeeded` or `failed`.
4. On success the job carries `images: [{"url": "/api/v1/files/{job_id}/output/result.png"}]`.
   The client fetches that URL to get the PNG.

**Uploading without background removal skips all of this.** No OpenAI call is needed, so the
file is saved and the endpoint responds `200` straight away with the URL — no job, no polling.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/upload` | Upload up to 3 images, optionally remove their backgrounds |
| `POST` | `/api/v1/generate-image` | Generate a transparent image from a text prompt |
| `POST` | `/api/v1/custom-text` | Render text in one of the style presets |
| `GET` | `/api/v1/jobs/{job_id}` | Job status and, once finished, the result URL |
| `GET` | `/api/v1/files/{job_id}/{kind}/{filename}` | Serve a stored image (`kind` is `input` or `output`) |
| `GET` | `/api/v1/usage` | Token totals per model and feature, filterable by date range |

The file URL is keyed by `job_id`, not by storage path, so the directory layout stays an
internal detail and can change without breaking clients. To make that resolution free, the
job id carries its own date: `20260825T140344-a3f9c1`. The service derives `2026_08/2026_08_25`
straight from the id — no Redis lookup and no directory scan, so stored files remain
addressable even if the result backend is wiped.

Style presets for `custom-text` come from `assets/text-styles/`: `collegiate`, `comic-bold`,
`gold-foil`, `miami-script`, `pastel-candy`, `pixel-block`, `street-tag`, `y2k-neon`.

**Upload creates one job per image.** A `POST /upload` with 3 files returns 3 job entries. That
keeps each job folder matching the layout below — one `original.*`, one `result.png` — and means
one image failing does not fail the other two, with token usage attributable per image.

## Storage layout

Partitioned by month, then day, then feature, then job — each job owns a self-contained folder:

```
storage/
  2026_08/
    2026_08_25/
      upload/
        {job_id}/
          input/original.jpg     # exactly what the user sent
          output/result.png      # background-removed result
          job.json               # status, timing, model, token usage
      generate_image/
        {job_id}/
          input/request.json     # the prompt and parameters
          output/result.png
          job.json
      custom_text/
        {job_id}/
          input/request.json     # the text and the style preset name
          output/result.png
          job.json
      usage.jsonl                # one line per OpenAI call
logs/
  2026_08_25.log
```

Feature keys are `upload`, `generate_image`, `custom_text` — the same strings are used for the
folder name, the route module, the Celery task module and the API enum.

A job folder is self-describing: input, output and metadata sit together, so one directory can
be inspected, archived or deleted as a unit. Redis is only the Celery broker; job status is
served from `job.json`, so polling and history survive a Redis restart.

## Token usage tracking

There is no pricing or cost calculation. Each OpenAI call appends one line to the day's
`usage.jsonl`:

```json
{"ts": "2026-08-25T14:03:44Z", "job_id": "...", "feature": "generate_image", "model": "gpt-image-1", "input_tokens": 128, "output_tokens": 4160, "total_tokens": 4288}
```

`GET /api/v1/usage` aggregates these — totals per model, per feature, over a date range.
Append-only with one JSON object per line means concurrent workers never rewrite each other's
records.

## Requirements

- Python 3.12+
- Redis (task queue) — or just use Docker Compose
- An OpenAI API key with access to the image models

## Setup

```bash
uv sync --extra dev
```

```bash
cp .env.example .env   # then fill in OPENAI_API_KEY
```

## Running

Everything at once (API + worker + Redis):

```bash
docker compose up --build
```

On Linux or macOS, when Redis is already running, the API and worker can also be started in
separate terminals:

```bash
uvicorn src.main:app --reload
```

```bash
celery -A src.workers.worker worker --loglevel=info
```

Celery does not officially support Windows workers, so Windows development should use Docker
Compose for the worker and Redis.

API at `http://localhost:8000`, docs at `/docs`.

## Layout

```
assets/
  text-styles/    Style reference images used by the custom-text feature (app input)
  samples/        Sample images for manual testing
scripts/          One-off scripts that hit the real OpenAI API — not part of the test suite
storage/          Uploads, output, job records, token usage (gitignored)
logs/             Log files (gitignored)
tests/            Automated tests; must not call the OpenAI API
src/
  main.py         FastAPI application entrypoint
  api/v1/         HTTP routes, one module per resource, wired up in router.py
  core/           Settings, logging, constants, enums, exceptions, shared dependencies
  schemas/        Pydantic request/response models
  services/       Business logic — the only layer the routes talk to
  providers/      Third-party clients (OpenAI)
  prompts/        Prompt builders, kept out of the service logic
  taskqueue/      Celery app and configuration
  workers/        Worker entrypoint and task definitions
  utils/          Small stateless helpers (files, hashing, ids, image ops)
```

`src` is imported from the project root (`src.main:app`); it is not an installable package.

## Development

```bash
ruff check . && ruff format .
```

```bash
pytest
```

Anything that calls the OpenAI API for real belongs in `scripts/`, not `tests/` — the test
suite must stay free of network calls and API spend.
