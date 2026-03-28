# digikam-face-thumbnails-export

Export face thumbnails for a specific person from [digiKam](https://www.digikam.org/)'s SQLite databases as PNG files.

digiKam stores its face recognition crops in a separate thumbnails database using the **PGF** (Progressive Graphics File) wavelet codec. This tool extracts them, decodes the PGF data via a small C++ helper, and saves every face crop for a chosen person as a standard PNG.

## How it works

1. The script queries `digikam4.db` for all face regions tagged with the given person name.
2. For each region it finds the matching face thumbnail in `thumbnails-digikam.db` (stored as a `detail://` URI in the `CustomIdentifiers` table).
3. The raw PGF blob is piped through `pgf2ppm` (a tiny C++ program linked against `libpgf`) to produce a PPM image.
4. Pillow reads the PPM, fixes the orientation, and saves it as PNG.
5. Optionally, [`findimagedupes`](https://gitlab.com/opennota/findimagedupes) detects perceptually similar exports and `dedup.py` removes the duplicates.

---

## Quick start (Docker — recommended)

A Docker image bundles **all** dependencies (`g++`, `libpgf`, Pillow, `findimagedupes`) so nothing needs to be installed on the host except Docker itself.

### 1. Install Docker

Follow the [official instructions](https://docs.docker.com/get-docker/) for your platform.

### 2. Clone this repo

```bash
git clone https://github.com/felixwestphal/digikam-face-export.git
cd digikam-face-export
```

### 3. Build the image

```bash
./run.sh build
```

### 4. List available persons

```bash
./run.sh list
```

The script looks for your digiKam databases automatically. The default location depends on your OS:

| OS | Default `DIGIKAM_DB_DIR` |
|----|--------------------------|
| Linux | `~/.local/share/digikam` |
| macOS | `~/Library/Containers/org.kde.digikam/Data/share/digikam` |
| Windows (WSL) | `/mnt/c/Users/<you>/AppData/Roaming/digikam` |
| Windows (Git Bash) | `$APPDATA/digikam` |

If your databases are elsewhere, set the environment variable:

```bash
export DIGIKAM_DB_DIR=/path/to/your/digikam/databases
```

### 5. Export faces

```bash
./run.sh export "John Doe"
```

PNGs are written to `./exported_faces/John_Doe/`.

### 6. Remove duplicates

Always preview first with `--dry-run`:

```bash
./run.sh dedup "John Doe" --dry-run
```

Then delete the duplicates:

```bash
./run.sh dedup "John Doe"
```

Or do export + dedup in one step (dedup is automatically scoped to the exported person):

```bash
./run.sh all "John Doe"
```

### run.sh reference

| Command | Description |
|---------|-------------|
| `./run.sh build` | Build the Docker image |
| `./run.sh list` | List all persons with face data |
| `./run.sh export "Name" [flags]` | Export face thumbnails for a person |
| `./run.sh dedup "Name" [--dry-run] [--keep first\|last]` | Find and remove duplicate exported faces |
| `./run.sh all "Name"` | Export + deduplicate in one step |
| `./run.sh help` | Show usage and detected DB path |

> **Note:** `run.sh` requires bash. On Windows use WSL (`wsl ./run.sh …`) or Git Bash. Native CMD / PowerShell is not supported.

---

## Native install (Linux)

If you prefer to run without Docker, install the dependencies directly.

### Requirements

- **Linux** (tested on Ubuntu/Debian)
- **Python 3** with **Pillow** (`apt install python3-pil` or `pip install Pillow`)
- **g++** (`apt install g++`)
- **libpgf-dev** (`apt install libpgf-dev`)
- **findimagedupes** (`apt install findimagedupes`) — only needed for dedup
- **digiKam databases**: `digikam4.db` and `thumbnails-digikam.db`

### 1. Install dependencies

```bash
sudo apt install g++ libpgf-dev python3-pil findimagedupes
```

### 2. Clone this repo

```bash
git clone https://github.com/felixwestphal/digikam-face-export.git
cd digikam-face-export
```

### 3. Copy your digiKam databases

Copy (or symlink) the two database files into the repo directory:

```bash
cp ~/.local/share/digikam/digikam4.db .
cp ~/.local/share/digikam/thumbnails-digikam.db .
```

> **Tip:** The default location on Linux is `~/.local/share/digikam/`. Your path may differ depending on your digiKam configuration.

### 4. List available persons

```bash
python3 export.py --list
```

### 5. Export faces

```bash
python3 export.py "John Doe"
```

PNGs will be written to `./exported_faces/John_Doe/`. The `pgf2ppm` helper is compiled automatically on first run.

### 6. Remove duplicates

```bash
# Preview what would be deleted
findimagedupes "exported_faces/John_Doe/*.png" | python3 dedup.py --dry-run

# Actually delete duplicates
findimagedupes "exported_faces/John_Doe/*.png" | python3 dedup.py
```

### export.py options

| Flag | Description |
|------|-------------|
| `--list` | List all persons with face data and exit |
| `-d DIR` | Directory containing the two `.db` files (default: script directory) |
| `-o DIR` | Output directory (default: `./exported_faces`) |
| `-v` | Verbose / debug logging |

### Examples

```bash
# Export with databases in a different folder
python3 export.py -d /media/backup/digikam "Jane Doe"

# Export to a custom output directory with verbose logging
python3 export.py -v -o ~/faces "Jane Doe"
```

---

## Removing duplicates

digiKam may store multiple similar thumbnails for the same face. `findimagedupes` uses perceptual hashing to detect visually similar images, and `dedup.py` deletes the extras.

**Important:** The ordering of duplicates reported by `findimagedupes` is arbitrary — it does **not** pick a "best quality" image. Always preview with `--dry-run` first.

### dedup.py options

| Flag | Description |
|------|-------------|
| `--dry-run`, `-n` | Show what would be deleted without removing anything |
| `--keep first\|last` | Which file in each duplicate group to keep (default: `first`) |

### Multi-person output directories

When you export several people into the same `exported_faces/` folder, running `dedup` over the entire directory may match faces of **different** people that happen to look similar. To avoid this:

- Use `./run.sh all "Name"` which automatically scopes dedup to that person's files.
- Or run `findimagedupes` manually with a name-prefixed glob:
  ```bash
  findimagedupes "exported_faces/John_Doe/*.png" | python3 dedup.py
  ```

---

## Building pgf2ppm manually

The script auto-compiles `pgf2ppm` on first run, but you can also build it yourself:

```bash
g++ -O2 -I/usr/include/libpgf -o pgf2ppm pgf2ppm.cpp -lpgf
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Person 'X' not found in Tags table` | Use `--list` to check the exact spelling. Names are case-sensitive. |
| `Missing database(s)` | Copy both `digikam4.db` and `thumbnails-digikam.db` into the script directory or pass `-d`. Set `DIGIKAM_DB_DIR` when using Docker. |
| `Compilation failed` | Install build dependencies: `sudo apt install g++ libpgf-dev`. Not needed when using Docker. |
| Many faces skipped | Some images may not have cached thumbnails in the database. This is normal. Use `-v` for details. |
| `Permission denied` on `exported_faces/` | The directory was created by Docker as root. Delete it (`sudo rm -rf exported_faces`) and re-run via `run.sh` which creates it with correct ownership. |
| Wrong DB path in Docker | Set `export DIGIKAM_DB_DIR=/your/path` before running `run.sh`. Use `./run.sh help` to see the currently detected default. |
| macOS DB not found | digiKam on macOS may use a different path. Check your digiKam settings and set `DIGIKAM_DB_DIR` explicitly. |

## License

MIT
