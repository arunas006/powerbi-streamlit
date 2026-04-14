import streamlit as st
import requests
import copy
from datetime import datetime

from src.config import Settings

# ---------------- CONFIG ----------------
settings = Settings()
API_URL = f"{settings.AGENT_URL}/chat"

st.set_page_config(page_title="Power BI Agent", page_icon="🤖", layout="wide")

import ast

import ast
import json

def extract_clean_response(data):
    """
    Fully unwraps agent response (handles nested/double-string JSON)
    """

    try:
        # Step 1: If response key exists
        if isinstance(data, dict) and "response" in data:
            raw = data["response"]
        else:
            raw = data

        # Step 2: Keep parsing until it's clean
        for _ in range(3):  # prevent infinite loop
            if isinstance(raw, str):
                raw = raw.strip()

                # Try JSON first
                try:
                    raw = json.loads(raw)
                    continue
                except:
                    pass

                # Try Python dict string
                try:
                    raw = ast.literal_eval(raw)
                    continue
                except:
                    pass

            break  # stop if not string

        # Step 3: Final formatting
        if isinstance(raw, dict):

            # ✅ Normal message
            if "response" in raw:
                return raw["response"]

            # ✅ Comparison format
            if "status" in raw and "data" in raw:
                counts = raw["data"]["status"]["counts"]

                return f"""
### 📊 Dashboard Comparison

- Dev Total: **{counts.get('dev_total')}**
- Prod Total: **{counts.get('prod_total')}**
- Missing in Prod: **{counts.get('missing_in_prod')}**
- Missing in Dev: **{counts.get('missing_in_dev')}**
"""

            return json.dumps(raw, indent=2)

        return str(raw)

    except Exception as e:
        return f"Error parsing response: {str(e)}"

# ---------------- SESSION STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "threads" not in st.session_state:
    st.session_state.threads = []

if "active_thread" not in st.session_state:
    st.session_state.active_thread = str(datetime.utcnow().timestamp())

if "processing" not in st.session_state:
    st.session_state.processing = False


# ---------------- HELPERS ----------------
def make_title(text: str) -> str:
    return (text[:40] + '…') if len(text) > 40 else text


def save_current_thread():
    if not st.session_state.messages:
        return

    title = make_title(st.session_state.messages[0]["content"])

    thread = {
        "id": str(datetime.utcnow().timestamp()),
        "title": title,
        "messages": copy.deepcopy(st.session_state.messages),
        "ts": datetime.utcnow().strftime("%H:%M")
    }

    st.session_state.threads.insert(0, thread)
    st.session_state.active_thread = thread["id"]


# ---------------- SIDEBAR ----------------
st.sidebar.markdown("## 💬 Chats")

col1, col2 = st.sidebar.columns([1, 1])

with col1:
    if st.button("➕ New Chat"):
        st.session_state.messages = []
        st.session_state.active_thread = str(datetime.utcnow().timestamp())
        st.rerun()

with col2:
    if st.button("💾 Save"):
        save_current_thread()
        st.sidebar.success("Saved")

st.sidebar.markdown("---")

# Thread list
for t in st.session_state.threads:
    if st.sidebar.button(t["title"], key=f"thr_{t['id']}"):
        st.session_state.messages = copy.deepcopy(t["messages"])
        st.session_state.active_thread = t["id"]
        st.rerun()


# ---------------- TITLE ----------------
st.title("🤖 Power BI Assistant")


# ---------------- DISPLAY CHAT ----------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):

        # Dashboard cards
        if isinstance(msg["content"], list):
            for dash in msg["content"]:
                st.markdown(f"""
                <div style="background:#0f172a;padding:14px;border-radius:12px;margin-bottom:8px;border:1px solid #1f2937;">
                    <b style="color:#93c5fd;">📊 {dash.get('Selected_Dashboard')}</b><br>
                    <span style="color:#cbd5f5;">💡 {dash.get('Reason')}</span>
                </div>
                """, unsafe_allow_html=True)

        # Normal text
        else:
            st.markdown(msg["content"])


# ---------------- USER INPUT ----------------
user_input = st.chat_input("Ask something about Power BI...")

if user_input and not st.session_state.processing:

    # 🔥 Step 1: Add user message and rerun immediately
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    st.session_state.processing = True
    st.rerun()


# ---------------- API CALL AFTER RERUN ----------------
if st.session_state.processing:

    try:
        last_user_msg = st.session_state.messages[-1]["content"]

        response = requests.post(
            API_URL,
            json={
                "message": last_user_msg,
                "thread_id": str(st.session_state.active_thread)
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code != 200:
            assistant_message = f"❌ API Error: {response.status_code}\n{response.text}"
        else:
            raw_data = response.json()
            data = extract_clean_response(raw_data)

            assistant_message = ""

            if isinstance(data, dict) and "status" in data:

                payload = data.get("data", {})

                if data.get("status") == "success":

                    # ✅ Comparison response
                    if isinstance(payload, dict) and "status" in payload and "counts" in payload["status"]:
                        stats = payload["status"]["counts"]

                        assistant_message = f"""
📊 Dev: {stats.get('dev_total')}
📊 Prod: {stats.get('prod_total')}
❌ Missing in Prod: {stats.get('missing_in_prod')}
❌ Missing in Dev: {stats.get('missing_in_dev')}
📊 Dev Dashboards: {stats.get('dev_dashboards', 0)}
📊 Prod Dashboards: {stats.get('prod_dashboards', 0)}

"""

                    # ✅ Dashboard recommendations
                    elif "dashboards" in payload:
                        assistant_message = payload["dashboards"]

                    # ✅ Generic response
                    else:
                        assistant_message = str(payload)

                else:
                    assistant_message = f"❌ Failed: {str(data)}"

            else:
                assistant_message = str(data)

        # 🔥 Step 2: Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_message
        })

    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"❌ Error: {str(e)}"
        })

    # 🔥 Step 3: Reset + rerun
    st.session_state.processing = False
    st.rerun()