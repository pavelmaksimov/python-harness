---
name: python-speech
description: Installs OpenAI speech-to-text and text-to-speech adapters for Python backends. Use when adding OGG voice transcription with a configurable model or generated MP3 speech with configurable voice instructions.
---

# OpenAI STT and TTS

Create the selected files under `project/infrastructure/adapters/` from the
templates below. Substitute the package root and existing LLM client, retry,
exception, and monitoring imports when the target repository uses other paths.

Dependencies: `openai`, `pydub`, and system `ffmpeg`.

## `speech.py`

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
    Конвертирует входной .ogg в WAV (mono, 16kHz, PCM16) и отправляет в транскрибацию.

    Для телеграм используйте скачивание в байты

    ogg_data = await voice_file.download_as_bytearray()
    await stt(ogg_data)
    """
    wav_buffer = await asyncio.to_thread(convert_ogg_to_wav_bytes, bytes(voice))

    resp = await llm_client().audio.transcriptions.create(
        model=model,
        file=wav_buffer,
        language=language,
        response_format="text",
    )

    return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))
```

## `speech.py`

```python
import io

from openai import AsyncOpenAI

def llm_client() -> AsyncOpenAI: ...

async def tts(
    text: str,
    instructions: str,
    model="gpt-4o-mini-tts",
    voice: str = "alloy",
) -> io.BytesIO:
    response = await llm_client().audio.speech.create(
        input=text, instructions=instructions, model=model, voice=voice
    )
    file = io.BytesIO(response.content)
    file.name = "voice.mp3"
    file.seek(0)

    return file
```
