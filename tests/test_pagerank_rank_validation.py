from pathlib import Path
import subprocess
import tempfile
import unittest


class PageRankValidationTests(unittest.TestCase):
    def test_global_error_and_nonfinite_guards(self):
        root = Path(__file__).resolve().parents[1]
        source = r'''
#include "tools/pagerank_rank_validation.hpp"
#include <cassert>
#include <initializer_list>
#include <limits>

int main() {
    grasu_regraph::PageRankValidation exact, noise, zero, shifted;
    for (unsigned i = 0; i < 100000; ++i) {
        exact.observe(1.0e-5, 1.0e-5);
        noise.observe(1.0e-5, 1.0e-5 + 1.0e-9);
        zero.observe(1.0e-5, 0.0);
        shifted.observe(1.0e-5, 1.0e-5 + 1.0e-7);
    }
    assert(exact.passes());
    assert(noise.passes());
    assert(!zero.passes());
    assert(!shifted.passes());
    for (double invalid : {std::numeric_limits<double>::quiet_NaN(),
                           std::numeric_limits<double>::infinity(),
                           -std::numeric_limits<double>::infinity()}) {
        grasu_regraph::PageRankValidation actual, expected;
        actual.observe(1.0, invalid);
        expected.observe(invalid, 1.0);
        assert(!actual.passes() && actual.nonfinite == 1);
        assert(!expected.passes() && expected.nonfinite == 1);
    }
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "check"
            subprocess.run(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-I", str(root),
                 "-x", "c++", "-", "-o", str(binary)],
                input=source, text=True, check=True, capture_output=True,
            )
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
