import os
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

# -----------------------------
# Gemini configuration
# -----------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


# -----------------------------
# SAP BTP Destination Service
# -----------------------------
BTP_CLIENT_ID = os.getenv("BTP_CLIENT_ID")
BTP_CLIENT_SECRET = os.getenv("BTP_CLIENT_SECRET")
BTP_AUTH_URL = os.getenv("BTP_AUTH_URL")
BTP_DESTINATION_URI = os.getenv("BTP_DESTINATION_URI")
BTP_DESTINATION_NAME = os.getenv(
    "BTP_DESTINATION_NAME",
    "EmployeeStatusAzureAPI"
)


def get_btp_token():
    """Get OAuth token for SAP BTP Destination Service."""

    token_url = f"{BTP_AUTH_URL.rstrip('/')}/oauth/token"

    response = requests.post(
        token_url,
        auth=(BTP_CLIENT_ID, BTP_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=15
    )

    response.raise_for_status()

    return response.json()["access_token"]


def get_btp_destination():
    """Get EmployeeStatusAzureAPI configuration from SAP BTP."""

    token = get_btp_token()

    destination_url = (
        f"{BTP_DESTINATION_URI.rstrip('/')}"
        f"/destination-configuration/v1/destinations/"
        f"{BTP_DESTINATION_NAME}"
    )

    response = requests.get(
        destination_url,
        headers={
            "Authorization": f"Bearer {token}"
        },
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def get_employee_details(employee_id):
    """
    Get employee information using the URL stored
    in SAP BTP Destination Service.
    """

    try:
        destination = get_btp_destination()

        destination_config = destination["destinationConfiguration"]

        base_url = destination_config["URL"].rstrip("/")

        employee_url = (
            f"{base_url}/employees/{employee_id.upper()}"
        )

        response = requests.get(
            employee_url,
            timeout=15
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            return {
                "error": f"Employee {employee_id} was not found."
            }

        return {
            "error": (
                f"Employee API returned status "
                f"{response.status_code}"
            )
        }

    except requests.RequestException as error:
        return {
            "error": f"Connection error: {str(error)}"
        }

    except Exception as error:
        return {
            "error": f"Agent error: {str(error)}"
        }


def ask_employee_agent(question, employee_id):
    employee = get_employee_details(employee_id)

    if "error" in employee:
        return employee["error"]

    prompt = f"""
You are an Employee Status Assistant.

User question:
{question}

Employee information:
Employee ID: {employee['employee_id']}
Name: {employee['name']}
Department: {employee['department']}
Role: {employee['role']}
Location: {employee['location']}
Status: {employee['status']}

Answer the user's question using only this employee information.
Keep the answer simple and professional.
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    return response.text
