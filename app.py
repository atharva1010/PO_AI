from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")

# Lowercase copy for matching
df_lower = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# Translation dictionary for common mispronunciations / Hindi-English words
TRANSLATE_DICT = {
    "subhabhool": "SUBABOOL",
    "uk liptis": "EUCALYPTUS",
    "shiva winner": "SHIVA VEENER",
    "shiva goods you careptus": "SHIVA GOODS CARRIER",
    "mfk": "M.F.K.ENTERPRISES"
}

def clean_text(text):
    text = str(text).lower().strip()
    for k, v in TRANSLATE_DICT.items():
        text = text.replace(k.lower(), v.lower())
    return re.sub(r'\s+', ' ', text)

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

        scores = [max(fuzz.partial_ratio(q, r) for r in row_words) for q in query_words]
        if all(s >= 80 for s in scores):
            matched_row = df.iloc[idx]  # original uppercase row
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
