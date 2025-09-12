from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV (uppercase headers)
df = pd.read_csv("data/po_data.csv")

# Ensure all string columns are uppercase
df = df.apply(lambda col: col.str.upper() if col.dtype == 'object' else col)

# Simple Hindi/English translation dictionary for common materials
translation_dict = {
    "सुबाबूल": "SUBABOOL",
    "UK LIPTIS": "EUCALYPTUS",
    "EUCALYPTUS": "EUCALYPTUS",
    "SUBABOOL": "SUBABOOL"
    # Add more mappings as needed
}

def clean_text(text):
    """Lowercase, strip extra spaces, remove punctuation for matching"""
    text = str(text).upper().strip()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    return text

def translate_words(words):
    """Translate words using translation dictionary"""
    return [translation_dict.get(w, w) for w in words]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = translate_words(query_clean.split())

    matches = []
    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Check if ALL query words are present approximately in row words
        if all(any(fuzz.partial_ratio(qw, rw) >= 80 for rw in row_words) for qw in query_words):
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "Area": row['AREA'],
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
