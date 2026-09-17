# Employee Information & Status Assistant

Python Flask API backed by `data/employees.csv`. The frontend folder is currently empty.

## Run in Windows PowerShell

From the project folder, set up the environment once:

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the API:

```powershell
.\venv\Scripts\python.exe backend\app.py
```

Using the environment's Python directly avoids needing to activate PowerShell scripts.
Open http://127.0.0.1:5000/employees. Stop the server with Ctrl+C before starting another instance on the same port.
The Flask development-server warning is expected for local use.

## Endpoints

- `GET /`: API message.
- `GET /employees`: all employees and their count.
- `GET /employees?department=IT&location=Pune&status=Active`: optional case-insensitive filters, combined with AND.
- `GET /employees/EMP001`: case-insensitive employee ID lookup; returns 404 if absent.

The CSV requires employee_id, name, department, role, location, and status columns.
Employee IDs must be unique and required values must be nonempty. Missing or invalid data returns JSON with status 503; the cause is logged in the terminal. UTF-8 files with or without a byte-order mark are supported.

## Verify

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m pip check
```

## Generate sample data

This command replaces `data/employees.csv` with 100 random sample records. Back up any data you want to keep first.

```powershell
.\venv\Scripts\python.exe data\generate_employees.py
```

Importing the generator does not modify files. Debug mode is disabled by default; set `$env:FLASK_DEBUG = "1"` before starting the server to enable it locally.
