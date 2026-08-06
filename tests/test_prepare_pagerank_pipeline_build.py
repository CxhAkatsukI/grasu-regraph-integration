#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_pagerank_pipeline_build.sh"


def parse_manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def prepare(
    root: Path,
    algorithm: str,
    target: str,
    pipelines: int = 1,
    pipeline_mode: str = "weighted-axis",
) -> Path:
    output = root / f"{algorithm}-{target}-{pipeline_mode}-k{pipelines}"
    env = os.environ.copy()
    env["GRI_ROOT"] = str(ROOT)
    subprocess.run(
        [
            str(PREPARE),
            "--target",
            target,
            "--algorithm",
            algorithm,
            "--compute-pipelines",
            str(pipelines),
            "--pipeline-mode",
            pipeline_mode,
            "--build-root",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return output


with tempfile.TemporaryDirectory() as temp_name:
    temp = Path(temp_name)
    full = prepare(temp, "full_pagerank", "sw_emu")
    residual = prepare(temp, "residual_pagerank", "hw")
    residual_k2 = prepare(temp, "residual_pagerank", "hw", pipelines=2)
    residual_sharded = prepare(
        temp, "residual_pagerank", "hw", pipelines=4,
        pipeline_mode="sharded-k4"
    )

    full_commands = (full / "compile_commands.sh").read_text(encoding="utf-8")
    full_cfg = (full / "config/full_pagerank_sw_emu.cfg").read_text(
        encoding="utf-8"
    )
    full_link = (full / "link_command.sh").read_text(encoding="utf-8")
    full_manifest = parse_manifest(full / "manifest.env")
    residual_commands = (residual / "compile_commands.sh").read_text(
        encoding="utf-8"
    )
    residual_cfg = (residual / "config/residual_pagerank_hw.cfg").read_text(
        encoding="utf-8"
    )
    residual_manifest = parse_manifest(residual / "manifest.env")
    residual_k2_cfg = (
        residual_k2 / "config/residual_pagerank_hw.cfg"
    ).read_text(encoding="utf-8")
    residual_k2_manifest = parse_manifest(residual_k2 / "manifest.env")
    residual_sharded_cfg = (
        residual_sharded / "config/residual_pagerank_hw.cfg"
    ).read_text(encoding="utf-8")
    residual_sharded_commands = (
        residual_sharded / "compile_commands.sh"
    ).read_text(encoding="utf-8")
    residual_sharded_manifest = parse_manifest(
        residual_sharded / "manifest.env"
    )

    assert full_commands.count("v++ --target sw_emu --compile") == 11
    assert residual_commands.count("v++ --target hw --compile") == 11
    assert residual_commands.count("--kernel_frequency 150") == 11
    assert "-DGRASU_REGRAPH_PAGERANK_MODE=1" in full_commands
    assert "-DGRASU_REGRAPH_PAGERANK_MODE=2" in residual_commands
    assert "-DGRASU_REGRAPH_DESTINATION_ONLY=1" in full_commands
    assert "-DGRASU_COMPACT_HBM_PORTS" in residual_commands
    assert "-DGRASU_SHARE_HBM_PORTS" in residual_commands
    assert "-DGRASU_REGRAPH_SHARE_ROW_OFFSET_PORT=1" in residual_commands
    assert "-I" + str(ROOT / "include/regraph_pagerank") in full_commands
    assert "CPLUS_INCLUDE_PATH=" + str(full / "gcc_compat") in full_link
    assert "-D_GTHREAD_USE_COND_INIT_FUNC" in full_link
    assert "pma_to_regraph_edge_array" not in full_cfg
    assert "dispatch_degree_1.degree_delta:grasu_degree_update_1.degree_delta:64" in full_cfg
    assert "regraph_pagerank_apply_1.residual_state" not in full_cfg
    assert "pr_source_1.residual_state" not in full_cfg
    assert "sp=regraph_pagerank_apply_1.residual_state:HBM[5]" in residual_cfg
    assert "sp=pr_source_1.residual_state:HBM[5]" in residual_cfg
    assert "nk=regraph_pagerank_source_prepare:1:pr_source_1" in full_cfg
    assert "sp=pr_source_1.rank_state:HBM[4]" in full_cfg
    assert "sp=bin_search_1.binary_0:HBM[0]" in full_cfg
    assert "sp=bin_search_1.row_offset_0" not in full_cfg
    assert "sp=bin_search_1.binary_1" not in full_cfg
    assert "sp=bin_search_1.row_offset_1" not in full_cfg
    assert "sp=grasu_degree_update_1.status:HBM[6]" in full_cfg
    assert "sp=regraph_pagerank_apply_1.round_stats:HBM[6]" in full_cfg
    assert "sp=pr_source_1.round_stats:HBM[6]" in full_cfg
    assert "HBM[7]" not in full_cfg
    assert "source_prop_write:kernelHBMWrapper_1.prop_write_burst_stm:16" in full_cfg
    assert full_manifest["CLAIM_CLASS"] == (
        "proposed_conversion_free_hls_not_yet_built"
    )
    assert full_manifest["DEGREE_SIDEBAND"] == (
        "dispatch_ordered_projected_optimization"
    )
    assert full_manifest["RESIDUAL_HBM_CHANNEL"] == "unused"
    assert residual_manifest["RESIDUAL_HBM_CHANNEL"] == "5"
    assert residual_manifest["KERNEL_FREQUENCY_MHZ"] == "150"
    assert residual_manifest["COMPUTE_PIPELINES"] == "1"
    assert residual_k2_manifest["COMPUTE_PIPELINES"] == "2"
    assert residual_k2_manifest["PIPELINE_TOPOLOGY"] == (
        "direct_complete_worker_replication"
    )
    assert (
        "nk=pma_to_regraph_adapter:2:"
        "pma_to_regraph_adapter_1.pma_to_regraph_adapter_2"
    ) in residual_k2_cfg
    assert "nk=lksg_stream:2:lksg_stream_1.lksg_stream_2" in residual_k2_cfg
    assert (
        "regraph_pagerank_apply_2.source_prop_write:"
        "kernelHBMWrapper_2.prop_write_burst_stm:16"
    ) in residual_k2_cfg
    assert residual_sharded_commands.count("v++ --target hw --compile") == 12
    assert "-DGRASU_REGRAPH_SHARDED_PMA=1" in residual_sharded_commands
    assert (
        "-DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1"
        in residual_sharded_commands
    )
    assert "-DGRASU_SHARE_HBM_PORTS" not in residual_sharded_commands
    assert "-DLITTLE_KERNEL_NUM=4" in residual_sharded_commands
    source_prepare_line = next(
        line for line in residual_sharded_commands.splitlines()
        if "regraph_pagerank_source_prepare_compile.cfg" in line
    )
    assert "-DGRASU_REGRAPH_SHARDED_PMA=1" in source_prepare_line
    assert "regraph_k4_shared_hbm_wrapper" in residual_sharded_commands
    assert (
        "port=src_prop_3 offset=slave bundle=gmem1"
        in (ROOT / "kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp")
        .read_text(encoding="utf-8")
    )
    assert (
        "port=src_prop_4 offset=slave bundle=gmem2"
        in (ROOT / "kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp")
        .read_text(encoding="utf-8")
    )
    assert "sharedLittleKernelReadMemory<0>" in (
        ROOT / "kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp"
    ).read_text(encoding="utf-8")
    assert "nk=pma_to_regraph_adapter:4:" in residual_sharded_cfg
    assert "nk=lksg_stream:4:" in residual_sharded_cfg
    assert "nk=regraph_frontend_mux:1:regraph_frontend_mux_1" in (
        residual_sharded_cfg
    )
    assert residual_sharded_cfg.count("nk=kernelLittleGSMerger:1") == 1
    assert residual_sharded_cfg.count("nk=regraph_pagerank_apply:1") == 1
    assert residual_sharded_cfg.count("nk=kernelHBMWrapper:1") == 1
    assert "sp=pr_source_1.rank_state:HBM[25:26]" in residual_sharded_cfg
    assert "sp=pr_source_1.residual_state" not in residual_sharded_cfg
    assert "sp=pr_source_1.out_degree:HBM[27]" in residual_sharded_cfg
    assert "sp=kernelHBMWrapper_1.src_prop_3:HBM[23]" in residual_sharded_cfg
    assert residual_sharded_manifest["PIPELINE_MODE"] == "sharded-k4"
    assert residual_sharded_manifest["COMPUTE_PIPELINES"] == "4"
    assert residual_sharded_manifest["PIPELINE_TOPOLOGY"] == (
        "four_sharded_pma_source_gather_frontends_one_shared_downstream"
    )
    assert residual_sharded_manifest["SHARED_REGRAPH_DOWNSTREAM"] == "1"
    assert residual_sharded_manifest["PMA_DDR_AXI_BUNDLES_PER_CU"] == "4"
    assert residual_sharded_manifest["SHARED_SOURCE_AXI_BUNDLES"] == "2"
    assert residual_sharded_manifest["RESIDUAL_HBM_CHANNEL"] == "26"
    sharded_run_build = (residual_sharded / "run_build.sh").read_text(
        encoding="utf-8"
    )
    assert "--pipeline-mode sharded-k4" in sharded_run_build
    assert "kernelHBMWrapper.hw.xo --expected-masters 2" in sharded_run_build
    assert "regraph_pagerank_source_prepare.hw.xo --expected-masters 4" in (
        sharded_run_build
    )
    assert "--kernel_frequency 150" in (residual / "link_command.sh").read_text(
        encoding="utf-8"
    )
    assert (full / "inputs.tsv").read_text().count("generated_xo\tpending") == 11
    assert "check_xo_master_budget.py" in (residual / "run_build.sh").read_text(
        encoding="utf-8"
    )
    assert "check_pipeline_master_budget.py" in (
        residual / "run_build.sh"
    ).read_text(encoding="utf-8")
    assert "check_xo_master_budget.py" not in (full / "run_build.sh").read_text(
        encoding="utf-8"
    )
    assert "sw_emu XO omits synthesized bundle metadata" in (
        full / "run_build.sh"
    ).read_text(encoding="utf-8")

    for packet in (full, residual, residual_k2, residual_sharded):
        subprocess.run(["bash", "-n", str(packet / "compile_commands.sh")], check=True)
        subprocess.run(["bash", "-n", str(packet / "link_command.sh")], check=True)
        subprocess.run(["bash", "-n", str(packet / "run_build.sh")], check=True)

    invalid = subprocess.run(
        [str(PREPARE), "--algorithm", "not-an-algorithm"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert "Invalid --algorithm" in invalid.stderr

print("test_prepare_pagerank_pipeline_build PASS")
