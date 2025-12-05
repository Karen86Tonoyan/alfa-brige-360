package com.alfa.mail.email

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Properties
import javax.mail.*
import javax.mail.internet.InternetAddress
import javax.mail.internet.MimeMessage
import javax.mail.internet.MimeBodyPart
import javax.mail.internet.MimeMultipart

/**
 * 📧 ALFA EMAIL SERVICE
 * 
 * Prawdziwe wysyłanie emaili przez SMTP
 * Zintegrowane z CERBER (szum online, prawda offline)
 */
class EmailService private constructor(private val context: Context) {
    
    data class EmailConfig(
        val smtpHost: String = "smtp.gmail.com",
        val smtpPort: Int = 587,
        val username: String = "",
        val password: String = "",
        val senderEmail: String = "",
        val senderName: String = "ALFA Mail",
        val useTls: Boolean = true
    )
    
    data class Email(
        val to: List<String>,
        val cc: List<String> = emptyList(),
        val bcc: List<String> = emptyList(),
        val subject: String,
        val body: String,
        val isHtml: Boolean = false,
        val attachments: List<AttachmentData> = emptyList()
    )
    
    data class AttachmentData(
        val filename: String,
        val data: ByteArray,
        val mimeType: String = "application/octet-stream"
    )
    
    sealed class SendResult {
        data class Success(val messageId: String) : SendResult()
        data class Error(val message: String, val exception: Throwable? = null) : SendResult()
        object Queued : SendResult()  // Offline - zapisano do kolejki
    }
    
    private var config: EmailConfig? = null
    private val pendingEmails = mutableListOf<Email>()
    
    companion object {
        @Volatile
        private var instance: EmailService? = null
        
        fun getInstance(context: Context): EmailService {
            return instance ?: synchronized(this) {
                instance ?: EmailService(context.applicationContext).also { instance = it }
            }
        }
    }
    
    /**
     * Konfiguruj SMTP
     */
    fun configure(config: EmailConfig) {
        this.config = config
    }
    
    /**
     * Konfiguruj z SecureStorage
     */
    suspend fun configureFromSecureStorage(): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val prefs = context.getSharedPreferences("alfa_mail_config", Context.MODE_PRIVATE)
                val host = prefs.getString("smtp_host", null) ?: return@withContext false
                val port = prefs.getInt("smtp_port", 587)
                val username = prefs.getString("smtp_username", null) ?: return@withContext false
                val password = prefs.getString("smtp_password", null) ?: return@withContext false
                val senderEmail = prefs.getString("sender_email", username) ?: username
                val senderName = prefs.getString("sender_name", "ALFA Mail") ?: "ALFA Mail"
                
                config = EmailConfig(
                    smtpHost = host,
                    smtpPort = port,
                    username = username,
                    password = password,
                    senderEmail = senderEmail,
                    senderName = senderName
                )
                true
            } catch (e: Exception) {
                false
            }
        }
    }
    
    /**
     * Zapisz konfigurację do SecureStorage
     */
    suspend fun saveConfig(newConfig: EmailConfig): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val prefs = context.getSharedPreferences("alfa_mail_config", Context.MODE_PRIVATE)
                prefs.edit().apply {
                    putString("smtp_host", newConfig.smtpHost)
                    putInt("smtp_port", newConfig.smtpPort)
                    putString("smtp_username", newConfig.username)
                    putString("smtp_password", newConfig.password)
                    putString("sender_email", newConfig.senderEmail)
                    putString("sender_name", newConfig.senderName)
                    apply()
                }
                config = newConfig
                true
            } catch (e: Exception) {
                false
            }
        }
    }
    
    /**
     * Wyślij email
     */
    suspend fun send(email: Email): SendResult {
        val cfg = config ?: return SendResult.Error("Email not configured. Call configure() first.")
        
        return withContext(Dispatchers.IO) {
            try {
                // Sprawdź czy mamy internet
                if (!isOnline()) {
                    // Zapisz do kolejki offline
                    pendingEmails.add(email)
                    return@withContext SendResult.Queued
                }
                
                val props = Properties().apply {
                    put("mail.smtp.auth", "true")
                    put("mail.smtp.host", cfg.smtpHost)
                    put("mail.smtp.port", cfg.smtpPort.toString())
                    
                    if (cfg.useTls) {
                        put("mail.smtp.starttls.enable", "true")
                    }
                    
                    // Timeout
                    put("mail.smtp.connectiontimeout", "10000")
                    put("mail.smtp.timeout", "10000")
                }
                
                val session = Session.getInstance(props, object : Authenticator() {
                    override fun getPasswordAuthentication(): PasswordAuthentication {
                        return PasswordAuthentication(cfg.username, cfg.password)
                    }
                })
                
                val message = MimeMessage(session).apply {
                    setFrom(InternetAddress(cfg.senderEmail, cfg.senderName))
                    
                    // To
                    email.to.forEach { recipient ->
                        addRecipient(Message.RecipientType.TO, InternetAddress(recipient))
                    }
                    
                    // CC
                    email.cc.forEach { recipient ->
                        addRecipient(Message.RecipientType.CC, InternetAddress(recipient))
                    }
                    
                    // BCC
                    email.bcc.forEach { recipient ->
                        addRecipient(Message.RecipientType.BCC, InternetAddress(recipient))
                    }
                    
                    subject = email.subject
                    
                    if (email.attachments.isEmpty()) {
                        // Prosty email
                        if (email.isHtml) {
                            setContent(email.body, "text/html; charset=utf-8")
                        } else {
                            setText(email.body, "utf-8")
                        }
                    } else {
                        // Email z załącznikami
                        val multipart = MimeMultipart()
                        
                        // Body
                        val bodyPart = MimeBodyPart().apply {
                            if (email.isHtml) {
                                setContent(email.body, "text/html; charset=utf-8")
                            } else {
                                setText(email.body, "utf-8")
                            }
                        }
                        multipart.addBodyPart(bodyPart)
                        
                        // Attachments
                        email.attachments.forEach { attachment ->
                            val attachPart = MimeBodyPart().apply {
                                setContent(attachment.data, attachment.mimeType)
                                fileName = attachment.filename
                            }
                            multipart.addBodyPart(attachPart)
                        }
                        
                        setContent(multipart)
                    }
                }
                
                Transport.send(message)
                
                SendResult.Success(message.messageID ?: "sent_${System.currentTimeMillis()}")
                
            } catch (e: AuthenticationFailedException) {
                SendResult.Error("Authentication failed. Check username/password.", e)
            } catch (e: MessagingException) {
                SendResult.Error("Failed to send email: ${e.message}", e)
            } catch (e: Exception) {
                SendResult.Error("Unexpected error: ${e.message}", e)
            }
        }
    }
    
    /**
     * Wyślij prosty email (helper)
     */
    suspend fun sendSimple(
        to: String,
        subject: String,
        body: String,
        cc: String? = null
    ): SendResult {
        val recipients = to.split(",", ";").map { it.trim() }.filter { it.isNotEmpty() }
        val ccList = cc?.split(",", ";")?.map { it.trim() }?.filter { it.isNotEmpty() } ?: emptyList()
        
        return send(Email(
            to = recipients,
            cc = ccList,
            subject = subject,
            body = body
        ))
    }
    
    /**
     * Wyślij oczekujące emaile (po powrocie online)
     */
    suspend fun sendPending(): List<SendResult> {
        if (!isOnline() || pendingEmails.isEmpty()) {
            return emptyList()
        }
        
        val results = mutableListOf<SendResult>()
        val emailsToSend = pendingEmails.toList()
        pendingEmails.clear()
        
        emailsToSend.forEach { email ->
            val result = send(email)
            results.add(result)
            
            // Jeśli nadal offline, przerwij
            if (result is SendResult.Queued) {
                pendingEmails.addAll(emailsToSend.drop(results.size))
                return results
            }
        }
        
        return results
    }
    
    /**
     * Ile emaili czeka?
     */
    fun pendingCount(): Int = pendingEmails.size
    
    /**
     * Sprawdź połączenie
     */
    private fun isOnline(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val capabilities = cm.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
    
    /**
     * Test połączenia SMTP
     */
    suspend fun testConnection(): SendResult {
        val cfg = config ?: return SendResult.Error("Not configured")
        
        return withContext(Dispatchers.IO) {
            try {
                val props = Properties().apply {
                    put("mail.smtp.auth", "true")
                    put("mail.smtp.host", cfg.smtpHost)
                    put("mail.smtp.port", cfg.smtpPort.toString())
                    put("mail.smtp.starttls.enable", cfg.useTls.toString())
                    put("mail.smtp.connectiontimeout", "5000")
                    put("mail.smtp.timeout", "5000")
                }
                
                val session = Session.getInstance(props, object : Authenticator() {
                    override fun getPasswordAuthentication(): PasswordAuthentication {
                        return PasswordAuthentication(cfg.username, cfg.password)
                    }
                })
                
                val transport = session.getTransport("smtp")
                transport.connect()
                transport.close()
                
                SendResult.Success("Connection OK")
            } catch (e: Exception) {
                SendResult.Error("Connection failed: ${e.message}", e)
            }
        }
    }
}
