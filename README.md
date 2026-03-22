# digikam-face-export

Export face thumbnails for a specific person from [digiKam](https://www.digikam.org/)'s SQLite databases as PNG files.

digiKam stores its face recognition crops in a separate thumbnails database using the **PGF** (Progressive Graphics File) wavelet codec. This tool extracts them, decodes the PGF data via a small C++ helper, and saves every face crop for a chosen person as a standard PNG.

## How it works

1. The script queries `digikam4.db` for all face regions tagged with the given person name.
2. For each region it finds the matching face thumbnail in `thumbnails-digikam.db` (stored as a `detail://` URI in the `CustomIdentifiers` table).
3. The raw PGF blob is piped through `pgf2ppm` (a tiny C++ program linked against `libpgf`) to produce a PPM image.
4. Pillow reads the PPM, fixes the orientation, and saves it as PNG.

## Requirements

- **Linux** (tested on Ubuntu/Debian)
- **Python 3** with **Pillow** (`apt install python3-pil` or `pip install Pillow`)
- **g++** (`apt install g++`)
- **libpgf-dev** (`apt install libpgf-dev`)
- **digiKam databases**: `digikam4.db` and `thumbnails-digikam.db`

## Quick start

### 1. Install dependencies

```bash
sudo apt install g++ libpgf-dev python3-pil
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

This prints every person tag that has at least one face region, along with the count.

### 5. Export faces

```bash
python3 export.py "John Doe"
```

PNGs will be written to `./exported_faces/`. The `pgf2ppm` helper is compiled automatically on first run.

### Options

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

## Building pgf2ppm manually

The script auto-compiles `pgf2ppm` on first run, but you can also build it yourself:

```bash
g++ -O2 -I/usr/include/libpgf -o pgf2ppm pgf2ppm.cpp -lpgf
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Person 'X' not found in Tags table` | Use `--list` to check the exact spelling. Names are case-sensitive. |
| `Missing database(s)` | Copy both `digikam4.db` and `thumbnails-digikam.db` into the script directory or pass `-d`. |
| `Compilation failed` | Install build dependencies: `sudo apt install g++ libpgf-dev` |
| Many faces skipped | Some images may not have cached thumbnails in the database. This is normal. Use `-v` for details. |

## License

MIT
