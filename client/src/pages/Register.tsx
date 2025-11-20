import { Button } from "@/components/ui/button";
import { useLocation } from "wouter";
import { getLoginUrl } from "@/const";

export default function Register() {
  const [, setLocation] = useLocation();

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-cover bg-center relative"
      style={{
        backgroundColor: "#000000",
      }}
    >
      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/40"></div>

      {/* Registration form */}
      <div className="relative z-10 bg-card/95 backdrop-blur border border-border rounded-lg p-8 max-w-md w-full mx-4 shadow-2xl">
        <h1 className="text-3xl font-bold text-accent text-center mb-2">
          Rejestracja
        </h1>
        <p className="text-center text-muted-foreground mb-6">
          Utwórz konto, aby uzyskać dostęp do produktów
        </p>

        <div className="space-y-4">
          <a href={getLoginUrl()}>
            <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90">
              Zarejestruj się przez Google
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

          <div className="space-y-3">
            <input
              type="email"
              placeholder="Email"
              className="w-full px-4 py-2 rounded-lg border border-border bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:border-accent"
            />
            <input
              type="password"
              placeholder="Hasło"
              className="w-full px-4 py-2 rounded-lg border border-border bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:border-accent"
            />
            <input
              type="password"
              placeholder="Potwierdź hasło"
              className="w-full px-4 py-2 rounded-lg border border-border bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:border-accent"
            />
            <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90">
              Zarejestruj się
            </Button>
          </div>
        </div>

        <p className="text-center text-sm text-muted-foreground mt-6">
          Masz już konto?{" "}
          <button
            onClick={() => setLocation("/")}
            className="text-accent hover:underline font-bold"
          >
            Zaloguj się
          </button>
        </p>

        <p className="text-xs text-center text-muted-foreground mt-6">
          Bezpieczne logowanie przez Manus OAuth
        </p>
      </div>
    </div>
  );
}
