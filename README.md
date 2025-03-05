# Resume Analysis Project

## Project Overview
A Flask-based web application that analyzes resumes against job descriptions using AI. The application extracts information from resumes (PDF/DOCX), compares them with job requirements, and provides detailed scoring and analysis.

## Features
- Resume parsing (PDF and DOCX support)
- AI-powered resume analysis using Google's Generative AI
- Secure login system
- Detailed scoring system (out of 25 points)
- Visual score representation
- History of previous analyses
- PDF and DOCX file support

## Prerequisites
- Python 3.x
- pip (Python package installer)
- Google API Key for Gemini

## Environment Variables
Create a `.env` file in the root directory with:
```
FLASK_SECRET_KEY=your-secret-key-here
APP_PASSWORD=your-password-here
GOOGLE_API_KEY=your-gemini-api-key
```

## Setup Instructions

1. **Clone the repository**
```sh
git clone <repository-url>
cd Resume-Analysis
```

2. **Create a virtual environment**
```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```sh
pip install -r requirements.txt
```

4. **Set up environment variables**
- Create `.env` file as described above
- Replace placeholder values with your actual credentials

## Running the Application

1. **Start the application**
```sh
python app.py
```

2. **Access the application**
- Open your web browser and go to `http://localhost:5000`
- Login using the password set in APP_PASSWORD

## Project Structure
```
Resume-Analysis/
├── app.py                  # Main application file
├── requirements.txt        # Python dependencies
├── resume_results.json     # Analysis results storage
├── .env                   # Environment variables
├── .gitignore            # Git ignore rules
├── templates/             # HTML templates
│   ├── index.html        # Upload page
│   ├── login.html        # Login page
│   ├── result.html       # Individual result page
│   └── results.html      # All results page
└── uploads/              # Upload directory for resumes
```

## How It Works
1. User logs in with configured password
2. Uploads a resume (PDF/DOCX) and provides job description
3. Application extracts text from the resume
4. Google's Generative AI analyzes the content
5. System generates:
   - Structured information extraction
   - Skills gap analysis
   - Detailed scoring (out of 25)
   - Visual representation of scores
   - Recommendations
   - Critical missing qualifications
   - Areas for improvement

## Scoring Criteria
The system evaluates candidates on five dimensions (1-5 points each):
1. Educational Background
2. Technical Skills Match
3. Relevant Experience
4. Domain Expertise & Advanced Technologies
5. Soft Skills & Culture Fit

## Security Notes
- Ensure proper permissions on the uploads directory
- Change default password and secret key
- Use HTTPS in production
- Keep API keys secure

## License
This project is licensed under the MIT License.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
