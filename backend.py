from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import FastAPI, HTTPException, Query
import random
import uuid
import json
import subprocess
import ollama


app = FastAPI()

with open("practice_qs.json", "r") as f:
    question_bank = json.load(f)
sessions = {}


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Q&A API"}

def query_ollama(model_name: str, prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", model_name, prompt],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error running ollama: {e}"

@app.post("/start-session")
def start_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "qa_history": []
    }
    return {"session_id": session_id}

@app.api_route("/random-question", methods=["GET", "POST"])
def random_question(session_id: str = Query(...)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    question = random.choice(question_bank)

    sessions[session_id]["qa_history"].append({
        "context": "random_mcq",
        "question": question["question"],
        "options": question["options"],
        "answer": question["answer"],
        "explanation": question.get("explanation", "No explanation available."),
        "conversation_history": []
    })

    return {
        "question": question["question"],
        "options": question["options"]
    }

@app.get("/get-question-and-answer")
def get_question_and_answer(question: str, session_id: str = Query(...)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    prompt = f"Question: {question}\nProvide the correct answer and an explanation."
    model_name = "llama2"
    answer_expl = query_ollama(model_name, prompt)

    sessions[session_id]["qa_history"].append({
        "context": "custom_qa",
        "question": question,
        "options": None,
        "answer": None,
        "explanation": None,
        "conversation_history": [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer_expl}
        ]
    })

    return {
        "question": question,
        "answer_and_explanation": answer_expl
    }

def is_context_relevant_qa(last_qa: dict, user_message: str, threshold=0.3) -> bool:
    combined_text = last_qa.get("question", "")
    if last_qa.get("answer"):
        combined_text += " " + last_qa["answer"]
    if last_qa.get("explanation"):
        combined_text += " " + last_qa["explanation"]

    vectorizer = TfidfVectorizer().fit([combined_text, user_message])
    tfidf_matrix = vectorizer.transform([combined_text, user_message])
    similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
    return similarity >= threshold

@app.post("/follow-up")
def follow_up(session_id: str, user_message: str):
    if session_id not in sessions:
        return {"reply": "Invalid session ID. Please start a new session."}

    qa_history = sessions[session_id].get("qa_history", [])
    if not qa_history:
        return {"reply": " No previous question found. Please start with a question first."}

    last_qa = qa_history[-1]
    context = last_qa.get("context")
    answer = last_qa.get("answer")
    explanation = last_qa.get("explanation")
    conv_history = last_qa["conversation_history"]
    user_msg_lower = user_message.lower().strip()


    if context == "random_mcq":
        if "answer" in user_msg_lower and answer:
            return {"reply": f"✅ Correct Answer: {answer}"}
        if ("explain" in user_msg_lower or "explanation" in user_msg_lower) and explanation:
            return {"reply": f"🧠 Explanation: {explanation}"}
        return {"reply": "Please ask about the answer or explanation for the last question."}


    if context == "custom_qa":
        if not is_context_relevant_qa(last_qa, user_message):
            return {"reply": "That seems like a new question. Please ask it again as a new question."}

    conv_history.append({"role": "user", "content": user_message})
    prompt_text = "\n".join([f"{m['role']}: {m['content']}" for m in conv_history])

    try:
        reply = query_ollama("llama2", prompt_text)
    except Exception as e:
        return {"reply": f"LLM error: {str(e)}"}

    conv_history.append({"role": "assistant", "content": reply})
    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)