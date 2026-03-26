<div align="center">

# 📊 Elastic IOPS Monitor

**Real-time IOPS and MB/s monitoring for Elasticsearch hot-tier nodes**

**Monitoramento em tempo real de IOPS e MB/s para nós hot do Elasticsearch**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-7.x%20%7C%208.x%20%7C%209.x-005571?logo=elasticsearch&logoColor=white)](https://elastic.co)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?logo=windows&logoColor=white)](https://github.com)

<img src="https://img.shields.io/badge/No%20extra%20dependencies-only%20requests-orange" />

</div>

---

> **🇧🇷 Português** · [🇺🇸 English](#-english)

---

## 🇧🇷 Português

### ✨ O que é

Script Python leve que monitora **IOPS** (operações de I/O por segundo) e **throughput em MB/s** dos nós *hot tier* de um cluster Elasticsearch — em tempo real no terminal ou como relatório HTML interativo gerado a partir de uma coleta por tempo determinado.

Não requer Stack Monitoring habilitado, agentes externos ou bibliotecas pesadas — apenas `requests`.

---

### 🚀 Como usar

#### 1. Pré-requisitos

```bash
python --version   # 3.8 ou superior
pip install requests
```

#### 2. Configuração

```bash
# Clone o repositório
git clone https://github.com/ggianini-elastic/elastic-iops-monitor.git
cd elastic-iops-monitor

# Copie e edite o arquivo de configuração
cp .env.example .env
```

Abra `.env` e preencha com os dados do seu cluster:

```env
ES_HOST=https://seu-cluster.es.regiao.cloud.es.io
ES_API_KEY=SUA_API_KEY_AQUI
```

> 💡 **Permissões mínimas da API Key:** `cluster:monitor/nodes/stats`

#### 3. Executar

**Monitor contínuo** — atualiza a tabela a cada ciclo:
```bash
python monitor_iops.py
```

**Relatório HTML** — coleta por N minutos e gera arquivo com gráficos:
```bash
python monitor_iops.py --report 10m   # 10 minutos
python monitor_iops.py --report 1h    # 1 hora
python monitor_iops.py --report 30s   # 30 segundos (teste rápido)
```

O relatório abre automaticamente no browser ao terminar.
Pressione **Ctrl+C** a qualquer momento para interromper e gerar o relatório com os dados coletados até então.

---

### 📋 Modos de uso

| Modo | Comando | Descrição |
|------|---------|-----------|
| 🔄 Monitor | `python monitor_iops.py` | Tabela atualizada em loop no terminal |
| 📈 Relatório | `python monitor_iops.py --report 10m` | HTML com gráficos Chart.js |
| 🔧 .env custom | `python monitor_iops.py /path/.env` | Aponta para arquivo de configuração alternativo |

---

### ⚙️ Configuração completa (`.env`)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ES_HOST` | — | URL do cluster Elasticsearch |
| `ES_API_KEY` | — | API Key para autenticação *(preferido)* |
| `ES_USER` | — | Usuário *(alternativa à API Key)* |
| `ES_PASSWORD` | — | Senha *(alternativa à API Key)* |
| `SAMPLE_INTERVAL` | `10` | Segundos entre as duas coletas para calcular o delta |
| `REFRESH_INTERVAL` | `30` | Segundos entre ciclos no modo monitor (`0` = executa uma vez) |
| `HOT_ROLES` | `data_hot` | Roles que identificam nós hot (separados por vírgula) |
| `REPORT_DURATION` | `10m` | Duração padrão do relatório quando omitido no comando |

---

### 📊 Saída — Monitor terminal

```
════════════════════════════════════════════════════════════════════════
 Elastic IOPS Monitor  │  2026-03-26 13:15:25  │  amostra: 10s
════════════════════════════════════════════════════════════════════════
 Nó                           R-IOPS   W-IOPS     IOPS   R-MB/s  W-MB/s    MB/s
 ────────────────────────────────────────────────────────────────────────
 instance-0000000000               0      508      508      0.0     1.8     1.8
 instance-0000000001               0    1,047    1,047      0.0     3.7     3.7
 ────────────────────────────────────────────────────────────────────────
 TOTAL (2 nós)                     0    1,555    1,555      0.0     5.5     5.5
════════════════════════════════════════════════════════════════════════
```

Cores automáticas: 🟢 normal · 🟡 atenção · 🔴 crítico

---

### 📈 Saída — Relatório HTML

O relatório gerado (`iops_report_YYYYMMDD_HHMMSS.html`) contém:

- **6 gráficos interativos** (Chart.js): IOPS total, Read IOPS, Write IOPS, MB/s total, Read MB/s, Write MB/s
- **Linha por nó** + linha TOTAL no mesmo gráfico
- **Tabelas de estatísticas**: mínimo, média, p95, máximo por nó
- Arquivo HTML **autossuficiente** — pode ser compartilhado por e-mail ou salvo

---

### 🔒 Segurança

- O arquivo `.env` está no `.gitignore` — **nunca será comitado**
- Somente `.env.example` (com placeholders) é versionado
- A API Key precisa apenas de permissão de leitura: `cluster:monitor/nodes/stats`

---

### 🛠️ Dependências

| Pacote | Versão | Uso |
|--------|--------|-----|
| `requests` | ≥ 2.20 | Chamadas à API do Elasticsearch |

Apenas biblioteca padrão do Python para todo o resto (`os`, `sys`, `signal`, `json`, `webbrowser`).

---

### 🤝 Contribuindo

Pull requests são bem-vindos. Para mudanças grandes, abra uma issue primeiro para discutir o que você gostaria de mudar.

---

---

## 🇺🇸 English

### ✨ What it is

A lightweight Python script that monitors **IOPS** (I/O operations per second) and **throughput in MB/s** for Elasticsearch *hot-tier* nodes — either as a live terminal table or as an interactive HTML report generated from a timed collection run.

No Stack Monitoring required, no external agents, no heavy dependencies — just `requests`.

---

### 🚀 How to use

#### 1. Prerequisites

```bash
python --version   # 3.8 or higher
pip install requests
```

#### 2. Setup

```bash
# Clone the repository
git clone https://github.com/ggianini-elastic/elastic-iops-monitor.git
cd elastic-iops-monitor

# Copy and edit the configuration file
cp .env.example .env
```

Open `.env` and fill in your cluster details:

```env
ES_HOST=https://your-cluster.es.region.cloud.es.io
ES_API_KEY=YOUR_API_KEY_HERE
```

> 💡 **Minimum API Key permissions:** `cluster:monitor/nodes/stats`

#### 3. Run

**Live monitor** — refreshes the table every cycle:
```bash
python monitor_iops.py
```

**HTML report** — collects for N minutes then generates a chart file:
```bash
python monitor_iops.py --report 10m   # 10 minutes
python monitor_iops.py --report 1h    # 1 hour
python monitor_iops.py --report 30s   # 30 seconds (quick test)
```

The report opens automatically in your browser when done.
Press **Ctrl+C** at any time to stop and generate the report with data collected so far.

---

### 📋 Usage modes

| Mode | Command | Description |
|------|---------|-------------|
| 🔄 Monitor | `python monitor_iops.py` | Live table refreshed in a loop |
| 📈 Report | `python monitor_iops.py --report 10m` | HTML file with Chart.js graphs |
| 🔧 Custom .env | `python monitor_iops.py /path/.env` | Point to an alternative config file |

---

### ⚙️ Full configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ES_HOST` | — | Elasticsearch cluster URL |
| `ES_API_KEY` | — | API Key for authentication *(preferred)* |
| `ES_USER` | — | Username *(alternative to API Key)* |
| `ES_PASSWORD` | — | Password *(alternative to API Key)* |
| `SAMPLE_INTERVAL` | `10` | Seconds between the two snapshots used to compute the delta |
| `REFRESH_INTERVAL` | `30` | Seconds between cycles in monitor mode (`0` = run once) |
| `HOT_ROLES` | `data_hot` | Comma-separated roles that identify hot nodes |
| `REPORT_DURATION` | `10m` | Default report duration when omitted from the command |

---

### 📊 Output — Terminal monitor

```
════════════════════════════════════════════════════════════════════════
 Elastic IOPS Monitor  │  2026-03-26 13:15:25  │  sample: 10s
════════════════════════════════════════════════════════════════════════
 Node                          R-IOPS   W-IOPS     IOPS   R-MB/s  W-MB/s    MB/s
 ────────────────────────────────────────────────────────────────────────
 instance-0000000000               0      508      508      0.0     1.8     1.8
 instance-0000000001               0    1,047    1,047      0.0     3.7     3.7
 ────────────────────────────────────────────────────────────────────────
 TOTAL (2 nodes)                   0    1,555    1,555      0.0     5.5     5.5
════════════════════════════════════════════════════════════════════════
```

Automatic color coding: 🟢 normal · 🟡 warning · 🔴 critical

---

### 📈 Output — HTML report

The generated report (`iops_report_YYYYMMDD_HHMMSS.html`) includes:

- **6 interactive charts** (Chart.js): total IOPS, Read IOPS, Write IOPS, total MB/s, Read MB/s, Write MB/s
- **One line per node** + TOTAL line on the same chart
- **Statistics tables**: min, avg, p95, max per node
- **Self-contained HTML file** — shareable by email or easy to save

---

### 🔒 Security

- The `.env` file is in `.gitignore` — **it will never be committed**
- Only `.env.example` (with placeholders) is versioned
- The API Key only needs read permission: `cluster:monitor/nodes/stats`

---

### 🛠️ Dependencies

| Package | Version | Usage |
|---------|---------|-------|
| `requests` | ≥ 2.20 | Elasticsearch API calls |

Standard Python library only for everything else (`os`, `sys`, `signal`, `json`, `webbrowser`).

---

### 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

### 📄 License

[MIT](LICENSE)
