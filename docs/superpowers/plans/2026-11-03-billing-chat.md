# Billing Chat Implementation Plan

> Execute inline using superpowers:executing-plans.

**Goal:** Apply the approved light billing support design.
**Architecture:** Retain the Streamlit script and n8n client. Add local visual
assets and a native light theme; route suggestion buttons into the chat handler.
**Tech stack:** Python, Streamlit, CSS, SVG.
**Spec:** ../specs/2026-11-03-billing-chat-design.md

## Constraints and review focus

Keep credentials server-side; preserve client behavior and citation text. Cover
starter submission, typed submission, reset, service errors, and history replay.
Review mobile wrapping, focus visibility, contrast, and local asset loading.

## Task: Billing chat presentation and starter interaction

- [x] Add an AppTest for a starter question reaching the real chat handler.
- [x] Run it and confirm failure before implementation.
- [x] Add `.streamlit/config.toml`, `assets/billing.svg`, and `assets/chat.css`.
- [x] Update `app.py` with branding, welcome panel, accessible icons, starter
  buttons, transcript styling, and a single assistant message on failures.
- [x] Verify typed/starter requests, reset, history, and error display with
  mocked client calls. Run the full unittest suite and compile the app.

No Git executable is available in this workspace; leave changes for review.

Validation: all 10 unittest tests pass; Python compilation, SVG XML parsing,
and Streamlit theme configuration loading pass. AppTest emits its standard
bare-mode context warning. Browser rendering and mobile CSS were not visually
verified (no browser automation package installed). Streamlit floor is 1.66
to match the native UI APIs used by this app.
