#!/usr/bin/env python3
"""Prepare Carlos's conversation history for context mining.

Extracts human-authored user messages from Claude Code transcripts (dropping
tool results, system reminders, slash-command wrappers, and local-command
caveats), optionally filtered to messages newer than a watermark, then packs
them into balanced chronological batches for parallel agent analysis. Writes a
manifest with the max timestamp seen so the caller can advance the watermark.

Usage:
  mine_prepare.py --out <dir> [--since <ISO8601>] [--target 55000]
                  [--projects-dir ~/.claude/projects]

The --since filter is a strict lower bound: only messages with timestamp > since
are included, so re-running with the previous max_ts never re-reads old sessions.
"""
import json
import os
import glob
import re
import argparse
from collections import defaultdict


def is_tool_result(content):
    """True if the message content carries a tool_result block (machine echo)."""
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    return False


def extract_text(content):
    """Return the human text from a user message content (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def clean(text):
    """Strip machine-injected wrappers (reminders, command tags) from text."""
    if not text:
        return ""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"<local-command-[^>]*>.*?</local-command-[^>]*>", "", text, flags=re.S)
    text = re.sub(r"<command-[^>]*>.*?</command-[^>]*>", "", text, flags=re.S)
    text = re.sub(r"<command-[^>]*/>", "", text)
    return text.strip()


NOISE_PREFIXES = ("<system-reminder>", "<command-name>", "<local-command-", "Caveat:")


def looks_human(text):
    """Heuristic: keep only text a human actually typed (drop noise / bare slash cmds)."""
    if not text:
        return False
    s = text.lstrip()
    if any(s.startswith(p) for p in NOISE_PREFIXES):
        return False
    if re.fullmatch(r"/[a-z0-9_-]+\s*", s):  # bare slash command, e.g. "/effort"
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output base dir (a batches/ subdir is created)")
    ap.add_argument("--since", default=None, help="ISO timestamp; only messages strictly after this")
    ap.add_argument("--target", type=int, default=55000, help="target chars per batch")
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    args = ap.parse_args()

    batch_dir = os.path.join(args.out, "batches")
    os.makedirs(batch_dir, exist_ok=True)

    blocks = []  # (ts, sid, proj, text)
    max_ts = args.since or ""
    min_ts = ""
    for jf in sorted(glob.glob(os.path.join(args.projects_dir, "*", "*.jsonl"))):
        proj = os.path.basename(os.path.dirname(jf))
        sid = os.path.basename(jf)[:-6]
        with open(jf, errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("type") != "user":
                    continue
                msg = d.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if is_tool_result(content):
                    continue
                txt = clean(extract_text(content))
                if not looks_human(txt):
                    continue
                ts = d.get("timestamp", "") or ""
                # Incremental (--since set): drop messages at/older than the watermark
                # AND messages with no timestamp (they can't be placed relative to the
                # watermark, so re-including them every run would duplicate findings).
                # A full run (args.since is None) keeps untimestamped messages, which is
                # how they get recovered — matching "Límites conocidos" in SKILL.md.
                if args.since and (not ts or ts <= args.since):
                    continue
                blocks.append((ts, sid, proj, txt))
                if ts:
                    if ts > max_ts:
                        max_ts = ts
                    if not min_ts or ts < min_ts:
                        min_ts = ts

    blocks.sort(key=lambda x: x[0])

    # Group messages by session (preserving first-seen chronological order)
    sess_map = defaultdict(list)
    order = []
    for ts, sid, proj, txt in blocks:
        if sid not in sess_map:
            order.append((sid, proj))
        sess_map[sid].append((ts, txt))

    session_blocks = []
    for sid, proj in order:
        body = "\n".join(f"[{ts}]\n{t}" for ts, t in sess_map[sid])
        header = f"[PROJECT: {proj}] ===== SESSION {sid} ====="
        session_blocks.append(f"{header}\n{body}")

    # Greedy pack whole sessions into ~target-sized batches (never split a session)
    batches = []
    cur = []
    sz = 0
    for b in session_blocks:
        if cur and sz + len(b) > args.target:
            batches.append(cur)
            cur = []
            sz = 0
        cur.append(b)
        sz += len(b)
    if cur:
        batches.append(cur)

    for i, b in enumerate(batches, 1):
        with open(os.path.join(batch_dir, f"batch_{i:02d}.txt"), "w") as fh:
            fh.write("\n\n".join(b))

    manifest = {
        "total_messages": len(blocks),
        "total_chars": sum(len(b) for b in session_blocks),
        "n_sessions": len(session_blocks),
        "n_batches": len(batches),
        "min_ts": min_ts,
        "max_ts": max_ts,
        "since": args.since,
        "batch_dir": batch_dir,
    }
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
