import Link from "next/link"
import { notFound } from "next/navigation"
import { connection } from "next/server"
import { Suspense } from "react"
import { ArrowLeft, Pencil } from "lucide-react"

import { DeletePostButton } from "@/components/delete-post-button"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { formatDateTime } from "@/lib/format"
import { viewPost } from "@/lib/posts"

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
      <PostDetail params={params} />
    </Suspense>
  )
}

async function PostDetail({ params }: { params: PageProps<"/posts/[id]">["params"] }) {
  await connection()
  const { id } = await params
  const postId = Number(id)
  if (!Number.isInteger(postId)) notFound()

  const post = await viewPost(postId)
  if (!post) notFound()

  const edited = post.updatedAt !== post.createdAt

  return (
    <Card>
      <CardHeader className="gap-3">
        <CardTitle className="text-2xl break-words">{post.title}</CardTitle>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{post.author}</span>
          <span>{formatDateTime(post.createdAt)}</span>
          {edited && <span>(수정됨 {formatDateTime(post.updatedAt)})</span>}
          <span>조회 {post.views}</span>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="min-h-48 py-6 whitespace-pre-wrap break-words leading-7">
        {post.content}
      </CardContent>
      <CardFooter className="flex flex-wrap justify-between gap-2">
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          <ArrowLeft />
          목록
        </Link>
        <div className="flex gap-2">
          <Link href={`/posts/${post.id}/edit`} className={buttonVariants({ variant: "secondary" })}>
            <Pencil />
            수정
          </Link>
          <DeletePostButton postId={post.id} />
        </div>
      </CardFooter>
    </Card>
  )
}
