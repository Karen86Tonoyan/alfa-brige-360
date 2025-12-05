AIzaSyCogUkcjP8nJAg41CukA1YIc5mDsnOPkKM
# Quick chunking
chunks = chunk_text(text, model="gemini-2.0-flash")

# Hierarchical summarization (multi-pass)
result = hierarchical_summarize(text, summarize_fn)

# Stream large files (1GB+)
for chunk in stream_file_chunks(Path("huge_file.txt")):
    process(chunk)