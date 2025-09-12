from flask import Flask, request, render_template, jsonify
import pandas as pd
import difflib

app = Flask(name)

Load CSV

df = pd.read_csv("data/po_data.csv")

Convert all string columns to lowercase for matching

df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

@app.route("/")
def home():
return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
query = request.form["query"].lower().strip()

query_words = query.split()  

matches = []  
for _, row in df.iterrows():  
    # Keep special characters intact  
    row_text = " ".join(map(str, row.values)).lower()  

    # Fuzzy match with threshold 0.5  
    from difflib import SequenceMatcher  
    match_score = SequenceMatcher(None, " ".join(query_words), row_text).ratio()  
    if match_score >= 0.5:  
        matches.append({  
"PO": f"<b>{row['PO']}</b>",  
"Party": row['PARTY'],  
"SubArea": row.get('AREA', ''),   # <- yahan AREA use karein  
"Material": row['MATERIAL']

})

if matches:  
    return jsonify({"answer": matches})  
else:  
    return jsonify({"answer": "No result find, I am working on this result."})

if name == "main":
app.run(debug=True)

