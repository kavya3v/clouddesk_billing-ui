"""Local Streamlit interface for CloudDesk Billing Support."""

import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from client import ChatClientError
from chat_backend import send_chat_message


load_dotenv()

st.set_page_config(
    page_title="KRMB Desk Billing Support",
    page_icon=":material/receipt_long:",
    layout="centered",
)

ASSETS = Path(__file__).resolve().parent / "assets"
st.html((ASSETS / "chat.css").read_text(encoding="utf-8"))


def start_new_conversation() -> None:
    st.session_state["conversation_id"] = str(uuid.uuid4())
    st.session_state["messages"] = []


if "conversation_id" not in st.session_state:
    start_new_conversation()
if "messages" not in st.session_state:
    st.session_state["messages"] = []


with st.container(horizontal=True, vertical_alignment="center"):
    st.html('''<div class="desk-brand">
      <div class="desk-mark" aria-hidden="true">K</div>
      <div><div class="desk-name">KRMB Desk</div>
      <div class="desk-label">Billing support assistant</div></div>
    </div>''')
    if st.button("New conversation", icon=":material/add:", key="new_conversation"):
        start_new_conversation()
        st.rerun()

st.divider()
welcome = st.empty()
starter_prompt = None
if not st.session_state["messages"]:
    with welcome.container():
        text, illustration = st.columns([1.6, 1], vertical_alignment="center")
        with text:
            st.html('''<div class="desk-welcome">
              <div class="desk-eyebrow">A little clarity for your billing</div>
              <h1>Let’s make sense<br>of your bill.</h1>
              <p>Questions about an invoice, a payment, or your subscription?
              Ask away. We’ll help you find the next step.</p>
              <div class="desk-meta"><span>Invoices &amp; receipts</span>
              <span>Payments</span><span>Subscriptions</span></div>
            </div>''')
        with illustration:
            st.image(str(ASSETS / "billing.svg"), width="stretch",
                     alt="An invoice with a payment checkmark and chat bubble")
        st.space("small")
        st.markdown("**What can we help you with?**")
        with st.container(horizontal=True, key="starters"):
            for key, label, icon, question in (
                ("invoices", "Find my invoices", "receipt_long", "Where can I download my invoices?"),
                ("payments", "Payment help", "credit_card", "How can I update my payment method?"),
                ("subscription", "My subscription", "autorenew", "How can I change my subscription plan?"),
            ):
                if st.button(label, icon=f":material/{icon}:",
                             key=f"starter_{key}", width="stretch"):
                    starter_prompt = question

st.info("Keep card numbers, passwords, and sign-in codes out of this chat.",
        icon=":material/lock:")

for message in st.session_state["messages"]:
    avatar = ":material/support_agent:" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

chat_input = st.chat_input("Ask about your invoice, payment, or plan…", submit_mode="disable")
chat_input = chat_input or starter_prompt
if chat_input:
    welcome.empty()
    st.session_state["messages"].append(
        {"role": "user", "content": chat_input}
    )
    with st.chat_message("user"):
        st.markdown(chat_input)

    with st.chat_message("assistant", avatar=":material/support_agent:"):
        try:
            with st.spinner("Checking billing information..."):
                answer = send_chat_message(
                    session_id=st.session_state["conversation_id"],
                    chat_input=chat_input,
                )
            st.markdown(answer)
            st.session_state["messages"].append(
                {"role": "assistant", "content": answer}
            )
        except ChatClientError as exc:
            st.error(str(exc))

st.html('''<div class="desk-help">Account-specific requests may need human review.
    Each question is answered independently; earlier messages are shown for
    your reference only.</div>''')
