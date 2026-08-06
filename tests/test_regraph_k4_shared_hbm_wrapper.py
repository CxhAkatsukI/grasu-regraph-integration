from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
HLS_INCLUDE = Path("/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include")


class SharedHbmWrapperTests(unittest.TestCase):
    def test_two_frontends_share_each_physical_hbm_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "shared_hbm_wrapper_tb"
            subprocess.run(
                [
                    "g++", "-std=c++17", "-O2", "-w",
                    f"-I{HLS_INCLUDE}",
                    f"-I{HLS_INCLUDE / 'etc'}",
                    f"-I{ROOT / 'repos/ReGraph/acc_template/common'}",
                    f"-I{ROOT / 'repos/ReGraph/acc_template/kernel_hbm_wrapper'}",
                    "-DPARTITION_SIZE=65536",
                    "-DLITTLE_KERNEL_DST_BUFFER_SIZE=65536",
                    "-DBIG_KERNEL_DST_BUFFER_SIZE=524288",
                    "-DSRC_BUFFER_SIZE=4096",
                    "-DLOG2_SRC_BUFFER_SIZE=12",
                    "-DLITTLE_KERNEL_NUM=4",
                    "-DBIG_KERNEL_NUM=0",
                    "-DREGRAPH_PURE_LITTLE_ONLY",
                    str(ROOT / "tests/regraph_k4_shared_hbm_wrapper_tb.cpp"),
                    "-o", str(binary),
                ],
                check=True,
                cwd=ROOT,
            )
            completed = subprocess.run(
                [str(binary)], check=True, capture_output=True, text=True
            )
            self.assertIn("PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
