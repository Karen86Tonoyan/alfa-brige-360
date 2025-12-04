//! ALFA Photos Vault - Thumbnail Engine
//!
//! Generates and manages encrypted thumbnails.

use std::path::{Path, PathBuf};
use image::{DynamicImage, GenericImageView, imageops::FilterType};
use std::io::Cursor;

use crate::error::{VaultError, VaultResult};

/// Thumbnail Engine
pub struct ThumbnailEngine {
    /// Root path
    root: PathBuf,
    /// Thumbnail size (square)
    size: u32,
}

impl ThumbnailEngine {
    /// Create new thumbnail engine
    pub fn new(root: &Path, size: u32) -> Self {
        Self {
            root: root.to_path_buf(),
            size,
        }
    }
    
    /// Generate thumbnail from image data
    pub fn generate(&self, image_data: &[u8]) -> VaultResult<Vec<u8>> {
        // Load image
        let img = image::load_from_memory(image_data)
            .map_err(|e| VaultError::ThumbnailFailed(e.to_string()))?;
        
        // Generate thumbnail
        let thumb = self.resize_to_thumbnail(&img);
        
        // Encode as JPEG (smaller than PNG)
        let mut output = Vec::new();
        let mut cursor = Cursor::new(&mut output);
        
        thumb
            .write_to(&mut cursor, image::ImageFormat::Jpeg)
            .map_err(|e| VaultError::ThumbnailFailed(e.to_string()))?;
        
        Ok(output)
    }
    
    /// Resize image to thumbnail (maintaining aspect ratio)
    fn resize_to_thumbnail(&self, img: &DynamicImage) -> DynamicImage {
        let (width, height) = img.dimensions();
        
        // Calculate crop dimensions for square thumbnail
        let (crop_x, crop_y, crop_size) = if width > height {
            let offset = (width - height) / 2;
            (offset, 0, height)
        } else {
            let offset = (height - width) / 2;
            (0, offset, width)
        };
        
        // Crop to square
        let cropped = img.crop_imm(crop_x, crop_y, crop_size, crop_size);
        
        // Resize to target size
        cropped.resize_exact(self.size, self.size, FilterType::Lanczos3)
    }
    
    /// Generate high-quality thumbnail (for preview)
    pub fn generate_preview(&self, image_data: &[u8], max_dimension: u32) -> VaultResult<Vec<u8>> {
        let img = image::load_from_memory(image_data)
            .map_err(|e| VaultError::ThumbnailFailed(e.to_string()))?;
        
        let (width, height) = img.dimensions();
        
        // Calculate new dimensions maintaining aspect ratio
        let (new_width, new_height) = if width > height {
            let ratio = max_dimension as f32 / width as f32;
            (max_dimension, (height as f32 * ratio) as u32)
        } else {
            let ratio = max_dimension as f32 / height as f32;
            ((width as f32 * ratio) as u32, max_dimension)
        };
        
        let resized = img.resize_exact(new_width, new_height, FilterType::Lanczos3);
        
        let mut output = Vec::new();
        let mut cursor = Cursor::new(&mut output);
        
        resized
            .write_to(&mut cursor, image::ImageFormat::Jpeg)
            .map_err(|e| VaultError::ThumbnailFailed(e.to_string()))?;
        
        Ok(output)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    
    #[test]
    fn test_thumbnail_generation() {
        // Create a simple test image
        let img = image::DynamicImage::new_rgb8(800, 600);
        let mut buffer = Vec::new();
        img.write_to(&mut Cursor::new(&mut buffer), image::ImageFormat::Png).unwrap();
        
        let engine = ThumbnailEngine::new(&PathBuf::from("/tmp"), 256);
        let thumb = engine.generate(&buffer).unwrap();
        
        // Verify thumbnail was generated
        assert!(!thumb.is_empty());
        
        // Verify it's a valid JPEG
        let decoded = image::load_from_memory(&thumb).unwrap();
        assert_eq!(decoded.dimensions(), (256, 256));
    }
}
