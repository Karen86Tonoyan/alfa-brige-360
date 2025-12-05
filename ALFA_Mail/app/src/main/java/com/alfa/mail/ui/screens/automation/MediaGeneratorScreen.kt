package com.alfa.mail.ui.screens.automation

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.alfa.mail.automation.MediaGenerator
import com.alfa.mail.automation.MediaGenerator.*
import kotlinx.coroutines.launch
import java.io.File

/**
 * 🎬 MEDIA GENERATOR SCREEN
 * 
 * Ekran do generowania:
 * ✅ Zdjęć z AI (DALL-E 3, Stable Diffusion, Midjourney)
 * ✅ Wideo 6 sekund (Runway, Pika, Stable Video)
 * ✅ Animacji zdjęć (image-to-video)
 * ✅ Edycji i upscale
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MediaGeneratorScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val generator = remember { MediaGenerator.getInstance(context) }
    
    var selectedTab by remember { mutableStateOf(0) }
    var prompt by remember { mutableStateOf("") }
    var isGenerating by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf<GenerationProgress?>(null) }
    var lastResult by remember { mutableStateOf<Any?>(null) }
    var generatedFiles by remember { mutableStateOf<List<File>>(emptyList()) }
    
    // Image settings
    var selectedImageStyle by remember { mutableStateOf(ImageStyle.CINEMATIC) }
    var selectedImageProvider by remember { mutableStateOf(ImageProvider.DALL_E_3) }
    var selectedQuality by remember { mutableStateOf(ImageQuality.HD) }
    
    // Video settings
    var selectedVideoStyle by remember { mutableStateOf(VideoStyle.CINEMATIC) }
    var selectedVideoProvider by remember { mutableStateOf(VideoProvider.RUNWAY_GEN2) }
    var selectedMotion by remember { mutableStateOf(MotionType.AUTO) }
    var videoDuration by remember { mutableStateOf(6) }
    
    LaunchedEffect(Unit) {
        generatedFiles = generator.getGeneratedMediaList()
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("🎬 Media Generator", fontWeight = FontWeight.Bold)
                        Text("AI Image & Video", fontSize = 12.sp, color = Color.Gray)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, "Back", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF1A1A2E),
                    titleContentColor = Color.White
                )
            )
        },
        containerColor = Color(0xFF0F0F1A)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Tabs
            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = Color(0xFF1A1A2E),
                contentColor = Color(0xFFE94560)
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("🖼️ Zdjęcia") }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("🎬 Wideo 6s") }
                )
                Tab(
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 },
                    text = { Text("📁 Galeria") }
                )
            }
            
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                when (selectedTab) {
                    0 -> {
                        // IMAGE GENERATION TAB
                        item {
                            Text(
                                "🎨 Generuj Zdjęcie z AI",
                                fontSize = 20.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                        
                        // Prompt input
                        item {
                            OutlinedTextField(
                                value = prompt,
                                onValueChange = { prompt = it },
                                label = { Text("Opisz zdjęcie...") },
                                placeholder = { Text("np. Futurystyczne miasto o zachodzie słońca, neonowe światła...") },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(120.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    focusedBorderColor = Color(0xFFE94560),
                                    unfocusedBorderColor = Color(0xFF333333)
                                )
                            )
                        }
                        
                        // Style selection
                        item {
                            Text("🎨 Styl", color = Color.Gray, fontSize = 14.sp)
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                items(ImageStyle.values()) { style ->
                                    StyleChip(
                                        name = style.name.replace("_", " "),
                                        icon = getStyleIcon(style),
                                        selected = selectedImageStyle == style,
                                        onClick = { selectedImageStyle = style }
                                    )
                                }
                            }
                        }
                        
                        // Provider selection
                        item {
                            Text("🤖 Model AI", color = Color.Gray, fontSize = 14.sp)
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                items(ImageProvider.values()) { provider ->
                                    ProviderChip(
                                        name = provider.name.replace("_", " "),
                                        selected = selectedImageProvider == provider,
                                        onClick = { selectedImageProvider = provider }
                                    )
                                }
                            }
                        }
                        
                        // Quality selection
                        item {
                            Text("📐 Jakość", color = Color.Gray, fontSize = 14.sp)
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                ImageQuality.values().forEach { quality ->
                                    QualityChip(
                                        name = quality.name,
                                        selected = selectedQuality == quality,
                                        onClick = { selectedQuality = quality }
                                    )
                                }
                            }
                        }
                        
                        // Generate button
                        item {
                            GenerateButton(
                                text = "🎨 GENERUJ ZDJĘCIE",
                                isGenerating = isGenerating,
                                progress = progress,
                                onClick = {
                                    if (prompt.isNotBlank()) {
                                        scope.launch {
                                            isGenerating = true
                                            val result = generator.generateImage(
                                                ImageRequest(
                                                    prompt = prompt,
                                                    style = selectedImageStyle,
                                                    quality = selectedQuality,
                                                    provider = selectedImageProvider
                                                )
                                            ) { prog ->
                                                progress = prog
                                            }
                                            lastResult = result
                                            isGenerating = false
                                            progress = null
                                            generatedFiles = generator.getGeneratedMediaList()
                                        }
                                    }
                                }
                            )
                        }
                        
                        // Result preview
                        (lastResult as? ImageResult)?.let { result ->
                            item {
                                ResultCard(result)
                            }
                        }
                    }
                    
                    1 -> {
                        // VIDEO GENERATION TAB
                        item {
                            Text(
                                "🎬 Generuj Wideo 6 Sekund",
                                fontSize = 20.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                        
                        // Prompt input
                        item {
                            OutlinedTextField(
                                value = prompt,
                                onValueChange = { prompt = it },
                                label = { Text("Opisz scenę wideo...") },
                                placeholder = { Text("np. Lot przez chmury o wschodzie słońca, kamera płynnie się porusza...") },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(120.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    focusedBorderColor = Color(0xFFE94560),
                                    unfocusedBorderColor = Color(0xFF333333)
                                )
                            )
                        }
                        
                        // Duration slider
                        item {
                            Column {
                                Text("⏱️ Długość: $videoDuration sekund", color = Color.Gray)
                                Slider(
                                    value = videoDuration.toFloat(),
                                    onValueChange = { videoDuration = it.toInt() },
                                    valueRange = 2f..6f,
                                    steps = 3,
                                    colors = SliderDefaults.colors(
                                        thumbColor = Color(0xFFE94560),
                                        activeTrackColor = Color(0xFFE94560)
                                    )
                                )
                            }
                        }
                        
                        // Video style selection
                        item {
                            Text("🎥 Styl wideo", color = Color.Gray, fontSize = 14.sp)
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                items(VideoStyle.values()) { style ->
                                    StyleChip(
                                        name = style.name.replace("_", " "),
                                        icon = getVideoStyleIcon(style),
                                        selected = selectedVideoStyle == style,
                                        onClick = { selectedVideoStyle = style }
                                    )
                                }
                            }
                        }
                        
                        // Motion type
                        item {
                            Text("🎬 Typ ruchu", color = Color.Gray, fontSize = 14.sp)
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                items(MotionType.values()) { motion ->
                                    MotionChip(
                                        name = motion.name.replace("_", " "),
                                        selected = selectedMotion == motion,
                                        onClick = { selectedMotion = motion }
                                    )
                                }
                            }
                        }
                        
                        // Provider
                        item {
                            Text("🤖 Generator", color = Color.Gray, fontSize = 14.sp)
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(top = 8.dp)
                            ) {
                                items(VideoProvider.values()) { provider ->
                                    ProviderChip(
                                        name = provider.name.replace("_", " "),
                                        selected = selectedVideoProvider == provider,
                                        onClick = { selectedVideoProvider = provider }
                                    )
                                }
                            }
                        }
                        
                        // Generate button
                        item {
                            GenerateButton(
                                text = "🎬 GENERUJ WIDEO 6s",
                                isGenerating = isGenerating,
                                progress = progress,
                                onClick = {
                                    if (prompt.isNotBlank()) {
                                        scope.launch {
                                            isGenerating = true
                                            val result = generator.generateVideo(
                                                VideoRequest(
                                                    prompt = prompt,
                                                    duration = videoDuration,
                                                    style = selectedVideoStyle,
                                                    motion = selectedMotion,
                                                    provider = selectedVideoProvider
                                                )
                                            ) { prog ->
                                                progress = prog
                                            }
                                            lastResult = result
                                            isGenerating = false
                                            progress = null
                                            generatedFiles = generator.getGeneratedMediaList()
                                        }
                                    }
                                }
                            )
                        }
                        
                        // Video result preview
                        (lastResult as? VideoResult)?.let { result ->
                            item {
                                VideoResultCard(result)
                            }
                        }
                    }
                    
                    2 -> {
                        // GALLERY TAB
                        item {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    "📁 Wygenerowane Media",
                                    fontSize = 20.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                                Text(
                                    "${generatedFiles.size} plików",
                                    color = Color.Gray,
                                    fontSize = 14.sp
                                )
                            }
                        }
                        
                        if (generatedFiles.isEmpty()) {
                            item {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(200.dp)
                                        .background(Color(0xFF1A1A2E), RoundedCornerShape(16.dp)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("📭", fontSize = 48.sp)
                                        Text("Brak wygenerowanych mediów", color = Color.Gray)
                                        Text("Wygeneruj zdjęcie lub wideo!", color = Color.Gray, fontSize = 12.sp)
                                    }
                                }
                            }
                        } else {
                            items(generatedFiles.chunked(2)) { rowFiles ->
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    rowFiles.forEach { file ->
                                        MediaThumbnail(
                                            file = file,
                                            modifier = Modifier.weight(1f)
                                        )
                                    }
                                    if (rowFiles.size == 1) {
                                        Spacer(modifier = Modifier.weight(1f))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun StyleChip(
    name: String,
    icon: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(
                if (selected) Color(0xFFE94560) else Color(0xFF2A2A3E)
            )
            .border(
                1.dp,
                if (selected) Color(0xFFE94560) else Color(0xFF444444),
                RoundedCornerShape(20.dp)
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(icon, fontSize = 16.sp)
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                name,
                color = if (selected) Color.White else Color.Gray,
                fontSize = 12.sp
            )
        }
    }
}

@Composable
fun ProviderChip(
    name: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .background(
                if (selected) 
                    Brush.horizontalGradient(listOf(Color(0xFFE94560), Color(0xFF0F3460)))
                else 
                    Brush.horizontalGradient(listOf(Color(0xFF2A2A3E), Color(0xFF2A2A3E)))
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Text(
            name,
            color = Color.White,
            fontSize = 12.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal
        )
    }
}

@Composable
fun QualityChip(
    name: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(if (selected) Color(0xFF00D9FF) else Color(0xFF2A2A3E))
            .clickable(onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 8.dp)
    ) {
        Text(
            name,
            color = if (selected) Color.Black else Color.Gray,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal
        )
    }
}

@Composable
fun MotionChip(
    name: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .background(if (selected) Color(0xFF9C27B0) else Color(0xFF2A2A3E))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Text(
            name,
            color = Color.White,
            fontSize = 11.sp
        )
    }
}

@Composable
fun GenerateButton(
    text: String,
    isGenerating: Boolean,
    progress: GenerationProgress?,
    onClick: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Button(
            onClick = onClick,
            enabled = !isGenerating,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFFE94560),
                disabledContainerColor = Color(0xFF444444)
            ),
            shape = RoundedCornerShape(16.dp)
        ) {
            if (isGenerating) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = Color.White,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(progress?.message ?: "Generowanie...", fontSize = 16.sp)
            } else {
                Text(text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        }
        
        // Progress bar
        if (isGenerating && progress != null) {
            Spacer(modifier = Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { progress.progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(2.dp)),
                color = Color(0xFFE94560),
                trackColor = Color(0xFF333333)
            )
            Text(
                "${(progress.progress * 100).toInt()}%",
                color = Color.Gray,
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}

@Composable
fun ResultCard(result: ImageResult) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Color(0xFF1A1A2E))
            .padding(16.dp)
    ) {
        Column {
            if (result.success && result.imagePath != null) {
                AsyncImage(
                    model = File(result.imagePath),
                    contentDescription = "Generated image",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(300.dp)
                        .clip(RoundedCornerShape(12.dp)),
                    contentScale = ContentScale.Crop
                )
                
                Spacer(modifier = Modifier.height(12.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text("✅ Wygenerowano!", color = Color(0xFF4CAF50), fontWeight = FontWeight.Bold)
                        Text("${result.width}x${result.height}", color = Color.Gray, fontSize = 12.sp)
                    }
                    Text(
                        "${result.generationTimeMs / 1000}s",
                        color = Color.Gray
                    )
                }
                
                result.revisedPrompt?.let {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "AI prompt: $it",
                        color = Color.Gray,
                        fontSize = 11.sp,
                        maxLines = 2
                    )
                }
            } else {
                Text("❌ ${result.error ?: "Błąd generowania"}", color = Color(0xFFE94560))
            }
        }
    }
}

@Composable
fun VideoResultCard(result: VideoResult) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Color(0xFF1A1A2E))
            .padding(16.dp)
    ) {
        Column {
            if (result.success && result.videoPath != null) {
                // Thumbnail
                result.thumbnailPath?.let { thumbPath ->
                    AsyncImage(
                        model = File(thumbPath),
                        contentDescription = "Video thumbnail",
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .clip(RoundedCornerShape(12.dp)),
                        contentScale = ContentScale.Crop
                    )
                }
                
                Spacer(modifier = Modifier.height(12.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("🎬 Wideo gotowe!", color = Color(0xFF4CAF50), fontWeight = FontWeight.Bold)
                        Text("${result.duration}s • ${result.width}x${result.height}", color = Color.Gray, fontSize = 12.sp)
                    }
                    
                    Button(
                        onClick = { /* Play video */ },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFE94560))
                    ) {
                        Icon(Icons.Default.PlayArrow, "Play")
                        Text("Odtwórz")
                    }
                }
            } else {
                Text("❌ ${result.error ?: "Błąd generowania"}", color = Color(0xFFE94560))
            }
        }
    }
}

@Composable
fun MediaThumbnail(
    file: File,
    modifier: Modifier = Modifier
) {
    val isVideo = file.extension in listOf("mp4", "webm", "mov")
    
    Box(
        modifier = modifier
            .aspectRatio(1f)
            .clip(RoundedCornerShape(12.dp))
            .background(Color(0xFF2A2A3E))
    ) {
        AsyncImage(
            model = file,
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop
        )
        
        if (isVideo) {
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(40.dp)
                    .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(20.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.PlayArrow,
                    contentDescription = "Video",
                    tint = Color.White
                )
            }
        }
        
        // File info overlay
        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .fillMaxWidth()
                .background(
                    Brush.verticalGradient(
                        listOf(Color.Transparent, Color.Black.copy(alpha = 0.7f))
                    )
                )
                .padding(8.dp)
        ) {
            Text(
                file.name.take(15) + if (file.name.length > 15) "..." else "",
                color = Color.White,
                fontSize = 10.sp
            )
        }
    }
}

// Helper functions
private fun getStyleIcon(style: ImageStyle): String {
    return when (style) {
        ImageStyle.REALISTIC -> "📷"
        ImageStyle.ARTISTIC -> "🎨"
        ImageStyle.ANIME -> "🎌"
        ImageStyle.CARTOON -> "🖌️"
        ImageStyle.CINEMATIC -> "🎬"
        ImageStyle.FANTASY -> "🧙"
        ImageStyle.CYBERPUNK -> "🤖"
        ImageStyle.WATERCOLOR -> "💧"
        ImageStyle.OIL_PAINTING -> "🖼️"
        ImageStyle.SKETCH -> "✏️"
        ImageStyle.PIXEL_ART -> "👾"
        ImageStyle.THREE_D_RENDER -> "🎮"
    }
}

private fun getVideoStyleIcon(style: VideoStyle): String {
    return when (style) {
        VideoStyle.CINEMATIC -> "🎬"
        VideoStyle.ANIMATION -> "🎭"
        VideoStyle.SLOW_MOTION -> "🐢"
        VideoStyle.TIMELAPSE -> "⏰"
        VideoStyle.DOCUMENTARY -> "📹"
        VideoStyle.MUSIC_VIDEO -> "🎵"
        VideoStyle.COMMERCIAL -> "📺"
        VideoStyle.ARTISTIC -> "🎨"
    }
}
