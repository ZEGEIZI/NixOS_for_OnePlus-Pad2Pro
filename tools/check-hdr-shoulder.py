#!/usr/bin/env python3
"""Exercise the compiled Mutter 51 color pipeline without starting a compositor."""
import argparse
import ctypes as C
import math
from pathlib import Path


def bind(lib, name, result, *args):
    func = getattr(lib, name)
    func.restype, func.argtypes = result, args
    return func


def check_pipeline(lib):
    ptr, flt = C.c_void_p, C.c_float
    unref = lib.g_object_unref
    context_type = bind(lib, "clutter_context_get_type", C.c_size_t)
    object_new = bind(lib, "g_object_new", ptr, C.c_size_t, C.c_char_p)
    make_state = bind(lib, "clutter_color_state_params_new_full", ptr, ptr,
                      C.c_int, C.c_int, C.POINTER(flt), *([flt] * 5))
    make_transform = bind(lib, "clutter_color_transform_new", ptr, ptr, ptr, C.c_uint)
    get_pipeline = bind(lib, "clutter_color_transform_get_pipeline", ptr, ptr)
    transform = bind(lib, "clutter_color_pipeline_do_transform", None,
                     ptr, C.POINTER(flt), C.c_size_t)
    # A context object supplies color-state IDs. CPU transforms do not need a
    # Clutter backend, a Wayland socket, or DRM master access.
    context = object_new(context_type(), None)
    # Mutter 51: colorspaces sRGB=0 / BT.2020=1; transfer sRGB=0 / gamma22=1 / PQ=2.
    primaries = (flt * 8)(0.675582, 0.318530, 0.265860, 0.685836,
                           0.143320, 0.058331, 0.297390, 0.311374)
    sdr = make_state(context, 0, 0, None, -1, 0.2, 80, 80, 80)
    pq = make_state(context, 1, 2, None, -1, 0.005, 10000, 203, 1000)
    panel = make_state(context, 0, 1, primaries, -1, 0.5315, 561.5, 203, 561.5)

    def output_nits(source, gray):
        pipe = make_transform(source, panel, 1)  # opaque RGB
        pixel = (flt * 4)(gray, gray, gray, 1)
        try:
            transform(get_pipeline(pipe), pixel, 1)
        finally:
            unref(pipe)
        assert 0 <= min(pixel[:3]) <= max(pixel[:3]) <= 1
        assert max(pixel[:3]) - min(pixel[:3]) < 0.001
        return pixel[0] ** 2.2 * 561.5

    def encode_pq(nits):
        power = (nits / 10000) ** (2610 / 16384)
        return ((3424 / 4096 + 2413 / 128 * power) / (1 + 2392 / 128 * power)) ** (2523 / 32)

    try:
        white = output_nits(sdr, 1)
        steps = [output_nits(pq, encode_pq(v)) for v in (100, 203, 400, 600, 1000)]
        assert abs(white - 203) < 0.5 and abs(steps[1] - white) < 0.5
        assert all(a < b for a, b in zip(steps, steps[1:]))
        assert steps[-1] <= 561.51
        print(f"Full Clutter PQ → native gamma: SDR white {white:.2f} nit, "
              f"nominal HDR steps {[round(v, 2) for v in steps]} nit")
        # Adaptive tone mapping must anchor the chosen reference white while
        # mapping the declared content peak to the panel's full capability.
        for reference in (2.03, 20, 203, 426.3):
            for content_peak in (400, 1000, 4000):
                source = make_state(context, 1, 2, None, -1, 0.005, 10000, 203, content_peak)
                target = make_state(context, 0, 1, primaries, -1, 0.5315, 561.5, reference, 561.5)
                pipe = make_transform(source, target, 1)
                previous = -1
                try:
                    for nits in (0, 20, 100, 203, (203 + content_peak) / 2, content_peak):
                        code = encode_pq(nits)
                        pixel = (flt * 4)(code, code, code, 1)
                        transform(get_pipeline(pipe), pixel, 1)
                        light = pixel[0] ** 2.2 * 561.5
                        assert light >= previous - 0.02 and light <= 561.52
                        previous = light
                        if nits == 203:
                            assert abs(light - reference) < 0.02, (reference, light)
                        if nits == content_peak:
                            assert abs(light - 561.5) < 0.03, (content_peak, light)
                finally:
                    for obj in (pipe, target, source):
                        unref(obj)
        print("Adaptive tone mapping: 2–426 nit reference whites, 400/1000/4000 nit content peaks passed")
        for reference in (2.03, 203, 426.3):
            source = make_state(context, 1, 2, None, -1, 0.005, 10000, 203, 10000)
            target = make_state(context, 0, 1, primaries, -1, 0.5315, 561.5, reference, 561.5)
            pipe = make_transform(source, target, 1)
            levels = []
            try:
                for nits in (203, 600, 1000, 2000, 4000, 10000):
                    code = encode_pq(nits)
                    pixel = (flt * 4)(code, code, code, 1)
                    transform(get_pipeline(pipe), pixel, 1)
                    levels.append(pixel[0] ** 2.2 * 561.5)
                assert abs(levels[0] - reference) < 0.02
                assert all(a <= b + 0.001 for a, b in zip(levels, levels[1:]))
                assert levels[3] > levels[2] + 0.1 and levels[-1] <= 561.52
            finally:
                for obj in (pipe, target, source):
                    unref(obj)
        print("Unknown content metadata: reference anchor and high-luminance tail passed")
    finally:
        for obj in (panel, pq, sdr, context):
            unref(obj)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clutter_library", type=Path)
    args = parser.parse_args()
    lib = C.CDLL(str(args.clutter_library.resolve(strict=True)))
    lib.clutter_color_op_hdr_shoulder_new.argtypes = [C.c_float]
    lib.clutter_color_op_hdr_shoulder_new.restype = C.c_void_p
    lib.clutter_color_op_do_transform.argtypes = [C.c_void_p, C.POINTER(C.c_float), C.c_size_t]
    lib.clutter_color_op_do_transform.restype = None
    lib.g_object_unref.argtypes = [C.c_void_p]
    lib.g_object_unref.restype = None

    knee = 203 / 561.5
    op = lib.clutter_color_op_hdr_shoulder_new(knee)
    if not op:
        raise RuntimeError("Could not construct HDR shoulder")
    # Black, SDR white, increasingly bright gray, and a saturated highlight.
    levels = [0, 0.01, knee / 2, knee, knee + 0.001, 1, 2, 4, 10, 100]
    samples = [[x, x, x, 1] for x in levels] + [[2, 1, 0.5, 0.75]]
    pixels = (C.c_float * (4 * len(samples)))(*(x for pixel in samples for x in pixel))
    try:
        lib.clutter_color_op_do_transform(op, pixels, len(samples))
    finally:
        lib.g_object_unref(op)
    mapped = list(pixels[::4])
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(levels[:4], mapped[:4]))
    assert math.isclose(mapped[4] - mapped[3], 0.001, abs_tol=1e-5)
    assert all(a < b for a, b in zip(mapped[:-2], mapped[1:-1]))
    assert 0.9 < mapped[-2] < 1
    r, g, b, alpha = pixels[-4:]
    assert 0 < b < g < r < 1 and math.isclose(r / g, 2) and math.isclose(g / b, 2)
    assert alpha == 0.75
    print("Compiled HDR shoulder: SDR white, monotonic highlight roll-off, RGB ratios and alpha passed")
    check_pipeline(lib)


if __name__ == "__main__":
    main()
