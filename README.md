# StudyHub
A study OS for CIE A level students

<img width="1280" height="720" alt="studyhub-board" src="https://github.com/user-attachments/assets/f89ba772-2066-48b7-8555-df0101b10512" />


## About the App
  - StudyHub is a study OS for A level/CIE students where you can track your subjects, deadlines and everything on one draggable, zoomable board
  - You can walk around the board, upload notes and it auto sorts them into your subject category using an AI algorithm
  - You can solve past papers right on the board and get marked by a unique AI method, and it even logs your mistakes so you know what to improve next time
  - The app is still early in development so alot of things will change

## Running the App
  - `Local Setup`:
  - 1. **Prerequisite**: Python 3.10 or newer (Windows/Linux/macOS all work)
  - 2. Clone the repo and cd into it
  - 3. Create a venv and install deps:
    - `python -m venv venv`
    - `source venv/bin/activate` (or `venv\Scripts\activate` on windows)
    - `pip install -r requirements.txt`
  - 4. Copy `.env.example` to `.env` and fill in your keys
  - 5. Run `python seed.py` to create the database and a demo account
  - 6. Run `flask --app app run --debug`
  - 7. Open http://127.0.0.1:5000 and log in with demo / demo1234
  - `Docker`:
    - 1. Build the image: `docker build -t studyhub .`
    - 2. Run it: `docker run -p 8000:8000 --env-file .env studyhub`
    - * note: needs poppler-utils which the Dockerfile already installs for the past paper OCR stuff
  - * note: do not run the app with admin level access on windows or it can cause issues with the database file

## Tech Stack
- Python and Flask for the backend
- Flask-SQLAlchemy with SQLite (PostgreSQL also works via DATABASE_URL)
- Flask-Login for auth
- Jinja2 templates and Bootstrap 5 for the UI
- Jev AI API (hackclub) for auto sorting notes and marking past papers
- CAIE past paper archive for fetching papers
- Docker and gunicorn for deployment

## Feature List
  - We have proper auth, signup and login with password hashing
  - We have subjects management and deadlines with countdown
  - We have a big board/OS vibe, pan/zoom/move, you can drag things around
  - We have upload of any notes/files and it auto sorts them using a python algorithm + AI
  - We have past papers, you can fetch them from the CAIE archive or upload your own inclduing your own notes
  - We have an AI marker that grades your answers against the mark scheme
  - We have an error log that records your mistakes from past papers automatically
  - And lastly we have a dashboard with upcoming and past deadlines

## Project Status
  - The app is still a work in progress
  - Some systems are working but still need polish
  - The UI and tutorial are not finished yet

## Roadmap
  - Finish the board UI with proper text and icons
  - Add a tutorial so new users know what to do
  - Improve the overall UI and mobile support
  - Add flashcards from mistakes automatically
  - More content and polish later on

## Contributing
  - The project is not open for contributions right now
  - If you find a bug or have a suggestion feel free to open an issue

#Credits
  - Mirza Ali Akbar

#Known Bugs and issues
  - The UI is not great, just alright
  - The tag doesn't appear properly.
  - For past paper fetcher right now the OCR fallback is slow and not great
  - There is no tutorial
  - App is incomplete
  - Duplicate item has a bug where it references undefined variables

#License
  - This project is licensed under the [MIT License](LICENSE)
