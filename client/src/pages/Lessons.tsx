import { Button } from "@/components/ui/button";
import { useAuth } from "@/_core/hooks/useAuth";
import { AlertCircle, CheckCircle2, Lock } from "lucide-react";
import { useLocation } from "wouter";
import { useState } from "react";
import { getLoginUrl } from "@/const";

export default function Lessons() {
  const { isAuthenticated } = useAuth();
  const [, setLocation] = useLocation();
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [agreedToGDPR, setAgreedToGDPR] = useState(false);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="rounded-lg border border-border bg-card p-8 max-w-md w-full mx-4 shadow-2xl">
          <Lock className="h-12 w-12 text-accent mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-foreground text-center mb-2">
            Wymagane logowanie
          </h1>
          <p className="text-center text-muted-foreground mb-6">
            Aby uzyskać dostęp do lekcji Ethical Hacking, musisz się zalogować.
          </p>
          <a href={getLoginUrl()}>
            <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90">
              Zaloguj się
            </Button>
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur">
        <div className="container flex items-center justify-between py-4">
          <h1 className="text-3xl font-bold text-accent">Lekcje Ethical Hacking</h1>
          <Button
            variant="outline"
            className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
            onClick={() => setLocation("/")}
          >
            Powrót
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8">
        {!agreedToTerms || !agreedToGDPR ? (
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Terms Agreement */}
            <div className="rounded-lg border border-border bg-card p-8">
              <h2 className="text-2xl font-bold text-accent mb-4 flex items-center">
                <AlertCircle className="mr-3 h-6 w-6" />
                Umowa o warunkach korzystania
              </h2>

              <div className="bg-background rounded-lg p-6 mb-6 max-h-96 overflow-y-auto">
                <p className="text-sm text-foreground mb-4">
                  <strong>WAŻNE - PRZECZYTAJ UWAŻNIE:</strong>
                </p>
                <div className="text-sm text-muted-foreground space-y-4">
                  <p>
                    Materiały edukacyjne zawarte w kursie "Ethical Hacking" są przeznaczone <strong>wyłącznie do celów edukacyjnych i nauki</strong>.
                  </p>
                  <p>
                    <strong>Oświadczam, że:</strong>
                  </p>
                  <ul className="list-disc list-inside space-y-2 ml-4">
                    <li>Będę używać wiedzy wyłącznie w celach edukacyjnych i legalnych</li>
                    <li>Nie będę stosować technik do krzywdzenia, włamania lub naruszania prywatności osób trzecich</li>
                    <li>Rozumiem, że nielegalne użycie tej wiedzy może prowadzić do poważnych konsekwencji prawnych</li>
                    <li>Jestem w pełni odpowiedzialny za swoje działania</li>
                    <li>Nie będę publikować, rozpowszechniać ani udostępniać materiałów bez zgody autora</li>
                  </ul>
                  <p>
                    <strong>Autor nie ponosi odpowiedzialności za:</strong>
                  </p>
                  <ul className="list-disc list-inside space-y-2 ml-4">
                    <li>Nielegalne użycie wiedzy zawartej w kursie</li>
                    <li>Szkody wyrządzone przez uczestnika trzecim osobom</li>
                    <li>Naruszenie prawa przez uczestnika</li>
                  </ul>
                </div>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreedToTerms}
                  onChange={(e) => setAgreedToTerms(e.target.checked)}
                  className="w-5 h-5 rounded border-border"
                />
                <span className="text-sm text-foreground">
                  Oświadczam, że przeczytałem i akceptuję warunki korzystania
                </span>
              </label>
            </div>

            {/* GDPR Agreement */}
            <div className="rounded-lg border border-border bg-card p-8">
              <h2 className="text-2xl font-bold text-accent mb-4 flex items-center">
                <AlertCircle className="mr-3 h-6 w-6" />
                Zgoda na przetwarzanie danych osobowych (RODO)
              </h2>

              <div className="bg-background rounded-lg p-6 mb-6 max-h-96 overflow-y-auto">
                <div className="text-sm text-muted-foreground space-y-4">
                  <p>
                    <strong>Administrator danych:</strong> Karen Tonoyan
                  </p>
                  <p>
                    <strong>Cel przetwarzania:</strong> Świadczenie usług edukacyjnych i zarządzanie dostępem do kursów
                  </p>
                  <p>
                    <strong>Dane przetwarzane:</strong>
                  </p>
                  <ul className="list-disc list-inside space-y-2 ml-4">
                    <li>Imię i nazwisko</li>
                    <li>Adres email</li>
                    <li>Historia postępu w kursie</li>
                    <li>Data zalogowania</li>
                  </ul>
                  <p>
                    <strong>Podstawa prawna:</strong> Twoja dobrowolna zgoda
                  </p>
                  <p>
                    <strong>Okres przechowywania:</strong> Przez czas korzystania z usługi i 12 miesięcy po jej zakończeniu
                  </p>
                  <p>
                    <strong>Twoje prawa:</strong> Masz prawo do dostępu, sprostowania, usunięcia i przeniesienia swoich danych
                  </p>
                  <p>
                    <strong>Kontakt:</strong> W sprawie swoich danych skontaktuj się z administratorem na adres email
                  </p>
                </div>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreedToGDPR}
                  onChange={(e) => setAgreedToGDPR(e.target.checked)}
                  className="w-5 h-5 rounded border-border"
                />
                <span className="text-sm text-foreground">
                  Wyrażam zgodę na przetwarzanie moich danych osobowych zgodnie z RODO
                </span>
              </label>
            </div>

            {/* Accept Button */}
            <Button
              className="w-full bg-accent text-accent-foreground hover:bg-accent/90 py-6 text-lg"
              disabled={!agreedToTerms || !agreedToGDPR}
              onClick={() => {
                if (agreedToTerms && agreedToGDPR) {
                  // Save agreement to database
                  window.location.reload();
                }
              }}
            >
              <CheckCircle2 className="mr-2 h-5 w-5" />
              Akceptuję warunki i przystępuję do lekcji
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Lessons Content */}
            <div className="rounded-lg border border-border bg-card p-8">
              <h2 className="text-2xl font-bold text-accent mb-6">
                Dostępne lekcje
              </h2>

              <div className="space-y-4">
                <div className="rounded-lg border border-border/50 bg-background p-6 hover:border-accent transition-colors cursor-pointer">
                  <h3 className="text-lg font-bold text-foreground mb-2">
                    Lekcja 1: Podstawy Ethical Hacking
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Wprowadzenie do bezpiecznego hakownia, etyki i odpowiedzialności
                  </p>
                  <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                    Rozpocznij lekcję
                  </Button>
                </div>

                <div className="rounded-lg border border-border/50 bg-background p-6 hover:border-accent transition-colors cursor-pointer">
                  <h3 className="text-lg font-bold text-foreground mb-2">
                    Lekcja 2: Testowanie penetracyjne
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Techniki testowania bezpieczeństwa systemów
                  </p>
                  <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                    Rozpocznij lekcję
                  </Button>
                </div>

                <div className="rounded-lg border border-border/50 bg-background p-6 hover:border-accent transition-colors cursor-pointer">
                  <h3 className="text-lg font-bold text-foreground mb-2">
                    Lekcja 3: Bezpieczeństwo sieci
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Ochrona sieci i systemów przed atakami
                  </p>
                  <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                    Rozpocznij lekcję
                  </Button>
                </div>
              </div>
            </div>

            {/* Payment Info */}
            <div className="rounded-lg border border-accent bg-card p-8">
              <h2 className="text-2xl font-bold text-accent mb-4">
                Instrukcja platnosci
              </h2>
              <div className="space-y-4">
                <div>
                  <p className="text-muted-foreground mb-3">
                    Aby uzyskac dostep do szkolenia, dokonaj przelewu:
                  </p>
                  <div className="bg-background border border-border rounded p-4 font-mono text-sm text-accent">
                    44 1050 1748 1000 0092 1603 7961
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    Kwota: 200 zl
                  </p>
                </div>
                <div className="border-t border-border pt-4">
                  <p className="text-muted-foreground mb-3">
                    Po przelewu wyslij SMS:
                  </p>
                  <div className="bg-background border border-accent rounded p-4 font-mono text-sm text-accent text-center">
                    796 230 413
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    SMS: Szkolenie - [Twoj email]
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6 mt-12">
        <div className="container text-center text-sm text-muted-foreground">
          <p>© 2025 Karen Tonoyan. Wszelkie prawa zastrzeżone.</p>
        </div>
      </footer>
    </div>
  );
}
