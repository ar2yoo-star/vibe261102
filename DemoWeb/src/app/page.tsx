import Link from "next/link"
import { connection } from "next/server"
import { Suspense } from "react"
import { Search } from "lucide-react"

import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDate } from "@/lib/format"
import { listPosts } from "@/lib/posts"
import { cn } from "@/lib/utils"

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">자유게시판</CardTitle>
        <CardDescription>자유롭게 글을 남겨 주세요.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-muted-foreground">불러오는 중...</p>}>
          <PostList searchParams={searchParams} />
        </Suspense>
      </CardContent>
    </Card>
  )
}

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "")
}

async function PostList({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  await connection()
  const params = await searchParams
  const query = firstValue(params.q)
  const page = Number.parseInt(firstValue(params.page), 10) || 1
  const result = await listPosts({ query, page })

  const pageHref = (target: number) => {
    const next = new URLSearchParams()
    if (query) next.set("q", query)
    if (target > 1) next.set("page", String(target))
    const qs = next.toString()
    return qs ? `/?${qs}` : "/"
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {query ? `"${query}" 검색 결과 ` : "전체 글 "}
          <span className="font-medium text-foreground">{result.total}</span>개
        </p>
        <form action="/" className="flex gap-2">
          <Input
            name="q"
            defaultValue={query}
            placeholder="제목, 작성자, 내용 검색"
            className="sm:w-64"
            aria-label="검색어"
          />
          <Button type="submit" variant="outline">
            <Search />
            검색
          </Button>
        </form>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="hidden w-16 text-center sm:table-cell">번호</TableHead>
            <TableHead>제목</TableHead>
            <TableHead className="w-28">작성자</TableHead>
            <TableHead className="hidden w-28 text-center md:table-cell">작성일</TableHead>
            <TableHead className="hidden w-16 text-center sm:table-cell">조회</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.posts.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                {query ? "검색 결과가 없습니다." : "아직 작성된 글이 없습니다."}
              </TableCell>
            </TableRow>
          ) : (
            result.posts.map((post) => (
              <TableRow key={post.id}>
                <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                  {post.id}
                </TableCell>
                <TableCell className="max-w-0 truncate">
                  <Link href={`/posts/${post.id}`} className="font-medium hover:underline">
                    {post.title}
                  </Link>
                </TableCell>
                <TableCell className="truncate">{post.author}</TableCell>
                <TableCell className="hidden text-center text-muted-foreground md:table-cell">
                  {formatDate(post.createdAt)}
                </TableCell>
                <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                  {post.views}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {result.totalPages > 1 && (
        <nav aria-label="페이지" className="flex flex-wrap justify-center gap-1">
          {Array.from({ length: result.totalPages }, (_, i) => i + 1).map((n) => (
            <Link
              key={n}
              href={pageHref(n)}
              aria-current={n === result.page ? "page" : undefined}
              className={cn(
                buttonVariants({ variant: n === result.page ? "default" : "ghost", size: "icon-sm" }),
              )}
            >
              {n}
            </Link>
          ))}
        </nav>
      )}
    </div>
  )
}
