from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po-data.csv")

# Make all string columns lowercase for matching
df_lower = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# Optional: define translation dictionary for common Hindi/English variations
TRANSLATE_DICT = {
    "subhabhool": "subabool",
    "uk liptis": "eucalyptus",
    "shiva winner": "shiva veener",
    "shiva goods you careptus": "shiva goods carrier",
    "mfk": "m.f.k.enterprises"
}

def clean_text(text):
    """Lowercase, translate, remove extra spaces"""
    text = str(text).lower().strip()
    # Replace translations
    for k, v in TRANSLATE_DICT.items():
        text = text.replace(k, v)
    text = re.sub(r'\s+', ' ', text)
    return text

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = query_clean.split()

    matched_row = None
    for idx, row in df_lower.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Check if all query words are in row words (fuzzy)
        scores = [max(fuzz.partial_ratio(q, r) for r in row_words) for q in query_words]
        if all(s >= 80 for s in scores):  # threshold
            matched_row = df.iloc[idx]  # original row with proper capitalization
            break

    if matched_row is not None:
        result = {
            "PO": f"<b>{matched_row['PO']}</b>",
            "Party": matched_row['PARTY'],
            "Area": matched_row['AREA'],
            "Material": matched_row['MATERIAL']
        }
        return jsonify({"answer": [result]})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
