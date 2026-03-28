#!/usr/bin/env bash
set -euo pipefail

IMAGE="digikam-face-export"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/exported_faces"

# ---------------------------------------------------------------------------
# Detect default DIGIKAM_DB_DIR per platform
# ---------------------------------------------------------------------------
detect_db_dir() {
    if [[ -n "${DIGIKAM_DB_DIR:-}" ]]; then
        echo "$DIGIKAM_DB_DIR"
        return
    fi

    local os
    os="$(uname -s)"

    if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
        # Windows / WSL — databases live on the Windows side
        local winuser
        winuser="$(powershell.exe -NoProfile -Command '[Environment]::UserName' 2>/dev/null | tr -d '\r')" || winuser=""
        if [[ -n "$winuser" ]]; then
            echo "/mnt/c/Users/$winuser/AppData/Roaming/digikam"
            return
        fi
    fi

    case "$os" in
        Linux)   echo "$HOME/.local/share/digikam" ;;
        Darwin)  echo "$HOME/Library/Containers/org.kde.digikam/Data/share/digikam" ;;
        MINGW*|MSYS*)
            # Git Bash on Windows
            echo "${APPDATA:-$HOME/AppData/Roaming}/digikam" ;;
        *)       echo "$HOME/.local/share/digikam" ;;
    esac
}

DB_DIR="$(detect_db_dir)"

# ---------------------------------------------------------------------------
# Common docker-run flags
# ---------------------------------------------------------------------------
run_docker() {
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        "$@"
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
cmd_build() {
    docker build -t "$IMAGE" "$SCRIPT_DIR"
}

cmd_list() {
    run_docker \
        -v "$DB_DIR:/db:ro" \
        "$IMAGE" \
        python3 /app/export.py -d /db --list
}

cmd_export() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 export \"Person Name\" [extra export.py flags...]" >&2
        exit 1
    fi
    mkdir -p "$OUTPUT_DIR"
    run_docker \
        -v "$DB_DIR:/db:ro" \
        -v "$OUTPUT_DIR:/output" \
        "$IMAGE" \
        python3 /app/export.py -d /db -o /output "$@"
}

cmd_dedup() {
    if [[ ! -d "$OUTPUT_DIR" ]]; then
        echo "No exported_faces/ directory found. Run 'export' first." >&2
        exit 1
    fi
    run_docker \
        -v "$OUTPUT_DIR:/output" \
        "$IMAGE" \
        bash -c 'findimagedupes /output/*.png | python3 /app/dedup.py "$@"' _ "$@"
}

cmd_all() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 all \"Person Name\"" >&2
        exit 1
    fi
    local person="$1"
    shift
    mkdir -p "$OUTPUT_DIR"

    # Sanitise person name to match the filename prefix export.py produces
    local prefix
    prefix="$(echo "$person" | tr ' ' '_')"

    run_docker \
        -v "$DB_DIR:/db:ro" \
        -v "$OUTPUT_DIR:/output" \
        "$IMAGE" \
        bash -c '
            set -e
            python3 /app/export.py -d /db -o /output "$1"
            findimagedupes /output/"$2"_*.png 2>/dev/null \
                | python3 /app/dedup.py
        ' _ "$person" "$prefix"
}

cmd_help() {
    cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  build                         Build the Docker image
  list                          List all persons with face data
  export "Person Name" [flags]  Export face thumbnails for a person
  dedup  [--dry-run] [--keep first|last]
                                Find and remove duplicate exported faces
  all    "Person Name"          Export faces then deduplicate (scoped to that person)
  help                          Show this help message

Environment:
  DIGIKAM_DB_DIR   Path to the directory containing digikam4.db and
                   thumbnails-digikam.db.
                   Detected default: $DB_DIR
EOF
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
case "${1:-help}" in
    build)  shift; cmd_build "$@" ;;
    list)   shift; cmd_list "$@" ;;
    export) shift; cmd_export "$@" ;;
    dedup)  shift; cmd_dedup "$@" ;;
    all)    shift; cmd_all "$@" ;;
    help|--help|-h) cmd_help ;;
    *)
        echo "Unknown command: $1" >&2
        cmd_help >&2
        exit 1
        ;;
esac
