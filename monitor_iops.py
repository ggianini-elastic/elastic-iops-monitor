#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_iops.py — Monitor e relatório de IOPS/MB/s para nós hot do Elasticsearch.

Modos:
    python monitor_iops.py                   # monitor contínuo (lê .env)
    python monitor_iops.py --report 10m      # coleta por 10 min → HTML
    python monitor_iops.py --report 1h       # coleta por 1 hora → HTML
    python monitor_iops.py /path/.env        # arquivo .env customizado

Duração aceita: <N>s  <N>m  <N>h  (ex: 30s, 5m, 2h)

Dependências: apenas requests (pip install requests)
"""

import os
import sys
import time
import signal
import json
import webbrowser
from datetime import datetime
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# ─── Encoding: UTF-8 garantido em qualquer plataforma ─────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7
        )
    except Exception:
        pass

# ─── Cores ANSI ───────────────────────────────────────────────────────────────
ANSI = (
    sys.stdout.isatty()
    and os.environ.get("NO_COLOR", "") == ""
    and os.environ.get("TERM", "") != "dumb"
)

def c(code, text):  return f"\033[{code}m{text}\033[0m" if ANSI else text
BOLD   = lambda t: c("1",  t)
CYAN   = lambda t: c("96", t)
GREEN  = lambda t: c("92", t)
YELLOW = lambda t: c("93", t)
RED    = lambda t: c("91", t)
DIM    = lambda t: c("2",  t)


# ─── Parser de .env ───────────────────────────────────────────────────────────

def load_env(path: str) -> dict:
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.split("#")[0].strip()
    for key in list(env.keys()):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def parse_duration(s: str) -> float:
    """Converte '10m', '1h', '30s' em segundos (float)."""
    s = s.strip().lower()
    if s.endswith("h"):   return float(s[:-1]) * 3600
    if s.endswith("m"):   return float(s[:-1]) * 60
    if s.endswith("s"):   return float(s[:-1])
    return float(s)


# ─── Autenticação ─────────────────────────────────────────────────────────────

def build_session(cfg: dict) -> requests.Session:
    s = requests.Session()
    api_key = cfg.get("ES_API_KEY", "").strip()
    user    = cfg.get("ES_USER",    "").strip()
    passwd  = cfg.get("ES_PASSWORD","").strip()
    if api_key:
        s.headers["Authorization"] = f"ApiKey {api_key}"
    elif user and passwd:
        s.auth = HTTPBasicAuth(user, passwd)
    else:
        print(RED("ERRO: defina ES_API_KEY ou ES_USER + ES_PASSWORD no .env"))
        sys.exit(1)
    s.headers["Content-Type"] = "application/json"
    return s


# ─── Coleta de métricas ───────────────────────────────────────────────────────

def fetch_fs_stats(session: requests.Session, host: str) -> dict:
    url = f"{host.rstrip('/')}/_nodes/stats/fs"
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Falha de conexão: {e}")
    except requests.exceptions.HTTPError:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

    result = {}
    for nid, node in r.json().get("nodes", {}).items():
        io = node.get("fs", {}).get("io_stats", {}).get("total", {})
        result[nid] = {
            "name":  node.get("name", nid),
            "roles": node.get("roles", []),
            "r_ops": io.get("read_operations",  0),
            "w_ops": io.get("write_operations", 0),
            "r_kb":  io.get("read_kilobytes",   0),
            "w_kb":  io.get("write_kilobytes",  0),
        }
    return result


def filter_hot_nodes(stats: dict, hot_roles: list) -> dict:
    role_set = set(hot_roles)
    return {nid: n for nid, n in stats.items() if role_set & set(n["roles"])}


def compute_delta(snap1: dict, snap2: dict, interval: float) -> list:
    rows = []
    for nid, n2 in snap2.items():
        if nid not in snap1:
            continue
        n1 = snap1[nid]
        d_r_ops = max(0, n2["r_ops"] - n1["r_ops"])
        d_w_ops = max(0, n2["w_ops"] - n1["w_ops"])
        d_r_kb  = max(0, n2["r_kb"]  - n1["r_kb"])
        d_w_kb  = max(0, n2["w_kb"]  - n1["w_kb"])
        rows.append({
            "name":     n2["name"],
            "r_iops":   d_r_ops / interval,
            "w_iops":   d_w_ops / interval,
            "tot_iops": (d_r_ops + d_w_ops) / interval,
            "r_mbs":    d_r_kb  / 1024 / interval,
            "w_mbs":    d_w_kb  / 1024 / interval,
            "tot_mbs":  (d_r_kb + d_w_kb) / 1024 / interval,
        })
    rows.sort(key=lambda x: x["name"])
    return rows


# ─── Tabela no terminal ───────────────────────────────────────────────────────

COL_W  = 30
NUM_W  = 10
LINE_W = COL_W + NUM_W * 6 + 2
HDR    = (f"{'Nó':<{COL_W}}"
          f"{'R-IOPS':>{NUM_W}}{'W-IOPS':>{NUM_W}}{'IOPS':>{NUM_W}}"
          f"{'R-MB/s':>{NUM_W}}{'W-MB/s':>{NUM_W}}{'MB/s':>{NUM_W}}")

def _ic(v): t = f"{v:>{NUM_W},.0f}"; return GREEN(t) if v<5000 else YELLOW(t) if v<20000 else RED(t)
def _mc(v): t = f"{v:>{NUM_W}.1f}"; return GREEN(t) if v<100  else YELLOW(t) if v<300   else RED(t)

def render_row(row, highlight=False):
    name = (row["name"][:COL_W-1]).ljust(COL_W-1) + " "
    if highlight: name = BOLD(name)
    return name + _ic(row["r_iops"]) + _ic(row["w_iops"]) + _ic(row["tot_iops"]) \
                + _mc(row["r_mbs"])  + _mc(row["w_mbs"])  + _mc(row["tot_mbs"])

def print_table(rows, cfg, interval):
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host = cfg.get("ES_HOST","").replace("https://","")
    sep2 = "═" * LINE_W
    sep1 = "─" * LINE_W
    print()
    print(CYAN(sep2))
    print(BOLD(" Elastic IOPS Monitor") + f"  │  {now}" + DIM(f"  │  amostra: {interval:.0f}s  │  {host}"))
    print(CYAN(sep2))
    print(DIM(" " + HDR))
    print(DIM(" " + sep1))
    if not rows:
        print(YELLOW("  Nenhum nó hot encontrado."))
    else:
        for row in rows: print(" " + render_row(row))
        print(DIM(" " + sep1))
        tot = {"name": f"TOTAL ({len(rows)} nós)",
               "r_iops": sum(r["r_iops"] for r in rows), "w_iops": sum(r["w_iops"] for r in rows),
               "tot_iops": sum(r["tot_iops"] for r in rows), "r_mbs": sum(r["r_mbs"] for r in rows),
               "w_mbs": sum(r["w_mbs"] for r in rows), "tot_mbs": sum(r["tot_mbs"] for r in rows)}
        print(" " + render_row(tot, highlight=True))
    print(CYAN(sep2))


# ─── Modo RELATÓRIO ───────────────────────────────────────────────────────────

def collect_report_data(session, cfg, hot_roles, sample_interval, duration_secs):
    """
    Coleta amostras de IOPS/MB/s durante `duration_secs` segundos.
    Retorna lista de pontos: [{ts, nodes: [{name, r_iops, w_iops, ...}]}]
    """
    host   = cfg["ES_HOST"]
    points = []
    end_at = time.time() + duration_secs
    snap1  = None

    total   = int(duration_secs / sample_interval)
    current = 0

    print(CYAN(f"\n  Coletando dados por {duration_secs/60:.1f} min "
               f"(~{total} amostras a cada {sample_interval:.0f}s)"))
    print(DIM("  Ctrl+C encerra e gera o relatório com os dados coletados até agora.\n"))

    while time.time() < end_at:
        try:
            raw  = fetch_fs_stats(session, host)
            snap = filter_hot_nodes(raw, hot_roles)
        except RuntimeError as e:
            print(RED(f"  [{datetime.now().strftime('%H:%M:%S')}] Erro: {e}"))
            time.sleep(sample_interval)
            continue

        if snap1 is not None:
            rows = compute_delta(snap1, snap, sample_interval)
            points.append({
                "ts":    datetime.now().strftime("%H:%M:%S"),
                "nodes": rows,
            })
            current += 1
            remaining = max(0, end_at - time.time())
            bar_filled = int(40 * current / max(total, 1))
            bar = "█" * bar_filled + "░" * (40 - bar_filled)
            tot_iops = sum(r["tot_iops"] for r in rows)
            tot_mbs  = sum(r["tot_mbs"]  for r in rows)
            print(f"  [{bar}] {current}/{total}  "
                  f"IOPS={tot_iops:,.0f}  MB/s={tot_mbs:.1f}  "
                  f"resta {remaining:.0f}s   ", end="\r")

        snap1 = snap
        time.sleep(sample_interval)

    print()
    return points


def generate_html_report(points, cfg, hot_roles, sample_interval, duration_secs):
    """Gera arquivo HTML com gráficos Chart.js de IOPS e MB/s ao longo do tempo."""
    if not points:
        print(RED("  Nenhum dado coletado — relatório não gerado."))
        return None

    host      = cfg.get("ES_HOST","").replace("https://","")
    now_str   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = Path(__file__).parent / f"iops_report_{file_ts}.html"

    # ── Extrai nomes únicos de nós ─────────────────────────────────────────
    node_names = []
    for p in points:
        for n in p["nodes"]:
            if n["name"] not in node_names:
                node_names.append(n["name"])
    node_names.sort()

    labels = [p["ts"] for p in points]

    # ── Paleta de cores Elastic ────────────────────────────────────────────
    PALETTE = [
        "#1BA9F5", "#F04E98", "#00BFB3", "#FEC514",
        "#F86B00", "#6092C0", "#54B399", "#D36086",
    ]

    def series(metric):
        """Gera datasets Chart.js para cada nó + TOTAL."""
        datasets = []
        for i, name in enumerate(node_names):
            color = PALETTE[i % len(PALETTE)]
            data  = []
            for p in points:
                val = next((r[metric] for r in p["nodes"] if r["name"] == name), None)
                data.append(round(val, 2) if val is not None else None)
            datasets.append({
                "label":           name,
                "data":            data,
                "borderColor":     color,
                "backgroundColor": color + "22",
                "borderWidth":     2,
                "pointRadius":     2,
                "tension":         0.3,
                "fill":            False,
                "spanGaps":        True,
            })
        # TOTAL
        if len(node_names) > 1:
            total_data = []
            for p in points:
                total_data.append(round(sum(r[metric] for r in p["nodes"]), 2))
            datasets.append({
                "label":           "TOTAL",
                "data":            total_data,
                "borderColor":     "#fff",
                "backgroundColor": "#ffffff22",
                "borderWidth":     2,
                "borderDash":      [6, 3],
                "pointRadius":     0,
                "tension":         0.3,
                "fill":            False,
                "spanGaps":        True,
            })
        return datasets

    # ── Estatísticas resumo ────────────────────────────────────────────────
    def stats_row(metric):
        rows = []
        for name in node_names:
            vals = [r[metric] for p in points for r in p["nodes"] if r["name"] == name]
            if vals:
                rows.append({
                    "name": name,
                    "min":  min(vals),
                    "avg":  sum(vals)/len(vals),
                    "max":  max(vals),
                    "p95":  sorted(vals)[int(len(vals)*0.95)],
                })
        return rows

    iops_rows = stats_row("tot_iops")
    mbs_rows  = stats_row("tot_mbs")

    def fmt_iops(v): return f"{v:,.0f}"
    def fmt_mbs(v):  return f"{v:.2f}"

    def stats_table_html(rows, fmt, unit):
        if not rows: return "<p>Sem dados.</p>"
        html = f"""<table>
<tr><th>Nó</th><th>Mín ({unit})</th><th>Méd ({unit})</th>
    <th>p95 ({unit})</th><th>Máx ({unit})</th></tr>"""
        for r in rows:
            html += (f"<tr><td>{r['name']}</td>"
                     f"<td>{fmt(r['min'])}</td><td>{fmt(r['avg'])}</td>"
                     f"<td>{fmt(r['p95'])}</td><td>{fmt(r['max'])}</td></tr>")
        html += "</table>"
        return html

    # ── Serializa datasets como JSON ───────────────────────────────────────
    iops_datasets  = json.dumps(series("tot_iops"), ensure_ascii=False)
    r_iops_datasets = json.dumps(series("r_iops"), ensure_ascii=False)
    w_iops_datasets = json.dumps(series("w_iops"), ensure_ascii=False)
    mbs_datasets   = json.dumps(series("tot_mbs"),  ensure_ascii=False)
    r_mbs_datasets = json.dumps(series("r_mbs"),    ensure_ascii=False)
    w_mbs_datasets = json.dumps(series("w_mbs"),    ensure_ascii=False)
    labels_json    = json.dumps(labels)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Elastic IOPS Report — {now_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    font-size: 14px;
    padding: 24px;
  }}
  h1 {{ font-size: 22px; color: #fff; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; color: #58a6ff; margin: 28px 0 10px; border-bottom: 1px solid #21262d; padding-bottom: 6px; }}
  .meta {{ color: #8b949e; font-size: 12px; margin-bottom: 24px; }}
  .meta span {{ margin-right: 20px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px;
  }}
  .card-title {{ font-size: 13px; color: #8b949e; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .5px; }}
  canvas {{ max-height: 260px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-top: 8px;
  }}
  th, td {{ padding: 8px 12px; text-align: right; border-bottom: 1px solid #21262d; }}
  th {{ color: #8b949e; font-weight: 500; text-transform: uppercase; font-size: 11px; }}
  td:first-child, th:first-child {{ text-align: left; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    background: #1f6feb33;
    color: #58a6ff;
    border: 1px solid #1f6feb55;
  }}
</style>
</head>
<body>

<h1>Elastic IOPS Report</h1>
<div class="meta">
  <span>🖥  {host}</span>
  <span>📅 {now_str}</span>
  <span>⏱ Duração: {duration_secs/60:.1f} min</span>
  <span>📊 {len(points)} amostras a cada {sample_interval:.0f}s</span>
  <span>🔥 Roles: <span class="badge">{', '.join(hot_roles)}</span></span>
  <span>💾 Nós: {', '.join(f'<span class="badge">{n}</span>' for n in node_names)}</span>
</div>

<h2>IOPS Total (leitura + escrita)</h2>
<div class="card">
  <canvas id="chartIops"></canvas>
</div>

<h2>IOPS por Direção</h2>
<div class="grid-2">
  <div class="card">
    <div class="card-title">Read IOPS</div>
    <canvas id="chartRiops"></canvas>
  </div>
  <div class="card">
    <div class="card-title">Write IOPS</div>
    <canvas id="chartWiops"></canvas>
  </div>
</div>

<h2>Throughput MB/s Total (leitura + escrita)</h2>
<div class="card">
  <canvas id="chartMbs"></canvas>
</div>

<h2>Throughput por Direção</h2>
<div class="grid-2">
  <div class="card">
    <div class="card-title">Read MB/s</div>
    <canvas id="chartRmbs"></canvas>
  </div>
  <div class="card">
    <div class="card-title">Write MB/s</div>
    <canvas id="chartWmbs"></canvas>
  </div>
</div>

<h2>Estatísticas de IOPS Total por Nó</h2>
<div class="card">
{stats_table_html(iops_rows, fmt_iops, "IOPS")}
</div>

<h2>Estatísticas de Throughput Total por Nó</h2>
<div class="card">
{stats_table_html(mbs_rows, fmt_mbs, "MB/s")}
</div>

<script>
const labels = {labels_json};

const chartDefaults = {{
  type: "line",
  options: {{
    responsive: true,
    animation: false,
    interaction: {{ mode: "index", intersect: false }},
    plugins: {{
      legend: {{ labels: {{ color: "#8b949e", boxWidth: 12, font: {{ size: 12 }} }} }},
      tooltip: {{ backgroundColor: "#161b22", borderColor: "#21262d", borderWidth: 1,
                  titleColor: "#c9d1d9", bodyColor: "#8b949e" }}
    }},
    scales: {{
      x: {{ ticks: {{ color: "#8b949e", maxTicksLimit: 12, font: {{ size: 11 }} }},
            grid:  {{ color: "#21262d" }} }},
      y: {{ ticks: {{ color: "#8b949e", font: {{ size: 11 }} }},
            grid:  {{ color: "#21262d" }}, beginAtZero: true }}
    }}
  }}
}};

function mkChart(id, datasets, yLabel) {{
  const cfg = JSON.parse(JSON.stringify(chartDefaults));
  cfg.data = {{ labels, datasets }};
  cfg.options.scales.y.title = {{ display: true, text: yLabel, color: "#8b949e", font: {{ size: 11 }} }};
  return new Chart(document.getElementById(id), cfg);
}}

mkChart("chartIops",  {iops_datasets},   "IOPS");
mkChart("chartRiops", {r_iops_datasets}, "IOPS");
mkChart("chartWiops", {w_iops_datasets}, "IOPS");
mkChart("chartMbs",   {mbs_datasets},    "MB/s");
mkChart("chartRmbs",  {r_mbs_datasets},  "MB/s");
mkChart("chartWmbs",  {w_mbs_datasets},  "MB/s");
</script>
</body>
</html>"""

    out_file.write_text(html, encoding="utf-8")
    return str(out_file)


# ─── Loop do monitor contínuo ─────────────────────────────────────────────────

def run_once(session, cfg, hot_roles, interval):
    host = cfg["ES_HOST"]
    print(DIM(f"  [{datetime.now().strftime('%H:%M:%S')}] Coletando snapshot 1..."), end="\r")
    snap1 = filter_hot_nodes(fetch_fs_stats(session, host), hot_roles)

    if not snap1:
        print(YELLOW(f"\n  Nenhum nó com roles {hot_roles} encontrado."))
        for nid, n in fetch_fs_stats(session, host).items():
            print(f"    {n['name']}: {n['roles']}")
        return

    print(DIM(f"  [{datetime.now().strftime('%H:%M:%S')}] Aguardando {interval:.0f}s...      "), end="\r")
    time.sleep(interval)

    print(DIM(f"  [{datetime.now().strftime('%H:%M:%S')}] Coletando snapshot 2..."), end="\r")
    snap2 = filter_hot_nodes(fetch_fs_stats(session, host), hot_roles)
    print_table(compute_delta(snap1, snap2, interval), cfg, interval)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # ── Detecta modo --report ───────────────────────────────────────────────
    report_mode     = False
    report_duration = None
    env_path_arg    = None

    i = 0
    while i < len(args):
        if args[i] == "--report":
            report_mode = True
            if i + 1 < len(args) and not args[i+1].startswith("-"):
                report_duration = args[i+1]
                i += 1
            i += 1
        else:
            env_path_arg = args[i]
            i += 1

    env_path = env_path_arg or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(env_path):
        print(YELLOW(f"Aviso: .env não encontrado em {env_path} — usando variáveis de ambiente."))

    cfg = load_env(env_path)

    if not cfg.get("ES_HOST"):
        print(RED("ERRO: ES_HOST não definido."))
        sys.exit(1)

    sample_interval  = float(cfg.get("SAMPLE_INTERVAL",  "10"))
    refresh_interval = float(cfg.get("REFRESH_INTERVAL", "30"))
    hot_roles        = [r.strip() for r in cfg.get("HOT_ROLES", "data_hot").split(",") if r.strip()]
    session          = build_session(cfg)

    print()
    print(BOLD(CYAN("  Elastic IOPS Monitor")))
    print(DIM(f"  Host     : {cfg['ES_HOST']}"))
    print(DIM(f"  Hot roles: {', '.join(hot_roles)}"))

    # ── Modo RELATÓRIO ──────────────────────────────────────────────────────
    if report_mode:
        dur_str = report_duration or cfg.get("REPORT_DURATION", "10m")
        try:
            dur_secs = parse_duration(dur_str)
        except ValueError:
            print(RED(f"ERRO: duração inválida '{dur_str}'. Use: 30s, 5m, 1h"))
            sys.exit(1)

        print(DIM(f"  Modo     : relatório HTML ({dur_str})"))
        print(DIM(f"  Amostra  : {sample_interval:.0f}s"))

        points = []

        def _finish(*_):
            print(f"\n{YELLOW('  Interrompido — gerando relatório com dados coletados...')}")
            path = generate_html_report(points, cfg, hot_roles, sample_interval, dur_secs)
            if path:
                print(GREEN(f"\n  Relatório: {path}"))
                webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
            sys.exit(0)

        signal.signal(signal.SIGINT,  _finish)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _finish)

        try:
            points = collect_report_data(session, cfg, hot_roles, sample_interval, dur_secs)
        except RuntimeError as e:
            print(RED(f"  Erro na coleta: {e}"))

        path = generate_html_report(points, cfg, hot_roles, sample_interval, dur_secs)
        if path:
            print(GREEN(f"\n  Relatório gerado: {path}"))
            print(DIM("  Abrindo no browser..."))
            webbrowser.open(f"file:///{path.replace(os.sep, '/')}")

    # ── Modo MONITOR contínuo ───────────────────────────────────────────────
    else:
        print(DIM(f"  Amostra  : {sample_interval:.0f}s  |  Refresh: "
                  + ("única execução" if refresh_interval == 0 else f"{refresh_interval:.0f}s")))
        print(DIM("  Ctrl+C para sair\n"))
        print(DIM("  Dica: use --report 10m para gerar relatório HTML com gráficos."))

        def _sig(*_):
            print(f"\n{DIM('  Encerrando...')}\n")
            sys.exit(0)

        signal.signal(signal.SIGINT,  _sig)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sig)

        while True:
            try:
                run_once(session, cfg, hot_roles, sample_interval)
            except RuntimeError as e:
                print(RED(f"\n  Erro: {e}"))

            if refresh_interval == 0:
                break

            print(DIM(f"\n  Próxima leitura em {refresh_interval:.0f}s — Ctrl+C para sair"))
            time.sleep(refresh_interval)


if __name__ == "__main__":
    main()
