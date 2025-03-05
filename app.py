from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import json
import pdfplumber
import docx
import google.generativeai as genai
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import re
import logging
import uuid
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FILE'] = 'resume_results.json'
# Change this to a secure random value in production
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')
# Set this to your desired password
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'your-password-here')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Google Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', "your-api-key-here")
genai.configure(api_key=GOOGLE_API_KEY)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == APP_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/results')
@login_required
def list_results():
    results = load_results()
    # Sort results by timestamp in descending order
    sorted_results = dict(sorted(results.items(), 
                               key=lambda x: x[1].get('timestamp', ''), 
                               reverse=True))
    return render_template('results.html', results=sorted_results)

@app.route('/result/<result_id>')
@login_required
def view_result(result_id):
    results = load_results()
    
    if result_id not in results:
        return render_template('result.html', error="Result not found")
        
    result = results[result_id]
    
    return render_template(
        'result.html', 
        json_output=result['json_output'],
        chart_image=result['chart_image'],
        job_description=result['job_description'],
        result_id=result_id
    )

@app.route('/process', methods=['POST'])
@login_required
def process():
    if 'resume' not in request.files or not request.form.get('job_description'):
        return render_template('result.html', error="Please upload a resume and provide a job description.")

    resume_file = request.files['resume']
    job_description = request.form['job_description']
    
    # Generate unique ID for this analysis
    result_id = str(uuid.uuid4())
    
    # Create unique filename to keep in uploads folder
    filename_parts = os.path.splitext(resume_file.filename)
    unique_filename = f"{filename_parts[0]}_{result_id}{filename_parts[1]}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    # Save uploaded file with unique name
    resume_file.save(file_path)

    # Extract text based on file type
    if resume_file.filename.lower().endswith('.pdf'):
        resume_text = extract_text_from_pdf(file_path)
    elif resume_file.filename.lower().endswith('.docx'):
        resume_text = extract_text_from_docx(file_path)
    else:
        os.remove(file_path)
        return render_template('result.html', error="Unsupported file format. Please upload a PDF or DOCX file.")

    if not resume_text.strip():
        os.remove(file_path)
        return render_template('result.html', error="No text extracted from the resume.")

    # Prepare prompt for Gemini
    prompt = f"""
    Extract structured information from the following resume text and job description, then perform a HIGHLY CRITICAL evaluation of how well the resume matches the specific job requirements. Apply rigorous standards to identify only truly exceptional candidates. Return everything in JSON format with special attention to the 'fit_score' object structure.
    
    ### Instructions for Extraction:
    Extract the following fields from the resume:
    - Name
    - Contact Information (Email, Phone, LinkedIn)
    - Summary
    - Skills (LIST format, NOT long phrases)
    - Work Experience (LIST of dictionaries with 'Company', 'Role', 'Duration', 'Description' – Each Description MUST be 3+ sentences)
    - Education (LIST of dictionaries with 'Degree', 'Institution', 'Year')
    - Certifications (LIST format)
    - Projects (LIST of dictionaries with 'Title', 'Duration', 'Description' – Each Description MUST be 3+ sentences)
    
    Extract the following from the job description:
    - Job Keywords and Required Qualifications (as 'keywords' and 'qualifications' in a dictionary)

    ### Instructions for Fit Score Calculation:
    Calculate a fit score (out of 25) based on the following five criteria (1-5 points each) using EXTREMELY RIGOROUS evaluation standards:

    1. Educational Background (1-5 points):
       - 5 points: Perfect match to required education with advanced degree in EXACT field specified
       - 4 points: Meets education requirements perfectly with additional relevant coursework
       - 3 points: Meets minimum education requirements exactly
       - 2 points: Slightly below education requirements but in the exact same field
       - 1 point: Missing education requirements but has some relevant educational background
       - 0 points: Completely unrelated education

    2. Technical Skills Match (1-5 points):
       - 5 points: Demonstrates mastery of 90%+ of required technical skills with proven experience
       - 4 points: Strong command of 80-89% of required skills with demonstrated applications
       - 3 points: Working knowledge of 70-79% of required skills
       - 2 points: Basic familiarity with 50-69% of required skills
       - 1 point: Minimal overlap with required skills (<50%)
       - 0 points: Almost no match with required technical skills

    3. Relevant Experience (1-5 points):
       - 5 points: Exceeds required experience with identical role and industry
       - 4 points: Meets required experience with very similar role in relevant industry
       - 3 points: Slightly less experience than required but same job functions
       - 2 points: Significantly less experience or only related experience
       - 1 point: Only tangentially related experience
       - 0 points: No relevant experience

    4. Domain Expertise & Advanced Technologies (1-5 points):
       - 5 points: Expert in specific domain with advanced technology experience required
       - 4 points: Strong domain knowledge with most advanced technologies required
       - 3 points: Some domain knowledge with basic understanding of advanced technologies
       - 2 points: Limited domain exposure but shows aptitude for advanced technologies
       - 1 point: No domain experience but some exposure to relevant technologies
       - 0 points: No domain knowledge or advanced technology experience

    5. Soft Skills & Culture Fit (1-5 points):
       - 5 points: Clear evidence of ALL required soft skills with concrete examples
       - 4 points: Strong evidence of most required soft skills
       - 3 points: Some evidence of required soft skills
       - 2 points: Minimal evidence of some required soft skills
       - 1 point: Little to no evidence of required soft skills
       - 0 points: Evidence contradicting required soft skills

    Total Score Interpretation (Using HIGHER STANDARDS to better filter candidates):
    - >= 22 points: "Top Candidate" - Excellent match, interview immediately (expect top ~10% of applicants)
    - 18-21 points: "Strong Candidate" - Good match, schedule interview (expect next ~20% of applicants)
    - 15-17 points: "Potential Candidate" - Consider only if needed (expect next ~30% of applicants)
    - <= 14 points: "Not Recommended" - Do not proceed (expect bottom ~40% of applicants)

    Include the following in the JSON output - make sure the 'fit_score' section is properly formatted:
    - All extracted resume fields (as above)
    - Job Keywords and Required Qualifications
    - Detailed Skills Gap Analysis:
      - List every required skill/qualification and rate as "EXACT MATCH", "PARTIAL MATCH", or "NO MATCH"
      - For each "NO MATCH" or "PARTIAL MATCH", provide specific evidence for this determination
    - Fit Score details:
      - 'fit_score' object with the following keys:
        - 'total_score' (out of 25)
        - 'education_score' (out of 5)
        - 'technical_skills_score' (out of 5)
        - 'experience_score' (out of 5)
        - 'advanced_tech_score' (out of 5)
        - 'soft_skills_score' (out of 5)
        - 'score_explanations': An object containing explanation keys matching each score key
        - 'recommendation': Based on total score using the updated scale
        - 'critical_missing_qualifications': List specific required qualifications the candidate is missing
        - 'improvement_areas': List specific areas where the candidate needs improvement

    IMPORTANT: 
    1. Ensure the JSON structure is valid and always includes the 'fit_score' object at the top level
    2. Be extremely critical and scrutinizing of candidates
    3. Apply evaluation consistently across all resumes
    4. Rate based on EXACT matches to job requirements, not general impressions

    ### Input:
    Resume Text:
    {resume_text}

    Job Description:
    {job_description}

    ### Output:
    Return ONLY JSON. Do NOT include extra text, explanations, or formatting issues.
    """

    # Send request to Gemini
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(prompt)
        logging.debug(f"API Response: {response.text}")
    except Exception as e:
        os.remove(file_path)
        return render_template('result.html', error=f"API Error: {str(e)}")

    # Extract JSON from response
    json_output = extract_json_from_text(response.text)

    if "error" in json_output:
        os.remove(file_path)
        return render_template('result.html', error=json_output["error"])

    # Generate chart
    fit_score = json_output.get("fit_score", {})
    chart_image = create_fit_score_chart(fit_score)
    
    # Save this result
    save_result(
        result_id=result_id,
        resume_filename=resume_file.filename,
        job_description=job_description,
        json_output=json_output,
        chart_image=chart_image
    )

    # Redirect to view this specific result
    return redirect(url_for('view_result', result_id=result_id))

# Function to load existing results
def load_results():
    if os.path.exists(app.config['RESULTS_FILE']):
        with open(app.config['RESULTS_FILE'], 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Function to save results
def save_result(result_id, resume_filename, job_description, json_output, chart_image):
    results = load_results()
    
    # Store the result with metadata
    results[result_id] = {
        "id": result_id,
        "resume_filename": resume_filename,
        "job_description": job_description,
        "json_output": json_output,
        "chart_image": chart_image,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Save back to file
    with open(app.config['RESULTS_FILE'], 'w') as f:
        json.dump(results, f, indent=4)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    logging.debug(f"Extracted text from PDF: {text[:500]}...")  # Log first 500 chars
    return text

# Function to extract text from DOCX
def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    logging.debug(f"Extracted text from DOCX: {text[:500]}...")  # Log first 500 chars
    return text

# Function to extract JSON from Gemini response
def extract_json_from_text(text):
    start = text.find('{')
    if start == -1:
        return {"error": "No JSON found in response"}
    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return {"error": "Invalid JSON in response"}
    return {"error": "Incomplete JSON in response"}

# Function to create fit score chart
def create_fit_score_chart(fit_score):
    # New 25-point system
    education_score = fit_score.get("education_score", 0)
    technical_skills_score = fit_score.get("technical_skills_score", 0)
    experience_score = fit_score.get("experience_score", 0)
    advanced_tech_score = fit_score.get("advanced_tech_score", 0)
    soft_skills_score = fit_score.get("soft_skills_score", 0)
    total_score = fit_score.get("total_score", 0)
    
    categories = ['Education (5)', 'Tech Skills (5)', 'Experience (5)', 'Adv. Tech (5)', 'Soft Skills (5)', 'Total (25)']
    scores = [education_score, technical_skills_score, experience_score, advanced_tech_score, soft_skills_score, total_score]
    max_scores = [5, 5, 5, 5, 5, 25]

    
    logging.debug(f"Plotting scores: {scores}")  # Debug to check values
    
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#E91E63', '#3F51B5']
    bars = ax.bar(categories, scores, color=colors[:len(categories)], edgecolor='black', linewidth=1)
    
    ax.set_ylim(0, max(max_scores) * 1.2)
    ax.set_ylabel('Score')
    ax.set_title('Resume Fit Score Breakdown')
    ax.grid(True, axis='y', linestyle='--', alpha=0.7)
    
    # Add labels on top of bars
    for bar, max_score in zip(bars, max_scores):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.1,
                f'{height}/{max_score}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)
    
    return image_base64

if __name__ == '__main__':
    app.run(debug=True)