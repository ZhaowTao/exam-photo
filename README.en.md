# exam-photo

Cross-platform registration photo prep for Chinese public exams. Reproduces the output spec of the official `PhotoProcess.exe` (Ministry of Human Resources, PRC) so you can process ID photos for civil-service exams on **macOS, Linux or Windows** — no VM, no Windows-only tool.

```bash
$ exam-photo photo.jpg -o id_photo.jpg
  1280x1707 -> 295x413
  id_photo.jpg
  9.9 KB (quality=79) OK
  validation passed
```

## Why

Chinese exam portals ship a Windows-only `PhotoProcess.exe`. Reverse-engineering it showed the whole job is:

```
read photo.ini
→ reject if width < 295
→ Haar face detection, exactly 1 face
→ check backdrop is white or blue
→ resize to 295x413
→ save a baseline JPEG around 10 KB
```

The output carries no signature or watermark — the server only checks format, dimensions, file size and backdrop colour. This project reimplements that pipeline with Pillow + numpy, in ~600 lines, on any OS.

Details: [docs/photoprocess-reverse-notes.md](docs/photoprocess-reverse-notes.md) (Chinese).

## Install

```bash
git clone https://github.com/ZhaowTao/exam-photo.git
cd exam-photo && pip install .
```

Or run from source without installing:

```bash
pip install Pillow numpy
PYTHONPATH=src python3 -m exam_photo photo.jpg
```

## Usage

```bash
exam-photo photo.jpg                      # 295x413, <=10KB
exam-photo photo.jpg -o out.jpg           # explicit output
exam-photo photo.jpg --preset cet         # 144x192
exam-photo photo.jpg --size 480x640       # custom
exam-photo photo.jpg --max-kb 20          # byte budget
exam-photo photo.jpg --bg blue            # replace backdrop
exam-photo photo.jpg --check-only         # validate only, no rewrite
exam-photo --batch ./raw --outdir ./out   # batch
exam-photo photo.jpg --json               # machine-readable
exam-photo photo.jpg --strict             # warnings fail the run
```

`--bg` is an extra beyond the official tool: it flood-fills from the four borders and only replaces the border-connected region, so hair, skin and a white shirt survive. It requires a solid-colour backdrop.

## Presets

| key | size | max size |
|---|---|---|
| `rsks` | 295×413 | 10 KB |
| `1inch` | 295×413 | 20 KB |
| `2inch` | 413×579 | 40 KB |
| `480x640` | 480×640 | 100 KB |
| `cet` | 144×192 | 200 KB |
| `small2` | 413×531 | 50 KB |

Only `rsks` is verified against the binary. **Always follow your own exam announcement** and use `--size` when it differs.

## What it validates

Format, minimum pixels (295×413), target dimensions, aspect ratio, backdrop colour (white/blue/red/unknown), file size, and JPEG segment structure (flags EXIF / ICC / progressive / restart markers, which some provincial portals reject).

## Caveat on face detection

The official tool runs OpenCV Haar. This project does **not** bundle OpenCV — it uses a cheap centre-vs-border contrast heuristic that only catches "this is a flat colour block". If the portal rejects you for "no face detected", take a new photo; don't argue with the tool.

## Requirements

Python 3.8+, Pillow>=9.0, numpy>=1.20. Tested on macOS / Linux / Windows, including non-ASCII paths. Transparent PNGs are flattened onto white first — saving RGBA directly to JPEG renders the transparent area black.

## License

MIT. Not affiliated with the Ministry of Human Resources and Social Security of the PRC.
