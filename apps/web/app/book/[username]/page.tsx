import { CalendarIcon, Clock, Globe } from "lucide-react"

export default async function BookingPage({ params }: { params: Promise<{ username: string }> }) {
  const resolvedParams = await params;
  
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-4 selection:bg-primary selection:text-primary-foreground">
      <div className="w-full max-w-2xl bg-secondary/20 border border-border rounded-xl p-8 backdrop-blur-xl">
        <div className="mb-8 border-b border-border/50 pb-6">
          <h1 className="text-3xl font-serif tracking-tight text-primary mb-2">
            Meet with {resolvedParams.username}
          </h1>
          <p className="text-muted-foreground flex items-center gap-2">
            <Globe className="h-4 w-4" /> Timezone automatically adjusted to your locale
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h2 className="font-medium text-lg mb-4 text-primary">Available Today</h2>
            <div className="space-y-3">
              {["10:00 AM", "11:30 AM", "2:15 PM", "4:00 PM"].map((time) => (
                <button 
                  key={time}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-border bg-background hover:border-primary transition-all group"
                >
                  <span className="font-medium">{time}</span>
                  <span className="text-xs text-muted-foreground group-hover:text-primary transition-colors">Select</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <h2 className="font-medium text-lg mb-4 text-primary">Meeting Details</h2>
            <div className="bg-background rounded-lg border border-border p-4 space-y-4">
              <div className="flex items-start gap-3">
                <Clock className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div>
                  <h3 className="font-medium">30 Minute Sync</h3>
                  <p className="text-sm text-muted-foreground">General catch-up or introductory call.</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CalendarIcon className="h-5 w-5 text-muted-foreground mt-0.5" />
                <div>
                  <h3 className="font-medium">Fluid Scheduling</h3>
                  <p className="text-sm text-muted-foreground">Horolog protects focus time by default. Picking a slot here will automatically shuffle {resolvedParams.username}&apos;s flexible tasks.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
