#!/usr/bin/env bash
# Build from the pinned lockfile; install no packages and request no root access.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
cargo build --release --locked --manifest-path "$repo_dir/tools/workstation-files/Cargo.toml"
install -d -m 755 "$HOME/.local/lib/workstation-tools"
install -m 755 "$repo_dir/tools/workstation-files/target/release/workstation-files" "$HOME/.local/lib/workstation-tools/workstation-files.new"
mv -f -- "$HOME/.local/lib/workstation-tools/workstation-files.new" "$HOME/.local/lib/workstation-tools/workstation-files"
