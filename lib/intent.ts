import type { IntentRequest } from "./types"

const atTodayLocal = (hours: number, minutes: number): Date => {
  const d = new Date()
  d.setHours(hours, minutes, 0, 0)
  return d
}

export type SuggestionId = "sun-riva" | "shade-varos" | "sun-marmontova"

export type Suggestion = {
  id: SuggestionId
  utterance: string
}

export const suggestions: Suggestion[] = [
  {
    id: "sun-riva",
    utterance: "I want a cafe in the sun on the Riva between 3 and 5pm today."
  },
  {
    id: "shade-varos",
    utterance: "Find me somewhere shady to sit in Varoš this afternoon."
  },
  {
    id: "sun-marmontova",
    utterance: "Sunny terrace around Marmontova at noon."
  }
]

export const intentForSuggestion = (id: SuggestionId): IntentRequest => {
  if (id === "sun-riva") {
    return {
      id,
      utterance: suggestions[0].utterance,
      preference: "sun",
      windowStart: atTodayLocal(15, 0),
      windowEnd: atTodayLocal(17, 0),
      area: {
        name: "the Riva",
        center: [16.43898, 43.5074],
        radiusM: 380,
        zoom: 17
      }
    }
  }
  if (id === "shade-varos") {
    return {
      id,
      utterance: suggestions[1].utterance,
      preference: "shade",
      windowStart: atTodayLocal(14, 0),
      windowEnd: atTodayLocal(17, 0),
      area: {
        name: "Varoš",
        center: [16.43655, 43.50915],
        radiusM: 320,
        zoom: 17
      }
    }
  }
  return {
    id: "sun-marmontova",
    utterance: suggestions[2].utterance,
    preference: "sun",
    windowStart: atTodayLocal(11, 30),
    windowEnd: atTodayLocal(13, 30),
    area: {
      name: "Marmontova",
      center: [16.43785, 43.50845],
      radiusM: 280,
      zoom: 17
    }
  }
}

export const intentForFreeText = (text: string): IntentRequest => {
  const lower = text.toLowerCase()
  if (lower.includes("var")) return intentForSuggestion("shade-varos")
  if (lower.includes("marm")) return intentForSuggestion("sun-marmontova")
  if (lower.includes("shad") || lower.includes("shade"))
    return intentForSuggestion("shade-varos")
  return intentForSuggestion("sun-riva")
}
