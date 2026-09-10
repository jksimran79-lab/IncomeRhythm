"""
app.py — IncomeRhythm: AI-powered cash flow coach for gig workers.
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

import db
import analytics as anl
import ai

# ---------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="IncomeRhythm",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Bootstrap database once per session
# ---------------------------------------------------------------------------

if "db_ready" not in st.session_state:
    db.init_db()
    db.seed_demo_data()
    st.session_state["db_ready"] = True

# ---------------------------------------------------------------------------
# User identity (single-user demo, easily extensible)
# ---------------------------------------------------------------------------

USER = db.DEMO_USER

# ---------------------------------------------------------------------------
# Sidebar: user info + API key hint
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("💸 IncomeRhythm")
    st.caption("AI cash flow coach for gig workers")
    st.divider()
    st.markdown("**User:** Demo Worker")
    st.markdown("**Sources:** Swiggy · Zomato · Uber · Tutoring · Freelance")
    st.divider()

    # API key hint
    api_key_configured = bool(ai._get_api_key())
    if api_key_configured:
        st.success("Gemini AI: Connected", icon="✅")
    else:
        st.warning(
            "Gemini AI not configured.\n\n"
            "Add your key to `.streamlit/secrets.toml`:\n\n"
            "`GEMINI_API_KEY = \"your-key\"`",
            icon="⚠️",
        )
    st.divider()
    st.caption("IncomeRhythm v1.0 · Powered by Gemini 2.5 Flash")

# ---------------------------------------------------------------------------
# Load data (cached within the run, refreshed on next rerun)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def load_data(user: str):
    income = db.get_income(user)
    expenses = db.get_expenses(user)
    goals = db.get_goals(user)
    return income, expenses, goals


income_rows, expense_rows, goals = load_data(USER)
analytics = anl.compute_analytics(income_rows)
primary_goal = goals[0] if goals else None

today_str = date.today().isoformat()
today_income = sum(r["amount"] for r in income_rows if r["entry_date"] == today_str)

context = ai.build_income_context(income_rows, expense_rows, analytics, primary_goal)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_dashboard, tab_log, tab_chat, tab_rhythm, tab_goals = st.tabs([
    "🏠 Dashboard",
    "📝 Log Entry",
    "💬 Chat Assistant",
    "📈 Rhythm Tracker",
    "🎯 Goals",
])


# ============================================================================
# TAB 1 — DASHBOARD
# ============================================================================

with tab_dashboard:
    st.header("Your Day at a Glance")
    st.caption(f"Today is {date.today().strftime('%A, %d %B %Y')}")

    # --- Lean period alert ---------------------------------------------------
    upcoming_lean = anl.get_upcoming_lean_days(analytics)
    if upcoming_lean:
        alert_key = f"lean_alert_{today_str}"
        if alert_key not in st.session_state:
            st.session_state[alert_key] = ai.get_lean_period_alert(context, upcoming_lean)
        lean_alert_text = st.session_state[alert_key]
        if lean_alert_text:
            st.warning(f"📉 **Lean Days Ahead:** {lean_alert_text}", icon="⚠️")

    # --- Top metrics row -----------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Today's Income",
            value=f"₹{today_income:,.0f}",
            help="Total income logged so far today",
        )
    with col2:
        st.metric(
            label="Last 7 Days",
            value=f"₹{analytics['total_7d']:,.0f}",
            help="Total income in the past 7 days",
        )
    with col3:
        st.metric(
            label="Avg Daily Income",
            value=f"₹{analytics['avg_daily_income']:,.0f}",
            help="Average daily income over the past 30 days",
        )
    with col4:
        vol_color_map = {"stable": "🟢", "moderate": "🟡", "high": "🔴", "unknown": "⚪"}
        vol_icon = vol_color_map.get(analytics["volatility_label"], "⚪")
        st.metric(
            label="Income Rhythm",
            value=f"{vol_icon} {analytics['volatility_label'].title()}",
            help="How variable your daily income is",
        )

    st.divider()

    # --- Safe-to-Spend -------------------------------------------------------
    col_spend, col_nudge = st.columns([1, 1])

    with col_spend:
        st.subheader("💰 Safe to Spend Today")
        sts_key = f"sts_{today_str}"
        if sts_key not in st.session_state:
            with st.spinner("Calculating your safe-to-spend..."):
                st.session_state[sts_key] = ai.get_safe_to_spend(context, today_income)
        sts = st.session_state[sts_key]
        sts_amount = sts.get("amount", 0)
        sts_reason = sts.get("reasoning", "")

        st.metric(label="Safe to Spend", value=f"₹{sts_amount:,.0f}", label_visibility="hidden")
        if sts_reason:
            st.info(f"💡 {sts_reason}")

        if st.button("🔄 Refresh Recommendation", key="refresh_sts"):
            if sts_key in st.session_state:
                del st.session_state[sts_key]
            st.cache_data.clear()
            st.rerun()

    with col_nudge:
        st.subheader("🐷 Micro-Saving Nudge")
        nudge_key = f"nudge_{today_str}"
        if nudge_key not in st.session_state:
            with st.spinner("Crafting a nudge..."):
                st.session_state[nudge_key] = ai.get_saving_nudge(context, today_income)
        nudge = st.session_state[nudge_key]
        if nudge:
            st.success(f"✨ {nudge}")
        else:
            st.info("Log some income today to get a personalised saving nudge!")

    st.divider()

    # --- Weekly summary -------------------------------------------------------
    st.subheader("📅 Weekly AI Summary")
    summary_key = f"weekly_summary_{(date.today() - timedelta(days=date.today().weekday())).isoformat()}"
    if summary_key not in st.session_state:
        with st.spinner("Generating your weekly summary..."):
            st.session_state[summary_key] = ai.get_weekly_summary(context)
    weekly_summary = st.session_state[summary_key]
    st.info(weekly_summary)

    if st.button("🔄 Refresh Weekly Summary", key="refresh_summary"):
        if summary_key in st.session_state:
            del st.session_state[summary_key]
        st.rerun()

    st.divider()

    # --- Quick income chart (last 14 days) ------------------------------------
    st.subheader("📊 Last 14 Days — Income vs Expenses")
    chart_data = anl.chart_expense_income(income_rows, expense_rows, days=14)
    if any(v > 0 for v in chart_data["income"]):
        df_chart = pd.DataFrame({
            "Income": chart_data["income"],
            "Expenses": chart_data["expenses"],
        }, index=chart_data["dates"])
        st.line_chart(df_chart, width="stretch", height=220)
    else:
        st.info("No income data yet. Log some entries to see your chart!")

    # --- Best / lean day highlight -------------------------------------------
    col_best, col_lean = st.columns(2)
    with col_best:
        st.metric("Best Earning Day", analytics["best_weekday_name"])
    with col_lean:
        lean_names = ", ".join(analytics["lean_weekdays_names"]) or "None detected yet"
        st.metric("Typical Lean Days", lean_names)


# ============================================================================
# TAB 2 — LOG ENTRY
# ============================================================================

with tab_log:
    st.header("Log Your Income & Expenses")

    col_income, col_expense = st.columns(2)

    # ---- Income form --------------------------------------------------------
    with col_income:
        st.subheader("➕ Log Income")
        with st.form("income_form", clear_on_submit=True):
            inc_date = st.date_input("Date", value=date.today(), key="inc_date")
            inc_amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.0f", key="inc_amount")
            inc_source = st.selectbox(
                "Income Source",
                ["Swiggy", "Zomato", "Uber", "Ola", "Tutoring", "Freelance Design",
                 "Freelance Writing", "Daily Wage", "Other"],
                key="inc_source",
            )
            custom_source = st.text_input("Custom source (optional — overrides above)", key="inc_custom")
            submitted_income = st.form_submit_button("✅ Save Income Entry")
            if submitted_income:
                source = custom_source.strip() if custom_source.strip() else inc_source
                if inc_amount > 0:
                    db.add_income(USER, inc_date.isoformat(), inc_amount, source)
                    st.cache_data.clear()
                    # Clear cached AI responses so they regenerate with fresh data
                    for k in list(st.session_state.keys()):
                        if k.startswith(("sts_", "nudge_", "lean_alert_", "weekly_summary_")):
                            del st.session_state[k]
                    st.success(f"Logged ₹{inc_amount:,.0f} from {source}!")
                    st.rerun()
                else:
                    st.error("Please enter a positive amount.")

    # ---- Expense form -------------------------------------------------------
    with col_expense:
        st.subheader("➖ Log Expense")
        with st.form("expense_form", clear_on_submit=True):
            exp_date = st.date_input("Date", value=date.today(), key="exp_date")
            exp_amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.0f", key="exp_amount")
            exp_category = st.selectbox(
                "Category",
                ["Essential", "Discretionary"],
                help="Essential = rent, food, transport. Discretionary = entertainment, dining out, etc.",
                key="exp_cat",
            )
            submitted_expense = st.form_submit_button("✅ Save Expense Entry")
            if submitted_expense:
                if exp_amount > 0:
                    db.add_expense(USER, exp_date.isoformat(), exp_amount, exp_category)
                    st.cache_data.clear()
                    st.success(f"Logged ₹{exp_amount:,.0f} expense ({exp_category})!")
                    st.rerun()
                else:
                    st.error("Please enter a positive amount.")

    st.divider()

    # ---- Recent entries table -----------------------------------------------
    st.subheader("🕒 Recent Entries")
    col_ri, col_re = st.columns(2)

    with col_ri:
        st.caption("Recent Income (last 10)")
        if income_rows:
            df_inc = pd.DataFrame(income_rows[:10])[["entry_date", "source", "amount"]]
            df_inc.columns = ["Date", "Source", "₹ Amount"]
            df_inc["₹ Amount"] = df_inc["₹ Amount"].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(df_inc, width="stretch", hide_index=True)
        else:
            st.info("No income logged yet.")

    with col_re:
        st.caption("Recent Expenses (last 10)")
        if expense_rows:
            df_exp = pd.DataFrame(expense_rows[:10])[["entry_date", "category", "amount"]]
            df_exp.columns = ["Date", "Category", "₹ Amount"]
            df_exp["₹ Amount"] = df_exp["₹ Amount"].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(df_exp, width="stretch", hide_index=True)
        else:
            st.info("No expenses logged yet.")


# ============================================================================
# TAB 3 — CHAT ASSISTANT
# ============================================================================

with tab_chat:
    st.header("💬 Ask IncomeRhythm Anything")
    st.caption(
        "Ask questions like: 'Can I spend ₹500 today?', 'How was my week?', "
        "'What should I save this week?', 'Will this Friday be lean?'"
    )

    # Initialise in-memory chat messages for Streamlit display
    if "chat_messages" not in st.session_state:
        history_from_db = db.get_chat_history(USER, limit=20)
        if history_from_db:
            st.session_state["chat_messages"] = [
                {"role": h["role"], "content": h["message"]} for h in history_from_db
            ]
        else:
            st.session_state["chat_messages"] = [
                {
                    "role": "assistant",
                    "content": (
                        "Hi! 👋 I'm your IncomeRhythm coach. I can see your income history and "
                        "help you make smart spending and saving decisions. What's on your mind today?"
                    ),
                }
            ]

    # Render chat history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask me anything about your finances...")
    if user_input:
        # Append user message
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        db.append_chat(USER, "user", user_input)

        with st.chat_message("user"):
            st.write(user_input)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history_for_ai = [
                    {"role": m["role"], "message": m["content"]}
                    for m in st.session_state["chat_messages"][:-1]
                ]
                # Reload latest data for context
                inc_fresh = db.get_income(USER)
                exp_fresh = db.get_expenses(USER)
                analytics_fresh = anl.compute_analytics(inc_fresh)
                goals_fresh = db.get_goals(USER)
                goal_fresh = goals_fresh[0] if goals_fresh else None
                context_fresh = ai.build_income_context(inc_fresh, exp_fresh, analytics_fresh, goal_fresh)

                response = ai.chat_response(user_input, context_fresh, history_for_ai)
            st.write(response)

        st.session_state["chat_messages"].append({"role": "assistant", "content": response})
        db.append_chat(USER, "assistant", response)

    # Clear chat button
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Chat cleared! How can I help you today? 😊",
            }
        ]
        st.rerun()


# ============================================================================
# TAB 4 — RHYTHM TRACKER
# ============================================================================

with tab_rhythm:
    st.header("📈 Your Income Rhythm")

    if not income_rows:
        st.info("Log some income entries first to see your rhythm!")
    else:
        # Time window selector
        window = st.radio(
            "Time window",
            ["Last 7 Days", "Last 14 Days", "Last 30 Days"],
            horizontal=True,
            key="rhythm_window",
        )
        days_map = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30}
        n_days = days_map[window]

        # Daily income chart
        st.subheader(f"Daily Income — {window}")
        daily_data = anl.chart_daily_income(income_rows, days=n_days)
        df_daily = pd.DataFrame({"Daily Income (₹)": daily_data["income"]}, index=daily_data["dates"])
        st.bar_chart(df_daily, width="stretch", height=250)

        st.divider()

        # Income vs Expenses
        st.subheader("Income vs Expenses")
        ie_data = anl.chart_expense_income(income_rows, expense_rows, days=n_days)
        df_ie = pd.DataFrame(
            {"Income": ie_data["income"], "Expenses": ie_data["expenses"]},
            index=ie_data["dates"],
        )
        st.line_chart(df_ie, width="stretch", height=230)

        st.divider()

        # Weekday average bar chart
        wd_data = anl.weekday_avg_chart(analytics)
        if wd_data["days"]:
            st.subheader("Average Income by Weekday (Last 30 Days)")
            df_wd = pd.DataFrame(
                {"Avg Income (₹)": wd_data["avg_income"]},
                index=wd_data["days"],
            )
            st.bar_chart(df_wd, width="stretch", height=220)

        st.divider()

        # Income by source
        st.subheader("Income by Source (All Time)")
        src_totals = anl.source_totals(income_rows)
        if src_totals:
            df_src = pd.DataFrame(
                {"Total Income (₹)": list(src_totals.values())},
                index=list(src_totals.keys()),
            )
            st.bar_chart(df_src, width="stretch", height=220)

        st.divider()

        # Key stats table
        st.subheader("Key Pattern Stats")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("30-Day Total", f"₹{analytics['total_30d']:,.0f}")
        col_s2.metric("Days Worked (30d)", str(analytics["days_with_income"]))
        col_s3.metric("Income Volatility", f"{analytics['volatility_pct']}% CV")

        col_s4, col_s5, _ = st.columns(3)
        col_s4.metric("Best Day", analytics["best_weekday_name"])
        col_s5.metric("Lean Days", ", ".join(analytics["lean_weekdays_names"]) or "None")


# ============================================================================
# TAB 5 — GOALS
# ============================================================================

with tab_goals:
    st.header("🎯 Savings Goals")

    # ---- Existing goals -----------------------------------------------------
    if goals:
        st.subheader("Your Goals")
        for goal in goals:
            pct = min(100.0, goal["saved"] / goal["target"] * 100) if goal["target"] > 0 else 0
            remaining = max(0, goal["target"] - goal["saved"])

            with st.container(border=True):
                col_g1, col_g2 = st.columns([3, 1])
                with col_g1:
                    st.markdown(f"**{goal['description']}**")
                    st.progress(pct / 100, text=f"₹{goal['saved']:,.0f} of ₹{goal['target']:,.0f} ({pct:.0f}%)")
                    st.caption(f"₹{remaining:,.0f} remaining · Started {goal['created_at']}")
                with col_g2:
                    new_saved = st.number_input(
                        "Update saved (₹)",
                        min_value=0.0,
                        max_value=float(goal["target"]),
                        value=float(goal["saved"]),
                        step=50.0,
                        format="%.0f",
                        key=f"goal_saved_{goal['id']}",
                    )
                    if st.button("Update", key=f"update_goal_{goal['id']}"):
                        db.update_goal_saved(goal["id"], new_saved)
                        st.cache_data.clear()
                        st.success("Goal updated!")
                        st.rerun()
    else:
        st.info("No savings goals yet. Add one below!")

    st.divider()

    # ---- Add new goal --------------------------------------------------------
    st.subheader("➕ Add New Goal")
    with st.form("new_goal_form", clear_on_submit=True):
        goal_desc = st.text_input("Goal description", placeholder="e.g. Emergency fund, New phone, Rent buffer")
        goal_target = st.number_input("Target amount (₹)", min_value=100.0, step=100.0, format="%.0f")
        goal_initial = st.number_input("Already saved (₹)", min_value=0.0, step=50.0, format="%.0f")
        submit_goal = st.form_submit_button("🎯 Save Goal")
        if submit_goal:
            if goal_desc.strip() and goal_target > 0:
                db.add_goal(USER, goal_desc.strip(), goal_target)
                if goal_initial > 0:
                    new_goals = db.get_goals(USER)
                    if new_goals:
                        db.update_goal_saved(new_goals[0]["id"], goal_initial)
                st.cache_data.clear()
                st.success(f"Goal '{goal_desc}' created!")
                st.rerun()
            else:
                st.error("Please enter a description and a target amount.")

    st.divider()

    # ---- Savings tips from AI -----------------------------------------------
    st.subheader("💡 Personalised Savings Tip")
    tips_key = f"savings_tip_{today_str}"
    if tips_key not in st.session_state:
        tip_prompt = (
            f"You are IncomeRhythm, a warm financial coach for gig workers.\n"
            f"User context: {context}\n"
            f"Give ONE short, encouraging savings tip tailored to this user's income pattern. "
            f"Max 2 sentences. Be specific and practical."
        )
        if ai._get_api_key():
            with st.spinner("Getting your tip..."):
                st.session_state[tips_key] = ai._call_gemini(tip_prompt, fallback="Keep setting aside a small amount each day — even ₹20 adds up over a month!")
        else:
            st.session_state[tips_key] = "Keep setting aside a small amount each day — even ₹20 adds up over a month! On your strong weekend days, try to save an extra 10%."

    st.success(f"✨ {st.session_state[tips_key]}")
