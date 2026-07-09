#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

check_path() {
  local label="$1"
  local path="$2"
  if [[ -e "${path}" ]]; then
    printf "PASS %-12s %s\n" "${label}" "${path}"
  else
    printf "MISS %-12s %s\n" "${label}" "${path}"
  fi
}

git_summary() {
  local label="$1"
  local path="$2"
  if git -C "${path}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch
    local head
    local dirty
    branch="$(git -C "${path}" branch --show-current)"
    if git -C "${path}" rev-parse --verify HEAD >/dev/null 2>&1; then
      head="$(git -C "${path}" rev-parse --short HEAD)"
    else
      head="no-commits-yet"
    fi
    dirty="$(git -C "${path}" status --short | wc -l)"
    printf "GIT  %-12s branch=%s head=%s dirty_lines=%s\n" \
      "${label}" "${branch:-detached}" "${head}" "${dirty}"
  else
    printf "GIT  %-12s not-a-git-repository\n" "${label}"
  fi
}

printf "Integration root: %s\n" "${GRI_ROOT}"
check_path "GraSU" "${GRASU_ROOT}"
check_path "ReGraph" "${REGRAPH_ROOT}"
check_path "Spine" "${SPINE_ROOT}"

git_summary "workspace" "${GRI_ROOT}"
git_summary "GraSU" "${GRASU_ROOT}"
git_summary "ReGraph" "${REGRAPH_ROOT}"
git_summary "Spine" "${SPINE_ROOT}"

check_path "GraSU host" "${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/GraSU_host_u55c"
check_path "GraSU xclbin" "${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin"
check_path "Spine xclbin" "${SPINE_ROOT}/tests/test_integration/xclbin/spine_integration.hw.xclbin"
