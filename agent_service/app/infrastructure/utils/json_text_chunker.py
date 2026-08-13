import re
import json
from typing import List, Union
import tiktoken

class JsonTextChunker:
    """
    A hybrid chunker for Agno that safely chunks prompts
    containing both text and JSON/code sections.
    """
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def _is_json_block(self, text: str) -> bool:
        """Check if text looks like valid JSON."""
        text = text.strip()
        if not (text.startswith("{") or text.startswith("[")):
            return False
        try:
            json.loads(text)
            return True
        except Exception:
            return False

    def chunk(self, text: str) -> List[str]:
        """
        Splits mixed JSON + text data into safe chunks.
        Each chunk length ≈ chunk_size with slight overlap.
        """
        chunks = []

        # Split by code fences, JSON blocks, or large newlines
        parts = re.split(r"(```.*?```|\{.*?\}|\n{2,})", text, flags=re.S)

        current_chunk = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # If JSON block → keep whole
            if self._is_json_block(part):
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.append(part)
                continue

            # Otherwise, add text normally
            if len(current_chunk) + len(part) > self.chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # Keep a bounded overlap from the previous chunk without
                # manufacturing empty chunks on oversized first segments.
                overlap_source = current_chunk.strip()
                current_chunk = overlap_source[-self.overlap:] if overlap_source else ""
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += part
            else:
                current_chunk += "\n" + part

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks






class SmartJsonChunker(JsonTextChunker):
    def __init__(self, model: str = "gpt-4o", target_tokens: int = 3500, overlap: int = 200):
        super().__init__(chunk_size=target_tokens, overlap=overlap)
        self.enc = tiktoken.encoding_for_model(model)
        self.target_tokens = target_tokens

    def chunk(self, text: str):
        # Step 1: use normal JsonTextChunker logic
        small_chunks = super().chunk(text)
        merged_chunks = []
        current = ""

        # Step 2: merge small chunks until token target is reached
        for ch in small_chunks:
            tokens = len(self.enc.encode(current + ch))
            if tokens < self.target_tokens:
                current += ch + "\n"
            else:
                merged_chunks.append(current.strip())
                current = ch

        if current.strip():
            merged_chunks.append(current.strip())

        return merged_chunks
