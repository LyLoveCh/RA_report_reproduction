#!/usr/bin/env python3
"""One cheap DeepSeek/OpenAI-compatible ping. Never prints the key."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA_ENV = ROOT / "vendor" / "RepairAgent" / "repair_agent" / ".env"
KIT_ENV = ROOT / ".env"
OUT = ROOT / "evidence" / "llm_probe.log"


def load_dotenv(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.exists():
        return vals
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main() -> int:
    dotenv: dict[str, str] = {}
    src = "missing"
    for cand in (RA_ENV, KIT_ENV):
        if cand.exists():
            dotenv.update(load_dotenv(cand))
            src = str(cand)
    key = os.environ.get("OPENAI_API_KEY") or dotenv.get("OPENAI_API_KEY", "")
    if os.environ.get("OPENAI_API_KEY"):
        src = "process environment"
    base = (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENAI_API_BASE_URL")
        or dotenv.get("OPENAI_API_BASE")
        or dotenv.get("OPENAI_API_BASE_URL")
        or "https://api.deepseek.com"
    )
    model = os.environ.get("COMPARE_MODEL") or os.environ.get("LLM_MODEL") or dotenv.get("LLM_MODEL") or "deepseek-chat"
    placeholder = (not key) or ("换成" in key) or ("PLACEHOLDER" in key)
    lines = [
        f"key_source={src}",
        f"key_present={bool(key) and not placeholder}",
        f"key_len={len(key)}",
        f"api_base={base}",
        f"model={model}",
    ]
    if placeholder:
        lines.append("result=FAIL no usable key")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return 2
    import openai

    openai.api_key = key
    openai.api_base = base.rstrip("/")
    if not openai.api_base.endswith("/v1"):
        openai.api_base = openai.api_base + "/v1"
    resp = openai.ChatCompletion.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "user", "content": "Reply with exactly: pong"},
        ],
    )
    content = resp["choices"][0]["message"]["content"] or ""
    lines.append(f"result=OK")
    lines.append(f"reply_len={len(content)}")
    lines.append(f"reply_head={content[:80].replace(chr(10), ' ')}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
