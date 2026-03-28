## Plan: Docker packaging + dedup workflow integration

Add a `Dockerfile` bundling all dependencies and pre-compiling `pgf2ppm`, a `run.sh` wrapper with clean subcommands, a `.dockerignore`, and update the README to make Docker the primary path and document the full export→dedup workflow.

---

## Steps

### Phase 1 — Docker infrastructure

1. Create `.dockerignore`:
   - Excludes `exported_faces/`, `*.db`, `*.db-wal`, `*.db-shm`, `pgf2ppm` (compiled binary), `.git/`
   - Prevents large or sensitive files from being accidentally copied into the build context

2. Create `Dockerfile`:
   - Base: `debian:bookworm-slim`
   - Installs: `g++`, `libpgf-dev`, `python3-pil`, `findimagedupes`
   - Copies `export.py`, `dedup.py`, `pgf2ppm.cpp` into `/app`
   - Pre-compiles `pgf2ppm` at build time (`g++ -O2 -I/usr/include/libpgf -o /app/pgf2ppm /app/pgf2ppm.cpp -lpgf`) so the auto-compile fallback in `export.py` is never triggered inside the container
   - No fixed `ENTRYPOINT` — each `docker run` in `run.sh` specifies its own command

3. Create `run.sh` (`#!/usr/bin/env bash`) — executable wrapper with subcommands:
   | Command | What it does |
   |---|---|
   | `./run.sh build` | `docker build -t digikam-face-export .` |
   | `./run.sh list` | Lists all persons (mounts `$DIGIKAM_DB_DIR` read-only) |
   | `./run.sh export "Name"` | Exports faces for one person (mounts DB read-only + `./exported_faces`) |
   | `./run.sh dedup [--dry-run] [--keep first\|last]` | Runs `findimagedupes \| dedup.py` on `./exported_faces` |
   | `./run.sh all "Name"` | export + dedup in a single container call (scoped to that person's output) |
   | `./run.sh help` | Prints usage |

   - All `docker run` calls use `--user "$(id -u):$(id -g)"` so output files are owned by the host user, not root
   - `$DIGIKAM_DB_DIR` env var controls DB path; script detects platform:
     - Linux default: `~/.local/share/digikam`
     - macOS default: `~/Library/Containers/org.kde.digikam/Data/share/digikam` (with a note that the path varies)
   - DB is always mounted **read-only** (`-v ...:ro`) for all subcommands including `all`
   - `run.sh` pre-creates `./exported_faces` on the host before mounting to avoid Docker creating it as root

4. `dedup` scoping for `all` command:
   - Export writes files as `{PersonName}_{image_id}.png`
   - The `all` command passes a name-prefixed glob to findimagedupes (e.g., `exported_faces/JohnDoe_*.png`) so dedup only compares faces for that one person — prevents cross-person false-positive deduplication

### Phase 2 — README update

5. Restructure `README.md`:
   - Update "How it works" to include step 5: dedup via `findimagedupes` + `dedup.py`
   - Make **Docker quick start** the primary section:
     1. Install Docker
     2. Clone repo
     3. `./run.sh build`
     4. `./run.sh list`
     5. `./run.sh export "John Doe"`
     6. `./run.sh dedup --dry-run` (review first), then `./run.sh dedup`
     - Or: `./run.sh all "John Doe"` to do export + dedup in one step
   - Add a macOS DB path note in the Docker quick start
   - Rename existing quick start → **Native install (Linux)** as a secondary section, add dedup steps there too
   - Add a **Removing duplicates** section:
     - Explain that `findimagedupes` uses perceptual hashing — ordering is arbitrary, not quality-based
     - Strongly recommend `--dry-run` before live deletion
     - Document `--keep first|last` flags
     - Warn: when running `dedup` standalone over a multi-person output directory, it operates across all exported faces — use `all` or scope manually to avoid cross-person matches
   - Add Docker-specific entries to the troubleshooting table:
     - `Permission denied on exported_faces/` → missing `--user` flag or directory owned by root; re-run `run.sh build` and use `run.sh` wrapper
     - Wrong DB path → set `DIGIKAM_DB_DIR` explicitly
     - macOS path differs → see macOS note in quick start

---

## Relevant files

- `export.py` — read-only reference; `build_pgf2ppm()` must find pre-built binary at `/app/pgf2ppm`; output filenames are `{PersonName}_{image_id}.png` (used for per-person dedup glob)
- `dedup.py` — read-only reference for documenting its flags
- `README.md` — restructure significantly
- `Dockerfile` — new file
- `run.sh` — new file (`#!/usr/bin/env bash`; note for zsh/dash users to invoke as `bash run.sh` if needed)
- `.dockerignore` — new file

---

## Decisions

- Dockerfile only, no Docker Hub publishing
- Both separate (`dedup`) and combined (`all`) commands available
- DB path via `$DIGIKAM_DB_DIR`, with platform-aware defaults (Linux, macOS, Windows/WSL, Windows/Git Bash)
- DB always mounted read-only
- Output dir always `./exported_faces` in the working directory (matches existing behavior)
- `all` command scopes dedup to the exported person's files via filename prefix glob
- Users should always `--dry-run` dedup before committing deletions

---

## Verification

1. `docker build -t digikam-face-export .` — should complete without errors and find `findimagedupes` in the image
2. `./run.sh help` — should print all subcommands with usage
3. `./run.sh list` with `$DIGIKAM_DB_DIR` pointing to a real DB — container should invoke and return person list
4. `./run.sh dedup --dry-run` — should print what would be deleted without removing anything
5. Confirm `exported_faces/` is created with correct host ownership after `export`
6. Review README Docker quick start end-to-end for a new user with no prior knowledge of digiKam internals