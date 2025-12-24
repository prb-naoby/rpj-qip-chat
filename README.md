# QIP Data Assistant

An intelligent data analysis application tailored for QIP data, powered by **Google Gemini 2.5 Flash** and **PandasAI**. This tool allows users to upload datasets, perform natural language queries, and automatically transform data for analysis.

## Features

-   **AI-Powered Q&A**: Ask questions about your data in plain English using Google's Gemini 2.5 Flash model.
-   **Intelligent Data Transformation**: Automatically cleans and normalizes messy Excel/CSV data. The AI iteratively generates, executes, and validates transformation code, self-correcting if errors occur.
-   **OneDrive Integration**: Directly browse, select, and upload files from your OneDrive for Business.
-   **Secure Access**: JWT-based authentication to protect your data.
-   **Data Catalog**: Keeps track of uploaded files and their metadata using a local SQLite database.
-   **Modern Dashboard**: React/Next.js frontend with ShadCN UI components.

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
-   **Containerization**: Docker

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
