import Link from "next/link"
import { MessagesSquare, PenSquare } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"

export function SiteHeader() {
  return (
    <header className="border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <MessagesSquare className="size-5" />
          DemoWeb 게시판
        </Link>
        <Link href="/posts/new" className={buttonVariants({ size: "sm" })}>
          <PenSquare />
          글쓰기
        </Link>
      </div>
    </header>
  )
}
