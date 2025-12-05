"""
ALFA_MIRROR PRO — GALLERY UI
Czarno-złoty interfejs galerii z pełnym wsparciem media.
Poziom: WOLF-KING READY
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger("ALFA.Mirror.Gallery")


# ═══════════════════════════════════════════════════════════════════════════
# STYLE — WOLF-KING THEME
# ═══════════════════════════════════════════════════════════════════════════

GALLERY_CSS = """
:root {
    --bg-primary: #0a0a0a;
    --bg-secondary: #141414;
    --bg-tertiary: #1a1a1a;
    --gold: #FFD700;
    --gold-dim: #c9a227;
    --gold-glow: rgba(255, 215, 0, 0.3);
    --text-primary: #f0f0f0;
    --text-secondary: #888;
    --border: #333;
    --success: #4CAF50;
    --error: #f44336;
    --font: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: var(--font);
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* HEADER */
/* ═══════════════════════════════════════════════════════════════════════ */

.header {
    background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
    border-bottom: 3px solid var(--gold);
    padding: 30px 40px;
    text-align: center;
    position: sticky;
    top: 0;
    z-index: 100;
}

.header h1 {
    font-size: 2.8em;
    font-weight: 700;
    color: var(--gold);
    text-shadow: 0 0 20px var(--gold-glow);
    letter-spacing: 2px;
}

.header h1 .wolf {
    font-size: 1.2em;
}

.header .subtitle {
    color: var(--text-secondary);
    margin-top: 8px;
    font-size: 1.1em;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* NAV / STATS BAR */
/* ═══════════════════════════════════════════════════════════════════════ */

.stats-bar {
    display: flex;
    justify-content: center;
    gap: 30px;
    padding: 20px 40px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
}

.stat-item {
    background: var(--bg-tertiary);
    padding: 12px 24px;
    border-radius: 8px;
    border: 1px solid var(--border);
    text-align: center;
    min-width: 120px;
}

.stat-item .value {
    font-size: 1.8em;
    font-weight: 700;
    color: var(--gold);
}

.stat-item .label {
    font-size: 0.85em;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* SEARCH */
/* ═══════════════════════════════════════════════════════════════════════ */

.search-container {
    max-width: 700px;
    margin: 30px auto;
    padding: 0 20px;
}

.search-box {
    display: flex;
    background: var(--bg-tertiary);
    border: 2px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    transition: border-color 0.3s;
}

.search-box:focus-within {
    border-color: var(--gold);
    box-shadow: 0 0 15px var(--gold-glow);
}

.search-box input {
    flex: 1;
    padding: 16px 24px;
    font-size: 1.1em;
    background: transparent;
    border: none;
    color: var(--text-primary);
    outline: none;
}

.search-box input::placeholder {
    color: var(--text-secondary);
}

.search-box button {
    padding: 16px 28px;
    background: var(--gold);
    color: #000;
    border: none;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.3s;
}

.search-box button:hover {
    background: var(--gold-dim);
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* FILTER TAGS */
/* ═══════════════════════════════════════════════════════════════════════ */

.filter-bar {
    display: flex;
    justify-content: center;
    gap: 10px;
    padding: 20px;
    flex-wrap: wrap;
}

.filter-tag {
    padding: 8px 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 0.9em;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
}

.filter-tag:hover {
    border-color: var(--gold);
    color: var(--gold);
}

.filter-tag.active {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* GALLERY GRID */
/* ═══════════════════════════════════════════════════════════════════════ */

.gallery-container {
    padding: 30px 40px;
}

.gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 24px;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* SESSION CARD */
/* ═══════════════════════════════════════════════════════════════════════ */

.session-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.session-card:hover {
    transform: translateY(-8px);
    border-color: var(--gold);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5), 0 0 20px var(--gold-glow);
}

.card-preview {
    height: 200px;
    background: var(--bg-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
}

.card-preview img,
.card-preview video {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.card-preview .placeholder {
    font-size: 3em;
    color: var(--border);
}

.card-preview .media-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 4px 10px;
    background: rgba(0, 0, 0, 0.8);
    border: 1px solid var(--gold);
    border-radius: 4px;
    font-size: 0.75em;
    color: var(--gold);
}

.card-header {
    padding: 16px 20px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
}

.card-header h3 {
    font-size: 0.95em;
    color: var(--gold);
    word-break: break-all;
    font-family: monospace;
}

.card-header .date {
    font-size: 0.8em;
    color: var(--text-secondary);
    margin-top: 4px;
}

.card-body {
    padding: 16px 20px;
}

.card-stats {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.card-stat {
    font-size: 0.85em;
    color: var(--text-secondary);
}

.card-stat .icon {
    margin-right: 4px;
}

.card-stat.text { color: #4CAF50; }
.card-stat.image { color: #2196F3; }
.card-stat.video { color: #9C27B0; }
.card-stat.audio { color: #FF9800; }

.card-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 10px;
}

.card-tag {
    padding: 3px 10px;
    background: var(--bg-primary);
    border: 1px solid var(--gold-dim);
    border-radius: 12px;
    font-size: 0.75em;
    color: var(--gold-dim);
}

.card-summary {
    margin-top: 12px;
    padding: 12px;
    background: var(--bg-primary);
    border-radius: 8px;
    font-size: 0.85em;
    color: var(--text-secondary);
    max-height: 80px;
    overflow: hidden;
    position: relative;
}

.card-summary::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 30px;
    background: linear-gradient(transparent, var(--bg-primary));
}

.card-actions {
    padding: 12px 20px;
    background: var(--bg-tertiary);
    display: flex;
    gap: 10px;
    border-top: 1px solid var(--border);
}

.btn {
    flex: 1;
    padding: 10px 16px;
    background: var(--bg-primary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.85em;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    transition: all 0.2s;
}

.btn:hover {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
}

.btn.primary {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
}

.btn.primary:hover {
    background: var(--gold-dim);
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* MEDIA EMBEDS */
/* ═══════════════════════════════════════════════════════════════════════ */

.audio-embed {
    background: var(--bg-primary);
    padding: 12px 16px;
    border-radius: 8px;
    margin: 8px 0;
}

.audio-embed audio {
    width: 100%;
    height: 40px;
}

.audio-meta {
    font-size: 0.75em;
    color: var(--gold-dim);
    margin-top: 6px;
}

.video-container {
    position: relative;
}

.video-container .duration {
    position: absolute;
    bottom: 8px;
    right: 8px;
    padding: 4px 8px;
    background: rgba(0, 0, 0, 0.9);
    color: #fff;
    font-size: 0.8em;
    border-radius: 4px;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* PAGINATION */
/* ═══════════════════════════════════════════════════════════════════════ */

.pagination {
    display: flex;
    justify-content: center;
    gap: 10px;
    padding: 40px 20px;
}

.pagination a,
.pagination span {
    padding: 12px 20px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--text-primary);
    text-decoration: none;
    border-radius: 8px;
    transition: all 0.2s;
}

.pagination a:hover {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
}

.pagination .current {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* FOOTER */
/* ═══════════════════════════════════════════════════════════════════════ */

.footer {
    text-align: center;
    padding: 30px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 0.9em;
}

.footer .brand {
    color: var(--gold);
    font-weight: 600;
}

/* ═══════════════════════════════════════════════════════════════════════ */
/* RESPONSIVE */
/* ═══════════════════════════════════════════════════════════════════════ */

@media (max-width: 768px) {
    .header h1 {
        font-size: 2em;
    }
    
    .stats-bar {
        gap: 15px;
    }
    
    .gallery-grid {
        grid-template-columns: 1fr;
    }
    
    .gallery-container {
        padding: 20px;
    }
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# HTML GENERATORS
# ═══════════════════════════════════════════════════════════════════════════

def generate_session_card(
    session: dict,
    base_url: str = "/archive"
) -> str:
    """Generuje HTML karty sesji."""
    
    session_id = session.get("session_id", "unknown")
    
    # Parsuj datę z session_id
    date_str = "Unknown date"
    try:
        date_part = session_id.split("_")[0]
        if len(date_part) == 8:
            dt = datetime.strptime(date_part, "%Y%m%d")
            date_str = dt.strftime("%d %b %Y, %H:%M")
    except:
        pass
    
    # Preview image
    preview_html = '<div class="placeholder">📄</div>'
    media_badge = ""
    
    files = session.get("files", [])
    
    # Szukaj thumbnail lub pierwszego obrazu
    for f in files:
        if "_thumb.jpg" in f:
            preview_html = f'<img src="{base_url}/{session_id}/{f}" alt="Video thumbnail" loading="lazy">'
            media_badge = '<span class="media-badge">🎬 VIDEO</span>'
            break
        if f.startswith("image_"):
            preview_html = f'<img src="{base_url}/{session_id}/{f}" alt="Image" loading="lazy">'
            media_badge = '<span class="media-badge">🖼️ IMAGE</span>'
            break
    
    # Stats
    text_count = session.get("text_count", 0)
    image_count = session.get("image_count", 0)
    video_count = session.get("video_count", 0)
    audio_count = session.get("audio_count", 0)
    
    stats_html = ""
    if text_count:
        stats_html += f'<span class="card-stat text"><span class="icon">📝</span>{text_count} text</span>'
    if image_count:
        stats_html += f'<span class="card-stat image"><span class="icon">🖼️</span>{image_count} images</span>'
    if video_count:
        stats_html += f'<span class="card-stat video"><span class="icon">🎬</span>{video_count} videos</span>'
    if audio_count:
        stats_html += f'<span class="card-stat audio"><span class="icon">🎵</span>{audio_count} audio</span>'
    
    # Tags
    tags = session.get("tags", [])
    tags_html = ""
    if tags:
        tags_html = '<div class="card-tags">'
        for tag in tags[:5]:
            tags_html += f'<span class="card-tag">{tag}</span>'
        tags_html += '</div>'
    
    # Summary
    summary_html = ""
    if session.get("has_summary"):
        summary_html = '''
        <div class="card-summary">
            <em>AI Summary available</em>
        </div>
        '''
    
    return f'''
    <div class="session-card">
        <div class="card-preview">
            {preview_html}
            {media_badge}
        </div>
        <div class="card-header">
            <h3>{session_id}</h3>
            <div class="date">{date_str}</div>
        </div>
        <div class="card-body">
            <div class="card-stats">{stats_html}</div>
            {tags_html}
            {summary_html}
        </div>
        <div class="card-actions">
            <a href="{base_url}/{session_id}/" class="btn" target="_blank">📂 Browse</a>
            <a href="/api/v1/mirror/export/{session_id}" class="btn">📦 ZIP</a>
        </div>
    </div>
    '''


def generate_gallery_page(
    sessions: List[dict],
    stats: dict,
    page: int = 1,
    total_pages: int = 1,
    search_query: str = "",
    active_tag: str = "",
    tags: List[str] = None
) -> str:
    """Generuje pełną stronę galerii."""
    
    if tags is None:
        tags = []
    
    # Stats bar
    stats_html = f'''
    <div class="stats-bar">
        <div class="stat-item">
            <div class="value">{stats.get('total_sessions', 0)}</div>
            <div class="label">Sessions</div>
        </div>
        <div class="stat-item">
            <div class="value">{stats.get('total_files', 0)}</div>
            <div class="label">Files</div>
        </div>
        <div class="stat-item">
            <div class="value">{stats.get('total_size_mb', 0)} MB</div>
            <div class="label">Total Size</div>
        </div>
        <div class="stat-item">
            <div class="value">{stats.get('sessions_with_media', 0)}</div>
            <div class="label">With Media</div>
        </div>
    </div>
    '''
    
    # Filter tags
    filter_html = ""
    if tags:
        filter_html = '<div class="filter-bar">'
        for tag in tags[:15]:
            active = 'active' if tag == active_tag else ''
            filter_html += f'<span class="filter-tag {active}" onclick="filterByTag(\'{tag}\')">{tag}</span>'
        filter_html += '</div>'
    
    # Gallery grid
    cards_html = ""
    for session in sessions:
        cards_html += generate_session_card(session)
    
    if not sessions:
        cards_html = '''
        <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">
            <div style="font-size: 4em; margin-bottom: 20px;">🐺</div>
            <h3 style="color: var(--gold); margin-bottom: 10px;">No sessions found</h3>
            <p>The archive is empty or no results match your search.</p>
        </div>
        '''
    
    # Pagination
    pagination_html = '<div class="pagination">'
    
    if page > 1:
        pagination_html += f'<a href="?page={page-1}&q={search_query}">← Previous</a>'
    
    pagination_html += f'<span class="current">Page {page} of {total_pages}</span>'
    
    if page < total_pages:
        pagination_html += f'<a href="?page={page+1}&q={search_query}">Next →</a>'
    
    pagination_html += '</div>'
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALFA MIRROR — Gallery</title>
    <style>{GALLERY_CSS}</style>
</head>
<body>
    <header class="header">
        <h1><span class="wolf">🐺</span> ALFA MIRROR</h1>
        <p class="subtitle">Complete Archive of Gemini Conversations</p>
    </header>
    
    {stats_html}
    
    <div class="search-container">
        <form class="search-box" action="/api/v1/gallery" method="get">
            <input 
                type="text" 
                name="q" 
                placeholder="Search sessions, content, tags..." 
                value="{search_query}"
            >
            <button type="submit">🔍 Search</button>
        </form>
    </div>
    
    {filter_html}
    
    <main class="gallery-container">
        <div class="gallery-grid">
            {cards_html}
        </div>
    </main>
    
    {pagination_html}
    
    <footer class="footer">
        <span class="brand">ALFA MIRROR PRO</span> — Part of ALFA_CORE_KERNEL v3.0
    </footer>
    
    <script>
        function filterByTag(tag) {{
            window.location.href = '/api/v1/gallery?tag=' + encodeURIComponent(tag);
        }}
    </script>
</body>
</html>
    '''


def generate_session_detail_page(session: dict, content: dict) -> str:
    """Generuje stronę szczegółów sesji."""
    
    session_id = session.get("session_id", "unknown")
    
    # Media sections
    text_html = ""
    images_html = ""
    videos_html = ""
    audio_html = ""
    
    for text in content.get("texts", []):
        text_html += f'''
        <div class="text-block">
            <pre>{text[:2000]}{"..." if len(text) > 2000 else ""}</pre>
        </div>
        '''
    
    for img in content.get("images", []):
        images_html += f'''
        <div class="media-item">
            <img src="/archive/{session_id}/{img}" loading="lazy">
        </div>
        '''
    
    for vid in content.get("videos", []):
        thumb = vid.replace("video_", "video_").replace(".", "_thumb.")
        videos_html += f'''
        <div class="video-container">
            <video controls poster="/archive/{session_id}/{thumb}">
                <source src="/archive/{session_id}/{vid}">
            </video>
        </div>
        '''
    
    for aud in content.get("audio", []):
        videos_html += f'''
        <div class="audio-embed">
            <audio controls>
                <source src="/archive/{session_id}/{aud}">
            </audio>
            <div class="audio-meta">{aud}</div>
        </div>
        '''
    
    # Summary
    summary_html = ""
    if content.get("summary"):
        summary_html = f'''
        <section>
            <h2>📝 AI Summary</h2>
            <div class="summary-box">{content['summary']}</div>
        </section>
        '''
    
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Session: {session_id}</title>
    <style>{GALLERY_CSS}</style>
</head>
<body>
    <header class="header">
        <h1>🐺 Session Details</h1>
        <p class="subtitle">{session_id}</p>
    </header>
    
    <main class="gallery-container" style="max-width: 1000px; margin: 0 auto;">
        {summary_html}
        
        {"<section><h2>📝 Text Content</h2>" + text_html + "</section>" if text_html else ""}
        {"<section><h2>🖼️ Images</h2><div class='gallery-grid'>" + images_html + "</div></section>" if images_html else ""}
        {"<section><h2>🎬 Videos</h2>" + videos_html + "</section>" if videos_html else ""}
        {"<section><h2>🎵 Audio</h2>" + audio_html + "</section>" if audio_html else ""}
        
        <div style="margin-top: 40px; text-align: center;">
            <a href="/api/v1/gallery" class="btn primary">← Back to Gallery</a>
            <a href="/api/v1/mirror/export/{session_id}" class="btn">📦 Download ZIP</a>
        </div>
    </main>
    
    <footer class="footer">
        <span class="brand">ALFA MIRROR PRO</span>
    </footer>
</body>
</html>
    '''


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT CSS FOR EXTERNAL USE
# ═══════════════════════════════════════════════════════════════════════════

def get_gallery_css() -> str:
    """Zwraca CSS galerii."""
    return GALLERY_CSS


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test generation
    test_sessions = [
        {
            "session_id": "20251204_143022_abc123",
            "files": ["text_0.md", "image_0.png"],
            "text_count": 2,
            "image_count": 1,
            "video_count": 0,
            "audio_count": 0,
            "has_summary": True,
            "tags": ["python", "alfa", "test"]
        }
    ]
    
    test_stats = {
        "total_sessions": 42,
        "total_files": 256,
        "total_size_mb": 1024.5,
        "sessions_with_media": 30
    }
    
    html = generate_gallery_page(
        sessions=test_sessions,
        stats=test_stats,
        page=1,
        total_pages=5,
        tags=["python", "alfa", "gemini", "vision"]
    )
    
    # Zapisz do pliku testowego
    Path("test_gallery.html").write_text(html, encoding="utf8")
    print("✅ Test gallery saved to test_gallery.html")
