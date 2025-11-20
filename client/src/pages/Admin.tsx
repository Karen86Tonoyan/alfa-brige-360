import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { useLocation } from "wouter";
import { AlertCircle } from "lucide-react";

export default function Admin() {
  const { user } = useAuth();
  const [, setLocation] = useLocation();

  // Check if user is admin
  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="rounded-lg border border-destructive bg-card p-8 max-w-md text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-foreground mb-2">Brak dostępu</h1>
          <p className="text-muted-foreground mb-6">
            Nie masz uprawnień do przeglądania tego panelu.
          </p>
          <Button
            className="bg-accent text-accent-foreground hover:bg-accent/90"
            onClick={() => setLocation("/")}
          >
            Powrót do strony głównej
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur">
        <div className="container flex items-center justify-between py-4">
          <h1 className="text-3xl font-bold text-accent">Panel Administratora</h1>
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
        <div className="grid gap-6">
          {/* Admin Info */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-xl font-bold text-accent mb-4">Informacje o koncie</h2>
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">Email:</span>{" "}
                <span className="text-foreground font-mono">{user?.email}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Rola:</span>{" "}
                <span className="text-accent font-bold">Administrator</span>
              </p>
              <p>
                <span className="text-muted-foreground">Dołączył:</span>{" "}
                <span className="text-foreground">
                  {user?.createdAt ? new Date(user.createdAt).toLocaleDateString("pl-PL") : "N/A"}
                </span>
              </p>
            </div>
          </div>

          {/* Zarządzanie produktami */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-xl font-bold text-accent mb-4">Zarządzanie produktami</h2>
            <div className="space-y-4">
              <div className="rounded-lg border border-border/50 bg-background p-4">
                <h3 className="font-bold text-foreground mb-2">Książki (30 zł)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Zarządzaj książkami dostępnymi w sklepie
                </p>
                <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                  Zarządzaj książkami
                </Button>
              </div>

              <div className="rounded-lg border border-border/50 bg-background p-4">
                <h3 className="font-bold text-foreground mb-2">E-booki (100 zł)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Zarządzaj e-bookami dostępnymi w sklepie
                </p>
                <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                  Zarządzaj e-bookami
                </Button>
              </div>

              <div className="rounded-lg border border-border/50 bg-background p-4">
                <h3 className="font-bold text-foreground mb-2">Kursy (200 zł)</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Zarządzaj kursami dostępnymi w sklepie
                </p>
                <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                  Zarządzaj kursami
                </Button>
              </div>
            </div>
          </div>

          {/* Statystyki */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-xl font-bold text-accent mb-4">Statystyki</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-border/50 bg-background p-4 text-center">
                <div className="text-2xl font-bold text-accent">0</div>
                <p className="text-sm text-muted-foreground">Sprzedane produkty</p>
              </div>
              <div className="rounded-lg border border-border/50 bg-background p-4 text-center">
                <div className="text-2xl font-bold text-accent">0 zł</div>
                <p className="text-sm text-muted-foreground">Całkowity przychód</p>
              </div>
              <div className="rounded-lg border border-border/50 bg-background p-4 text-center">
                <div className="text-2xl font-bold text-accent">0</div>
                <p className="text-sm text-muted-foreground">Zarejestrowani użytkownicy</p>
              </div>
            </div>
          </div>

          {/* Aktualizacja wkrótce */}
          <div className="rounded-lg border border-accent bg-card p-6">
            <h2 className="text-xl font-bold text-accent mb-4">Aktualizacja wkrótce</h2>
            <p className="text-muted-foreground">
              Po zapisaniu praw autorskich będą dostępne pełne funkcje zarządzania produktami,
              statystyki sprzedaży i zarządzanie użytkownikami.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6 mt-12">
        <div className="container text-center text-sm text-muted-foreground">
          <p>© 2025 Ethical Hacking Platform. Wszelkie prawa zastrzeżone.</p>
        </div>
      </footer>
    </div>
  );
}
