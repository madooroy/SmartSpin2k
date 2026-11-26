"""ERG failsafe: ease to the recent recovery target when the controlling app is gone.

Run: python -B -m unittest discover -s test -p test_erg_failsafe.py
"""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <cassert>
#include <cstdio>
#include "ErgFailsafe.h"
using namespace ErgFailsafe;
int main() {
  {  // Nov 26 shape: 165 W recovery, 395 W effort, Wi-Fi drops mid-effort: eased to 165 W after 5 s, once.
    State s; uint32_t t = 1000;
    for (int i = 0; i < 20; ++i, t += 500) assert(update(s, true, 165, 1, t) == 0);
    for (int i = 0; i < 20; ++i, t += 500) assert(update(s, true, 395, 1, t) == 0);
    int eased = 0;
    for (int i = 0; i < 20; ++i, t += 500) { int e = update(s, true, 395, 0, t); if (e) { eased = e; break; } }
    assert(eased == 165);
    for (int i = 0; i < 20; ++i, t += 500) assert(update(s, true, 165, 0, t) == 0);   // once per disconnection
    printf("eased to %d\n", eased);
  }
  {  // A blip shorter than the grace period changes nothing.
    State s; uint32_t t = 1000;
    update(s, true, 165, 1, t); t += 500; update(s, true, 395, 1, t);
    for (int i = 0; i < 9; ++i) { t += 500; assert(update(s, true, 395, 0, t) == 0); }
    t += 500; assert(update(s, true, 395, 1, t) == 0);
    for (int i = 0; i < 9; ++i) { t += 500; assert(update(s, true, 395, 0, t) == 0); }
  }
  {  // No app ever connected (SmartSpin2K's own ERG with shifters): never eased.
    State s; uint32_t t = 1000;
    update(s, true, 150, 0, t);
    for (int i = 0; i < 40; ++i) { t += 500; assert(update(s, true, 200, 0, t) == 0); }
  }
  {  // Not in ERG: nothing; already at the lowest: nothing; old lows expire after MEMORY_MS.
    State s; uint32_t t = 1000;
    update(s, true, 100, 1, t); t += MEMORY_MS + 1000; update(s, true, 300, 1, t);
    int eased = 0;
    for (int i = 0; i < 20; ++i) { t += 500; int e = update(s, true, 300, 0, t); if (e) eased = e; }
    assert(eased == 0);   // the 100 W low expired; 300 W is the lowest recent target
    State n; update(n, false, 0, 1, 1000);
    for (uint32_t k = 1500; k < 12000; k += 500) assert(update(n, false, 0, 0, k) == 0);
  }
  printf("erg failsafe OK\n");
  return 0;
}
'''


class TestErgFailsafe(unittest.TestCase):
    def test_failsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "failsafe.cpp"
            exe = Path(tmp) / "failsafe"
            src.write_text(HARNESS)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-I", str(ROOT / "include"), str(src), "-o", str(exe)], check=True)
            out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
            self.assertIn("erg failsafe OK", out)


if __name__ == "__main__":
    unittest.main()
