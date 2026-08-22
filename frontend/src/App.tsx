import { Md2WordApp } from './apps/md2word/Md2WordApp'

export function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Md2WordApp />
      </div>
    </div>
  )
}
