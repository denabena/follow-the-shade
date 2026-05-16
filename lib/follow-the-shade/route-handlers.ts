import { buildDemoChatResponse, getAnalysis } from "./demo-backend";
import type { ChatRequest } from "./types";

const SPEECH_CONTEXT_TERMS = [
  "Follow the Shade",
  "Split",
  "Riva",
  "Bacvice",
  "Marmontova",
  "Diocletian Palace",
  "shade",
  "sunny terrace",
  "outdoor seating",
];

export async function handleFinalAnswer(request: Request): Promise<Response> {
  let body: ChatRequest;
  try {
    body = (await request.json()) as ChatRequest;
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (shouldProxyToBackend()) {
    return proxyToBackend("/chat/final_answer", body);
  }

  const response = await buildDemoChatResponse(body);
  return Response.json(response);
}

export async function handleAnalysis(
  _request: Request,
  analysisId: string,
): Promise<Response> {
  if (shouldProxyToBackend()) {
    return proxyToBackend(`/chat/analysis/${encodeURIComponent(analysisId)}`);
  }

  const record = getAnalysis(analysisId);
  if (!record) {
    return Response.json({ error: "analysis_not_found" }, { status: 404 });
  }

  return Response.json(record);
}

export async function handleSpeechKey(
  request: Request,
  kind: "stt" | "tts",
): Promise<Response> {
  if (shouldProxyToBackend()) {
    const path =
      kind === "stt" ? "/chat/speech/stt-key" : "/chat/speech/tts-key";
    let body: unknown = {};
    try {
      body = await request.json();
    } catch {
      body = {};
    }
    return proxyToBackend(path, body);
  }

  return Response.json(
    {
      error: "speech_backend_not_configured",
      message:
        "Temporary Soniox key generation belongs on the real backend. Set FOLLOW_THE_SHADE_API_BASE_URL and FOLLOW_THE_SHADE_USE_MOCK=false when that service is running.",
      context_terms: SPEECH_CONTEXT_TERMS,
    },
    { status: 501 },
  );
}

function shouldProxyToBackend(): boolean {
  return Boolean(
    process.env.FOLLOW_THE_SHADE_API_BASE_URL &&
      process.env.FOLLOW_THE_SHADE_USE_MOCK !== "true",
  );
}

async function proxyToBackend(path: string, body?: unknown): Promise<Response> {
  const baseUrl = process.env.FOLLOW_THE_SHADE_API_BASE_URL;
  if (!baseUrl) {
    return Response.json({ error: "backend_url_missing" }, { status: 500 });
  }

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (process.env.FOLLOW_THE_SHADE_API_TOKEN) {
    headers.Authorization = `Bearer ${process.env.FOLLOW_THE_SHADE_API_TOKEN}`;
  }

  const upstream = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const text = await upstream.text();

  return new Response(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}
