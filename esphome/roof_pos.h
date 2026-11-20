// Jarnan Observatory roof - position estimate from travel time.
// Position is in seconds of travel: 0 = fully closed, TRAVEL = fully open.
#pragma once
#include <cstdint>

namespace roof {

// position right now (clamped to 0..travel)
inline float current(float pos, int dir, uint32_t t0, uint32_t now, float travel) {
  float p = pos + dir * (float) (now - t0) / 1000.0f;
  if (p < 0.0f) p = 0.0f;
  if (p > travel) p = travel;
  return p;
}

// still travelling? (the margin covers a motor slightly slower than measured)
inline bool moving(float pos, int dir, uint32_t t0, uint32_t now, float travel, float margin) {
  if (dir == 0) return false;
  float remaining = dir > 0 ? travel - pos : pos;
  return (float) (now - t0) / 1000.0f < remaining + margin;
}

// seconds left until the end of the current move
inline float left(float pos, int dir, uint32_t t0, uint32_t now, float travel) {
  if (dir == 0) return 0.0f;
  float c = current(pos, dir, t0, now, travel);
  return dir > 0 ? travel - c : c;
}

}  // namespace roof
