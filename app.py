from flask import Flask, render_template, request, jsonify
import pandas as pd
import sqlite3
import os
from openai import OpenAI

# Flask app
app = Flask(__name__)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-your-api-key-here"))

# CSV data for PO search
CSV_FILE = "data/po_data.csv"
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    df.columns = df.columns.str.upper()  # Make sure headers are uppercase
else:
    df = pd.DataFrame(columns=["PO", "PARTY", "AREA", "MATERIAL"])

# Database file
DB_FILE = "study_data.db"

# --- Ensure DB and Table Exists ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()  # Run at startup


# --- Save study data ---
def save_study_data(question, answer):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO knowledge (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()


# --- Search study data ---
def search_study_data(query):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM knowledge WHERE question LIKE ?", ('%' + query + '%',))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# --- PO Search ---
def search_csv(query):
    results = []
    query = query.lower()
    for _, row in df.iterrows():
        if (query in str(row["PO"]).lower() or
            query in str(row["PARTY"]).lower() or
            query in str(row["AREA"]).lower() or
            query in str(row["MATERIAL"]).lower()):
            results.append({
                "PO": row["PO"],
                "PARTY": row["PARTY"],
                "AREA": row["AREA"],
                "MATERIAL": row["MATERIAL"]
            })
    return results


# --- Flask Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    mode = data.get("mode", "normal")  # normal, study, po

    if mode == "study":
        # In study mode: Save message as knowledge
        save_study_data(user_message, f"Learned: {user_message}")
        return jsonify({"reply": "📚 Study data saved!"})

    elif mode == "po":
        results = search_csv(user_message)
        if results:
            reply = "📑 PO Results:\n" + "\n".join(
                [f"PO: {r['PO']}, Party: {r['PARTY']}, Area: {r['AREA']}, Material: {r['MATERIAL']}" for r in results]
            )
        else:
            reply = "❌ No PO match found."
        return jsonify({"reply": reply})

    else:
        # First check in study DB
        study_answer = search_study_data(user_message)
        if study_answer:
            return jsonify({"reply": study_answer})

        # Fallback to OpenAI
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Tesa AI, a helpful assistant."},
                {"role": "user", "content": user_message}
            ]
        )
        ai_reply = completion.choices[0].message.content
        return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
