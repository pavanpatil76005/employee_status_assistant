import os
import re
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

# -----------------------------
# Gemini configuration
# -----------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)
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
    Get employee information using SAP BTP Destination Service.
    """

    # Clean employee ID
    employee_id = str(employee_id).strip().upper()

    # Validate employee ID format
    if not re.fullmatch(r"EMP\d{3}", employee_id):
        return {
            "error": (
                "Invalid employee ID. "
                "Please use a format like EMP001."
            )
        }

    try:
        # Get Azure API destination from SAP BTP
        destination = get_btp_destination()

        destination_config = destination.get(
            "destinationConfiguration"
        )

        if not destination_config:
            return {
                "error": "SAP BTP destination configuration was not found."
            }

        base_url = destination_config.get("URL")

        if not base_url:
            return {
                "error": "Azure API URL was not found in SAP BTP."
            }

        base_url = base_url.rstrip("/")

        employee_url = (
            f"{base_url}/employees/{employee_id}"
        )

        response = requests.get(
            employee_url,
            timeout=15
        )

        # Employee found
        if response.status_code == 200:
            return response.json()

        # Employee does not exist
        if response.status_code == 404:
            return {
                "error": (
                    f"Employee {employee_id} was not found. "
                    "Please check the employee ID and try again."
                )
            }

        # Azure/server error
        if response.status_code >= 500:
            return {
                "error": (
                    "The Azure employee service is temporarily unavailable. "
                    "Please try again later."
                )
            }

        return {
            "error": (
                f"Employee API returned status "
                f"{response.status_code}."
            )
        }

    except requests.Timeout:
        return {
            "error": (
                "The employee API request timed out. "
                "Please try again."
            )
        }

    except requests.ConnectionError:
        return {
            "error": (
                "Could not connect to the employee API."
            )
        }

    except requests.RequestException as error:
        return {
            "error": (
                f"Employee API connection error: {str(error)}"
            )
        }

    except Exception as error:
        return {
            "error": (
                f"Employee agent error: {str(error)}"
            )
        }


def ask_employee_agent(question, employee_id=None):
    # Find all employee IDs in the user's question
    employee_ids = re.findall(
        r"\bEMP\d+\b",
        question.upper()
    )

    # If no ID was found in the question,
    # use the employee_id passed by Streamlit
    if not employee_ids and employee_id:
        employee_ids = [employee_id.upper()]

    # Remove duplicates while keeping order
    employee_ids = list(dict.fromkeys(employee_ids))

    if not employee_ids:
        return "Please provide an employee ID such as EMP001."

    # Limit one request to 10 employees
    employee_ids = employee_ids[:10]

    employees = []
    errors = []

    for emp_id in employee_ids:
        employee = get_employee_details(emp_id)

        if "error" in employee:
            errors.append(employee["error"])
        else:
            employees.append(employee)

    if not employees:
        return "\n".join(errors)

    employee_information = []

    for employee in employees:
        employee_information.append(
            f"""
Employee ID: {employee['employee_id']}
Name: {employee['name']}
Department: {employee['department']}
Role: {employee['role']}
Location: {employee['location']}
Status: {employee['status']}
"""
        )

    employee_data = "\n".join(employee_information)

    prompt = f"""
You are an Employee Status Assistant.

User question:
{question}

Employee information:
{employee_data}

Answer the user's question using only the employee information above.

If multiple employees are requested, clearly give the details
for each employee separately.

Keep the answer simple and professional.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text
