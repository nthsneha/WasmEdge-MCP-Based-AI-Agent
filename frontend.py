import gradio as gr
import requests
import uuid

# Backend base URL
API_URL = "http://localhost:8001"


def init_session():
    """Initialize a new session with the backend"""
    try:
        response = requests.post(f"{API_URL}/start-session")
        response.raise_for_status()
        return response.json()["session_id"]
    except Exception as e:
        print(f"Failed to initialize session: {e}")
        return None


session_id = init_session()
if not session_id:
    raise Exception("Failed to initialize session with backend")

def handle_user_input(user_input, history):
    if not user_input.strip():
        return history + [(user_input, "Please enter a valid input.")]
    
    try:
        user_msg = user_input
        
        response = requests.post(
            f"{API_URL}/follow-up",
            params={
                "session_id": session_id,
                "user_message": user_msg
            },
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("reply", "⚠️ No reply received.")
        
        if "new question" not in reply:
            return history + [(user_msg, reply)]
        else:
            return ask_custom_question(user_msg, history)
            
    except Exception as e:
        return history + [(user_input, f"Error: {str(e)}")]

def ask_custom_question(question_text, history):
    if not question_text.strip():
        return history + [("❓", "Please enter a question.")]
    
    try:
        response = requests.get(
            f"{API_URL}/get-question-and-answer",
            params={"session_id": session_id, "question": question_text}
        )
        response.raise_for_status()
        data = response.json()
        answer_expl = data.get("answer_and_explanation", "⚠️ No answer received.")
        return history + [(f"❓ {question_text}", answer_expl)]
    except Exception as e:
        return history + [(f"❓ {question_text}", f"Error: {str(e)}")]

def get_random_question(history):
    try:
        response = requests.get(
            f"{API_URL}/random-question",
            params={"session_id": session_id}
        )
        response.raise_for_status()
        data = response.json()
        question = data["question"]
        options = data["options"]
        formatted_question = f"{question}\n\nOptions:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        return history + [("🎲 Practice Question", formatted_question)]
    except Exception as e:
        return history + [("🎲 Practice Question", f"Error: {str(e)}")]

with gr.Blocks() as demo:
    gr.Markdown("""
    ## 🤖 AI Practice & QA Assistant
    - Click '🎲 Practice Question' for a multiple choice question
    - Use the custom question box to ask your own questions
    - Type 'answer' to see the correct answer for practice questions
    - Type 'explain' to get an explanation
    """)
    
    chatbot = gr.Chatbot(label="Conversation", height=500)
    user_msg = gr.Textbox(
        placeholder="Type your message here...",
        label="Your follow-up message",
        show_label=True
    )
    send_btn = gr.Button("💬 Send")

    with gr.Row():
        random_btn = gr.Button("🎲 Practice Question")
        custom_question = gr.Textbox(
            placeholder="Ask your custom question...",
            label="Custom Question",
            show_label=True
        )
        ask_custom_btn = gr.Button("❓ Ask Custom Question")

    send_btn.click(handle_user_input, inputs=[user_msg, chatbot], outputs=chatbot)
    user_msg.submit(handle_user_input, inputs=[user_msg, chatbot], outputs=chatbot)
    random_btn.click(get_random_question, inputs=[chatbot], outputs=chatbot)
    ask_custom_btn.click(ask_custom_question, inputs=[custom_question, chatbot], outputs=chatbot)

    gr.Markdown("""
    ### Tips:
    - For practice questions, type 'answer' to see the solution
    - Type 'explain' to get a detailed explanation
    - Use follow-up questions to learn more
    """)

if __name__ == "__main__":
    demo.launch()