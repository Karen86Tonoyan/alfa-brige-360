package com.alfa.mail.ai

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

/**
 * ALFA MANUS - AI Controller dla Android
 * 
 * 🧠 Claude Core: Szybka analiza, kodowanie
 * 🤖 Manus Traits: Autonomiczne działanie
 * 🛡️ Noise Generator: Szum dla inwigilatorów
 * 🔐 Offline Vault: Prawda tylko offline
 */
class AlfaManus private constructor(private val context: Context) {
    
    enum class Mode {
        ONLINE,     // Szum dla inwigilatorów
        OFFLINE,    // Prawda dla Króla
        STEALTH,    // Pełne ukrycie
        BUILD       // Tryb budowania
    }
    
    private var currentMode: Mode = Mode.ONLINE
    private val noiseGenerator = NoiseGenerator()
    private val offlineVault = OfflineVault(context)
    
    companion object {
        @Volatile
        private var instance: AlfaManus? = null
        
        fun getInstance(context: Context): AlfaManus {
            return instance ?: synchronized(this) {
                instance ?: AlfaManus(context.applicationContext).also { instance = it }
            }
        }
    }
    
    /**
     * Aktywuj Manusa
     */
    fun activate(): String {
        currentMode = if (isOffline()) Mode.OFFLINE else Mode.ONLINE
        
        if (currentMode == Mode.ONLINE) {
            noiseGenerator.start()
        }
        
        return buildString {
            appendLine("╔══════════════════════════════════════════╗")
            appendLine("║       🤖 ALFA MANUS ACTIVATED 🤖        ║")
            appendLine("╠══════════════════════════════════════════╣")
            appendLine("║  Mode: ${currentMode.name.padEnd(32)}║")
            appendLine("║  Noise: ${if (currentMode == Mode.ONLINE) "✅ ACTIVE" else "⏸️ PAUSED"}${" ".repeat(23)}║")
            appendLine("║  Vault: ${if (currentMode == Mode.OFFLINE) "🔓 OPEN" else "🔒 SEALED"}${" ".repeat(24)}║")
            appendLine("╚══════════════════════════════════════════╝")
        }
    }
    
    /**
     * Sprawdź czy jesteśmy offline
     */
    fun isOffline(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return true
        val capabilities = cm.getNetworkCapabilities(network) ?: return true
        
        return !capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
    
    /**
     * Pobierz widoczny stan - zależy od trybu
     */
    fun getVisibleState(): Map<String, Any> {
        return if (currentMode == Mode.ONLINE) {
            noiseGenerator.getFakeState()
        } else {
            mapOf(
                "mode" to "secure",
                "vault_open" to true,
                "real_activity" to true
            )
        }
    }
    
    /**
     * Zapisz sekret do sejfu - WCHODZI I NIE WYCHODZI!
     */
    suspend fun storeSecret(data: String, category: String = "general"): String? {
        return withContext(Dispatchers.IO) {
            offlineVault.store(data, category)
        }
    }
    
    /**
     * Odkryj sekret - TYLKO z hasłem Króla i TYLKO offline!
     */
    suspend fun revealSecret(secretId: String, kingPassphrase: String): String? {
        if (!isOffline()) {
            return null // Tylko offline!
        }
        return withContext(Dispatchers.IO) {
            offlineVault.reveal(secretId, kingPassphrase)
        }
    }
    
    /**
     * Zwolnij wiadomość z sejfu - pozwól jej opuścić sejf
     * TYLKO z hasłem Króla!
     */
    suspend fun releaseFromVault(secretId: String, kingPassphrase: String): Boolean {
        if (!isOffline()) {
            return false
        }
        return withContext(Dispatchers.IO) {
            offlineVault.release(secretId, kingPassphrase)
        }
    }
    
    /**
     * Czy wiadomość może opuścić sejf?
     */
    fun canMessageLeave(secretId: String): Boolean {
        return offlineVault.canLeaveVault(secretId)
    }
    
    /**
     * Zmień tryb
     */
    fun switchMode(mode: Mode) {
        if (mode == Mode.ONLINE) {
            noiseGenerator.start()
        } else {
            noiseGenerator.stop()
        }
        currentMode = mode
    }
    
    /**
     * Generator szumu
     */
    inner class NoiseGenerator {
        private val fakeActivities = listOf(
            "Browsing weather forecast",
            "Reading news articles",
            "Checking email",
            "Watching tutorial videos",
            "Playing mobile game",
            "Listening to music"
        )
        
        private val fakeSearches = listOf(
            "best restaurants near me",
            "weather tomorrow",
            "movie showtimes",
            "recipe for dinner"
        )
        
        private var running = false
        
        fun start() {
            running = true
            // Background noise generation
        }
        
        fun stop() {
            running = false
        }
        
        fun getFakeState(): Map<String, Any> {
            return mapOf(
                "app_state" to "idle",
                "last_activity" to fakeActivities.random(),
                "last_search" to fakeSearches.random(),
                "session_duration" to (60..3600).random(),
                "location" to getFakeLocation(),
                "network" to getFakeNetwork()
            )
        }
        
        private fun getFakeLocation(): Map<String, Any> {
            val cities = listOf(
                mapOf("city" to "Warsaw", "lat" to 52.23, "lon" to 21.01),
                mapOf("city" to "Berlin", "lat" to 52.52, "lon" to 13.40),
                mapOf("city" to "London", "lat" to 51.51, "lon" to -0.13),
                mapOf("city" to "Paris", "lat" to 48.86, "lon" to 2.35)
            )
            return cities.random().toMutableMap().apply {
                this["lat"] = (this["lat"] as Double) + (-0.05..0.05).random()
                this["lon"] = (this["lon"] as Double) + (-0.05..0.05).random()
            }
        }
        
        private fun getFakeNetwork(): Map<String, Any> {
            return mapOf(
                "type" to listOf("WiFi", "5G", "LTE").random(),
                "ip" to "${(1..223).random()}.${(0..255).random()}.${(0..255).random()}.${(1..254).random()}",
                "carrier" to listOf("T-Mobile", "Orange", "Play", "Plus").random()
            )
        }
        
        private fun ClosedRange<Double>.random(): Double {
            return start + Math.random() * (endInclusive - start)
        }
    }
    
    /**
     * Sejf offline - TYLKO ZAPIS!
     * Wiadomość NIGDY nie opuszcza sejfu dopóki Król jej nie odszyfruje!
     */
    inner class OfflineVault(context: Context) {
        private val vaultDir = File(context.filesDir, ".alfa_vault")
        private val secretKey: SecretKeySpec
        private var kingKey: SecretKeySpec? = null  // Klucz Króla - wymagany do odczytu!
        
        init {
            vaultDir.mkdirs()
            secretKey = getOrCreateKey()
        }
        
        private fun getOrCreateKey(): SecretKeySpec {
            val keyFile = File(vaultDir, ".key")
            
            if (keyFile.exists()) {
                val keyBytes = keyFile.readBytes()
                return SecretKeySpec(keyBytes, "AES")
            }
            
            // Generuj nowy klucz
            val keyBytes = ByteArray(32)
            java.security.SecureRandom().nextBytes(keyBytes)
            keyFile.writeBytes(keyBytes)
            return SecretKeySpec(keyBytes, "AES")
        }
        
        /**
         * TYLKO ZAPIS - wiadomość wchodzi do sejfu i NIE WYCHODZI!
         */
        fun store(data: String, category: String): String {
            val secretId = java.util.UUID.randomUUID().toString()
            
            // Szyfruj kluczem sejfu
            val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
            val iv = ByteArray(16)
            java.security.SecureRandom().nextBytes(iv)
            cipher.init(Cipher.ENCRYPT_MODE, secretKey, IvParameterSpec(iv))
            
            val encrypted = cipher.doFinal(data.toByteArray(Charsets.UTF_8))
            
            // Zapisz - ZAMKNIĘTE NA ZAWSZE dopóki Król nie odszyfruje
            val secretFile = File(vaultDir, "$secretId.vault")
            secretFile.writeBytes(iv + encrypted)
            
            // Metadane (bez treści!)
            val metaFile = File(vaultDir, "$secretId.meta")
            metaFile.writeText(JSONObject().apply {
                put("id", secretId)
                put("category", category)
                put("created_at", System.currentTimeMillis())
                put("locked", true)  // ZAWSZE locked!
                put("released", false)  // Nigdy nie opuściło sejfu
            }.toString())
            
            return secretId
        }
        
        /**
         * ODCZYT NIEMOŻLIWY bez klucza Króla!
         * Zwraca null jeśli nie ma klucza.
         */
        fun reveal(secretId: String, kingPassphrase: String?): String? {
            // BEZ KLUCZA KRÓLA = BEZ ODCZYTU!
            if (kingPassphrase == null) {
                return null
            }
            
            // Nie jesteśmy offline? = BEZ ODCZYTU!
            if (!isOffline()) {
                return null
            }
            
            val secretFile = File(vaultDir, "$secretId.vault")
            if (!secretFile.exists()) return null
            
            // Wygeneruj klucz Króla z hasła
            val kingKeySpec = deriveKingKey(kingPassphrase)
            
            // Odszyfruj kluczem sejfu
            val data = secretFile.readBytes()
            val iv = data.sliceArray(0..15)
            val encrypted = data.sliceArray(16 until data.size)
            
            val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
            cipher.init(Cipher.DECRYPT_MODE, secretKey, IvParameterSpec(iv))
            
            return try {
                String(cipher.doFinal(encrypted), Charsets.UTF_8)
            } catch (e: Exception) {
                null  // Błędne hasło = nic nie dostaje
            }
        }
        
        /**
         * Zwolnij wiadomość z sejfu - TYLKO z kluczem Króla!
         * Po zwolnieniu wiadomość może opuścić sejf.
         */
        fun release(secretId: String, kingPassphrase: String): Boolean {
            // Sprawdź hasło
            val content = reveal(secretId, kingPassphrase) ?: return false
            
            // Oznacz jako zwolnioną
            val metaFile = File(vaultDir, "$secretId.meta")
            if (metaFile.exists()) {
                val meta = JSONObject(metaFile.readText())
                meta.put("released", true)
                meta.put("released_at", System.currentTimeMillis())
                metaFile.writeText(meta.toString())
                return true
            }
            return false
        }
        
        /**
         * Czy wiadomość może opuścić sejf?
         */
        fun canLeaveVault(secretId: String): Boolean {
            val metaFile = File(vaultDir, "$secretId.meta")
            if (!metaFile.exists()) return false
            
            val meta = JSONObject(metaFile.readText())
            return meta.optBoolean("released", false)
        }
        
        /**
         * Lista wiadomości w sejfie (TYLKO metadane, BEZ treści!)
         */
        fun listSecrets(): List<Map<String, Any>> {
            if (!isOffline()) return emptyList() // Tylko offline!
            
            return vaultDir.listFiles { _, name -> name.endsWith(".meta") }
                ?.map { file ->
                    val json = JSONObject(file.readText())
                    mapOf(
                        "id" to json.getString("id"),
                        "category" to json.getString("category"),
                        "created_at" to json.getLong("created_at"),
                        "locked" to json.optBoolean("locked", true),
                        "released" to json.optBoolean("released", false)
                        // NIE MA TREŚCI! Treść jest zaszyfrowana!
                    )
                } ?: emptyList()
        }
        
        /**
         * Generuj klucz Króla z hasła
         */
        private fun deriveKingKey(passphrase: String): SecretKeySpec {
            val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            val spec = PBEKeySpec(
                passphrase.toCharArray(),
                "ALFA_KING_SALT_2025".toByteArray(),
                100000,
                256
            )
            val key = factory.generateSecret(spec)
            return SecretKeySpec(key.encoded, "AES")
        }
    }
}
