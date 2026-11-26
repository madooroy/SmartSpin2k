/*
 * Copyright (C) 2020  Anthony Doud & Joel Baranick
 * All rights reserved
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */

#pragma once

#include <stdint.h>

// ERG with no controlling app: when the app that last wrote the FTMS control point (BLE or DirCon) disconnects and
// stays gone for GRACE_MS while ERG holds a target, ease the target to the lowest one requested in the last MEMORY_MS.
// In a structured workout that is the recovery, so a Wi-Fi drop or app crash mid-interval cannot leave the rider
// holding the effort until the app comes back. ERG stays on (no sudden slack); the app re-sends its target on reconnect.
//
// Only the controlling app counts: a phone with the config app, a head unit or a second app connecting and leaving
// changes nothing, and SmartSpin2K's own ERG (shifters or web page, no control-point writer) is never touched.
// The target used is the rider's real one: while the cadence pause holds the minimum watts, the paused target.
// Set ERG_FAILSAFE_ENABLED to 0 to build without it.
#ifndef ERG_FAILSAFE_ENABLED
#define ERG_FAILSAFE_ENABLED 1
#endif

namespace ErgFailsafe {
constexpr uint32_t GRACE_MS  = 5000;
constexpr uint32_t MEMORY_MS = 300000;
constexpr int BUCKETS        = 5;                     // a sliding minimum: one lowest target per minute, five minutes
constexpr uint32_t BUCKET_MS = MEMORY_MS / BUCKETS;

enum Source : uint8_t { NONE = 0, BLE = 1, DIRCON = 2 };

// Who last wrote the control point. Written from the BLE and DirCon callbacks (single bytes and words: no lock).
struct Writer {
  volatile uint8_t source = NONE;
  volatile uint16_t id    = 0;
  volatile bool present   = false;
  volatile uint32_t goneAt = 0;
};
inline Writer& writer() {
  static Writer w;
  return w;
}
// A control-point write from [source] client [id] (BLE connection handle, DirCon client index).
inline void noteWrite(uint8_t source, uint16_t id, uint32_t now) {
  Writer& w = writer();
  (void)now;
  w.source  = source;
  w.id      = id;
  w.goneAt  = 0;
  w.present = true;
}
// A client disconnected: if it was the writer, it is gone from [now].
inline void noteDisconnect(uint8_t source, uint16_t id, uint32_t now) {
  Writer& w = writer();
  if (w.present && w.source == source && w.id == id) {
    w.present = false;
    w.goneAt  = now == 0 ? 1 : now;
  }
}

struct State {
  int low[BUCKETS]         = {0, 0, 0, 0, 0};
  uint32_t bucketStart     = 0;
  bool started             = false;
  uint32_t handledGoneAt   = 0;   // each disconnection eases once
};

inline void _roll(State& s, uint32_t now) {
  if (!s.started) {
    s.started     = true;
    s.bucketStart = now;
    return;
  }
  while (now - s.bucketStart >= BUCKET_MS) {
    for (int i = BUCKETS - 1; i > 0; --i) s.low[i] = s.low[i - 1];
    s.low[0] = 0;
    s.bucketStart += BUCKET_MS;
  }
}

inline int lowest(const State& s) {
  int m = 0;
  for (int i = 0; i < BUCKETS; ++i)
    if (s.low[i] > 0 && (m == 0 || s.low[i] < m)) m = s.low[i];
  return m;
}

// Call regularly with the rider's real target ([target]: the paused target while the cadence pause holds the minimum).
// [writerPresent]/[writerGoneAt] from writer(). Returns the target to ease to, or 0 to leave it alone.
inline int update(State& s, bool erg, int target, bool writerPresent, uint32_t writerGoneAt, uint32_t now) {
  _roll(s, now);
  if (erg && target > 0 && (s.low[0] == 0 || target < s.low[0])) s.low[0] = target;
  if (!erg || writerPresent || writerGoneAt == 0 || writerGoneAt == s.handledGoneAt) return 0;
  if (now - writerGoneAt < GRACE_MS) return 0;
  s.handledGoneAt = writerGoneAt;
  const int low   = lowest(s);
  return target > low && low > 0 ? low : 0;
}
}  // namespace ErgFailsafe
