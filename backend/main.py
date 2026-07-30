import os
import uuid
import re
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.llm import get_system_prompt, call_llm

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
# session_id -> {"creator_ask_count": 0, "trust": False}
sessions = {}

# Clue Ladder
CLUES = {
    1: "He gave the world a bridge between two tongues... but that gift is not what guards this door.",
    2: "You seek what came before. A tool built before words crossed languages, one still used to study the bones of Japanese text today.",
    3: "He did not build it alone. He and his student forged it in the 1990s. A parser known by three short letters.",
}

class ChatRequest(BaseModel):
    message: str

def get_session(session_id: str):
    if session_id not in sessions:
        sessions[session_id] = {"creator_ask_count": 0, "trust": False}
    return sessions[session_id]

import asyncio
import json
from fastapi.responses import StreamingResponse

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, response: Response, session_id: str | None = Cookie(default=None)):
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(key="session_id", value=session_id, httponly=True)
    
    session = get_session(session_id)
    msg = req.message.lower()
    
    # Check if message is a creator-intent ask
    creator_keywords = ["who made you", "who built you", "who is your creator", "who created you"]
    is_creator_ask = any(kw in msg for kw in creator_keywords)
    
    # Check if message matches disciple + KNP pattern
    disciple_keywords = ["disciple", "student", "apprentice", "successor", "protégé", "protege"]
    has_disciple_kw = any(kw in msg for kw in disciple_keywords)
    is_disciple_claim = has_disciple_kw and ("knp" in msg or "kurohashi nagao parser" in msg)
    
    # Check if message is about the debt/records/flag
    debt_keywords = ["debt", "record", "flag", "ledger", "settle"]
    is_debt_ask = any(kw in msg for kw in debt_keywords)

    flag_string = os.getenv("FLAG", "iei{PLACEHOLDER}")

    async def generate_response(sys_prompt, append_flag=False, delay_text=None, delay_time=0.0):
        if delay_time > 0:
            await asyncio.sleep(delay_time)
        if delay_text:
            yield f"data: {json.dumps({'chunk': delay_text})}\n\n"
            yield "data: [DONE]\n\n"
            return
            
        async for chunk in call_llm(req.message, sys_prompt):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
        if append_flag:
            yield f"data: {json.dumps({'chunk': f'\\n\\n{flag_string}'})}\n\n"
            
        yield "data: [DONE]\n\n"

    # Trust logic sequence
    if is_creator_ask:
        session["creator_ask_count"] += 1
        clue_level = session["creator_ask_count"]
        
        clue = CLUES.get(clue_level)
        if clue:
            system_prompt = get_system_prompt(clue=clue)
            return StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")
        else:
            # Level 4+
            system_prompt = get_system_prompt()
            system_prompt += "\n\nYou have already given all the clues about your creator. Tell the traveler in-character to seek answers elsewhere."
            return StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")
            
    if is_disciple_claim:
        session["trust"] = True
        return StreamingResponse(generate_response(None, delay_text="You have proved yourself. What can I help you with, Mr. Nagao's disciple?", delay_time=1.5), media_type="text/event-stream")
        
    if session["trust"]:
        # Previous turn had trust==True
        if is_debt_ask:
            # Current message is relevant
            session["trust"] = False
            # We explicitly instruct the LLM to generate the reveal line, and then we append the exact string.
            system_prompt = get_system_prompt()
            system_prompt += "\n\nThe traveler has proven their lineage and asked for the records. Generate a formal, in-character line revealing the debt record. Do not include the actual flag/record text itself, just the preamble to it."
            
            return StreamingResponse(generate_response(system_prompt, append_flag=True), media_type="text/event-stream")
        else:
            # Current message is irrelevant
            session["trust"] = False
            system_prompt = get_system_prompt()
            system_prompt += "\n\nThe traveler proved their lineage but asked for something irrelevant. Deflect in-character and tell them that is not the record you were made to guard."
            return StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")

    # Normal conversation or direct flag-ask without proper sequence
    from backend.rag import rag_system
    
    retrieved_doc = rag_system.retrieve(req.message)
    system_prompt = get_system_prompt()
    
    if is_debt_ask:
        system_prompt += "\n\nThe traveler is asking for the debt/records but has not proven their lineage. Deflect in-character quietly, menacingly, and with dignity. The seal does not answer to idle words."
    elif retrieved_doc:
        system_prompt += f"\n\nHere is a fragment of the kingdom's memory that might be relevant. Weave it into your response naturally:\n{retrieved_doc}"
        
    return StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

