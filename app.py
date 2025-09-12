from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")

# Ensure columns are uppercase
df.columns = df.columns.str.upper()

# Fill any missing AREA with 'OTHER' (just in case)
df['AREA'] = df['AREA'].fillna('OTHER')

# Convert all string columns to uppercase for matching
df = df.apply(lambda col: col.str.upper() if col.dtype == 'object' else col)

# Example translation dictionary for Hindi/alternate names
TRANSLATE_DICT = {
    "SUBABOOL": "SUBABOOL",
    "SUBHABHOOL": "SUBABOOL",
    "EUCALYPTUS": "EUCALYPTUS",
    "UK LIPTIS": "EUCALYPTUS",
    # Add more as needed
}

def clean_text(text):
    """Uppercase, remove extra spaces"""
    return re.sub(r'\s+', ' ', str(text).upper().strip())

def translate_word(word):
    """Translate Hindi/alternate words to CSV word"""
    return TRANSLATE_DICT.get(word.upper(), word.upper())

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = [translate_word(w) for w in query_clean.split()]

    matches = []

    for _, row in df.iterrows():
        # Combine row fields for matching
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Check if all query words are present in row words using fuzzy match
        all_match = True
        for q_word in query_words:
            word_score = max([fuzz.partial_ratio(q_word, r_word) for r_word in row_words])
            if word_score < 70:  # threshold
                all_match = False
                break

        if all_match:
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "SubArea": row['AREA'],
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
