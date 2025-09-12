from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")  # Ensure columns: PO, AREA, PARTY, MATERIAL

# Clean text function
def clean_text(text):
    return re.sub(r'\s+', ' ', str(text).upper().strip())

# Simple translation mapping for common misheard words
TRANSLATIONS = {
    "SUBHABOOL": "SUBABOOL",
    "UK LIPTIS": "EUCALYPTUS",
    "EUCALIPTUS": "EUCALYPTUS",
    "VINAYAK TRADERS": "VINAYAK TRADERS",
    "SHIVA WINNER": "SHIVA VEENER",
    "SHIVA GOOD": "SHIVA VEENER",
    "SHIVA GOODS YOU CAREPTUS": "SHIVA VEENER",
    # Add more mappings as needed
}

def translate_words(query):
    words = query.split()
    new_words = []
    for w in words:
        w_upper = w.upper()
        new_words.append(TRANSLATIONS.get(w_upper, w_upper))
    return " ".join(new_words)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_translated = translate_words(query)
    query_clean = clean_text(query_translated)
    query_words = query_clean.split()

    matches = []
    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Check if **all query words exist** in row words (fuzzy match)
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
