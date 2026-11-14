#!/usr/bin/env python3
"""
Architecture Diagram for Hybrid Local AI Stack:
Kubernetes (Open WebUI) + Bare-Metal Host (RAMen AI & llama.cpp)
"""

import os
from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.saas.cdn import Cloudflare
from diagrams.k8s.compute import Deployment, Pod
from diagrams.k8s.network import Service, Endpoint
from diagrams.k8s.storage import PersistentVolumeClaim
from diagrams.generic.os import LinuxGeneral
from diagrams.generic.compute import Rack
from diagrams.generic.storage import Storage

DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(DIR, "docs", "architecture")

GRAPH_ATTR = {
    "fontsize": "18",
    "bgcolor": "#ffffff",
    "fontcolor": "#0f172a",
    "fontname": "Helvetica-Bold",
    "pad": "0.4",
    "splines": "spline",
    "nodesep": "0.6",
    "ranksep": "0.8",
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

with Diagram(
    "Hybrid Local AI Stack: Kubernetes Open WebUI + Bare-Metal RAMen AI",
    show=False,
    filename=OUTPUT_PATH,
    outformat="png",
    direction="LR",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    user = User("Client Browser\n(HTTPS)")
    cf_edge = Cloudflare("Cloudflare Edge\n(openwebui.homenode.online)")

    with Cluster("Physical Host: Fedora Linux (Intel i3-4160T, 16GB DDR3, 192.168.100.11)", graph_attr={"bgcolor": "#f8fafc", "pencolor": "#64748b", "fontsize": "15"}):
        with Cluster("Kubernetes Cluster (k3s) - Namespace: ai", graph_attr={"bgcolor": "#ffffff", "pencolor": "#3b82f6", "fontsize": "13"}):
            tunnel = Deployment("cloudflared\n(Outbound QUIC)")
            webui_svc = Service("openwebui-service\n(Port 8080)")
            webui_pod = Pod("openwebui\n(Web Container)")
            webui_pvc = PersistentVolumeClaim("openwebui-pvc\n(2Gi Chat DB)")
            ramen_ep = Endpoint("ramen-service\n(Bridge to 192.168.100.11:8090)")

            tunnel >> Edge(color="#0284c7", label="internal proxy") >> webui_svc
            webui_svc >> Edge(color="#0284c7") >> webui_pod
            webui_pod >> Edge(color="#64748b", style="dashed", label="persists") >> webui_pvc
            webui_pod >> Edge(color="#ea580c", label="OpenAI API (:8090)") >> ramen_ep

        with Cluster("Bare-Metal Host Runtime (Fedora 41)", graph_attr={"bgcolor": "#fef3c7", "pencolor": "#f59e0b", "fontsize": "13"}):
            firewall = LinuxGeneral("firewalld\n(Port 8090/TCP Allowed)")
            ramen_daemon = Rack("RAMen Daemon\n(Context Engine :8090)")
            llama_engine = Pod("llama-server\n(Qwen3-4B / 2048 ctx)")
            ssd_cache = Storage("SSD Session Store\n(~/.context-engine/sessions)")

            ramen_ep >> Edge(color="#ea580c", style="bold", label="TCP: 192.168.100.11:8090") >> firewall
            firewall >> Edge(color="#ea580c") >> ramen_daemon
            ramen_daemon >> Edge(color="#ea580c", label="manages slots") >> llama_engine
            ramen_daemon >> Edge(color="#d97706", style="dashed", label="zero-recompute KV cache swap") >> ssd_cache

    user >> Edge(color="#7c3aed", style="bold", label="Public Access") >> cf_edge
    cf_edge >> Edge(color="#0284c7", style="bold", label="Tunnel Ingress") >> tunnel
