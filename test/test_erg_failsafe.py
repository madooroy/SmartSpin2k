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
// Ride [n] half-second ticks at [target]; returns the first eased value (0 if none).
static int ride(State& s, uint32_t& t, int n, int target) {
  int eased = 0;
  for (int i = 0; i < n; ++i, t += 500) {
    const Writer& w = writer();
    int e = update(s, true, target, w.present, w.goneAt, t);
    if (e && !eased) eased = e;
  }
  return eased;
}
static void fresh() { writer() = Writer(); }
int main() {
  {  // Nov 26 shape: 165 W recovery, 395 W effort, the app's Wi-Fi drops mid-effort: eased to 165 W after 5 s, once.
    fresh(); State s; uint32_t t = 1000;
    noteWrite(DIRCON, 0, t);
    assert(ride(s, t, 20, 165) == 0);
    assert(ride(s, t, 20, 395) == 0);
    noteDisconnect(DIRCON, 0, t);
    assert(ride(s, t, 9, 395) == 0);                 // inside the grace period
    assert(ride(s, t, 4, 395) == 165);
    assert(ride(s, t, 40, 165) == 0);                // once per disconnection
    printf("eased to 165\n");
  }
  {  // The app back within the grace period: nothing.
    fresh(); State s; uint32_t t = 1000;
    noteWrite(DIRCON, 0, t); ride(s, t, 4, 165); ride(s, t, 4, 395);
    noteDisconnect(DIRCON, 0, t); ride(s, t, 6, 395);
    noteWrite(DIRCON, 1, t);
    assert(ride(s, t, 40, 395) == 0);
  }
  {  // Review: another client (config app on a phone, head unit) leaving changes nothing; only the writer counts.
    fresh(); State s; uint32_t t = 1000;
    noteWrite(DIRCON, 0, t); ride(s, t, 4, 165); ride(s, t, 4, 395);
    noteDisconnect(BLE, 3, t); noteDisconnect(DIRCON, 1, t);
    assert(ride(s, t, 40, 395) == 0);
  }
  {  // SmartSpin2K's own ERG (no control-point writer ever): never eased.
    fresh(); State s; uint32_t t = 1000;
    ride(s, t, 4, 150);
    noteDisconnect(BLE, 0, t);
    assert(ride(s, t, 40, 200) == 0);
  }
  {  // Review: the rider's real target during a cadence pause. The caller passes the paused target (395), never the
     // stand-in minimum, so the low stays the recovery and a stop while the app is gone still eases on resume.
    fresh(); State s; uint32_t t = 1000;
    noteWrite(BLE, 7, t); ride(s, t, 10, 165); ride(s, t, 10, 395);
    noteDisconnect(BLE, 7, t);
    assert(ride(s, t, 20, 395) == 165);
  }
  {  // Sliding minimum: a 100 W low over five minutes ago is forgotten, a long effort keeps the recovery before it.
    fresh(); State s; uint32_t t = 1000;
    noteWrite(DIRCON, 0, t);
    ride(s, t, 4, 100);
    ride(s, t, 2 * (MEMORY_MS / 1000) + 130, 300);   // > 5 min at 300 W
    noteDisconnect(DIRCON, 0, t);
    assert(ride(s, t, 20, 300) == 0);               // 300 W is the lowest recent target
    fresh(); State l; t = 1000;
    noteWrite(DIRCON, 0, t);
    ride(l, t, 4, 165);
    ride(l, t, 2 * 240, 395);                        // 4 min effort: the 165 W recovery is still remembered
    noteDisconnect(DIRCON, 0, t);
    assert(ride(l, t, 20, 395) == 165);
  }
  {  // Not in ERG: nothing.
    fresh(); State n; uint32_t t = 1000;
    noteWrite(DIRCON, 0, t); noteDisconnect(DIRCON, 0, t);
    for (int i = 0; i < 30; ++i, t += 500) assert(update(n, false, 0, writer().present, writer().goneAt, t) == 0);
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
