import { NextRequest, NextResponse } from "next/server";

const OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech";
const MAX_INPUT_LENGTH = 4096;

export async function POST(req: NextRequest) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "OpenAI API key not configured" },
      { status: 500 }
    );
  }

  let text: string;
  try {
    const body = await req.json();
    text = body.text;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!text || typeof text !== "string") {
    return NextResponse.json(
      { error: "Missing 'text' field" },
      { status: 400 }
    );
  }

  // Truncate to OpenAI's input limit
  const input = text.slice(0, MAX_INPUT_LENGTH);

  const response = await fetch(OPENAI_TTS_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "tts-1",
      voice: "nova",
      input,
    }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    return NextResponse.json(
      { error: `OpenAI TTS error: ${detail}` },
      { status: response.status }
    );
  }

  const audioBytes = await response.arrayBuffer();
  return new NextResponse(audioBytes, {
    status: 200,
    headers: { "Content-Type": "audio/mpeg" },
  });
}
