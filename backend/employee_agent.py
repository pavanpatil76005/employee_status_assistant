import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)
client = genai.Client(api_key=GEMINI_API_KEY)



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


def get_all_employees():
    """Get all employees through SAP BTP Destination Service."""

    try:
        destination = get_btp_destination()
        destination_config = destination.get("destinationConfiguration")

        if not destination_config:
            return {
                "error": "SAP BTP destination configuration was not found."
            }

        base_url = destination_config.get("URL")

        if not base_url:
            return {
                "error": "Azure API URL was not found in SAP BTP."
            }

        response = requests.get(
            f"{base_url.rstrip('/')}/employees",
            timeout=30
        )

        if response.status_code == 200:
            employees = response.json()

            # The Flask API wraps its list in {"count": ..., "employees": ...}.
            if isinstance(employees, dict):
                if "error" in employees:
                    return employees
                employees = employees.get("employees")

            if not isinstance(employees, list) or any(
                not isinstance(employee, dict) for employee in employees
            ):
                return {"error": "Employee data could not be retrieved."}

            return employees

        if response.status_code >= 500:
            return {
                "error": (
                    "The Azure employee service is temporarily unavailable. "
                    "Please try again later."
                )
            }

        return {
            "error": f"Employee API returned status {response.status_code}."
        }

    except requests.Timeout:
        return {"error": "The employee API request timed out."}

    except requests.RequestException as error:
        return {"error": f"Employee API connection error: {str(error)}"}

    except Exception as error:
        return {"error": f"Employee agent error: {str(error)}"}


def get_multiple_employee_details(employee_ids):
    """Fetch multiple employees in parallel, preserving the requested order."""

    if not employee_ids:
        return []

    results = {}

    with ThreadPoolExecutor(
        max_workers=min(10, len(employee_ids))
    ) as executor:
        future_map = {
            executor.submit(get_employee_details, employee_id): employee_id
            for employee_id in employee_ids
        }

        for future in as_completed(future_map):
            employee_id = future_map[future]

            try:
                results[employee_id] = future.result()
            except Exception as error:
                results[employee_id] = {"error": str(error)}

    return [results[employee_id] for employee_id in employee_ids]


def ask_employee_agent(question, employee_id=None):
    # Include malformed numeric IDs so validation reports them instead of
    # treating an invalid employee lookup as a dataset-wide question.
    employee_ids = re.findall(
        r"\bEMP\d+\b",
        question.upper()
    )

    if not employee_ids and employee_id:
        employee_ids = [str(employee_id).strip().upper()]

    # Remove duplicates while keeping order
    employee_ids = list(dict.fromkeys(employee_ids))

    errors = []

    # Questions about specific employees.
    if employee_ids:
        employee_ids = employee_ids[:10]
        employees = get_multiple_employee_details(employee_ids)
        valid_employees = []

        for employee_id_value, employee in zip(employee_ids, employees):
            if not isinstance(employee, dict) or not employee:
                errors.append(f"{employee_id_value} could not be retrieved.")
            elif "error" in employee:
                errors.append(employee["error"])
            else:
                valid_employees.append(employee)

        if not valid_employees:
            return "\n".join(errors)

        employee_information = []

        for employee in valid_employees:
            employee_information.append(
                f"""
Employee ID: {employee.get('employee_id')}
Name: {employee.get('name')}
Department: {employee.get('department')}
Role: {employee.get('role')}
Location: {employee.get('location')}
Status: {employee.get('status')}
"""
            )

        employee_data = "\n".join(employee_information)

        prompt = f"""
You are an Employee Information and Status Assistant.

User question:
{question}

Employee information:
{employee_data}

Understand exactly what the user is asking.

The user may ask different tasks for different employees.

Examples:
- status of one employee
- department of another employee
- location of another employee
- comparison between employees
- summary of multiple employees

Answer only using the employee data supplied above.
Only answer for employees whose information is supplied.
Retrieval errors for other employees will be shown separately.
Do not invent information.

Keep the answer clear, concise and professional.
"""

    # Search and analytics questions without an employee ID.
    else:
        employees = get_all_employees()

        if isinstance(employees, dict) and "error" in employees:
            return employees["error"]

        if not isinstance(employees, list):
            return "Employee data could not be retrieved."

        if not employees:
            return "No employees were found in the employee dataset."

        employee_information = []

        for employee in employees:
            employee_information.append(
                f"""
{employee.get('employee_id')} |
{employee.get('name')} |
Department: {employee.get('department')} |
Role: {employee.get('role')} |
Location: {employee.get('location')} |
Status: {employee.get('status')}
"""
            )

        employee_data = "\n".join(employee_information)

        prompt = f"""
You are an Employee Information and Analytics Assistant.

User question:
{question}

Employee dataset:
{employee_data}

Analyze the employee dataset and answer the user's question.

You can perform tasks such as:
- find employees by department
- find employees by status
- count employees
- combine department and status filters
- summarize employees
- compare groups

Examples:
"Show all employees in Sales"
"Show employees who are On Leave"
"How many employees are Active?"
"How many Sales employees are Active?"

Use only the supplied employee dataset.
Do not invent employees or values.

Keep the answer clear and professional.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        answer = response.text or (
            "The AI service returned no answer. Please try again."
        )
    except Exception as error:
        answer = (
            "The AI service could not prepare the response. "
            f"Please try again. ({type(error).__name__})"
        )

    return "\n\n".join([answer, *errors])
