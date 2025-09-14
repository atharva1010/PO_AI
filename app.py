import os
import sqlite3
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from openai import OpenAI
import pandas as pd
import fitz  # PyMuPDF for PDF
import docx   # for Word files

# --- Config ---
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DB_FILE = "study_data.db"
client = OpenAI(api_key="YOUR_API_KEY")

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS study_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT,
                        answer TEXT
                    )''')
    conn.commit()
    conn.close()

init_db()

# --- Helper: Insert Study Data ---
def save_to_db(question, answer):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO study_data (question, answer) VALUES (?, ?)", (question.strip(), answer.strip()))
    conn.commit()
    conn.close()

# --- Helper: Search Study Data ---
def search_study_data(query):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM study_data WHERE LOWER(question) LIKE ?", ('%' + query.lower() + '%',))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# --- Helper: AI Answer ---
def ask_ai(query):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": query}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# --- Helper: Extract Text from Files ---
def extract_text_from_file(filepath):
    text = ""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    elif ext == ".pdf":
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text()

    elif ext in [".xls", ".xlsx", ".csv"]:
        df = pd.read_excel(filepath) if ext in [".xls", ".xlsx"] else pd.read_csv(filepath)
        text = df.to_string()

    elif ext == ".docx":
        d = docx.Document(filepath)
        text = "\n".join([para.text for para in d.paragraphs])

    return text

# --- Helper: Auto Question Generation ---
def generate_questions_from_text(text):
    prompt = f"""
    Niche diye gaye text ke basis par jitne bhi possible short and clear Question-Answer pairs ban sakte hain unhe banao.
    Text:
    {text}

    Format:
    Q: <question>
    A: <answer>
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("message")
    mode = data.get("mode", "PO")

    # First check in study memory
    answer = search_study_data(query)

    if not answer:
        # Fallback to AI
        if mode == "PO":
            answer = ask_ai(query)
        else:
            answer = "Study mode enabled. Please teach me or upload a file."

    return jsonify({"answer": answer})

@app.route("/study", methods=["POST"])
def study():
    data = request.json
    question = data.get("question")
    answer = data.get("answer")

    if question and answer:
        save_to_db(question, answer)
        return jsonify({"status": "success", "message": "Data saved."})
    return jsonify({"status": "error", "message": "Missing question or answer."})

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."})

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "Empty filename."})

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    file.save(filepath)

    # Extract text
    extracted_text = extract_text_from_file(filepath)

    # Generate Q/A
    qa_text = generate_questions_from_text(extracted_text)

    # Parse Q/A and Save
    for block in qa_text.split("\n"):
        if block.startswith("Q:"):
            q = block.replace("Q:", "").strip()
        elif block.startswith("A:"):
            a = block.replace("A:", "").strip()
            if q and a:
                save_to_db(q, a)

    return jsonify({"status": "success", "message": "File studied and data saved!"})

# --- Run ---
if __name__ == "__main__":
    app.run(debug=True)
