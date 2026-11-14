/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef XN242_HDR_POLICY_H
#define XN242_HDR_POLICY_H

#include <math.h>

/* Factory reference, not a Linux photometer measurement. KTZ8868's estimated
 * exponential current curve is deliberately kept separate from pixel gamma.
 * Replace this estimate with measured per-code luminance when available. */
#define XN242_PEAK_NITS 561.5
#define XN242_MAX_CODE 2047
#define XN242_LOG_CODE_STEP 0.003035958
#define XN242_SAMPLE_INTERVAL_US 100000
#define XN242_HIGHLIGHT_HOLD_US 1000000

static inline double
xn242_peak_for_code (int code)
{
  if (code <= 0)
    return 0;
  if (code > XN242_MAX_CODE)
    code = XN242_MAX_CODE;
  return XN242_PEAK_NITS * exp ((code - XN242_MAX_CODE) * XN242_LOG_CODE_STEP);
}

static inline int
xn242_code_for_peak (double nits)
{
  int code;
  if (!isfinite (nits) || nits <= 0)
    return 1;
  code = (int) ceil (XN242_MAX_CODE + log (nits / XN242_PEAK_NITS) / XN242_LOG_CODE_STEP);
  return code < 1 ? 1 : code > XN242_MAX_CODE ? XN242_MAX_CODE : code;
}

static inline double
xn242_target_peak (double reference, double content_peak)
{
  double peak;
  reference = isfinite (reference) ? fmax (1, fmin (reference, XN242_PEAK_NITS)) : 203;
  content_peak = isfinite (content_peak) ? fmax (0, content_peak) : XN242_PEAK_NITS;
  /* Small measurement/quantization margin, no HDR-window/metadata-only boost. */
  peak = fmax (reference, content_peak) * 1.04;
  return fmin (XN242_PEAK_NITS, peak);
}

static inline int
xn242_slew_code (int current, int target)
{
  /* ~5% rise / ~2.5% fall in estimated light per 25 ms step. */
  int delta = target - current;
  return current + (delta > 16 ? 16 : delta < -8 ? -8 : delta);
}

#endif
