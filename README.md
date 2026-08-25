# TransferATS

TransferATS is a FastAPI backend with a React/Vite frontend. The backend stores data in PostgreSQL and exposes interactive API documentation through Swagger UI.

Production: <https://transferats.neuroforge-sol.com/>

## Quick start

Open Docker Desktop, then run these commands from the repository root.

Start PostgreSQL:

```powershell
docker start transferats-db
```

Start the backend in its own PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second PowerShell terminal:

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

Then open <http://127.0.0.1:5173>. The backend is at <http://127.0.0.1:8000>, and its interactive API documentation is at <http://127.0.0.1:8000/docs>. Use `Ctrl+C` in each terminal to stop its server.

## Local development setup

The verified local setup uses:

- Python 3.11.2 in a project-local `.venv`
- Node.js with npm 11
- PostgreSQL in the existing Docker container `transferats-db`
- Backend at <http://127.0.0.1:8000>
- API documentation at <http://127.0.0.1:8000/docs>
- Frontend at <http://127.0.0.1:5173>

Anaconda is installed on the development machine, but this project was not associated with a dedicated Conda environment. A local virtual environment is used so the backend dependencies remain isolated and the setup is reproducible.

## First-time setup (Windows PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script, either run the Python executable directly as shown in the daily startup commands below, or allow scripts only for the current PowerShell process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install the frontend packages:

```powershell
Set-Location frontend
npm.cmd install
Set-Location ..
```

On this machine, use `npm.cmd` rather than `npm`; the PowerShell execution policy blocks the `npm.ps1` wrapper.

## Environment variables

Copy `.env.example` to `.env` and replace the placeholders:

```powershell
Copy-Item .env.example .env
```

The backend reads `.env` from the repository root. The expected database URL format is:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/transferats
```

The OpenAI, Groq, and O*NET credentials are needed by the features that call those services. Never commit `.env`; it is ignored by Git.

The frontend defaults to the local backend. To override it, copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_BASE_URL`.

## Start the application

1. Start Docker Desktop, then start and verify the existing PostgreSQL container:

```powershell
docker start transferats-db
docker ps --filter "name=transferats-db"
```

The container maps PostgreSQL to `localhost:5432`. Its restart policy is currently `no`, so it normally needs to be started again after Docker Desktop or the computer restarts.

2. In a PowerShell window at the repository root, start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

3. In a second PowerShell window, start the frontend:

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173>. Stop either development server with `Ctrl+C` in its terminal.

## Quick verification

With the services running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:5173/ -UseBasicParsing | Select-Object StatusCode
```

The expected backend response is `status: healthy`, and the frontend status code should be `200`.

To confirm the frontend production bundle can compile:

```powershell
Set-Location frontend
npm.cmd run build
```

## Troubleshooting

- **Backend cannot connect to PostgreSQL:** confirm `transferats-db` is running, port `5432` is published, and the username, password, and database name in `.env` match the container.
- **Port already in use:** check the process with `Get-NetTCPConnection -LocalPort 8000` or `Get-NetTCPConnection -LocalPort 5173` before choosing another port.
- **`npm.ps1` cannot be loaded:** use `npm.cmd` in PowerShell.
- **Missing Python module:** ensure commands use `.\.venv\Scripts\python.exe`, then reinstall with `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
