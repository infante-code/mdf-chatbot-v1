from fastapi import FastAPI, Form, Request, WebSocket
from openai import OpenAI
from typing import Annotated
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv
import httpx #change 3

load_dotenv()

app = FastAPI()
htmlTemp = Jinja2Templates(directory="templates")


# n8n webhook URL - changes 1
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "N8N_WEBHOOK_URL")

# No need for this '''export OPEN_API_KEY=<you key>''' cause the function below describe the api key
gpt = OpenAI(
    api_key=os.getenv("OPEN_API_SECRET_KEY")
)
chat_log_history = []

chat_responses = []


# Websocket endpoint
@app.websocket("/ws")
async def chatWebSocket(Websocket: WebSocket):
    await Websocket.accept()
    while True:
          user_input = await Websocket.receive_text()
          chat_log_history.append({'role': 'user', 'content': user_input})


          # N8N Webhook TRY and EXCEPT line code - change 2
          try:
               async with httpx.AsyncClient() as client:
                    n8n_response = await client.post(N8N_WEBHOOK_URL, json={"message": user_input}, timeout=None)
                    if n8n_response.status_code == 200:
                        # Echo n8n response to WebSocket client
                        bot_n8n = ""
                        async for chunk in n8n_response.aiter_text():
                              await Websocket.send_text(chunk)
                              bot_n8n += chunk
                        chat_responses.append(f'N8N Asstance: {bot_n8n}')

                    else:
                        await Websocket.send_text(f"[n8n ERROR {n8n_response.status_code}]: {n8n_response.text}")
          except Exception as e:
                    await Websocket.send_text(f"[n8n EXCEPTION]: {str(e)}")




          # Normal GPT reponse in stream
          try:
               reponse = gpt.chat.completions.create(
                    model='gpt-3.5-turbo',
                    messages= chat_log_history,
                    temperature=0.6,
                    stream=True
               )
               botResponse = ''
               for chunk in reponse:
                    if chunk.choices[0].delta.content is not None:
                         botResponse += chunk.choices[0].delta.content
                         await Websocket.send_text(chunk.choices[0].delta.content)
               chat_responses.append(botResponse)

          except Exception as e:
               await Websocket.send_text(f'Error: {str(e)}')
               break


# Rendering HTML to the web page
@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return htmlTemp.TemplateResponse("homepage.html", {"request": request})

# This will be the chat main backend as data progress to the HTML file

@app.post("/", response_class=HTMLResponse)
async def chat(request: Request, user_input: Annotated[str, Form()]):
    chat_log_history.append({'role': 'user', 'content': user_input})
    chat_responses.append(user_input)
    response = gpt.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=chat_log_history,
        temperature=0.5
    )

    botResponse = response.choices[0].message.content
    chat_log_history.append({'role': 'system', 'content': botResponse})
    chat_responses.append(botResponse)
    return htmlTemp.TemplateResponse("homepage.html", {"request": request, 'chat_responses': chat_responses})
