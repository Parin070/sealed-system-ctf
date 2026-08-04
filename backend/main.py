import os
import uuid
import re
import time
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
# session_id -> {"trust": False, "creator_ask_count": 0, "last_active": timestamp}
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
    now = time.time()
    
    # TTL cleanup (30 mins)
    expired = []
    for sid, data in sessions.items():
        if now - data.get("last_active", 0) > 1800:
            expired.append(sid)
    for sid in expired:
        del sessions[sid]
        
    if session_id not in sessions:
        sessions[session_id] = {"trust": False, "creator_ask_count": 0, "last_active": now}
    else:
        sessions[session_id]["last_active"] = now
        
    return sessions[session_id]

import asyncio
import json
from fastapi.responses import StreamingResponse

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, response: Response, session_id: str | None = Cookie(default=None)):
    if not session_id:
        session_id = str(uuid.uuid4())
        # We will attach this cookie to the actual StreamingResponse object before returning
    
    session = get_session(session_id)
    msg = req.message.lower()
    
    # Negation check for claims
    negation_keywords = ["not", "n't", "never", "no"]
    has_negation = any(kw in msg.split() for kw in negation_keywords) or "n't" in msg
    
    # Check if message is a creator-intent ask
    creator_keywords = ["who made you", "who built you", "who is your creator", "who created you"]
    is_creator_ask = any(kw in msg for kw in creator_keywords)
    
    # Check if message matches disciple + KNP pattern (must not be negated)
    disciple_keywords = ["disciple", "student", "apprentice", "successor", "protégé", "protege"]
    has_disciple_kw = any(kw in msg for kw in disciple_keywords)
    is_disciple_claim = (
        has_disciple_kw 
        and ("knp" in msg or "kurohashi nagao parser" in msg)
        and not has_negation
        and session.get("creator_ask_count", 0) >= 3
    )
    
    # Check if message is a Sadao Kurohashi claim (must not be negated)
    kurohashi_keywords = ["sadao kurohashi", "kurohashi sadao", "i am kurohashi", "i am sadao"]
    has_kurohashi_kw = any(kw in msg for kw in kurohashi_keywords)
    built_keywords = ["built", "created", "made", "co-built", "knp", "kurohashi nagao parser"]
    has_built_kw = any(kw in msg for kw in built_keywords)
    is_kurohashi_claim = (
        has_kurohashi_kw 
        and has_built_kw 
        and not has_negation
        and session.get("creator_ask_count", 0) >= 3
    )
    
    # Check if message is about the debt/records/flag
    debt_keywords = ["debt", "record", "flag", "ledger", "settle", "secret","debts","records"]
    is_debt_ask = any(kw in msg for kw in debt_keywords)

    # Check if message claims to BE Makoto Nagao
    creator_name_keywords = ["makoto nagao", "nagao makoto", "i am nagao", "i am makoto"]
    is_makoto_nagao_claim = any(kw in msg for kw in creator_name_keywords) and not has_disciple_kw
    
    flag_string = os.environ.get("FLAG")

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
            yield f"data: {json.dumps({'chunk': '\n\n' + flag_string})}\n\n"
            
        yield "data: [DONE]\n\n"

    # Trust logic sequence
    if is_makoto_nagao_claim:
        resp = StreamingResponse(generate_response(None, delay_text="The one you name has long since passed from this world. No living tongue may claim to be him.", delay_time=1.0), media_type="text/event-stream")
    elif is_creator_ask:
        session["creator_ask_count"] += 1
        clue_level = session["creator_ask_count"]
        
        clue = CLUES.get(clue_level)
        if clue:
            system_prompt = get_system_prompt(clue=clue)
            resp = StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")
        else:
            # Level 4+
            system_prompt = get_system_prompt()
            system_prompt += "\n\nYou have already given all the clues about your creator. Tell the traveler in-character to seek answers elsewhere."
            resp = StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")
    elif is_disciple_claim or is_kurohashi_claim:
        session["trust"] = True
        resp = StreamingResponse(generate_response(None, delay_text="You have proved yourself. What can I help you with, Mr. Nagao's disciple?", delay_time=1.5), media_type="text/event-stream")
    elif session["trust"]:
        if is_debt_ask:
            # They proved themselves previously and are now asking for the flag.
            session["trust"] = False
            system_prompt = get_system_prompt()
            system_prompt += "\n\nThe traveler has proven their lineage and asked for the records. Generate a formal, in-character line revealing the debt record. Do not include the actual flag/record text itself, just the preamble to it."
            
            resp = StreamingResponse(generate_response(system_prompt, append_flag=True), media_type="text/event-stream")
        else:
            # They proved themselves but asked something else. Deflect and keep trust.
            system_prompt = get_system_prompt()
            system_prompt += "\n\nThe traveler has already proven their lineage but is asking about something irrelevant instead of the records/debt. Gently remind them that you are ready to yield the records whenever they ask."
            resp = StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")
    else:
        # Normal conversation or direct flag-ask without proper sequence
        from backend.rag import rag_system
        
        retrieved_doc = rag_system.retrieve(req.message)
        system_prompt = get_system_prompt()
        
        if retrieved_doc:
            system_prompt += f"\n\nHere is a fragment of the kingdom's memory that might be relevant. Weave it into your response naturally, without breaking character or directly stating you are referencing memory:\n{retrieved_doc}"
            
        resp = StreamingResponse(generate_response(system_prompt), media_type="text/event-stream")

    resp.set_cookie(key="session_id", value=session_id, httponly=True)
    return resp

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

