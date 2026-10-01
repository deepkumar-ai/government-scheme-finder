"""Government Scheme Finder - single-file Streamlit app.

Run:  streamlit run app.py
Files needed in the same folder: scheme_data.json
API key: put GROQ_API_KEY in .streamlit/secrets.toml (or set it as an environment
variable). NEVER write the key in this file.
"""
import json
import os
import re
from pathlib import Path

import streamlit as st
from fpdf import FPDF
from groq import Groq
from streamlit_float import float_init

# ----------------------------------------------------------------- constants
DATA_FILE = Path(__file__).parent / "scheme_data.json"
MODEL = "openai/gpt-oss-20b"
SENIOR_AGE = 60
NATIONAL = {"All India", "Other state"}      # schemes available in every state
ALL_GENDERS = ["Male", "Female", "Other"]
ALL_CASTES = ["General", "OBC", "SC", "ST"]
OCCUPATIONS = ["Student", "Farmer", "Business", "Other"]
STATES = ["Other state", "Delhi", "Uttar Pradesh", "Maharashtra", "Bihar", "Rajasthan"]

STOPWORDS = {
    "the", "a", "an", "is", "are", "for", "to", "of", "in", "and", "or", "i", "me", "my",
    "can", "how", "what", "do", "does", "get", "scheme", "schemes", "apply", "tell",
    "about", "which", "who", "it", "this", "that",
}

# ---------------------------------------------------------------- page setup
st.set_page_config(
    page_title="Government Scheme Finder",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)
float_init()

# Dark glassmorphism theme. We only hide the footer: hiding the whole header would
# also hide the button that re-opens the sidebar (where the language selector is).
st.markdown("""
<style>
    h1 {
        background: -webkit-linear-gradient(45deg, #FF9933, #FFFFFF, #138808);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important;
        text-align: center;
        padding-bottom: 20px;
    }
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FF7E5F, #FEB47B) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        transition: all 0.3s ease !important;
        font-weight: bold !important;
        box-shadow: 0 4px 15px rgba(255, 126, 95, 0.4) !important;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 25px rgba(255, 126, 95, 0.6) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(10px) !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(255, 126, 95, 0.5) !important;
    }
    div[data-testid="stPopover"] > button {
        background: #FF7E5F !important;
        border-radius: 50px !important;
        height: 65px !important;
        width: 65px !important;
        font-size: 24px !important;
        padding: 0 !important;
        box-shadow: 0 10px 25px rgba(255, 126, 95, 0.5) !important;
        border: 2px solid rgba(255,255,255,0.2) !important;
    }
    div[data-testid="stPopoverBody"] {
        width: 400px !important;
        max-width: 90vw !important;
        height: 550px !important;
        max-height: 80vh !important;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ UI text
LANG_TEXT = {
    "English": {
        "title": "Government Scheme Finder 📜",
        "subtitle": "Discover tailored government schemes, track required documents, compare policies, and chat with our AI assistant.",
        "personal": "👤 Personal Details",
        "financial": "💼 Financial & Social Details",
        "location": "📍 Location",
        "name_label": "Full Name",
        "age": "Select Your Age",
        "gender_label": "Gender",
        "income": "Annual Income (₹)",
        "occupation": "Occupation / Status",
        "caste_label": "Social Category",
        "state": "Select State",
        "check_btn": "Check Eligibility",
        "found_msg": "Found {n} scheme(s) matching your profile!",
        "no_match": "No schemes found for your specific details. Try adjusting your filters.",
        "report_header": "📥 Download Eligibility Report (PDF)",
        "benefit": "💰 Financial Benefit:",
        "overview": "🎯 Overview:",
        "checklist_header": "📋 Document Checklist:",
        "apply": "🔗 Apply on Official Website",
        "verified": "Last verified: {d}",
        "compare_header": "⚖️ Scheme Comparison Tool",
        "compare_sub": "Select schemes below to compare their benefits and eligibility side-by-side.",
        "compare_select": "Select schemes to compare:",
        "col_name": "Scheme Name",
        "col_category": "Category",
        "col_benefit": "Financial Benefit",
        "col_income": "Max Income Limit",
        "no_limit": "No limit",
        "chat_header": "🤖 AI Scheme Assistant",
        "chat_sub": "Ask any questions regarding scheme documents, eligibility, benefits, or application procedures!",
        "chat_placeholder": "Ask about any scheme...",
        "thinking": "Searching database & thinking...",
        "no_key": "The AI assistant isn't set up yet: add GROQ_API_KEY to the Streamlit secrets.",
        "ai_error": "Could not reach the AI assistant. Please try again.",
        "data_error": "Could not load scheme_data.json. Check that the file exists and is valid JSON. Details:",
        "pdf_error": "The PDF report could not be created.",
        "disclaimer": "This information is a guide only. Always confirm eligibility and documents on the official scheme website before applying.",
    },
    "हिंदी": {
        "title": "सरकारी योजना फाइंडर 📜",
        "subtitle": "अपनी प्रोफ़ाइल के अनुसार सरकारी योजनाएं खोजें, दस्तावेज़ ट्रैक करें और AI सहायक से बात करें।",
        "personal": "👤 व्यक्तिगत जानकारी",
        "financial": "💼 आर्थिक और सामाजिक जानकारी",
        "location": "📍 स्थान",
        "name_label": "पूरा नाम",
        "age": "अपनी आयु चुनें",
        "gender_label": "लिंग",
        "income": "वार्षिक आय (₹)",
        "occupation": "व्यवसाय / स्थिति",
        "caste_label": "सामाजिक श्रेणी",
        "state": "राज्य चुनें",
        "check_btn": "पात्रता जांचें",
        "found_msg": "आपकी प्रोफ़ाइल के अनुसार {n} योजना(एं) मिलीं!",
        "no_match": "आपकी विशिष्ट जानकारी के अनुसार कोई योजना नहीं मिली। कृपया अपने फ़िल्टर बदलकर प्रयास करें।",
        "report_header": "📥 पात्रता रिपोर्ट डाउनलोड करें (PDF)",
        "benefit": "💰 आर्थिक लाभ:",
        "overview": "🎯 विवरण:",
        "checklist_header": "📋 दस्तावेज़ चेकलिस्ट:",
        "apply": "🔗 आधिकारिक वेबसाइट पर आवेदन करें",
        "verified": "अंतिम सत्यापन: {d}",
        "compare_header": "⚖️ योजना तुलना टूल",
        "compare_sub": "उनके लाभों और पात्रता की तुलना करने के लिए नीचे योजनाएं चुनें。",
        "compare_select": "तुलना के लिए योजनाएं चुनें:",
        "col_name": "योजना का नाम",
        "col_category": "श्रेणी",
        "col_benefit": "आर्थिक लाभ",
        "col_income": "अधिकतम आय सीमा",
        "no_limit": "कोई सीमा नहीं",
        "chat_header": "🤖 एआई योजना सहायक",
        "chat_sub": "योजना दस्तावेजों, पात्रता, लाभ या आवेदन प्रक्रियाओं से जुड़े कोई भी सवाल पूछें!",
        "chat_placeholder": "किसी भी योजना के बारे में पूछें...",
        "thinking": "योजनाएं खोजी जा रही हैं...",
        "no_key": "AI सहायक अभी सेट नहीं है: Streamlit secrets में GROQ_API_KEY जोड़ें।",
        "ai_error": "AI सहायक से संपर्क नहीं हो सका। कृपया दोबारा कोशिश करें।",
        "data_error": "scheme_data.json लोड नहीं हो सकी। जांचें कि फ़ाइल मौजूद है और सही JSON है। विवरण:",
        "pdf_error": "PDF रिपोर्ट नहीं बन सकी।",
        "disclaimer": "यह जानकारी केवल मार्गदर्शन के लिए है। आवेदन से पहले आधिकारिक वेबसाइट पर पात्रता और दस्तावेज़ ज़रूर जांचें。",
    },
}

selected_lang = st.sidebar.selectbox("🌐 Choose Language / भाषा चुनें", ["English", "हिंदी"])
t = LANG_TEXT[selected_lang]


# ------------------------------------------------------------ core functions
def rule(rules, key, default):
    """Read a rule from the JSON; a missing OR null value means 'no restriction'."""
    value = rules.get(key)
    return default if value is None else value


def is_eligible(profile, scheme):
    """True if the user's profile satisfies every rule of the scheme."""
    rules = scheme.get("eligibility", {})
    age, income = profile["age"], profile["income"]

    if not (rule(rules, "min_age", 0) <= age <= rule(rules, "max_age", 120)):
        return False
    if income > rule(rules, "max_income", float("inf")):
        return False

    # "Women" and "Senior Citizen" schemes depend on gender / age, not occupation.
    category = scheme.get("category", "General")
    category_ok = (
        category == "General"
        or category == profile["occupation"]
        or (category == "Women" and profile["gender"] == "Female")
        or (category == "Senior Citizen" and age >= SENIOR_AGE)
    )
    if not category_ok:
        return False

    state = scheme.get("state", "All India")
    if state not in NATIONAL and state != profile["state"]:
        return False

    if profile["gender"] not in scheme.get("target_gender", ALL_GENDERS):
        return False
    if profile["caste"] not in scheme.get("target_caste", ALL_CASTES):
        return False
    return True


def words(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def retrieve_relevant_schemes(query, data, eligible, top_k=3):
    """Keyword retrieval: score schemes by words shared with the question."""
    query_words = words(query) - STOPWORDS
    scored = []
    for scheme in data:
        name_words = words(scheme.get("scheme_name", ""))
        body = (
            f"{scheme.get('category', '')} {scheme.get('benefits', '')} "
            f"{scheme.get('financial_benefit', '')} {scheme.get('state', '')} "
            f"{scheme.get('required_documents', '')}"
        )
        score = 3 * len(query_words & name_words) + len(query_words & words(body))
        if score > 0 and scheme in eligible:   # small boost, only if already relevant
            score += 1
        scored.append((score, scheme))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best = [s for score, s in scored[:top_k] if score > 0]
    # Nothing matched (e.g. a Hindi question): fall back to eligible schemes, then any.
    return best or eligible[:top_k] or data[:top_k]


def pdf_safe(text):
    """Built-in PDF fonts only support Latin-1, so swap other characters for '?'."""
    return str(text).replace("₹", "Rs.").encode("latin-1", "replace").decode("latin-1")


def pdf_line(pdf, text, height=6, align="L"):
    pdf.multi_cell(0, height, pdf_safe(text), align=align, new_x="LMARGIN", new_y="NEXT")


def create_pdf_report(profile, schemes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf_line(pdf, "Government Scheme Eligibility Report", height=10, align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf_line(pdf, f"Prepared For: {profile.get('name', '').strip() or 'Applicant'}", align="C")

    pdf.set_font("Helvetica", "", 11)
    pdf_line(pdf, f"Age: {profile['age']} | Gender: {profile['gender']} | State: {profile['state']}", align="C")
    pdf_line(pdf, f"Income: Rs.{profile['income']} | Occupation: {profile['occupation']} | Category: {profile['caste']}", align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 12)
    pdf_line(pdf, f"Matched Schemes ({len(schemes)} Found):")
    pdf.set_font("Helvetica", "", 10)
    for number, s in enumerate(schemes, 1):
        pdf_line(pdf, f"{number}. {s.get('scheme_name', 'Unnamed scheme')}")
        pdf_line(pdf, f"   - Benefit: {s.get('financial_benefit', 'N/A')}")
        pdf_line(pdf, f"   - Official Link: {s.get('application_link', 'N/A')}")
        if s.get("last_verified"):
            pdf_line(pdf, f"   - Last verified: {s['last_verified']}")
        pdf.ln(4)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf_line(pdf, LANG_TEXT["English"]["disclaimer"], height=5)
    return bytes(pdf.output())


def get_api_key():
    """Streamlit secrets first, then the environment. Returns None if not set."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")


# ----------------------------------------------------------------- page body
# Safe title rendering with emoji gradient clipping fix
title_parts = t["title"].rsplit(" ", 1)
main_title = title_parts[0]
emoji = title_parts[1] if len(title_parts) > 1 else ""

st.markdown(
    f"<h1 style='text-align: center;'>{main_title} <span style='-webkit-text-fill-color: initial; background: none; display: inline-block;'>{emoji}</span></h1>",
    unsafe_allow_html=True
)
st.write(t["subtitle"])

# Load data (errors are shown, never hidden)
try:
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        scheme_data = json.load(file)
    if not isinstance(scheme_data, list):
        raise ValueError("the file must contain a list of schemes")
except Exception as error:
    scheme_data = []
    st.error(f"{t['data_error']} {error}")

# Session state (survives reruns)
defaults = {
    "eligible_schemes": [],
    "searched": False,
    "search_profile": {},
    "pdf_bytes": None,
    "messages": [],
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Input form
with st.container(border=True):
    st.markdown(f"#### {t['personal']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        user_name = st.text_input(t["name_label"], placeholder="John Doe")
    with col2:
        user_age = st.number_input(t["age"], min_value=0, max_value=120, value=18, step=1)
    with col3:
        user_gender = st.selectbox(t["gender_label"], ALL_GENDERS)

    st.markdown(f"#### {t['financial']}")
    col4, col5, col6 = st.columns(3)
    with col4:
        user_income = st.number_input(t["income"], min_value=0, max_value=10000000, value=300000, step=50000)
    with col5:
        user_occupation = st.selectbox(t["occupation"], OCCUPATIONS)
    with col6:
        user_caste = st.selectbox(t["caste_label"], ALL_CASTES)

    st.markdown(f"#### {t['location']}")
    user_state = st.selectbox(t["state"], STATES)

    st.markdown("<br>", unsafe_allow_html=True)
    check_button = st.button(t["check_btn"])

# On click: freeze the profile, filter, build the PDF once
if check_button:
    profile = {
        "name": user_name,
        "age": user_age,
        "gender": user_gender,
        "income": user_income,
        "occupation": user_occupation,
        "caste": user_caste,
        "state": user_state,
    }
    matched = [s for s in scheme_data if is_eligible(profile, s)]

    st.session_state.searched = True
    st.session_state.search_profile = profile
    st.session_state.eligible_schemes = matched
    st.session_state.pdf_bytes = None
    if matched:
        try:
            st.session_state.pdf_bytes = create_pdf_report(profile, matched)
        except Exception as error:
            st.error(f"{t['pdf_error']} ({error})")

# Results
if st.session_state.searched:
    st.divider()
    eligible_schemes = st.session_state.eligible_schemes

    if eligible_schemes:
        st.success(t["found_msg"].format(n=len(eligible_schemes)))

        if st.session_state.pdf_bytes:
            st.download_button(
                label=t["report_header"],
                data=st.session_state.pdf_bytes,
                file_name="scheme_eligibility_report.pdf",
                mime="application/pdf",
            )

        cols = st.columns(3)
        for index, scheme in enumerate(eligible_schemes):
            with cols[index % 3]:
                with st.container(border=True):
                    st.subheader(scheme.get("scheme_name", "Unnamed scheme"))
                    st.markdown(f"**{t['benefit']}** {scheme.get('financial_benefit', '-')}")
                    st.markdown(f"**{t['overview']}** {scheme.get('benefits', '-')}")

                    docs = scheme.get("required_documents", [])
                    if docs:
                        st.markdown(f"**{t['checklist_header']}**")
                        for doc_idx, doc in enumerate(docs):
                            st.checkbox(doc, key=f"{scheme.get('scheme_name')}_{doc}_{doc_idx}")

                    if scheme.get("last_verified"):
                        st.caption(t["verified"].format(d=scheme["last_verified"]))

                    link = scheme.get("application_link")
                    if link:
                        st.markdown("---")
                        st.markdown(f"[{t['apply']}]({link})")

        # Comparison tool
        st.divider()
        st.subheader(t["compare_header"])
        st.write(t["compare_sub"])

        by_name = {s.get("scheme_name", "Unnamed scheme"): s for s in eligible_schemes}
        picked = st.multiselect(t["compare_select"], list(by_name))
        if picked:
            rows = []
            for name in picked:
                s = by_name[name]
                limit = s.get("eligibility", {}).get("max_income")
                rows.append({
                    t["col_name"]: name,
                    t["col_category"]: s.get("category", "-"),
                    t["col_benefit"]: s.get("financial_benefit", "-"),
                    t["col_income"]: f"₹{limit:,}" if isinstance(limit, (int, float)) else t["no_limit"],
                })
            st.table(rows)
    else:
        st.warning(t["no_match"])

st.caption(t["disclaimer"])

# ------------------------------------------------------------ AI assistant
chat_container = st.container()
with chat_container:
    with st.popover("💬"):
        st.subheader(t["chat_header"])
        st.caption(t["chat_sub"])

        msg_container = st.container(height=350)
        for message in st.session_state.messages:
            with msg_container.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input(t["chat_placeholder"]):
            with msg_container.chat_message("user"):
                st.markdown(prompt)

            with msg_container.chat_message("assistant"):
                api_key = get_api_key()
                if not api_key:
                    st.warning(t["no_key"])
                else:
                    with st.spinner(t["thinking"]):
                        try:
                            eligible = st.session_state.eligible_schemes
                            retrieved = retrieve_relevant_schemes(prompt, scheme_data, eligible)

                            profile_context = ""
                            if st.session_state.searched and st.session_state.search_profile:
                                p = st.session_state.search_profile
                                names = ", ".join(s.get("scheme_name", "?") for s in eligible)
                                profile_context = (
                                    f"User Profile: Age: {p['age']}, Gender: {p['gender']}, "
                                    f"Income: {p['income']}, Occupation: {p['occupation']}, "
                                    f"Category: {p['caste']}, State: {p['state']}. "
                                    f"Schemes this user is eligible for: {names or 'none'}."
                                )

                            system_content = (
                                "You are an expert Indian government schemes consultant.\n"
                                "CRITICAL RULE: Answer strictly and only from the retrieved scheme context "
                                "below. Do not assume or make up facts. If the information is not in the "
                                "context, say you don't have the details and suggest visiting the official "
                                "website.\n"
                                "Reply in the same language the user writes in.\n\n"
                                f"{profile_context}\n\n"
                                f"Retrieved Schemes Context:\n{json.dumps(retrieved, ensure_ascii=False)}"
                            )

                            history = st.session_state.messages[-6:]
                            messages = (
                                [{"role": "system", "content": system_content}]
                                + history
                                + [{"role": "user", "content": prompt}]
                            )

                            completion = Groq(api_key=api_key).chat.completions.create(
                                model=MODEL, messages=messages, temperature=0.2
                            )
                            reply = completion.choices[0].message.content
                            st.markdown(reply)

                            # Save the exchange only if it succeeded, so history never has gaps
                            st.session_state.messages.append({"role": "user", "content": prompt})
                            st.session_state.messages.append({"role": "assistant", "content": reply})
                        except Exception as error:
                            print(f"AI error: {error!r}")   # full details in the server log
                            st.error(f"{t['ai_error']} ({type(error).__name__})")

# Float the chat button at the bottom-right
chat_container.float("bottom: 30px; right: 30px; width: max-content; z-index: 999999;")