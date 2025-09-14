from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
import sqlite3
import fitz  # PyMuPDF
import docx
from werkzeug.utils import secure_filename
from openai import OpenAI

# -------------------
# Config
# -------------------
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
PO_FILE = "data/po_data.csv"
DB_FILE = "data/study_data.db"
os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------
# Database Setup
# -------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------
# File Text Extractor
# -------------------
def extract_text_from_file(file_path):
    text = ""
    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    elif file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
        text = df.to_string()
    return text.strip()

# -------------------
# Helpers
# -------------------
def search_po(query):
    if not os.path.exists(PO_FILE):
        return None
    df = pd.read_csv(PO_FILE)
    for _, row in df.iterrows():
        if query.lower() in str(row.values).lower():
            return f"📑 PO Result: PO={row['PO']}, PARTY={row['PARTY']}, AREA={row['AREA']}, MATERIAL={row['MATERIAL']}"
    return None

def search_study(query):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT answer FROM study_data WHERE question LIKE ? OR answer LIKE ? LIMIT 1", 
              (f"%{query}%", f"%{query}%"))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def ask_openai(query):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Tesa AI, a helpful assistant."},
                {"role": "user", "content": query}
            ]
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ OpenAI error: {e}"

# -------------------
# Routes
# -------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    mode = data.get("mode", "search")

    # STUDY mode -> save into DB
    if mode == "study":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO study_data (question, answer) VALUES (?, ?)", (message, message))
        conn.commit()
        conn.close()
        return jsonify({"reply": f"📝 Studied: '{message}'"})

    # SEARCH mode -> check PO > study > OpenAI
    reply = search_po(message)
    if not reply:
        reply = search_study(message)
    if not reply:
        reply = ask_openai(message)

    return jsonify({"reply": reply})

@app.route("/upload", methods=["POST"])
def upload():
    if "files" not in request.files:
        return jsonify({"message": "No file uploaded."})
    
    files = request.files.getlist("files")

    for file in files:
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        text = extract_text_from_file(path)
        if text:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO study_data (question, answer) VALUES (?, ?)", (filename, text))
            conn.commit()
            conn.close()

    return jsonify({"message": "✅ Files studied successfully!"})

# -------------------
if __name__ == "__main__":
    app.run(debug=True)
