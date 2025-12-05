package com.alfa.mail.ai

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * 🎨 ALFA UI GENERATOR
 * 
 * AI generuje CAŁE EKRANY i KOMPONENTY UI w Jetpack Compose!
 * 
 * Możliwości:
 * - Opisz co chcesz → AI tworzy ekran
 * - Widoczny proces myślenia (jak DeepSeek)
 * - Generuje kod Kotlin/Compose
 * - Preview w czasie rzeczywistym
 * - Export do plików .kt
 * 
 * Przykład:
 * "Stwórz ekran logowania z logo, email, hasło i przyciskiem"
 * → AI generuje pełny LoginScreen.kt composable
 */
class AlfaUIGenerator private constructor(private val context: Context) {
    
    data class GeneratedUI(
        val componentName: String,
        val code: String,
        val imports: List<String>,
        val preview: String,
        val description: String
    )
    
    sealed class GenerationResult {
        data class Success(val ui: GeneratedUI) : GenerationResult()
        data class Error(val message: String) : GenerationResult()
    }
    
    private val aiAssist = AiAssistService.getInstance(context)
    
    companion object {
        @Volatile
        private var instance: AlfaUIGenerator? = null
        
        fun getInstance(context: Context): AlfaUIGenerator {
            return instance ?: synchronized(this) {
                instance ?: AlfaUIGenerator(context.applicationContext).also { instance = it }
            }
        }
        
        // Biblioteka wzorców UI
        private val UI_PATTERNS = mapOf(
            "login_screen" to """
                @Composable
                fun LoginScreen() {
                    var email by remember { mutableStateOf("") }
                    var password by remember { mutableStateOf("") }
                    
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text("Login", style = MaterialTheme.typography.headlineLarge)
                        Spacer(modifier = Modifier.height(32.dp))
                        
                        OutlinedTextField(
                            value = email,
                            onValueChange = { email = it },
                            label = { Text("Email") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            label = { Text("Password") },
                            visualTransformation = PasswordVisualTransformation(),
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        
                        Button(
                            onClick = { /* TODO: Login logic */ },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Sign In")
                        }
                    }
                }
            """.trimIndent(),
            
            "list_screen" to """
                @Composable
                fun ItemListScreen(items: List<String>) {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(items) { item ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                            ) {
                                Text(
                                    text = item,
                                    modifier = Modifier.padding(16.dp)
                                )
                            }
                        }
                    }
                }
            """.trimIndent(),
            
            "form_screen" to """
                @Composable
                fun FormScreen() {
                    var name by remember { mutableStateOf("") }
                    var email by remember { mutableStateOf("") }
                    var message by remember { mutableStateOf("") }
                    
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                    ) {
                        OutlinedTextField(
                            value = name,
                            onValueChange = { name = it },
                            label = { Text("Name") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        OutlinedTextField(
                            value = email,
                            onValueChange = { email = it },
                            label = { Text("Email") },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        OutlinedTextField(
                            value = message,
                            onValueChange = { message = it },
                            label = { Text("Message") },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(120.dp),
                            maxLines = 5
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        
                        Button(
                            onClick = { /* Submit */ },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Submit")
                        }
                    }
                }
            """.trimIndent()
        )
    }
    
    /**
     * Generuj UI z opisem - Z WIDOCZNYMI MYŚLAMI!
     */
    suspend fun generateUI(
        userPrompt: String,
        onThought: (AiAssistService.ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (GeneratedUI) -> Unit,
        onError: (String) -> Unit
    ) {
        withContext(Dispatchers.IO) {
            try {
                onThought(AiAssistService.ThinkingStep("🤔 Analizuję co chcesz stworzyć..."))
                kotlinx.coroutines.delay(300)
                
                onThought(AiAssistService.ThinkingStep("📋 Prompt: \"$userPrompt\""))
                kotlinx.coroutines.delay(200)
                
                // Wykryj typ ekranu
                val screenType = detectScreenType(userPrompt)
                onThought(AiAssistService.ThinkingStep("🎯 Wykryto typ: $screenType"))
                kotlinx.coroutines.delay(200)
                
                // Znajdź podobny wzorzec
                val basePattern = findBestPattern(screenType)
                onThought(AiAssistService.ThinkingStep("📐 Wybieram bazowy wzorzec..."))
                kotlinx.coroutines.delay(200)
                
                onThought(AiAssistService.ThinkingStep("🧠 Łączę się z AI do dostosowania..."))
                kotlinx.coroutines.delay(300)
                
                // Generuj z AI (streaming)
                val prompt = buildUIPrompt(userPrompt, basePattern)
                
                aiAssist.improveEmailStreaming(
                    currentBody = prompt,
                    onThought = { thought ->
                        onThought(AiAssistService.ThinkingStep("🤖 AI: ${thought.thought}"))
                    },
                    onProgress = { progress ->
                        onProgress(progress)
                        onThought(AiAssistService.ThinkingStep("✍️ Generuję kod... (${progress.length} znaków)"))
                    },
                    onComplete = { generatedCode ->
                        onThought(AiAssistService.ThinkingStep("🎨 Przetwarzam wygenerowany kod..."))
                        
                        // Parse i struktura
                        val ui = parseGeneratedCode(generatedCode, userPrompt)
                        
                        onThought(AiAssistService.ThinkingStep("✅ UI wygenerowane pomyślnie!"))
                        onThought(AiAssistService.ThinkingStep("📦 Komponent: ${ui.componentName}"))
                        onThought(AiAssistService.ThinkingStep("📝 Linie kodu: ${ui.code.lines().size}"))
                        
                        onComplete(ui)
                    },
                    onError = { error ->
                        onThought(AiAssistService.ThinkingStep("❌ Błąd AI: $error"))
                        
                        // Fallback - użyj wzorca
                        onThought(AiAssistService.ThinkingStep("🔄 Używam wzorca offline..."))
                        val fallbackUI = createFromPattern(screenType, userPrompt)
                        onComplete(fallbackUI)
                    }
                )
                
            } catch (e: Exception) {
                onError("Generator error: ${e.message}")
            }
        }
    }
    
    /**
     * Wykryj jaki typ ekranu user chce
     */
    private fun detectScreenType(prompt: String): String {
        val lowerPrompt = prompt.lowercase()
        
        return when {
            lowerPrompt.contains("login") || lowerPrompt.contains("logowanie") -> "login"
            lowerPrompt.contains("list") || lowerPrompt.contains("lista") -> "list"
            lowerPrompt.contains("form") || lowerPrompt.contains("formularz") -> "form"
            lowerPrompt.contains("profile") || lowerPrompt.contains("profil") -> "profile"
            lowerPrompt.contains("settings") || lowerPrompt.contains("ustawienia") -> "settings"
            lowerPrompt.contains("detail") || lowerPrompt.contains("szczegóły") -> "detail"
            lowerPrompt.contains("card") || lowerPrompt.contains("karta") -> "card"
            lowerPrompt.contains("navigation") || lowerPrompt.contains("nawigacja") -> "navigation"
            lowerPrompt.contains("dashboard") || lowerPrompt.contains("pulpit") -> "dashboard"
            else -> "custom"
        }
    }
    
    /**
     * Znajdź najlepszy wzorzec bazowy
     */
    private fun findBestPattern(screenType: String): String {
        return when (screenType) {
            "login" -> UI_PATTERNS["login_screen"]!!
            "list" -> UI_PATTERNS["list_screen"]!!
            "form" -> UI_PATTERNS["form_screen"]!!
            else -> UI_PATTERNS["form_screen"]!! // Default
        }
    }
    
    /**
     * Zbuduj prompt dla AI
     */
    private fun buildUIPrompt(userPrompt: String, basePattern: String): String {
        return """
            Jesteś ekspertem od Jetpack Compose UI w Androidzie.
            
            USER REQUEST: $userPrompt
            
            BASE PATTERN:
            ```kotlin
            $basePattern
            ```
            
            ZADANIE:
            1. Przeanalizuj co user chce stworzyć
            2. Użyj BASE PATTERN jako punkt startowy
            3. Dostosuj kod do wymagań usera
            4. Wygeneruj KOMPLETNY @Composable function
            5. Używaj Material3
            6. Dodaj wszystkie potrzebne importy
            
            WYMAGANIA:
            - Kod musi być gotowy do użycia (bez TODO)
            - Wszystkie state używa remember { mutableStateOf() }
            - Używaj Modifier.fillMaxWidth(), padding(), etc.
            - Dodaj sensowne domyślne wartości
            
            ODPOWIEDŹ TYLKO KODEM KOTLIN (bez markdown, bez wyjaśnień):
        """.trimIndent()
    }
    
    /**
     * Parsuj wygenerowany kod AI
     */
    private fun parseGeneratedCode(code: String, originalPrompt: String): GeneratedUI {
        // Wyciągnij nazwę funkcji
        val functionNameRegex = """@Composable\s+fun\s+(\w+)""".toRegex()
        val match = functionNameRegex.find(code)
        val componentName = match?.groupValues?.get(1) ?: "GeneratedScreen"
        
        // Wykryj potrzebne importy
        val imports = mutableListOf<String>()
        imports.add("androidx.compose.runtime.*")
        imports.add("androidx.compose.material3.*")
        imports.add("androidx.compose.foundation.layout.*")
        imports.add("androidx.compose.ui.Modifier")
        imports.add("androidx.compose.ui.Alignment")
        imports.add("androidx.compose.ui.unit.dp")
        
        if (code.contains("LazyColumn")) {
            imports.add("androidx.compose.foundation.lazy.*")
        }
        if (code.contains("PasswordVisualTransformation")) {
            imports.add("androidx.compose.ui.text.input.PasswordVisualTransformation")
        }
        
        // Generuj preview
        val preview = """
            @Preview(showBackground = true)
            @Composable
            fun ${componentName}Preview() {
                MaterialTheme {
                    $componentName()
                }
            }
        """.trimIndent()
        
        return GeneratedUI(
            componentName = componentName,
            code = code.trim(),
            imports = imports,
            preview = preview,
            description = originalPrompt
        )
    }
    
    /**
     * Stwórz z wzorca (fallback offline)
     */
    private fun createFromPattern(screenType: String, prompt: String): GeneratedUI {
        val pattern = findBestPattern(screenType)
        return parseGeneratedCode(pattern, prompt)
    }
    
    /**
     * Zapisz wygenerowany UI do pliku
     */
    suspend fun exportToFile(ui: GeneratedUI, fileName: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val file = java.io.File(context.filesDir, "$fileName.kt")
                
                val fullCode = buildString {
                    appendLine("package com.alfa.mail.generated")
                    appendLine()
                    ui.imports.forEach { imp ->
                        appendLine("import $imp")
                    }
                    appendLine()
                    appendLine("// Generated by ALFA UI Generator")
                    appendLine("// Prompt: ${ui.description}")
                    appendLine()
                    appendLine(ui.code)
                    appendLine()
                    appendLine(ui.preview)
                }
                
                file.writeText(fullCode)
                true
            } catch (e: Exception) {
                false
            }
        }
    }
    
    /**
     * Lista wygenerowanych UI
     */
    fun listGeneratedUIs(): List<String> {
        return context.filesDir.listFiles { file ->
            file.extension == "kt" && file.name.startsWith("Generated")
        }?.map { it.nameWithoutExtension } ?: emptyList()
    }
}
