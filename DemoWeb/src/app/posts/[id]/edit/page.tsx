import { notFound } from "next/navigation"
import { connection } from "next/server"
import { Suspense } from "react"

import { updatePostAction } from "@/app/actions"
import { PostForm } from "@/components/post-form"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getPost } from "@/lib/posts"

export const metadata = { title: "글 수정 | DemoWeb 게시판" }

export default function EditPostPage({ params }: PageProps<"/posts/[id]/edit">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글 수정</CardTitle>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <EditForm params={params} />
        </Suspense>
      </CardContent>
    </Card>
  )
}

async function EditForm({ params }: { params: PageProps<"/posts/[id]/edit">["params"] }) {
  await connection()
  const { id } = await params
  const postId = Number(id)
  if (!Number.isInteger(postId)) notFound()

  const post = await getPost(postId)
  if (!post) notFound()

  return (
    <PostForm
      action={updatePostAction.bind(null, post.id)}
      cancelHref={`/posts/${post.id}`}
      submitLabel="수정 완료"
      defaultValues={{ title: post.title, author: post.author, content: post.content }}
    />
  )
}
