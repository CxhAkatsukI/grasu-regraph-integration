#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts" / "prepare_weighted_pma_hw_relink.py"
COLLECT = ROOT / "scripts" / "collect_weighted_pma_hw_relink.py"

XO_NAMES = (
    "bin_search.hw.xo",
    "dispatch.hw.xo",
    "kernelApply.hw.xilinx_u55c.xo",
    "kernelHBMWrapper.hw.xilinx_u55c.xo",
    "kernelLittleGSMerger.hw.xilinx_u55c.xo",
    "process_cache.hw.xo",
    "process_ddr.hw.xo",
    "pma_completion_barrier.hw.xo",
    "pma_to_regraph_adapter.hw.xo",
    "lksg_stream.hw.xo",
)

PAGERANK_XO_NAMES = (
    "bin_search.hw.xo",
    "dispatch_degree.hw.xo",
    "grasu_degree_update.hw.xo",
    "kernelHBMWrapper.hw.xo",
    "kernelLittleGSMerger.hw.xo",
    "lksg_stream.hw.xo",
    "pma_to_regraph_adapter.hw.xo",
    "process_cache.hw.xo",
    "process_ddr.hw.xo",
    "regraph_frontend_mux.hw.xo",
    "regraph_pagerank_apply.hw.xo",
    "regraph_pagerank_source_prepare.hw.xo",
)


def make_source(root: Path, target: str = "hw") -> Path:
    source = root / "source"
    (source / "build").mkdir(parents=True)
    (source / "config").mkdir()
    cfg = source / "config" / "weighted.cfg"
    cfg.write_text(
        "\n".join(
            [
                "platform=fake.xpfm",
                "messageDb=/old/build.mdb",
                "temp_dir=/old/temp",
                "report_dir=/old/reports",
                "log_dir=/old/logs",
                "remote_ip_cache=/old/cache",
                "",
                "[connectivity]",
                "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1",
                "stream_connect=pma_to_regraph_adapter_1.out:lksg_stream_1.in:32",
                "",
                "[vivado]",
                "prop=run.impl_1.STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE=Explore",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (source / "manifest.env").write_text(
        "\n".join(
            [
                f"TARGET={target}",
                "PIPELINE_MODE=weighted-axis",
                "GRI_GIT_HEAD=a927186",
                f"LINK_CFG={cfg}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    for index, name in enumerate(XO_NAMES):
        (source / "build" / name).write_bytes(f"xo-{index}".encode())
    return source


def make_pagerank_source(root: Path) -> Path:
    source = root / "source"
    (source / "build").mkdir(parents=True)
    (source / "config").mkdir()
    cfg = source / "config" / "residual_pagerank_hw.cfg"
    cfg.write_text(
        "\n".join(
            [
                "platform=fake.xpfm",
                "messageDb=/old/build.mdb",
                "temp_dir=/old/temp",
                "report_dir=/old/reports",
                "log_dir=/old/logs",
                "remote_ip_cache=/old/cache",
                "",
                "[connectivity]",
                "nk=regraph_frontend_mux:1:regraph_frontend_mux_1",
                "slr=pr_source_1:SLR1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    source_xclbin = source / "build" / "grasu_regraph_residual_pagerank.hw.xclbin"
    (source / "manifest.env").write_text(
        "\n".join(
            [
                "TARGET=hw",
                "PIPELINE_MODE=sharded-k4",
                "ALGORITHM=residual_pagerank",
                "GRI_GIT_HEAD=bfe2024",
                f"LINK_CFG={cfg}",
                f"OUT_XCLBIN={source_xclbin}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    for index, name in enumerate(PAGERANK_XO_NAMES):
        (source / "build" / name).write_bytes(f"pagerank-xo-{index}".encode())
    return source


def write_timing_report(path: Path, wns: float, tns: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "| Design Timing Summary",
                "| ---------------------",
                "WNS(ns) TNS(ns) Failing Total WHS THS HoldFail HoldTotal WPWS TPWS",
                "------- ------- ------- ----- --- --- -------- --------- ---- ----",
                f" {wns:.3f} {tns:.3f} 0 1000 0.010 0.000 0 1000 0.000 0.000",
            ]
        ),
        encoding="utf-8",
    )


class WeightedPmaRelinkTest(unittest.TestCase):
    def test_route_aggressive_packet_reuses_exact_xos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_source(temp)
            packet = temp / "packet"
            subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(packet),
                    "--profile",
                    "route-aggressive",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
            cfg = (packet / "config/weighted_pma_native_hw_relink.cfg").read_text(
                encoding="utf-8"
            )
            command = (packet / "link_command.sh").read_text(encoding="utf-8")
            self.assertEqual(manifest["input_xo_count"], 10)
            self.assertEqual(manifest["source_git_head"], "a927186")
            self.assertEqual(cfg.count("[vivado]"), 1)
            self.assertIn("DIRECTIVE=AltSpreadLogic_high", cfg)
            self.assertIn("ROUTE_DESIGN.ARGS.DIRECTIVE=AggressiveExplore", cfg)
            self.assertNotIn("/old/", cfg)
            self.assertIn(str(source / "build/bin_search.hw.xo"), command)
            self.assertIn(str(packet / "build/grasu_regraph_weighted_pma_native.hw.xclbin"), command)
            self.assertEqual(len((packet / "inputs.tsv").read_text().splitlines()), 13)

    def test_place_extranet_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_source(temp)
            packet = temp / "packet"
            subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(packet),
                    "--profile",
                    "place-extranet",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            cfg = (packet / "config/weighted_pma_native_hw_relink.cfg").read_text()
            self.assertIn("DIRECTIVE=ExtraNetDelay_high", cfg)
            self.assertIn("ROUTE_DESIGN.ARGS.DIRECTIVE=AlternateCLBRouting", cfg)

    def test_sharded_pagerank_packet_reuses_exact_xos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_pagerank_source(temp)
            packet = temp / "packet"
            subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(packet),
                    "--profile",
                    "route-aggressive",
                    "--pipeline-kind",
                    "sharded-pagerank",
                    "--kernel-frequency",
                    "150",
                    "--source-prepare-slr",
                    "SLR2",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(
                (packet / "manifest.json").read_text(encoding="utf-8")
            )
            cfg = (
                packet / "config/sharded_k4_residual_pagerank_hw_relink.cfg"
            ).read_text(encoding="utf-8")
            command = (packet / "link_command.sh").read_text(encoding="utf-8")
            self.assertEqual(manifest["algorithm"], "residual_pagerank")
            self.assertEqual(manifest["pipeline_kind"], "sharded-pagerank")
            self.assertEqual(manifest["input_xo_count"], len(PAGERANK_XO_NAMES))
            self.assertEqual(manifest["kernel_frequency_mhz"], 150)
            self.assertEqual(manifest["source_prepare_slr"], "SLR2")
            self.assertEqual(cfg.count("[vivado]"), 1)
            self.assertIn("DIRECTIVE=AltSpreadLogic_high", cfg)
            self.assertIn("slr=pr_source_1:SLR2", cfg)
            self.assertNotIn("/old/", cfg)
            self.assertIn(
                str(source / "build/regraph_pagerank_source_prepare.hw.xo"),
                command,
            )
            self.assertIn(
                str(packet / "build/grasu_regraph_residual_pagerank.hw.xclbin"),
                command,
            )

    def test_non_hw_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_source(temp, target="hw_emu")
            result = subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(temp / "packet"),
                    "--profile",
                    "route-aggressive",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TARGET must be hw", result.stderr)

    def test_collector_requires_xclbin_and_nonnegative_timing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_source(temp)
            packet = temp / "packet"
            subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(packet),
                    "--profile",
                    "route-aggressive",
                ],
                check=True,
            )
            report = packet / "reports/link/impl/timing_summary_routed.rpt"
            write_timing_report(report, -0.187, -13.166)
            failed = subprocess.run(
                ["python3", str(COLLECT), "--packet-root", str(packet)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(failed.returncode, 1)
            failed_json = json.loads((packet / "result.json").read_text())
            self.assertFalse(failed_json["passed"])
            self.assertEqual(failed_json["wns_ns"], -0.187)

            Path(failed_json["xclbin"]).write_bytes(b"xclbin")
            write_timing_report(report, 0.031, 0.0)
            passed = subprocess.run(
                ["python3", str(COLLECT), "--packet-root", str(packet)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(passed.returncode, 0)
            passed_json = json.loads((packet / "result.json").read_text())
            self.assertTrue(passed_json["passed"])
            self.assertEqual(passed_json["claim_class"], "routed_timing_closed")

    def test_collector_can_accept_platform_autoscale_without_hiding_slack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = make_source(temp)
            packet = temp / "packet"
            subprocess.run(
                [
                    "python3",
                    str(PREPARE),
                    "--source-build-root",
                    str(source),
                    "--out-root",
                    str(packet),
                    "--profile",
                    "route-aggressive",
                    "--kernel-frequency",
                    "150",
                ],
                check=True,
            )
            manifest = json.loads((packet / "manifest.json").read_text())
            xclbin = Path(manifest["output_xclbin"])
            xclbin.write_bytes(b"xclbin")
            Path(str(xclbin) + ".info").write_text(
                "\n".join(
                    [
                        "Scalable Clocks",
                        "---------------",
                        "   Name:      hbm_aclk",
                        "   Type:      SYSTEM",
                        "   Frequency: 429 MHz",
                        "",
                        "   Name:      DATA_CLK",
                        "   Type:      DATA",
                        "   Frequency: 150 MHz",
                        "",
                        "System Clocks",
                    ]
                ),
                encoding="utf-8",
            )
            report = packet / "reports/link/impl/timing_summary_routed.rpt"
            write_timing_report(report, -0.107, -28.768)

            strict = subprocess.run(
                ["python3", str(COLLECT), "--packet-root", str(packet)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(strict.returncode, 1)

            accepted = subprocess.run(
                [
                    "python3",
                    str(COLLECT),
                    "--packet-root",
                    str(packet),
                    "--accept-platform-autoscale",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            result = json.loads((packet / "result.json").read_text())
            self.assertTrue(result["passed"])
            self.assertFalse(result["timing_closed"])
            self.assertTrue(result["platform_autoscale_accepted"])
            self.assertTrue(result["kernel_target_met"])
            self.assertEqual(result["selected_kernel_frequency_mhz"], 150.0)
            self.assertEqual(result["selected_system_frequency_mhz"], 429.0)
            self.assertEqual(
                result["claim_class"],
                "routed_kernel_target_met_platform_autoscaled",
            )


if __name__ == "__main__":
    unittest.main()
