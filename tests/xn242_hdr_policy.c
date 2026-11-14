/* SPDX-License-Identifier: MIT */
/* Compile with -include packages/xn242-hdr-policy.h and -lm. */
#include <assert.h>
#include <stdio.h>

int main(void)
{
    double previous = 0;
    for (int code = 1; code <= 2047; code++) {
        double peak = xn242_peak_for_code(code);
        int roundtrip = xn242_code_for_peak(peak);
        assert(peak > previous && peak <= XN242_PEAK_NITS);
        assert(roundtrip >= code && roundtrip <= code + 1);
        previous = peak;
    }
    assert(xn242_peak_for_code(0) == 0);
    assert(xn242_code_for_peak(10000) == 2047);
    assert(xn242_code_for_peak(NAN) == 1);
    /* An HDR-tagged black or SDR-only frame must not demand peak backlight. */
    assert(xn242_target_peak(20, 0) < 21);
    assert(xn242_target_peak(203, 203) < 212);
    assert(xn242_target_peak(203, 561.5) == 561.5);
    assert(xn242_target_peak(20, NAN) == 561.5);
    /* White compensation must preserve light, not the pixel code, as the
     * global LCD backlight changes. This is digital/model verification. */
    for (double white = 2.03; white <= 426.3; white *= 1.5) {
        for (int code = xn242_code_for_peak(white * 1.04); code <= 2047; code++) {
            double available = xn242_peak_for_code(code);
            double pixel = pow(white / available, 1.0 / 2.2);
            double emitted = pow(pixel, 2.2) * available;
            assert(fabs(emitted - white) < 1e-8);
        }
    }
    for (int current = 1; current <= 2047; current += 7) {
        for (int target = 1; target <= 2047; target += 13) {
            int next = xn242_slew_code(current, target);
            assert(next >= 1 && next <= 2047);
            assert(abs(next - target) <= abs(current - target));
            assert(next - current <= 16 && next - current >= -8);
        }
    }
    puts("HDR policy: code inversion, SDR-only power floor, peak demand, stable reference white and bounded ramps passed");
    return 0;
}
