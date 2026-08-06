#!/usr/bin/env python3

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_pure_hw_pipeline_build.sh"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_manifest(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        result[key] = value
    return result


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    grasu = tmp / "GraSU"
    regraph = tmp / "ReGraph"
    hls = tmp / "hls"
    platform = tmp / "platform.xpfm"
    platform.touch()
    (hls / "etc").mkdir(parents=True)

    write(
        grasu / "u55c_hbm/config/GraSU-link.cfg",
        """[connectivity]
nk=bin_search:4:bin_search_1.bin_search_2.bin_search_3.bin_search_4
sp=bin_search_1.edges:HBM[0]
sp=bin_search_1.binary_0:HBM[0]
sp=bin_search_1.row_offset_0:HBM[0]
nk=dispatch:1:dispatch_1
nk=process_cache:2:process_cache_1.process_cache_2
sp=process_cache_1.pma_cache:HBM[0]
nk=process_ddr:2:process_ddr_1.process_ddr_2
sp=process_ddr_1.pma_in0_ddr:HBM[1]
""",
    )
    write(
        grasu / "u55c_hbm/config/stream_connect.ini",
        """[connectivity]
stream_connect=bin_search_1.segment_head_stream_out:dispatch_1.segment_head_stream_1
stream_connect=dispatch_1.dispatch_to_process_cache_1:process_cache_1.update_stream
""",
    )
    write(
        regraph / "acc_template/connectivity.cfg",
        """[connectivity]
stream_connect=littleKernelScatterGather_1.l_ppb_request_stm:kernelHBMWrapper_1.l_ppb_request_stm_1
stream_connect=kernelHBMWrapper_1.l_ppb_response_stm_1:littleKernelScatterGather_1.l_ppb_response_stm
stream_connect=littleKernelScatterGather_1.l_tmp_prop_stm:kernelLittleGSMerger_1.l_tmp_prop_stm_1:16
stream_connect=bigKernelScatterGather_1.b_tmp_prop_stm:kernelBigGSMerger_1.b_tmp_prop_stm_1
stream_connect=kernelLittleGSMerger_1.l_write_burst_stm:kernelApply_1.l_merged_prop_stm:16
stream_connect=kernelBigGSMerger_1.b_write_burst_stm:kernelApply_1.b_merged_prop_stm:16
nk=kernelLittleGSMerger:1
nk=kernelBigGSMerger:1
nk=kernelApply:1
nk=kernelHBMWrapper:1
nk=littleKernelScatterGather:1
sp=littleKernelScatterGather_1.part_edge_array:HBM[0]
nk=bigKernelScatterGather:1
sp=bigKernelScatterGather_1.part_edge_array:HBM[2]
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "GRI_ROOT": str(ROOT),
            "GRASU_ROOT": str(grasu),
            "REGRAPH_ROOT": str(regraph),
        }
    )

    outputs = {}
    cases = (
        ("compactor", "weighted_sssp"),
        ("weighted-axis", "weighted_sssp"),
        ("weighted-axis", "connected_components"),
        ("sharded-k4", "weighted_sssp"),
        ("sharded-k4", "connected_components"),
    )
    for mode, algorithm in cases:
        if mode == "sharded-k4" and algorithm == "connected_components":
            key = "sharded-k4-cc"
        else:
            key = mode if algorithm == "weighted_sssp" else algorithm
        out = tmp / key
        subprocess.run(
            [
                str(PREPARE),
                "--target",
                "sw_emu",
                "--pipeline-mode",
                mode,
                "--algorithm",
                algorithm,
                "--platform-xpfm",
                str(platform),
                "--hls-include",
                str(hls),
                "--hls-include-etc",
                str(hls / "etc"),
                "--build-root",
                str(out),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["bash", "-n", str(out / "compile_commands.sh")], check=True)
        subprocess.run(["bash", "-n", str(out / "link_command.sh")], check=True)
        outputs[key] = out

    compactor = outputs["compactor"]
    compactor_manifest = parse_manifest(compactor / "manifest.env")
    compactor_cfg = Path(compactor_manifest["LINK_CFG"]).read_text(encoding="utf-8")
    compactor_compile = (compactor / "compile_commands.sh").read_text(encoding="utf-8")
    assert compactor_manifest["CLAIM_CLASS"] == "native_hls_aligned_with_conversion"
    assert compactor_manifest["HANDOFF"] == "capacity_wide_compactor_to_edge_array"
    assert compactor_manifest["CONVERSION_COST"] == "included"
    assert "nk=pma_to_regraph_edge_array:1:pma_to_regraph_edge_array_1" in compactor_cfg
    assert "nk=littleKernelScatterGather:1" in compactor_cfg
    assert "pma_to_regraph_adapter" not in compactor_cfg
    assert "GRASU_REGRAPH_WEIGHTED_PMA" not in compactor_compile

    weighted = outputs["weighted-axis"]
    weighted_manifest = parse_manifest(weighted / "manifest.env")
    weighted_cfg = Path(weighted_manifest["LINK_CFG"]).read_text(encoding="utf-8")
    weighted_compile = (weighted / "compile_commands.sh").read_text(encoding="utf-8")
    weighted_link = (weighted / "link_command.sh").read_text(encoding="utf-8")
    weighted_inputs = (weighted / "inputs.tsv").read_text(encoding="utf-8")
    assert weighted_manifest["CLAIM_CLASS"] == "candidate_hls_not_yet_built"
    assert weighted_manifest["HANDOFF"] == "weighted_pma_to_axis_stream"
    assert weighted_manifest["CONVERSION_COST"] == "absent"
    compile_lines = [
        line for line in weighted_compile.splitlines() if line.startswith("v++ ")
    ]
    assert compile_lines
    assert all("--kernel_frequency 200" in line for line in compile_lines)
    assert "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1" in weighted_cfg
    assert "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32" in weighted_cfg
    assert "nk=lksg_stream:1:lksg_stream_1" in weighted_cfg
    assert "sp=kernelApply_1.active_count:HBM[30]" in weighted_cfg
    assert "pma_to_regraph_edge_array" not in weighted_cfg
    assert "part_edge_array" not in weighted_cfg
    assert "bigKernelScatterGather" not in weighted_cfg
    assert "kernelBigGSMerger" not in weighted_cfg
    assert "-DGRASU_REGRAPH_WEIGHTED_PMA=1" in weighted_compile
    assert "kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp" in weighted_compile
    assert "kernels/regraph_stream_little_gs/little_gs_stream.cpp" in weighted_compile
    assert "kernels/regraph_sssp_apply_status/kernel_apply.cpp" in weighted_compile
    lksg_command = next(
        line for line in weighted_compile.splitlines()
        if "lksg_stream.sw_emu.xo" in line
    )
    assert f"-I{regraph}/acc_template/kernel_little_gs" in lksg_command
    assert "pma_to_regraph_edge_array.cpp" not in weighted_compile
    assert "pma_to_regraph_adapter.sw_emu.xo" in weighted_link
    assert "lksg_stream.sw_emu.xo" in weighted_link
    assert "generator_source\tpresent\t" in weighted_inputs
    assert "pma_to_regraph_adapter.cpp" in weighted_inputs
    assert "little_gs_stream.cpp" in weighted_inputs
    assert "GRI_GIT_HEAD" in weighted_manifest
    assert "GRASU_GIT_HEAD" in weighted_manifest
    assert "GRI_GIT_TRACKED_DIRTY" in weighted_manifest
    assert "GRASU_GIT_UNTRACKED_COUNT" in weighted_manifest

    cc = outputs["connected_components"]
    cc_manifest = parse_manifest(cc / "manifest.env")
    cc_cfg = Path(cc_manifest["LINK_CFG"]).read_text(encoding="utf-8")
    cc_compile = (cc / "compile_commands.sh").read_text(encoding="utf-8")
    assert cc_manifest["ALGORITHM"] == "connected_components"
    assert cc_manifest["PIPELINE_STEM"] == "connected_components_pma_native"
    assert cc_manifest["REGRAPH_EDGE_PROP"] == "0"
    assert cc_manifest["ADAPTER_MODE_DEFINE"] == (
        "-DGRASU_REGRAPH_DESTINATION_ONLY=1"
    )
    assert "-DHAVE_EDGE_PROP=0" in cc_compile
    assert f"-I{ROOT}/include/regraph_cc" in cc_compile
    assert "-DGRASU_REGRAPH_DESTINATION_ONLY=1" in cc_compile
    assert "-DGRASU_REGRAPH_WEIGHTED_PMA=1" not in cc_compile
    assert "connected_components connectivity" in cc_cfg
    assert "sp=kernelApply_1.active_count:HBM[30]" in cc_cfg

    sharded = outputs["sharded-k4"]
    sharded_manifest = parse_manifest(sharded / "manifest.env")
    sharded_cfg = Path(sharded_manifest["LINK_CFG"]).read_text(encoding="utf-8")
    sharded_compile = (sharded / "compile_commands.sh").read_text(
        encoding="utf-8"
    )
    sharded_link = (sharded / "link_command.sh").read_text(encoding="utf-8")
    assert sharded_manifest["PIPELINE_MODE"] == "sharded-k4"
    assert sharded_manifest["CLAIM_CLASS"] == (
        "candidate_sharded_k4_hls_not_yet_built"
    )
    assert sharded_manifest["HANDOFF"] == (
        "four_sharded_pma_source_gather_frontends_to_one_regraph_downstream"
    )
    assert sharded_manifest["PMA_FRONTEND_CUS"] == "4"
    assert sharded_manifest["SHARED_REGRAPH_DOWNSTREAM"] == "1"
    assert sharded_manifest["SHARDED_PMA_DEFINE"] == (
        "-DGRASU_REGRAPH_SHARDED_PMA=1"
    )
    assert (
        "nk=pma_to_regraph_adapter:4:"
        "pma_to_regraph_adapter_1.pma_to_regraph_adapter_2."
        "pma_to_regraph_adapter_3.pma_to_regraph_adapter_4"
    ) in sharded_cfg
    assert "nk=lksg_stream:4:" in sharded_cfg
    assert "nk=regraph_frontend_mux:1:regraph_frontend_mux_1" in sharded_cfg
    assert sharded_cfg.count(".edge_burst_out:lksg_stream_") == 4
    assert sharded_cfg.count(".l_tmp_prop_stm:regraph_frontend_mux_1.input") == 4
    assert (
        "stream_connect=regraph_frontend_mux_1.output:"
        "kernelLittleGSMerger_1.l_tmp_prop_stm_1:32"
    ) in sharded_cfg
    assert sharded_cfg.count("nk=lksg_stream:") == 1
    assert sharded_cfg.count("nk=kernelApply:1") == 1
    assert sharded_cfg.count("nk=kernelHBMWrapper:1") == 1
    assert "sp=bin_search_1.edges:HBM[0:5]" in sharded_cfg
    assert "sp=bin_search_1.edges:HBM[0]\n" not in sharded_cfg
    assert "sp=process_cache_1.pma_cache:HBM[0:5]" in sharded_cfg
    assert "sp=process_ddr_1.pma_in0_ddr:HBM[6:11]" in sharded_cfg
    for index in range(1, 5):
        assert (
            f"sp=pma_to_regraph_adapter_{index}.pma0:HBM[0:22]"
            in sharded_cfg
        )
        assert f"sp=pma_to_regraph_adapter_{index}.pma1:" not in sharded_cfg
    assert "sp=kernelHBMWrapper_1.src_prop_1:HBM[23]" in sharded_cfg
    assert "sp=kernelHBMWrapper_1.src_prop_2:HBM[24]" in sharded_cfg
    assert "sp=kernelHBMWrapper_1.src_prop_3:HBM[23]" in sharded_cfg
    assert "sp=kernelHBMWrapper_1.src_prop_4:HBM[24]" in sharded_cfg
    assert "sp=kernelApply_1.vertex_prop:HBM[30]" in sharded_cfg
    assert "-DGRASU_REGRAPH_WEIGHTED_PMA=1" in sharded_compile
    assert "-DGRASU_REGRAPH_SHARDED_PMA=1" in sharded_compile
    assert "-DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1" in sharded_compile
    assert "kernels/regraph_frontend_mux/regraph_frontend_mux.cpp" in sharded_compile
    assert "kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp" in (
        sharded_compile
    )
    assert "-DLITTLE_KERNEL_NUM=4" in sharded_compile
    assert "regraph_frontend_mux.sw_emu.xo" in sharded_link

    sharded_cc = outputs["sharded-k4-cc"]
    sharded_cc_manifest = parse_manifest(sharded_cc / "manifest.env")
    sharded_cc_cfg = Path(sharded_cc_manifest["LINK_CFG"]).read_text(
        encoding="utf-8"
    )
    sharded_cc_compile = (sharded_cc / "compile_commands.sh").read_text(
        encoding="utf-8"
    )
    assert sharded_cc_manifest["ALGORITHM"] == "connected_components"
    assert sharded_cc_manifest["PIPELINE_MODE"] == "sharded-k4"
    assert sharded_cc_manifest["PIPELINE_STEM"] == (
        "connected_components_pma_native_sharded_k4"
    )
    assert sharded_cc_manifest["PMA_FRONTEND_CUS"] == "4"
    assert sharded_cc_manifest["SHARED_REGRAPH_DOWNSTREAM"] == "1"
    assert sharded_cc_cfg.count("nk=lksg_stream:") == 1
    assert "nk=lksg_stream:4:" in sharded_cc_cfg
    assert sharded_cc_cfg.count("nk=kernelApply:1") == 1
    assert sharded_cc_cfg.count("nk=kernelHBMWrapper:1") == 1
    assert "-DHAVE_EDGE_PROP=0" in sharded_cc_compile
    assert "-DGRASU_REGRAPH_DESTINATION_ONLY=1" in sharded_cc_compile
    assert "-DGRASU_REGRAPH_SHARDED_PMA=1" in sharded_cc_compile
    assert "-DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1" in sharded_cc_compile
    assert "-DGRASU_REGRAPH_WEIGHTED_PMA=1" not in sharded_cc_compile

    invalid = subprocess.run(
        [str(PREPARE), "--pipeline-mode", "invalid"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert "Invalid --pipeline-mode" in invalid.stderr

print("test_prepare_weighted_pma_native_build PASS")
