from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .qdrant_db import (
    get_conversations_collection,
    get_summaries_collection,
    get_turns_collection,
)


import json

def persist_turn(
    conversation_id: str, 
    turns: Iterable[Tuple[str, str]], 
    *, 
    paired: Tuple[str, str],
    files: Optional[List[Dict[str, str]]] = None
) -> int:
    turns_coll = get_turns_collection()
    convs_coll = get_conversations_collection()
    
    timestamp = datetime.now().isoformat()
    current_time_float = time.time()
    
    turn_id_base = int(current_time_float * 1000)
    
    messages_to_add = []
    ids = []
    metadatas = []
    
    offset = 0
    final_turn_id = turn_id_base
    
    # Serialize files for storage if present
    # We attribute files to the 'user' message usually.
    files_json = json.dumps(files) if files else ""
    
    for role, text in turns:
        offset += 1
        this_id = str(turn_id_base + offset)
        final_turn_id = int(this_id)
        
        # We store each message as a document
        messages_to_add.append(text)
        ids.append(f"{conversation_id}_{this_id}")
        
        meta = {
            "conversation_id": conversation_id,
            "role": role,
            "turn_id": final_turn_id, # Store as int for filtering
            "timestamp": timestamp
        }
        
        # Attach files metadata to 'user' role message if files exist
        # Assuming typical flow: User sends files + message -> Model replies.
        if role == "user" and files_json:
            meta["files"] = files_json
            
        metadatas.append(meta)

    if messages_to_add:
        turns_coll.add(
            documents=messages_to_add,
            metadatas=metadatas,
            ids=ids
        )

    # Update conversation metadata (last activity)
    existing = convs_coll.get(ids=[conversation_id])
    now_iso = timestamp
    
    if existing and existing["ids"]:
        # Update
        convs_coll.update(
            ids=[conversation_id],
            metadatas=[{
                "updated_at": now_iso,
                **existing['metadatas'][0],
                "updated_at": now_iso
            }]
        )
    else:
        # Create
        user_text, _ = paired
        title = (user_text or "Percakapan Baru")[:50]
        convs_coll.add(
            ids=[conversation_id],
            metadatas=[{
                "created_at": now_iso,
                "updated_at": now_iso,
                "title": title
            }],
            documents=["Conversation Metadata"]
        )

    return final_turn_id


def fetch_history(conversation_id: str) -> List[Dict[str, Any]]:
    turns_coll = get_turns_collection()
    
    results = turns_coll.get(
        where={"conversation_id": conversation_id},
        include=["metadatas", "documents"]
    )
    
    if not results or not results["ids"]:
        return []
    
    # Pack into list of tuples (turn_id, role, text, files)
    data = []
    for meta, text in zip(results["metadatas"], results["documents"]):
        # Parse files if present
        files = []
        if "files" in meta and meta["files"]:
            try:
                files = json.loads(meta["files"])
            except json.JSONDecodeError:
                pass
        
        data.append((meta["turn_id"], meta["role"], text, files))
        
    # Sort by turn_id
    data.sort(key=lambda x: x[0])
    
    history: List[Dict[str, Any]] = []
    for _, role, text, files in data:
        r = "model" if role == "ai" or role == "model" else role
        entry = {"role": r, "text": text}
        if files:
            entry["files"] = files
        history.append(entry)
        
    return history


def fetch_recent_turns(conversation_id: str, limit: int) -> List[Dict[str, str]]:
    # Similar to fetch_history but we only want the last N messages?
    # Or last N *turns*? The original SQL was 'turns' table which had paired user/ai.
    # Here we have individual messages.
    # If limit is N turns, that's 2*N messages roughly.
    
    turns_coll = get_turns_collection()
    results = turns_coll.get(
        where={"conversation_id": conversation_id},
        include=["metadatas", "documents"]
    )
    
    if not results or not results["ids"]:
        return []
        
    data = []
    for meta, text in zip(results["metadatas"], results["documents"]):
        data.append((meta["turn_id"], meta["role"], text))
        
    data.sort(key=lambda x: x[0])
    
    # The original expected (limit) turns, where a turn is user+ai.
    # We'll just return the last limit * 2 messages to approximate.
    
    recent_data = data[-(limit * 2):] if limit > 0 else []
    
    history: List[Dict[str, str]] = []
    for _, role, text in recent_data:
        r = "model" if role == "ai" or role == "model" else role
        history.append({"role": r, "text": text})
        
    return history


def get_summary_state(conversation_id: str) -> Tuple[str, int]:
    if not conversation_id:
        return "", 0
        
    summ_coll = get_summaries_collection()
    result = summ_coll.get(ids=[conversation_id])
    
    if result and result["ids"]:
        doc = result["documents"][0]
        meta = result["metadatas"][0]
        last_id = int(meta.get("last_processed_turn_id", 0))
        return doc, last_id
        
    return "", 0


def save_summary_state(
    conversation_id: str,
    summary: str,
    last_turn_id: int,
    *,
    max_chars: int,
) -> None:
    if not conversation_id:
        return

    summary = (summary or "").strip()
    if max_chars > 0:
        summary = summary[:max_chars]
        
    summ_coll = get_summaries_collection()
    
    # Upsert
    summ_coll.upsert(
        ids=[conversation_id],
        documents=[summary],
        metadatas=[{
            "conversation_id": conversation_id,
            "last_processed_turn_id": last_turn_id,
            "updated_at": datetime.now().isoformat()
        }]
    )


def load_unsummarized_turns(
    conversation_id: str, last_turn_id: int
) -> List[Tuple[int, str, str]]:
    # This needs to return (id, user_text, ai_text) tuples
    # querying for turn_id > last_turn_id
    turns_coll = get_turns_collection()
    
    # Filter: turn_id > X
    results = turns_coll.get(
        where={
            "$and": [
                {"conversation_id": {"$eq": conversation_id}},
                {"turn_id": {"$gt": last_turn_id}}
            ]
        },
        include=["metadatas", "documents"]
    )
    
    if not results or not results["ids"]:
        return []
        
    data = []
    for meta, text in zip(results["metadatas"], results["documents"]):
        data.append((meta["turn_id"], meta["role"], text))
        
    data.sort(key=lambda x: x[0])
    
    # Reconstruct paired turns (user, ai)
    # This is heuristic since we store messages individually now.
    # We iterate and group user followed by model.
    
    paired = []
    current_user = None
    
    for tid, role, text in data:
        if role == "user":
            if current_user:
                # Previous user msg had no response, push it alone?
                # Or wait. simpler to just handle user -> model pairs.
                pass
            current_user = (tid, text)
        elif role == "model" or role == "ai":
            if current_user:
                utid, utext = current_user
                # Use the Model's ID as the 'turn' ID? Or the user's?
                # Original logic: ID of the turn row (which contained both).
                # We'll use the Model's message ID (later in time) as the "turn completed" check.
                paired.append((tid, utext, text))
                current_user = None
    
    return paired


def count_turns(conversation_id: str) -> int:
    turns_coll = get_turns_collection()
    results = turns_coll.get(
        where={"conversation_id": conversation_id},
        include=["metadatas"]
    )
    # Approx check: count user messages?
    count = 0
    if results and results["ids"]:
        for meta in results["metadatas"]:
            if meta["role"] == "user":
                count += 1
    return count


def list_conversations(limit: int = 50) -> List[Dict[str, str]]:
    convs_coll = get_conversations_collection()
    # List all, sort manually by updated_at
    # Fetch all metadata then sort by updated_at.
    
    results = convs_coll.get(include=["metadatas"])
    
    items = []
    if results and results["ids"]:
        for mid, meta in zip(results["ids"], results["metadatas"]):
            items.append({
                "conversation_id": mid,
                "title": meta.get("title", "Percakapan"),
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at")
            })
            
    # Sort desc
    items.sort(key=lambda x: x["updated_at"] or "", reverse=True)
    
    final_list = []
    for item in items[:limit]:
        # fetch preview?
        # Ideally we'd store preview in metadata.
        # For now, let's leave preview generic or fetch last message if critical.
        # We'll say "Lihat detail..."
        final_list.append({
            "conversation_id": item["conversation_id"],
            "title": item["title"],
            "preview": "...",
            "created_at": item["created_at"],
            "updated_at": item["updated_at"]
        })
        
    return final_list


def delete_conversation(conversation_id: str) -> bool:
    if not conversation_id:
        return False
        
    convs_coll = get_conversations_collection()
    turns_coll = get_turns_collection()
    summ_coll = get_summaries_collection()
    
    # Check existence
    existing = convs_coll.get(ids=[conversation_id])
    if not existing or not existing["ids"]:
        return False
        
    convs_coll.delete(ids=[conversation_id])
    summ_coll.delete(ids=[conversation_id])
    
    # Delete turns
    turns_coll.delete(where={"conversation_id": conversation_id})
    
    return True

__all__ = [
    "persist_turn",
    "fetch_history",
    "fetch_recent_turns",
    "get_summary_state",
    "save_summary_state",
    "load_unsummarized_turns",
    "count_turns",
    "list_conversations",
    "delete_conversation",
]
