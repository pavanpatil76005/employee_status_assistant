import os
import re
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

# Load local .env when running in VS Code
load_dotenv(override=False)

# Load Streamlit Cloud secrets when deployed
SECRET_KEYS = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "BTP_CLIENT_ID",
    "BTP_CLIENT_SECRET",
    "BTP_AUTH_URL",
    "BTP_DESTINATION_URI",
    "BTP_DESTINATION_NAME",
]

try:
    for key in SECRET_KEYS:
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except StreamlitSecretNotFoundError:
    # Local development can use .env without a Streamlit secrets file.
    pass

# Import backend only AFTER secrets are loaded
from backend.employee_agent import (
    ask_employee_agent,
    get_employee_details,
    get_btp_destination,
)

# -------------------------------------------------
# Page settings
# -------------------------------------------------

st.set_page_config(
    page_title="Employee Status AI Assistant",
    page_icon="🤖",
    layout="wide",
)

# -------------------------------------------------
# Styling
# -------------------------------------------------

st.markdown(
    """
    <style>

    .main-title {
        font-size: 38px;
        font-weight: 700;
        margin-bottom: 0px;
    }

    .subtitle {
        font-size: 16px;
        color: #9ca3af;
        margin-bottom: 25px;
    }

    .employee-card {
        padding: 20px;
        border: 1px solid #333;
        border-radius: 12px;
        margin-top: 10px;
        margin-bottom: 20px;
    }

    .status-connected {
        color: #21c55d;
        font-weight: 600;
    }

    .status-error {
        color: #ef4444;
        font-weight: 600;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# System connection checks
# -------------------------------------------------

@st.cache_data(ttl=120)
def check_connections():

    status = {
        "btp": False,
        "azure": False,
        "gemini": False,
    }

    # SAP BTP Destination Service
    try:
        destination = get_btp_destination()

        if destination.get("destinationConfiguration"):
            status["btp"] = True

    except Exception:
        status["btp"] = False

    # Azure through SAP BTP
    try:
        employee = get_employee_details("EMP001")

        if (
            isinstance(employee, dict)
            and employee.get("employee_id") == "EMP001"
        ):
            status["azure"] = True

    except Exception:
        status["azure"] = False

    # Gemini configuration check
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        status["gemini"] = bool(api_key and api_key.strip())
    except Exception:
        status["gemini"] = False

    return status


# -------------------------------------------------
# Session
# -------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "employee" not in st.session_state:
    st.session_state.employee = None


# -------------------------------------------------
# Sidebar
# -------------------------------------------------

with st.sidebar:

    st.title("⚙️ Assistant Controls")

    st.write(
        "Employee information is retrieved through "
        "SAP BTP and Microsoft Azure."
    )

    st.divider()

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True
    ):

        st.session_state.messages = []
        st.session_state.employee = None
        st.rerun()

    if st.button(
        "🔄 Refresh Connections",
        use_container_width=True
    ):

        check_connections.clear()
        st.rerun()

    st.divider()

    st.caption("AI Model")
    st.write(
        os.getenv(
            "GEMINI_MODEL",
            "gemini-3.6-flash"
        )
    )

    st.caption("BTP Destination")
    st.write("EmployeeStatusAzureAPI")


# -------------------------------------------------
# Header
# -------------------------------------------------

st.markdown(
    """
    <div class="main-title">
        🤖 Employee Status AI Assistant
    </div>

    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------
# Connection status
# -------------------------------------------------

connections = check_connections()

# st.subheader("System Connection Status")

# col1, col2, col3 = st.columns(3)

# with col1:

#     if connections["btp"]:
#         st.success("✅ SAP BTP Connected")
#     else:
#         st.error("❌ SAP BTP Connection Failed")


# with col2:

#     if connections["azure"]:
#         st.success("✅ Microsoft Azure Connected")
#     else:
#         st.error("❌ Azure Connection Failed")


# with col3:

#     if connections["gemini"]:
#         st.success("✅ Gemini AI Connected")
#     else:
#         st.error("❌ Gemini AI Connection Failed")


st.divider()


# -------------------------------------------------
# Employee Information Card
# -------------------------------------------------

if st.session_state.employee:

    employee = st.session_state.employee

    st.subheader("👤 Employee Information")

    with st.container(border=True):

        row1_col1, row1_col2, row1_col3 = st.columns(3)

        with row1_col1:
            st.caption("Employee ID")
            st.write(
                f"**{employee.get('employee_id', '-')}**"
            )

        with row1_col2:
            st.caption("Employee Name")
            st.write(
                f"**{employee.get('name', '-')}**"
            )

        with row1_col3:
            st.caption("Status")

            employee_status = employee.get(
                "status",
                "-"
            )

            if employee_status.lower() == "active":
                st.success(employee_status)

            elif employee_status.lower() == "inactive":
                st.error(employee_status)

            else:
                st.warning(employee_status)


        row2_col1, row2_col2, row2_col3 = st.columns(3)

        with row2_col1:
            st.caption("Department")
            st.write(
                employee.get(
                    "department",
                    "-"
                )
            )

        with row2_col2:
            st.caption("Role")
            st.write(
                employee.get(
                    "role",
                    "-"
                )
            )

        with row2_col3:
            st.caption("Location")
            st.write(
                employee.get(
                    "location",
                    "-"
                )
            )

    st.divider()


# -------------------------------------------------
# Chat
# -------------------------------------------------

st.subheader("💬 Employee Assistant")

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.write(
            message["content"]
        )


user_message = st.chat_input(
    "Ask something like: What is the status of EMP001?"
)


# -------------------------------------------------
# Process User Question
# -------------------------------------------------

if user_message:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    with st.chat_message("user"):
        st.write(user_message)


    # Extract employee ID
    match = re.search(
        r"\bEMP\d+\b",
        user_message,
        re.IGNORECASE,
    )


    if not match:

        answer = (
            "Please provide an employee ID. "
            "For example: **EMP001**."
        )

        st.session_state.employee = None


    else:

        employee_id = (
            match.group(0).upper()
        )

        try:

            with st.spinner(
                "Retrieving employee data through SAP BTP..."
            ):

                employee = get_employee_details(
                    employee_id
                )


            # API returned error
            if (
                not employee
                or "error" in employee
            ):

                error_message = (
                    employee.get(
                        "error",
                        "Employee information could not be retrieved."
                    )
                    if isinstance(employee, dict)
                    else "Employee information could not be retrieved."
                )

                answer = (
                    f"⚠️ {error_message}"
                )

                st.session_state.employee = None


            else:

                st.session_state.employee = employee

                with st.spinner(
                    "Gemini is preparing the answer..."
                ):

                    answer = ask_employee_agent(
                        user_message,
                        employee_id,
                    )


        except Exception as error:

            answer = (
                "⚠️ Something went wrong while processing "
                "the request. Please check the system "
                "connections and try again."
            )

            st.session_state.employee = None

            print("CHAT ERROR:", repr(error), flush=True)


    with st.chat_message(
        "assistant"
    ):

        st.write(answer)


    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )

    st.rerun()
