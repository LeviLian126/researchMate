import { ArrowRight, Github } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "./BrandLogo";

interface AuthViewProps {
  onDemo?: () => void;
}

export function AuthView({ onDemo }: AuthViewProps) {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-gradient-to-br from-accent via-background to-background p-6">
      <div className="w-full max-w-md">
        {/* Glass auth panel */}
        <div className="rounded-2xl border border-white/30 bg-white/70 p-8 shadow-xl shadow-primary/5 backdrop-blur-xl sm:p-10">
          <BrandLogo className="mb-8" />

          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Research workspace for rigorous minds
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
            Private conversations, cited answers, source libraries, and project
            quizzes.
          </p>

          <div className="mt-8 flex flex-col gap-3">
            <Button className="h-11 w-full justify-center gap-2 rounded-lg bg-foreground text-background hover:bg-foreground/90">
              <Github className="h-4 w-4" strokeWidth={1.5} />
              Continue with GitHub
            </Button>
            <Button
              variant="outline"
              onClick={onDemo}
              className="h-11 w-full justify-center gap-2 rounded-lg"
            >
              Try demo mode
              <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
            </Button>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Open source · MIT licensed
        </p>
      </div>
    </div>
  );
}
