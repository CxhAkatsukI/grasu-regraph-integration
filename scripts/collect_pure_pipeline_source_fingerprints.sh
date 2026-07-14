#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

LABEL=""
OUT_FILE=""

usage() {
  cat <<USAGE
Usage: $0 [--label NAME] [--out-file PATH]

Collect deterministic source tree fingerprints for the GraSU -> ReGraph pure
pipeline. The output TSV is small; per-file lists and hashes are written next
to it for auditability.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --out-file) OUT_FILE="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cd "${GRI_ROOT}"

if [[ -z "${LABEL}" ]]; then
  LABEL="after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi
if [[ -z "${OUT_FILE}" ]]; then
  OUT_FILE="${GRI_ROOT}/.tmp_build/pure_pipeline_source_fingerprints/source_fingerprints_${LABEL}.tsv"
fi

OUT_DIR="$(dirname "${OUT_FILE}")"
mkdir -p "${OUT_DIR}"

{
  printf 'role\tstatus\ttree_sha256\troot\n'
  hash_tree integration_scripts "${GRI_ROOT}/scripts" \
    \( -name '*.sh' -o -name '*.py' \)
  hash_tree integration_kernels "${GRI_ROOT}/kernels" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree integration_tools "${GRI_ROOT}/tools" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree grasu_kernel_src "${GRASU_ROOT}/GraSU/GraSU_kernels/src" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree grasu_host_src "${GRASU_ROOT}/GraSU/GraSU/src" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree grasu_u55c_scripts "${GRASU_ROOT}/u55c_hbm" \
    \( -name '*.sh' -o -name '*.cfg' -o -name '*.ini' \)
  hash_tree regraph_acc_template "${REGRAPH_ROOT}/acc_template" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.cfg' -o -name '*.mk' \)
  hash_tree regraph_acc_udfs "${REGRAPH_ROOT}/acc_udfs" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \)
  hash_tree regraph_host_src "${REGRAPH_ROOT}/host" \
    \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.mk' \)
} > "${OUT_FILE}"

echo "DONE source_fingerprints_out=${OUT_FILE}"
