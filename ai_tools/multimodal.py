"""
multimodal.py — Multi-modal capability mixin for Agent.

``MultiModalMixin`` adds image generation, text-to-speech, audio transcription,
and text embedding to any class. It leverages the unified client factory
and tracing infrastructure from the ai_tools package.
"""

import base64
import io
import mimetypes
from typing import Union, List, Optional, Dict, Any, TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from .agent import Agent

class MultiModalMixin:
    """
    Mixin that adds image, TTS, transcription, and embedding capabilities.

    Designed to be composed with ``Agent`` via inheritance.
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
        """
        from .agent import get_client
        from .config import strip_provider_prefix
        
        target_model = model if model is not None else getattr(self, "image_model", "openai/dall-e-3")
        client = get_client(target_model)
        _, api_model = strip_provider_prefix(target_model)

        response = client.images.generate(
            model=api_model,
            prompt=prompt,
            size=size,
            quality=quality,
            response_format="b64_json",
        )

        if not response.data or not response.data[0].b64_json:
            raise ValueError("No image data returned from API")

        image_data = base64.b64decode(response.data[0].b64_json)
        return Image.open(io.BytesIO(image_data))

    def generate_tts(
        self,
        text: str,
        model: Optional[str] = None,
        voice: str = "onyx",
        speed: float = 1.0,
    ) -> bytes:
        """ Synthesise speech from text. """
        from .agent import get_client
        from .config import strip_provider_prefix

        target_model = model if model is not None else getattr(self, "tts_model", "openai/tts-1")
        client = get_client(target_model)
        _, api_model = strip_provider_prefix(target_model)

        response = client.audio.speech.create(
            model=api_model,
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
        """ Transcribe audio to text. """
        from .agent import get_client
        from .config import strip_provider_prefix

        target_model = model if model is not None else getattr(self, "transcription_model", "openai/whisper-1")
        client = get_client(target_model)
        provider, api_model = strip_provider_prefix(target_model)

        # Track whether we opened the file ourself so we can close it cleanly.
        file_obj = None
        should_close = False
        is_gemini = provider == "gemini"

        try:
            if is_gemini:
                audio_bytes = None
                mime_type = "audio/wav"

                if isinstance(audio_source, str):
                    mime_type_guess = mimetypes.guess_type(audio_source)[0]
                    if mime_type_guess:
                        mime_type = mime_type_guess
                    with open(audio_source, "rb") as f:
                        audio_bytes = f.read()
                elif isinstance(audio_source, bytes):
                    audio_bytes = audio_source
                elif isinstance(audio_source, io.IOBase):
                    audio_bytes = audio_source.read()
                    if hasattr(audio_source, "name") and audio_source.name:
                        mime_type_guess = mimetypes.guess_type(audio_source.name)[0]
                        if mime_type_guess:
                            mime_type = mime_type_guess
                else:
                    raise ValueError(f"Unsupported audio_source type: {type(audio_source).__name__}")

                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                response = client.chat.completions.create(
                    model=api_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Transcribe the following audio."},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime_type};base64,{b64_audio}"},
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content or ""

            else:
                if isinstance(audio_source, str):
                    file_obj = open(audio_source, "rb")
                    should_close = True
                elif isinstance(audio_source, bytes):
                    file_obj = io.BytesIO(audio_source)
                    file_obj.name = "audio.wav"
                elif isinstance(audio_source, io.IOBase):
                    file_obj = audio_source
                else:
                    raise ValueError(f"Unsupported audio_source type: {type(audio_source).__name__}")

                response = client.audio.transcriptions.create(
                    model=api_model,
                    file=file_obj,
                )
                return response.text

        finally:
            if should_close and file_obj:
                file_obj.close()

    def generate_embedding(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """ Generate vector embeddings for a list of strings. """
        from .agent import get_client
        from .config import strip_provider_prefix
        from .tracing import get_langfuse_params, propagate_langfuse_attributes

        target_model = model if model is not None else getattr(self, "embedding_model", "openai/text-embedding-3-small")
        client = get_client(target_model)
        provider, api_model = strip_provider_prefix(target_model)

        agent_name = getattr(self, "name", "Agent")
        user_id = getattr(self, "user_id", None)
        session_id = getattr(self, "session_id", None)

        lparams = get_langfuse_params(
            model=api_model,
            agent_name=agent_name,
            name_prefix="embedding",
            include_model=True,
            user_id=user_id,
            session_id=session_id,
        )
        lparams.setdefault("metadata", {})["provider"] = provider

        with propagate_langfuse_attributes(
            session_id=session_id,
            user_id=user_id,
            tags=[agent_name, provider],
        ):
            response = client.embeddings.create(
                model=api_model,
                input=texts,
                **lparams
            )
            
        return [data.embedding for data in response.data]
