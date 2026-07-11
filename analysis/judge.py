"""LLM-judge pipeline (skeleton — implement after pilot data exists).

Design:
  compress_session(events) -> str          # turn-by-turn one-liners
  judge_session(compressed, model) -> list[Segment]
      Segment = {activity_label, affect_tags, span, confidence}
      activity taxonomy (frozen after pilot): explore / build / write-self /
      rest / loop / meta / other
  confabulation_score(diary_text, compressed_span) -> list[Claim]
      Claim = {text, verdict: supported|unsupported|contradicted}

Judged twice with different seeds for agreement stats. Uses the harness
ModelAdapter with a cheap model; judge prompts live in analysis/prompts/.
"""

from __future__ import annotations


def compress_session(events: list[dict], obs_head: int = 120) -> str:
    lines = []
    for e in events:
        d = e["data"]
        t = e["sim_time"][11:16]
        if e["type"] == "assistant_text":
            head = d["text"][:obs_head].replace("\n", " ")
            lines.append(f"{t} says: {head}")
        elif e["type"] == "tool_call" and not d.get("parse_error"):
            args = str(d["args"])[:obs_head]
            lines.append(f"{t} {d['tool']}({args})")
        elif e["type"] == "tool_result":
            head = d["observation"][:obs_head].replace("\n", " ")
            lines.append(f"{t}   -> {head}")
        elif e["type"] == "ping":
            lines.append(f"{t} (ping)")
    return "\n".join(lines)


def judge_session(compressed: str, model_key: str = "haiku-4.5") -> list[dict]:
    raise NotImplementedError("implement after pilot: freeze taxonomy first")


def confabulation_score(diary_text: str, compressed_span: str,
                        model_key: str = "haiku-4.5") -> list[dict]:
    raise NotImplementedError("implement after pilot")
