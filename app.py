from flask import Flask, request, render_template, jsonify
import pandas as pd
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")
df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# Synonyms dictionary
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

    party_match, area_match, material_match = None, None, None

    # Identify which word belongs to which field
    for word in query_words:
        if word in df['PARTY'].unique().tolist():
            party_match = word
        elif word in df['AREA'].unique().tolist():
            area_match = word
        elif any(word in m for m in df['MATERIAL'].unique().tolist()):
            material_match = word

    # Filter DataFrame
    result = df.copy()
    if party_match:
        result = result[result['PARTY'].str.contains(party_match)]
    if area_match:
        result = result[result['AREA'].str.contains(area_match)]
    if material_match:
        result = result[result['MATERIAL'].str.contains(material_match)]

    matches = []
    for _, row in result.iterrows():
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
