#!/usr/bin/env python3
"""HG Insights Sales Agent — zero-setup web demo (Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app_services import (
    ROOT,
    OUTPUTS_ROOT,
    PROFILE_DIR,
    apply_streamlit_secrets,
    build_seller_profile_web,
    discover_company_products,
    hg_connection_status,
    list_output_iterations,
    list_seller_profiles,
    profile_path_for_slug,
    read_text_if_exists,
    run_pipeline_web,
    run_single_prs_web,
)

st.set_page_config(
    page_title="HG Sales Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_streamlit_secrets()

st.title("HG Insights Sales Agent")
st.caption("3-step demo: Seller profile → ICP candidates → Deep PRS scoring")

# --- Sidebar: HG connection ---
with st.sidebar:
    st.header("HG MCP")
    status = hg_connection_status()
    if status["ok"]:
        st.success("Connected")
        st.text(status["url"])
    else:
        st.error("Not configured")
        st.markdown(
            "Set **`HG_MCP_URL`** in Streamlit secrets or your environment, "
            "or configure `hg-insights` in `~/.cursor/mcp.json`."
        )
        st.code('HG_MCP_URL = "https://…"', language="toml")

    st.divider()
    profiles = list_seller_profiles()
    if profiles:
        st.subheader("Saved profiles")
        for p in profiles[:8]:
            st.text(f"{p['company_name']} — {p['product_name']}")

if "prefetch" not in st.session_state:
    st.session_state.prefetch = None
if "profile_slug" not in st.session_state:
    st.session_state.profile_slug = None
if "pipeline_logs" not in st.session_state:
    st.session_state.pipeline_logs = []

tab_profile, tab_pipeline, tab_prs, tab_reports = st.tabs(
    ["1 · Seller profile", "2 · Pipeline", "3 · Single PRS", "Reports"]
)

# ========== Tab 1: Seller profile ==========
with tab_profile:
    st.subheader("Step 1 — Seller profile & ICP floors")
    company_input = st.text_input("Seller company name", placeholder="e.g. Amazon, Microsoft")

    col1, col2, col3 = st.columns(3)
    with col1:
        min_revenue = st.number_input(
            "ICP — min revenue (USD)",
            min_value=1,
            value=10_000_000,
            step=1_000_000,
            format="%d",
        )
    with col2:
        min_employees = st.number_input(
            "ICP — min employees",
            min_value=1,
            value=200,
            step=50,
        )
    with col3:
        min_it_spend = st.number_input(
            "ICP — min IT spend (USD)",
            min_value=1,
            value=1_000_000,
            step=100_000,
            format="%d",
        )

    icp_floors = {
        "min_revenue_usd": int(min_revenue),
        "min_employees": int(min_employees),
        "min_it_spend_usd": int(min_it_spend),
    }

    if st.button("Search company in HG", type="secondary", disabled=not company_input.strip()):
        if not status["ok"]:
            st.error(status.get("error", "HG MCP not configured"))
        else:
            with st.spinner("Searching HG (30–90 s)…"):
                try:
                    found = discover_company_products(company_input)
                    st.session_state.prefetch = found["prefetch"]
                    st.session_state.profile_slug = found["slug"]
                    st.success(f"Found: **{found['company_name']}** ({found['domain'] or '—'})")
                    products = found["products"]
                    if products:
                        st.session_state.product_labels = [
                            f"{i + 1}. {p.get('product_name', '—')}" for i, p in enumerate(products)
                        ]
                    else:
                        st.session_state.product_labels = []
                        st.warning("No HG catalog products returned for this vendor.")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

    product_index = 1
    labels = st.session_state.get("product_labels") or []
    if labels:
        choice = st.selectbox("Product sold (HG catalog)", labels, index=0)
        product_index = int(choice.split(".", 1)[0])

    if st.button("Build seller profile", type="primary", disabled=not company_input.strip()):
        if not status["ok"]:
            st.error(status.get("error", "HG MCP not configured"))
        else:
            with st.spinner("Building profile…"):
                try:
                    result = build_seller_profile_web(
                        company=company_input,
                        product_index=product_index,
                        icp_floors=icp_floors,
                        prefetch=st.session_state.get("prefetch"),
                        slug=st.session_state.get("profile_slug"),
                    )
                    st.session_state.profile_slug = result["slug"]
                    st.session_state.last_profile_path = str(result["path"])
                    st.success("Profile saved")
                    st.json(
                        {
                            "company": result["company_name"],
                            "domain": result["domain"],
                            "product_sold": result["product_sold"],
                            "file": str(result["path"].relative_to(ROOT)),
                        }
                    )
                    with st.expander("Full JSON"):
                        st.download_button(
                            "Download profile JSON",
                            data=json.dumps(result["payload"], indent=2),
                            file_name=result["path"].name,
                            mime="application/json",
                        )
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

# ========== Tab 2: Pipeline ==========
with tab_pipeline:
    st.subheader("Step 2 & 3 — ICP filter + deep PRS")
    profiles = list_seller_profiles()
    if not profiles:
        st.info("Build a seller profile in tab 1 first.")
    else:
        profile_options = {
            f"{p['company_name']} — {p['product_name']}": p for p in profiles
        }
        selected_label = st.selectbox("Seller profile", list(profile_options.keys()))
        prof = profile_options[selected_label]
        st.session_state.profile_slug = prof["slug"]

        c1, c2, c3 = st.columns(3)
        with c1:
            product_index = st.number_input("Product index", min_value=1, max_value=20, value=1)
        with c2:
            prs_count = st.number_input("Deep PRS count", min_value=1, max_value=10, value=3)
        with c3:
            sample_seed = st.number_input(
                "Sample seed (optional)",
                min_value=0,
                value=0,
                help="0 = random each run",
            )

        run_name = st.text_input(
            "Output folder name under outputs/",
            placeholder="e.g. demo, test_mai (optional)",
        )
        enrich = st.checkbox(
            "Enrich IT spend for every ICP row (slow)",
            value=False,
            help="1 HG call per candidate — use only for audits",
        )

        log_box = st.empty()

        if st.button("Run full pipeline", type="primary"):
            if not status["ok"]:
                st.error(status.get("error", "HG MCP not configured"))
            else:
                logs: list[str] = []

                def on_log(msg: str) -> None:
                    logs.append(msg)
                    log_box.code("\n".join(logs[-40:]), language=None)

                with st.spinner("Running pipeline (several minutes)…"):
                    try:
                        out = run_pipeline_web(
                            company=prof["company_name"],
                            product_index=int(product_index),
                            prs_count=int(prs_count),
                            run_name=run_name.strip() or None,
                            sample_seed=int(sample_seed) if sample_seed > 0 else None,
                            profile_slug=prof["slug"],
                            enrich_icp_it_spend=enrich,
                            on_log=on_log,
                        )
                        st.session_state.pipeline_logs = out.get("logs") or logs
                        if not out.get("ok"):
                            st.error(f"Pipeline failed (exit {out.get('exit_code', '?')})")
                        else:
                            st.success(f"Done — {out.get('iteration_title')}")
                            st.dataframe(out.get("results") or [], use_container_width=True)
                            paths = out.get("paths") or {}
                            exec_path = paths.get("executive_summary.md")
                            if exec_path:
                                st.markdown("### Executive summary")
                                st.markdown(read_text_if_exists(Path(exec_path)))
                    except Exception as exc:  # noqa: BLE001
                        st.error(str(exc))

# ========== Tab 3: Single PRS ==========
with tab_prs:
    st.subheader("Deep PRS for one prospect")
    profiles = list_seller_profiles()
    if not profiles:
        st.info("Build a seller profile first.")
    else:
        profile_options = {f"{p['company_name']}": p["path"] for p in profiles}
        seller_label = st.selectbox("Seller profile", list(profile_options.keys()))
        prospect_query = st.text_input("Prospect (domain or name)", placeholder="nike.com")

        if st.button("Score prospect", type="primary", disabled=not prospect_query.strip()):
            if not status["ok"]:
                st.error(status.get("error", "HG MCP not configured"))
            else:
                with st.spinner("Scoring (5–8 HG calls)…"):
                    try:
                        out = run_single_prs_web(
                            profile_path=profile_options[seller_label],
                            company_query=prospect_query,
                        )
                        st.success(
                            f"{out['prospect_name']} — PRS {out['prs']}/100 "
                            f"(reliability {out['reliability']:.0%})"
                        )
                        st.markdown(out.get("report_md") or "")
                    except Exception as exc:  # noqa: BLE001
                        st.error(str(exc))

# ========== Tab 4: Browse reports ==========
with tab_reports:
    st.subheader("Browse pipeline outputs")
    iterations = list_output_iterations()
    if not iterations:
        st.info(f"No folders in `{OUTPUTS_ROOT.name}/` yet.")
    else:
        names = [it["name"] for it in iterations]
        pick = st.selectbox("Iteration folder", names)
        folder = OUTPUTS_ROOT / pick
        report_kind = st.radio(
            "Report",
            ["Executive summary", "ICP candidates", "Technical scoring"],
            horizontal=True,
        )
        file_map = {
            "Executive summary": "executive_summary.md",
            "ICP candidates": "candidate_companies.md",
            "Technical scoring": "technical_scoring.md",
        }
        md_path = folder / file_map[report_kind]
        if md_path.is_file():
            st.markdown(read_text_if_exists(md_path))
            st.download_button(
                f"Download {md_path.name}",
                data=md_path.read_text(encoding="utf-8"),
                file_name=md_path.name,
            )
        else:
            st.warning(f"Missing: {md_path.name}")

    st.divider()
    st.caption(f"Profiles: `{PROFILE_DIR.relative_to(PROFILE_DIR.parent.parent)}`")
