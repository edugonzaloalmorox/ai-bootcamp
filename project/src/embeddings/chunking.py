from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class ChunkingConfig:
    """
    Configuration for the chunking strategy based on logical segments
    (paragraphs, clauses) and approximate character limits.

    Attributes
    ----------
    max_chars : int
        Maximum desired length of each chunk in characters. The final chunk
        may exceed this slightly depending on segment boundaries.
    min_chars : int
        Minimum acceptable length of a chunk. If the final chunk is shorter
        than this threshold, it may be merged with the previous chunk.
    overlap_segments : int
        Number of segments from the end of each chunk to reuse as overlap
        in the following chunk. Usually 1–2 is sufficient.
    """

    max_chars: int = 1500
    min_chars: int = 400
    overlap_segments: int = 1


# Matches headings like "CLÁUSULA X", "CLAUSULA X", "ARTÍCULO", "ARTICULO"
_HEADING_REGEX = re.compile(
    r"""
    ^\s*(
        CL[AÁ]USULA
        |
        ART[ÍI]CULO
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_whitespace(text: str) -> str:
    """
    Normalize text by collapsing whitespace and cleaning redundant blank lines.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    str
        Normalized text with simplified spacing.
    """
    text = text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_segments(page_text: str) -> List[str]:
    """
    Split a page of text into logical segments (paragraphs, clauses).

    Rules
    -----
    - A blank line ends the current segment.
    - A line that matches a clause/article heading starts a new segment.
      (e.g., “CLÁUSULA …”, “ARTÍCULO …”)

    Parameters
    ----------
    page_text : str
        Raw page text.

    Returns
    -------
    List[str]
        A list of logical text segments extracted from the page.
    """
    page_text = normalize_whitespace(page_text)
    if not page_text:
        return []

    lines = page_text.splitlines()
    segments: List[str] = []
    current_lines: List[str] = []

    def flush_segment() -> None:
        """Append the current accumulated segment, if non-empty."""
        if current_lines:
            segment = "\n".join(current_lines).strip()
            if segment:
                segments.append(segment)

    for raw_line in lines:
        line = raw_line.rstrip()

        # Blank line → close current segment
        if not line.strip():
            flush_segment()
            current_lines = []
            continue

        # Clause/article heading → start a new segment
        if _HEADING_REGEX.match(line) and current_lines:
            flush_segment()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final segment
    flush_segment()

    return segments


def build_chunks_from_segments(
    segments: List[str],
    config: Optional[ChunkingConfig] = None
) -> List[str]:
    """
    Build final text chunks from a list of pre-split logical segments.

    Strategy
    --------
    - Accumulate segments until adding another one would exceed `max_chars`.
    - When exceeding, close current chunk and start a new one.
    - Carry over `overlap_segments` from the previous chunk as overlap.
    - If the last chunk is too small (< `min_chars`), merge it with the previous one.

    Parameters
    ----------
    segments : List[str]
        List of logical text segments.
    config : ChunkingConfig, optional
        Chunking parameters. If None, defaults are used.

    Returns
    -------
    List[str]
        The final list of chunked text blocks.
    """
    if config is None:
        config = ChunkingConfig()

    if not segments:
        return []

    chunks: List[str] = []
    current_segments: List[str] = []

    def current_length_with(segment: Optional[str] = None) -> int:
        """Return the length if `segment` were added to the buffer."""
        if segment is None:
            joined = "\n\n".join(current_segments)
        else:
            joined = "\n\n".join(current_segments + [segment])
        return len(joined)

    for seg in segments:
        # If adding this segment would exceed max_chars, close the chunk
        if current_segments and current_length_with(seg) > config.max_chars:
            chunk_text = "\n\n".join(current_segments).strip()
            if chunk_text:
                chunks.append(chunk_text)

            # Prepare overlap
            if config.overlap_segments > 0:
                overlap = current_segments[-config.overlap_segments:]
            else:
                overlap = []

            # New buffer starts with overlap + new segment
            current_segments = overlap + [seg]
        else:
            current_segments.append(seg)

    # Final chunk
    if current_segments:
        chunk_text = "\n\n".join(current_segments).strip()
        if chunk_text:
            chunks.append(chunk_text)

    # Merge last chunk if it's too small
    if len(chunks) >= 2 and len(chunks[-1]) < config.min_chars:
        prev = chunks[-2]
        last = chunks[-1]
        chunks[-2] = prev + "\n\n" + last
        chunks.pop()

    return chunks


def chunk_page_text(
    page_text: str,
    config: Optional[ChunkingConfig] = None
) -> List[str]:
    """
    Apply the full chunking strategy to a single page of text.

    Steps
    -----
    1. Split the page into logical segments (paragraphs, clauses).
    2. Group those segments into bounded-sized chunks with overlap.

    Parameters
    ----------
    page_text : str
        Raw text of the page.
    config : ChunkingConfig, optional
        Chunking configuration.

    Returns
    -------
    List[str]
        List of text chunks for the page.
    """
    segments = split_into_segments(page_text)
    if not segments:
        return []
    return build_chunks_from_segments(segments, config=config)
