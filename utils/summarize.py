"""Plain-English failure summarisation (docs/TESTING_REBUILD_SPEC.md Days 4-6).

Composes a single readable line from a failure's step name, exception text,
and captured console/network diagnostics, so a failure explains itself on
the dashboard without anyone opening the raw pytest traceback.

No external LLM call is wired up by default -- no API key is configured for
this repo. If ANTHROPIC_API_KEY is set, an LLM pass is attempted for a
tighter summary; otherwise this falls back to a deterministic composed line,
which is already a large improvement over the raw 300-char-truncated pytest
longrepr previously shown in the dashboard widget.
"""
import os
import re


def _shorten(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _extract_reason(exception_text: str) -> str:
    """Playwright's own error text is usually readable on its own -- pull
    just the headline plus the last "Call log:" line (where Playwright puts
    the specific actionable detail, e.g. "waiting for locator(...) to be
    visible") rather than the surrounding traceback noise."""
    # pytest prefixes each line of an assertion failure with "E " -- strip it.
    cleaned = re.sub(r"(?m)^E\s?", "", exception_text)

    m = re.search(r"(?:Timeout)?Error: (.+)", cleaned, re.DOTALL)
    if not m:
        lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
        for line in reversed(lines):
            if "AssertionError" in line:
                return _shorten(line)
        return _shorten(lines[-1]) if lines else "failed (see raw error)"

    rest = m.group(1)
    headline = rest.split("\n", 1)[0].strip()

    call_log = re.search(r"Call log:\n(.*)", rest, re.DOTALL)
    if call_log:
        # Stop at the first blank line -- pytest appends a "<file>:<line>: <ExceptionType>"
        # footer after one, which isn't part of the actual call log.
        log_block = call_log.group(1).split("\n\n")[0]
        log_lines = [l.strip(" -") for l in log_block.splitlines() if l.strip()]
        if log_lines:
            return _shorten(f"{headline} — {log_lines[-1]}")

    return _shorten(headline)


def summarize_failure(
    test_name: str,
    step: str | None,
    exception_text: str,
    console_errors: list,
    page_errors: list,
    failed_requests: list,
) -> str:
    """Compose a single readable line describing a test failure."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _summarize_with_llm(
                test_name, step, exception_text, console_errors, page_errors, failed_requests
            )
        except Exception as e:
            print(f"[summarize] LLM summarisation failed, falling back to deterministic summary: {e}")

    parts = ["Failed"]
    if step:
        parts.append(f'during "{step}"')
    parts.append(f"— {_extract_reason(exception_text)}")

    extra = []
    if page_errors:
        extra.append(f"{len(page_errors)} JS error(s), e.g. {_shorten(page_errors[0], 100)!r}")
    if failed_requests:
        extra.append(f"{len(failed_requests)} failed request(s), e.g. {_shorten(failed_requests[0], 100)!r}")
    if console_errors:
        extra.append(f"{len(console_errors)} console error/warning(s)")
    if extra:
        parts.append("[" + "; ".join(extra) + "]")

    return " ".join(parts)


def _summarize_with_llm(test_name, step, exception_text, console_errors, page_errors, failed_requests) -> str:
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        f"A Playwright browser test named '{test_name}' just failed"
        + (f" during the step '{step}'" if step else "")
        + ".\n\nException:\n" + exception_text[:2000]
        + "\n\nConsole errors:\n" + "\n".join(console_errors[:10])
        + "\n\nUnhandled JS page errors:\n" + "\n".join(page_errors[:10])
        + "\n\nFailed network requests:\n" + "\n".join(failed_requests[:10])
        + "\n\nWrite ONE short, plain-English sentence (no jargon, no code) "
          "explaining what went wrong and roughly where, for a non-technical "
          "staff member reading a results dashboard. Just the sentence, no preamble."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
