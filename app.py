from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")

# Convert all string columns to lowercase
df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# 🔹 Synonyms Dictionary (expandable)
synonyms = {
    "subabool": ["subabool", "subhabhool", "subabul", "subabulh"],
    "eucalyptus": ["eucalyptus", "ukliptis", "uk liptis", "nilgiri", "neelgiri", "eucaliptus"],
    "poplar": ["poplar", "poplaar", "poplur"],
    "chips": ["chips", "chip", "chippes"],
    "rampur": ["rampur", "rmpur"],
    "sitapur": ["sitapur", "sittapur", "sittapoor"],
    "shiva veener": ["shiva veener", "shiva veneer", "shiv veneer", "shiva viner"],
}

def clean_text(text):
    """Lowercase and remove extra spaces"""
    return re.sub(r'\s+', ' ', str(text).lower().strip())

def normalize_word(word):
    """Normalize query words using synonyms + fuzzy"""
    word = word.lower().strip()
    best_match = word
    best_score = 0
    for key, values in synonyms.items():
        for val in values:
            score = fuzz.ratio(word, val)
            if score > best_score and score > 70:  # fuzzy threshold
                best_match = key
                best_score = score
    return best_match

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = query_clean.split()

    # 🔹 Normalize words
    normalized_words = [normalize_word(w) for w in query_words]

    matches = []
    for _, row in df.iterrows():
        # Combine row fields for matching
        row_text = f"{row['PARTY']} {row.get('AREA','')} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)

        # Check if all normalized words exist in row_text
        if all(any(fuzz.partial_ratio(q, rw) > 70 for rw in row_text_clean.split()) for q in normalized_words):
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "SubArea": row.get('AREA', ''),
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi PO nahi mila, query check karein."})

if __name__ == "__main__":
    app.run(debug=True)
