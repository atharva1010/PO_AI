from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
import fitz  # PyMuPDF for PDFs
import docx  # python-docx for Word files
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
STUDY_FILE = "data/study_data.csv"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)

# Agar study file nahi hai to ek bana do
if not os.path.exists(STUDY_FILE):
    pd.DataFrame(columns=["question", "answer"]).to_csv(STUDY_FILE, index=False)


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    mode = data.get("mode", "study")

    if mode == "study":
        # simple chatbot style
        return jsonify({"reply": f"📝 Studied message: {message}"})
    else:
        # search mode simple echo
        df = pd.read_csv(STUDY_FILE)
        if df.empty:
            return jsonify({"reply": "⚠️ No study data available."})
        results = df[df["question"].str.contains(message, case=False, na=False)]
        if results.empty:
            return jsonify({"reply": "❌ No match found."})
        return jsonify({"reply": results.iloc[0]['answer']})


@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query", "")
    df = pd.read_csv(STUDY_FILE)
    matches = df[df["question"].str.contains(query, case=False, na=False)]
    if matches.empty:
        return jsonify({"results": ["❌ No results found"]})
    return jsonify({"results": matches["answer"].head(5).tolist()})


@app.route("/upload", methods=["POST"])
def upload():
    if "files" not in request.files:
        return jsonify({"message": "No file uploaded."})

    files = request.files.getlist("files")
    study_df = pd.read_csv(STUDY_FILE)

    for file in files:
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        text = extract_text_from_file(path)
        if text:
            # For now just save full text as one study entry
            study_df = pd.concat(
                [study_df, pd.DataFrame([{"question": filename, "answer": text}])],
                ignore_index=True,
            )

    study_df.to_csv(STUDY_FILE, index=False)
    return jsonify({"message": "Files studied successfully!"})


if __name__ == "__main__":
    app.run(debug=True)
