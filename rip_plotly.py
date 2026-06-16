#!/usr/bin/env python3
"""Extract the first Plotly figure from a write_html-style page into a plain
figure JSON ({"data": ..., "layout": ...}), decoding Plotly's base64 typed
arrays into normal number lists so the result works with any Plotly version.

Usage:
    python3 rip_plotly.py <url-or-html-file> <output.json>

Note: assumes a little-endian host (true for normal x86/ARM machines).
"""
import sys, json, base64, array, urllib.request

# Plotly bdata dtype -> Python `array` typecode (little-endian, native on x86/ARM)
_TYPE = {'f8': 'd', 'f4': 'f', 'i1': 'b', 'u1': 'B', 'i2': 'h', 'u2': 'H',
         'i4': 'i', 'u4': 'I', 'i8': 'q', 'u8': 'Q'}


def load_source(src):
    if src.startswith(('http://', 'https://')):
        req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
    with open(src, encoding='utf-8', errors='replace') as f:
        return f.read()


def parse_value(s, i):
    """Return (json_text, end_index) for the JSON value starting at/after i."""
    while s[i] in ' \n\r\t':
        i += 1
    start, c = i, s[i]
    if c == '"':                                  # string
        i += 1
        while True:
            if s[i] == '\\':
                i += 2
                continue
            if s[i] == '"':
                i += 1
                break
            i += 1
        return s[start:i], i
    if c in '[{':                                 # array / object (string-aware)
        depth, instr = 0, False
        while i < len(s):
            ch = s[i]
            if instr:
                if ch == '\\':
                    i += 2
                    continue
                if ch == '"':
                    instr = False
            else:
                if ch == '"':
                    instr = True
                elif ch in '[{':
                    depth += 1
                elif ch in ']}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1
        return s[start:i], i
    while i < len(s) and s[i] not in ',)]}':      # primitive
        i += 1
    return s[start:i].strip(), i


def reshape(flat, dims):
    if len(dims) <= 1:
        return flat
    step = len(flat) // dims[0]
    return [reshape(flat[k * step:(k + 1) * step], dims[1:]) for k in range(dims[0])]


def decode(o):
    """Recursively turn Plotly base64 typed arrays into plain lists."""
    if isinstance(o, dict):
        if 'bdata' in o and 'dtype' in o:
            a = array.array(_TYPE[o['dtype']])
            a.frombytes(base64.b64decode(o['bdata']))
            vals = list(a)
            shape = o.get('shape')
            if shape:
                dims = [int(x) for x in str(shape).replace(' ', '').split(',') if x]
                vals = reshape(vals, dims)
            return vals
        return {k: decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [decode(v) for v in o]
    return o


# for a "pure" graph keep only geometry + axis labels, drop all cosmetics
_AXIS_KEEP = ('title', 'range', 'type', 'autorange')
_SCENE_KEEP = ('camera', 'aspectmode', 'aspectratio', 'dragmode')


def purify(layout):
    """Strip title, background, template, buttons, etc. — keep only what defines
    the graph's shape and axis labels, so the site can theme the rest."""
    out = {}
    scene = layout.get('scene')
    if isinstance(scene, dict):
        s = {}
        for ax in ('xaxis', 'yaxis', 'zaxis'):
            a = scene.get(ax)
            if isinstance(a, dict):
                kept = {k: a[k] for k in _AXIS_KEEP if k in a}
                if kept:
                    s[ax] = kept
        for k in _SCENE_KEEP:
            if k in scene:
                s[k] = scene[k]
        if s:
            out['scene'] = s
    return out


def main():
    full = '--full' in sys.argv                   # keep the original layout verbatim
    bare = '--no-axes' in sys.argv                # hide the 3D axes (lines/grid/labels)
    argv = [a for a in sys.argv[1:] if a not in ('--full', '--no-axes')]
    if len(argv) < 2:
        print("usage: python3 rip_plotly.py [--full] [--no-axes] <url-or-html-file> <output.json>")
        sys.exit(1)
    html = load_source(argv[0])
    key = 'Plotly.newPlot('
    k = html.find(key)
    if k < 0:
        print("no Plotly.newPlot() call found in the page")
        sys.exit(2)
    i = k + len(key)
    _, i = parse_value(html, i)                   # div id (discarded)
    i = html.index(',', i) + 1
    data_txt, i = parse_value(html, i)            # data array
    i = html.index(',', i) + 1
    layout_txt, i = parse_value(html, i)          # layout object
    layout = decode(json.loads(layout_txt))
    lay = layout if full else purify(layout)
    if bare:
        scene = lay.setdefault('scene', {})
        for ax in ('xaxis', 'yaxis', 'zaxis'):
            scene[ax] = {'visible': False}        # no axis line, ticks, grid or labels
    fig = {'data': decode(json.loads(data_txt)), 'layout': lay}
    with open(argv[1], 'w') as f:
        json.dump(fig, f)
    print("wrote %s  (%d traces, %s%s)" % (argv[1], len(fig['data']),
          'full' if full else 'pure', ', no axes' if bare else ''))


if __name__ == '__main__':
    main()
