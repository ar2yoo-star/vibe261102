import { createPostAction } from "@/app/actions"
import { PostForm } from "@/components/post-form"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const metadata = { title: "글쓰기 | DemoWeb 게시판" }

export default function NewPostPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글쓰기</CardTitle>
      </CardHeader>
      <CardContent>
        <PostForm action={createPostAction} cancelHref="/" submitLabel="등록" />
      </CardContent>
    </Card>
  )
}
