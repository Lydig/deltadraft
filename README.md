DeltaDraft

A real-time League of Legends draft analysis and recommendation tool.
Core Architecture

The project is a decoupled system composed of three main parts:

    Frontend (Electron Application): The desktop application used by the end-user. It runs on their machine and makes API requests to the backend.

    Backend (Vercel Server): A serverless Python Flask API hosted on Vercel. It receives requests from the user's application, fetches the appropriate dataset from cloud storage, and returns the analysis.

    Data Pipeline (GitHub Actions & Cloudflare R2): An automated, scheduled process that scrapes the latest data from LoLalytics, processes it, and uploads it to a cloud storage bucket.

Technology Stack

    Frontend: Electron, HTML, CSS, JavaScript (no framework)

    Backend: Python (Flask), Vercel (hosting), Gunicorn (web server)

    Data Pipeline: Python, GitHub Actions (automation), Cloudflare R2 (S3-compatible object storage)

Component Breakdown
1. Frontend (Electron App)

    Location: /desktop-app/

    Description: A desktop application built with web technologies. It is the only component the end-user interacts with directly.

    Key Files:

        index.html: The main UI and application logic.

        main.js: The Electron main process. Handles window creation, LCU connection, and secure file system access for settings/favorites.

        preload.js: Securely exposes backend functions from main.js to the index.html frontend.

        package.json: Defines dependencies and build scripts.

To Run Locally:
    
    cd desktop-app
    npm install
    npm start

  

To Build Installer:
        
    cd desktop-app
    npm run dist 
    # Installer will be in /desktop-app/dist/

      

2. Backend (Vercel Server)

    Location: /backend/

    Description: A Python Flask API that serves data from Cloudflare R2. It is deployed as a serverless function on Vercel.

    Key Files:

        server.py: The Flask application. Contains all API endpoints (/recommend, /role_data, etc.) and the logic for fetching and caching data from R2.

        vercel.json: Vercel's configuration file. Tells Vercel how to build and route requests to the Python application.

        requirements.txt: A list of Python dependencies required for the server.

    Deployment: Deployment to production is automatic. Pushing a commit to the main branch on GitHub will trigger a new deployment on Vercel.

3. Data Pipeline (GitHub Actions)

    Location: /backend/scripts/ and /.github/workflows/

    Description: This system automatically scrapes data from LoLalytics and uploads it to the Cloudflare R2 bucket. It runs on a schedule, requiring no manual intervention.

    Key Files:

        backend/scripts/scrape_lolalytics.py: The Python script that performs the scraping and uploads the data to R2.

        .github/workflows/update_data.yml: The GitHub Actions configuration file. Defines the schedule (cron: '0 6,18 * * *') and the steps to run the scraper.

    Manual Trigger: You can run the data update job manually by going to the "Actions" tab on the GitHub repository, selecting "Update LoLalytics Dataset", and clicking "Run workflow".

Key Credentials & Environment Variables

DO NOT COMMIT SECRET KEYS TO THE REPOSITORY. They must be stored as environment variables on their respective platforms.
For the Data Pipeline (GitHub Actions):

These are required for the scraper to upload data to R2.

    Location: GitHub Repo -> Settings -> Secrets and variables -> Actions

    Secrets Needed:

        CLOUDFLARE_ACCOUNT_ID

        AWS_ACCESS_KEY_ID

        AWS_SECRET_ACCESS_KEY

For the Backend Server (Vercel):

These are required for the server to read data from R2.

    Location: Vercel Project -> Settings -> Environment Variables

    Variables Needed:

        CLOUDFLARE_ACCOUNT_ID

        AWS_ACCESS_KEY_ID

        AWS_SECRET_ACCESS_KEY

Development Workflow

    To Update the UI or Frontend Logic:

        Modify files in /desktop-app/.

        Test locally using npm start.

        When complete, build a new installer with npm run dist and distribute the new .exe.

    To Update the Backend API Logic:

        Modify files in /backend/ (likely server.py).

        Test locally by pointing the API_BASE_URL in index.html to http://127.0.0.1:5000 and running the local Python server.

        When complete, revert the API_BASE_URL to the Vercel URL, commit, and push to main. Vercel will redeploy automatically.

    To Update the Data Scraper:

        Modify backend/scripts/scrape_lolalytics.py.

        Commit and push to main. The next scheduled GitHub Action will use the new script.

Project Structure

    
/deltadraft/
├── .github/
│   └── workflows/
│       └── update_data.yml      # GitHub Action for scraping
├── backend/
│   ├── scripts/
│   │   └── scrape_lolalytics.py # The data scraping and R2 upload script
│   ├── server.py                # The Vercel/Flask backend API
│   ├── requirements.txt         # Python dependencies
│   └── vercel.json              # Vercel deployment config
└── desktop-app/
    ├── main.js                  # Electron main process (LCU, settings)
    ├── preload.js               # Electron security bridge
    ├── index.html               # Frontend UI and logic
    ├── package.json             # Node.js dependencies and scripts
    └── ...

  