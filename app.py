from flask import Flask, request, render_template, jsonify
import pandas as pd
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")
df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# Synonyms for correction
synonyms = {
    "subabool": ["subabool", "subhabhool", "subabul"],
    "eucalyptus": ["eucalyptus", "uk liptis", "ukliptis", "nilgiri"],
    "poplar": ["poplar", "poplaar"],
    "rampur": ["rampur", "rmpur"],
    "sitapur": ["sitapur", "sittapur"],
    "shiva veener": ["shiva veener", "shiva veneer", "shiv veneer"],
}

def clean_text(text):
    return re.sub(r'\s+', ' ', str(text).lower().strip())

def normalize_word(word):
    for key, values in synonyms.items():
        if word in values:
            return key
    return word

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_words = [normalize_word(clean_text(w)) for w in query.split()]

    matches = []
    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row.get('AREA','')} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)

        # ✅ Check: ALL query words must exist in the same row
        if all(word in row_text_clean for word in query_words):
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "SubArea": row.get('AREA', ''),
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
