"""
Ingestion Service - Process and store all types of content.

Handles:
- Text/thoughts
- Documents (PDF, Word, Markdown)
- Voice memos (transcription)
- Web clips
- Structured data
"""

import re
from datetime import datetime
from typing import Optional, BinaryIO
from pathlib import Path

from nexus.config import config
from nexus.models.entry import Entry, EntryCreate, EntryType, EntrySource
from nexus.storage import get_vector_store, get_metadata_store, get_embedding_provider


class IngestionService:
    """
    Service for ingesting content into Nexus.

    Usage:
        service = IngestionService()
        entry = await service.ingest_text("My thought here", tags=["idea"])
        entry = await service.ingest_document(file_path)
        entry = await service.ingest_voice(audio_file)
    """

    def __init__(self):
        self.vector_store = get_vector_store()
        self.metadata_store = get_metadata_store()
        self.embedding_provider = get_embedding_provider()

    async def ingest(self, create: EntryCreate) -> Entry:
        """
        Ingest a new entry.

        This is the main entry point for all ingestion.
        It handles: storage, embedding, and indexing.
        """
        # 1. Store in metadata DB
        entry = await self.metadata_store.create_entry(create)

        # 2. Generate embedding
        embedding = await self.embedding_provider.embed(
            self._prepare_for_embedding(entry)
        )

        # 3. Store embedding in vector DB
        metadata = {
            "type": entry.type.value,
            "tags": ",".join(entry.tags),
            "created_at": entry.created_at.isoformat(),
            "collection_id": entry.collection_id or "",
        }
        await self.vector_store.add(entry.id, embedding, metadata)

        return entry

    async def ingest_text(
        self,
        content: str,
        title: Optional[str] = None,
        tags: list[str] = None,
        entry_type: EntryType = EntryType.THOUGHT,
        source: EntrySource = EntrySource.MANUAL,
        event_date: datetime = None,
        collection_id: str = None,
        custom_fields: dict = None,
    ) -> Entry:
        """Ingest plain text content."""
        # Auto-generate title if not provided
        if not title and len(content) > 50:
            title = content[:50] + "..."

        # Auto-extract tags if none provided
        if not tags:
            tags = self._auto_extract_tags(content)

        create = EntryCreate(
            type=entry_type,
            title=title,
            content=content,
            tags=tags or [],
            source=source,
            event_date=event_date,
            collection_id=collection_id,
            custom_fields=custom_fields or {},
        )

        return await self.ingest(create)

    async def ingest_document(
        self,
        file_path: str | Path,
        tags: list[str] = None,
        collection_id: str = None,
    ) -> list[Entry]:
        """
        Ingest a document file (PDF, Word, Markdown, etc.)

        Returns list of entries (documents may be split into chunks).
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect file type and parse
        suffix = file_path.suffix.lower()
        content = ""

        if suffix == ".pdf":
            content = await self._parse_pdf(file_path)
        elif suffix in (".doc", ".docx"):
            content = await self._parse_word(file_path)
        elif suffix in (".md", ".markdown"):
            content = file_path.read_text(encoding="utf-8")
        elif suffix == ".txt":
            content = file_path.read_text(encoding="utf-8")
        elif suffix in (".html", ".htm"):
            content = await self._parse_html(file_path)
        else:
            # Try as plain text
            content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Split into chunks if too long
        chunks = self._split_into_chunks(content, max_tokens=1000)

        entries = []
        for i, chunk in enumerate(chunks):
            title = file_path.stem
            if len(chunks) > 1:
                title = f"{title} (part {i + 1}/{len(chunks)})"

            entry = await self.ingest_text(
                content=chunk,
                title=title,
                tags=tags or [],
                entry_type=EntryType.DOCUMENT,
                source=EntrySource.DOCUMENT,
                collection_id=collection_id,
                custom_fields={
                    "source_file": str(file_path),
                    "file_type": suffix,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )
            entries.append(entry)

        return entries

    async def ingest_voice(
        self,
        audio_file: str | Path | BinaryIO,
        tags: list[str] = None,
        collection_id: str = None,
    ) -> Entry:
        """
        Ingest a voice memo by transcribing it.

        CUSTOMIZATION POINT:
        - Uses OpenAI Whisper locally (free, private)
        - Can switch to AssemblyAI for cloud transcription
        """
        # Transcribe audio
        transcript = await self._transcribe_audio(audio_file)

        return await self.ingest_text(
            content=transcript,
            tags=tags or ["voice"],
            entry_type=EntryType.THOUGHT,
            source=EntrySource.VOICE,
            collection_id=collection_id,
            custom_fields={
                "original_audio": str(audio_file) if isinstance(audio_file, (str, Path)) else "uploaded"
            }
        )

    async def ingest_web_clip(
        self,
        url: str,
        content: str = None,
        title: str = None,
        tags: list[str] = None,
    ) -> Entry:
        """Ingest a web page clip."""
        # If no content provided, fetch the page
        if not content:
            content, title = await self._fetch_web_page(url)

        return await self.ingest_text(
            content=content,
            title=title,
            tags=tags or ["bookmark"],
            entry_type=EntryType.BOOKMARK,
            source=EntrySource.WEB_CLIP,
            custom_fields={"source_url": url}
        )

    async def ingest_batch(self, items: list[EntryCreate]) -> list[Entry]:
        """Ingest multiple entries at once."""
        entries = []
        for item in items:
            entry = await self.ingest(item)
            entries.append(entry)
        return entries

    # ==========================================================================
    # PARSING HELPERS
    # ==========================================================================

    async def _parse_pdf(self, file_path: Path) -> str:
        """Parse PDF file."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}")

    async def _parse_word(self, file_path: Path) -> str:
        """Parse Word document."""
        try:
            from docx import Document
            doc = Document(str(file_path))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to parse Word document: {e}")

    async def _parse_html(self, file_path: Path) -> str:
        """Parse HTML file."""
        try:
            from bs4 import BeautifulSoup
            html = file_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            # Remove scripts and styles
            for tag in soup(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            raise ValueError(f"Failed to parse HTML: {e}")

    async def _transcribe_audio(self, audio_file) -> str:
        """Transcribe audio using Whisper."""
        try:
            import whisper
            model = whisper.load_model("base")

            if isinstance(audio_file, (str, Path)):
                result = model.transcribe(str(audio_file))
            else:
                # Save to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_file.read())
                    temp_path = f.name
                result = model.transcribe(temp_path)
                Path(temp_path).unlink()

            return result["text"]
        except Exception as e:
            raise ValueError(f"Failed to transcribe audio: {e}")

    async def _fetch_web_page(self, url: str) -> tuple[str, str]:
        """Fetch and parse a web page."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True)
                html = response.text

            soup = BeautifulSoup(html, "html.parser")

            # Get title
            title = soup.title.string if soup.title else url

            # Get main content
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()

            content = soup.get_text(separator="\n", strip=True)

            return content, title
        except Exception as e:
            raise ValueError(f"Failed to fetch web page: {e}")

    # ==========================================================================
    # UTILITY HELPERS
    # ==========================================================================

    def _prepare_for_embedding(self, entry: Entry) -> str:
        """Prepare entry content for embedding."""
        parts = []
        if entry.title:
            parts.append(entry.title)
        parts.append(entry.content)
        if entry.tags:
            parts.append(f"Tags: {', '.join(entry.tags)}")
        return "\n".join(parts)

    def _auto_extract_tags(self, content: str) -> list[str]:
        """Auto-extract potential tags from content."""
        # Look for hashtags
        hashtags = re.findall(r"#(\w+)", content)

        # Look for @mentions
        mentions = re.findall(r"@(\w+)", content)

        # Common categories to detect
        categories = {
            "work": ["meeting", "project", "deadline", "client", "email"],
            "personal": ["family", "friend", "birthday", "vacation"],
            "health": ["workout", "exercise", "diet", "sleep", "doctor"],
            "learning": ["book", "course", "tutorial", "learned"],
            "idea": ["idea", "thought", "maybe", "consider"],
            "todo": ["todo", "need to", "should", "must", "reminder"],
        }

        content_lower = content.lower()
        detected_tags = []
        for tag, keywords in categories.items():
            if any(kw in content_lower for kw in keywords):
                detected_tags.append(tag)

        return list(set(hashtags + mentions + detected_tags))[:10]

    def _split_into_chunks(
        self,
        content: str,
        max_tokens: int = 1000,
        overlap: int = 100
    ) -> list[str]:
        """Split long content into chunks for embedding."""
        # Rough estimate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        overlap_chars = overlap * 4

        if len(content) <= max_chars:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + max_chars

            # Try to break at paragraph or sentence
            if end < len(content):
                # Look for paragraph break
                para_break = content.rfind("\n\n", start, end)
                if para_break > start + max_chars // 2:
                    end = para_break

                # Or sentence break
                else:
                    sent_break = content.rfind(". ", start, end)
                    if sent_break > start + max_chars // 2:
                        end = sent_break + 1

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap_chars

        return chunks
