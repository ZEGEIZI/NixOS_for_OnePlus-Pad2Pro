{ runCommandNoCC, python3, ffmpeg-headless }:
runCommandNoCC "pad2pro-hdr-test-patterns" {
  nativeBuildInputs = [ python3 ffmpeg-headless ];
} ''
  directory=$out/share/pad2pro-display-tests
  mkdir -p "$directory"
  cp ${../tools/hdr-gray-check.html} "$directory/hdr-gray-check.html"
  for pattern in steps reference highlight; do
    python3 ${../tools/make-hdr10-pattern.py} frame.yuv --pattern "$pattern"
    ffmpeg -nostdin -hide_banner -loglevel error -y \
      -f rawvideo -pixel_format yuv420p10le -video_size 1000x200 -framerate 1 \
      -i frame.yuv -frames:v 1 \
      -vf setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc:range=limited \
      -c:v libvpx-vp9 -profile:v 2 -lossless 1 -b:v 0 \
      -color_range tv -colorspace bt2020nc -color_primaries bt2020 \
      -color_trc smpte2084 -fflags +bitexact -flags:v +bitexact \
      "$directory/$pattern.webm"
    ffprobe -v error -show_entries stream=pix_fmt,color_space,color_transfer,color_primaries \
      -of json "$directory/$pattern.webm" > metadata.json
    python3 - <<'PY'
  import json
  stream = json.load(open("metadata.json"))["streams"][0]
  assert stream["pix_fmt"] == "yuv420p10le", stream
  assert stream["color_space"] == "bt2020nc", stream
  assert stream["color_transfer"] == "smpte2084", stream
  assert stream["color_primaries"] == "bt2020", stream
  PY
  done
''
