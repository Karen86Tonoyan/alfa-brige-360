//! ALFA Photos Vault - CLI
//!
//! Command-line interface for vault operations.

use std::path::PathBuf;
use clap::{Parser, Subcommand};

use alfa_photos_vault::{PhotoVault, VaultResult};

#[derive(Parser)]
#[command(name = "alfa-photos")]
#[command(author = "Karen Tonoyan")]
#[command(version = alfa_photos_vault::VERSION)]
#[command(about = "ALFA Photos Vault - Military-grade encrypted photo gallery")]
struct Cli {
    /// Vault path
    #[arg(short, long, default_value = "./vault")]
    vault: PathBuf,
    
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Create a new vault
    Create {
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Unlock vault
    Unlock {
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Import a photo
    Import {
        /// Photo path
        path: PathBuf,
        
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// List all photos
    List {
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Export a photo
    Export {
        /// Photo ID
        id: String,
        
        /// Output path
        output: PathBuf,
        
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Delete a photo
    Delete {
        /// Photo ID
        id: String,
        
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Reset vault (clear cache, rebuild index)
    Reset {
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Show vault statistics
    Stats {
        /// PIN code
        #[arg(short, long)]
        pin: String,
    },
    
    /// Demo mode (create sample vault)
    Demo,
}

fn main() {
    let cli = Cli::parse();
    
    if let Err(e) = run(cli) {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}

fn run(cli: Cli) -> VaultResult<()> {
    match cli.command {
        Commands::Create { pin } => {
            println!("🔐 Creating new ALFA Photos Vault...");
            let vault = PhotoVault::create(&cli.vault, &pin)?;
            println!("✅ Vault created at: {}", cli.vault.display());
            println!("📁 Structure:");
            println!("   /photos/  - Encrypted photos");
            println!("   /thumbs/  - Encrypted thumbnails");
            println!("   /db/      - Encrypted index");
            println!("   /ai/      - Self-healing AI data");
        }
        
        Commands::Unlock { pin } => {
            println!("🔓 Unlocking vault...");
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            println!("✅ Vault unlocked!");
        }
        
        Commands::Import { path, pin } => {
            println!("📥 Importing photo: {}", path.display());
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            let filename = path.file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("unknown");
            
            let id = vault.import_photo(&path, filename)?;
            println!("✅ Photo imported with ID: {}", id);
        }
        
        Commands::List { pin } => {
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            let photos = vault.list_photos()?;
            
            if photos.is_empty() {
                println!("📭 No photos in vault");
            } else {
                println!("📷 Photos in vault ({}):", photos.len());
                println!("{:-<60}", "");
                for photo in photos {
                    let hidden = if photo.is_hidden { "🔒" } else { "  " };
                    let fav = if photo.is_favorite { "⭐" } else { "  " };
                    println!(
                        "{} {} {} - {} ({} bytes)",
                        hidden, fav, photo.id, photo.original_name, photo.original_size
                    );
                }
            }
        }
        
        Commands::Export { id, output, pin } => {
            println!("📤 Exporting photo: {}", id);
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            let data = vault.get_photo(&id)?;
            std::fs::write(&output, &data)?;
            
            println!("✅ Photo exported to: {}", output.display());
        }
        
        Commands::Delete { id, pin } => {
            println!("🗑️ Deleting photo: {}", id);
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            vault.delete_photo(&id)?;
            println!("✅ Photo deleted!");
        }
        
        Commands::Reset { pin } => {
            println!("🔄 Resetting vault...");
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            let report = vault.reset()?;
            
            println!("✅ Reset complete!");
            println!("   Thumbnails cleared: {}", report.thumbs_cleared);
            println!("   Index errors fixed: {}", report.index_errors);
            println!("   Integrity issues: {}", report.integrity_issues.len());
            println!("   AI fixes: {}", report.ai_fixes);
            
            if report.is_healthy() {
                println!("💚 Vault is healthy!");
            } else {
                println!("⚠️ Some issues remain");
                for issue in &report.integrity_issues {
                    println!("   - {}", issue);
                }
            }
        }
        
        Commands::Stats { pin } => {
            let vault = PhotoVault::open(&cli.vault)?;
            vault.unlock(&pin)?;
            
            let photos = vault.list_photos()?;
            let total: u64 = photos.iter().map(|p| p.original_size).sum();
            let encrypted: u64 = photos.iter().map(|p| p.encrypted_size).sum();
            
            println!("📊 ALFA Photos Vault Statistics");
            println!("{:-<40}", "");
            println!("Total photos:     {}", photos.len());
            println!("Hidden photos:    {}", photos.iter().filter(|p| p.is_hidden).count());
            println!("Favorite photos:  {}", photos.iter().filter(|p| p.is_favorite).count());
            println!("Original size:    {} MB", total / 1024 / 1024);
            println!("Encrypted size:   {} MB", encrypted / 1024 / 1024);
            println!("Overhead:         {:.1}%", (encrypted as f64 / total.max(1) as f64 - 1.0) * 100.0);
        }
        
        Commands::Demo => {
            println!("🎮 ALFA Photos Vault - Demo Mode");
            println!("{:-<40}", "");
            println!("Creating demo vault...");
            
            let demo_path = PathBuf::from("./demo_vault");
            let pin = "1234";
            
            if demo_path.exists() {
                std::fs::remove_dir_all(&demo_path)?;
            }
            
            let vault = PhotoVault::create(&demo_path, pin)?;
            
            println!("✅ Demo vault created!");
            println!("   Path: {}", demo_path.display());
            println!("   PIN: {}", pin);
            println!();
            println!("Try these commands:");
            println!("  alfa-photos --vault ./demo_vault import <photo.jpg> -p 1234");
            println!("  alfa-photos --vault ./demo_vault list -p 1234");
            println!("  alfa-photos --vault ./demo_vault stats -p 1234");
        }
    }
    
    Ok(())
}
