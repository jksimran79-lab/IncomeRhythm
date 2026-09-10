"""
ai.py — Google Gemini 2.5 Flash integration for IncomeRhythm.
Uses the google-genai SDK (v1+).
All AI-generated text (recommendations, nudges, summaries, chat) lives here.
"""

import os
from typing import Optional
import streamlit as st

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

MODEL_ID = "models/gemini-3.6-flash"


# ---------------------------------------------------------------------------
# API key resolution: st.secrets → environment variable
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    # Try st.secrets first (works when running via `streamlit run`)
    try:
        key = st.secrets["GEMINI_API_KEY"]
        if key:
            return key
    except Exception:
        pass
    # Fallback: environment variable
    return os.environ.get("GEMINI_API_KEY")


def _get_client():
    if not GENAI_AVAILABLE:
        return None
    api_key = _get_api_key()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _call_gemini(prompt: str, fallback: str = "") -> str:
    """Send a single prompt to Gemini and return the text response."""
    client = _get_client()
    if client is None:
        return fallback or _offline_fallback()
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return fallback or f"(AI unavailable: {e})"


def _offline_fallback() -> str:
    """Generic fallback when no API key is configured."""
    return (
        "🔑 AI features require a Gemini API key. "
        "Add GEMINI_API_KEY to .streamlit/secrets.toml or set it as an environment variable."
    )


# ---------------------------------------------------------------------------
# Helper: build a concise income context string for prompts
# ---------------------------------------------------------------------------

def build_income_context(
    income_rows: list,
    expense_rows: list,
    analytics: dict,
    savings_goal: Optional[dict] = None,
) -> str:
    total_income_7d = sum(r["amount"] for r in income_rows if _within_days(r["entry_date"], 7))
    total_income_30d = sum(r["amount"] for r in income_rows if _within_days(r["entry_date"], 30))
    total_expense_7d = sum(r["amount"] for r in expense_rows if _within_days(r["entry_date"], 7))

    lean_days = analytics.get("lean_weekdays_names", [])
    avg_daily = analytics.get("avg_daily_income", 0)
    volatility = analytics.get("volatility_label", "moderate")

    goal_text = ""
    if savings_goal:
        pct = min(100, round(savings_goal["saved"] / savings_goal["target"] * 100)) if savings_goal["target"] > 0 else 0
        goal_text = (
            f"Savings goal: '{savings_goal['description']}' — "
            f"₹{savings_goal['saved']:.0f} of ₹{savings_goal['target']:.0f} saved ({pct}%)."
        )

    sources = list({r["source"] for r in income_rows})

    return (
        f"Income sources: {', '.join(sources) if sources else 'none logged yet'}. "
        f"Last 7 days income: ₹{total_income_7d:.0f}. "
        f"Last 30 days income: ₹{total_income_30d:.0f}. "
        f"Average daily income: ₹{avg_daily:.0f}. "
        f"Income volatility: {volatility}. "
        f"Typical lean days: {', '.join(lean_days) if lean_days else 'none detected'}. "
        f"Last 7 days expenses: ₹{total_expense_7d:.0f}. "
        f"{goal_text}"
    )


def _within_days(date_str: str, days: int) -> bool:
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(date_str)
        return d >= date.today() - timedelta(days=days)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Feature 1: Daily Safe-to-Spend
# ---------------------------------------------------------------------------

def get_safe_to_spend(context: str, today_income: float) -> dict:
    """Returns {"amount": float, "reasoning": str}"""
    prompt = f"""
You are IncomeRhythm, a warm and simple cash-flow coach for gig workers.

User context:
{context}
Today's income logged so far: ₹{today_income:.0f}

Task: Calculate a safe-to-spend amount (in ₹) for today.
Rules:
- Be conservative when upcoming days are typically lean.
- Reserve a small buffer for savings if they have a goal.
- Keep leftover for expenses not yet logged.
- Return ONLY a JSON object with two keys:
  "amount": a number (integer, no currency symbol),
  "reasoning": one warm, simple sentence (max 20 words) explaining why.

Example: {{"amount": 350, "reasoning": "Your Tuesdays tend to be slow, so let's keep a small cushion today."}}
"""
    raw = _call_gemini(prompt)
    return _parse_json_response(raw, {"amount": max(0, today_income * 0.6), "reasoning": "Spend within your means today!"})


# ---------------------------------------------------------------------------
# Feature 2: Micro-Saving Nudge
# ---------------------------------------------------------------------------

def get_saving_nudge(context: str, today_income: float) -> str:
    if today_income <= 0:
        return ""
    prompt = f"""
You are IncomeRhythm, a warm financial coach for gig workers.

User context:
{context}
Today's income: ₹{today_income:.0f}

Give ONE short, warm micro-saving nudge (1 sentence, max 15 words).
Suggest a specific small ₹ amount to save today (proportional to income).
Be encouraging, not preachy.
Return ONLY the nudge sentence, nothing else.
"""
    return _call_gemini(
        prompt,
        fallback=f"You earned ₹{today_income:.0f} today — consider saving a little for a rainy day!",
    )


# ---------------------------------------------------------------------------
# Feature 3: Lean-Period Alert
# ---------------------------------------------------------------------------

def get_lean_period_alert(context: str, upcoming_lean_days: list) -> str:
    if not upcoming_lean_days:
        return ""
    days_text = ", ".join(upcoming_lean_days)
    prompt = f"""
You are IncomeRhythm, a friendly cash-flow coach.

User context:
{context}
Upcoming potentially lean days in the next 3 days: {days_text}

Write ONE short, warm, actionable alert (1–2 sentences, max 25 words total).
Tell the user to prepare without being alarming.
Return ONLY the alert sentence(s), nothing else.
"""
    return _call_gemini(
        prompt,
        fallback=f"Heads up — {days_text} tend to be quieter. Plan a little ahead!",
    )


# ---------------------------------------------------------------------------
# Feature 4: Weekly AI Summary
# ---------------------------------------------------------------------------

def get_weekly_summary(context: str) -> str:
    prompt = f"""
You are IncomeRhythm, a warm AI cash-flow coach for gig workers.

User's past 7-day context:
{context}

Write a short, friendly weekly summary (3–4 sentences) that:
1. Describes the week's earning rhythm (highs and lows).
2. Notes any pattern worth knowing.
3. Gives one simple, encouraging suggestion for next week.

Tone: warm, simple, non-technical. Avoid jargon.
Return ONLY the summary paragraph, nothing else.
"""
    return _call_gemini(
        prompt,
        fallback="You've been putting in the work this week! Review your rhythm chart to see your highs and lows, and plan a small buffer for quieter days ahead.",
    )


# ---------------------------------------------------------------------------
# Feature 5: Chat assistant
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are IncomeRhythm, a warm, encouraging, and simple AI cash-flow coach "
    "for gig workers and irregular-income earners. "
    "The user may be a delivery partner, freelancer, tutor, or daily-wage worker. "
    "Answer in plain, friendly language — no finance jargon. "
    "Use ₹ for currency. "
    "Keep answers short (2–4 sentences max) unless the user asks for detail. "
    "Never make up numbers; use only the context provided."
)


def chat_response(user_message: str, context: str, history: list) -> str:
    """
    history: list of {"role": "user"|"assistant", "message": str}
    """
    client = _get_client()
    if client is None:
        return _offline_fallback()

    try:
        # Build contents list for multi-turn chat
        contents = []
        for h in history[-8:]:
            role = "user" if h["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=h["message"])]))

        # Append current user message with full context injected
        full_user_message = (
            f"{SYSTEM_PROMPT}\n\n"
            f"User's financial context:\n{context}\n\n"
            f"User question: {user_message}"
        )
        contents.append(types.Content(role="user", parts=[types.Part(text=full_user_message)]))

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
        )
        return response.text.strip()
    except Exception as e:
        return f"Sorry, I couldn't process that right now. ({e})"


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_json_response(raw: str, fallback: dict) -> dict:
    import json, re
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return fallback
