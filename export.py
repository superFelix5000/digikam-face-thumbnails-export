#!/usr/bin/env python3
"""
Export face thumbnails for a specific person from digiKam's SQLite databases.

digiKam stores face thumbnails in a separate thumbnails database using the PGF
(Progressive Graphics File) codec. This script extracts them, converts PGF to
PNG via a small C++ helper (pgf2ppm), and saves all face crops for the chosen
person into an output directory.
"""

import argparse
import logging
import os
import re
import sqlite3
import subprocess
import sys
from io import BytesIO

from PIL import Image

LOG = logging.getLogger("digikam-face-export")


def find_databases(search_dir):
    """Locate digikam4.db and thumbnails-digikam.db in *search_dir*."""
    dk_path = os.path.join(search_dir, "digikam4.db")
    th_path = os.path.join(search_dir, "thumbnails-digikam.db")
    missing = [p for p in (dk_path, th_path) if not os.path.isfile(p)]
    if missing:
        LOG.error("Missing database(s): %s", ", ".join(missing))
        LOG.error("Place both digikam4.db and thumbnails-digikam.db in %s", search_dir)
        sys.exit(1)
    return dk_path, th_path


def build_pgf2ppm(script_dir):
    """Compile pgf2ppm if the binary doesn't exist yet."""
    binary = os.path.join(script_dir, "pgf2ppm")
    source = os.path.join(script_dir, "pgf2ppm.cpp")
    if os.path.isfile(binary):
        return binary
    if not os.path.isfile(source):
        LOG.error("pgf2ppm.cpp not found in %s", script_dir)
        sys.exit(1)
    LOG.info("Compiling pgf2ppm …")
    result = subprocess.run(
        ["g++", "-O2", "-I/usr/include/libpgf", "-o", binary, source, "-lpgf"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        LOG.error("Compilation failed:\n%s", result.stderr)
        LOG.error("Make sure g++ and libpgf-dev are installed (apt install g++ libpgf-dev)")
        sys.exit(1)
    LOG.info("pgf2ppm compiled successfully")
    return binary


def parse_region(xml):
    """Parse ``<rect x=".." y=".." width=".." height=".."/>`` into (x, y, w, h)."""
    m = re.search(r'x="(\d+)".*?y="(\d+)".*?width="(\d+)".*?height="(\d+)"', xml)
    if not m:
        return None
    return tuple(int(m.group(i)) for i in range(1, 5))


def pgf_to_png(pgf_data, pgf2ppm_bin):
    """Convert a raw PGF blob to PNG bytes via the pgf2ppm helper + Pillow."""
    proc = subprocess.run(
        [pgf2ppm_bin], input=pgf_data, capture_output=True,
    )
    if proc.returncode != 0:
        return None
    img = Image.open(BytesIO(proc.stdout))
    # Fix orientation (PGF stores bitmaps bottom-up / mirrored)
    img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(180)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def list_persons(dk_path):
    """Print all person tags that have at least one face region."""
    dk = sqlite3.connect(dk_path)
    rows = dk.execute("""
        SELECT t.name, COUNT(*) AS cnt
        FROM Tags t
        JOIN ImageTagProperties itp ON itp.tagid = t.id
        WHERE itp.property = 'tagRegion'
        GROUP BY t.name
        ORDER BY cnt DESC
    """).fetchall()
    dk.close()
    if not rows:
        print("No face tags found in the database.")
        return
    print(f"{'Person':<40} {'Faces':>6}")
    print("-" * 48)
    for name, cnt in rows:
        print(f"{name:<40} {cnt:>6}")


def export_faces(person_name, dk_path, th_path, output_dir, pgf2ppm_bin):
    """Export all face thumbnails for *person_name*."""
    dk = sqlite3.connect(dk_path)
    th = sqlite3.connect(th_path)

    # 1. Find the tag ID
    tag_row = dk.execute(
        "SELECT id FROM Tags WHERE name = ?", (person_name,)
    ).fetchone()
    if not tag_row:
        LOG.error("Person '%s' not found in Tags table.", person_name)
        LOG.info("Use --list to see available person names.")
        dk.close(); th.close()
        sys.exit(1)
    tag_id = tag_row[0]

    # 2. Get all face regions with image file info
    regions = dk.execute("""
        SELECT itp.imageid, itp.value, ii.name, al.relativePath, ar.specificPath
        FROM ImageTagProperties itp
        JOIN Images ii ON itp.imageid = ii.id
        JOIN Albums al ON ii.album = al.id
        JOIN AlbumRoots ar ON al.albumRoot = ar.id
        WHERE itp.tagid = ? AND itp.property = 'tagRegion'
    """, (tag_id,)).fetchall()

    if not regions:
        LOG.warning("No face regions found for '%s'.", person_name)
        dk.close(); th.close()
        return

    LOG.info("Found %d face regions for '%s'", len(regions), person_name)
    os.makedirs(output_dir, exist_ok=True)

    saved = 0
    skipped = 0

    for image_id, region_xml, img_name, rel_path, spec_path in regions:
        rect = parse_region(region_xml)
        if not rect:
            LOG.debug("Skipping image %d: unparseable region '%s'", image_id, region_xml)
            skipped += 1
            continue
        x, y, w, h = rect
        target_cx, target_cy = x + w / 2, y + h / 2

        # 3. Find face thumbnail candidates in CustomIdentifiers
        candidates = th.execute("""
            SELECT ci.identifier, ci.thumbId
            FROM CustomIdentifiers ci
            WHERE ci.identifier LIKE ?
        """, (f"%{img_name}%rect=%",)).fetchall()

        if not candidates:
            LOG.debug("No thumbnail found for image %d (%s)", image_id, img_name)
            skipped += 1
            continue

        # 4. Match by closest center point
        best_id = None
        best_dist = float('inf')
        for ident, thumb_id in candidates:
            m = re.search(r'rect=(\d+),(\d+)-(\d+)x(\d+)', ident)
            if not m:
                continue
            rx, ry, rw, rh = (int(m.group(i)) for i in range(1, 5))
            cx, cy = rx + rw / 2, ry + rh / 2
            dist = ((cx - target_cx) ** 2 + (cy - target_cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_id = thumb_id

        if best_id is None or best_dist > 50:
            LOG.debug("No close match for image %d (best_dist=%.1f)", image_id, best_dist)
            skipped += 1
            continue

        # 5. Get PGF blob and convert
        blob_row = th.execute("SELECT data FROM Thumbnails WHERE id = ?", (best_id,)).fetchone()
        if not blob_row or not blob_row[0]:
            skipped += 1
            continue

        png_data = pgf_to_png(blob_row[0], pgf2ppm_bin)
        if not png_data:
            LOG.debug("PGF conversion failed for image %d", image_id)
            skipped += 1
            continue

        out_name = f"{person_name}_{image_id}.png"
        with open(os.path.join(output_dir, out_name), "wb") as f:
            f.write(png_data)
        saved += 1
        if saved % 100 == 0:
            LOG.info("  …saved %d so far", saved)

    LOG.info("Done: %d thumbnails saved, %d skipped", saved, skipped)
    dk.close()
    th.close()


def main():
    parser = argparse.ArgumentParser(
        description="Export face thumbnails from digiKam's databases.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s "John Doe"              Export faces for John Doe
  %(prog)s --list                  Show all persons with face data
  %(prog)s -v "Jane Doe"           Export with verbose logging
  %(prog)s -d /path/to/dbs "Name"  Use databases from a custom directory
""",
    )
    parser.add_argument("person", nargs="?", help="Name of the person to export (must match exactly)")
    parser.add_argument("--list", action="store_true", help="List all persons with face regions and exit")
    parser.add_argument("-d", "--db-dir", default=None,
                        help="Directory containing digikam4.db and thumbnails-digikam.db (default: script directory)")
    parser.add_argument("-o", "--output", default=None, help="Output directory (default: ./exported_faces)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = args.db_dir or script_dir
    dk_path, th_path = find_databases(db_dir)

    if args.list:
        list_persons(dk_path)
        return

    if not args.person:
        parser.error("Please provide a person name, or use --list to see available names.")

    output_dir = args.output or os.path.join(script_dir, "exported_faces")
    pgf2ppm_bin = build_pgf2ppm(script_dir)

    export_faces(args.person, dk_path, th_path, output_dir, pgf2ppm_bin)


if __name__ == "__main__":
    main()
