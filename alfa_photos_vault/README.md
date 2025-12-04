# 🛡️ ALFA Photos Vault

**Military-grade encrypted photo gallery with self-healing AI**

> *Your photos are your fortress. Zero cloud, zero tracking, zero compromise.*

[![Rust](https://img.shields.io/badge/Rust-2021-orange.svg)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ALFA System](https://img.shields.io/badge/ALFA-System-gold.svg)](https://github.com/Karen86Tonoyan/ALFA__CORE)

---

## 🔥 Features

### 🔐 Military-Grade Encryption
- **AES-256-GCM** for photos and thumbnails
- **XChaCha20-Poly1305** for metadata and index
- **HKDF-SHA256** hierarchical key derivation
- **Argon2id** for PIN → Master Key
- **Per-file unique keys** - each photo has its own key
- **HMAC integrity verification** for every file

### 🧠 Self-Healing AI (Offline)
- Learns your patterns locally
- Detects duplicates (perceptual hashing)
- Auto-suggests tags
- Predicts hidden/sensitive photos
- Self-repairs index corruption
- **100% offline - no cloud, no network**

### 🔄 Reset Button
- One-click vault recovery
- Clears thumbnail cache
- Rebuilds corrupted index
- Verifies all file integrity
- Zero data loss

### 🔌 Sync Plugin (Optional)
- **Ente** - encrypted cloud backup
- **Nextcloud** - self-hosted WebDAV
- **Local NAS** - SMB/CIFS
- **USB Drive** - offline backup
- **Always encrypted** - sync target only sees blobs

---

## 📁 Architecture

```
ALFA Photos Vault
├── 🔐 Vault Core (vault.rs)
│   ├── Create / Open / Lock / Unlock
│   ├── Import / Export / Delete
│   └── Reset Button
│
├── 🔑 Crypto (crypto/)
│   ├── keys.rs      - KeyManager, HKDF derivation
│   ├── aead.rs      - AES-GCM, XChaCha20
│   └── hkdf.rs      - Subkey derivation, epochs
│
├── 📇 Index (index.rs)
│   ├── Encrypted SQLite database
│   ├── Tag search
│   └── Duplicate detection
│
├── 🖼️ Thumbnails (thumbs.rs)
│   ├── Encrypted thumbnails
│   └── Lazy decryption
│
├── 🧠 AI (ai.rs)
│   ├── Event learning
│   ├── Pattern recognition
│   └── Self-healing
│
├── 📱 Android (android.rs)
│   └── JNI bindings for Kotlin/Java
│
└── 🔌 Sync (sync_plugin.rs)
    ├── Ente / Nextcloud / NAS
    └── USB backup
```

---

## 🚀 Quick Start

### Build
```bash
cd alfa_photos_vault
cargo build --release
```

### Create Vault
```bash
alfa-photos --vault ./my_vault create --pin 123456
```

### Import Photo
```bash
alfa-photos --vault ./my_vault import photo.jpg --pin 123456
```

### List Photos
```bash
alfa-photos --vault ./my_vault list --pin 123456
```

### Reset Vault
```bash
alfa-photos --vault ./my_vault reset --pin 123456
```

---

## 🔒 Security Model

```
┌─────────────────────────────────────────────────────────┐
│                    USER LAYER                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐  │
│  │   PIN   │  │ Biomet. │  │  Android Keystore       │  │
│  └────┬────┘  └────┬────┘  └────────────┬────────────┘  │
│       │            │                     │               │
│       └────────────┴─────────────────────┘               │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────────┐ │
│  │              ARGON2ID (64MiB, 3 iter)                │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                │
│                    MASTER SEED                           │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────────┐ │
│  │                  HKDF-SHA256                         │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐  │ │
│  │  │K_photos │  │K_thumbs │  │ K_index │  │ K_hmac │  │ │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬───┘  │ │
│  └───────┼────────────┼───────────┼────────────┼───────┘ │
│          │            │           │            │         │
│  ┌───────▼────┐ ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐   │
│  │ Per-file   │ │ Thumbnail │ │ SQLite │ │ Integrity│   │
│  │ keys (HKDF)│ │ keys      │ │ encrypt│ │ verify   │   │
│  └────────────┘ └───────────┘ └────────┘ └──────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 Android Integration

### Kotlin Usage

```kotlin
class VaultActivity : AppCompatActivity() {
    
    companion object {
        init {
            System.loadLibrary("alfa_photos_vault")
        }
    }
    
    private external fun create(path: String, pin: String): Boolean
    private external fun open(path: String): Boolean
    private external fun unlock(pin: String): Boolean
    private external fun lock()
    private external fun isUnlocked(): Boolean
    private external fun importPhoto(data: ByteArray, name: String): String?
    private external fun getPhoto(id: String): ByteArray?
    private external fun getThumbnail(id: String): ByteArray?
    private external fun deletePhoto(id: String): Boolean
    private external fun reset(): Boolean
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val vaultPath = "${filesDir.absolutePath}/vault"
        
        // Create or open vault
        if (!File(vaultPath).exists()) {
            create(vaultPath, "123456")
        } else {
            open(vaultPath)
        }
        
        // Unlock with biometrics callback
        BiometricPrompt(...).authenticate { 
            unlock("123456")
        }
    }
}
```

### Build for Android

```bash
# Install Android NDK targets
rustup target add aarch64-linux-android
rustup target add armv7-linux-androideabi
rustup target add x86_64-linux-android

# Build
cargo build --release --target aarch64-linux-android --features android
```

---

## 🔧 Configuration

### VaultConfig

```rust
VaultConfig {
    name: "ALFA Photos Vault",
    thumb_size: 256,              // Thumbnail size
    ai_enabled: true,             // Self-healing AI
    max_failed_attempts: 5,       // Lockout after N failures
}
```

### Sync Config

```rust
SyncConfig {
    provider: SyncProvider::Ente,
    server_url: Some("https://api.ente.io"),
    auto_sync: true,
    sync_interval: 3600,  // 1 hour
}
```

---

## 📊 Storage Structure

```
/ALFA_VAULT/
    manifest.enc          ← Encrypted config
    /photos/
        IMG_001.enc       ← AES-256-GCM encrypted
        IMG_002.enc
        VIDEO_001.enc
    /thumbs/
        IMG_001.enc       ← Encrypted thumbnails
        IMG_002.enc
    /db/
        index.db          ← SQLite (data encrypted)
    /ai/
        events.json       ← Learning events
        patterns.json     ← Learned patterns
```

---

## 🆚 Comparison

| Feature | Google Photos | iCloud | Ente | **ALFA Vault** |
|---------|--------------|--------|------|----------------|
| E2E Encryption | ❌ | ❌ | ✅ | ✅ |
| Zero Cloud | ❌ | ❌ | ❌ | ✅ |
| Open Source | ❌ | ❌ | ✅ | ✅ |
| Self-hosted | ❌ | ❌ | ⚠️ | ✅ |
| AI (offline) | ❌ | ❌ | ❌ | ✅ |
| Per-file keys | ❌ | ❌ | ⚠️ | ✅ |
| Reset button | ❌ | ❌ | ❌ | ✅ |
| PQX-ready | ❌ | ❌ | ❌ | ✅ |

---

## 🛣️ Roadmap

- [x] Core vault (Rust)
- [x] AES-256-GCM encryption
- [x] HKDF key derivation
- [x] Thumbnail engine
- [x] Photo index (encrypted SQLite)
- [x] Self-healing AI
- [x] Reset button
- [x] CLI interface
- [x] Android JNI bindings
- [ ] Android app (Kotlin)
- [ ] Ente sync plugin
- [ ] Nextcloud sync plugin
- [ ] EXIF extraction
- [ ] Album support
- [ ] Face detection (offline)
- [ ] PQXHybrid keys (post-quantum)

---

## 📜 License

MIT License - Karen Tonoyan / ALFA System

---

## 🔗 Related

- [ALFA__CORE](https://github.com/Karen86Tonoyan/ALFA__CORE) - Main ALFA System
- [ALFA_KEYVAULT](../alfa_keyvault) - Cryptographic vault core
- [ALFA Guard](../alfa_guard.py) - Security monitor

---

> *"Twoje dane → u Ciebie. Chmura → tylko jako dodatek."*
> 
> — ALFA Philosophy
