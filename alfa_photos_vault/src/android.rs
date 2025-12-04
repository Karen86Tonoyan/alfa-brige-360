//! ALFA Photos Vault - Android JNI Bindings
//!
//! Exposes Rust vault functions to Kotlin/Java via JNI.

#![cfg(feature = "android")]

use jni::JNIEnv;
use jni::objects::{JClass, JString, JByteArray};
use jni::sys::{jbyteArray, jboolean, jint, jlong, jstring, JNI_TRUE, JNI_FALSE};
use std::sync::Mutex;
use std::path::PathBuf;

use crate::{PhotoVault, VaultResult};

// Global vault instance (singleton for Android)
static VAULT: Mutex<Option<PhotoVault>> = Mutex::new(None);

/// Initialize vault at path
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_create(
    mut env: JNIEnv,
    _class: JClass,
    path: JString,
    pin: JString,
) -> jboolean {
    let path: String = match env.get_string(&path) {
        Ok(s) => s.into(),
        Err(_) => return JNI_FALSE,
    };
    
    let pin: String = match env.get_string(&pin) {
        Ok(s) => s.into(),
        Err(_) => return JNI_FALSE,
    };
    
    match PhotoVault::create(&PathBuf::from(path), &pin) {
        Ok(vault) => {
            *VAULT.lock().unwrap() = Some(vault);
            JNI_TRUE
        }
        Err(_) => JNI_FALSE,
    }
}

/// Open existing vault
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_open(
    mut env: JNIEnv,
    _class: JClass,
    path: JString,
) -> jboolean {
    let path: String = match env.get_string(&path) {
        Ok(s) => s.into(),
        Err(_) => return JNI_FALSE,
    };
    
    match PhotoVault::open(&PathBuf::from(path)) {
        Ok(vault) => {
            *VAULT.lock().unwrap() = Some(vault);
            JNI_TRUE
        }
        Err(_) => JNI_FALSE,
    }
}

/// Unlock vault with PIN
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_unlock(
    mut env: JNIEnv,
    _class: JClass,
    pin: JString,
) -> jboolean {
    let pin: String = match env.get_string(&pin) {
        Ok(s) => s.into(),
        Err(_) => return JNI_FALSE,
    };
    
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.unlock(&pin) {
            Ok(_) => JNI_TRUE,
            Err(_) => JNI_FALSE,
        }
    } else {
        JNI_FALSE
    }
}

/// Lock vault
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_lock(
    _env: JNIEnv,
    _class: JClass,
) {
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        vault.lock();
    }
}

/// Check if unlocked
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_isUnlocked(
    _env: JNIEnv,
    _class: JClass,
) -> jboolean {
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        if vault.is_unlocked() { JNI_TRUE } else { JNI_FALSE }
    } else {
        JNI_FALSE
    }
}

/// Import photo from bytes
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_importPhoto(
    mut env: JNIEnv,
    _class: JClass,
    data: JByteArray,
    name: JString,
) -> jstring {
    let data = match env.convert_byte_array(&data) {
        Ok(d) => d,
        Err(_) => return std::ptr::null_mut(),
    };
    
    let name: String = match env.get_string(&name) {
        Ok(s) => s.into(),
        Err(_) => return std::ptr::null_mut(),
    };
    
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        // Write temp file and import
        let temp_path = PathBuf::from("/data/local/tmp").join(&name);
        if std::fs::write(&temp_path, &data).is_err() {
            return std::ptr::null_mut();
        }
        
        match vault.import_photo(&temp_path, &name) {
            Ok(id) => {
                let _ = std::fs::remove_file(&temp_path);
                match env.new_string(&id) {
                    Ok(s) => s.into_raw(),
                    Err(_) => std::ptr::null_mut(),
                }
            }
            Err(_) => {
                let _ = std::fs::remove_file(&temp_path);
                std::ptr::null_mut()
            }
        }
    } else {
        std::ptr::null_mut()
    }
}

/// Get photo by ID
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_getPhoto(
    mut env: JNIEnv,
    _class: JClass,
    id: JString,
) -> jbyteArray {
    let id: String = match env.get_string(&id) {
        Ok(s) => s.into(),
        Err(_) => return std::ptr::null_mut(),
    };
    
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.get_photo(&id) {
            Ok(data) => {
                match env.byte_array_from_slice(&data) {
                    Ok(arr) => arr.into_raw(),
                    Err(_) => std::ptr::null_mut(),
                }
            }
            Err(_) => std::ptr::null_mut(),
        }
    } else {
        std::ptr::null_mut()
    }
}

/// Get thumbnail by ID
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_getThumbnail(
    mut env: JNIEnv,
    _class: JClass,
    id: JString,
) -> jbyteArray {
    let id: String = match env.get_string(&id) {
        Ok(s) => s.into(),
        Err(_) => return std::ptr::null_mut(),
    };
    
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.get_thumbnail(&id) {
            Ok(data) => {
                match env.byte_array_from_slice(&data) {
                    Ok(arr) => arr.into_raw(),
                    Err(_) => std::ptr::null_mut(),
                }
            }
            Err(_) => std::ptr::null_mut(),
        }
    } else {
        std::ptr::null_mut()
    }
}

/// Delete photo
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_deletePhoto(
    mut env: JNIEnv,
    _class: JClass,
    id: JString,
) -> jboolean {
    let id: String = match env.get_string(&id) {
        Ok(s) => s.into(),
        Err(_) => return JNI_FALSE,
    };
    
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.delete_photo(&id) {
            Ok(_) => JNI_TRUE,
            Err(_) => JNI_FALSE,
        }
    } else {
        JNI_FALSE
    }
}

/// Get photo count
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_getPhotoCount(
    _env: JNIEnv,
    _class: JClass,
) -> jint {
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.list_photos() {
            Ok(photos) => photos.len() as jint,
            Err(_) => 0,
        }
    } else {
        0
    }
}

/// Reset vault
#[no_mangle]
pub extern "system" fn Java_dev_alfa_vault_NativeVault_reset(
    _env: JNIEnv,
    _class: JClass,
) -> jboolean {
    let guard = VAULT.lock().unwrap();
    if let Some(ref vault) = *guard {
        match vault.reset() {
            Ok(_) => JNI_TRUE,
            Err(_) => JNI_FALSE,
        }
    } else {
        JNI_FALSE
    }
}
