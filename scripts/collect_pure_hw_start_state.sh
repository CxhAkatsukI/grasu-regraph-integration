#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [--out-dir PATH]

Collect the reproducible start-state evidence for the GraSU -> ReGraph pure
hardware pipeline branch. The output is small text metadata; large xclbin and
build artifacts are hashed in place, not copied.
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
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/pure_hw_start_state_$(date +%Y%m%d_%H%M%S)"
fi

mkdir -p "${OUT_DIR}"

hash_one() {
  local role="$1"
  local path="$2"
  if [[ -e "${path}" ]]; then
    local digest size
    digest="$(sha256sum "${path}" | awk '{print $1}')"
    size="$(stat --printf '%s' "${path}")"
    printf '%s\tpresent\t%s\t%s\t%s\n' "${role}" "${digest}" "${size}" "${path}"
  else
    printf '%s\tmissing\t-\t-\t%s\n' "${role}" "${path}"
  fi
}

hash_tree() {
  local role="$1"
  local root="$2"
  shift 2
  if [[ ! -d "${root}" ]]; then
    printf '%s\tmissing\t-\t%s\n' "${role}" "${root}"
    return
  fi
  local list_file="${OUT_DIR}/${role}.files"
  local hashes_file="${OUT_DIR}/${role}.sha256s"
  find "${root}" -type f "$@" -print | LC_ALL=C sort > "${list_file}"
  if [[ ! -s "${list_file}" ]]; then
    printf '%s\tempty\t-\t%s\n' "${role}" "${root}"
    return
  fi
  xargs -r sha256sum < "${list_file}" > "${hashes_file}"
  local digest
  digest="$(sha256sum "${hashes_file}" | awk '{print $1}')"
  printf '%s\tpresent\t%s\t%s\n' "${role}" "${digest}" "${root}"
}

{
  echo "timestamp=$(date -Is)"
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "GRASU_ROOT=${GRASU_ROOT}"
  echo "REGRAPH_ROOT=${REGRAPH_ROOT}"
  echo "SPINE_ROOT=${SPINE_ROOT}"
  echo "OUT_DIR=${OUT_DIR}"
} > "${OUT_DIR}/environment.env"

{
  echo "[integration]"
  git -C "${GRI_ROOT}" status --short --branch
  git -C "${GRI_ROOT}" rev-parse HEAD
  git -C "${GRI_ROOT}" remote -v
  echo
  echo "[GraSU]"
  if [[ -d "${GRASU_ROOT}/.git" ]]; then
    git -C "${GRASU_ROOT}" status --short --branch
    git -C "${GRASU_ROOT}" rev-parse HEAD
  else
    echo "not a git repository: ${GRASU_ROOT}"
  fi
  echo
  echo "[ReGraph]"
  if [[ -d "${REGRAPH_ROOT}/.git" ]]; then
    git -C "${REGRAPH_ROOT}" status --short --branch
    git -C "${REGRAPH_ROOT}" rev-parse HEAD
  else
    echo "not a git repository: ${REGRAPH_ROOT}"
  fi
  echo
  echo "[Spine]"
  if [[ -d "${SPINE_ROOT}/.git" ]]; then
    git -C "${SPINE_ROOT}" status --short --branch
    git -C "${SPINE_ROOT}" rev-parse HEAD
  else
    echo "not a git repository: ${SPINE_ROOT}"
  fi
} > "${OUT_DIR}/git_state.txt"

{
  printf 'role\tstatus\tsha256_or_tree_sha256\tbytes\tpath\n'
  hash_one combined_hw_xclbin \
    "${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin"
  hash_one combined_hwemu_xclbin \
    "${GRI_ROOT}/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin"
  hash_one combined_hw_link_command \
    "${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/link_command.sh"
  hash_one combined_hw_manifest \
    "${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/manifest.env"
  hash_one grasu_export_host \
    "${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export"
  hash_one grasu_hw_xclbin \
    "${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin"
  hash_one regraph_sssp_host \
    "/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp"
  hash_one regraph_sssp_hw_xclbin \
    "/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin"
} > "${OUT_DIR}/artifact_hashes.tsv"

{
  printf 'role\tstatus\ttree_sha256\troot\n'
  hash_tree grasu_kernel_src "${GRASU_ROOT}/GraSU/GraSU_kernels/src" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree grasu_host_src "${GRASU_ROOT}/GraSU/GraSU/src" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree grasu_u55c_scripts "${GRASU_ROOT}/u55c_hbm" \
    \( -name '*.sh' -o -name '*.cfg' -o -name '*.ini' \)
  hash_tree regraph_acc_template "${REGRAPH_ROOT}/acc_template" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.cfg' -o -name '*.mk' \)
  hash_tree regraph_host_src "${REGRAPH_ROOT}/host" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.mk' \)
} > "${OUT_DIR}/source_fingerprints.tsv"

{
  echo "# Pure-HW Start State"
  echo
  echo "Generated: $(date -Is)"
  echo
  echo "## Commands"
  echo
  echo '```bash'
  echo "cd ${GRI_ROOT}"
  echo "./scripts/collect_pure_hw_start_state.sh --out-dir ${OUT_DIR}"
  echo '```'
  echo
  echo "## Files"
  echo
  echo "- environment: ${OUT_DIR}/environment.env"
  echo "- git state: ${OUT_DIR}/git_state.txt"
  echo "- artifact hashes: ${OUT_DIR}/artifact_hashes.tsv"
  echo "- source fingerprints: ${OUT_DIR}/source_fingerprints.tsv"
  echo
  echo "## Reminder"
  echo
  echo "This command records hashes and source fingerprints only. It does not prove"
  echo "that the pure hardware pipeline exists; it captures the reproducible baseline"
  echo "before adding completion tokens, the PMA adapter, and stream-based ReGraph input."
} > "${OUT_DIR}/summary.md"

echo "Wrote pure-hw start-state evidence:"
echo "  ${OUT_DIR}"
