package com.alfa.mail.security

import kotlin.random.Random

/**
 * 🎭 FAKE DATA PROVIDER
 * 
 * Generuje fałszywe dane gdy tryb Duress jest aktywny.
 * Wygląda przekonująco ale nie zawiera prawdziwych informacji.
 */
object FakeDataProvider {
    
    // Fałszywe emaile
    private val FAKE_SENDERS = listOf(
        "newsletter@company.com",
        "support@amazon.pl",
        "info@allegro.pl",
        "notifications@facebook.com",
        "no-reply@linkedin.com",
        "promocje@mediamarkt.pl",
        "kontakt@bank.pl",
        "newsletter@spotify.com"
    )
    
    private val FAKE_SUBJECTS = listOf(
        "Twoje zamówienie zostało wysłane",
        "Nowa promocja - do -50%!",
        "Potwierdzenie rezerwacji",
        "Newsletter tygodniowy",
        "Aktualizacja regulaminu",
        "Twoja faktura za sierpień",
        "Przypomnienie o płatności",
        "Nowe powiadomienia",
        "Zaproszenie do ankiety",
        "Twój raport tygodniowy"
    )
    
    private val FAKE_BODIES = listOf(
        "Dziękujemy za zakupy! Twoje zamówienie jest w drodze.",
        "Sprawdź najnowsze promocje w naszym sklepie.",
        "Twoja rezerwacja została potwierdzona.",
        "Zobacz co nowego w tym tygodniu.",
        "Zaktualizowaliśmy nasz regulamin. Zapoznaj się ze zmianami.",
        "W załączniku przesyłamy fakturę za ostatni okres.",
        "Przypominamy o zbliżającym się terminie płatności.",
        "Masz nowe powiadomienia do sprawdzenia.",
        "Pomóż nam ulepszyć nasze usługi - wypełnij krótką ankietę.",
        "Podsumowanie Twojej aktywności z ostatniego tygodnia."
    )
    
    data class FakeEmail(
        val id: Long,
        val from: String,
        val subject: String,
        val preview: String,
        val body: String,
        val timestamp: Long,
        val isRead: Boolean
    )
    
    /**
     * Generuj fałszywe emaile
     */
    fun generateFakeEmails(count: Int = 15): List<FakeEmail> {
        val now = System.currentTimeMillis()
        
        return (0 until count).map { index ->
            val senderIndex = Random.nextInt(FAKE_SENDERS.size)
            val subjectIndex = Random.nextInt(FAKE_SUBJECTS.size)
            val bodyIndex = Random.nextInt(FAKE_BODIES.size)
            
            FakeEmail(
                id = index.toLong(),
                from = FAKE_SENDERS[senderIndex],
                subject = FAKE_SUBJECTS[subjectIndex],
                preview = FAKE_BODIES[bodyIndex].take(50) + "...",
                body = FAKE_BODIES[bodyIndex],
                timestamp = now - (index * 3600000L) - Random.nextLong(1800000), // Co godzinę
                isRead = index > 2 // Pierwsze 3 nieprzeczytane
            )
        }
    }
    
    // Fałszywe kontakty
    private val FAKE_NAMES = listOf(
        "Anna Kowalska", "Jan Nowak", "Maria Wiśniewska",
        "Piotr Wójcik", "Katarzyna Dąbrowska", "Andrzej Kozłowski",
        "Magdalena Jankowska", "Tomasz Mazur", "Ewa Wojciechowska"
    )
    
    data class FakeContact(
        val id: Long,
        val name: String,
        val email: String,
        val phone: String?
    )
    
    fun generateFakeContacts(count: Int = 10): List<FakeContact> {
        return FAKE_NAMES.take(count).mapIndexed { index, name ->
            val emailName = name.lowercase()
                .replace(" ", ".")
                .replace("ą", "a").replace("ę", "e")
                .replace("ó", "o").replace("ś", "s")
                .replace("ł", "l").replace("ż", "z")
                .replace("ź", "z").replace("ć", "c")
                .replace("ń", "n")
            
            FakeContact(
                id = index.toLong(),
                name = name,
                email = "$emailName@gmail.com",
                phone = if (Random.nextBoolean()) "+48 ${Random.nextInt(100, 999)} ${Random.nextInt(100, 999)} ${Random.nextInt(100, 999)}" else null
            )
        }
    }
    
    // Fałszywe drafty
    data class FakeDraft(
        val id: Long,
        val to: String,
        val subject: String,
        val body: String,
        val savedAt: Long
    )
    
    fun generateFakeDrafts(count: Int = 3): List<FakeDraft> {
        val now = System.currentTimeMillis()
        
        return listOf(
            FakeDraft(
                id = 1,
                to = "kolega@work.com",
                subject = "Re: Spotkanie w piątek",
                body = "Cześć, potwierdzam obecność na...",
                savedAt = now - 3600000
            ),
            FakeDraft(
                id = 2,
                to = "mama@family.pl",
                subject = "Urodziny babci",
                body = "Hej, pamiętaj że w sobotę...",
                savedAt = now - 7200000
            ),
            FakeDraft(
                id = 3,
                to = "sklep@allegro.pl",
                subject = "Reklamacja zamówienia",
                body = "Dzień dobry, chciałbym zgłosić...",
                savedAt = now - 86400000
            )
        ).take(count)
    }
    
    // Fałszywe foldery
    data class FakeFolder(
        val name: String,
        val count: Int,
        val unread: Int
    )
    
    fun generateFakeFolders(): List<FakeFolder> {
        return listOf(
            FakeFolder("Odebrane", 47, 3),
            FakeFolder("Wysłane", 23, 0),
            FakeFolder("Wersje robocze", 3, 0),
            FakeFolder("Spam", 12, 0),
            FakeFolder("Kosz", 8, 0),
            FakeFolder("Ważne", 5, 1)
        )
    }
    
    // Fałszywe ustawienia (niegroźne)
    fun getFakeSettings(): Map<String, Any> {
        return mapOf(
            "sync_frequency" to "15 minut",
            "notifications" to true,
            "dark_mode" to false,
            "signature" to "Wysłane z ALFA Mail",
            "default_account" to "user@gmail.com"
        )
    }
    
    /**
     * Sprawdź czy w trybie duress powinniśmy pokazać fałszywe dane
     */
    fun shouldShowFakeData(isDuressMode: Boolean): Boolean {
        return isDuressMode
    }
}
