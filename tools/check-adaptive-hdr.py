#!/usr/bin/env python3
"""Exercise the actual adaptive-output GLSL without changing a display/session."""
import argparse
import ast
from pathlib import Path
import re
import subprocess
import tempfile


def strings(text):
    return "".join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"', text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_view", type=Path)
    parser.add_argument("runner", type=Path)
    args = parser.parse_args()
    source = args.stage_view.read_text()
    start = source.index("COGL_SNIPPET_HOOK_FRAGMENT,", source.index("add_adaptive_hdr ("))
    end = source.index("float values[2]", start)
    compensation = strings(source[start:end])
    declarations, body = compensation.split("highp vec3 light", 1)
    compensation = declarations + "void main() { vec4 cogl_color_out = texelFetch(cogl_sampler0, ivec2(0), 0);\nhighp vec3 light" + body + "\nfrag = cogl_color_out; }\n"
    start = source.index("cogl_snippet_set_replace (snippet,", source.index("sample_adaptive_hdr ("))
    end = source.index("priv->adaptive_hdr_reduction =", start)
    reduction = strings(source[start:end])
    reduction = reduction.replace("cogl_tex_coord0_in.st", "(gl_FragCoord.xy / xn242_size.zw)")
    reduction = reduction.replace("texture2D(", "texture(").replace("cogl_color_out =", "frag =")
    reduction = "uniform highp vec4 xn242_size;\nvoid main() {\n" + reduction + "\n}\n"
    preamble = "#version 300 es\nprecision highp float;\nuniform highp sampler2D cogl_sampler0;\nout vec4 frag;\n"
    with tempfile.TemporaryDirectory(prefix="xn242-adaptive-check-") as directory:
        paths = [Path(directory) / name for name in ("reduce.frag", "compensate.frag")]
        for path, text in zip(paths, (reduction, compensation)):
            path.write_text(preamble + text)
        subprocess.run([str(args.runner.resolve()), *(str(p) for p in paths)], check=True)


if __name__ == "__main__":
    main()
