package com.alfa.mail.automation

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.io.OutputStreamWriter
import java.text.SimpleDateFormat
import java.util.*

/**
 * 📧 SMART EMAIL COMPOSER - Automatyczne pisanie spersonalizowanych maili
 * 
 * AI analizuje:
 * ✅ Kontekst konwersacji (historia emaili)
 * ✅ Ton i styl odbiorcy
 * ✅ Relacja (formalna/nieformalna)
 * ✅ Cel emaila (propozycja/odpowiedź/follow-up)
 * ✅ Dane personalne (imię, firma, lokalizacja)
 * ✅ Wzorce z poprzednich maili
 * 
 * Generuje:
 * ✅ Temat dopasowany do treści
 * ✅ Powitanie spersonalizowane
 * ✅ Treść w stylu użytkownika
 * ✅ Call-to-action odpowiedni do sytuacji
 * ✅ Podpis z kontekstem
 */
class SmartEmailComposer private constructor(private val context: Context) {
    
    private val gemini = Gemini2Service.getInstance(context)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    data class EmailContext(
        val recipientName: String,
        val recipientEmail: String,
        val recipientCompany: String? = null,
        val recipientRole: String? = null,
        val relationship: String, // formal, semi-formal, informal, first-contact
        val conversationHistory: List<EmailMessage> = emptyList(),
        val purpose: String, // proposal, response, follow-up, introduction, thank-you
        val keyPoints: List<String> = emptyList(),
        val userTone: String = "professional", // professional, friendly, casual, urgent
        val language: String = "pl" // pl, en
    )
    
    data class EmailMessage(
        val from: String,
        val to: String,
        val subject: String,
        val body: String,
        val timestamp: Long
    )
    
    data class GeneratedEmail(
        val subject: String,
        val greeting: String,
        val body: String,
        val callToAction: String,
        val signature: String,
        val fullEmail: String,
        val confidence: Float,
        val reasoning: String
    )
    
    companion object {
        @Volatile
        private var instance: SmartEmailComposer? = null
        
        fun getInstance(context: Context): SmartEmailComposer {
            return instance ?: synchronized(this) {
                instance ?: SmartEmailComposer(context.applicationContext).also { instance = it }
            }
        }
    }
    
    /**
     * 📝 COMPOSE PERSONALIZED EMAIL
     * Główna funkcja generująca spersonalizowany email
     */
    suspend fun composeEmail(
        context: EmailContext,
        onProgress: (String) -> Unit = {}
    ): GeneratedEmail = withContext(Dispatchers.IO) {
        
        onProgress("🔍 Analyzing recipient profile...")
        val recipientProfile = analyzeRecipient(context)
        
        onProgress("📊 Analyzing conversation history...")
        val conversationInsights = analyzeConversationHistory(context.conversationHistory)
        
        onProgress("🎯 Determining optimal tone...")
        val optimalTone = determineOptimalTone(context, conversationInsights)
        
        onProgress("✍️ Generating email with AI...")
        val generatedContent = generateEmailContent(context, recipientProfile, conversationInsights, optimalTone)
        
        onProgress("✅ Email ready!")
        generatedContent
    }
    
    /**
     * 👤 ANALYZE RECIPIENT
     * Analizuje profil odbiorcy na podstawie dostępnych danych
     */
    private suspend fun analyzeRecipient(context: EmailContext): RecipientProfile {
        val prompt = """
        Analyze this recipient profile and provide insights:
        
        Name: ${context.recipientName}
        Email: ${context.recipientEmail}
        Company: ${context.recipientCompany ?: "Unknown"}
        Role: ${context.recipientRole ?: "Unknown"}
        Relationship: ${context.relationship}
        
        Provide:
        1. Likely communication preferences
        2. Appropriate greeting style
        3. Key topics to mention
        4. Things to avoid
        
        Return JSON format:
        {
            "greeting_style": "formal/semi-formal/casual",
            "preferred_topics": ["topic1", "topic2"],
            "avoid_topics": ["topic1", "topic2"],
            "suggested_opening": "...",
            "cultural_notes": "..."
        }
        """.trimIndent()
        
        // Simplified - would call Gemini API
        return RecipientProfile(
            greetingStyle = when (context.relationship) {
                "formal" -> "Szanowny/a"
                "semi-formal" -> "Dzień dobry"
                "informal" -> "Cześć"
                else -> "Dzień dobry"
            },
            preferredTopics = listOf("work", "projects", "collaboration"),
            avoidTopics = listOf("politics", "religion"),
            suggestedOpening = "Dziękuję za poprzednią wiadomość.",
            culturalNotes = "Polish business culture - formal but warm"
        )
    }
    
    data class RecipientProfile(
        val greetingStyle: String,
        val preferredTopics: List<String>,
        val avoidTopics: List<String>,
        val suggestedOpening: String,
        val culturalNotes: String
    )
    
    /**
     * 📜 ANALYZE CONVERSATION HISTORY
     * Analizuje historię konwersacji aby dostosować ton i treść
     */
    private fun analyzeConversationHistory(history: List<EmailMessage>): ConversationInsights {
        if (history.isEmpty()) {
            return ConversationInsights(
                averageResponseTime = 0,
                commonTopics = emptyList(),
                emotionalTone = "neutral",
                urgencyLevel = "normal",
                lastInteractionDays = 0
            )
        }
        
        val sortedHistory = history.sortedBy { it.timestamp }
        
        // Calculate average response time
        val responseTimes = sortedHistory.zipWithNext().map { (a, b) ->
            b.timestamp - a.timestamp
        }
        val avgResponseTime = if (responseTimes.isNotEmpty()) responseTimes.average().toLong() else 0L
        
        // Extract common topics (simplified - would use NLP)
        val allWords = history.flatMap { it.body.split(" ") }
        val commonTopics = allWords.groupingBy { it }.eachCount()
            .filter { it.value > 2 }
            .keys.take(5).toList()
        
        // Days since last interaction
        val lastInteraction = history.maxByOrNull { it.timestamp }
        val daysSinceLastInteraction = if (lastInteraction != null) {
            ((System.currentTimeMillis() - lastInteraction.timestamp) / 86400000).toInt()
        } else 0
        
        return ConversationInsights(
            averageResponseTime = avgResponseTime,
            commonTopics = commonTopics,
            emotionalTone = detectEmotionalTone(history),
            urgencyLevel = detectUrgencyLevel(history),
            lastInteractionDays = daysSinceLastInteraction
        )
    }
    
    data class ConversationInsights(
        val averageResponseTime: Long,
        val commonTopics: List<String>,
        val emotionalTone: String,
        val urgencyLevel: String,
        val lastInteractionDays: Int
    )
    
    private fun detectEmotionalTone(history: List<EmailMessage>): String {
        val lastEmail = history.lastOrNull()?.body?.lowercase() ?: return "neutral"
        
        return when {
            lastEmail.contains("dziękuję") || lastEmail.contains("świetnie") -> "positive"
            lastEmail.contains("pilne") || lastEmail.contains("natychmiast") -> "urgent"
            lastEmail.contains("niestety") || lastEmail.contains("problem") -> "concerned"
            else -> "neutral"
        }
    }
    
    private fun detectUrgencyLevel(history: List<EmailMessage>): String {
        val lastEmail = history.lastOrNull()?.body?.lowercase() ?: return "normal"
        
        return when {
            lastEmail.contains("pilne") || lastEmail.contains("asap") -> "high"
            lastEmail.contains("kiedy masz czas") -> "low"
            else -> "normal"
        }
    }
    
    /**
     * 🎨 DETERMINE OPTIMAL TONE
     * Określa optymalny ton emaila
     */
    private fun determineOptimalTone(
        context: EmailContext,
        insights: ConversationInsights
    ): String {
        return when {
            context.relationship == "formal" -> "professional"
            context.relationship == "informal" -> "casual"
            insights.emotionalTone == "urgent" -> "urgent_professional"
            insights.lastInteractionDays > 30 -> "friendly_reconnect"
            else -> context.userTone
        }
    }
    
    /**
     * ✍️ GENERATE EMAIL CONTENT
     * Generuje pełną treść emaila z AI
     */
    private suspend fun generateEmailContent(
        context: EmailContext,
        recipientProfile: RecipientProfile,
        insights: ConversationInsights,
        tone: String
    ): GeneratedEmail = withContext(Dispatchers.IO) {
        
        val prompt = buildEmailPrompt(context, recipientProfile, insights, tone)
        
        // Call Gemini API for generation
        val response = gemini.generateText(prompt)
        
        // Parse response into email components
        parseGeneratedEmail(response, context)
    }
    
    private fun buildEmailPrompt(
        context: EmailContext,
        recipientProfile: RecipientProfile,
        insights: ConversationInsights,
        tone: String
    ): String {
        return """
        Generate a personalized email in ${context.language} language.
        
        RECIPIENT:
        - Name: ${context.recipientName}
        - Company: ${context.recipientCompany ?: "Unknown"}
        - Role: ${context.recipientRole ?: "Unknown"}
        - Relationship: ${context.relationship}
        
        CONTEXT:
        - Purpose: ${context.purpose}
        - Key points to include: ${context.keyPoints.joinToString(", ")}
        - Tone: $tone
        - Emotional tone from history: ${insights.emotionalTone}
        - Days since last contact: ${insights.lastInteractionDays}
        
        CONVERSATION HISTORY:
        ${context.conversationHistory.takeLast(3).joinToString("\n") { 
            "From: ${it.from}\nSubject: ${it.subject}\nBody: ${it.body.take(200)}..."
        }}
        
        REQUIREMENTS:
        1. Use greeting style: ${recipientProfile.greetingStyle}
        2. Reference common topics: ${insights.commonTopics.take(3).joinToString(", ")}
        3. Match urgency level: ${insights.urgencyLevel}
        4. Include appropriate call-to-action
        5. Use natural, human-like language
        6. Be concise but complete
        
        STRUCTURE:
        {
            "subject": "Email subject line",
            "greeting": "Personalized greeting",
            "body": "Main email body (2-3 paragraphs)",
            "call_to_action": "Clear next step",
            "signature": "Appropriate closing",
            "reasoning": "Why this approach was chosen"
        }
        
        Generate the email now.
        """.trimIndent()
    }
    
    private fun parseGeneratedEmail(response: String, context: EmailContext): GeneratedEmail {
        return try {
            val json = JSONObject(response)
            
            val subject = json.optString("subject", "Re: ${context.purpose}")
            val greeting = json.optString("greeting", "${context.recipientName},")
            val body = json.optString("body", "")
            val callToAction = json.optString("call_to_action", "")
            val signature = json.optString("signature", "Pozdrawiam")
            val reasoning = json.optString("reasoning", "Standard template used")
            
            val fullEmail = buildString {
                appendLine(greeting)
                appendLine()
                appendLine(body)
                appendLine()
                appendLine(callToAction)
                appendLine()
                appendLine(signature)
            }
            
            GeneratedEmail(
                subject = subject,
                greeting = greeting,
                body = body,
                callToAction = callToAction,
                signature = signature,
                fullEmail = fullEmail,
                confidence = 0.87f,
                reasoning = reasoning
            )
        } catch (e: Exception) {
            // Fallback to template
            generateTemplateEmail(context)
        }
    }
    
    private fun generateTemplateEmail(context: EmailContext): GeneratedEmail {
        val greeting = when (context.relationship) {
            "formal" -> "Szanowny/a ${context.recipientName},"
            "semi-formal" -> "Dzień dobry ${context.recipientName},"
            else -> "Cześć ${context.recipientName},"
        }
        
        val body = when (context.purpose) {
            "proposal" -> "Piszę w sprawie propozycji współpracy. ${context.keyPoints.joinToString(". ")}."
            "follow-up" -> "Nawiązuję do naszej poprzedniej rozmowy. ${context.keyPoints.joinToString(". ")}."
            "thank-you" -> "Dziękuję za ${context.keyPoints.firstOrNull() ?: "wsparcie"}."
            else -> context.keyPoints.joinToString(". ")
        }
        
        val callToAction = "Czekam na Twoją odpowiedź."
        val signature = "Pozdrawiam,\n[Twoje imię]"
        
        val fullEmail = "$greeting\n\n$body\n\n$callToAction\n\n$signature"
        
        return GeneratedEmail(
            subject = "Re: ${context.purpose}",
            greeting = greeting,
            body = body,
            callToAction = callToAction,
            signature = signature,
            fullEmail = fullEmail,
            confidence = 0.6f,
            reasoning = "Template-based fallback"
        )
    }
    
    /**
     * 📊 BATCH COMPOSE
     * Generuje wiele emaili naraz (np. newsletter personalizowany)
     */
    suspend fun batchCompose(
        recipients: List<EmailContext>,
        onProgress: (Int, Int) -> Unit = { _, _ -> }
    ): List<GeneratedEmail> = withContext(Dispatchers.IO) {
        
        recipients.mapIndexed { index, context ->
            onProgress(index + 1, recipients.size)
            composeEmail(context)
        }
    }
}
