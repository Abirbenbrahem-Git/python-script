from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import re
import fitz
import spacy
from spacy.matcher import Matcher
import json
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize SpaCy and Matcher
nlp = spacy.load('en_core_web_sm')
matcher = Matcher(nlp.vocab)

# Function to extract email addresses
def extract_email(email):
    email = re.findall("([^@|\s]+@[^@]+\.[^@|\s]+)", email)
    if email:
        try:
            return email[0].split()[0].strip(';')
        except IndexError:
            return None

# Function to extract mobile numbers
def extract_mobile_number(text):
    phone = re.findall(r'\b\d{8}\b', text)
    if phone:
        number = ''.join(phone[0])
        return number
    else:
        return None

# Function to extract name from PDF
def extract_name_from_pdf(pdf_text):
    nlp_text = nlp(pdf_text)
    pattern = [{'POS': 'PROPN'}, {'POS': 'PROPN'}]
    matcher.add('NAME', patterns=[pattern])
    matches = matcher(nlp_text)
    for match_id, start, end in matches:
        span = nlp_text[start:end]
        return span.text

# Function to extract text from PDF
def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        pdf_reader = PdfReader(file)
        text = ''
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        return text.replace('\n', ' ')  # Replace newline characters with spaces

# Function to extract entities (education, experience, skills) from text
class EntityGenerator:
    def __init__(self, text=None):
        self.text = text

    def get(self):
        doc = nlp(self.text)
        entities = {"EDUCATION": [], "EXPERIENCE": [], "SKILLS": []}

        # Keywords to identify sections
        education_keywords = ["education", "formation", "diplôme", "études"]
        experience_keywords = ["experience", "expérience", "emploi", "travail"]
        skills_keywords = ["skills", "compétences", "aptitudes"]

        current_section = None
        current_phrase = []

        for token in doc:
            if token.text.lower() in education_keywords:
                current_section = "EDUCATION"
            elif token.text.lower() in experience_keywords:
                current_section = "EXPERIENCE"
            elif token.text.lower() in skills_keywords:
                current_section = "SKILLS"
            elif current_section is not None:
                current_phrase.append(token.text)
                if token.is_punct or token.is_space:
                    sentence = " ".join(current_phrase).strip()
                    if current_section == "SKILLS":
                        # Extract skills as a comma-separated list
                        entities["SKILLS"].extend(sentence.split(','))
                    else:
                        entities[current_section].append(sentence)
                    current_phrase = []

        # Remove empty strings from the skills list
        entities["SKILLS"] = list(filter(None, entities["SKILLS"]))

        return entities

# Global variable to store the file path
uploaded_file_path = None

# Route for uploading a file
@app.route('/upload', methods=['POST'])
def upload_file():
    global uploaded_file_path
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        uploaded_file_path = file_path
        return {'message': 'File uploaded successfully', 'file_path': file_path}, 200

# Route for extracting information from the uploaded file
@app.route('/get_results', methods=['GET'])
def get_results():
    global uploaded_file_path
    if uploaded_file_path is None:
        return jsonify({"error": "No file uploaded."}), 400

    pdf_text = extract_text_from_pdf(uploaded_file_path)

    # Extract emails and phone numbers
    lines = pdf_text.split('\n')
    extracted_info = {"phone": None, "email": None}
    for line in lines:
        extracted_email = extract_email(line)
        extracted_phone = extract_mobile_number(line)
        if extracted_email:
            extracted_info["email"] = extracted_email
        if extracted_phone:
            extracted_info["phone"] = extracted_phone

    # Extract name from PDF
    extracted_name = extract_name_from_pdf(pdf_text)
    if extracted_name:
        extracted_info["first_name"] = extracted_name.split()[0]
        extracted_info["last_name"] = extracted_name.split()[1]

    # Extract entities (education, experience, skills)
    entity_generator = EntityGenerator(text=pdf_text)
    entities = entity_generator.get()
    entities.update(extracted_info)
    return jsonify(entities)
 # Remove sentences starting with "\u25cb" from the EXPERIENCE section
if __name__ == '__main__':
    app.run(debug=True)
