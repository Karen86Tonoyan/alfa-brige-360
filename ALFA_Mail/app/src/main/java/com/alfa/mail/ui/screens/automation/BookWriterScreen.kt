package com.alfa.mail.ui.screens.automation

import androidx.compose.animation.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.alfa.mail.automation.BookWriter
import com.alfa.mail.automation.BookWriter.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

/**
 * 📚 BOOK WRITER SCREEN
 * 
 * Kompletny UI do pisania książek z AI:
 * ✅ Tworzenie nowej książki
 * ✅ Wybór gatunku i stylu
 * ✅ Progress w czasie rzeczywistym
 * ✅ Eksport do PDF/EPUB/DOCX
 * ✅ Generowanie audiobooka
 * ✅ Biblioteka zapisanych książek
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookWriterScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val bookWriter = remember { BookWriter.getInstance(context) }
    
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("✍️ Pisz", "📚 Biblioteka", "⚙️ Ustawienia")
    
    // Nowa książka
    var title by remember { mutableStateOf("") }
    var selectedGenre by remember { mutableStateOf(BookGenre.FICTION) }
    var selectedLength by remember { mutableStateOf(BookLength.MEDIUM) }
    var selectedStyle by remember { mutableStateOf(WritingStyle.DESCRIPTIVE) }
    var selectedModel by remember { mutableStateOf(AIModel.GPT4) }
    var authorName by remember { mutableStateOf("ALFA AI") }
    var description by remember { mutableStateOf("") }
    var customPrompt by remember { mutableStateOf("") }
    var generateCover by remember { mutableStateOf(true) }
    var generateAudiobook by remember { mutableStateOf(false) }
    var chapterCount by remember { mutableIntStateOf(10) }
    
    // Stan
    var isGenerating by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf<GenerationProgress?>(null) }
    var currentBook by remember { mutableStateOf<Book?>(null) }
    var books by remember { mutableStateOf<List<Book>>(emptyList()) }
    var showExportDialog by remember { mutableStateOf(false) }
    var exportResult by remember { mutableStateOf<ExportResult?>(null) }
    var showPreview by remember { mutableStateOf(false) }
    var previewChapter by remember { mutableIntStateOf(0) }
    
    // Audiobook
    var isNarrating by remember { mutableStateOf(false) }
    var selectedVoice by remember { mutableStateOf("onyx") }
    var useElevenLabs by remember { mutableStateOf(false) }
    
    // API Keys
    var openAiKey by remember { mutableStateOf("") }
    var anthropicKey by remember { mutableStateOf("") }
    var geminiKey by remember { mutableStateOf("") }
    var elevenLabsKey by remember { mutableStateOf("") }
    
    LaunchedEffect(Unit) {
        books = bookWriter.getBooks()
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("📚", fontSize = 24.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text("Book Writer AI", fontWeight = FontWeight.Bold)
                            Text(
                                "Pisz całe książki jednym tchem",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, "Wróć")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Tabs
            TabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, tab ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = { Text(tab) }
                    )
                }
            }
            
            when (selectedTab) {
                0 -> {
                    // ===== WRITE TAB =====
                    if (showPreview && currentBook != null) {
                        // Preview książki
                        BookPreviewContent(
                            book = currentBook!!,
                            chapterIndex = previewChapter,
                            onChapterChange = { previewChapter = it },
                            onClose = { showPreview = false },
                            onExport = { showExportDialog = true }
                        )
                    } else if (isGenerating) {
                        // Progress generowania
                        GeneratingBookContent(
                            progress = progress,
                            onCancel = { isGenerating = false }
                        )
                    } else {
                        // Formularz nowej książki
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            // Header
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(
                                        containerColor = MaterialTheme.colorScheme.primaryContainer
                                    )
                                ) {
                                    Row(
                                        modifier = Modifier.padding(16.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(
                                            Icons.Default.AutoAwesome,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.size(48.dp)
                                        )
                                        Spacer(modifier = Modifier.width(16.dp))
                                        Column {
                                            Text(
                                                "Stwórz Książkę z AI",
                                                style = MaterialTheme.typography.titleLarge,
                                                fontWeight = FontWeight.Bold
                                            )
                                            Text(
                                                "Cała powieść wygenerowana jednym kliknięciem!",
                                                style = MaterialTheme.typography.bodyMedium
                                            )
                                        }
                                    }
                                }
                            }
                            
                            // Tytuł
                            item {
                                OutlinedTextField(
                                    value = title,
                                    onValueChange = { title = it },
                                    label = { Text("📖 Tytuł książki") },
                                    placeholder = { Text("np. Tajemnice Starego Zamku") },
                                    modifier = Modifier.fillMaxWidth(),
                                    singleLine = true
                                )
                            }
                            
                            // Autor
                            item {
                                OutlinedTextField(
                                    value = authorName,
                                    onValueChange = { authorName = it },
                                    label = { Text("✍️ Autor") },
                                    modifier = Modifier.fillMaxWidth(),
                                    singleLine = true
                                )
                            }
                            
                            // Opis
                            item {
                                OutlinedTextField(
                                    value = description,
                                    onValueChange = { description = it },
                                    label = { Text("📝 Opis/Streszczenie (opcjonalne)") },
                                    modifier = Modifier.fillMaxWidth(),
                                    minLines = 2,
                                    maxLines = 4
                                )
                            }
                            
                            // Gatunek
                            item {
                                Text(
                                    "📚 Gatunek",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                LazyRow(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    items(BookGenre.entries) { genre ->
                                        GenreChip(
                                            genre = genre,
                                            selected = genre == selectedGenre,
                                            onClick = { selectedGenre = genre }
                                        )
                                    }
                                }
                            }
                            
                            // Długość
                            item {
                                Text(
                                    "📏 Długość",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Row(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    BookLength.entries.forEach { length ->
                                        LengthChip(
                                            length = length,
                                            selected = length == selectedLength,
                                            onClick = { 
                                                selectedLength = length
                                                chapterCount = length.chapters
                                            },
                                            modifier = Modifier.weight(1f)
                                        )
                                    }
                                }
                            }
                            
                            // Liczba rozdziałów
                            item {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(
                                        "📑 Rozdziały: $chapterCount",
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                    Spacer(modifier = Modifier.width(16.dp))
                                    Slider(
                                        value = chapterCount.toFloat(),
                                        onValueChange = { chapterCount = it.toInt() },
                                        valueRange = 3f..40f,
                                        steps = 36,
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }
                            
                            // Styl pisania
                            item {
                                Text(
                                    "🖊️ Styl pisania",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                LazyRow(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    items(WritingStyle.entries) { style ->
                                        StyleChip(
                                            style = style,
                                            selected = style == selectedStyle,
                                            onClick = { selectedStyle = style }
                                        )
                                    }
                                }
                            }
                            
                            // Model AI
                            item {
                                Text(
                                    "🤖 Model AI",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                LazyRow(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    items(AIModel.entries) { model ->
                                        ModelChip(
                                            model = model,
                                            selected = model == selectedModel,
                                            onClick = { selectedModel = model }
                                        )
                                    }
                                }
                            }
                            
                            // Dodatkowe wytyczne
                            item {
                                OutlinedTextField(
                                    value = customPrompt,
                                    onValueChange = { customPrompt = it },
                                    label = { Text("💡 Dodatkowe wytyczne (opcjonalne)") },
                                    placeholder = { Text("np. Bohater ma być kobietą, akcja w Polsce...") },
                                    modifier = Modifier.fillMaxWidth(),
                                    minLines = 2,
                                    maxLines = 4
                                )
                            }
                            
                            // Opcje
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.padding(16.dp)) {
                                        Text(
                                            "⚙️ Opcje dodatkowe",
                                            style = MaterialTheme.typography.titleMedium,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Spacer(modifier = Modifier.height(8.dp))
                                        
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.Image, null)
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text("Generuj okładkę (DALL-E 3)")
                                            Spacer(modifier = Modifier.weight(1f))
                                            Switch(
                                                checked = generateCover,
                                                onCheckedChange = { generateCover = it }
                                            )
                                        }
                                        
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.Headphones, null)
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text("Generuj audiobook")
                                            Spacer(modifier = Modifier.weight(1f))
                                            Switch(
                                                checked = generateAudiobook,
                                                onCheckedChange = { generateAudiobook = it }
                                            )
                                        }
                                    }
                                }
                            }
                            
                            // Szacowany czas
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(
                                        containerColor = MaterialTheme.colorScheme.tertiaryContainer
                                    )
                                ) {
                                    Row(
                                        modifier = Modifier.padding(16.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(Icons.Default.Timer, null)
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Column {
                                            Text(
                                                "Szacowany czas: ${estimateTime(selectedLength, chapterCount)}",
                                                fontWeight = FontWeight.Bold
                                            )
                                            Text(
                                                "~${selectedLength.wordCount} słów • ${chapterCount} rozdziałów",
                                                fontSize = 12.sp
                                            )
                                        }
                                    }
                                }
                            }
                            
                            // Przycisk generuj
                            item {
                                Button(
                                    onClick = {
                                        if (title.isNotBlank()) {
                                            isGenerating = true
                                            scope.launch {
                                                try {
                                                    val request = BookRequest(
                                                        title = title,
                                                        genre = selectedGenre,
                                                        targetLength = selectedLength,
                                                        style = selectedStyle,
                                                        authorName = authorName,
                                                        description = description,
                                                        chapters = chapterCount,
                                                        generateCover = generateCover,
                                                        generateAudiobook = generateAudiobook,
                                                        aiModel = selectedModel,
                                                        customPrompt = customPrompt.takeIf { it.isNotBlank() }
                                                    )
                                                    
                                                    currentBook = bookWriter.writeBook(request) { prog ->
                                                        progress = prog
                                                    }
                                                    
                                                    books = bookWriter.getBooks()
                                                    isGenerating = false
                                                    showPreview = true
                                                    
                                                } catch (e: Exception) {
                                                    isGenerating = false
                                                }
                                            }
                                        }
                                    },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(60.dp),
                                    enabled = title.isNotBlank()
                                ) {
                                    Icon(Icons.Default.AutoAwesome, null)
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        "📚 NAPISZ KSIĄŻKĘ JEDNYM TCHEM!",
                                        fontSize = 16.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                            
                            item { Spacer(modifier = Modifier.height(32.dp)) }
                        }
                    }
                }
                
                1 -> {
                    // ===== LIBRARY TAB =====
                    if (books.isEmpty()) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("📚", fontSize = 64.sp)
                                Text("Brak książek")
                                Text(
                                    "Napisz swoją pierwszą książkę!",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(16.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            item {
                                Text(
                                    "📚 Twoja Biblioteka (${books.size})",
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            
                            items(books) { book ->
                                BookCard(
                                    book = book,
                                    onClick = {
                                        currentBook = book
                                        previewChapter = 0
                                        showPreview = true
                                        selectedTab = 0
                                    },
                                    onExport = {
                                        currentBook = book
                                        showExportDialog = true
                                    },
                                    onNarrate = {
                                        currentBook = book
                                        scope.launch {
                                            isNarrating = true
                                            bookWriter.generateAudiobook(book, selectedVoice, useElevenLabs) { prog ->
                                                progress = prog
                                            }
                                            isNarrating = false
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
                
                2 -> {
                    // ===== SETTINGS TAB =====
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        item {
                            Text(
                                "🔑 Klucze API",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        
                        item {
                            ApiKeyCard(
                                title = "OpenAI (GPT-4)",
                                icon = "🤖",
                                value = openAiKey,
                                onValueChange = { openAiKey = it },
                                onSave = { bookWriter.setApiKey("openai", openAiKey) }
                            )
                        }
                        
                        item {
                            ApiKeyCard(
                                title = "Anthropic (Claude)",
                                icon = "🧠",
                                value = anthropicKey,
                                onValueChange = { anthropicKey = it },
                                onSave = { bookWriter.setApiKey("anthropic", anthropicKey) }
                            )
                        }
                        
                        item {
                            ApiKeyCard(
                                title = "Google (Gemini)",
                                icon = "💎",
                                value = geminiKey,
                                onValueChange = { geminiKey = it },
                                onSave = { bookWriter.setApiKey("gemini", geminiKey) }
                            )
                        }
                        
                        item {
                            ApiKeyCard(
                                title = "ElevenLabs (Audio)",
                                icon = "🎙️",
                                value = elevenLabsKey,
                                onValueChange = { elevenLabsKey = it },
                                onSave = { bookWriter.setApiKey("elevenlabs", elevenLabsKey) }
                            )
                        }
                        
                        item {
                            Divider()
                        }
                        
                        item {
                            Text(
                                "🎧 Ustawienia Audiobooka",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        
                        item {
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Text("Głos narracji", fontWeight = FontWeight.Bold)
                                    Spacer(modifier = Modifier.height(8.dp))
                                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        val voices = listOf(
                                            "alloy" to "Alloy 🎵",
                                            "echo" to "Echo 🔊",
                                            "fable" to "Fable 📖",
                                            "onyx" to "Onyx 🌑",
                                            "nova" to "Nova ⭐",
                                            "shimmer" to "Shimmer ✨"
                                        )
                                        items(voices) { (id, name) ->
                                            FilterChip(
                                                selected = selectedVoice == id,
                                                onClick = { selectedVoice = id },
                                                label = { Text(name) }
                                            )
                                        }
                                    }
                                    
                                    Spacer(modifier = Modifier.height(16.dp))
                                    
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text("Użyj ElevenLabs (lepsza jakość)")
                                        Spacer(modifier = Modifier.weight(1f))
                                        Switch(
                                            checked = useElevenLabs,
                                            onCheckedChange = { useElevenLabs = it }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        // Export Dialog
        if (showExportDialog && currentBook != null) {
            ExportDialog(
                book = currentBook!!,
                onDismiss = { showExportDialog = false },
                onExport = { format ->
                    scope.launch {
                        val result = when (format) {
                            ExportFormat.PDF -> bookWriter.exportToPDF(currentBook!!)
                            ExportFormat.EPUB -> bookWriter.exportToEPUB(currentBook!!)
                            ExportFormat.DOCX -> bookWriter.exportToDOCX(currentBook!!)
                            ExportFormat.TXT -> bookWriter.exportToTXT(currentBook!!)
                            else -> bookWriter.exportToTXT(currentBook!!)
                        }
                        exportResult = result
                    }
                    showExportDialog = false
                }
            )
        }
        
        // Export Result
        exportResult?.let { result ->
            AlertDialog(
                onDismissRequest = { exportResult = null },
                icon = { 
                    Icon(
                        if (result.success) Icons.Default.Check else Icons.Default.Error,
                        null,
                        tint = if (result.success) Color.Green else Color.Red
                    )
                },
                title = { Text(if (result.success) "Eksport zakończony!" else "Błąd eksportu") },
                text = {
                    if (result.success) {
                        Column {
                            Text("📄 Format: ${result.format?.extension?.uppercase()}")
                            Text("📁 Rozmiar: ${formatFileSize(result.fileSize)}")
                            Text("📂 ${result.filePath}", fontSize = 10.sp)
                        }
                    } else {
                        Text(result.error ?: "Nieznany błąd")
                    }
                },
                confirmButton = {
                    TextButton(onClick = { exportResult = null }) {
                        Text("OK")
                    }
                }
            )
        }
    }
}

@Composable
private fun GeneratingBookContent(
    progress: GenerationProgress?,
    onCancel: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Animated book icon
        Text("📖", fontSize = 80.sp)
        
        Spacer(modifier = Modifier.height(24.dp))
        
        Text(
            "Piszę książkę...",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        progress?.let { prog ->
            Text(
                prog.message,
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            LinearProgressIndicator(
                progress = { prog.progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp))
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                "${(prog.progress * 100).toInt()}%",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            
            if (prog.chapter > 0) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Rozdział ${prog.chapter}/${prog.totalChapters}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            if (prog.wordCount > 0) {
                Text(
                    "${prog.wordCount} słów napisanych",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        
        Spacer(modifier = Modifier.height(32.dp))
        
        OutlinedButton(onClick = onCancel) {
            Icon(Icons.Default.Close, null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Anuluj")
        }
    }
}

@Composable
private fun BookPreviewContent(
    book: Book,
    chapterIndex: Int,
    onChapterChange: (Int) -> Unit,
    onClose: () -> Unit,
    onExport: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        // Header
        Surface(
            color = MaterialTheme.colorScheme.primaryContainer
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Cover
                if (book.coverPath != null) {
                    AsyncImage(
                        model = book.coverPath,
                        contentDescription = null,
                        modifier = Modifier
                            .size(80.dp)
                            .clip(RoundedCornerShape(8.dp)),
                        contentScale = ContentScale.Crop
                    )
                    Spacer(modifier = Modifier.width(16.dp))
                }
                
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        book.title,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        book.author,
                        style = MaterialTheme.typography.bodyMedium,
                        fontStyle = FontStyle.Italic
                    )
                    Text(
                        "${book.wordCount} słów • ${book.chapters.size} rozdziałów",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                
                IconButton(onClick = onExport) {
                    Icon(Icons.Default.FileDownload, "Eksport")
                }
                
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.Close, "Zamknij")
                }
            }
        }
        
        // Chapter navigation
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            itemsIndexed(book.chapters) { index, chapter ->
                FilterChip(
                    selected = index == chapterIndex,
                    onClick = { onChapterChange(index) },
                    label = { 
                        Text(
                            "${index + 1}",
                            maxLines = 1
                        )
                    }
                )
            }
        }
        
        // Chapter content
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            val chapter = book.chapters.getOrNull(chapterIndex)
            
            chapter?.let { ch ->
                item {
                    Text(
                        ch.title,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth()
                    )
                    
                    Spacer(modifier = Modifier.height(24.dp))
                    
                    Text(
                        ch.content,
                        style = MaterialTheme.typography.bodyLarge,
                        lineHeight = 28.sp
                    )
                    
                    Spacer(modifier = Modifier.height(32.dp))
                    
                    // Navigation buttons
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        if (chapterIndex > 0) {
                            OutlinedButton(
                                onClick = { onChapterChange(chapterIndex - 1) }
                            ) {
                                Icon(Icons.Default.ArrowBack, null)
                                Text(" Poprzedni")
                            }
                        } else {
                            Spacer(modifier = Modifier.width(1.dp))
                        }
                        
                        if (chapterIndex < book.chapters.size - 1) {
                            Button(
                                onClick = { onChapterChange(chapterIndex + 1) }
                            ) {
                                Text("Następny ")
                                Icon(Icons.Default.ArrowForward, null)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun BookCard(
    book: Book,
    onClick: () -> Unit,
    onExport: () -> Unit,
    onNarrate: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.Top
        ) {
            // Cover or placeholder
            Box(
                modifier = Modifier
                    .size(80.dp, 120.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                MaterialTheme.colorScheme.primary,
                                MaterialTheme.colorScheme.tertiary
                            )
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                if (book.coverPath != null) {
                    AsyncImage(
                        model = book.coverPath,
                        contentDescription = null,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                } else {
                    Text(
                        book.title.take(1).uppercase(),
                        style = MaterialTheme.typography.headlineLarge,
                        color = Color.White
                    )
                }
            }
            
            Spacer(modifier = Modifier.width(16.dp))
            
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    book.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                
                Text(
                    book.author,
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic
                )
                
                Spacer(modifier = Modifier.height(4.dp))
                
                Row {
                    AssistChip(
                        onClick = {},
                        label = { Text(book.genre.displayName, fontSize = 10.sp) },
                        modifier = Modifier.height(24.dp)
                    )
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Text(
                    "${book.wordCount} słów • ${book.chapters.size} rozdziałów",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                
                Text(
                    SimpleDateFormat("dd.MM.yyyy", Locale.getDefault()).format(Date(book.createdAt)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IconButton(
                        onClick = onExport,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.FileDownload, "Eksport", modifier = Modifier.size(20.dp))
                    }
                    
                    IconButton(
                        onClick = onNarrate,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.Headphones, "Audiobook", modifier = Modifier.size(20.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun GenreChip(
    genre: BookGenre,
    selected: Boolean,
    onClick: () -> Unit
) {
    val icon = when (genre) {
        BookGenre.FICTION -> "📖"
        BookGenre.FANTASY -> "🧙"
        BookGenre.SCI_FI -> "🚀"
        BookGenre.THRILLER -> "🔪"
        BookGenre.ROMANCE -> "💕"
        BookGenre.HORROR -> "👻"
        BookGenre.MYSTERY -> "🔍"
        BookGenre.BIOGRAPHY -> "👤"
        BookGenre.SELF_HELP -> "💪"
        BookGenre.BUSINESS -> "💼"
        BookGenre.HISTORY -> "🏛️"
        BookGenre.CHILDREN -> "🧸"
        BookGenre.POETRY -> "🎭"
        BookGenre.COOKBOOK -> "🍳"
    }
    
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text("$icon ${genre.displayName}") }
    )
}

@Composable
private fun LengthChip(
    length: BookLength,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val (label, desc) = when (length) {
        BookLength.SHORT -> "Krótka" to "~50 stron"
        BookLength.MEDIUM -> "Średnia" to "~150 stron"
        BookLength.LONG -> "Długa" to "~300 stron"
        BookLength.EPIC -> "Epik" to "~450 stron"
    }
    
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { 
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(label, fontWeight = FontWeight.Bold)
                Text(desc, fontSize = 10.sp)
            }
        },
        modifier = modifier
    )
}

@Composable
private fun StyleChip(
    style: WritingStyle,
    selected: Boolean,
    onClick: () -> Unit
) {
    val label = when (style) {
        WritingStyle.MINIMALIST -> "Minimalistyczny"
        WritingStyle.DESCRIPTIVE -> "Opisowy"
        WritingStyle.LITERARY -> "Literacki"
        WritingStyle.CONVERSATIONAL -> "Konwersacyjny"
        WritingStyle.DRAMATIC -> "Dramatyczny"
        WritingStyle.HUMOROUS -> "Humorystyczny"
        WritingStyle.POETIC -> "Poetycki"
        WritingStyle.ACADEMIC -> "Akademicki"
    }
    
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) }
    )
}

@Composable
private fun ModelChip(
    model: AIModel,
    selected: Boolean,
    onClick: () -> Unit
) {
    val (label, icon) = when (model) {
        AIModel.GPT4 -> "GPT-4 Turbo" to "🤖"
        AIModel.GPT4O -> "GPT-4o" to "⚡"
        AIModel.CLAUDE -> "Claude Opus" to "🧠"
        AIModel.CLAUDE_SONNET -> "Claude Sonnet" to "🎵"
        AIModel.GEMINI -> "Gemini Pro" to "💎"
    }
    
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text("$icon $label") }
    )
}

@Composable
private fun ApiKeyCard(
    title: String,
    icon: String,
    value: String,
    onValueChange: (String) -> Unit,
    onSave: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(icon, fontSize = 24.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Text(title, fontWeight = FontWeight.Bold)
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                label = { Text("API Key") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                trailingIcon = {
                    IconButton(onClick = onSave) {
                        Icon(Icons.Default.Save, "Zapisz")
                    }
                }
            )
        }
    }
}

@Composable
private fun ExportDialog(
    book: Book,
    onDismiss: () -> Unit,
    onExport: (ExportFormat) -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.FileDownload, null) },
        title = { Text("Eksportuj: ${book.title}") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Wybierz format:")
                
                ExportFormatButton(
                    format = ExportFormat.PDF,
                    icon = "📄",
                    description = "Najlepszy do druku",
                    onClick = { onExport(ExportFormat.PDF) }
                )
                
                ExportFormatButton(
                    format = ExportFormat.EPUB,
                    icon = "📱",
                    description = "Kindle, czytniki e-book",
                    onClick = { onExport(ExportFormat.EPUB) }
                )
                
                ExportFormatButton(
                    format = ExportFormat.DOCX,
                    icon = "📝",
                    description = "Microsoft Word",
                    onClick = { onExport(ExportFormat.DOCX) }
                )
                
                ExportFormatButton(
                    format = ExportFormat.TXT,
                    icon = "📃",
                    description = "Czysty tekst",
                    onClick = { onExport(ExportFormat.TXT) }
                )
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Anuluj")
            }
        }
    )
}

@Composable
private fun ExportFormatButton(
    format: ExportFormat,
    icon: String,
    description: String,
    onClick: () -> Unit
) {
    OutlinedCard(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(icon, fontSize = 24.sp)
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    format.extension.uppercase(),
                    fontWeight = FontWeight.Bold
                )
                Text(
                    description,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(Icons.Default.ChevronRight, null)
        }
    }
}

private fun estimateTime(length: BookLength, chapters: Int): String {
    val baseMinutes = when (length) {
        BookLength.SHORT -> 5
        BookLength.MEDIUM -> 15
        BookLength.LONG -> 30
        BookLength.EPIC -> 45
    }
    val totalMinutes = baseMinutes * chapters / 10
    
    return when {
        totalMinutes < 60 -> "$totalMinutes min"
        else -> "${totalMinutes / 60}h ${totalMinutes % 60}min"
    }
}

private fun formatFileSize(bytes: Long): String {
    return when {
        bytes < 1024 -> "$bytes B"
        bytes < 1024 * 1024 -> "${bytes / 1024} KB"
        else -> "${bytes / (1024 * 1024)} MB"
    }
}
