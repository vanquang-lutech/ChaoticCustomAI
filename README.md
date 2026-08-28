# ChaoticCustomAI

FastAPI backend for AI image work on top of the OpenAI image models. Four features:

| Feature | Input | Output |
| --- | --- | --- |
| **Upload image** | 1–3 images, `remove_background` flag | The uploaded images, background stripped if the flag is set |
| **Generate image** | A text description | Generated PNG on a transparent background |
| **Custom text** | A text string + a style preset name | The text rendered in that style, PNG on a transparent background |
| **Custom product** | A product mock-up + how the customer wants it changed | The same mock-up, edited |

A `custom-product` job in `note` mode makes two OpenAI calls: a cheap text call that reads the
customer's note, then the image call. Everything else makes one.

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
| `POST` | `/api/v1/custom-product` | Edit an uploaded product mock-up to a customer's spec |
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

## Custom product

The storefront shows a mock-up of the garment and lets a customer say how they want it changed.
They get one of two ways to say it, never both, and `mode` records which they used:

| `mode` | What the customer did | What the request carries |
| --- | --- | --- |
| `fields` | Filled in the inputs beside the product | `fields`, `remove_fields` |
| `note` | Typed into the order note | `note`, optionally with an attached image |

The mock-up is uploaded with the request rather than looked up server-side, so a job folder
holds everything the edit was made from. `multipart/form-data`, because of the upload: `fields`
arrives as a JSON object string since multipart has no nested objects, and `remove_fields` as a
repeated form field (a JSON array is accepted there too).

**A field has three states, not two.** The number input on the storefront has an on/off toggle,
and switching it off is an instruction — the number printed on the mock-up has to come off the
garment:

| State | How it is sent | What happens |
| --- | --- | --- |
| Has a value | in `fields` | written onto the garment |
| Switched off | in `remove_fields` | erased from the garment, fabric underneath rebuilt |
| Not offered by this product | in neither | left untouched |

A blank value in `fields` is not a removal; it is dropped. Asking to both set and remove the
same field is rejected rather than guessed at. `remove_fields` on its own is a valid request —
"take the number off and change nothing else".

Two parameters are pinned for this feature and matter more than they look:

- `size=auto` — a mock-up showing a front and a back view is far wider than a single-view one, so
  a fixed size would squash it or crop a view away.
- `background=auto` — the other features return cutouts and want transparency. Here the product
  photo's own background is part of what must survive the edit.

`product_id` is recorded with the job but not yet checked against a catalogue: which products
may be customised, and which fields each one offers, is the storefront's answer to give once
that API exists. `CustomProductService._check_product` is where that check goes.

The image upload belongs to the order note, which is where the storefront offers it, so
attaching one in `fields` mode is refused rather than stored and ignored.

### Reading the order note first

An order note is a prompt written by a member of the public, so a `note` job makes a text call
before it makes an image call. `NoteNormalizer` asks a text model to read the note and report
what it asks for:

```json
{
  "feasible": true,
  "replace": {"name": "MRS. JOHNSON"},
  "remove": ["number"],
  "instructions": "Put MRS. JOHNSON on the back and take the number off.",
  "fully_structured": true,
  "rejected_reason": null
}
```

A text call on a 1000-character note costs a fraction of one image call, which is what pays for
three things:

- **A hopeless request costs no image call.** "Make me a coffee mug instead" comes back
  `feasible: false` in about a second, and the job fails with a sentence a shop assistant could
  read out, rather than after 30–60s and a wrong garment.
- **An understood note is prompted like a storefront field.** When `replace` and `remove` cover
  the whole request, the job uses the `fields_*` prompts — they name the element and its rules
  exactly, where the note prompts can only give general guidance. Anything left over in prose,
  or a reference image, keeps the note prompt.
- **The words that reach the image prompt have been read.** The customer's own text goes to the
  text model as its own message, never inside the instruction message, and fenced there too.

The step is **best-effort**. If the text call fails or comes back describing nothing, the note is
used exactly as the customer wrote it and the job carries on — an order is not worth losing to a
hiccup in an optimisation. `NORMALIZE_ORDER_NOTES=false` turns the step off entirely, which is
how the two paths stay comparable on real orders.

Both calls are recorded in `usage.jsonl` under their own model, so `GET /usage` shows the text
model and the image model as separate buckets. The job keeps `note` (as typed),
`note_normalized` (what the image model was actually asked) and `note_source` (`normalized`,
`raw`, or `raw-fallback`).

Output from the text model is not taken at its word: element names outside the vocabulary the
image prompts know are dropped, and `fully_structured` is downgraded if nothing survived —
otherwise a made-up element name would route the request to a prompt with nothing to say.

### The five prompts

`src/prompts/custom_product.py` holds one self-contained prompt per case, so each is worded for
its own job — the erase-only prompt leads with erasing rather than carrying replacement rules it
will never use:

| Case | When |
| --- | --- |
| `fields_replace` | values to write, nothing to erase |
| `fields_remove` | elements to erase, no values to write |
| `fields_replace_remove` | both at once |
| `note` | the customer described it themselves |
| `note_reference` | same, with an image they attached |

`customization_case()` picks the case and `GptImageService._product_prompt` calls that case's
builder. Each job records which one ran in `meta.prompt_case`, so a bad result can be traced to
its wording without rebuilding the request by hand.

The cost of independent prompts is that the shared rules appear in all five: a change to how the
garment must be treated has to be made five times. `tests/test_custom_product_api.py` asserts the
rules that all five must carry against all five, which is what catches a prompt left behind.
`python scripts/custom_product.py --dump` prints all five in full without spending anything on
the API.

### Three tiers, not two

A mock-up is a design, not a pile of independent stickers. Changing one thing on it means other
details stop making sense unless they change too: `KINDER GARTEN` becoming `FOURTH GRADE` is a
wider word, so the apple and crayons beside it have to make room and the per-letter colour run
has to continue over a different number of letters. A new colourway reaches the stripes, the
trim, the collar and the fills of the doodles, not just the body of the shirt.

So every prompt sorts the garment into three tiers rather than two:

| Tier | What it covers |
| --- | --- |
| **Change** | what the customer asked for |
| **Follow** | the details that depend on it, adjusted only as far as the change requires: room for lettering that changed length, a colourway carried through the motifs drawing from it, a per-letter colour sequence continued, every copy of a repeated value, and anything **derived** from what changed |
| **Preserve** | everything independent, plus a hard bound |

The Follow tier is the one loosening in an otherwise tightening set of rules, so the bound on it
is explicit and checked against all five prompts: motifs keep their identity and their number
(an apple stays that apple, it does not become a football), the composition is not rearranged,
whatever moves moves locally, and the result must read as the same product rather than a new
design in the same style.

The derived case is a dependency of **meaning** rather than of layout, and it is the one a rule
about preserving decoration silently forbids. A jersey reading `PRINCIPAL` on the back with a
large `P` on the front: change the word to `DIRECTOR` and the `P` has to become `D`. Nothing in
the layout rules reaches that, and `Keep every decorative motif as the thing it is` actively
blocks it, because a monogram looks exactly like decoration. So the motif bound excludes
lettering, digits, initials and monograms derived from what changed. Erasing works the same way:
what stands for the erased element goes with it.

**Erasing sits outside the Follow tier on purpose.** Switching an element off is not a change the
rest of the design adapts to — the space it occupied stays empty, and nothing shifts to close the
gap. Without that carve-out the Follow tier reads as permission to rebalance around the hole.

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
      custom_product/
        {job_id}/
          input/template.jpg     # the product mock-up the customer was looking at
          input/reference.png    # optional image they attached to their note
          input/request.json     # the mode and what they asked for
          output/result.png
          job.json
      usage.jsonl                # one line per OpenAI call
logs/
  2026_08_25.log
```

Feature keys are `upload`, `generate_image`, `custom_text`, `custom_product` — the same strings
are used for the folder name, the route module, the Celery task module and the API enum.

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
  providers/      Third-party clients (OpenAI images, OpenAI text)
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
