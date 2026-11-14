#!/usr/bin/env python3
"""Capture Chromium HDR Canvas values and Wayland-client capabilities.

Run inside the desktop user's session. Does not change the display mode.
WAYLAND_DEBUG=1 records the actual surface color description on stderr.
Screenshots are for layout checks; they cannot verify physical HDR luminance.
"""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlencode


def probe(binary, page, video, screenshot, seconds, testufo=False, engine="webgl"):
    with tempfile.TemporaryDirectory(prefix="pad2pro-browser-hdr-") as profile:
        read_command, write_command = os.pipe()
        read_reply, write_reply = os.pipe()
        command_fd = fcntl.fcntl(read_command, fcntl.F_DUPFD, 10)
        reply_fd = fcntl.fcntl(write_reply, fcntl.F_DUPFD, 10)
        env = os.environ.copy()
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        process = subprocess.Popen(
            ["bash", "-c", f'exec 3<&{command_fd} 4>&{reply_fd}; exec "$@"',
             "bash", binary, "--enable-automation", "--no-first-run",
             "--disable-background-networking", "--remote-debugging-pipe",
             "--ozone-platform=wayland", f"--user-data-dir={profile}",
             "--window-size=1400,1150", "about:blank"],
            env=env, pass_fds=(command_fd, reply_fd), start_new_session=True,
            stdout=subprocess.DEVNULL,
        )
        for fd in (read_command, write_reply, command_fd, reply_fd):
            os.close(fd)
        pending, count = b"", 0

        def cdp(method, params=None, session=None):
            nonlocal pending, count
            count += 1
            message = {"id": count, "method": method, "params": params or {}}
            if session:
                message["sessionId"] = session
            payload = json.dumps(message).encode() + b"\0"
            while payload:
                payload = payload[os.write(write_command, payload):]
            deadline = time.monotonic() + 15
            while True:
                while b"\0" not in pending:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([read_reply], [], [], remaining)[0]:
                        raise TimeoutError(method)
                    chunk = os.read(read_reply, 65536)
                    if not chunk:
                        raise EOFError(method)
                    pending += chunk
                item, pending = pending.split(b"\0", 1)
                response = json.loads(item)
                if response.get("id") == count:
                    if "error" in response:
                        raise RuntimeError(response["error"])
                    return response.get("result", {})

        try:
            targets = cdp("Target.getTargets")["targetInfos"]
            target = next(x["targetId"] for x in targets if x["type"] == "page")
            session = cdp("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]

            def js(expression):
                answer = cdp("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True}, session)
                if "exceptionDetails" in answer:
                    raise RuntimeError(answer["exceptionDetails"])
                return answer.get("result", {}).get("value")

            if testufo:
                url = "https://testufo.com/hdr"
            else:
                url = page.resolve(strict=True).as_uri()
                if video:
                    url += "?" + urlencode({"video": video.resolve(strict=True).as_uri()})
            cdp("Page.enable", session=session)
            if testufo:
                cdp("Page.addScriptToEvaluateOnNewDocument", {"source": """
                  window.fillTrace=[];
                  window.canvasContexts=new WeakMap();
                  window.hdrRequests=[];
                  const getContext=HTMLCanvasElement.prototype.getContext;
                  HTMLCanvasElement.prototype.getContext=function(...args){
                    const context=Reflect.apply(getContext,this,args);
                    if(context)canvasContexts.set(this,{context,type:args[0]});
                    return context;
                  };
                  const configure=HTMLCanvasElement.prototype.configureHighDynamicRange;
                  if(configure)HTMLCanvasElement.prototype.configureHighDynamicRange=function(...args){
                    hdrRequests.push(args);return Reflect.apply(configure,this,args);
                  };
                  const descriptor=Object.getOwnPropertyDescriptor(CanvasRenderingContext2D.prototype,'fillStyle');
                  Object.defineProperty(CanvasRenderingContext2D.prototype,'fillStyle',{
                    ...descriptor,set(value){
                      if(fillTrace.length<10000)fillTrace.push(String(value));
                      descriptor.set.call(this,value);
                    }
                  });
                """}, session)
            navigation = cdp("Page.navigate", {"url": url}, session)
            if navigation.get("errorText"):
                raise RuntimeError(navigation["errorText"])
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                ready = ("!!document.getElementById('testufo-hdr-global-colorspace')" if testufo else
                         "!!window.results && (!document.querySelector('video').src || document.querySelector('video').readyState >= 2 || !!document.querySelector('video').error)")
                if js(ready):
                    break
                time.sleep(0.2)
            if testufo:
                js("""(()=>{
                  for(const [id,value] of [['testufo-hdr-global-engine',__ENGINE__],['testufo-hdr-global-colorspace','rec2100-pq']]){
                    const select=document.getElementById(id);
                    if(!select)throw new Error('Missing TestUFO selector: '+id);
                    select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));
                  }
                })()""".replace("__ENGINE__", json.dumps(engine)))
                for _ in range(40):
                    if js("(()=>{const c=document.getElementById('area51');const r=canvasContexts.get(c);return r && (r.type!=='2d' || fillTrace.length>20);})()"):
                        break
                    time.sleep(0.2)
                result = js("""(async()=>{
                  const samples=[];
                  let details={};
                  for(let frame=0;frame<12;frame++){
                    const c=document.getElementById('area51');
                    const record=canvasContexts.get(c);
                    if(!record)throw new Error('TestUFO did not create a canvas context');
                    const ctx=record.context;
                    let pixels;
                    details={contextType:record.type,attributes:ctx.getContextAttributes()};
                    if(record.type==='2d'){
                      pixels=ctx.getImageData(0,0,c.width,c.height,{colorSpace:'rec2100-pq',pixelFormat:'rgba-float16'}).data;
                      details.globalHDRHeadroom=ctx.globalHDRHeadroom;
                    }else{
                      const type=ctx.getParameter(ctx.IMPLEMENTATION_COLOR_READ_TYPE);
                      const format=ctx.getParameter(ctx.IMPLEMENTATION_COLOR_READ_FORMAT);
                      if(format!==ctx.RGBA)throw new Error('Unexpected WebGL readback format: '+format);
                      const data=type===ctx.FLOAT?new Float32Array(c.width*c.height*4):type===ctx.HALF_FLOAT?new Uint16Array(c.width*c.height*4):new Uint8Array(c.width*c.height*4);
                      ctx.getError();ctx.readPixels(0,0,c.width,c.height,format,type,data);
                      const error=ctx.getError();if(error)throw new Error('WebGL readback failed: '+error);
                      pixels=type===ctx.HALF_FLOAT?new Float16Array(data.buffer):type===ctx.UNSIGNED_BYTE?Float32Array.from(data,v=>v/255):data;
                      details.drawingBufferColorSpace=ctx.drawingBufferColorSpace;
                      details.componentBits=[ctx.getParameter(ctx.RED_BITS),ctx.getParameter(ctx.GREEN_BITS),ctx.getParameter(ctx.BLUE_BITS)];
                    }
                    let max=0;
                    for(let p=0;p<pixels.length;p+=4)max=Math.max(max,pixels[p],pixels[p+1],pixels[p+2]);
                    samples.push(max);
                    await new Promise(resolve=>setTimeout(resolve,250));
                  }
                  return {url:location.href,hdr:matchMedia('(dynamic-range:high)').matches,
                    ...details,hdrRequests,
                    engine:document.getElementById('testufo-hdr-global-engine').value,
                    colorSpace:document.getElementById('testufo-hdr-global-colorspace').value,
                    fillStyles:[...new Set(fillTrace)],maxChannelPQ:samples};
                })()""")
            else:
                result = js("typeof results === 'object' ? (report(), results) : null")
            if not result:
                raise RuntimeError("The diagnostic page did not initialize")
            result["browser"] = cdp("Browser.getVersion")
            args = cdp("Browser.getBrowserCommandLine")["arguments"]
            result["flags"] = [a for a in args if any(t in a for t in ("ozone", "enable-features", "blink-features", "color-profile"))]
            aux = cdp("SystemInfo.getInfo").get("gpu", {}).get("auxAttributes", {})
            result["gpu"] = {k: aux.get(k) for k in ("glRenderer", "glVersion", "displayType")}
            if screenshot:
                shot = cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session)
                screenshot.write_bytes(base64.b64decode(shot["data"]))
            # Fail on missing/flattened input levels, independently of HDR detection.
            for key, row in result.get("rows", {}).items():
                if "error" in row:
                    raise RuntimeError(f"Canvas {key}: {row['error']}")
                values = [sample[0] for sample in row["samples"]]
                if not all(a < b for a, b in zip(values, values[1:])):
                    raise RuntimeError(f"Canvas {key} lost distinct PQ inputs: {values}")
            return result
        finally:
            try:
                cdp("Browser.close")
            except (OSError, TimeoutError, EOFError, RuntimeError):
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            for fd in (write_command, read_reply):
                os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default="chromium")
    parser.add_argument("--page", type=Path, default=Path(__file__).with_name("hdr-gray-check.html"))
    parser.add_argument("--video", type=Path, help="Optional HDR VP9/WebM reference clip")
    parser.add_argument("--screenshot", type=Path, help="Layout screenshot, not physical HDR evidence")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--testufo", action="store_true", help="Inspect TestUFO's actual drawing buffer over 12 samples")
    parser.add_argument("--engine", choices=["webgl", "2d"], default="webgl", help="TestUFO renderer; WebGL is the validated HDR path")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    print(json.dumps(probe(args.binary, args.page, args.video, args.screenshot, args.seconds, args.testufo, args.engine), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
