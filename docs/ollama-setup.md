# Using local models with Ollama

KIS can use a locally hosted [Ollama](https://ollama.com) as its LLM provider.
This is the cheapest way to run KIS — no API costs, data stays on your machine.

Ollama always runs **outside** the KIS stack. KIS is never shipped with an
Ollama container; you host Ollama yourself and KIS talks to it over HTTP. This
keeps KIS lean and lets each deployment use whatever hardware it has.

This guide covers the common case: **KIS in Docker + Ollama running natively on
the same machine** (laptop or workstation).

---

## 1. Install Ollama

Install Ollama natively (not in Docker) so it can use your GPU:

- **macOS:** `brew install ollama` or the app from [ollama.com](https://ollama.com/download)
- **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`
- **Windows:** installer from [ollama.com](https://ollama.com/download)

---

## 2. Make Ollama reachable from the KIS container

By default Ollama only listens on `127.0.0.1`, which the KIS Docker container
**cannot** reach (a container is a separate network host). Tell Ollama to listen
on all interfaces by setting `OLLAMA_HOST=0.0.0.0:11434`.

This is a one-time setup step and is standard practice for any Docker app that
talks to a host Ollama (Open WebUI, Open Notebook, etc. require the same).

| System | How |
| --- | --- |
| **macOS (app)** | `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"`, then restart Ollama |
| **macOS/Linux (manual)** | start with `OLLAMA_HOST=0.0.0.0:11434 ollama serve` |
| **Linux (systemd)** | `systemctl edit ollama.service` → add `Environment="OLLAMA_HOST=0.0.0.0:11434"`, then `systemctl restart ollama` |
| **Windows** | add a system env var `OLLAMA_HOST=0.0.0.0:11434`, then restart Ollama |

Verify it is reachable from the backend container:

```bash
docker exec kis-backend python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/version').read())"
```

---

## 3. Pull the models

KIS does not download models for you — pull them with Ollama first:

```bash
ollama pull qwen2.5:7b          # chat / RAG (minimum supported tier)
ollama pull nomic-embed-text    # embeddings (required for RAG)
```

**Model tiers.** KIS supports three tiers; the minimum is **Small (8B with a
32k context window)**. Tiny 8k-context models are not supported. What runs on
your machine depends on RAM:

| Tier | Example | Approx. RAM |
| --- | --- | --- |
| Small | `qwen2.5:7b` | ~6 GB |
| Mid | `qwen2.5:14b` | ~16 GB |
| Large | `qwen2.5:32b` | ~32 GB |

---

## 4. Register Ollama in KIS

In the KIS web app, go to **Admin → AI Settings** and add a provider:

- **Protocol:** `openai_compat`
- **Base URL:** `http://host.docker.internal:11434/v1` (note the `/v1` suffix)
- **API key:** leave empty — local endpoints need no key

KIS probes the endpoint automatically and discovers the installed models. Then
assign models to features under **Feature Routes** (chat, summary, embeddings,
etc.). Use the exact model name as shown by `ollama list`.

---

## Remote / server hosting

If Ollama runs on a separate server (e.g. a shared GPU box) instead of the same
machine, the only differences are:

- Still set `OLLAMA_HOST=0.0.0.0:11434` on that server, and make sure the port
  is reachable over the network.
- Use the server's address as the base URL: `http://<server-ip-or-domain>:11434/v1`.
- Leave the API key empty (Ollama does not use one).

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Probe fails / "connection refused" | Ollama not on `0.0.0.0` — see step 2. |
| Probe works but no models listed | Models not pulled — see step 3. |
| "Failed to send message" | Wrong model name in the feature route — match `ollama list` exactly. |
| Very slow responses | Model too large for available RAM, or Ollama running CPU-only (Docker on macOS has no GPU access — that's why Ollama must run natively). |
