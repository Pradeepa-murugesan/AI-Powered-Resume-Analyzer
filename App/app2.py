from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os
import time
import datetime
import pymysql
from pyresparser import ResumeParser  # Custom parser module
import base64
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
import io
import random
import socket
import platform
import geocoder
import secrets
from dotenv import load_dotenv
import google.generativeai as genai
from Courses import ds_course, web_course, android_course, ios_course, uiux_course, resume_videos, interview_videos
import nltk
nltk.download('stopwords')
import markdown



# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# MySQL Connection
connection = pymysql.connect(host='localhost', user='root', password='Pradeepa@19', db='cv')
cursor = connection.cursor()

# Gemini API Setup
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_resume_gap_analysis(resume_text, job_description):
    prompt = f"""
    Compare the following resume content with the given job description. List any missing skills or qualifications the candidate should add to their resume to be a better fit.

    Resume:
    {resume_text}

    Job Description:
    {job_description}

    Provide a list of skills, tools, or keywords that should be added or improved.
    """
    response = model.generate_content(prompt)
    return response.text

def pdf_reader(file_path):
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)
    with open(file_path, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            page_interpreter.process_page(page)
        text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text

def insert_data(*args):
    DB_table_name = 'user_data'
    insert_sql = "insert into " + DB_table_name + """
    values (0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    cursor.execute(insert_sql, args)
    connection.commit()

def insert_feedback(name, email, score, comments, timestamp):
    DBf_table_name = 'user_feedback'
    insert_sql = "insert into " + DBf_table_name + " values (0,%s,%s,%s,%s,%s)"
    cursor.execute(insert_sql, (name, email, score, comments, timestamp))
    connection.commit()

def get_must_have_skills(job_title):
    prompt = f"""
    Provide a list of top 10 must-have technical and soft skills (only names) required for a job title: '{job_title}'.
    Return the skills as a comma-separated list without extra explanation.
    """
    response = model.generate_content(prompt)
    return [skill.strip() for skill in response.text.split(',')]

def get_missing_must_have_skills(resume_skills, job_title):
    must_have_skills = get_must_have_skills(job_title)
    resume_skills_lower = [skill.lower() for skill in resume_skills]
    missing_skills = [skill for skill in must_have_skills if skill.lower() not in resume_skills_lower]
    return missing_skills, must_have_skills

def recommend_courses(skills):
    categories = {
        'Data Science': ds_course,
        'Web Development': web_course,
        'Android Development': android_course,
        'IOS Development': ios_course,
        'UI-UX Development': uiux_course
    }
    keywords = {
        'Data Science': ['tensorflow','keras','pytorch','machine learning','deep learning','flask','streamlit'],
        'Web Development': ['react', 'django', 'node js', 'react js', 'php', 'laravel', 'wordpress','javascript', 'flask'],
        'Android Development': ['android','flutter','kotlin','xml','kivy'],
        'IOS Development': ['ios','swift','cocoa','xcode'],
        'UI-UX Development': ['ux','figma','ui','photoshop','wireframes']
    }
    for field, kw_list in keywords.items():
        if any(skill.lower() in kw_list for skill in skills):
            return field, random.sample(categories[field], min(5, len(categories[field])))
    return 'NA', []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    name = request.form['name']
    email = request.form['email']
    mobile = request.form['mobile']
    job_desc = request.form['jobdesc']  # Job description from user
    file = request.files['resume']

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        resume_data = ResumeParser(file_path).get_extracted_data()
        resume_text = pdf_reader(file_path)

        if not resume_data:
            flash("Resume parsing failed. Try another resume.")
            return redirect(url_for('index'))

        sec_token = secrets.token_urlsafe(12)
        host_name = socket.gethostname()
        ip_add = socket.gethostbyname(host_name)
        dev_user = os.getlogin()
        os_name_ver = platform.system() + " " + platform.release()
        g = geocoder.ip('me')
        latlong = g.latlng
        geolocator = geocoder.osm(latlong, method='reverse')
        city = geolocator.city or ''
        state = geolocator.state or ''
        country = geolocator.country or ''

        pages = resume_data.get('no_of_pages', 1)
        skills = resume_data.get('skills', [])

        # Extract job title from resume text
        lines = resume_text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        resume_name = resume_data.get('name', '').lower()

        job_title = ""
        for i, line in enumerate(lines):
            if resume_name in line.lower():
                if i + 1 < len(lines):
                    job_title = lines[i + 1]
                    break
        if not job_title:
            job_title = "Unknown"

        print("Job Title:", job_title)
        cand_level = 'Fresher'
        #if 'internship' in resume_text.lower():
        #    cand_level = 'Intermediate'
        #if 'experience' in resume_text.lower():
        #    cand_level = 'Experienced'

        # Get missing must-have skills
        missing_skills, must_have_skills = get_missing_must_have_skills(skills, job_title)

        # Recommend courses based on missing skills only
        reco_field, recommended_courses = recommend_courses(missing_skills)
        recommended_skills = missing_skills  # these are needed to be job-ready
        print(str(skills), str(recommended_skills))  # resume_skills, recommended_skills


        score = 0
        sections = [
            ('objective', 6), ('education', 12), ('experience', 16), ('internship', 6),
            ('skills', 7), ('hobbies', 4), ('interests', 5),
            ('achievements', 13), ('certifications', 12), ('projects', 19)
        ]
        for sec, val in sections:
            if sec in resume_text.lower():
                score += val

        ts = time.time()
        timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H:%M:%S')

        insert_data(sec_token, ip_add, host_name, dev_user, os_name_ver, str(latlong), city, state, country,
                    name, email, mobile, resume_data['name'], resume_data['email'], str(score), timestamp,
                    str(pages), reco_field, cand_level, str(skills), str(recommended_skills),
                    str([name for name, link in recommended_courses]), filename)

        resume_vid = random.choice(resume_videos)
        interview_vid = random.choice(interview_videos)

        # Call Gemini API for skill gap analysis
        gemini_feedback = get_resume_gap_analysis(resume_text, job_desc)
        gemini_feedback = markdown.markdown(gemini_feedback, extensions=['extra'])
        return render_template('result.html',
                               resume=resume_data,
                               role = job_title,
                               level=cand_level,
                               field=reco_field,
                               skills=skills,
                               recommendations=recommended_skills,
                               courses=recommended_courses,
                               score=score,
                               resume_vid=resume_vid,
                               interview_vid=interview_vid,
                               gemini_feedback=gemini_feedback
                               )

    flash("File upload failed")
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)