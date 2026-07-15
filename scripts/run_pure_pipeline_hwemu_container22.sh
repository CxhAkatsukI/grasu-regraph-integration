#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

IMAGE="${VIVADO_RUNNER_IMAGE:-vivado-runner:22.04-feiyang}"
BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_hw_emu_stage0"
LABEL=""
PREPARE=0
CLEAN_LINK=1

usage() {
  cat <<USAGE
Usage: $0 [options]

Run the pure GraSU -> ReGraph hw_emu link inside the Ubuntu 22.04 Vitis
runner container. This avoids host glibc/libm RELR incompatibility during
xsim libdpi.so linking on newer distributions.

Options:
  --label NAME          Evidence/log label. Default: container22_after_<git-short-hash>
  --image IMAGE         Container image. Default: ${IMAGE}
  --build-root PATH     Build root. Default: ${BUILD_ROOT}
  --prepare             Regenerate build scripts before linking.
  --no-clean-link       Do not remove previous hw_emu link temp/log/report dirs.
  -h, --help            Show this help.

The wrapper preserves existing hw_emu .xo files and runs:
  scripts/run_pure_pipeline_build.sh --target hw_emu --skip-compile
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --prepare) PREPARE=1; shift ;;
    --no-clean-link) CLEAN_LINK=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${LABEL}" ]]; then
  LABEL="container22_after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi

mkdir -p "${GRI_ROOT}/target/vivado_home" "${GRI_ROOT}/target/container_logs" "${BUILD_ROOT}/run_logs"
printf '%s\n' 'collectusagestatistics=false' > "${GRI_ROOT}/target/webtalksettings"

if [[ "${CLEAN_LINK}" == "1" ]]; then
  rm -rf \
    "${BUILD_ROOT}/build/link" \
    "${BUILD_ROOT}/logs/link" \
    "${BUILD_ROOT}/reports/link"
fi

container_label="$(printf '%s' "${LABEL}" | tr -c 'A-Za-z0-9_.-' '_')"
outer_log="${GRI_ROOT}/target/container_logs/hw_emu_${LABEL}.outer.log"

run_args=(
  "${GRI_ROOT}/scripts/run_pure_pipeline_build.sh"
  --target hw_emu
  --build-root "${BUILD_ROOT}"
  --label "${LABEL}"
  --skip-compile
)
if [[ "${PREPARE}" == "1" ]]; then
  run_args+=(--prepare)
fi

{
  printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
  printf 'label=%s\n' "${LABEL}"
  printf 'uid=%s gid=%s\n' "$(id -u)" "$(id -g)"
  printf 'image=%s\n' "${IMAGE}"
  printf 'build_root=%s\n' "${BUILD_ROOT}"
  printf 'clean_link=%s\n' "${CLEAN_LINK}"
  printf 'prepare=%s\n' "${PREPARE}"
  printf 'action=containerized_hw_emu_link_skip_compile\n'
  printf '+ podman run ... %q' "${run_args[0]}"
  printf ' %q' "${run_args[@]:1}"
  printf '\n'

  podman run --rm \
    --name "grasu-regraph-hwemu-${container_label}" \
    --platform linux/amd64 \
    --userns=keep-id \
    --user "$(id -u):$(id -g)" \
    --network host \
    --shm-size=8g \
    -v /run/udev:/run/udev:ro \
    -v /sys:/sys:ro \
    -v /etc/machine-id:/etc/machine-id:ro \
    -v /data/yxx/tools/xilinx:/data/yxx/tools/xilinx:ro \
    -v /opt/xilinx:/opt/xilinx:ro \
    -v "${GRI_ROOT}:${GRI_ROOT}" \
    -v "${GRI_ROOT}/target/webtalksettings:/data/yxx/tools/xilinx/Vivado/2024.1/data/webtalk/webtalksettings:ro" \
    -e HOME="${GRI_ROOT}/target/vivado_home" \
    -e XILINX_XRT=/opt/xilinx/xrt \
    -e PLATFORM_REPO_PATHS=/opt/xilinx/platforms \
    -w "${GRI_ROOT}" \
    "${IMAGE}" \
    "${run_args[@]}"
} 2>&1 | tee "${outer_log}"
