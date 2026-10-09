
import smtplib
from email.mime.text import MIMEText

from google import genai
from google.genai import types
import streamlit as st

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)


# Credentials
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()

MODEL_NAME = "gemini-3.5-flash"


# Send email
def send_email(to_address, subject, body):
    try:
        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = GMAIL_ADDRESS
        message["To"] = to_address

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)

        return True, "Email sent successfully."

    except Exception as error:
        return False, str(error)


# Display chat messages
def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append(
        {"role": role, "kind": kind, "content": content}
    )
    render_message(st.session_state.messages[-1])


# Ask Gemini
def ask_gemini(parts):
    try:
        response = st.session_state.chat.send_message(parts)
        return response.text or "No summary available."
    except Exception as error:
        return f"Sorry, something went wrong: {error}"


# Step 1: Onboarding (name and email)
if "onboarded" not in st.session_state:
    st.title("📚 Snap & Study")
    st.caption("Upload your study material and email yourself the results.")

    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        email_address = st.text_input(
            "Email address",
            placeholder="student@example.com",
        )

        submitted = st.form_submit_button("Let's go 🚀")

    if submitted:
        name = name.strip()
        email_address = email_address.strip()

        if not name or not email_address:
            st.warning("Please fill in both your name and email address.")
        elif (
            "@" not in email_address
            or "." not in email_address.rsplit("@", 1)[-1]
        ):
            st.warning("Please enter a valid email address.")
        else:
            st.session_state.name = name
            st.session_state.email_address = email_address

            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )

            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()

    st.stop()


# Step 2: Chat interface
header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)

with header_col:
    st.title("📚 Snap & Study")

with button_col:
    send_disabled = len(st.session_state.messages) <= 2

    if st.button(
        "📧 Send to Email",
        disabled=send_disabled,
        use_container_width=True,
    ):
        with st.spinner("Preparing your summary..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])

        if summary.startswith("Sorry, something went wrong:"):
            st.error(summary)
        else:
            success, info = send_email(
                st.session_state.email_address,
                "Your Snap & Study Summary",
                summary,
            )

            if success:
                st.success("Sent! Check your email 📧")
            else:
                st.error(f"Couldn't send the email: {info}")


st.caption(
    f"Logged in as {st.session_state.name} - "
    f"updates go to {st.session_state.email_address}"
)


# Display conversation
if not st.session_state.messages:
    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name),
    )
else:
    for message in st.session_state.messages:
        render_message(message)


# Student input
user_input = st.chat_input(
    "Ask a question, or upload a photo of your study material",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf"],
)

if user_input:
    uploaded_file = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type

        if mime_type == "application/pdf":
            add_message(
                "user",
                "text",
                f"Uploaded PDF: {uploaded_file.name}",
            )
        else:
            add_message("user", "image", file_bytes)

        parts.append(
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type,
            )
        )

    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif uploaded_file is not None:
        parts.append(
            "Explain this study material in simple language "
            "and break down the key concepts step by step."
        )

    if parts:
        with st.spinner("Understanding your study material..."):
            answer = ask_gemini(parts)

        add_message("assistant", "text", answer)
