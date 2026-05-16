import os
import time
import requests
import json
from dotenv import dotenv_values

config = {**dotenv_values(".env"), **dotenv_values(".env.local")}

def probe_google_places_new():
    url = "https://places.googleapis.com/v1/places:searchNearby"
    key = config.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or config.get("GOOGLE_MAPS_API_KEY")
    if not key: return "Skipped", 0, 0, "No API Key"
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.displayName"}
    body = {"includedTypes": ["cafe"], "locationRestriction": {"circle": {"center": {"latitude": 43.5081, "longitude": 16.4382}, "radius": 500.0}}}
    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        count = len(resp.json().get("places", [])) if resp.status_code == 200 else 0
        return resp.status_code, elapsed, count, "" if resp.status_code == 200 else resp.text[:50]
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

def probe_google_places_legacy():
    key = config.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or config.get("GOOGLE_MAPS_API_KEY")
    if not key: return "Skipped", 0, 0, "No API Key"
    url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=43.5081,16.4382&radius=500&type=cafe&key={key}"
    start = time.time()
    try:
        resp = requests.get(url, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        data = resp.json()
        count = len(data.get("results", [])) if resp.status_code == 200 else 0
        status_msg = data.get("status") if data.get("status") != "OK" else ""
        return resp.status_code, elapsed, count, status_msg
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

def probe_overpass(query_type):
    if query_type == "buildings":
        query = '[out:json];way["building"](43.507,16.436,43.509,16.440);out count;'
    else:
        query = '[out:json];node["outdoor_seating"](around:100,43.5081,16.4382);out count;'
    url = "https://overpass-api.de/api/interpreter"
    start = time.time()
    try:
        resp = requests.post(url, data=f"data={query}", timeout=15)
        elapsed = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            count = resp.json().get("elements", [{}])[0].get("tags", {}).get("total", 0)
            return resp.status_code, elapsed, count, ""
        return resp.status_code, elapsed, 0, "Non-200"
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

def probe_open_meteo():
    url = "https://api.open-meteo.com/v1/forecast?latitude=43.5081&longitude=16.4382&start_date=2026-05-16&end_date=2026-05-16&hourly=temperature_2m"
    start = time.time()
    try:
        resp = requests.get(url, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        count = len(resp.json().get("hourly", {}).get("time", [])) if resp.status_code == 200 else 0
        return resp.status_code, elapsed, count, ""
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

def probe_soniox_key(usage_type):
    key = config.get("SONIOX_API_KEY")
    if not key: return "Skipped", 0, 0, "No API Key"
    url = "https://api.soniox.com/v1/create_temporary_key"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"usage_type": usage_type}
    start = time.time()
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        return resp.status_code, elapsed, 1 if resp.status_code == 200 else 0, ""
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

def probe_mapbox():
    token = config.get("NEXT_PUBLIC_MAPBOX_TOKEN")
    if not token: return "Skipped", 0, 0, "No Token"
    url = f"https://api.mapbox.com/styles/v1/mapbox/streets-v11?access_token={token}"
    start = time.time()
    try:
        resp = requests.get(url, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        return resp.status_code, elapsed, 1 if resp.status_code == 200 else 0, ""
    except Exception as e:
        return "Error", int((time.time() - start) * 1000), 0, str(e)[:50]

print(f"{'Provider':<25} | {'Status':<10} | {'ms':<6} | {'Count':<5} | {'Error'}")
print("-" * 75)
probes = [
    ("Google Places New", probe_google_places_new),
    ("Google Places Legacy", probe_google_places_legacy),
    ("Overpass Buildings", lambda: probe_overpass("buildings")),
    ("Overpass Seating", lambda: probe_overpass("seating")),
    ("Open-Meteo", probe_open_meteo),
    ("Soniox Key (Transcribe)", lambda: probe_soniox_key("usage_type_transcribe_websocket")),
    ("Soniox Key (TTS)", lambda: probe_soniox_key("usage_type_tts_rt")),
    ("Mapbox Style", probe_mapbox)
]
for name, func in probes:
    res = func()
    print(f"{name:<25} | {str(res[0]):<10} | {str(res[1]):<6} | {str(res[2]):<5} | {res[3]}")
print(f"{'ShadeMap':<25} | {'Not Probed':<10} | {'0':<6} | {'0':<5} | {'No obvious endpoint'}")
