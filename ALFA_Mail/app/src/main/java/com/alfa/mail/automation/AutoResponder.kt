package com.alfa.mail.automation

import android.content.Context
import com.alfa.mail.ai.AiAssistService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * 🤖 AUTO RESPONDER - Automatyczne odpowiadanie na emaile
 * 
 * AI czyta emaile → generuje odpowiedź → wysyła automatycznie
 * Wszystko z widocznym thinking process (jak DeepSeek)
 * 
 * Przykład:
 * Email od: jan@firma.pl
 * Temat: "Propozycja współpracy"
 * 
 * AI myśli:
 * 🤔 Analizuję email...
 * 📝 Od: jan@firma.pl
 * 📋 Temat: Propozycja współpracy
 * 🎯 Typ: Business proposal
 * 🧠 Generuję odpowiedź...
 * ✍️ Piszę... "Dziękuję za zainteresowanie..."
 * ✅ Odpowiedź gotowa! Wysyłam...
 */
class AutoResponder private constructor(private val context: Context) {
    
    data class EmailToRespond(
        val id: Long,
        val from: String,
        val subject: String,
        val body: String,
        val timestamp: Long = System.currentTimeMillis()
    )
    
    data class AutoResponse(
        val emailId: Long,
        val responseText: String,
        val confidence: Float = 1.0f,
        val thinking: List<AiAssistService.ThinkingStep> = emptyList(),
        val shouldAutoSend: Boolean = false,
        val requiresApproval: Boolean = false
    )
    
    enum class ResponseType {
        ACKNOWLEDGE,      // Potwierdzenie otrzymania
        QUESTION_ANSWER,  // Odpowiedź na pytanie
        BUSINESS_PROPOSAL, // Propozycja biznesowa
        COMPLAINT_RESOLUTION, // Rozwiązanie skargi
        NEWSLETTER_OPT_OUT, // Rezygnacja z newslettera
        SPAM_FILTER,      // Spam - nie odpowiadaj
        CUSTOM            // Custom rule
    }
    
    data class AutoResponderRule(
        val id: String = java.util.UUID.randomUUID().toString(),
        val name: String,
        val triggers: List<String> = emptyList(), // Keywords w subject/body
        val responseType: ResponseType = ResponseType.CUSTOM,
        val templateId: String? = null,
        val autoSend: Boolean = false,
        val requiresApproval: Boolean = true,
        val enabled: Boolean = true,
        val priority: Int = 50 // 1-100, wyższe = ważniejsze
    )
    
    private val aiAssist = AiAssistService.getInstance(context)
    private val prefs = context.getSharedPreferences("alfa_auto_responder", Context.MODE_PRIVATE)
    
    private var rules = mutableListOf<AutoResponderRule>()
    private var responseTemplates = mutableMapOf<String, String>()
    
    companion object {
        @Volatile
        private var instance: AutoResponder? = null
        
        fun getInstance(context: Context): AutoResponder {
            return instance ?: synchronized(this) {
                instance ?: AutoResponder(context.applicationContext).also { instance = it }
            }
        }
    }
    
    init {
        loadRules()
        loadTemplates()
    }
    
    /**
     * Główna funkcja - analizuj email i generuj odpowiedź
     */
    suspend fun respondToEmail(
        email: EmailToRespond,
        onThought: (AiAssistService.ThinkingStep) -> Unit,
        onProgress: (String) -> Unit,
        onComplete: (AutoResponse) -> Unit,
        onError: (String) -> Unit
    ) {
        withContext(Dispatchers.IO) {
            try {
                onThought(AiAssistService.ThinkingStep("🤔 Analizuję email..."))
                delay(200)
                
                onThought(AiAssistService.ThinkingStep("📝 Od: ${email.from}"))
                delay(150)
                
                onThought(AiAssistService.ThinkingStep("📋 Temat: ${email.subject}"))
                delay(150)
                
                // Wykryj typ emaila
                val responseType = detectEmailType(email)
                onThought(AiAssistService.ThinkingStep("🎯 Typ: $responseType"))
                delay(200)
                
                // Znajdź odpowiednią regułę
                val rule = findBestRule(email, responseType)
                if (rule != null) {
                    onThought(AiAssistService.ThinkingStep("📌 Reguła: ${rule.name}"))
                    delay(150)
                }
                
                // Jeśli to spam lub OPT-OUT - nie odpowiadaj
                if (responseType == ResponseType.SPAM_FILTER) {
                    onThought(AiAssistService.ThinkingStep("🚫 To spam - brak odpowiedzi"))
                    onComplete(AutoResponse(
                        emailId = email.id,
                        responseText = "",
                        shouldAutoSend = false,
                        requiresApproval = false
                    ))
                    return@withContext
                }
                
                // Generuj odpowiedź
                onThought(AiAssistService.ThinkingStep("🧠 Generuję odpowiedź..."))
                delay(300)
                
                val prompt = buildResponsePrompt(email, responseType, rule)
                
                // Stream response generation
                var responseText = ""
                aiAssist.improveEmailStreaming(
                    currentBody = prompt,
                    onThought = { thought ->
                        onThought(AiAssistService.ThinkingStep("🤖 ${thought.thought}"))
                    },
                    onProgress = { progress ->
                        responseText = progress
                        onProgress(progress)
                        onThought(AiAssistService.ThinkingStep("✍️ Piszę... (${progress.length} znaków)"))
                    },
                    onComplete = { result ->
                        responseText = result
                        
                        // Sprawdź czy wysłać automatycznie
                        val shouldAutoSend = rule?.autoSend ?: false
                        val confidence = calculateConfidence(email, result)
                        
                        onThought(AiAssistService.ThinkingStep("📊 Pewność: ${(confidence * 100).toInt()}%"))
                        delay(200)
                        
                        if (shouldAutoSend && confidence > 0.85f) {
                            onThought(AiAssistService.ThinkingStep("✅ Odpowiedź gotowa! Wysyłam automatycznie..."))
                        } else {
                            onThought(AiAssistService.ThinkingStep("✅ Odpowiedź gotowa! Czeka na zatwierdzenie..."))
                        }
                        delay(300)
                        
                        val autoResponse = AutoResponse(
                            emailId = email.id,
                            responseText = result,
                            confidence = confidence,
                            thinking = emptyList(), // Byłyby zbierane podczas myślenia AI
                            shouldAutoSend = shouldAutoSend && confidence > 0.85f,
                            requiresApproval = !shouldAutoSend || confidence <= 0.85f
                        )
                        
                        onComplete(autoResponse)
                    },
                    onError = { error ->
                        onThought(AiAssistService.ThinkingStep("❌ Błąd AI: $error"))
                        onThought(AiAssistService.ThinkingStep("🔄 Używam szablonu offline..."))
                        
                        // Fallback - template
                        val fallbackResponse = generateFromTemplate(email, responseType)
                        onComplete(AutoResponse(
                            emailId = email.id,
                            responseText = fallbackResponse,
                            confidence = 0.6f,
                            requiresApproval = true
                        ))
                    }
                )
                
            } catch (e: Exception) {
                onError("AutoResponder error: ${e.message}")
            }
        }
    }
    
    /**
     * Wykryj typ emaila
     */
    private fun detectEmailType(email: EmailToRespond): ResponseType {
        val combined = (email.subject + " " + email.body).lowercase()
        
        return when {
            // Spam patterns
            combined.contains("unsubscribe") || 
            combined.contains("newsletter") ||
            combined.contains("marketing") -> ResponseType.NEWSLETTER_OPT_OUT
            
            combined.contains("viagra") || 
            combined.contains("casino") ||
            combined.contains("click here") -> ResponseType.SPAM_FILTER
            
            // Business
            combined.contains("proposal") || 
            combined.contains("collaboration") ||
            combined.contains("partnership") -> ResponseType.BUSINESS_PROPOSAL
            
            // Questions
            combined.contains("?") && !email.body.contains("thank") -> ResponseType.QUESTION_ANSWER
            
            // Complaints
            combined.contains("problem") || 
            combined.contains("issue") ||
            combined.contains("complaint") -> ResponseType.COMPLAINT_RESOLUTION
            
            // Default - acknowledgement
            else -> ResponseType.ACKNOWLEDGE
        }
    }
    
    /**
     * Znajdź najlepszą regułę
     */
    private fun findBestRule(email: EmailToRespond, type: ResponseType): AutoResponderRule? {
        return rules
            .filter { it.enabled }
            .filter { rule ->
                rule.triggers.isEmpty() || 
                rule.triggers.any { trigger ->
                    email.subject.contains(trigger, ignoreCase = true) ||
                    email.body.contains(trigger, ignoreCase = true)
                }
            }
            .maxByOrNull { it.priority }
    }
    
    /**
     * Zbuduj prompt dla AI
     */
    private fun buildResponsePrompt(
        email: EmailToRespond,
        type: ResponseType,
        rule: AutoResponderRule?
    ): String {
        val instruction = when (type) {
            ResponseType.ACKNOWLEDGE -> 
                "Napisz krótkie, profesjonalne potwierdzenie otrzymania tej wiadomości"
            
            ResponseType.QUESTION_ANSWER -> 
                "Odpowiedz na pytanie zawarte w emailu. Bądź konkretny i pomocny"
            
            ResponseType.BUSINESS_PROPOSAL -> 
                "Odpowiedz na propozycję biznesową. Bądź profesjonalny i zainteresowany"
            
            ResponseType.COMPLAINT_RESOLUTION -> 
                "Odpowiedz na skargę. Bądź empatyczny i proponuj rozwiązanie"
            
            ResponseType.NEWSLETTER_OPT_OUT -> 
                "Potwierdź rezygnację z newslettera. Bądź krótki i profesjonalny"
            
            ResponseType.SPAM_FILTER -> 
                "Nie odpowiadaj na spam"
            
            ResponseType.CUSTOM -> 
                rule?.templateId?.let { responseTemplates[it] } ?: "Napisz profesjonalną odpowiedź"
        }
        
        return """
            $instruction
            
            Oryginalny email:
            Od: ${email.from}
            Temat: ${email.subject}
            Treść: ${email.body}
            
            Wygeneruj TYLKO treść odpowiedzi, bez tematu i nagłówków.
            Bądź naturalny, profesjonalny, krótki (2-3 akapity).
            W języku polskim.
        """.trimIndent()
    }
    
    /**
     * Wygeneruj z szablonu offline
     */
    private fun generateFromTemplate(email: EmailToRespond, type: ResponseType): String {
        return when (type) {
            ResponseType.ACKNOWLEDGE -> 
                """Dziękuję za Twoją wiadomość. Potwierdzam otrzymanie. 
                   Odpowiemy niedługo.
                   Pozdrawiam"""
            
            ResponseType.QUESTION_ANSWER ->
                """Dziękuję za pytanie. 
                   Przepraszamy, ale potrzebujemy więcej czasu na udzielenie odpowiedzi.
                   Wkrótce się do Ciebie odezwiemy.
                   Pozdrawiam"""
            
            ResponseType.BUSINESS_PROPOSAL ->
                """Dziękuję za zainteresowanie współpracą. 
                   Twoja propozycja nas interesuje. Przeanalizujemy ją i wrócimy do Ciebie.
                   Pozdrawiam"""
            
            ResponseType.COMPLAINT_RESOLUTION ->
                """Przepraszamy za problem. 
                   Twoja skarga jest dla nas ważna. Zajmiemy się tym priorytetowo.
                   Pozdrawiam"""
            
            else -> "Dziękuję za wiadomość. Pozdrawiam"
        }
    }
    
    /**
     * Oblicz pewność odpowiedzi
     */
    private fun calculateConfidence(email: EmailToRespond, response: String): Float {
        // Proste heurystyki
        var confidence = 0.8f
        
        // Jeśli response jest pełny - +0.1
        if (response.length > 100) confidence += 0.1f
        
        // Jeśli temat to business - mogą być więcej wątpliwości
        if (email.subject.lowercase().contains("proposal")) confidence -= 0.05f
        
        return minOf(confidence, 1.0f)
    }
    
    /**
     * Dodaj/edytuj regułę
     */
    fun addRule(rule: AutoResponderRule) {
        rules.removeIf { it.id == rule.id }
        rules.add(rule)
        saveRules()
    }
    
    /**
     * Usuń regułę
     */
    fun removeRule(ruleId: String) {
        rules.removeIf { it.id == ruleId }
        saveRules()
    }
    
    /**
     * Załaduj reguły
     */
    private fun loadRules() {
        try {
            val json = prefs.getString("rules", null) ?: return
            val arr = org.json.JSONArray(json)
            rules.clear()
            for (i in 0 until arr.length()) {
                val ruleJson = arr.getJSONObject(i)
                // Parse rule (uprościone)
                val rule = AutoResponderRule(
                    id = ruleJson.getString("id"),
                    name = ruleJson.getString("name"),
                    enabled = ruleJson.getBoolean("enabled")
                )
                rules.add(rule)
            }
        } catch (e: Exception) {
            // Defaults
            rules = mutableListOf(
                AutoResponderRule(
                    name = "Newsletter - Automatyczne odsubskrybowanie",
                    triggers = listOf("unsubscribe", "newsletter"),
                    responseType = ResponseType.NEWSLETTER_OPT_OUT,
                    autoSend = true,
                    requiresApproval = false,
                    priority = 100
                ),
                AutoResponderRule(
                    name = "Spam - Ignoruj",
                    responseType = ResponseType.SPAM_FILTER,
                    autoSend = true,
                    requiresApproval = false,
                    priority = 90
                ),
                AutoResponderRule(
                    name = "Business - Wymagaj zatwierdzenia",
                    triggers = listOf("proposal", "collaboration"),
                    responseType = ResponseType.BUSINESS_PROPOSAL,
                    autoSend = false,
                    requiresApproval = true,
                    priority = 70
                )
            )
        }
    }
    
    /**
     * Zapisz reguły
     */
    private fun saveRules() {
        try {
            val arr = org.json.JSONArray()
            rules.forEach { rule ->
                arr.put(JSONObject().apply {
                    put("id", rule.id)
                    put("name", rule.name)
                    put("enabled", rule.enabled)
                    put("priority", rule.priority)
                    put("responseType", rule.responseType.name)
                })
            }
            prefs.edit().putString("rules", arr.toString()).apply()
        } catch (e: Exception) {
            // Silent fail
        }
    }
    
    /**
     * Załaduj szablony
     */
    private fun loadTemplates() {
        responseTemplates = mutableMapOf(
            "formal" to """Szanowny Panie / Pani,

Dziękuję za Twoją wiadomość. 

[TREŚĆ]

Z poważaniem,
[IMIĘ]""",
            
            "informal" to """Cześć!

Dziękuję za wiadomość.

[TREŚĆ]

Pozdrawiam,
[IMIĘ]""",
            
            "business" to """Dzień dobry,

Dziękuję za zainteresowanie.

[TREŚĆ]

Czekam na odpowiedź.

Z poważaniem,
[IMIĘ]"""
        )
    }
    
    /**
     * Lista wszystkich reguł
     */
    fun getRules(): List<AutoResponderRule> = rules.toList()
    
    /**
     * Włącz/wyłącz regułę
     */
    fun toggleRule(ruleId: String, enabled: Boolean) {
        rules.find { it.id == ruleId }?.let { rule ->
            val updated = rule.copy(enabled = enabled)
            rules[rules.indexOf(rule)] = updated
            saveRules()
        }
    }
}
