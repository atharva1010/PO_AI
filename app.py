from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz, process
import re, os

app = Flask(__name__)

# -----------------------------
# Load CSV file safely
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(BASE_DIR, "data", "po_data.csv")
df = pd.read_csv(file_path)

# Convert all string columns to lowercase
df = df.apply(lambda col: col.str.lower() if col.dtype == "object" else col)

# -----------------------------
# Utility functions
# -----------------------------
def clean_text(text):
    """Lowercase and remove extra spaces"""
    return re.sub(r"\s+", " ", str(text).lower().strip())

def fuzzy_match(query_word, choices, threshold=70):
    """Find best fuzzy match in choices"""
    best_match, score, _ = process.extractOne(query_word, choices, scorer=fuzz.partial_ratio)
    return best_match if score >= threshold else None

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = query_clean.split()

    # Collect all searchable words from dataset
    all_words = set()
    for _, row in df.iterrows():
        row_text = f"{row['party']} {row.get('area','')} {row['material']}"
        all_words.update(row_text.split())

    # Try to autocorrect each query word using fuzzy matching
    corrected_words = []
    for q in query_words:
        match = fuzzy_match(q, list(all_words))
        if match:
            corrected_words.append(match)
        else:
            corrected_words.append(q)

    # Now filter rows that contain *all corrected words*
    matches = []
    for _, row in df.iterrows():
        row_text = f"{row['party']} {row.get('area','')} {row['material']}"
        row_text_clean = clean_text(row_text)

        if all(word in row_text_clean for word in corrected_words):
            matches.append({
                "PO": f"<b>{row['po']}</b>",
                "Party": row['party'],
                "Area": row.get('area', ''),
                "Material": row['material']
            })

    # Only exact rows where all words matched
    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
