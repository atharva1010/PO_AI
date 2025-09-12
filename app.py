from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")

# Convert all string columns to lowercase
df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

def clean_text(text):
    """Lowercase and remove extra spaces"""
    return re.sub(r'\s+', ' ', str(text).lower().strip())

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = query_clean.split()

    matches = []
    for _, row in df.iterrows():
        # Combine row fields for matching
        row_text = f"{row['PARTY']} {row.get('AREA','')} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Word-level fuzzy match
        word_scores = []
        for q_word in query_words:
            max_score = max([fuzz.partial_ratio(q_word, r_word) for r_word in row_words])
            word_scores.append(max_score)

        avg_score = sum(word_scores)/len(word_scores)

        if avg_score >= 70:  # Threshold for match
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "SubArea": row.get('AREA', ''),
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "Koi PO nahi mila, query check karein."})

if __name__ == "__main__":
    app.run(debug=True)
