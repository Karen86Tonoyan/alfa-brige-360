package com.alfa.mail.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.MessageDigest

/**
 * 🔐 DURESS PIN SYSTEM
 * 
 * PIN normalny = ODBLOKOWUJE (prawdziwe dane)
 * PIN odwrotny = BLOKUJE (fałszywe dane, alerty, ukrycie)
 * 
 * Przykład:
 * - Prawdziwy PIN: 1234
 * - Duress PIN: 4321 (odwrotność)
 * 
 * Gdy wpiszesz 4321:
 * - Aplikacja "odblokuje" się ale pokazuje FAŁSZYWE dane
 * - Prawdziwe dane są UKRYTE/USUNIĘTE
 * - Wysyła cichy alert (opcjonalnie)
 * - Wygląda normalnie dla obserwatora
 */
class DuressPin private constructor(private val context: Context) {
    
    enum class PinResult {
        CORRECT,        // Prawidłowy PIN - pokaż prawdziwe dane
        DURESS,         // PIN pod przymusem - pokaż fałszywe, ukryj prawdziwe
        INCORRECT,      // Błędny PIN
        LOCKED,         // Za dużo prób - zablokowane
        NOT_SET         // PIN nie ustawiony
    }
    
    data class VerifyResult(
        val result: PinResult,
        val attemptsLeft: Int = 5,
        val message: String = ""
    )
    
    private val prefs: SharedPreferences by lazy {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            
            EncryptedSharedPreferences.create(
                context,
                "alfa_duress_pin",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            // Fallback do zwykłych prefs (mniej bezpieczne)
            context.getSharedPreferences("alfa_duress_pin_fallback", Context.MODE_PRIVATE)
        }
    }
    
    companion object {
        private const val KEY_PIN_HASH = "pin_hash"
        private const val KEY_DURESS_ENABLED = "duress_enabled"
        private const val KEY_ATTEMPTS = "attempts"
        private const val KEY_LOCK_UNTIL = "lock_until"
        private const val KEY_DURESS_ACTION = "duress_action"
        private const val KEY_SILENT_ALERT = "silent_alert"
        
        private const val MAX_ATTEMPTS = 5
        private const val LOCK_DURATION_MS = 5 * 60 * 1000L // 5 minut
        
        @Volatile
        private var instance: DuressPin? = null
        
        fun getInstance(context: Context): DuressPin {
            return instance ?: synchronized(this) {
                instance ?: DuressPin(context.applicationContext).also { instance = it }
            }
        }
    }
    
    /**
     * Sprawdź czy PIN jest ustawiony
     */
    fun isPinSet(): Boolean {
        return prefs.contains(KEY_PIN_HASH)
    }
    
    /**
     * Ustaw PIN
     */
    fun setPin(pin: String, enableDuress: Boolean = true): Boolean {
        if (pin.length < 4) return false
        
        val pinHash = hashPin(pin)
        prefs.edit().apply {
            putString(KEY_PIN_HASH, pinHash)
            putBoolean(KEY_DURESS_ENABLED, enableDuress)
            putInt(KEY_ATTEMPTS, 0)
            apply()
        }
        return true
    }
    
    /**
     * Zmień PIN
     */
    fun changePin(oldPin: String, newPin: String): Boolean {
        val result = verifyPin(oldPin)
        if (result.result != PinResult.CORRECT) return false
        
        return setPin(newPin, prefs.getBoolean(KEY_DURESS_ENABLED, true))
    }
    
    /**
     * Zweryfikuj PIN
     * 
     * Zwraca:
     * - CORRECT jeśli PIN prawidłowy
     * - DURESS jeśli PIN odwrotny (przymus)
     * - INCORRECT jeśli błędny
     * - LOCKED jeśli za dużo prób
     */
    fun verifyPin(enteredPin: String): VerifyResult {
        // Sprawdź czy nie zablokowany
        val lockUntil = prefs.getLong(KEY_LOCK_UNTIL, 0)
        if (System.currentTimeMillis() < lockUntil) {
            val remainingSeconds = (lockUntil - System.currentTimeMillis()) / 1000
            return VerifyResult(
                PinResult.LOCKED,
                0,
                "Zablokowane. Spróbuj za ${remainingSeconds}s"
            )
        }
        
        // Sprawdź czy PIN ustawiony
        val storedHash = prefs.getString(KEY_PIN_HASH, null)
            ?: return VerifyResult(PinResult.NOT_SET, MAX_ATTEMPTS, "PIN nie ustawiony")
        
        val enteredHash = hashPin(enteredPin)
        val duressEnabled = prefs.getBoolean(KEY_DURESS_ENABLED, true)
        
        // Sprawdź prawidłowy PIN
        if (enteredHash == storedHash) {
            // Reset prób
            prefs.edit().putInt(KEY_ATTEMPTS, 0).apply()
            return VerifyResult(PinResult.CORRECT, MAX_ATTEMPTS, "Odblokowano")
        }
        
        // Sprawdź duress PIN (odwrotność)
        if (duressEnabled) {
            val reversedPin = enteredPin.reversed()
            val reversedHash = hashPin(reversedPin)
            
            if (reversedHash == storedHash) {
                // DURESS! Ktoś zmusza użytkownika
                handleDuress()
                return VerifyResult(
                    PinResult.DURESS,
                    MAX_ATTEMPTS,
                    "Tryb bezpieczeństwa aktywowany"
                )
            }
        }
        
        // Błędny PIN
        val attempts = prefs.getInt(KEY_ATTEMPTS, 0) + 1
        prefs.edit().putInt(KEY_ATTEMPTS, attempts).apply()
        
        if (attempts >= MAX_ATTEMPTS) {
            // Zablokuj
            prefs.edit()
                .putLong(KEY_LOCK_UNTIL, System.currentTimeMillis() + LOCK_DURATION_MS)
                .putInt(KEY_ATTEMPTS, 0)
                .apply()
            
            return VerifyResult(
                PinResult.LOCKED,
                0,
                "Za dużo prób. Zablokowano na 5 minut."
            )
        }
        
        return VerifyResult(
            PinResult.INCORRECT,
            MAX_ATTEMPTS - attempts,
            "Błędny PIN. Pozostało prób: ${MAX_ATTEMPTS - attempts}"
        )
    }
    
    /**
     * Obsłuż sytuację przymusu (duress)
     */
    private fun handleDuress() {
        val action = prefs.getString(KEY_DURESS_ACTION, "hide") ?: "hide"
        
        when (action) {
            "hide" -> {
                // Ukryj prawdziwe dane, pokaż fałszywe
                activateDuressMode()
            }
            "wipe" -> {
                // Wyczyść wrażliwe dane
                wipeSecretData()
            }
            "alert" -> {
                // Wyślij cichy alert
                sendSilentAlert()
            }
            "all" -> {
                activateDuressMode()
                sendSilentAlert()
            }
        }
    }
    
    /**
     * Aktywuj tryb duress - ukryj prawdziwe dane
     */
    private fun activateDuressMode() {
        val duressPrefs = context.getSharedPreferences("alfa_duress_state", Context.MODE_PRIVATE)
        duressPrefs.edit().apply {
            putBoolean("duress_active", true)
            putLong("duress_activated_at", System.currentTimeMillis())
            apply()
        }
    }
    
    /**
     * Czy tryb duress jest aktywny?
     */
    fun isDuressActive(): Boolean {
        val duressPrefs = context.getSharedPreferences("alfa_duress_state", Context.MODE_PRIVATE)
        return duressPrefs.getBoolean("duress_active", false)
    }
    
    /**
     * Dezaktywuj tryb duress (tylko z prawdziwym PIN + specjalna sekwencja)
     */
    fun deactivateDuress(pin: String, secretCode: String = "ALFA"): Boolean {
        val result = verifyPin(pin)
        if (result.result != PinResult.CORRECT) return false
        if (secretCode != "ALFA") return false
        
        val duressPrefs = context.getSharedPreferences("alfa_duress_state", Context.MODE_PRIVATE)
        duressPrefs.edit().putBoolean("duress_active", false).apply()
        return true
    }
    
    /**
     * Wyczyść wrażliwe dane
     */
    private fun wipeSecretData() {
        // Wyczyść vault
        val vaultDir = java.io.File(context.filesDir, "vault")
        vaultDir.deleteRecursively()
        
        // Wyczyść klucze
        val keysPrefs = context.getSharedPreferences("alfa_keys", Context.MODE_PRIVATE)
        keysPrefs.edit().clear().apply()
        
        // Wyczyść drafty
        val draftsPrefs = context.getSharedPreferences("alfa_drafts", Context.MODE_PRIVATE)
        draftsPrefs.edit().clear().apply()
    }
    
    /**
     * Wyślij cichy alert
     */
    private fun sendSilentAlert() {
        if (!prefs.getBoolean(KEY_SILENT_ALERT, false)) return
        
        // TODO: Wyślij SMS/email do zaufanego kontaktu
        // TODO: Zapisz lokalizację
        // TODO: Zrób zdjęcie frontem (dyskretnie)
        
        val alertPrefs = context.getSharedPreferences("alfa_alerts", Context.MODE_PRIVATE)
        alertPrefs.edit().apply {
            putLong("last_duress_alert", System.currentTimeMillis())
            putInt("duress_count", alertPrefs.getInt("duress_count", 0) + 1)
            apply()
        }
    }
    
    /**
     * Skonfiguruj akcję duress
     */
    fun setDuressAction(action: String) {
        prefs.edit().putString(KEY_DURESS_ACTION, action).apply()
    }
    
    /**
     * Włącz/wyłącz cichy alert
     */
    fun setSilentAlert(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_SILENT_ALERT, enabled).apply()
    }
    
    /**
     * Hash PIN
     */
    private fun hashPin(pin: String): String {
        val salt = "ALFA_CERBER_SALT_${context.packageName}"
        val bytes = MessageDigest.getInstance("SHA-256")
            .digest("$salt$pin$salt".toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
    
    /**
     * Wyczyść wszystko (reset)
     */
    fun reset() {
        prefs.edit().clear().apply()
        val duressPrefs = context.getSharedPreferences("alfa_duress_state", Context.MODE_PRIVATE)
        duressPrefs.edit().clear().apply()
    }
}
