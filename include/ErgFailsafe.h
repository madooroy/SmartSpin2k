/*
 * Copyright (C) 2020  Anthony Doud & Joel Baranick
 * All rights reserved
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */

#pragma once

#include <stdint.h>

// ERG with no controlling app: when every app that was connected (BLE or DirCon) has gone for ERG_FAILSAFE_GRACE_MS
// while ERG holds a target, ease the target to the lowest one requested in the last ERG_FAILSAFE_MEMORY_MS. In a
// structured workout that is the recovery, so a Wi-Fi drop or app crash mid-interval cannot leave the rider holding
// the effort until the app comes back. ERG stays on (no sudden slack); the app re-sends its target on reconnect.
// Riding the SmartSpin2K's own ERG without an app (shifters only) is untouched: it only acts after a disconnection.
namespace ErgFailsafe {
constexpr uint32_t GRACE_MS  = 5000;
constexpr uint32_t MEMORY_MS = 300000;

struct State {
  int lowTarget       = 0;
  uint32_t lowAt      = 0;
  uint32_t aloneSince = 0;
  bool hadController  = false;
};

// Call regularly. Returns the target to ease to, or 0 to leave the target alone.
inline int update(State& s, bool erg, int target, int controllers, uint32_t now) {
  if (erg && target > 0 && (s.lowTarget <= 0 || target <= s.lowTarget || now - s.lowAt > MEMORY_MS)) {
    s.lowTarget = target;
    s.lowAt     = now;
  }
  if (controllers > 0) {
    s.hadController = true;
    s.aloneSince    = 0;
    return 0;
  }
  if (!erg || !s.hadController) {
    s.aloneSince = 0;
    return 0;
  }
  if (s.aloneSince == 0) s.aloneSince = now == 0 ? 1 : now;
  if (now - s.aloneSince < GRACE_MS) return 0;
  s.hadController = false;   // once per disconnection
  s.aloneSince    = 0;
  return target > s.lowTarget && s.lowTarget > 0 ? s.lowTarget : 0;
}
}  // namespace ErgFailsafe
