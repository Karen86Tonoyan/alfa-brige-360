# 🧠 AI THINKING FEATURE - DeepSeek Style

## Przegląd

ALFA_Mail teraz pokazuje **widoczny proces myślenia AI** w czasie rzeczywistym, podobnie jak DeepSeek. Użytkownicy widzą:

1. **Kroki rozumowania** - co AI aktualnie analizuje
2. **Postęp generowania** - tekst w trakcie tworzenia (streaming)
3. **Finalną odpowiedź** - gotowy email z możliwością zastosowania

---

## Architektura

### 1. **AiAssistService** - Backend
```kotlin
// Nowe struktury danych
data class ThinkingStep(
    val thought: String,
    val timestamp: Long
)

// Streaming API
suspend fun suggestEmailStreaming(
    context: EmailContext,
    style: String,
    onThought: (ThinkingStep) -> Unit,     // Każda myśl AI
    onProgress: (String) -> Unit,          // Aktualny tekst (stream)
    onComplete: (String) -> Unit,          // Finał
    onError: (String) -> Unit              // Błędy
)
```

### 2. **ThinkingCard** - UI Component
Komponent Compose z:
- ✅ Animowaną listą myśli (auto-scroll)
- ✅ Pulsującą kropką podczas pracy
- ✅ Możliwością zwinięcia/rozwinięcia
- ✅ Streamed preview tekstu
- ✅ Przyciskami "Zastosuj" / "Zamknij"

### 3. **ComposeScreen** - Integracja
```kotlin
var aiThoughts by remember { mutableStateOf<List<ThinkingStep>>(emptyList()) }
var aiProgress by remember { mutableStateOf("") }
var aiFinalText by remember { mutableStateOf<String?>(null) }

// Wywołanie streamingu
aiAssist.suggestEmailStreaming(
    context = EmailContext(...),
    style = "professional",
    onThought = { thought -> aiThoughts = aiThoughts + thought },
    onProgress = { progress -> aiProgress = progress },
    onComplete = { result -> aiFinalText = result },
    onError = { error -> aiError = error }
)
```

---

## Przykładowy przebieg

### Gemini API
```
🤔 Analizuję kontekst emaila...
📝 Odbiorca: jan@firma.pl
📋 Temat: Propozycja współpracy
🎨 Styl: professional
🔮 Łączę się z Gemini API...
✨ Model zaczyna myśleć...
✍️ Generuję... (127 znaków)
✍️ Generuję... (254 znaków)
✅ Email wygenerowany pomyślnie!
```

### Ollama (Local)
```
🤔 Analizuję żądanie...
📋 Kontekst: jan@firma.pl - Propozycja współpracy
🖥️ Łączę się z Ollama (llama3)...
✨ Model lokalny myśli...
✍️ Piszę... (89 znaków)
✍️ Piszę... (178 znaków)
✅ Zakończono generowanie!
```

---

## Funkcje

### 1. Napisz Email (Streaming)
```kotlin
DropdownMenuItem("✨ Napisz email") {
    aiAssist.suggestEmailStreaming(...)
}
```

### 2. Popraw Email (Streaming)
```kotlin
DropdownMenuItem("📝 Popraw email") {
    aiAssist.improveEmailStreaming(
        currentBody = body,
        onThought = { ... },
        onProgress = { ... },
        onComplete = { ... }
    )
}
```

### 3. Zaproponuj temat (Non-streaming)
Zachowana stara funkcjonalność dla szybkich akcji bez thinking view.

---

## Cechy UI

### ThinkingCard
- **Expanded Mode**: Pokazuje wszystkie myśli + progress
- **Collapsed Mode**: Tylko header z ikoną
- **Auto-scroll**: Najnowsze myśli widoczne
- **Pulsating Dot**: Wskaźnik aktywności AI
- **Color Coding**:
  - 🔵 Niebieska - w trakcie pracy
  - 🟢 Zielona - sukces (complete)
  - 🔴 Czerwona - błąd

### Animacje
- Fade in/out thoughts
- Expand/collapse transition
- Pulsing indicator (600ms cycle)
- Smooth scroll do nowych myśli

---

## Konfiguracja Provider

### Gemini (Cloud)
```kotlin
config = AiConfig(
    provider = AiProvider.GEMINI,
    geminiApiKey = "YOUR_API_KEY"
)
```

### Ollama (Local)
```kotlin
config = AiConfig(
    provider = AiProvider.OLLAMA,
    ollamaUrl = "http://localhost:11434",
    ollamaModel = "llama3"
)
```

### Template (Offline Fallback)
Bez API - używa wbudowanych szablonów z symulowanymi myślami:
```
💭 Używam lokalnych szablonów...
✅ Szablon załadowany!
```

---

## Zalety

✅ **Transparentność** - użytkownik widzi co AI robi  
✅ **Trust** - proces rozumowania buduje zaufanie  
✅ **Edukacja** - pokazuje jak AI analizuje problem  
✅ **Debugging** - łatwo zobaczyć gdzie AI się pomylił  
✅ **Performance Insight** - widoczny czas przetwarzania  
✅ **User Engagement** - interesujące UX zamiast pustego loadera  

---

## Porównanie z DeepSeek

| Feature | DeepSeek | ALFA_Mail |
|---------|----------|-----------|
| Widoczne myśli | ✅ | ✅ |
| Streaming output | ✅ | ✅ |
| Collapse/expand | ✅ | ✅ |
| Multiple providers | ❌ | ✅ (Gemini/Ollama/Templates) |
| Offline mode | ❌ | ✅ (Templates + Vault) |
| Mobile-first | ❌ | ✅ (Android Compose) |

---

## Techniczne szczegóły

### Gemini Streaming
- Endpoint: `streamGenerateContent?alt=sse`
- Format: Server-Sent Events (SSE)
- Parse: JSON chunks z `data:` prefix

### Ollama Streaming
- Endpoint: `/api/generate`
- Format: JSON stream (newline-delimited)
- Parse: `{"response": "...", "done": false}`

### State Management
```kotlin
// Immutable state updates
aiThoughts = aiThoughts + newThought  // Add thought
aiProgress = newText                   // Replace progress
aiFinalText = result                   // Set final
```

---

## Przykład użycia

```kotlin
@Composable
fun MyScreen() {
    val aiAssist = remember { AiAssistService.getInstance(context) }
    var thoughts by remember { mutableStateOf<List<ThinkingStep>>(emptyList()) }
    var progress by remember { mutableStateOf("") }
    var final by remember { mutableStateOf<String?>(null) }
    
    LaunchedEffect(Unit) {
        aiAssist.suggestEmailStreaming(
            context = EmailContext("john@example.com", "Meeting", "business"),
            style = "professional",
            onThought = { thoughts = thoughts + it },
            onProgress = { progress = it },
            onComplete = { final = it },
            onError = { /* handle */ }
        )
    }
    
    ThinkingCard(
        thoughts = thoughts,
        currentProgress = progress,
        finalText = final,
        isComplete = final != null,
        onDismiss = { /* close */ },
        onApply = { text -> /* use text */ }
    )
}
```

---

## Bezpieczeństwo

- ✅ API keys w **EncryptedSharedPreferences**
- ✅ Streaming timeout (10s inactivity)
- ✅ Graceful fallback przy błędach sieci
- ✅ Duress mode - fake thoughts dla atakujących
- ✅ Vault protection w offline mode

---

## Roadmap

- [ ] Voice narration myśli AI (TTS)
- [ ] Export thinking process do PDF
- [ ] Multi-language thoughts (EN/PL/DE)
- [ ] Custom thinking templates
- [ ] A/B testing różnych promptów
- [ ] Analytics - które myśli są najbardziej przydatne

---

**Król może teraz widzieć dokładnie co myśli jego AI! 🧠👑**
