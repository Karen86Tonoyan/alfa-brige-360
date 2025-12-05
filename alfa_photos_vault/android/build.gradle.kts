plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "dev.alfa.vault"
    compileSdk = 34

    defaultConfig {
        minSdk = 26
        targetSdk = 34

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
        
        externalNativeBuild {
            cmake {
                cppFlags += "-std=c++17"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    
    kotlinOptions {
        jvmTarget = "17"
    }
    
    sourceSets {
        getByName("main") {
            jniLibs.srcDirs("src/main/jniLibs")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
}

# Import
from modules.automation_hub import AutomationHub
from modules.integrations import IntegrationManager

# Inicjalizacja
hub = AutomationHub()

# CRM - dodaj lead
hub.business.add_lead(Lead(name="Jan", email="jan@firma.pl"))

# Content - generuj treść
await hub.content.generate(ContentRequest(type="blog", prompt="AI w biznesie"))

# Chatbot
response = hub.communication.chatbot_respond("Cześć!")

# Analytics
hub.analytics.track_metric("users", 150)
hub.analytics.generate_report("daily", ["users", "revenue"])

# Integracje
manager = IntegrationManager()
manager.register("my_slack", "slack", IntegrationConfig(token="xoxb-..."))
await manager.send("my_slack", {"channel": "#general", "text": "Hello!"})
