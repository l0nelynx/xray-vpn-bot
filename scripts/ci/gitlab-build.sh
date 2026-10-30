#!/usr/bin/env bash
set -euo pipefail

# Bake resolves python-base from the same checkout on MR and publish builds.
image="$CI_REGISTRY_IMAGE/$NAME"
publish=false
if [[ "$CI_PIPELINE_SOURCE" != merge_request_event && ( "${CI_COMMIT_BRANCH:-}" == main || "${CI_COMMIT_BRANCH:-}" == develop ) ]]; then
  publish=true
fi
candidate="local/$NAME:check"
args=(--metadata-file build-metadata.json --pull
      --set "*.cache-from=type=registry,ref=$CI_REGISTRY_IMAGE/build-cache:$NAME")
if [[ "$publish" == true ]]; then
  candidate="$image:ci-$CI_PIPELINE_ID"
  args+=(--push --provenance=mode=max --sbom=true
         --set "$NAME.cache-to=type=registry,ref=$CI_REGISTRY_IMAGE/build-cache:$NAME,mode=max")
else
  args+=(--load --provenance=false --sbom=false)
fi
[[ "$CI_PIPELINE_SOURCE" != schedule ]] || args+=(--no-cache)
docker buildx bake "$NAME" "${args[@]}" --set "$NAME.tags=$candidate"
digest="$(python3 -c 'import json,os; print(json.load(open("build-metadata.json"))[os.environ["NAME"]]["containerimage.digest"])')"
scan_ref="$candidate"
[[ "$publish" != true ]] || scan_ref="$image@$digest"

# Install a pinned scanner and verify its release checksum; no install script.
trivy_version=0.76.1
case "$(uname -m)" in
  x86_64) platform=Linux-64bit ;;
  aarch64) platform=Linux-ARM64 ;;
  *) echo 'Unsupported scanner architecture' >&2; exit 1 ;;
esac
tools_dir="$(mktemp -d)"
archive="trivy_${trivy_version}_${platform}.tar.gz"
release="https://github.com/aquasecurity/trivy/releases/download/v${trivy_version}"
wget -q "$release/$archive" -O "$tools_dir/$archive"
wget -q "$release/trivy_${trivy_version}_checksums.txt" -O "$tools_dir/checksums.txt"
(cd "$tools_dir"; awk -v name="$archive" '$2 == name {print}' checksums.txt | sha256sum -c -)
tar -xzf "$tools_dir/$archive" -C "$tools_dir" trivy
"$tools_dir/trivy" image --quiet --scanners vuln --severity HIGH,CRITICAL \
  --list-all-pkgs --format json --output "trivy-$NAME.json" "$scan_ref"
python3 scripts/ci/check_image.py "trivy-$NAME.json"
if [[ "$NAME" != frontend ]]; then
  docker run --rm --network=none --entrypoint uv "$scan_ref" pip check --system
fi

if [[ "$publish" == true ]]; then
  environment_tag=staging
  [[ "$CI_COMMIT_BRANCH" != main ]] || environment_tag=latest
  for tag in "sha-${CI_COMMIT_SHORT_SHA}" "build-${CI_PIPELINE_IID}" "$environment_tag"; do
    docker buildx imagetools create --prefer-index=false --tag "$image:$tag" "$image@$digest"
  done
fi
