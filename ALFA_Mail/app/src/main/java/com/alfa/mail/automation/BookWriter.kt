package com.alfa.mail.automation

import android.content.Context
import android.graphics.*
import android.graphics.pdf.PdfDocument
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.*
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.math.min

/**
 * 📚 ALFA BOOK WRITER v2.0
 * 
 * Kompletny system pisania książek z AI:
 * ✅ Generowanie całej książki jednym tchem
 * ✅ Eksport do PDF, EPUB, DOCX, TXT
 * ✅ Narracja audiobook (TTS + ElevenLabs)
 * ✅ Automatyczne rozdziały
 * ✅ Formatowanie i stylizacja
 * ✅ Okładka generowana AI
 * ✅ Spis treści
 * ✅ Metadane książki
 */
class BookWriter private constructor(private val context: Context) {
    
    companion object {
        @Volatile
        private var INSTANCE: BookWriter? = null
        
        fun getInstance(context: Context): BookWriter {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: BookWriter(context.applicationContext).also { INSTANCE = it }
            }
        }
        
        // API endpoints
        private const val OPENAI_API = "https://api.openai.com/v1"
        private const val ANTHROPIC_API = "https://api.anthropic.com/v1"
        private const val GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
        private const val ELEVENLABS_API = "https://api.elevenlabs.io/v1"
    }
    
    private val prefs = context.getSharedPreferences("book_writer", Context.MODE_PRIVATE)
    private val outputDir = File(context.filesDir, "books").apply { mkdirs() }
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    
    init {
        initTTS()
    }
    
    // ============================================================
    // DATA CLASSES
    // ============================================================
    
    data class BookRequest(
        val title: String,
        val genre: BookGenre,
        val targetLength: BookLength = BookLength.MEDIUM,
        val style: WritingStyle = WritingStyle.DESCRIPTIVE,
        val language: String = "pl",
        val authorName: String = "ALFA AI",
        val description: String = "",
        val chapters: Int = 10,
        val generateCover: Boolean = true,
        val generateAudiobook: Boolean = false,
        val aiModel: AIModel = AIModel.GPT4,
        val customPrompt: String? = null
    )
    
    enum class BookGenre(val displayName: String, val prompt: String) {
        FICTION("Fikcja literacka", "literary fiction with deep characters and meaningful themes"),
        FANTASY("Fantasy", "epic fantasy with magic, mythical creatures, and heroic quests"),
        SCI_FI("Science Fiction", "science fiction exploring technology, space, and future societies"),
        THRILLER("Thriller", "suspenseful thriller with twists, tension, and high stakes"),
        ROMANCE("Romans", "romantic story with emotional depth and compelling relationships"),
        HORROR("Horror", "horror with psychological tension, supernatural elements, and fear"),
        MYSTERY("Kryminał", "mystery with clues, investigation, and surprising revelations"),
        BIOGRAPHY("Biografia", "biographical narrative with real events and personal insights"),
        SELF_HELP("Poradnik", "self-help guide with practical advice and actionable steps"),
        BUSINESS("Biznes", "business book with strategies, case studies, and insights"),
        HISTORY("Historia", "historical narrative with accurate facts and engaging storytelling"),
        CHILDREN("Dla dzieci", "children's story with adventure, lessons, and imagination"),
        POETRY("Poezja", "poetry collection with various styles and emotional depth"),
        COOKBOOK("Kulinaria", "cookbook with recipes, techniques, and culinary stories")
    }
    
    enum class BookLength(val wordCount: Int, val chapters: Int) {
        SHORT(15000, 5),        // Novella ~50 stron
        MEDIUM(40000, 12),      // Standard ~150 stron
        LONG(80000, 20),        // Long novel ~300 stron
        EPIC(120000, 30)        // Epic ~450 stron
    }
    
    enum class WritingStyle(val description: String) {
        MINIMALIST("concise, direct prose with minimal description"),
        DESCRIPTIVE("rich, detailed descriptions and vivid imagery"),
        LITERARY("sophisticated language with metaphors and symbolism"),
        CONVERSATIONAL("friendly, easy-to-read casual tone"),
        DRAMATIC("intense, emotional with dramatic tension"),
        HUMOROUS("witty, funny with comedic elements"),
        POETIC("lyrical, rhythmic with poetic language"),
        ACADEMIC("formal, well-researched with citations")
    }
    
    enum class AIModel(val id: String, val maxTokens: Int) {
        GPT4("gpt-4-turbo-preview", 128000),
        GPT4O("gpt-4o", 128000),
        CLAUDE("claude-3-opus-20240229", 200000),
        CLAUDE_SONNET("claude-3-5-sonnet-20241022", 200000),
        GEMINI("gemini-1.5-pro", 1000000)
    }
    
    data class Book(
        val id: String = UUID.randomUUID().toString(),
        val title: String,
        val author: String,
        val genre: BookGenre,
        val language: String,
        val description: String,
        val chapters: List<Chapter>,
        val wordCount: Int,
        val createdAt: Long = System.currentTimeMillis(),
        val coverPath: String? = null,
        val metadata: BookMetadata
    )
    
    data class Chapter(
        val number: Int,
        val title: String,
        val content: String,
        val wordCount: Int,
        val summary: String = ""
    )
    
    data class BookMetadata(
        val isbn: String = generateISBN(),
        val publisher: String = "ALFA Publishing",
        val publishDate: String = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date()),
        val copyright: String = "© ${Calendar.getInstance().get(Calendar.YEAR)} ALFA Foundation",
        val keywords: List<String> = emptyList(),
        val dedication: String = "",
        val acknowledgments: String = ""
    ) {
        companion object {
            fun generateISBN(): String {
                val random = Random()
                return "978-${random.nextInt(9)}-${(10000..99999).random()}-${(100..999).random()}-${random.nextInt(10)}"
            }
        }
    }
    
    data class GenerationProgress(
        val stage: String,
        val chapter: Int,
        val totalChapters: Int,
        val progress: Float,
        val message: String,
        val wordCount: Int = 0
    )
    
    data class ExportResult(
        val success: Boolean,
        val filePath: String? = null,
        val format: ExportFormat? = null,
        val fileSize: Long = 0,
        val error: String? = null
    )
    
    enum class ExportFormat(val extension: String, val mimeType: String) {
        PDF("pdf", "application/pdf"),
        EPUB("epub", "application/epub+zip"),
        DOCX("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        TXT("txt", "text/plain"),
        HTML("html", "text/html"),
        MARKDOWN("md", "text/markdown")
    }
    
    data class AudiobookResult(
        val success: Boolean,
        val audioFiles: List<String> = emptyList(),
        val totalDuration: Long = 0,
        val error: String? = null
    )
    
    // ============================================================
    // BOOK GENERATION - JEDNYM TCHEM!
    // ============================================================
    
    /**
     * 📚 Generuje całą książkę jednym tchem
     */
    suspend fun writeBook(
        request: BookRequest,
        onProgress: (GenerationProgress) -> Unit = {}
    ): Book = withContext(Dispatchers.IO) {
        
        onProgress(GenerationProgress("init", 0, request.chapters, 0.02f, "📚 Rozpoczynam pisanie książki...", 0))
        
        // 1. Generuj outline (zarys książki)
        onProgress(GenerationProgress("outline", 0, request.chapters, 0.05f, "📋 Tworzę zarys fabuły...", 0))
        val outline = generateBookOutline(request)
        
        // 2. Generuj rozdziały
        val chapters = mutableListOf<Chapter>()
        var totalWords = 0
        
        for (i in 1..request.chapters) {
            onProgress(GenerationProgress(
                "writing", i, request.chapters, 
                0.1f + (0.7f * i / request.chapters),
                "✍️ Piszę rozdział $i/${request.chapters}: ${outline.chapterTitles.getOrElse(i-1) { "Rozdział $i" }}",
                totalWords
            ))
            
            val chapter = generateChapter(
                request = request,
                chapterNumber = i,
                chapterTitle = outline.chapterTitles.getOrElse(i-1) { "Rozdział $i" },
                chapterOutline = outline.chapterOutlines.getOrElse(i-1) { "" },
                previousChapters = chapters,
                targetWords = request.targetLength.wordCount / request.chapters
            )
            
            chapters.add(chapter)
            totalWords += chapter.wordCount
        }
        
        // 3. Generuj okładkę
        var coverPath: String? = null
        if (request.generateCover) {
            onProgress(GenerationProgress("cover", request.chapters, request.chapters, 0.85f, "🎨 Generuję okładkę...", totalWords))
            coverPath = generateCover(request)
        }
        
        // 4. Finalizacja
        onProgress(GenerationProgress("finalizing", request.chapters, request.chapters, 0.95f, "📖 Finalizuję książkę...", totalWords))
        
        val book = Book(
            title = request.title,
            author = request.authorName,
            genre = request.genre,
            language = request.language,
            description = request.description.ifEmpty { outline.synopsis },
            chapters = chapters,
            wordCount = totalWords,
            coverPath = coverPath,
            metadata = BookMetadata(
                keywords = outline.keywords,
                dedication = "Dla wszystkich, którzy wierzą w moc słowa."
            )
        )
        
        // Zapisz książkę
        saveBook(book)
        
        onProgress(GenerationProgress("complete", request.chapters, request.chapters, 1.0f, "✅ Książka gotowa! $totalWords słów", totalWords))
        
        book
    }
    
    /**
     * Generuje zarys książki
     */
    private suspend fun generateBookOutline(request: BookRequest): BookOutline = withContext(Dispatchers.IO) {
        val prompt = """
            Stwórz szczegółowy zarys książki:
            
            Tytuł: ${request.title}
            Gatunek: ${request.genre.displayName}
            Styl: ${request.style.description}
            Liczba rozdziałów: ${request.chapters}
            Język: ${if (request.language == "pl") "Polski" else request.language}
            ${request.customPrompt?.let { "Dodatkowe wytyczne: $it" } ?: ""}
            
            Wygeneruj:
            1. Krótkie streszczenie (synopsis) - 2-3 zdania
            2. Lista tytułów ${request.chapters} rozdziałów
            3. Krótki opis każdego rozdziału (1-2 zdania)
            4. 5 słów kluczowych
            5. Główni bohaterowie (jeśli fikcja)
            
            Odpowiedz w formacie JSON:
            {
                "synopsis": "...",
                "chapterTitles": ["Rozdział 1: ...", "Rozdział 2: ...", ...],
                "chapterOutlines": ["Opis rozdziału 1...", "Opis rozdziału 2...", ...],
                "keywords": ["słowo1", "słowo2", ...],
                "characters": ["Postać 1", "Postać 2", ...]
            }
        """.trimIndent()
        
        val response = callAI(request.aiModel, prompt, 4000)
        
        try {
            val json = JSONObject(response)
            BookOutline(
                synopsis = json.getString("synopsis"),
                chapterTitles = json.getJSONArray("chapterTitles").let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                },
                chapterOutlines = json.getJSONArray("chapterOutlines").let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                },
                keywords = json.getJSONArray("keywords").let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                },
                characters = json.optJSONArray("characters")?.let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                } ?: emptyList()
            )
        } catch (e: Exception) {
            // Fallback
            BookOutline(
                synopsis = "Fascynująca opowieść pełna przygód i emocji.",
                chapterTitles = (1..request.chapters).map { "Rozdział $it" },
                chapterOutlines = (1..request.chapters).map { "Kontynuacja głównej fabuły..." },
                keywords = listOf(request.genre.displayName),
                characters = emptyList()
            )
        }
    }
    
    private data class BookOutline(
        val synopsis: String,
        val chapterTitles: List<String>,
        val chapterOutlines: List<String>,
        val keywords: List<String>,
        val characters: List<String>
    )
    
    /**
     * Generuje pojedynczy rozdział
     */
    private suspend fun generateChapter(
        request: BookRequest,
        chapterNumber: Int,
        chapterTitle: String,
        chapterOutline: String,
        previousChapters: List<Chapter>,
        targetWords: Int
    ): Chapter = withContext(Dispatchers.IO) {
        
        // Kontekst z poprzednich rozdziałów (ostatnie 2)
        val context = previousChapters.takeLast(2).joinToString("\n\n") { chapter ->
            "=== ${chapter.title} ===\n${chapter.summary}"
        }
        
        val prompt = """
            Napisz pełny rozdział książki.
            
            KSIĄŻKA: ${request.title}
            GATUNEK: ${request.genre.displayName}
            STYL: ${request.style.description}
            JĘZYK: ${if (request.language == "pl") "Polski" else request.language}
            
            ROZDZIAŁ $chapterNumber: $chapterTitle
            ZARYS: $chapterOutline
            
            ${if (context.isNotBlank()) "POPRZEDNIE ROZDZIAŁY (streszczenie):\n$context\n" else ""}
            
            WYMAGANIA:
            - Napisz pełny, kompletny rozdział
            - Długość: około $targetWords słów
            - Zachowaj spójność z poprzednimi rozdziałami
            - Używaj dialogów, opisów, narracji
            - Zakończ rozdział w sposób zachęcający do czytania dalej
            ${request.customPrompt?.let { "- $it" } ?: ""}
            
            Pisz TYLKO treść rozdziału, bez nagłówków czy metadanych.
            Pisz płynnie, literacko, angażująco.
        """.trimIndent()
        
        val content = callAI(request.aiModel, prompt, targetWords * 2)
        
        // Wygeneruj streszczenie rozdziału
        val summaryPrompt = "Napisz 2-3 zdania streszczenia tego rozdziału:\n\n${content.take(2000)}..."
        val summary = callAI(request.aiModel, summaryPrompt, 200)
        
        Chapter(
            number = chapterNumber,
            title = chapterTitle,
            content = content,
            wordCount = content.split("\\s+".toRegex()).size,
            summary = summary
        )
    }
    
    /**
     * Generuje okładkę książki
     */
    private suspend fun generateCover(request: BookRequest): String? = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("openai_api_key", null) ?: return@withContext null
        
        try {
            val prompt = """
                Book cover design for "${request.title}".
                Genre: ${request.genre.displayName}.
                Style: Professional, modern book cover, high quality.
                ${request.genre.prompt}
                No text on the cover, just the artwork.
                Dramatic lighting, compelling imagery.
            """.trimIndent()
            
            val url = URL("$OPENAI_API/images/generations")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $apiKey")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            
            val body = JSONObject().apply {
                put("model", "dall-e-3")
                put("prompt", prompt)
                put("n", 1)
                put("size", "1024x1792") // Book cover ratio
                put("quality", "hd")
            }
            
            conn.outputStream.write(body.toString().toByteArray())
            
            if (conn.responseCode == 200) {
                val response = conn.inputStream.bufferedReader().readText()
                val imageUrl = JSONObject(response)
                    .getJSONArray("data")
                    .getJSONObject(0)
                    .getString("url")
                
                // Download cover
                val coverFile = File(outputDir, "cover_${System.currentTimeMillis()}.png")
                URL(imageUrl).openStream().use { input ->
                    FileOutputStream(coverFile).use { output ->
                        input.copyTo(output)
                    }
                }
                
                coverFile.absolutePath
            } else null
            
        } catch (e: Exception) {
            null
        }
    }
    
    // ============================================================
    // EKSPORT - PDF, EPUB, DOCX, TXT
    // ============================================================
    
    /**
     * 📄 Eksportuje książkę do PDF
     */
    suspend fun exportToPDF(book: Book): ExportResult = withContext(Dispatchers.IO) {
        try {
            val pdfFile = File(outputDir, "${sanitizeFilename(book.title)}.pdf")
            val document = PdfDocument()
            
            val pageWidth = 595 // A4 width in points
            val pageHeight = 842 // A4 height in points
            val margin = 72f // 1 inch margins
            val lineHeight = 16f
            val fontSize = 12f
            val titleFontSize = 24f
            val chapterTitleSize = 18f
            
            val textPaint = Paint().apply {
                color = Color.BLACK
                textSize = fontSize
                isAntiAlias = true
                typeface = Typeface.create(Typeface.SERIF, Typeface.NORMAL)
            }
            
            val titlePaint = Paint().apply {
                color = Color.BLACK
                textSize = titleFontSize
                isAntiAlias = true
                typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
            }
            
            val chapterPaint = Paint().apply {
                color = Color.BLACK
                textSize = chapterTitleSize
                isAntiAlias = true
                typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
            }
            
            var pageNumber = 1
            var currentPage: PdfDocument.Page? = null
            var canvas: Canvas? = null
            var yPosition = margin
            
            fun newPage(): Canvas {
                currentPage?.let { document.finishPage(it) }
                val pageInfo = PdfDocument.PageInfo.Builder(pageWidth, pageHeight, pageNumber++).create()
                currentPage = document.startPage(pageInfo)
                yPosition = margin
                return currentPage!!.canvas
            }
            
            fun drawText(text: String, paint: Paint, centered: Boolean = false) {
                val textWidth = pageWidth - 2 * margin
                val words = text.split(" ")
                var line = ""
                
                for (word in words) {
                    val testLine = if (line.isEmpty()) word else "$line $word"
                    val testWidth = paint.measureText(testLine)
                    
                    if (testWidth > textWidth) {
                        if (yPosition > pageHeight - margin) {
                            canvas = newPage()
                        }
                        val x = if (centered) (pageWidth - paint.measureText(line)) / 2 else margin
                        canvas?.drawText(line, x, yPosition, paint)
                        yPosition += lineHeight * (paint.textSize / fontSize)
                        line = word
                    } else {
                        line = testLine
                    }
                }
                
                if (line.isNotEmpty()) {
                    if (yPosition > pageHeight - margin) {
                        canvas = newPage()
                    }
                    val x = if (centered) (pageWidth - paint.measureText(line)) / 2 else margin
                    canvas?.drawText(line, x, yPosition, paint)
                    yPosition += lineHeight * (paint.textSize / fontSize)
                }
            }
            
            // Title page
            canvas = newPage()
            yPosition = pageHeight / 3f
            drawText(book.title, titlePaint, centered = true)
            yPosition += 50f
            textPaint.textSize = 14f
            drawText("Autor: ${book.author}", textPaint, centered = true)
            yPosition += 30f
            drawText(book.metadata.publisher, textPaint, centered = true)
            yPosition += 20f
            drawText(book.metadata.publishDate, textPaint, centered = true)
            
            // Copyright page
            canvas = newPage()
            textPaint.textSize = 10f
            drawText(book.metadata.copyright, textPaint)
            yPosition += 20f
            drawText("ISBN: ${book.metadata.isbn}", textPaint)
            
            // Table of contents
            canvas = newPage()
            drawText("Spis Treści", chapterPaint, centered = true)
            yPosition += 30f
            textPaint.textSize = 12f
            book.chapters.forEach { chapter ->
                drawText("${chapter.number}. ${chapter.title}", textPaint)
                yPosition += 5f
            }
            
            // Chapters
            textPaint.textSize = fontSize
            book.chapters.forEach { chapter ->
                canvas = newPage()
                yPosition = margin + 50f
                drawText(chapter.title, chapterPaint, centered = true)
                yPosition += 40f
                
                // Split content into paragraphs
                chapter.content.split("\n\n").forEach { paragraph ->
                    if (paragraph.isNotBlank()) {
                        drawText(paragraph.trim(), textPaint)
                        yPosition += lineHeight
                    }
                }
            }
            
            currentPage?.let { document.finishPage(it) }
            
            FileOutputStream(pdfFile).use { output ->
                document.writeTo(output)
            }
            document.close()
            
            ExportResult(
                success = true,
                filePath = pdfFile.absolutePath,
                format = ExportFormat.PDF,
                fileSize = pdfFile.length()
            )
            
        } catch (e: Exception) {
            ExportResult(false, error = e.message)
        }
    }
    
    /**
     * 📱 Eksportuje książkę do EPUB
     */
    suspend fun exportToEPUB(book: Book): ExportResult = withContext(Dispatchers.IO) {
        try {
            val epubFile = File(outputDir, "${sanitizeFilename(book.title)}.epub")
            
            ZipOutputStream(FileOutputStream(epubFile)).use { zip ->
                // mimetype (must be first, uncompressed)
                zip.putNextEntry(ZipEntry("mimetype"))
                zip.write("application/epub+zip".toByteArray())
                zip.closeEntry()
                
                // META-INF/container.xml
                zip.putNextEntry(ZipEntry("META-INF/container.xml"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                        <rootfiles>
                            <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
                        </rootfiles>
                    </container>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // OEBPS/content.opf
                val manifest = StringBuilder()
                val spine = StringBuilder()
                
                manifest.append("""<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>""")
                manifest.append("""<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>""")
                spine.append("""<itemref idref="toc"/>""")
                
                book.chapters.forEachIndexed { index, _ ->
                    manifest.append("""<item id="chapter${index + 1}" href="chapter${index + 1}.xhtml" media-type="application/xhtml+xml"/>""")
                    spine.append("""<itemref idref="chapter${index + 1}"/>""")
                }
                
                zip.putNextEntry(ZipEntry("OEBPS/content.opf"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
                        <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                            <dc:identifier id="uid">${book.metadata.isbn}</dc:identifier>
                            <dc:title>${escapeXml(book.title)}</dc:title>
                            <dc:creator>${escapeXml(book.author)}</dc:creator>
                            <dc:language>${book.language}</dc:language>
                            <dc:publisher>${escapeXml(book.metadata.publisher)}</dc:publisher>
                            <dc:date>${book.metadata.publishDate}</dc:date>
                            <meta property="dcterms:modified">${SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).format(Date())}</meta>
                        </metadata>
                        <manifest>
                            $manifest
                        </manifest>
                        <spine>
                            $spine
                        </spine>
                    </package>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // Navigation document
                zip.putNextEntry(ZipEntry("OEBPS/nav.xhtml"))
                val navItems = book.chapters.mapIndexed { index, chapter ->
                    """<li><a href="chapter${index + 1}.xhtml">${escapeXml(chapter.title)}</a></li>"""
                }.joinToString("\n")
                
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <!DOCTYPE html>
                    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
                    <head><title>Navigation</title></head>
                    <body>
                        <nav epub:type="toc" id="toc">
                            <h1>Spis Treści</h1>
                            <ol>$navItems</ol>
                        </nav>
                    </body>
                    </html>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // Table of contents
                zip.putNextEntry(ZipEntry("OEBPS/toc.xhtml"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <!DOCTYPE html>
                    <html xmlns="http://www.w3.org/1999/xhtml">
                    <head>
                        <title>${escapeXml(book.title)}</title>
                        <style>
                            body { font-family: Georgia, serif; margin: 2em; }
                            h1 { text-align: center; }
                            .author { text-align: center; font-style: italic; }
                        </style>
                    </head>
                    <body>
                        <h1>${escapeXml(book.title)}</h1>
                        <p class="author">${escapeXml(book.author)}</p>
                        <hr/>
                        <h2>Spis Treści</h2>
                        <ol>$navItems</ol>
                    </body>
                    </html>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // Chapters
                book.chapters.forEachIndexed { index, chapter ->
                    zip.putNextEntry(ZipEntry("OEBPS/chapter${index + 1}.xhtml"))
                    
                    val paragraphs = chapter.content.split("\n\n")
                        .filter { it.isNotBlank() }
                        .joinToString("\n") { "<p>${escapeXml(it.trim())}</p>" }
                    
                    zip.write("""
                        <?xml version="1.0" encoding="UTF-8"?>
                        <!DOCTYPE html>
                        <html xmlns="http://www.w3.org/1999/xhtml">
                        <head>
                            <title>${escapeXml(chapter.title)}</title>
                            <style>
                                body { font-family: Georgia, serif; margin: 2em; line-height: 1.6; }
                                h1 { text-align: center; margin-bottom: 2em; }
                                p { text-indent: 1.5em; margin: 0.5em 0; }
                            </style>
                        </head>
                        <body>
                            <h1>${escapeXml(chapter.title)}</h1>
                            $paragraphs
                        </body>
                        </html>
                    """.trimIndent().toByteArray())
                    zip.closeEntry()
                }
            }
            
            ExportResult(
                success = true,
                filePath = epubFile.absolutePath,
                format = ExportFormat.EPUB,
                fileSize = epubFile.length()
            )
            
        } catch (e: Exception) {
            ExportResult(false, error = e.message)
        }
    }
    
    /**
     * 📝 Eksportuje książkę do DOCX (Word)
     */
    suspend fun exportToDOCX(book: Book): ExportResult = withContext(Dispatchers.IO) {
        try {
            val docxFile = File(outputDir, "${sanitizeFilename(book.title)}.docx")
            
            ZipOutputStream(FileOutputStream(docxFile)).use { zip ->
                // [Content_Types].xml
                zip.putNextEntry(ZipEntry("[Content_Types].xml"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                        <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                        <Default Extension="xml" ContentType="application/xml"/>
                        <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
                    </Types>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // _rels/.rels
                zip.putNextEntry(ZipEntry("_rels/.rels"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                        <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
                    </Relationships>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // word/_rels/document.xml.rels
                zip.putNextEntry(ZipEntry("word/_rels/document.xml.rels"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                    </Relationships>
                """.trimIndent().toByteArray())
                zip.closeEntry()
                
                // word/document.xml
                val content = StringBuilder()
                
                // Title
                content.append("""
                    <w:p>
                        <w:pPr><w:jc w:val="center"/><w:pStyle w:val="Title"/></w:pPr>
                        <w:r><w:rPr><w:b/><w:sz w:val="56"/></w:rPr><w:t>${escapeXml(book.title)}</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr><w:jc w:val="center"/></w:pPr>
                        <w:r><w:rPr><w:i/><w:sz w:val="28"/></w:rPr><w:t>${escapeXml(book.author)}</w:t></w:r>
                    </w:p>
                    <w:p><w:r><w:br w:type="page"/></w:r></w:p>
                """.trimIndent())
                
                // Table of Contents
                content.append("""
                    <w:p>
                        <w:pPr><w:jc w:val="center"/></w:pPr>
                        <w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr><w:t>Spis Treści</w:t></w:r>
                    </w:p>
                """.trimIndent())
                
                book.chapters.forEach { chapter ->
                    content.append("""
                        <w:p>
                            <w:r><w:t>${chapter.number}. ${escapeXml(chapter.title)}</w:t></w:r>
                        </w:p>
                    """.trimIndent())
                }
                
                content.append("""<w:p><w:r><w:br w:type="page"/></w:r></w:p>""")
                
                // Chapters
                book.chapters.forEach { chapter ->
                    content.append("""
                        <w:p>
                            <w:pPr><w:jc w:val="center"/></w:pPr>
                            <w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>${escapeXml(chapter.title)}</w:t></w:r>
                        </w:p>
                        <w:p/>
                    """.trimIndent())
                    
                    chapter.content.split("\n\n").filter { it.isNotBlank() }.forEach { para ->
                        content.append("""
                            <w:p>
                                <w:pPr><w:ind w:firstLine="720"/></w:pPr>
                                <w:r><w:t>${escapeXml(para.trim())}</w:t></w:r>
                            </w:p>
                        """.trimIndent())
                    }
                    
                    content.append("""<w:p><w:r><w:br w:type="page"/></w:r></w:p>""")
                }
                
                zip.putNextEntry(ZipEntry("word/document.xml"))
                zip.write("""
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                        <w:body>
                            $content
                        </w:body>
                    </w:document>
                """.trimIndent().toByteArray())
                zip.closeEntry()
            }
            
            ExportResult(
                success = true,
                filePath = docxFile.absolutePath,
                format = ExportFormat.DOCX,
                fileSize = docxFile.length()
            )
            
        } catch (e: Exception) {
            ExportResult(false, error = e.message)
        }
    }
    
    /**
     * 📄 Eksportuje książkę do TXT
     */
    suspend fun exportToTXT(book: Book): ExportResult = withContext(Dispatchers.IO) {
        try {
            val txtFile = File(outputDir, "${sanitizeFilename(book.title)}.txt")
            
            txtFile.writeText(buildString {
                appendLine("=" .repeat(60))
                appendLine(book.title.uppercase())
                appendLine("=" .repeat(60))
                appendLine()
                appendLine("Autor: ${book.author}")
                appendLine("Gatunek: ${book.genre.displayName}")
                appendLine("ISBN: ${book.metadata.isbn}")
                appendLine("Data publikacji: ${book.metadata.publishDate}")
                appendLine()
                appendLine(book.metadata.copyright)
                appendLine()
                appendLine("-".repeat(60))
                appendLine("SPIS TREŚCI")
                appendLine("-".repeat(60))
                appendLine()
                
                book.chapters.forEach { chapter ->
                    appendLine("${chapter.number}. ${chapter.title}")
                }
                
                appendLine()
                appendLine("=".repeat(60))
                appendLine()
                
                book.chapters.forEach { chapter ->
                    appendLine()
                    appendLine("-".repeat(60))
                    appendLine(chapter.title.uppercase())
                    appendLine("-".repeat(60))
                    appendLine()
                    appendLine(chapter.content)
                    appendLine()
                }
                
                appendLine()
                appendLine("=".repeat(60))
                appendLine("KONIEC")
                appendLine("=".repeat(60))
            })
            
            ExportResult(
                success = true,
                filePath = txtFile.absolutePath,
                format = ExportFormat.TXT,
                fileSize = txtFile.length()
            )
            
        } catch (e: Exception) {
            ExportResult(false, error = e.message)
        }
    }
    
    // ============================================================
    // AUDIOBOOK - NARRACJA
    // ============================================================
    
    /**
     * 🎧 Generuje audiobook z narracji
     */
    suspend fun generateAudiobook(
        book: Book,
        voice: String = "onyx", // alloy, echo, fable, onyx, nova, shimmer
        useElevenLabs: Boolean = false,
        onProgress: (GenerationProgress) -> Unit = {}
    ): AudiobookResult = withContext(Dispatchers.IO) {
        
        val audioFiles = mutableListOf<String>()
        var totalDuration = 0L
        
        try {
            book.chapters.forEachIndexed { index, chapter ->
                onProgress(GenerationProgress(
                    "narrating",
                    index + 1,
                    book.chapters.size,
                    (index + 1f) / book.chapters.size,
                    "🎧 Narracja rozdziału ${index + 1}/${book.chapters.size}",
                    0
                ))
                
                val audioPath = if (useElevenLabs) {
                    narrateWithElevenLabs(chapter, voice)
                } else {
                    narrateWithOpenAI(chapter, voice)
                }
                
                audioPath?.let {
                    audioFiles.add(it)
                    totalDuration += getAudioDuration(it)
                }
            }
            
            onProgress(GenerationProgress(
                "complete",
                book.chapters.size,
                book.chapters.size,
                1f,
                "✅ Audiobook gotowy!",
                0
            ))
            
            AudiobookResult(
                success = true,
                audioFiles = audioFiles,
                totalDuration = totalDuration
            )
            
        } catch (e: Exception) {
            AudiobookResult(false, error = e.message)
        }
    }
    
    /**
     * Narracja przez OpenAI TTS
     */
    private suspend fun narrateWithOpenAI(chapter: Chapter, voice: String): String? = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("openai_api_key", null) ?: return@withContext null
        
        try {
            val url = URL("$OPENAI_API/audio/speech")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $apiKey")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            
            // Podziel na części jeśli za długie (max 4096 znaków)
            val textChunks = chapter.content.chunked(4000)
            val audioChunks = mutableListOf<ByteArray>()
            
            textChunks.forEach { chunk ->
                val body = JSONObject().apply {
                    put("model", "tts-1-hd")
                    put("input", chunk)
                    put("voice", voice)
                    put("response_format", "mp3")
                }
                
                val request = url.openConnection() as HttpURLConnection
                request.requestMethod = "POST"
                request.setRequestProperty("Authorization", "Bearer $apiKey")
                request.setRequestProperty("Content-Type", "application/json")
                request.doOutput = true
                request.outputStream.write(body.toString().toByteArray())
                
                if (request.responseCode == 200) {
                    audioChunks.add(request.inputStream.readBytes())
                }
            }
            
            // Połącz chunki
            if (audioChunks.isNotEmpty()) {
                val audioFile = File(outputDir, "audio_chapter${chapter.number}_${System.currentTimeMillis()}.mp3")
                FileOutputStream(audioFile).use { out ->
                    audioChunks.forEach { chunk ->
                        out.write(chunk)
                    }
                }
                audioFile.absolutePath
            } else null
            
        } catch (e: Exception) {
            null
        }
    }
    
    /**
     * Narracja przez ElevenLabs (lepszej jakości)
     */
    private suspend fun narrateWithElevenLabs(chapter: Chapter, voiceId: String): String? = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("elevenlabs_api_key", null) ?: return@withContext null
        
        try {
            val url = URL("$ELEVENLABS_API/text-to-speech/$voiceId")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("xi-api-key", apiKey)
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            
            val body = JSONObject().apply {
                put("text", chapter.content)
                put("model_id", "eleven_multilingual_v2")
                put("voice_settings", JSONObject().apply {
                    put("stability", 0.5)
                    put("similarity_boost", 0.8)
                })
            }
            
            conn.outputStream.write(body.toString().toByteArray())
            
            if (conn.responseCode == 200) {
                val audioFile = File(outputDir, "audio_chapter${chapter.number}_${System.currentTimeMillis()}.mp3")
                conn.inputStream.use { input ->
                    FileOutputStream(audioFile).use { output ->
                        input.copyTo(output)
                    }
                }
                audioFile.absolutePath
            } else null
            
        } catch (e: Exception) {
            null
        }
    }
    
    /**
     * Lokalna narracja przez Android TTS
     */
    suspend fun narrateWithLocalTTS(
        book: Book,
        onProgress: (GenerationProgress) -> Unit = {}
    ): AudiobookResult = withContext(Dispatchers.IO) {
        
        if (!ttsReady) {
            return@withContext AudiobookResult(false, error = "TTS nie jest gotowy")
        }
        
        // Użyj Android TTS (synchroniczne czekanie)
        val audioFiles = mutableListOf<String>()
        
        // To wymaga bardziej złożonej implementacji z syntezą do pliku
        // Uproszczona wersja:
        
        AudiobookResult(
            success = false,
            error = "Lokalna narracja TTS w implementacji. Użyj OpenAI lub ElevenLabs."
        )
    }
    
    // ============================================================
    // HELPER FUNCTIONS
    // ============================================================
    
    private suspend fun callAI(model: AIModel, prompt: String, maxTokens: Int): String = withContext(Dispatchers.IO) {
        when (model) {
            AIModel.GPT4, AIModel.GPT4O -> callOpenAI(model.id, prompt, maxTokens)
            AIModel.CLAUDE, AIModel.CLAUDE_SONNET -> callClaude(model.id, prompt, maxTokens)
            AIModel.GEMINI -> callGemini(prompt, maxTokens)
        }
    }
    
    private suspend fun callOpenAI(model: String, prompt: String, maxTokens: Int): String = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("openai_api_key", null) ?: return@withContext ""
        
        try {
            val url = URL("$OPENAI_API/chat/completions")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("Authorization", "Bearer $apiKey")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 120000
            conn.readTimeout = 120000
            
            val body = JSONObject().apply {
                put("model", model)
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", prompt)
                    })
                })
                put("max_tokens", min(maxTokens, 4096))
                put("temperature", 0.7)
            }
            
            conn.outputStream.write(body.toString().toByteArray())
            
            if (conn.responseCode == 200) {
                val response = conn.inputStream.bufferedReader().readText()
                JSONObject(response)
                    .getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .getString("content")
            } else ""
            
        } catch (e: Exception) {
            ""
        }
    }
    
    private suspend fun callClaude(model: String, prompt: String, maxTokens: Int): String = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("anthropic_api_key", null) ?: return@withContext ""
        
        try {
            val url = URL("$ANTHROPIC_API/messages")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("x-api-key", apiKey)
            conn.setRequestProperty("anthropic-version", "2023-06-01")
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 120000
            conn.readTimeout = 120000
            
            val body = JSONObject().apply {
                put("model", model)
                put("max_tokens", maxTokens)
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", prompt)
                    })
                })
            }
            
            conn.outputStream.write(body.toString().toByteArray())
            
            if (conn.responseCode == 200) {
                val response = conn.inputStream.bufferedReader().readText()
                JSONObject(response)
                    .getJSONArray("content")
                    .getJSONObject(0)
                    .getString("text")
            } else ""
            
        } catch (e: Exception) {
            ""
        }
    }
    
    private suspend fun callGemini(prompt: String, maxTokens: Int): String = withContext(Dispatchers.IO) {
        val apiKey = prefs.getString("gemini_api_key", null) ?: return@withContext ""
        
        try {
            val url = URL("$GEMINI_API/models/gemini-1.5-pro:generateContent?key=$apiKey")
            val conn = url.openConnection() as HttpURLConnection
            
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 120000
            conn.readTimeout = 120000
            
            val body = JSONObject().apply {
                put("contents", JSONArray().apply {
                    put(JSONObject().apply {
                        put("parts", JSONArray().apply {
                            put(JSONObject().apply {
                                put("text", prompt)
                            })
                        })
                    })
                })
                put("generationConfig", JSONObject().apply {
                    put("maxOutputTokens", maxTokens)
                    put("temperature", 0.7)
                })
            }
            
            conn.outputStream.write(body.toString().toByteArray())
            
            if (conn.responseCode == 200) {
                val response = conn.inputStream.bufferedReader().readText()
                JSONObject(response)
                    .getJSONArray("candidates")
                    .getJSONObject(0)
                    .getJSONObject("content")
                    .getJSONArray("parts")
                    .getJSONObject(0)
                    .getString("text")
            } else ""
            
        } catch (e: Exception) {
            ""
        }
    }
    
    private fun initTTS() {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale("pl", "PL")
                ttsReady = true
            }
        }
    }
    
    private fun saveBook(book: Book) {
        val json = JSONObject().apply {
            put("id", book.id)
            put("title", book.title)
            put("author", book.author)
            put("genre", book.genre.name)
            put("language", book.language)
            put("description", book.description)
            put("wordCount", book.wordCount)
            put("createdAt", book.createdAt)
            put("coverPath", book.coverPath)
            put("chapters", JSONArray().apply {
                book.chapters.forEach { chapter ->
                    put(JSONObject().apply {
                        put("number", chapter.number)
                        put("title", chapter.title)
                        put("content", chapter.content)
                        put("wordCount", chapter.wordCount)
                        put("summary", chapter.summary)
                    })
                }
            })
        }
        
        File(outputDir, "${book.id}.json").writeText(json.toString())
    }
    
    private fun sanitizeFilename(name: String): String {
        return name.replace(Regex("[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ\\s-]"), "")
            .replace("\\s+".toRegex(), "_")
            .take(50)
    }
    
    private fun escapeXml(text: String): String {
        return text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
    }
    
    private fun getAudioDuration(filePath: String): Long {
        return try {
            val player = MediaPlayer()
            player.setDataSource(filePath)
            player.prepare()
            val duration = player.duration.toLong()
            player.release()
            duration
        } catch (e: Exception) {
            0L
        }
    }
    
    fun setApiKey(provider: String, apiKey: String) {
        val key = when (provider.lowercase()) {
            "openai", "gpt" -> "openai_api_key"
            "anthropic", "claude" -> "anthropic_api_key"
            "google", "gemini" -> "gemini_api_key"
            "elevenlabs" -> "elevenlabs_api_key"
            else -> provider
        }
        prefs.edit().putString(key, apiKey).apply()
    }
    
    fun getBooks(): List<Book> {
        return outputDir.listFiles { _, name -> name.endsWith(".json") }
            ?.mapNotNull { file ->
                try {
                    val json = JSONObject(file.readText())
                    Book(
                        id = json.getString("id"),
                        title = json.getString("title"),
                        author = json.getString("author"),
                        genre = BookGenre.valueOf(json.getString("genre")),
                        language = json.getString("language"),
                        description = json.getString("description"),
                        wordCount = json.getInt("wordCount"),
                        createdAt = json.getLong("createdAt"),
                        coverPath = json.optString("coverPath").takeIf { it.isNotBlank() },
                        chapters = json.getJSONArray("chapters").let { arr ->
                            (0 until arr.length()).map { i ->
                                val chJson = arr.getJSONObject(i)
                                Chapter(
                                    number = chJson.getInt("number"),
                                    title = chJson.getString("title"),
                                    content = chJson.getString("content"),
                                    wordCount = chJson.getInt("wordCount"),
                                    summary = chJson.optString("summary", "")
                                )
                            }
                        },
                        metadata = BookMetadata()
                    )
                } catch (e: Exception) {
                    null
                }
            }
            ?.sortedByDescending { it.createdAt }
            ?: emptyList()
    }
}
