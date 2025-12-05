package com.alfa.mail.ai

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * 🤖 AI ASSIST SERVICE
 * 
 * Inteligentne sugestie dla emaili:
 * - Gemini API (online)
 * - Ollama (local, offline)
 * - Szablony (fallback)
 */
class AiAssistService private constructor(private val context: Context) {
    
    enum class AiProvider {
        GEMINI,     // Google Gemini API
        OLLAMA,     // Local Ollama
        OPENAI,     // OpenAI (backup)
        TEMPLATE    // Offline templates
    }
    
    data class AiConfig(
        val provider: AiProvider = AiProvider.GEMINI,
        val geminiApiKey: String? = null,
        val ollamaUrl: String = "http://localhost:11434",
        val ollamaModel: String = "llama3",
        val openaiApiKey: String? = null
    )
    
    sealed class AiResult {
        data class Success(val text: String, val provider: AiProvider) : AiResult()
        data class Error(val message: String) : AiResult()
    }
    
    // 🧠 Streaming result z widocznymi myślami (jak DeepSeek)
    data class ThinkingStep(
        val thought: String,
        val timestamp: Long = System.currentTimeMillis()
    )
    
    data class StreamingResult(
        val thoughts: MutableList<ThinkingStep> = mutableListOf(),
        val finalText: String = "",
        val isComplete: Boolean = false,
        val error: String? = null
    )
    
    private var config: AiConfig = AiConfig()
    
    companion object {
        @Volatile
        private var instance: AiAssistService? = null
        
        fun getInstance(context: Context): AiAssistService {
            return instance ?: synchronized(this) {
                instance ?: AiAssistService(context.applicationContext).also { instance = it }
            }
        }
        
        // Szablony dla różnych typów emaili
        private val TEMPLATES = mapOf(
            "formal" to """
                Szanowny/a Panie/Pani,
                
                [Treść wiadomości]
                
                Z poważaniem,
                [Twoje imię]
            """.trimIndent(),
            
            "informal" to """
                Cześć!
                
                [Treść wiadomości]
                
                Pozdrawiam,
                [Twoje imię]
            """.trimIndent(),
            
            "business" to """
                Dzień dobry,
                
                W nawiązaniu do [temat], chciałbym/chciałabym [cel wiadomości].
                
                [Szczegóły]
                
                Czekam na odpowiedź.
                
                Z poważaniem,
                [Twoje imię]
                [Stanowisko]
            """.trimIndent(),
            
            "thank_you" to """
                Szanowny/a [imię],
                
                Dziękuję za [powód podziękowania].
                
                [Opcjonalnie: szczegóły]
                
                Jeszcze raz dziękuję i pozdrawiam,
                [Twoje imię]
            """.trimIndent(),
            
            "follow_up" to """
                Dzień dobry,
                
                Nawiązuję do naszej poprzedniej rozmowy/wymiany emaili dotyczącej [temat].
                
                Chciałbym/chciałabym zapytać o aktualny status [sprawa].
                
                Czekam na informację.
                
                Z poważaniem,
                [Twoje imię]
            """.trimIndent(),
            
            "apology" to """
                Szanowny/a [imię],
                
                Przepraszam za [powód przeprosin].
                
                [Wyjaśnienie sytuacji]
                
                [Propozycja rozwiązania]
                
                Mam nadzieję na zrozumienie.
                
                Z poważaniem,
                [Twoje imię]
            """.trimIndent()
        )
    }
    
    /**
     * Konfiguruj AI
     */
    fun configure(newConfig: AiConfig) {
        config = newConfig
    }
    
    /**
     * Załaduj konfigurację z storage
     */
    suspend fun loadConfig(): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val prefs = context.getSharedPreferences("alfa_ai_config", Context.MODE_PRIVATE)
                val provider = AiProvider.valueOf(prefs.getString("provider", "GEMINI") ?: "GEMINI")
                
                config = AiConfig(
                    provider = provider,
                    geminiApiKey = prefs.getString("gemini_key", null),
                    ollamaUrl = prefs.getString("ollama_url", "http://localhost:11434") ?: "http://localhost:11434",
                    ollamaModel = prefs.getString("ollama_model", "llama3") ?: "llama3",
                    openaiApiKey = prefs.getString("openai_key", null)
                )
                true
            } catch (e: Exception) {
                false
            }
        }
    }
    
    /**
     * Sugestia dla emaila
     */
    suspend fun suggestEmail(
        context: EmailContext,
        style: String = "professional"
    ): AiResult {
        val prompt = buildPrompt(context, style)
        
        // Próbuj różne providery
        return when (config.provider) {
            AiProvider.GEMINI -> {
                val result = tryGemini(prompt)
                if (result is AiResult.Error) tryOllama(prompt) else result
            }
            AiProvider.OLLAMA -> {
                val result = tryOllama(prompt)
                if (result is AiResult.Error) tryTemplate(context, style) else result
            }
            AiProvider.OPENAI -> {
                val result = tryOpenAI(prompt)
                if (result is AiResult.Error) tryGemini(prompt) else result
            }
            AiProvider.TEMPLATE -> tryTemplate(context, style)
        }
    }
    
    /**
     * Popraw email
     */
    suspend fun improveEmail(
        currentBody: String,
        instruction: String = "Popraw ten email, zachowując sens ale ulepszając styl"
    ): AiResult {
        val prompt = """
            $instruction
            
            Oryginalny email:
            $currentBody
            
            Poprawiony email:
        """.trimIndent()
        
        return when (config.provider) {
            AiProvider.GEMINI -> tryGemini(prompt)
            AiProvider.OLLAMA -> tryOllama(prompt)
            AiProvider.OPENAI -> tryOpenAI(prompt)
            AiProvider.TEMPLATE -> AiResult.Success(currentBody, AiProvider.TEMPLATE)
        }
    }
    
    /**
     * Generuj temat emaila
     */
    suspend fun suggestSubject(body: String): AiResult {
        val prompt = """
            Wygeneruj krótki, profesjonalny temat emaila dla poniższej treści.
            Odpowiedz TYLKO tematem, bez dodatkowego tekstu.
            
            Treść:
            $body
        """.trimIndent()
        
        return when (config.provider) {
            AiProvider.GEMINI -> tryGemini(prompt)
            AiProvider.OLLAMA -> tryOllama(prompt)
            AiProvider.OPENAI -> tryOpenAI(prompt)
            AiProvider.TEMPLATE -> AiResult.Success("Re: Wiadomość", AiProvider.TEMPLATE)
        }
    }
    
    /**
     * Automatyczne odpowiedzi
     */
    suspend fun suggestReply(
        originalEmail: String,
        replyIntent: String = "positive" // positive, negative, neutral, question
    ): AiResult {
        val intentDescription = when (replyIntent) {
            "positive" -> "pozytywna, zgadzająca się"
            "negative" -> "grzeczna odmowa"
            "neutral" -> "neutralna, informacyjna"
            "question" -> "pytająca o więcej szczegółów"
            else -> "profesjonalna"
        }
        
        val prompt = """
            Napisz $intentDescription odpowiedź na poniższy email.
            Zachowaj profesjonalny ton.
            
            Oryginalny email:
            $originalEmail
            
            Odpowiedź:
        """.trimIndent()
        
        return when (config.provider) {
            AiProvider.GEMINI -> tryGemini(prompt)
            AiProvider.OLLAMA -> tryOllama(prompt)
            else -> tryTemplate(EmailContext("", "", "reply"), "formal")
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PROVIDERS
    // ═══════════════════════════════════════════════════════════════════════
    
    private suspend fun tryGemini(prompt: String): AiResult {
        val apiKey = config.geminiApiKey ?: return AiResult.Error("Gemini API key not configured")
        
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=$apiKey")
                val connection = url.openConnection() as HttpURLConnection
                
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    doOutput = true
                    connectTimeout = 15000
                    readTimeout = 30000
                }
                
                val requestBody = JSONObject().apply {
                    put("contents", JSONArray().apply {
                        put(JSONObject().apply {
                            put("parts", JSONArray().apply {
                                put(JSONObject().apply {
                                    put("text", prompt)
                                })
                            })
                        })
                    })
                }
                
                connection.outputStream.use { os ->
                    os.write(requestBody.toString().toByteArray())
                }
                
                if (connection.responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().readText()
                    val json = JSONObject(response)
                    val text = json.getJSONArray("candidates")
                        .getJSONObject(0)
                        .getJSONObject("content")
                        .getJSONArray("parts")
                        .getJSONObject(0)
                        .getString("text")
                    
                    AiResult.Success(text.trim(), AiProvider.GEMINI)
                } else {
                    val error = connection.errorStream?.bufferedReader()?.readText() ?: "Unknown error"
                    AiResult.Error("Gemini error: $error")
                }
            } catch (e: Exception) {
                AiResult.Error("Gemini failed: ${e.message}")
            }
        }
    }
    
    private suspend fun tryOllama(prompt: String): AiResult {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("${config.ollamaUrl}/api/generate")
                val connection = url.openConnection() as HttpURLConnection
                
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    doOutput = true
                    connectTimeout = 5000
                    readTimeout = 60000
                }
                
                val requestBody = JSONObject().apply {
                    put("model", config.ollamaModel)
                    put("prompt", prompt)
                    put("stream", false)
                }
                
                connection.outputStream.use { os ->
                    os.write(requestBody.toString().toByteArray())
                }
                
                if (connection.responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().readText()
                    val json = JSONObject(response)
                    val text = json.getString("response")
                    
                    AiResult.Success(text.trim(), AiProvider.OLLAMA)
                } else {
                    AiResult.Error("Ollama error: ${connection.responseCode}")
                }
            } catch (e: Exception) {
                AiResult.Error("Ollama unavailable: ${e.message}")
            }
        }
    }
    
    private suspend fun tryOpenAI(prompt: String): AiResult {
        val apiKey = config.openaiApiKey ?: return AiResult.Error("OpenAI API key not configured")
        
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("https://api.openai.com/v1/chat/completions")
                val connection = url.openConnection() as HttpURLConnection
                
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Authorization", "Bearer $apiKey")
                    doOutput = true
                    connectTimeout = 15000
                    readTimeout = 30000
                }
                
                val requestBody = JSONObject().apply {
                    put("model", "gpt-3.5-turbo")
                    put("messages", JSONArray().apply {
                        put(JSONObject().apply {
                            put("role", "user")
                            put("content", prompt)
                        })
                    })
                    put("max_tokens", 1000)
                }
                
                connection.outputStream.use { os ->
                    os.write(requestBody.toString().toByteArray())
                }
                
                if (connection.responseCode == 200) {
                    val response = connection.inputStream.bufferedReader().readText()
                    val json = JSONObject(response)
                    val text = json.getJSONArray("choices")
                        .getJSONObject(0)
                        .getJSONObject("message")
                        .getString("content")
                    
                    AiResult.Success(text.trim(), AiProvider.OPENAI)
                } else {
                    AiResult.Error("OpenAI error: ${connection.responseCode}")
                }
            } catch (e: Exception) {
                AiResult.Error("OpenAI failed: ${e.message}")
            }
        }
    }
    
    private fun tryTemplate(context: EmailContext, style: String): AiResult {
        val template = TEMPLATES[style] ?: TEMPLATES["formal"]!!
        return AiResult.Success(template, AiProvider.TEMPLATE)
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════════════
    
    data class EmailContext(
        val to: String,
        val subject: String,
        val purpose: String, // e.g., "request", "thank_you", "inquiry"
        val additionalContext: String = ""
    )
    
    private fun buildPrompt(context: EmailContext, style: String): String {
        val styleDescription = when (style) {
            "formal" -> "formalny, oficjalny"
            "informal" -> "nieformalny, przyjazny"
            "business" -> "biznesowy, profesjonalny"
            "friendly" -> "przyjacielski, ciepły"
            else -> "profesjonalny"
        }
        
        return """
            Napisz email w stylu: $styleDescription
            
            Odbiorca: ${context.to}
            Temat: ${context.subject}
            Cel: ${context.purpose}
            ${if (context.additionalContext.isNotEmpty()) "Dodatkowy kontekst: ${context.additionalContext}" else ""}
            
            Napisz TYLKO treść emaila, bez tematu i nagłówków.
            Email powinien być w języku polskim.
        """.trimIndent()
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // 🧠 STREAMING Z WIDOCZNYMI MYŚLAMI (JAK DEEPSEEK)
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Streamuj generowanie emaila z widocznymi myślami AI
     */
    suspend fun suggestEmailStreaming(
        context: EmailContext,
        style: String = "professional",
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        return when (config.provider) {
            AiProvider.GEMINI -> streamGemini(context, style, onThought, onProgress, onComplete, onError)
            AiProvider.OLLAMA -> streamOllama(context, style, onThought, onProgress, onComplete, onError)
            else -> {
                // Fallback bez streaming
                onThought(ThinkingStep("💭 Używam lokalnych szablonów..."))
                kotlinx.coroutines.delay(300)
                val result = tryTemplate(context, style)
                when (result) {
                    is AiResult.Success -> {
                        onThought(ThinkingStep("✅ Szablon załadowany!"))
                        onComplete(result.text)
                    }
                    is AiResult.Error -> onError(result.message)
                }
            }
        }
    }
    
    /**
     * Streamuj poprawę emaila z myślami
     */
    suspend fun improveEmailStreaming(
        currentBody: String,
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        onThought(ThinkingStep("🤔 Analizuję oryginalny email..."))
        kotlinx.coroutines.delay(200)
        onThought(ThinkingStep("📏 Długość: ${currentBody.length} znaków"))
        kotlinx.coroutines.delay(200)
        
        val prompt = """
            Popraw ten email, zachowując sens ale ulepszając styl.
            Pomyśl krok po kroku jak go poprawić.
            
            Oryginalny email:
            $currentBody
            
            Poprawiony email:
        """.trimIndent()
        
        when (config.provider) {
            AiProvider.GEMINI -> streamGeminiRaw(prompt, onThought, onProgress, onComplete, onError)
            AiProvider.OLLAMA -> streamOllamaRaw(prompt, onThought, onProgress, onComplete, onError)
            else -> {
                onThought(ThinkingStep("⚠️ Brak AI, zwracam oryginalny tekst"))
                onComplete(currentBody)
            }
        }
    }
    
    // Gemini streaming implementation
    private suspend fun streamGemini(
        context: EmailContext,
        style: String,
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        try {
            onThought(ThinkingStep("🤔 Analizuję kontekst emaila..."))
            kotlinx.coroutines.delay(300)
            onThought(ThinkingStep("📝 Odbiorca: ${context.to}"))
            kotlinx.coroutines.delay(200)
            onThought(ThinkingStep("📋 Temat: ${context.subject}"))
            kotlinx.coroutines.delay(200)
            onThought(ThinkingStep("🎨 Styl: $style"))
            kotlinx.coroutines.delay(300)
            
            val prompt = buildPrompt(context, style)
            streamGeminiRaw(prompt, onThought, onProgress, onComplete, onError)
        } catch (e: Exception) {
            onError("Gemini error: ${e.message}")
        }
    }
    
    private suspend fun streamGeminiRaw(
        prompt: String,
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        try {
            val apiKey = config.geminiApiKey
            if (apiKey.isNullOrBlank()) {
                onError("Brak klucza API Gemini")
                return@withContext
            }
            
            onThought(ThinkingStep("🔮 Łączę się z Gemini API..."))
            kotlinx.coroutines.delay(200)
            
            val url = URL("https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:streamGenerateContent?key=$apiKey&alt=sse")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            
            val jsonBody = JSONObject().apply {
                put("contents", JSONArray().apply {
                    put(JSONObject().apply {
                        put("parts", JSONArray().apply {
                            put(JSONObject().apply {
                                put("text", prompt)
                            })
                        })
                    })
                })
            }.toString()
            
            connection.outputStream.use { it.write(jsonBody.toByteArray()) }
            
            onThought(ThinkingStep("✨ Model zaczyna myśleć..."))
            kotlinx.coroutines.delay(300)
            
            val reader = connection.inputStream.bufferedReader()
            var fullText = ""
            var line: String?
            var lastThoughtTime = System.currentTimeMillis()
            
            while (reader.readLine().also { line = it } != null) {
                if (line!!.startsWith("data: ")) {
                    val data = line!!.substring(6)
                    if (data.trim() != "[DONE]") {
                        try {
                            val json = JSONObject(data)
                            val candidates = json.optJSONArray("candidates")
                            if (candidates != null && candidates.length() > 0) {
                                val content = candidates.getJSONObject(0).optJSONObject("content")
                                val parts = content?.optJSONArray("parts")
                                if (parts != null && parts.length() > 0) {
                                    val text = parts.getJSONObject(0).optString("text", "")
                                    if (text.isNotEmpty()) {
                                        fullText += text
                                        onProgress(fullText)
                                        
                                        // Pokazuj myśli co jakiś czas
                                        val now = System.currentTimeMillis()
                                        if (now - lastThoughtTime > 1000) {
                                            onThought(ThinkingStep("✍️ Generuję... (${fullText.length} znaków)"))
                                            lastThoughtTime = now
                                        }
                                    }
                                }
                            }
                        } catch (e: Exception) {
                            // Ignoruj błędy parsowania pojedynczych chunków
                        }
                    }
                }
            }
            
            if (fullText.isBlank()) {
                onThought(ThinkingStep("⚠️ Streaming niedostępny, próbuję standardowego API..."))
                val result = tryGemini(prompt)
                when (result) {
                    is AiResult.Success -> {
                        onThought(ThinkingStep("✅ Gotowe!"))
                        onComplete(result.text)
                    }
                    is AiResult.Error -> onError(result.message)
                }
            } else {
                onThought(ThinkingStep("✅ Email wygenerowany pomyślnie!"))
                kotlinx.coroutines.delay(300)
                onComplete(fullText)
            }
        } catch (e: Exception) {
            onError("Gemini streaming error: ${e.message}")
        }
    }
    
    // Ollama streaming implementation
    private suspend fun streamOllama(
        context: EmailContext,
        style: String,
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        try {
            onThought(ThinkingStep("🤔 Analizuję żądanie..."))
            kotlinx.coroutines.delay(200)
            onThought(ThinkingStep("📋 Kontekst: ${context.to} - ${context.subject}"))
            kotlinx.coroutines.delay(200)
            
            val prompt = buildPrompt(context, style)
            streamOllamaRaw(prompt, onThought, onProgress, onComplete, onError)
        } catch (e: Exception) {
            onError("Ollama error: ${e.message}")
        }
    }
    
    private suspend fun streamOllamaRaw(
        prompt: String,
        onThought: (ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) = withContext(Dispatchers.IO) {
        try {
            onThought(ThinkingStep("🖥️ Łączę się z Ollama (${config.ollamaModel})..."))
            kotlinx.coroutines.delay(200)
            
            val url = URL("${config.ollamaUrl}/api/generate")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.doOutput = true
            
            val jsonBody = JSONObject().apply {
                put("model", config.ollamaModel)
                put("prompt", prompt)
                put("stream", true)
            }.toString()
            
            connection.outputStream.use { it.write(jsonBody.toByteArray()) }
            
            onThought(ThinkingStep("✨ Model lokalny myśli..."))
            kotlinx.coroutines.delay(300)
            
            val reader = connection.inputStream.bufferedReader()
            var fullText = ""
            var line: String?
            var lastThoughtTime = System.currentTimeMillis()
            
            while (reader.readLine().also { line = it } != null) {
                try {
                    val json = JSONObject(line!!)
                    val response = json.optString("response", "")
                    if (response.isNotEmpty()) {
                        fullText += response
                        onProgress(fullText)
                        
                        val now = System.currentTimeMillis()
                        if (now - lastThoughtTime > 800) {
                            onThought(ThinkingStep("✍️ Piszę... (${fullText.length} znaków)"))
                            lastThoughtTime = now
                        }
                    }
                    
                    if (json.optBoolean("done", false)) {
                        break
                    }
                } catch (e: Exception) {
                    // Ignoruj błędy parsowania
                }
            }
            
            onThought(ThinkingStep("✅ Zakończono generowanie!"))
            kotlinx.coroutines.delay(200)
            onComplete(fullText)
        } catch (e: Exception) {
            onError("Ollama error: ${e.message}")
        }
    }
}

