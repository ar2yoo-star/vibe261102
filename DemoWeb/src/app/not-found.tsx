import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="grid place-items-center gap-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">페이지를 찾을 수 없습니다</h1>
      <p className="text-muted-foreground">삭제되었거나 존재하지 않는 게시글입니다.</p>
      <Link href="/" className={buttonVariants()}>
        목록으로
      </Link>
    </div>
  )
}
