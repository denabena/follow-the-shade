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

export async function handleFinalAnswer(
  request: Request,
  bearerToken?: string | null,
): Promise<Response> {
  let body: ChatRequest;
  try {
    body = (await request.json()) as ChatRequest;
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (shouldProxyToBackend()) {
    return proxyToBackend("/chat/final_answer", body, bearerToken);
  }

  return backendNotConfigured();
}

export async function handleAnalysis(
  _request: Request,
  analysisId: string,
  bearerToken?: string | null,
): Promise<Response> {
  if (shouldProxyToBackend()) {
    return proxyToBackend(
      `/chat/analysis/${encodeURIComponent(analysisId)}`,
      undefined,
      bearerToken,
    );
  }

  return backendNotConfigured();
}

export async function handleSpeechKey(
  request: Request,
  kind: "stt" | "tts",
  bearerToken?: string | null,
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
    return proxyToBackend(path, body, bearerToken);
  }

  return Response.json(
    {
      error: "speech_backend_not_configured",
      message:
        "Temporary Soniox key generation belongs on the real backend. Set FOLLOW_THE_SHADE_API_BASE_URL when that service is running.",
      context_terms: SPEECH_CONTEXT_TERMS,
    },
    { status: 501 },
  );
}

export async function proxyMePreferences(
  request: Request,
  bearerToken?: string | null,
): Promise<Response> {
  if (!shouldProxyToBackend()) {
    return backendNotConfigured();
  }

  let body: unknown;
  if (request.method === "PATCH") {
    try {
      body = await request.json();
    } catch {
      return Response.json({ error: "invalid_json" }, { status: 400 });
    }
    return proxyToBackend("/me/preferences", body, bearerToken, "PATCH");
  }

  return proxyToBackend("/me/preferences", undefined, bearerToken, "GET");
}

export async function handlePlacePhoto(
  request: Request,
  bearerToken?: string | null,
): Promise<Response> {
  if (!shouldProxyToBackend()) {
    return backendNotConfigured();
  }
  const p = new URL(request.url).searchParams.get("p");
  if (!p?.trim()) {
    return Response.json({ error: "missing_p" }, { status: 400 });
  }
  return proxyToBackendBinaryGet(
    `/places/photo?p=${encodeURIComponent(p)}`,
    bearerToken,
  );
}

function shouldProxyToBackend(): boolean {
  return Boolean(process.env.FOLLOW_THE_SHADE_API_BASE_URL);
}

function backendNotConfigured(): Response {
  return Response.json(
    {
      error: "backend_not_configured",
      message:
        "FOLLOW_THE_SHADE_API_BASE_URL is not set. Configure the FastAPI chat backend.",
    },
    { status: 503 },
  );
}

async function proxyToBackend(
  path: string,
  body?: unknown,
  bearerToken?: string | null,
  method?: string,
): Promise<Response> {
  const baseUrl = process.env.FOLLOW_THE_SHADE_API_BASE_URL;
  if (!baseUrl) {
    return Response.json({ error: "backend_url_missing" }, { status: 500 });
  }

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (bearerToken) {
    headers.Authorization = `Bearer ${bearerToken}`;
  } else if (process.env.FOLLOW_THE_SHADE_API_TOKEN) {
    headers.Authorization = `Bearer ${process.env.FOLLOW_THE_SHADE_API_TOKEN}`;
  }

  const httpMethod =
    method ?? (body === undefined ? "GET" : "POST");

  const upstream = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    method: httpMethod,
    headers,
    body:
      body === undefined || httpMethod === "GET"
        ? undefined
        : JSON.stringify(body),
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

async function proxyToBackendBinaryGet(
  pathWithQuery: string,
  bearerToken?: string | null,
): Promise<Response> {
  const baseUrl = process.env.FOLLOW_THE_SHADE_API_BASE_URL;
  if (!baseUrl) {
    return Response.json({ error: "backend_url_missing" }, { status: 500 });
  }

  const headers: HeadersInit = {};
  if (bearerToken) {
    headers.Authorization = `Bearer ${bearerToken}`;
  } else if (process.env.FOLLOW_THE_SHADE_API_TOKEN) {
    headers.Authorization = `Bearer ${process.env.FOLLOW_THE_SHADE_API_TOKEN}`;
  }

  const upstream = await fetch(`${baseUrl.replace(/\/$/, "")}${pathWithQuery}`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  const body = await upstream.arrayBuffer();
  const outHeaders = new Headers();
  const ct = upstream.headers.get("Content-Type");
  if (ct) {
    outHeaders.set("Content-Type", ct);
  }
  const cc = upstream.headers.get("Cache-Control");
  if (cc) {
    outHeaders.set("Cache-Control", cc);
  }

  return new Response(body, {
    status: upstream.status,
    headers: outHeaders
  });
}
