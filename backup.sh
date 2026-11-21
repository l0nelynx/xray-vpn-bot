#!/usr/bin/env bash
set -euo pipefail
umask 077

fail() { printf '%s\n' "$*" >&2; exit 1; }
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
backups=/var/backups/xray

printf '%s\n' '1) Create a backup' '2) Restore from a backup' '0) Exit'
while true; do
    read -r -p 'Choose an action [1/2/0]: ' choice || exit 0
    case "$choice" in
        1|2) break ;;
        0) exit 0 ;;
        *) printf '%s\n' 'Enter 1, 2, or 0.' ;;
    esac
done

[[ $(uname -s) == Linux ]] || fail 'Run this launcher on the Linux Docker Compose host.'
[[ $(id -u) == 0 ]] || fail 'File ownership requires root. Run sudo bash backup.sh.'
docker compose version >/dev/null
engine="$base/scripts/deployment_backup.py"
if [[ $choice == 1 ]]; then
    [[ -f $engine ]] || fail 'Run the copy of backup.sh in the project containing scripts/deployment_backup.py.'
    default="$backups/xray-$(date +%Y%m%d-%H%M%S).zip"
    printf 'Project: %s\nServices will stop while the snapshot is taken.\n' "$base"
    read -r -p "Save ZIP to [$default]: " archive || exit 1
    archive=${archive:-$default}
    args=(backup "$archive" --project-dir "$base")
else
    shopt -s nullglob
    candidates=("$base"/*.zip)
    if (( ${#candidates[@]} == 0 )); then candidates=("$backups"/*.zip); fi
    default=''
    if (( ${#candidates[@]} == 1 )); then default=${candidates[0]}; fi
    read -r -p "Backup ZIP path${default:+ [$default]}: " archive || exit 1
    archive=${archive:-$default}
    [[ -f $archive ]] || fail 'Backup ZIP file not found.'
    archive=$(realpath -- "$archive")
    read -r -p 'Restore into a new directory [/opt/xray-vpn-bot]: ' target || exit 1
    target=${target:-/opt/xray-vpn-bot}
    [[ ! -e $target && ! -L $target ]] || fail "Destination already exists: $target"
    args=(restore "$archive" "$target")
fi

arch=$(uname -m)
libc=gnu
if [[ -e /lib/ld-musl-$arch.so.1 ]] && ! getconf GNU_LIBC_VERSION >/dev/null 2>&1; then
    libc=musl
fi
case "$arch-$libc" in
    x86_64-gnu)   digest=f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb ;;
    aarch64-gnu)  digest=55c00325f7c1fddf325dfc621aabdfbbac4dc54adda224af88ec411dc12db239 ;;
    x86_64-musl)  digest=a75bf409606303deed964d4769544f98b74e7b53d4efb44f4a95cb38e86ff403 ;;
    aarch64-musl) digest=5616ed1d426cb12cc135e5998b42bfd665cf2f9e3f3f9f6c77c73f0ae26f7d03 ;;
    *) fail "The portable runtime is unavailable for $arch-$libc." ;;
esac
release=20261110
asset="cpython-3.13.18+${release}-$arch-unknown-linux-${libc}-install_only_stripped.tar.gz"
cache=${XDG_CACHE_HOME:-/var/cache}/xray-deployment-backup
mkdir -p -- "$cache"
work=$(mktemp -d "$cache/run.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
runtime="$cache/$asset"
verified() {
    local actual
    [[ -f $1 ]] && actual=$(sha256sum < "$1") && [[ ${actual%% *} == "$digest" ]]
}

if [[ $choice == 2 ]]; then
    # The embedded engine understands the archive version, including older backups.
    engine="$work/deployment_backup.py"
    unzip -p "$archive" deployment_backup.py > "$engine"
fi
if ! verified "$runtime"; then
    if [[ $choice == 1 ]] || ! unzip -p "$archive" "runtime/$asset" > "$work/$asset" 2>/dev/null; then
        printf '%s\n' 'Downloading the portable backup runtime...'
        url="https://github.com/astral-sh/python-build-standalone/releases/download/$release/$asset"
        curl --fail --location --silent --show-error --retry 2 --output "$work/$asset" "$url"
    fi
    verified "$work/$asset" || fail 'Portable runtime SHA-256 verification failed.'
    mv -f -- "$work/$asset" "$runtime"
fi
tar -xzf "$runtime" -C "$work"
XRAY_BACKUP_RUNTIME="$runtime" "$work/python/bin/python3" -I "$engine" "${args[@]}"
