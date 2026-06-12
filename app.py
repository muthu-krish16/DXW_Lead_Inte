import streamlit as st
import pandas as pd
from analyzer import analyze_company
from scoring import calculate_final_score
from database import create_tables, save_report

create_tables()
st.set_page_config(page_title="DXW Lead Intelligence", page_icon="🧠", layout="wide")
st.title("🧠 DXW Lead Intelligence")
st.caption("Upload → Analyze → Decide")
st.divider()


if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = ""

st.subheader("🔑 Gemini API Key")

col1, col2 = st.columns([4, 1])

with col1:
    api_key = st.text_input(
        "Enter Gemini API Key",
        type="password",
        value=st.session_state.gemini_key,
        placeholder="Paste your Gemini API key here"
    )

    if api_key:
        st.session_state.gemini_key = api_key
        st.success("✅ Key Added")

with col2:
    st.write("")
    st.write("")

    if st.button("🗑️ Clear Memory"):
        st.session_state.clear()
        st.success("✅ Memory Cleared")
        st.rerun()

st.divider()


URL_COLUMNS = ["Domain", "LinkedIn_Company", "Blog", "News"]
INFO_MAP = {"company_name":"company_name","industry":"industry","employee_size":"Employee Size",
            "revenue":"Revenue","city":"City","state":"State","country":"Country"}

def safe(v): return "" if pd.isna(v) else str(v).strip()
def extract_urls(row, cols):
    urls, seen = [], set()
    for c in URL_COLUMNS:
        if c in cols:
            for l in safe(row[c]).split("\n"):
                l = l.strip()
                if l.startswith("http") and l not in seen: urls.append(l); seen.add(l)
    return urls
def extract_contacts(g):
    out = []
    for _, r in g.iterrows():
        n = f"{safe(r.get('First Name',''))} {safe(r.get('Last Name',''))}".strip()
        t, e = safe(r.get("Title","")), safe(r.get("Email ID",""))
        if n or t or e: out.append({"name":n,"title":t,"email":e})
    return out
def extract_info(row): return {k: safe(row.get(v,"")) for k,v in INFO_MAP.items()}
def sl(s): return "🔴 High" if s>=8 else "🟡 Medium" if s>=5 else "🟢 Low"
def ok(val): return val and val not in ["","—","INSUFFICIENT DATA","None"]
def prose(text):
    """Display narrative text, converting [URL] citations to clickable links."""
    if not ok(text): return
    import re
    linked = re.sub(r'\[(https?://[^\]]+)\]', r'[\1](\1)', text)
    st.markdown(linked)

uploaded = st.file_uploader("Upload Excel", type=["xlsx"])
if uploaded:
    df = pd.read_excel(uploaded); df.columns = df.columns.str.strip()
    st.dataframe(df, use_container_width=True)
    cos = df.groupby("company_name", sort=False)
    sel = st.selectbox("Select Company", list(cos.groups.keys()))
    if sel:
        g = cos.get_group(sel); fr = g.iloc[0]
        info = extract_info(fr); urls = extract_urls(fr, df.columns.tolist()); contacts = extract_contacts(g)
        st.divider()
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Company", info.get("company_name","—")); st.caption(info.get("industry",""))
        with c2: st.metric("Employees", info.get("employee_size","—")); st.caption(f"Revenue: {info.get('revenue','—')}")
        with c3: st.metric("Location", ", ".join(filter(None,[info.get("city",""),info.get("country","")])) or "—")
        st.divider()

        if st.button("🚀 Analyze This Company", type="primary"):

            # Validate Gemini API Key
            if not st.session_state.get("gemini_key"):
                st.error("❌ Please add a Gemini API Key first.")
                st.stop()

            with st.spinner(
                "Scraping → Detecting Tech → Searching → Deep Analysis..."
            ):
                try:
                    ai, sources = analyze_company(
                        info,
                        urls,
                        contacts,
                        st.session_state.gemini_key
                    )
                    fs = calculate_final_score(ai)
                    save_report(ai, fs, info, contacts)
                except Exception as e:
                    st.error("❌ Analysis Failed")
                    st.exception(e)
                    st.stop()

            st.success("✅ Analysis Complete")

            if st.button("🗑️ Clear Memory", key="clear_after_analysis"):
                saved_key = st.session_state.get("gemini_key")
                st.session_state.clear()
                st.session_state.gemini_key = saved_key
                st.success("✅ Search Memory Cleared")
                st.rerun()

            # ══════ 15. SUMMARY (TOP) ══════
            s = ai.get("15_summary", {})
            if s:
                st.subheader("📋 Quick Summary")
                c1,c2 = st.columns([2,1])
                with c1:
                    prose(s.get("why_dxw_should_care",""))
                    top3 = s.get("top_3_opportunities",[])
                    if top3:
                        st.markdown("**Top Opportunities:**")
                        for i,o in enumerate(top3,1): st.write(f"{i}. {o}")
                    st.markdown(f"**Who to Call:** {s.get('who_to_call','—')}")
                with c2:
                    st.metric("Tier", s.get("tier","—"))
                    st.markdown(f"**Deal Size:** {s.get('deal_size','—')}")
                    st.markdown(f"**Next Step:** {s.get('next_step','—')}")
                st.divider()

            # ══════ 1. BUSINESS OPERATIONS ══════
            s1 = ai.get("1_business_operations", {})
            if s1:
                st.subheader("1️⃣ Business Operations")
                st.info(s1.get("one_line_summary","—"))
                prose(s1.get("company_overview",""))

                c1,c2 = st.columns(2)
                with c1:
                    for k,l in [("who_they_serve","Serves"),("business_model","Model"),("company_size_and_stage","Size & Stage")]:
                        v = s1.get(k,"")
                        if ok(v): st.markdown(f"**{l}:**"); prose(v)
                with c2:
                    for k,l in [("competitive_positioning","Positioning"),("geography_and_presence","Geography"),("regulatory_environment","Regulatory")]:
                        v = s1.get(k,"")
                        if ok(v): st.markdown(f"**{l}:**"); prose(v)
                    p = s1.get("key_partnerships",[])
                    if p: st.markdown(f"**Partners:** {', '.join(p)}")

                for k,l in [("operational_complexity_analysis","Operational Complexity"),("where_data_is_generated","Data Generation Points"),("real_time_data_environment","Real-Time Data")]:
                    v = s1.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                st.divider()

            # ══════ 2. TECHNOLOGY STACK ══════
            s2 = ai.get("2_technology_stack", {})
            if s2:
                st.subheader("2️⃣ Technology Stack")
                c1,c2 = st.columns(2)
                with c1:
                    st.markdown("**✅ Confirmed**")
                    for t in s2.get("confirmed_technologies",[]): st.write(f"- {t}")
                with c2:
                    st.markdown("**🔍 Likely**")
                    for t in s2.get("likely_technologies",[]): st.write(f"- {t}")

                for k,l in [("cloud_infrastructure","Cloud"),("databases_and_warehouses","DB/Warehouse"),("data_pipelines_and_etl","Pipelines/ETL"),
                            ("ai_ml_tools_and_frameworks","AI/ML"),("analytics_and_bi","Analytics/BI"),("crm_and_marketing_tools","CRM/Marketing")]:
                    v = s2.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)

                for k,l in [("legacy_vs_modern_assessment","Legacy vs Modern"),("hybrid_complexity_analysis","Hybrid Complexity"),("integration_burden_analysis","Integration Burden")]:
                    v = s2.get(k,"")
                    if ok(v): st.warning(f"**{l}:**"); prose(v)

                fits = s2.get("where_dxw_fits",[])
                if fits:
                    st.markdown("### 🔌 Where DXW Plugs In")
                    for f in fits:
                        with st.expander(f"**{f.get('their_system','—')}** → {f.get('dxw_service','—')} ({f.get('urgency','')})"):
                            prose(f.get("the_problem","")); prose(f.get("what_dxw_does","")); st.success(f.get("impact",""))

                sug = s2.get("new_suggestions",[])
                if sug:
                    st.markdown("### 💡 New Suggestions")
                    for n in sug:
                        st.success(f"**{n.get('recommendation','')}**"); prose(n.get("why","")); st.caption(f"DXW: {n.get('dxw_service','')} | Impact: {n.get('impact','')}")
                st.divider()

            # ══════ 3. DATA ARCHITECTURE ══════
            s3 = ai.get("3_data_architecture", {})
            if s3:
                st.subheader("3️⃣ Data Architecture")
                prose(s3.get("data_flow_analysis",""))
                for k,l in [("silo_analysis","Silo Analysis"),("governance_break_points","Governance Break Points"),("central_warehouse_assessment","Central Warehouse"),
                            ("data_duplication_risks","Duplication Risks"),("cross_system_dependencies","Cross-System Dependencies"),("scalability_assessment","Scalability"),("migration_signals","Migration Signals")]:
                    v = s3.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                systems = s3.get("known_data_systems",[])
                if systems: st.markdown("**Known Systems:**"); [st.write(f"- {sys}") for sys in systems]
                opps = s3.get("dxw_opportunities",[])
                if opps:
                    st.markdown("### 🎯 DXW Opportunities")
                    for o in opps:
                        with st.expander(f"**{o.get('gap','—')}** → {o.get('dxw_service','—')}"):
                            prose(o.get("what_dxw_does","")); st.success(o.get("impact",""))
                st.divider()

            # ══════ 4. GOVERNANCE MATURITY ══════
            s4 = ai.get("4_governance_maturity", {})
            if s4:
                st.subheader("4️⃣ Governance Maturity")
                r = s4.get("overall_rating","")
                if ok(r): st.metric("Rating", r)
                prose(s4.get("governance_analysis",""))
                for k,l in [("governance_hiring_signals","Hiring Signals"),("outsourcing_signals","Outsourcing"),("missing_standards","Missing Standards"),("compliance_pressure","Compliance")]:
                    v = s4.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                opps = s4.get("dxw_opportunities",[])
                if opps:
                    for o in opps:
                        with st.expander(f"**{o.get('gap','—')}** → {o.get('dxw_service','—')}"):
                            prose(o.get("what_dxw_does","")); st.success(o.get("impact",""))
                st.divider()

            # ══════ 5. HIRING ══════
            s5 = ai.get("5_hiring_intelligence", {})
            if s5:
                st.subheader("5️⃣ Hiring Intelligence")
                prose(s5.get("overview",""))
                for role in s5.get("roles_detected",[]): st.write(f"- {role}")
                infs = s5.get("hiring_inferences",[])
                if infs:
                    st.markdown("### 🔍 What Hiring Reveals")
                    for h in infs:
                        with st.expander(f"**{h.get('role_or_pattern','—')}** `[{h.get('evidence_type','')}]`"):
                            prose(h.get("what_it_means","")); st.warning(f"**Pain:** {h.get('implied_pain','—')}"); st.success(f"**DXW:** {h.get('dxw_relevance','—')}")
                for k,l in [("talent_gaps","Talent Gaps"),("budget_direction","Budget Direction")]:
                    v = s5.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                st.divider()

            # ══════ 6. PUBLIC SIGNALS ══════
            s6 = ai.get("6_public_signals", {})
            if s6:
                st.subheader("6️⃣ Public Signals & Sentiment")
                prose(s6.get("overview",""))
                for k,l in [("glassdoor_analysis","Glassdoor"),("customer_feedback","Customer Feedback"),("news_and_media","Media"),("regulatory_signals","Regulatory"),("transformation_friction","Transformation")]:
                    v = s6.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                infs = s6.get("signal_inferences",[])
                if infs:
                    for si in infs:
                        with st.expander(f"{si.get('signal','—')} — {si.get('confidence','')}"):
                            prose(si.get("what_it_means","")); st.success(f"**DXW:** {si.get('dxw_relevance','—')}")
                st.divider()

            # ══════ 7. PRODUCTS & PAIN ══════
            s7 = ai.get("7_products_and_pain_areas", {})
            if s7:
                st.subheader("7️⃣ Products & Pain Areas")
                for p in s7.get("products",[]):
                    with st.expander(f"📦 **{p.get('name','—')}**"):
                        prose(p.get("description","")); st.markdown(f"**Target:** {p.get('target_customer','—')}")
                        st.warning(f"**Pain:**"); prose(p.get("pain_analysis",""))
                        st.success(f"**DXW Fit:**"); prose(p.get("dxw_fit",""))
                        st.caption(f"Service: {p.get('dxw_service','')} | Evidence: `[{p.get('evidence_type','')}]`")
                for svc in s7.get("services",[]):
                    with st.expander(f"🔧 **{svc.get('name','—')}**"):
                        prose(svc.get("description","")); st.warning("**Pain:**"); prose(svc.get("pain_analysis",""))
                        st.success("**DXW Fit:**"); prose(svc.get("dxw_fit",""))
                st.divider()

            # ══════ 8. MATURITY ASSESSMENT ══════
            s8 = ai.get("8_maturity_assessment", {})
            if s8:
                st.subheader("8️⃣ AI & Data Maturity Assessment")
                for k,l in [("ai_ml_maturity","AI/ML"),("data_governance_maturity","Data Governance"),("data_operations_maturity","Data Operations"),
                            ("integration_maturity","Integration"),("reporting_bi_maturity","Reporting/BI"),("automation_maturity","Automation")]:
                    item = s8.get(k,{})
                    if isinstance(item,dict):
                        with st.expander(f"**{l}** — {item.get('rating','—')}"):
                            prose(item.get("analysis",""))
                overall = s8.get("overall_assessment","")
                if ok(overall): st.info(f"**Overall:** {overall}")
                st.divider()

            # ══════ 9. PAIN CHAIN ══════
            s9 = ai.get("9_pain_hypothesis_chain", [])
            if s9:
                st.subheader("9️⃣ Pain → Opportunity Chain")
                for i,h in enumerate(s9,1):
                    with st.expander(f"#{i} — {h.get('likely_pain','—')} ({h.get('confidence','')}, {h.get('urgency','')})"):
                        st.markdown(f"**Observation:**"); prose(h.get("observation",""))
                        st.markdown(f"**→ Inference:**"); prose(h.get("inference",""))
                        st.markdown(f"**→ Pain:**"); prose(h.get("likely_pain",""))
                        st.markdown(f"**→ Impact:**"); prose(h.get("business_impact",""))
                        st.success(f"**→ DXW Solution:** {h.get('dxw_solution','—')}")
                        st.caption(f"Service: {h.get('dxw_service','')} | Stakeholder: {h.get('stakeholder','')} | Evidence: `[{h.get('evidence_type','')}]`")
                st.divider()

            # ══════ 10. DXW MAPPING ══════
            s10 = ai.get("10_dxw_opportunity_mapping", [])
            if s10:
                st.subheader("🔟 DXW Opportunity Mapping")
                for o in s10:
                    with st.expander(f"**{o.get('dxw_service','—')}** — {o.get('urgency','')}"):
                        prose(o.get("why_relevant","")); st.markdown(f"**Need:** {o.get('target_need','—')}")
                        st.success(f"**Impact:** {o.get('impact','—')}"); st.caption(f"Stakeholder: {o.get('stakeholder','')}")
                st.divider()

            # ══════ 11. FUNDING ══════
            s11 = ai.get("11_funding_and_investment", {})
            if s11:
                st.subheader("1️⃣1️⃣ Funding & Investment")
                ct = s11.get("company_type",""); pub = s11.get("publicly_traded",""); tick = s11.get("ticker","")
                if ok(ct): st.markdown(f"**Type:** {ct}")
                if pub and "yes" in pub.lower() and tick: st.markdown(f"**Traded:** {tick}")
                c1,c2 = st.columns(2)
                with c1: st.metric("Funding", s11.get("total_funding","—"))
                with c2: st.metric("Valuation", s11.get("valuation","—"))
                for rnd in s11.get("funding_rounds",[]):
                    st.write(f"**{rnd.get('round','—')}** — {rnd.get('amount','—')} ({rnd.get('date','—')}) Lead: {rnd.get('lead_investor','—')}")
                inv = s11.get("key_investors",[])
                if inv: st.markdown(f"**Investors:** {', '.join(inv)}")
                for k,l in [("revenue_analysis","Revenue"),("investment_focus","Investment Focus"),("financial_health","Health")]:
                    v = s11.get(k,"")
                    if ok(v): st.markdown(f"**{l}:**"); prose(v)
                ms = s11.get("recent_milestones",[])
                if ms: [st.write(f"• {m}") for m in ms]
                dx = s11.get("dxw_implication","")
                if ok(dx): st.success(f"**DXW Implication:**"); prose(dx)
                st.divider()

            # ══════ 12. LEADERSHIP ══════
            s12 = ai.get("12_leadership_signals", {})
            if s12:
                st.subheader("1️⃣2️⃣ Leadership")
                for lead in s12.get("key_leaders",[]): st.write(f"- {lead}")
                prose(s12.get("leadership_messaging_analysis",""))
                for pri in s12.get("strategic_priorities",[]): st.write(f"→ {pri}")
                ip = s12.get("implied_pain","")
                if ok(ip): st.warning(f"**Implied Pain:**"); prose(ip)
                st.divider()

            # ══════ 13. CONFIDENCE ══════
            s13 = ai.get("13_confidence_and_risk", {})
            if s13:
                st.subheader("1️⃣3️⃣ Confidence & Risk Notes")
                prose(s13.get("overall_confidence",""))
                for k,l,icon in [("high_confidence_findings","High Confidence","🟢"),("medium_confidence_findings","Medium Confidence","🟡"),("low_confidence_findings","Low Confidence","🔴")]:
                    items = s13.get(k,[])
                    if items:
                        st.markdown(f"**{icon} {l}:**")
                        for item in items: st.write(f"- {item}")
                unc = s13.get("key_uncertainties",[])
                if unc: st.markdown("**Uncertainties:**"); [st.write(f"- {u}") for u in unc]
                dk = s13.get("what_we_dont_know",[])
                if dk: st.markdown("**What We Don't Know:**"); [st.write(f"- {d}") for d in dk]
                nxt = s13.get("recommended_next_steps_to_validate",[])
                if nxt: st.markdown("**To Validate:**"); [st.write(f"- {n}") for n in nxt]
                st.divider()

            # ══════ 14. SCORES ══════
            s14 = ai.get("14_scores", {})
            if s14:
                st.subheader("1️⃣4️⃣ Scores")
                keys = [("dxw_fitment","DXW Fit"),("operational_complexity","Ops"),("data_architecture_risk","Data Arch"),
                        ("governance_gap","Governance"),("tech_modernization_need","Tech Mod"),("ai_maturity","AI"),
                        ("timing_urgency","Timing"),("account_potential","Potential")]
                cols = st.columns(4)
                for i,(k,l) in enumerate(keys):
                    v = s14.get(k,{})
                    sc = v.get("score",0) if isinstance(v,dict) else v
                    with cols[i%4]:
                        st.metric(l, f"{sc}/10", sl(sc))
                        if isinstance(v,dict): st.caption(v.get("why",""))
                st.divider()

            # ══════ FOOTER ══════
            with st.expander(f"🔗 Sources ({len(sources)})"):
                for src in sources: st.markdown(f"- **[{src['type']}]** [{src['url']}]({src['url']})")
            with st.expander("🔧 Raw JSON"): st.json(ai)
            st.metric("🎯 Strategic Fitment Score", f"{fs}%")