//! Bezpieczne zeroizowanie pamięci

use zeroize::Zeroize;

/// Bezpiecznie zeroizuje bufor
pub fn zeroize_buffer(buffer: &mut [u8]) {
    buffer.zeroize();
}

/// Bezpiecznie zeroizuje wektor
pub fn zeroize_vec(vec: &mut Vec<u8>) {
    vec.zeroize();
}

/// Bezpiecznie zeroizuje string
pub fn zeroize_string(s: &mut String) {
    // SAFETY: modyfikujemy bajty stringa in-place
    unsafe {
        let bytes = s.as_bytes_mut();
        bytes.zeroize();
    }
    s.clear();
}

/// Bufor z automatycznym zeroizowaniem przy drop
#[derive(Clone)]
pub struct SecureBuffer {
    data: Vec<u8>,
}

impl SecureBuffer {
    pub fn new(size: usize) -> Self {
        Self {
            data: vec![0u8; size],
        }
    }

    pub fn from_slice(slice: &[u8]) -> Self {
        Self {
            data: slice.to_vec(),
        }
    }

    pub fn as_slice(&self) -> &[u8] {
        &self.data
    }

    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        &mut self.data
    }

    pub fn len(&self) -> usize {
        self.data.len()
    }

    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}

impl Drop for SecureBuffer {
    fn drop(&mut self) {
        self.data.zeroize();
    }
}

impl std::ops::Deref for SecureBuffer {
    type Target = [u8];

    fn deref(&self) -> &Self::Target {
        &self.data
    }
}

impl std::ops::DerefMut for SecureBuffer {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.data
    }
}

/// Bezpieczny array z automatycznym zeroizowaniem
#[derive(Clone)]
pub struct SecureArray<const N: usize> {
    data: [u8; N],
}

impl<const N: usize> SecureArray<N> {
    pub fn new() -> Self {
        Self { data: [0u8; N] }
    }

    pub fn from_array(arr: [u8; N]) -> Self {
        Self { data: arr }
    }

    pub fn as_array(&self) -> &[u8; N] {
        &self.data
    }

    pub fn as_mut_array(&mut self) -> &mut [u8; N] {
        &mut self.data
    }
}

impl<const N: usize> Default for SecureArray<N> {
    fn default() -> Self {
        Self::new()
    }
}

impl<const N: usize> Drop for SecureArray<N> {
    fn drop(&mut self) {
        self.data.zeroize();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_secure_buffer_zeroize() {
        let mut buf = SecureBuffer::from_slice(&[1, 2, 3, 4, 5]);
        assert_eq!(buf.len(), 5);
        drop(buf);
        // Po drop dane powinny być wyzerowane
        // (nie możemy tego bezpośrednio sprawdzić, ale test kompilacji + uruchomienia)
    }

    #[test]
    fn test_zeroize_string() {
        let mut s = "secret_password".to_string();
        zeroize_string(&mut s);
        assert!(s.is_empty());
    }
}
