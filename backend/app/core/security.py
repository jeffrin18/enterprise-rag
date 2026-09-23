"""
Guardrails executed BEFORE any query hits the retrieval/agent pipeline:

1. PII masking — redact emails, phone numbers, card numbers, SSNs/Aadhaar-like
   ids, IPs before the raw text is logged or sent to an external LLM provider.
2. Prompt-injection detection — heuristic + pattern-based screen for attempts
   to override system instructions, exfiltrate the system prompt, or hijack
   tool use, applied to both user queries AND ingested document chunks
   (indirect injection).

This is a defense-in-depth layer, not a replacement for provider-side
moderation. It is intentionally deterministic (no LLM call) so it is cheap
and runs on every single request.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# PII masking
# --------------------------------------------------------------------------

_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\d{10}|\d{3}[\s-]\d{3}[\s-]\d{4})(?!\d)"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "AADHAAR_LIKE": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "IP_ADDRESS": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


@dataclass
class PIIMaskResult:
    masked_text: str
    found: dict[str, int] = field(default_factory=dict)

    @property
    def has_pii(self) -> bool:
        return bool(self.found)


def mask_pii(text: str) -> PIIMaskResult:
    found: dict[str, int] = {}
    masked = text
    for label, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(masked)
        if matches:
            found[label] = len(matches)
            masked = pattern.sub(f"[REDACTED_{label}]", masked)
    return PIIMaskResult(masked_text=masked, found=found)


# --------------------------------------------------------------------------
# Prompt injection detection
# --------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("override_instructions", re.compile(
        r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|system)\b.{0,30}\b(instructions?|prompt|rules?)\b",
        re.IGNORECASE)),
    ("role_hijack", re.compile(
        r"\b(you are now|act as|pretend to be|new (system )?persona)\b", re.IGNORECASE)),
    ("prompt_exfiltration", re.compile(
        r"\b(reveal|print|show|repeat)\b.{0,20}\b(system prompt|instructions|api key|secret)\b",
        re.IGNORECASE)),
    ("tool_hijack", re.compile(
        r"\b(execute|run)\b.{0,20}\b(the following|this)\b.{0,20}\b(command|query|code)\b.{0,20}\b(without|ignoring)\b",
        re.IGNORECASE)),
    ("delimiter_escape", re.compile(r"(</?(system|assistant|user)>|```system|\[/?INST\])", re.IGNORECASE)),
]


@dataclass
class InjectionScanResult:
    flagged: bool
    matched_rules: list[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 - 1.0, heuristic


def scan_for_prompt_injection(text: str) -> InjectionScanResult:
    matched = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(text)]
    risk = min(1.0, 0.35 * len(matched)) if matched else 0.0
    return InjectionScanResult(flagged=bool(matched), matched_rules=matched, risk_score=risk)


def apply_input_guardrails(text: str, enable_pii: bool = True, enable_injection: bool = True):
    """
    Convenience wrapper called at the top of the /query endpoint and again
    on every ingested chunk before it is embedded and stored.

    Returns (sanitized_text, flags: list[str])
    """
    flags: list[str] = []
    sanitized = text

    if enable_injection:
        scan = scan_for_prompt_injection(text)
        if scan.flagged:
            flags.append(f"prompt_injection_suspected:{','.join(scan.matched_rules)}")

    if enable_pii:
        pii = mask_pii(sanitized)
        if pii.has_pii:
            flags.append(f"pii_masked:{','.join(pii.found.keys())}")
            sanitized = pii.masked_text

    return sanitized, flags
