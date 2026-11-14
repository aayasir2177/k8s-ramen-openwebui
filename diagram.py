#!/usr/bin/env python3
"""
Architecture Diagram & GIF Generator for Hybrid Local AI Stack:
Kubernetes (Open WebUI) + Bare-Metal Host (RAMen AI & llama.cpp)
"""

import os
import re
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.saas.cdn import Cloudflare
from diagrams.k8s.compute import Deployment, Pod
from diagrams.k8s.network import Service
from diagrams.k8s.storage import PersistentVolumeClaim
from diagrams.generic.os import LinuxGeneral
from diagrams.generic.compute import Rack
from diagrams.generic.storage import Storage

DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DIR, "docs")
NAME = "architecture"

GRAPH_ATTR = {
    "fontsize": "18",
    "bgcolor": "#ffffff",
    "fontcolor": "#0f172a",
    "fontname": "Helvetica-Bold",
    "pad": "0.4",
    "splines": "spline",
    "nodesep": "0.6",
    "ranksep": "0.85",
    "labelloc": "t",
}

NODE_ATTR = {
    "fontcolor": "#0f172a",
    "fontsize": "12",
    "fontname": "Helvetica-Bold",
}

EDGE_ATTR = {
    "fontsize": "11",
    "fontcolor": "#1e293b",
    "fontname": "Helvetica-Bold",
}


def build_diagram(outformat):
    out_path = os.path.join(OUTPUT_DIR, NAME)
    with Diagram(
        "Kubernetes Open WebUI + Bare-Metal RAMen AI",
        show=False,
        filename=out_path,
        outformat=outformat,
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        user = User("Client Browser\n(HTTPS)")
        cf_edge = Cloudflare("Cloudflare Edge\n(Secure Public Ingress)")

        with Cluster("Physical Host (Bare-Metal)", graph_attr={"bgcolor": "#f8fafc", "pencolor": "#64748b", "fontsize": "15"}):
            with Cluster("Kubernetes Cluster - Namespace: ai", graph_attr={"bgcolor": "#ffffff", "pencolor": "#3b82f6", "fontsize": "13"}):
                tunnel = Deployment("cloudflared\n(Outbound QUIC)")
                webui_svc = Service("openwebui-service\n(Port 8080)")
                webui_pod = Pod("openwebui\n(Web Container)")
                webui_pvc = PersistentVolumeClaim("openwebui-pvc\n(Persistent DB)")

                tunnel >> Edge(color="#0284c7", label="internal proxy\n ") >> webui_svc
                webui_svc >> Edge(color="#0284c7") >> webui_pod
                webui_pod >> Edge(color="#64748b", style="dashed", label="persists\n ") >> webui_pvc

            with Cluster("Bare-Metal AI Runtime", graph_attr={"bgcolor": "#fef3c7", "pencolor": "#f59e0b", "fontsize": "13"}):
                firewall = LinuxGeneral("Host Firewall\n(Port 8090 Allowed)")
                ramen_daemon = Rack("RAMen Daemon\n(Context Engine :8090)")
                llama_engine = Pod("llama-server\n(Quantized GGUF / 2048 ctx)")
                ssd_cache = Storage("SSD Storage\n(Session KV-Cache)")

                webui_pod >> Edge(color="#ea580c", style="bold", label="OpenAI API Protocol (:8090/v1)\n ") >> firewall
                firewall >> Edge(color="#ea580c") >> ramen_daemon
                ramen_daemon >> Edge(color="#ea580c", label="manages slots\n ") >> llama_engine
                ramen_daemon >> Edge(color="#d97706", style="dashed", label="zero-recompute KV cache swap\n ") >> ssd_cache

        user >> Edge(color="#7c3aed", style="bold", label="Public Access\n ") >> cf_edge
        cf_edge >> Edge(color="#0284c7", style="bold", label="Tunnel Ingress\n ") >> tunnel


# --- Animation Engine ---
def parse_svg_paths(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    tx, ty = 0.0, 0.0
    for g in root.iter("{http://www.w3.org/2000/svg}g"):
        if g.attrib.get("id") == "graph0":
            transform = g.attrib.get("transform", "")
            m = re.search(r"translate\(([-0-9.]+)\s+([-0-9.]+)\)", transform)
            if m:
                tx, ty = float(m.group(1)), float(m.group(2))
            break

    viewbox = root.attrib.get("viewBox", "0 0 1000 1000").split()
    vb_w, vb_h = float(viewbox[2]), float(viewbox[3])

    edges = []
    for g in root.iter("{http://www.w3.org/2000/svg}g"):
        if g.attrib.get("class") == "edge":
            title = g.find("{http://www.w3.org/2000/svg}title")
            path = g.find("{http://www.w3.org/2000/svg}path")
            if path is not None:
                d = path.attrib.get("d", "")
                stroke = path.attrib.get("stroke", "#2563eb")
                edges.append({
                    "title": title.text if title is not None else "",
                    "d": d,
                    "color": stroke,
                })
    return edges, tx, ty, vb_w, vb_h


def parse_bezier(d):
    tokens = re.findall(r"([A-Za-z])|(-?[0-9]+\.?[0-9]*)", d)
    cmd = ""
    coords = []
    segments = []
    current_pt = (0.0, 0.0)
    for c, val in tokens:
        if c:
            cmd = c
            coords = []
        else:
            coords.append(float(val))
            if cmd == "M" and len(coords) == 2:
                current_pt = (coords[0], coords[1])
                coords = []
            elif cmd == "C" and len(coords) == 6:
                p0 = current_pt
                p1 = (coords[0], coords[1])
                p2 = (coords[2], coords[3])
                p3 = (coords[4], coords[5])
                segments.append((p0, p1, p2, p3))
                current_pt = p3
                coords = []
    return segments


def sample_bezier(p0, p1, p2, p3, num=15):
    pts = []
    for i in range(num + 1):
        u = i / num
        mu = 1 - u
        x = (mu**3) * p0[0] + 3 * (mu**2) * u * p1[0] + 3 * mu * (u**2) * p2[0] + (u**3) * p3[0]
        y = (mu**3) * p0[1] + 3 * (mu**2) * u * p1[1] + 3 * mu * (u**2) * p2[1] + (u**3) * p3[1]
        pts.append((x, y))
    return pts


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        return tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))
    return (37, 99, 235)


def render_gif_from_diagram(target_width=1760):
    png_path = os.path.join(OUTPUT_DIR, f"{NAME}.png")
    svg_path = os.path.join(OUTPUT_DIR, f"{NAME}.svg")
    gif_path = os.path.join(OUTPUT_DIR, f"{NAME}.gif")

    edges, tx, ty, vb_w, vb_h = parse_svg_paths(svg_path)
    base_img = Image.open(png_path).convert("RGBA")

    scale_factor = target_width / base_img.width
    target_height = int(base_img.height * scale_factor)
    base_resized = base_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    sx = (base_img.width / vb_w) * scale_factor
    sy = (base_img.height / vb_h) * scale_factor

    # Extract text bounding boxes in scaled pixel space to prevent pulse overlap
    tree = ET.parse(svg_path)
    root = tree.getroot()
    text_boxes = []
    for el in root.iter("{http://www.w3.org/2000/svg}text"):
        raw_x = float(el.attrib.get("x", "0"))
        raw_y = float(el.attrib.get("y", "0"))
        fs = float(el.attrib.get("font-size", "11"))
        t_str = el.text or ""
        if not t_str.strip():
            continue
        w_svg = len(t_str) * (fs * 0.58)
        h_svg = fs * 1.1
        px = (raw_x + tx) * sx
        py = (raw_y + ty) * sy
        pw = w_svg * sx
        ph = h_svg * sy
        buf = 12
        text_boxes.append((px - pw / 2 - buf, py - ph * 0.85 - buf, px + pw / 2 + buf, py + ph * 0.25 + buf))

    def get_bubble_alpha(px, py, fade_zone=16.0):
        min_d = 999999.0
        for x0, y0, x1, y1 in text_boxes:
            dx = max(0.0, x0 - px, px - x1)
            dy = max(0.0, y0 - py, py - y1)
            if dx == 0.0 and dy == 0.0:
                return 0.0
            d = (dx * dx + dy * dy) ** 0.5
            if d < min_d:
                min_d = d
                if min_d < 1.0:
                    return 0.0
        if min_d >= fade_zone:
            return 1.0
        return min_d / fade_zone

    # Detect dark text pixels in base image to preserve them strictly on top of pulses
    base_arr = np.array(base_resized)
    is_text_pixel = (base_arr[:, :, 0] < 80) & (base_arr[:, :, 1] < 80) & (base_arr[:, :, 2] < 80) & (base_arr[:, :, 3] > 200)

    edge_polylines = []
    for edge in edges:
        segments = parse_bezier(edge["d"])
        pts = []
        for p0, p1, p2, p3 in segments:
            pts.extend(sample_bezier(p0, p1, p2, p3))
        pixel_pts = [((x + tx) * sx, (ty + y) * sy) for x, y in pts]
        if pixel_pts:
            edge_polylines.append({
                "points": pixel_pts,
                "color": hex_to_rgb(edge["color"]),
            })

    total_frames = 20
    rgba_frames = []
    for frame_idx in range(total_frames):
        t = frame_idx / total_frames
        frame = base_resized.copy()
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for poly in edge_polylines:
            pts = poly["points"]
            if len(pts) < 2:
                continue
            color = poly["color"]
            for offset in [0.0, 0.5]:
                progress = (t + offset) % 1.0
                idx_float = progress * (len(pts) - 1)
                i0 = int(idx_float)
                i1 = min(i0 + 1, len(pts) - 1)
                frac = idx_float - i0
                x = pts[i0][0] + frac * (pts[i1][0] - pts[i0][0])
                y = pts[i0][1] + frac * (pts[i1][1] - pts[i0][1])

                alpha = get_bubble_alpha(x, y)
                if alpha > 0.05:
                    a_outer = int(80 * alpha)
                    a_mid = int(200 * alpha)
                    a_core = int(255 * alpha)
                    draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(color[0], color[1], color[2], a_outer))
                    draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(color[0], color[1], color[2], a_mid))
                    draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255, a_core))

        frame = Image.alpha_composite(frame, overlay)
        frame_arr = np.array(frame)
        frame_arr[is_text_pixel] = base_arr[is_text_pixel]
        rgba_frames.append(Image.fromarray(frame_arr))

    # Quantize with MEDIANCUT and dither=NONE for sharp backgrounds and text
    base_palette = rgba_frames[0].convert("RGB").quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )

    p_frames = [
        f.convert("RGB").quantize(palette=base_palette, dither=Image.Dither.NONE)
        for f in rgba_frames
    ]

    p_frames[0].save(
        gif_path,
        save_all=True,
        append_images=p_frames[1:],
        duration=70,
        loop=0,
        optimize=True,
    )
    print(f"Generated GIF: {gif_path}")


if __name__ == "__main__":
    print("Generating PNG and SVG diagrams...")
    build_diagram("png")
    build_diagram("svg")
    print("Rendering animated GIF...")
    render_gif_from_diagram()
    # Clean up SVG
    svg_p = os.path.join(OUTPUT_DIR, f"{NAME}.svg")
    if os.path.exists(svg_p):
        os.remove(svg_p)
    print("Done!")
