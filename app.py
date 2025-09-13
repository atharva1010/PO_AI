from flask import Flask, request, jsonify, render_template
import pandas as pd
import openai
import os
import difflib

# Flask app
app = Flask(__name__)

# Load environment variable (Render पर आप OPENAI_API_KEY set करेंगे)
openai.api_key = os.getenv("OPENAI_API_KEY") or "sk-your-api-key-here"

# Load CSV file
CSV_FILE = "data.csv"
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
else:
    df = pd.DataFrame(columns=["question", "answer"])

def search_csv(user_query):
    """CSV file me closest match dhundho"""
    questions = df['question'].astype(str).tolist()
    matches = difflib.get_close_matches(user_query.lower(), [q.lower() for q in questions], n=1, cutoff=0.6)

    if matches:
        match_index = [q.lower() for q in questions].index(matches[0])
        return df.iloc[match_index]['answer']
    return None

def ask_ai(user_query):
    """Agar CSV me answer na mile to AI se pucho"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",   # free/cheap model
            messages=[
                {"role": "system", "content": "You are a helpful assistant. User will ask about CSV topics or anything else."},
                {"role": "user", "content": user_query}
            ],
            max_tokens=200
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ AI error: {str(e)}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    user_query = data.get("query", "").strip()

    if not user_query:
        return jsonify({"answer": "⚠️ Please ask a valid question."})

    # 1) Try CSV search
    csv_answer = search_csv(user_query)
    if csv_answer:
        return jsonify({"answer": csv_answer})

    # 2) Else ask AI
    ai_answer = ask_ai(user_query)
    return jsonify({"answer": ai_answer})

if __name__ == "__main__":
    app.run(debug=True)
