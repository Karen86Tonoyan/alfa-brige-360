import { Button } from "@/components/ui/button";
import { ShoppingCart, BookOpen, Zap } from "lucide-react";
import { useLocation } from "wouter";

export default function Marketplace() {
  const [, setLocation] = useLocation();

  const products = [
    {
      id: 1,
      type: "book",
      title: "Książka - Ethical Hacking",
      description: "Kompletny przewodnik po bezpiecznym hakowaniu",
      price: 30,
      icon: BookOpen,
    },
    {
      id: 2,
      type: "ebook",
      title: "E-book - Cyberbezpieczeństwo",
      description: "Praktyczne wskazówki do ochrony systemów",
      price: 100,
      icon: Zap,
    },
    {
      id: 3,
      type: "course",
      title: "Kurs - Ethical Hacking",
      description: "Pełny kurs z certyfikatem",
      price: 200,
      icon: Zap,
    },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur">
        <div className="container flex items-center justify-between py-4">
          <h1 className="text-3xl font-bold text-accent">Produkty</h1>
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
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => {
            const Icon = product.icon;
            return (
              <div
                key={product.id}
                className="rounded-lg border border-border bg-card p-6 hover:border-accent transition-colors"
              >
                <div className="flex items-center justify-between mb-4">
                  <Icon className="h-8 w-8 text-accent" />
                  <span className="text-sm bg-accent/20 text-accent px-3 py-1 rounded-full">
                    {product.type === "book" && "Książka"}
                    {product.type === "ebook" && "E-book"}
                    {product.type === "course" && "Kurs"}
                  </span>
                </div>

                <h2 className="text-xl font-bold text-foreground mb-2">
                  {product.title}
                </h2>
                <p className="text-sm text-muted-foreground mb-4">
                  {product.description}
                </p>

                <div className="flex items-center justify-between">
                  <div className="text-2xl font-bold text-accent">
                    {product.price} zł
                  </div>
                  <Button className="bg-accent text-accent-foreground hover:bg-accent/90">
                    <ShoppingCart className="mr-2 h-4 w-4" />
                    Kup
                  </Button>
                </div>

                {product.type === "book" && (
                  <p className="text-xs text-muted-foreground mt-4">
                    Podział: 50% Manus, 50% Autor
                  </p>
                )}
                {product.type === "ebook" && (
                  <p className="text-xs text-muted-foreground mt-4">
                    Podział: 50% Manus, 50% Autor
                  </p>
                )}
                {product.type === "course" && (
                  <p className="text-xs text-muted-foreground mt-4">
                    Podział: 50% Manus, 50% Autor
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Contact Section */}
        <div className="mt-12 rounded-lg border border-accent bg-card p-8">
          <h2 className="text-2xl font-bold text-accent mb-4">
            Potrzebujesz pomocy
          </h2>
          <p className="text-muted-foreground mb-6">
            Skontaktuj sie z administratorem przez SMS:
          </p>
          <div className="bg-background border border-accent rounded-lg p-6 text-center">
            <p className="text-lg font-mono text-accent mb-2">
              796 230 413
            </p>
            <p className="text-sm text-muted-foreground">
              Wyslij SMS z pytaniem lub potwierdzeniem przelewu
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
