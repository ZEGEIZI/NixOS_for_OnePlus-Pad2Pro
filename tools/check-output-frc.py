#!/usr/bin/env python3
"""Run the compositor's FRC GLSL through composition and XR30 GPU buffers.

Pass the patched Mutter clutter-stage-view.c and a compiled
tests/xn242_output_frc.c executable. No compositor or display mode is changed.
"""
import argparse
import ast
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_view", type=Path)
    parser.add_argument("runner", type=Path)
    args = parser.parse_args()
    source = args.stage_view.read_text()
    start = source.index("snippet = cogl_snippet_new (", source.index("add_output_frc ("))
    end = source.index("cogl_pipeline_add_snippet", start)
    strings = re.findall(r'"(?:\\.|[^"\\])*"', source[start:end])
    glsl = "".join(ast.literal_eval(s) for s in strings)
    declarations, body = glsl.split("highp vec2 pixel", 1)
    shader = (
        "#version 300 es\nprecision highp float;\n"
        "uniform highp sampler2D input_texture;\nout vec4 frag;\n"
        + declarations
        + "void main() {\n"
        "highp vec4 cogl_color_out = texelFetch(input_texture, ivec2(gl_FragCoord.xy), 0);\n"
        "highp vec2 pixel" + body + "\nfrag = cogl_color_out;\n}\n"
    )
    with tempfile.TemporaryDirectory(prefix="xn242-frc-check-") as directory:
        path = Path(directory) / "frc.frag"
        path.write_text(shader)
        subprocess.run([str(args.runner.resolve()), str(path)], check=True)


if __name__ == "__main__":
    main()
