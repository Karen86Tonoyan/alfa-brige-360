package dev.alfa.vault

/**
 * ALFA Photos Vault - Native Kotlin Bindings
 * 
 * JNI wrapper for Rust vault library.
 */
object NativeVault {
    
    init {
        System.loadLibrary("alfa_photos_vault")
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VAULT LIFECYCLE
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Create a new vault at the given path
     */
    external fun create(path: String, pin: String): Boolean
    
    /**
     * Open an existing vault
     */
    external fun open(path: String): Boolean
    
    /**
     * Unlock vault with PIN
     */
    external fun unlock(pin: String): Boolean
    
    /**
     * Lock vault (zeroize keys)
     */
    external fun lock()
    
    /**
     * Check if vault is unlocked
     */
    external fun isUnlocked(): Boolean
    
    // ═══════════════════════════════════════════════════════════════════════
    // PHOTO OPERATIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Import a photo from byte array
     * @return Photo ID or null on failure
     */
    external fun importPhoto(data: ByteArray, name: String): String?
    
    /**
     * Get decrypted photo by ID
     * @return Photo bytes or null on failure
     */
    external fun getPhoto(id: String): ByteArray?
    
    /**
     * Get decrypted thumbnail by ID
     * @return Thumbnail bytes or null on failure
     */
    external fun getThumbnail(id: String): ByteArray?
    
    /**
     * Delete photo by ID
     */
    external fun deletePhoto(id: String): Boolean
    
    /**
     * Get total photo count
     */
    external fun getPhotoCount(): Int
    
    // ═══════════════════════════════════════════════════════════════════════
    // MAINTENANCE
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Reset vault - clear cache, rebuild index, run AI healing
     */
    external fun reset(): Boolean
}

/**
 * High-level Kotlin wrapper with coroutine support
 */
class AlfaPhotosVault(private val vaultPath: String) {
    
    private var isCreated = false
    
    suspend fun create(pin: String): Result<Unit> = runCatching {
        require(NativeVault.create(vaultPath, pin)) { "Failed to create vault" }
        isCreated = true
    }
    
    suspend fun open(): Result<Unit> = runCatching {
        require(NativeVault.open(vaultPath)) { "Failed to open vault" }
        isCreated = true
    }
    
    suspend fun unlock(pin: String): Result<Unit> = runCatching {
        require(NativeVault.unlock(pin)) { "Invalid PIN or vault locked" }
    }
    
    fun lock() {
        NativeVault.lock()
    }
    
    val isUnlocked: Boolean
        get() = NativeVault.isUnlocked()
    
    suspend fun importPhoto(data: ByteArray, name: String): Result<String> = runCatching {
        NativeVault.importPhoto(data, name) 
            ?: throw IllegalStateException("Failed to import photo")
    }
    
    suspend fun getPhoto(id: String): Result<ByteArray> = runCatching {
        NativeVault.getPhoto(id) 
            ?: throw IllegalStateException("Photo not found: $id")
    }
    
    suspend fun getThumbnail(id: String): Result<ByteArray> = runCatching {
        NativeVault.getThumbnail(id) 
            ?: throw IllegalStateException("Thumbnail not found: $id")
    }
    
    suspend fun deletePhoto(id: String): Result<Unit> = runCatching {
        require(NativeVault.deletePhoto(id)) { "Failed to delete photo: $id" }
    }
    
    val photoCount: Int
        get() = NativeVault.getPhotoCount()
    
    suspend fun reset(): Result<Unit> = runCatching {
        require(NativeVault.reset()) { "Reset failed" }
    }
}
