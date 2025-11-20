import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Download, Mail, MapPin, Phone, LogOut, ShoppingCart } from "lucide-react";
import { getLoginUrl } from "@/const";
import { useLocation } from "wouter";

export default function Home() {
  const { user, logout, isAuthenticated } = useAuth();
  const [, setLocation] = useLocation();

  const handleLogout = async () => {
    await logout();
    setLocation("/");
  };

  const handlePrint = () => {
    window.print();
  };

  // If not authenticated, show login page with background
  if (!isAuthenticated) {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-cover bg-center relative"
        style={{
          backgroundImage: `url('/profile-logo.png')`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Dark overlay */}
        <div className="absolute inset-0 bg-black/60"></div>

        {/* Login form */}
        <div className="relative z-10 bg-card/95 backdrop-blur border border-border rounded-lg p-8 max-w-md w-full mx-4 shadow-2xl">
          <h1 className="text-3xl font-bold text-accent text-center mb-2">
            Ethical Hacking Platform
          </h1>
          <p className="text-center text-muted-foreground mb-6">
            Zaloguj się, aby uzyskać dostęp do produktów
          </p>

          <div className="space-y-4">
            <a href={getLoginUrl()}>
              <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90">
                Zaloguj się przez Google
              </Button>
            </a>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-card text-muted-foreground">lub</span>
              </div>
            </div>

            <Button
              variant="outline"
              className="w-full border-accent text-accent hover:bg-accent hover:text-accent-foreground"
              onClick={() => setLocation("/register")}
            >
              Zarejestruj się
            </Button>
          </div>

          <p className="text-xs text-center text-muted-foreground mt-6">
            Bezpieczne logowanie przez Manus OAuth
          </p>
        </div>
      </div>
    );
  }

  // If authenticated, show CV or marketplace
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="container flex items-center justify-between py-4">
          <h1 className="text-3xl font-bold text-accent">Karen Tonoyan</h1>
          <div className="flex gap-3 items-center">
            {user?.role === "admin" && (
              <span className="text-sm bg-accent/20 text-accent px-3 py-1 rounded-full">
                Admin
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
              onClick={handlePrint}
            >
              <Download className="mr-2 h-4 w-4" />
              CV
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
              onClick={() => setLocation("/marketplace")}
            >
              <ShoppingCart className="mr-2 h-4 w-4" />
              Produkty
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
              onClick={() => setLocation("/books")}
            >
              📚 Książki
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
              onClick={() => setLocation("/lessons")}
            >
              🎓 Lekcje
            </Button>
            {user?.role === "admin" && (
              <Button
                variant="outline"
                size="sm"
                className="border-accent text-accent hover:bg-accent hover:text-accent-foreground"
                onClick={() => setLocation("/admin")}
              >
                Panel Admin
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
              onClick={handleLogout}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Wyloguj
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8">
        <div className="grid gap-8 lg:grid-cols-4">
          {/* Left Sidebar */}
          <aside className="lg:col-span-1">
            {/* Profile Photo */}
            <div className="mb-6 overflow-hidden rounded-lg border-2 border-accent bg-card">
              <img
                src="/login-bg.png"
                alt="Karen Tonoyan"
                className="w-full h-auto object-cover"
              />
            </div>

            {/* Personal Info */}
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-3 text-lg font-bold text-accent">Karen Tonoyan</h3>
                <p className="mb-4 text-sm text-foreground">
                  Profesjonalista z wieloletnim doświadczeniem
                </p>

                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-accent font-bold">📅</span>
                    <span>06.06.1986</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <MapPin className="h-4 w-4 text-accent flex-shrink-0 mt-0.5" />
                    <span>Marsa 1/3, 59-220 Legnica</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <Phone className="h-4 w-4 text-accent flex-shrink-0 mt-0.5" />
                    <span>796 230 413</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 text-accent flex-shrink-0 mt-0.5" />
                    <span className="break-all">karen.tonoyan@email.com</span>
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content Area */}
          <section className="lg:col-span-3 space-y-6">
            {/* Education */}
            <div className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 flex items-center text-2xl font-bold text-accent">
                <span className="mr-2">⭐</span>
                Wykształcenie
              </h2>
              <div className="space-y-4 border-l-2 border-accent pl-4">
                <div>
                  <p className="font-bold text-accent">2003-2005</p>
                  <p className="text-foreground">
                    Technikum Medyczne w Armenii "Hipokrat"
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Specjalność: technik protetyk
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">2005-2007</p>
                  <p className="text-foreground">
                    Jednostki Specjalne Rezerwowe (SAPER)
                  </p>
                </div>
              </div>
            </div>

            {/* Work Experience */}
            <div className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 flex items-center text-2xl font-bold text-accent">
                <span className="mr-2">💼</span>
                Doświadczenie Zawodowe
              </h2>
              <div className="space-y-4 border-l-2 border-accent pl-4">
                <div>
                  <p className="font-bold text-accent">2024 - 2025</p>
                  <p className="text-foreground">Castorama - Kierowca</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2023</p>
                  <p className="text-foreground">DPD - Kurier do 3,5t</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2019 - 2023</p>
                  <p className="text-foreground">Opiekun Medyczny w Niemczech</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2018 - 2019</p>
                  <p className="text-foreground">Hurtownia Gordon - Dostawca części</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2015 - 2018</p>
                  <p className="text-foreground">Multi grup - Magazynier, kierowca</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2013 - 2015</p>
                  <p className="text-foreground">Pizzeria "Hallo Pizza" - Pizzerman</p>
                </div>
                <div>
                  <p className="font-bold text-accent">2010 - 2013</p>
                  <p className="text-foreground">Pizzeria "Valentino" - Pizzerman</p>
                </div>
              </div>
            </div>

            {/* Languages */}
            <div className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 flex items-center text-2xl font-bold text-accent">
                <span className="mr-2">🌐</span>
                Języki Obce
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="font-bold text-accent">Angielski</p>
                  <p className="text-sm text-muted-foreground">
                    Podstawowy, komunikatywny
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Rosyjski</p>
                  <p className="text-sm text-muted-foreground">Bardzo dobrze</p>
                </div>
                <div>
                  <p className="font-bold text-accent">Ormiański</p>
                  <p className="text-sm text-muted-foreground">Celujący</p>
                </div>
                <div>
                  <p className="font-bold text-accent">Niemiecki</p>
                  <p className="text-sm text-muted-foreground">Komunikatywny</p>
                </div>
              </div>
            </div>

            {/* Skills */}
            <div className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 flex items-center text-2xl font-bold text-accent">
                <span className="mr-2">⚙️</span>
                Umiejętności
              </h2>
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <p className="font-bold text-accent mb-2">Obsługa komputera</p>
                  <p className="text-sm text-foreground">
                    Word, Excel, Photoshop, Corel Draw, Internet
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent mb-2">Inne umiejętności</p>
                  <p className="text-sm text-foreground">
                    Grafik dizajner, Fotograf, Ratownik (1 pomoc)
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent mb-2">Nowe technologie</p>
                  <p className="text-sm text-foreground">
                    Machine Learning, AI Development, Automatyzacja firm
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent mb-2">Bezpieczeństwo IT</p>
                  <p className="text-sm text-foreground">
                    Ethical Hacking, Cyberbezpieczeństwo
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent mb-2">Twórczość</p>
                  <p className="text-sm text-foreground">
                    Pisanie e-booków, Książek
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent mb-2">Prawo jazdy</p>
                  <p className="text-sm text-foreground">Kategoria B</p>
                </div>
              </div>
            </div>

            {/* Interests */}
            <div className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 flex items-center text-2xl font-bold text-accent">
                <span className="mr-2">✨</span>
                Zainteresowania
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="font-bold text-accent">Rozwój AI i ML</p>
                  <p className="text-sm text-muted-foreground">
                    Trenowanie modeli maszynowych, Tworzenie systemów AI
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Automatyzacja</p>
                  <p className="text-sm text-muted-foreground">
                    Optymalizacja procesów biznesowych
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Cyberbezpieczeństwo</p>
                  <p className="text-sm text-muted-foreground">
                    Ethical Hacking, Zabezpieczenia systemów
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Psychologia</p>
                  <p className="text-sm text-muted-foreground">
                    Uczenie i praktyka psychologiczna
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Pisanie</p>
                  <p className="text-sm text-muted-foreground">
                    Tworzenie książek i e-booków
                  </p>
                </div>
                <div>
                  <p className="font-bold text-accent">Edukacja</p>
                  <p className="text-sm text-muted-foreground">
                    Nauczanie nowych technologii
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6 mt-12">
        <div className="container text-center text-sm text-muted-foreground">
          <p>© 2025 Karen Tonoyan. Wszelkie prawa zastrzeżone.</p>
        </div>
      </footer>

      {/* Print Styles */}
      <style>{`
        @media print {
          header, footer {
            display: none;
          }
          body {
            background: white;
            color: black;
          }
          .border-accent {
            border-color: #d4af37 !important;
          }
          .text-accent {
            color: #d4af37 !important;
          }
          .bg-accent {
            background-color: #d4af37 !important;
          }
        }
      `}</style>
    </div>
  );
}
