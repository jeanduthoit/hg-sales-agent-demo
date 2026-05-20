# Web demo (Streamlit)

Hosted demo for evaluators: no terminal, HG URL configured server-side.

## Local run

```bash
cd seller_profile_agent
pip install -r requirements.txt
export HG_MCP_URL="https://…"   # or use ~/.cursor/mcp.json
streamlit run streamlit_app.py
```

From repo root:

```bash
npm run demo:web
```

## Streamlit Cloud

1. Push this repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → New app.
3. **Repository**: your fork; **Branch**: main.
4. **Main file path**: `seller_profile_agent/streamlit_app.py`
5. **App URL** → Settings → Secrets:

```toml
HG_MCP_URL = "https://your-hg-mcp-endpoint"
```

6. Deploy. Evaluators open the public URL — no API keys on their machine.

## What the UI covers

| Tab | CLI equivalent |
|-----|----------------|
| Seller profile | `npm run profile:seller` |
| Pipeline | `npm run pipeline` |
| Single PRS | `npm run prs -- --company example.com` |
| Reports | Read `outputs/*/executive_summary.md` |

Pre-generated reports under `outputs/demo/` work in **Reports** even without HG.
