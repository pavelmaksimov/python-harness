# Speech adapter (OpenAI STT / TTS)

Render into `project/infrastructure/adapters/speech.py` (copy only if missing).
Reuse the target repository's LLM client factory (shown here as `llm_client()`)
plus its retry, exception, and logging conventions. Dependencies: `openai`,
`pydub`, and system `ffmpeg`.

```python
import asyncio
from io import BytesIO

from openai import AsyncOpenAI
from pydub import AudioSegment

def llm_client() -> AsyncOpenAI: ...

def convert_ogg_to_wav(ogg_data: bytes) -> BytesIO:
    """
    Converts OGG audio from bytes to WAV (mono, 16kHz, PCM16) and returns BytesIO.
    """
    audio = AudioSegment.from_ogg(BytesIO(ogg_data))
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    wav_buffer = BytesIO()
    audio.export(wav_buffer, format="wav")
    wav_buffer.seek(0)
    wav_buffer.name = "audio.wav"

    return wav_buffer


async def stt(
    voice: bytes | bytearray,
    model: str,
    language: str = "ru",
) -> str:
    """
    Converts an .ogg voice message to WAV and transcribes it.

    Download Telegram voice messages as bytes first:

    ogg_data = await voice_file.download_as_bytearray()
    text = await stt(bytes(ogg_data), model="whisper-1")
    """
    wav_buffer = await asyncio.to_thread(convert_ogg_to_wav, bytes(voice))

    resp = await llm_client().audio.transcriptions.create(
        model=model,
        file=wav_buffer,
        language=language,
        response_format="text",
    )

    return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))


async def tts(
    text: str,
    instructions: str,
    model: str = "gpt-4o-mini-tts",
    voice: str = "alloy",
) -> BytesIO:
    response = await llm_client().audio.speech.create(
        input=text, instructions=instructions, model=model, voice=voice
    )
    file = BytesIO(response.content)
    file.name = "voice.mp3"
    file.seek(0)

    return file
```
