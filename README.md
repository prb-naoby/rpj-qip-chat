# QIP Data Assistant

An intelligent data analysis application tailored for QIP data, powered by **Google Gemini 2.5 Flash** and **PandasAI**. This tool allows users to upload datasets, perform natural language queries, and automatically transform data for analysis.

## Features

-   **AI-Powered Q&A**: Ask questions about your data in plain English using Google's Gemini 2.5 Flash model.
-   **Intelligent Data Transformation**: Automatically cleans and normalizes messy Excel/CSV data. The AI iteratively generates, executes, and validates transformation code, self-correcting if errors occur.
-   **Background Job Processing**: Long-running tasks (analysis, file processing) run asynchronously with real-time progress tracking via Redis.
-   **OneDrive Integration**: Directly browse, select, and upload files from your OneDrive for Business.
-   **Enhanced Security**: JWT-based authentication with path traversal protection and configurable secrets.
-   **Data Catalog**: Keeps track of uploaded files and their metadata using a local SQLite database.
-   **Modern Dashboard**: React/Next.js frontend with ShadCN UI components.
-   **Comprehensive Testing**: 113 automated tests covering security, API, and E2E flows.

## Prerequisites

-   **Docker Desktop** (Recommended)
-   **Google API Key** (Get one from [Google AI Studio](https://aistudio.google.com/))
-   **OneDrive Credentials** (Client ID, Secret, Tenant ID) - *Optional, for OneDrive features*

## Configuration

1.  Clone the repository.
2.  Copy `.env.example` to `.env`:
    ```bash
    cp .env.example .env
    ```
3.  Edit `.env` and set the following variables:
    ```ini
    # Required
    GOOGLE_API_KEY=your_google_api_key_here
    OPENAI_API_KEY=your_openai_api_key_here

    # Optional (for OneDrive Integration)
    MS_CLIENT_ID=your_client_id
    MS_CLIENT_SECRET=your_client_secret
    MS_TENANT_ID=your_tenant_id
    ONEDRIVE_DRIVE_ID=your_drive_id
    ONEDRIVE_ROOT_PATH=/path/to/folder
    ```

## Running the Application

### Option 1: Using Docker (Recommended)

The easiest way to run the app is using Docker Compose. This ensures all dependencies and the environment are correctly set up.

1.  Build and start the container:
    ```bash
    docker-compose up -d --build
    ```
2.  Open your browser and navigate to:
    ```
    http://localhost:1234
    ```

### Option 2: Running Locally

If you prefer to run it without Docker:

1.  **Backend (FastAPI)**:
    ```bash
    # Create virtual environment
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Run the API
    uvicorn api.main:app --reload --port 1234
    ```

2.  **Frontend (React/Next.js)**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes* | - | Google AI API key for Gemini |
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key (alternative to Google) |
| `JWT_SECRET_KEY` | **Production** | weak-default | **CRITICAL**: Set strong random 32-char string |
| `REDIS_HOST` | No | `redis` | Redis hostname for job queue |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | - | Redis password if required |
| `JOB_MAX_WORKERS` | No | `2` | Max concurrent background jobs |
| `UPLOAD_MAX_MB` | No | `25` | Max file upload size (MB) |
| `MS_CLIENT_ID` | No | - | Microsoft Azure Client ID (OneDrive) |
| `MS_CLIENT_SECRET` | No | - | Microsoft Azure Client Secret |
| `MS_TENANT_ID` | No | - | Microsoft Azure Tenant ID |
| `ONEDRIVE_DRIVE_ID` | No | - | OneDrive Drive ID |
| `ONEDRIVE_ROOT_PATH` | No | - | OneDrive folder path |

*At least one AI API key (Google or OpenAI) is required.

---

## Production Deployment Checklist

### 1. Security Configuration
- [ ] **Set JWT  Secret**:
  ```bash
  # Generate a strong random secret
  openssl rand -hex 32
  # Or use Python
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
  Add to `.env`:
  ```ini
  JWT_SECRET_KEY=your-generated-64-character-hex-string
  ```

- [ ] **Review CORS Settings**: In `api/main.py`, update allowed origins for production

### 2. Docker Deployment
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check health
curl http://localhost:1234/health

# View logs
docker-compose logs -f
```

### 3. Testing
```bash
# Run all tests (113 tests)
python -m pytest tests/ --ignore=tests/integration -v

# Quick smoke test
python -m pytest tests/test_security_enhancements.py -q
```

### 4. Data Persistence
- Data stored in Docker volume `data`
- Backup location: Check `docker volume inspect qip_data`

---

## Project Structure

```
.
├── api/
│   ├── main.py           # FastAPI application entry point
│   ├── routes.py         # API endpoints
│   ├── database.py       # User database operations
│   └── auth_utils.py     # JWT authentication utilities
├── app/
│   ├── data_analyzer.py  # AI-driven data transformation logic
│   ├── data_store.py     # SQLite database operations
│   ├── datasets.py       # File handling and dataframe management
│   ├── job_manager.py    # Background job processing
│   ├── redis_client.py   # Redis integration
│   ├── onedrive_client.py# OneDrive API integration
│   ├── qa_engine.py      # AI query engine wrapper
│   └── settings.py       # Configuration management
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   ├── lib/          # API client and utilities
│   │   └── store/        # Redux state management
│   └── package.json
├── tests/                # 113 automated tests
│   ├── test_security_enhancements.py
│   ├── test_api_routes.py
│   ├── test_e2e_flows.py
│   └── ...
├── data/                 # Storage for uploaded files and SQLite DB
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker services configuration
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables (not committed)
```

## Tech Stack

-   **Frontend**: React, Next.js 16, ShadCN UI, Redux Toolkit
-   **Backend**: FastAPI, Uvicorn
-   **AI Engine**: Google Gemini 2.5 Flash (via OpenAI-compatible API)
-   **Data Processing**: Pandas, PandasAI
-   **Database**: SQLite
-   **Job Queue**: Redis (async job processing)
-   **Security**: JWT, bcrypt, path traversal protection
-   **Testing**: Pytest (113 tests), FastAPI TestClient
-   **Containerization**: Docker, Docker Compose

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/token` | Login and get JWT token |
| GET | `/auth/me` | Get current user info |
| GET | `/api/tables` | List all cached tables |
| POST | `/api/chat/ask` | Ask a question about data |
| GET | `/api/onedrive/files` | List OneDrive files |
| POST | `/api/onedrive/load-sheet` | Load sheet from OneDrive |

## Troubleshooting

-   **Port Conflicts**: If port `1234` is in use, modify the `ports` section in `docker-compose.yml`.
-   **API Errors**: Ensure your `GOOGLE_API_KEY` or `OPENAI_API_KEY` is valid.
-   **OneDrive Issues**: Verify your Azure App Registration permissions if OneDrive sync fails.
-   **JWT Warnings**: If you see "Using default JWT_SECRET_KEY" warning, set `JWT_SECRET_KEY` in `.env`.
-   **Redis Connection**: Ensure Redis service is running (`docker-compose ps`). Jobs won't process without Redis.
-   **File Upload Fails**: Check `UPLOAD_MAX_MB` setting and disk space in Docker volume.

### Common Issues

**"Path traversal detected"**
- This is a security feature. Ensure table IDs are valid paths from the data directory.

**Background jobs stuck**
- Check Redis connection: `docker-compose logs qip-backend | grep -i redis`
- Verify `JOB_MAX_WORKERS` is set appropriately (default: 2)

**Tests failing**
- Install dev dependencies: `pip install -r requirements.txt`
- Ensure you're not running integration tests: `pytest tests/ --ignore=tests/integration`
