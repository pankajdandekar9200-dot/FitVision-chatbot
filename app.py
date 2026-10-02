
import json

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)



# MODEL


MODEL_NAME = "gemini-3.5-flash"



# PAGE CONFIG


st.set_page_config(
    page_title="FitVision",
    page_icon="🥗",
)

# SECRETS


GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


# GEMINI CLIENT


@st.cache_resource
def get_gemini_client():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


gemini_client = get_gemini_client()



# TWILIO CLIENT


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )


twilio_client = get_twilio_client()


# RENDER MESSAGE


def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":

            st.write(message["content"])

        elif message["kind"] == "image":

            st.image(
                message["content"],
                use_container_width=True
            )



# ADD MESSAGE


def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
        }
    )

    render_message(
        st.session_state.messages[-1]
    )



# ASK GEMINI

def ask_gemini(parts):

    try:

        response = st.session_state.chat.send_message(
            parts
        )

        return response.text

    except Exception as error:

        return f"Sorry, something went wrong: {error}"

# CLEAN WHATSAPP TEXT


def clean_whatsapp_text(text):

    if not text:

        return "No nutrition summary available."

    text = " ".join(
        text.split()
    )

    return (
        text[:1500] + "..."
        if len(text) > 1500
        else text
    )


# SEND WHATSAPP


def send_whatsapp(
    to_number,
    user_name,
    summary
):

    try:

        to_number = to_number.strip()

        if to_number.startswith("whatsapp:"):

            to_number = to_number.replace(
                "whatsapp:",
                "",
                1
            )

        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary),
            },
            ensure_ascii=False,
        )

        message = twilio_client.messages.create(

            from_=TWILIO_WHATSAPP_FROM,

            to=f"whatsapp:{to_number}",

            content_sid=TWILIO_CONTENT_SID,

            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:

        return False, str(error)


# ONBOARDING


if "onboarded" not in st.session_state:

    st.title("🥗 FitVision")

    st.caption(
        "Snap it. Track it. Text yourself the results."
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name"
        )

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help=(
                "This is the number FitVision "
                "will text your summary to."
            ),
        )

        submitted = st.form_submit_button(
            "Let's go 🚀"
        )

    if submitted:

        if (
            not name.strip()
            or not whatsapp_number.strip()
        ):

            st.warning(
                "Please fill in both your name "
                "and WhatsApp number."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

         
            st.session_state.chat = (
                gemini_client.chats.create(

                    model=MODEL_NAME,

                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()



# CHAT HEADER


header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:

    st.title("🥗 FitVision")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 2
    )

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your day..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )



# USER INFORMATION


st.caption(
    f"Logged in as "
    f"{st.session_state.name} - "
    f"updates go to "
    f"{st.session_state.whatsapp_number}"
)


# SHOW MESSAGE HISTORY


if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# CHAT INPUT


user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
    ],
)



# HANDLE INPUT


if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []



    # PHOTO


    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )



    # TEXT

    if text:

        add_message(
            "user",
            "text",
            text
        )

        parts.append(text)


    # PHOTO WITHOUT TEXT
 

    elif photo is not None:

        parts.append(
            "What is this meal? "
            "Give me the calories and macros."
        )


 
    # SEND TO GEMINI
  

    with st.spinner(
        "Crunching the numbers..."
    ):

        answer = ask_gemini(parts)


    # SHOW AI RESPONSE
   

    add_message(
        "assistant",
        "text",
        answer
    )

