from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any


def render_digest_email(
    map_payload: dict[str, Any],
    schedule: dict[str, Any],
    *,
    app_public_url: str = "http://localhost:3000",
) -> tuple[str, str, str]:
    request = map_payload.get("request") or {}
    area = str(schedule.get("area") or request.get("location_label") or "Split")
    preset = str(schedule.get("time_window_preset") or "afternoon")
    preference = str(schedule.get("exposure_preference") or request.get("preference") or "shade")
    results = list(map_payload.get("results") or [])[:3]

    subject = f"Your {area} {preference} picks for {preset}"
    if not results:
        text = (
            f"Follow the Shade could not find cafe picks for {area} "
            f"{preset}. Try changing your notification area or time window."
        )
        html = f"<p>{escape(text)}</p>"
        return subject, html, text

    intro = (
        f"Here are your best {preference} terrace picks near {area} "
        f"for {preset}."
    )
    text_lines = [intro, ""]
    html_items = []
    for index, result in enumerate(results, start=1):
        name = str(result.get("name") or "Cafe")
        exposure = result.get("exposure") or {}
        summary = str(exposure.get("summary") or "Exposure timing is available in the app.")
        samples = _format_samples(exposure.get("samples") or [])
        score = exposure.get("match_score")
        score_text = (
            f" Match score: {round(float(score) * 100)}%."
            if isinstance(score, (int, float))
            else ""
        )
        text_lines.append(f"{index}. {name}: {summary}{score_text}")
        if samples:
            text_lines.append(f"   Timeline: {samples}")
        html_items.append(
            "<li>"
            f"<strong>{escape(name)}</strong><br>"
            f"{escape(summary)}{escape(score_text)}"
            f"{f'<br><span>{escape(samples)}</span>' if samples else ''}"
            "</li>"
        )

    link = _analysis_link(map_payload, app_public_url)
    if link:
        text_lines.extend(["", f"Open this shade map: {link}"])

    text = "\n".join(text_lines)
    link_html = (
        f'<p><a href="{escape(link)}">Open this shade map</a></p>' if link else ""
    )
    html = (
        "<main>"
        "<h1>Follow the Shade</h1>"
        f"<p>{escape(intro)}</p>"
        f"<ol>{''.join(html_items)}</ol>"
        f"{link_html}"
        "</main>"
    )
    return subject, html, text


def _format_samples(samples: list[dict[str, Any]]) -> str:
    parts = []
    for sample in samples[:5]:
        raw_time = str(sample.get("time") or "")
        state = str(sample.get("state") or "")
        if not raw_time or not state:
            continue
        parts.append(f"{_short_time(raw_time)} {state}")
    return ", ".join(parts)


def _short_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return value[:5]


def _analysis_link(map_payload: dict[str, Any], app_public_url: str) -> str:
    analysis_id = map_payload.get("analysis_id")
    if not analysis_id:
        return ""
    base_url = app_public_url.strip().rstrip("/") or "http://localhost:3000"
    return f"{base_url}/?analysis_id={analysis_id}"
