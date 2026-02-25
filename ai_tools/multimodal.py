"""
multimodal.py — Multi-modal capability mixin for LLMQuery.

``MultiModalMixin`` adds image generation, text-to-speech, audio transcription,
and text embedding to any class that provides:

- ``self._get_client_for_model(model: str) -> OpenAI`` — returns a configured
  OpenAI-compatible client for the given model name.
- ``self.image_model``, ``self.tts_model``, ``self.transcription_model``,
  ``self.embedding_model`` — default model name attributes used when the
  caller does not specify an override.

All methods follow the same override pattern as ``LLMQuery.query()``:
pass ``model=None`` (or omit it) to use the instance default.

Note on Gemini transcription
----------------------------
Gemini's OpenAI-compatible endpoint does not support the
``audio/transcriptions`` REST path.  As a workaround, audio bytes are
base64-encoded and submitted as an inline data URL inside a chat completion
request.  This is handled transparently inside ``transcribe_audio()``.
"""

import base64
import io
import mimetypes
from typing import Union, List, Optional
from PIL import Image


class MultiModalMixin:
    """
    Mixin that adds image, TTS, transcription, and embedding capabilities.

    Designed to be composed with ``LLMQuery`` via multiple inheritance.
    All methods delegate to ``self._get_client_for_model()`` which must be
    implemented by the inheriting class.

    Inheriting class MUST provide:
        - ``_get_client_for_model(model: str) -> OpenAI``
        - ``image_model: str``
        - ``tts_model: str``
        - ``transcription_model: str``
        - ``embedding_model: str``
    """

    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> Image.Image:
        """
        Generate an image from a text prompt.

        Requests the image in ``b64_json`` format and decodes it into a PIL
        ``Image`` object, which can be displayed in notebooks or saved to disk
        with ``image.save("output.png")``.

        Args:
            prompt: Natural-language description of the desired image.
            model: Model override.  If ``None``, ``self.image_model`` is used.
            size: Output resolution, e.g. ``"1024x1024"``, ``"1792x1024"``.
            quality: ``"standard"`` or ``"hd"`` (where supported by the model).

        Returns:
            Image.Image: The generated image as a PIL Image object.

        Raises:
            ValueError: If the API returns no image data.
        """
        target_model = model if model is not None else getattr(self, "image_model")
        client = self._get_client_for_model(target_model)  # type: ignore[attr-defined]

        # Always request base64 output — avoids a second HTTP round-trip to
        # download from a temporary URL, and works in offline / firewalled envs.
        response = client.images.generate(  # pyrefly: ignore
            model=target_model,
            prompt=prompt,
            size=size,
            quality=quality,
            response_format="b64_json",
        )

        if not response.data or not response.data[0].b64_json:
            raise ValueError("No image data returned from API")

        # Decode the base64 image bytes and wrap in a PIL Image for easy use.
        image_data = base64.b64decode(response.data[0].b64_json)
        return Image.open(io.BytesIO(image_data))

    def generate_tts(
        self,
        text: str,
        model: Optional[str] = None,
        voice: str = "onyx",
        speed: float = 1.0,
    ) -> bytes:
        """
        Synthesise speech from text.

        Returns raw audio bytes (typically MP3) which can be written to a
        file or played with ``IPython.display.Audio``::

            audio = llm.generate_tts("Hello!")
            from IPython.display import Audio
            Audio(audio, rate=24000)

        Args:
            text: The text to convert to speech.
            model: Model override.  If ``None``, ``self.tts_model`` is used.
            voice: Speaker voice name (model-dependent, e.g. ``"onyx"``,
                ``"alloy"``, ``"nova"``).
            speed: Playback speed multiplier (0.25–4.0 for OpenAI TTS).

        Returns:
            bytes: Raw audio content (format depends on the model).
        """
        target_model = model if model is not None else getattr(self, "tts_model")
        client = self._get_client_for_model(target_model)  # type: ignore[attr-defined]

        response = client.audio.speech.create(
            model=target_model,
            input=text,
            voice=voice,
            speed=speed,
        )
        return response.content

    def transcribe_audio(
        self,
        audio_source: Union[bytes, str, io.IOBase],
        model: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio to text.

        Supports two underlying API paths depending on the model:

        - **OpenAI / Whisper models**: uses the standard
          ``audio/transcriptions`` endpoint via a file upload.
        - **Gemini models**: uses the chat completions endpoint with the audio
          embedded as a base64 data URL because Gemini's OpenAI-compatible
          layer does not currently expose ``audio/transcriptions``.

        The MIME type is inferred from the file extension where possible and
        defaults to ``audio/wav``.

        Args:
            audio_source: Input audio as a file path ``str``, raw ``bytes``,
                or a file-like object (``io.IOBase`` subclass).
            model: Model override.  If ``None``, ``self.transcription_model``
                is used.

        Returns:
            str: The transcribed text.

        Raises:
            ValueError: If ``audio_source`` is an unsupported type.
        """
        target_model = (
            model if model is not None else getattr(self, "transcription_model")
        )
        client = self._get_client_for_model(target_model)  # type: ignore[attr-defined]

        # Track whether we opened the file ourself so we can close it cleanly.
        file_obj = None
        should_close = False

        # Select the API path: Gemini needs base64 inline data in a chat call
        # because it lacks the /audio/transcriptions endpoint.
        is_gemini = "gemini" in target_model

        try:
            if is_gemini:
                # ----------------------------------------------------------------
                # Gemini workaround: embed audio as a base64 data URL inside a
                # chat completion.  The model treats it as a vision/audio input.
                # ----------------------------------------------------------------
                audio_bytes = None
                mime_type = "audio/wav"  # Conservative default if detection fails

                if isinstance(audio_source, str):
                    # File path — detect MIME from extension before reading
                    mime_type_guess = mimetypes.guess_type(audio_source)[0]
                    if mime_type_guess:
                        mime_type = mime_type_guess
                    with open(audio_source, "rb") as f:
                        audio_bytes = f.read()
                elif isinstance(audio_source, bytes):
                    audio_bytes = audio_source
                elif isinstance(audio_source, io.IOBase):
                    audio_bytes = audio_source.read()
                    # Try to infer MIME from the stream's name attribute if present
                    if hasattr(audio_source, "name") and audio_source.name:
                        mime_type_guess = mimetypes.guess_type(audio_source.name)[0]
                        if mime_type_guess:
                            mime_type = mime_type_guess
                else:
                    raise ValueError(
                        f"Unsupported audio_source type: {type(audio_source).__name__}. "
                        "Expected str (file path), bytes, or io.IOBase."
                    )

                # Encode audio to base64 so it can be embedded in the JSON payload
                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                # Submit as a multimodal chat completion using the image_url type
                # (Gemini's OpenAI compat layer accepts audio via this field)
                response = client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Transcribe the following audio.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{b64_audio}"
                                    },
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content or ""

            else:
                # ----------------------------------------------------------------
                # Standard OpenAI / Whisper path: multipart file upload
                # ----------------------------------------------------------------
                if isinstance(audio_source, str):
                    # File path: open it; mark should_close so the finally block
                    # handles cleanup even if an exception occurs mid-request.
                    file_obj = open(audio_source, "rb")
                    should_close = True
                elif isinstance(audio_source, bytes):
                    # Wrap raw bytes in a BytesIO with a .name attribute.
                    # The openai client reads .name to set Content-Disposition.
                    file_obj = io.BytesIO(audio_source)
                    file_obj.name = "audio.wav"
                elif isinstance(audio_source, io.IOBase):
                    # Use the stream directly; caller is responsible for closing.
                    file_obj = audio_source
                else:
                    raise ValueError(
                        f"Unsupported audio_source type: {type(audio_source).__name__}. "
                        "Expected str (file path), bytes, or io.IOBase."
                    )

                response = client.audio.transcriptions.create(  # pyrefly: ignore
                    model=target_model,
                    file=file_obj,
                )
                return response.text

        finally:
            # Only close files we opened ourselves; never close caller-owned streams.
            if should_close and file_obj:
                file_obj.close()  # pyrefly: ignore

    def generate_embedding(
        self,
        text: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        Generate vector embeddings for a list of strings.

        Each string is embedded independently.  The order of returned vectors
        corresponds to the order of the input list::

            vectors = llm.generate_embedding(["Hello", "World"])
            # vectors[0] is the embedding for "Hello"

        Args:
            text: List of strings to embed.  Pass a single-element list for
                one string.
            model: Model override.  If ``None``, ``self.embedding_model`` is
                used.

        Returns:
            List[List[float]]: One embedding vector per input string.
        """
        target_model = model if model is not None else getattr(self, "embedding_model")
        client = self._get_client_for_model(target_model)  # type: ignore[attr-defined]

        response = client.embeddings.create(
            model=target_model,
            input=text,
        )

        # Extract just the embedding vectors from the response objects,
        # preserving the same order as the input list.
        return [data.embedding for data in response.data]
