
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ProcessPoolExecutor

import aiohttp
import pandas as pd
import pymupdf4llm


start = time.time()

CSV_URL = (
    "https://raw.githubusercontent.com/alexeygrigorev/ai-engineering-buildcamp-code/"
    "main/01-foundation/homework/books.csv"
)

PDF_DIR = Path("pdfs")
MD_DIR = Path("books_text")

# Tune these
DOWNLOAD_CONCURRENCY = 12  # I/O bound: can be higher
CONVERT_CONCURRENCY = 3   # CPU bound: keep modest (2–4 is typical)


@dataclass(frozen=True)
class Book:
    url: str
    pdf_path: Path
    md_path: Path


def url_to_filename(url: str) -> str:
    """Return a filename based on the URL path."""
    name = Path(urlparse(url).path).name
    return name or "download.pdf"


def iter_pdf_urls(df: pd.DataFrame) -> list[str]:
    """
    Extract PDF URLs from a DataFrame.
    Prefers 'pdf_url', falls back to 'url'.
    """
    if "pdf_url" in df.columns:
        col = "pdf_url"
    elif "url" in df.columns:
        col = "url"
    else:
        raise ValueError(f"No PDF URL column found. Columns: {df.columns.tolist()}")

    urls: list[str] = []
    for v in df[col].dropna().tolist():
        if isinstance(v, str) and ".pdf" in v.lower():
            urls.append(v.strip())
    return urls


async def fetch_bytes(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_s: int = 120,
    retries: int = 3,
) -> bytes:
    """Fetch a URL as bytes with retries."""
    for attempt in range(1, retries + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.read()
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1.5 ** attempt)
            else:
                raise RuntimeError(f"Failed to fetch {url!r} after {retries} tries") from e

    raise RuntimeError("Unreachable")


async def download_one_pdf(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    book: Book,
) -> Book:
    """Download a single PDF if it doesn't exist."""
    async with sem:
        out_path = book.pdf_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"Skip PDF (exists): {out_path.name}")
            return book

        print(f"Download PDF: {out_path.name}")
        data = await fetch_bytes(session, book.url)

        tmp = out_path.with_suffix(out_path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(out_path)

        return book


def convert_pdf_to_md_process(pdf_path_str: str, md_path_str: str) -> str:
    """
    Run in a separate process. Imports inside to avoid cross-process issues.
    """

    pdf_path = Path(pdf_path_str)
    md_path = Path(md_path_str)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    md_text = pymupdf4llm.to_markdown(str(pdf_path))
    md_path.write_text(md_text, encoding="utf-8")
    return str(md_path)


async def convert_many_process(
    books: list[Book],
    *,
    max_workers: int,
    force_md: bool = False,
) -> None:
    """Convert many PDFs to Markdown using a process pool (safer for pymupdf4llm)."""
    loop = asyncio.get_running_loop()

    jobs: list[tuple[str, str]] = []
    for book in books:
        if book.md_path.exists() and not force_md:
            print(f"Skip MD (exists): {book.md_path.name}")
            continue
        jobs.append((str(book.pdf_path), str(book.md_path)))

    if not jobs:
        print("No PDFs to convert.")
        return

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        tasks = [
            loop.run_in_executor(ex, convert_pdf_to_md_process, pdf_s, md_s)
            for (pdf_s, md_s) in jobs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    ok = 0
    fail = 0
    for r in results:
        if isinstance(r, Exception):
            fail += 1
            print(f"CONVERT ERROR: {r!r}")
        else:
            ok += 1

    print(f"Conversion done. ok={ok} failed={fail}")


async def run_etl_async(*, force_md: bool = False) -> None:
    """Run the ETL: download PDFs then convert them to Markdown."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading books.csv...")
    df = pd.read_csv(CSV_URL)
    print("Columns:", df.columns.tolist())

    pdf_urls = iter_pdf_urls(df)
    print(f"Found {len(pdf_urls)} PDF URLs")

    books: list[Book] = []
    for url in pdf_urls:
        filename = url_to_filename(url)
        pdf_path = PDF_DIR / filename
        md_path = MD_DIR / f"{pdf_path.stem}.md"
        books.append(Book(url=url, pdf_path=pdf_path, md_path=md_path))

    # --- Stage 1: Download concurrently (I/O bound) ---
    download_sem = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
    async with aiohttp.ClientSession(headers={"User-Agent": "etl-books/1.0"}) as session:
        download_tasks = [download_one_pdf(session, download_sem, book) for book in books]
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

    ok_download: list[Book] = []
    failed_download = 0
    for r in download_results:
        if isinstance(r, Exception):
            failed_download += 1
            print(f"DOWNLOAD ERROR: {r!r}")
        else:
            ok_download.append(r)

    print(f"Downloads done. ok={len(ok_download)} failed={failed_download}")

    # --- Stage 2: Convert using processes (CPU bound / safer) ---
    await convert_many_process(
        ok_download,
        max_workers=CONVERT_CONCURRENCY,
        force_md=force_md,
    )

    print(f"Markdown output: {MD_DIR.resolve()}")


def main() -> None:
    asyncio.run(run_etl_async(force_md=False))
    print(f"ETL process complete. It took {time.time() - start:.2f} seconds.")


if __name__ == "__main__":
    main()
