"use client"

import { Trash2 } from "lucide-react"
import { useActionState } from "react"

import { deletePostAction } from "@/app/actions"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function DeletePostButton({ postId }: { postId: number }) {
  const [state, formAction, pending] = useActionState(deletePostAction.bind(null, postId), {
    error: null,
  })

  return (
    <AlertDialog>
      <AlertDialogTrigger render={<Button variant="destructive" />}>
        <Trash2 />
        삭제
      </AlertDialogTrigger>
      <AlertDialogContent>
        <form action={formAction} className="grid gap-4">
          <AlertDialogHeader>
            <AlertDialogTitle>게시글을 삭제할까요?</AlertDialogTitle>
            <AlertDialogDescription>
              삭제한 글은 되돌릴 수 없습니다. 작성할 때 입력한 비밀번호를 입력해 주세요.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="delete-password">비밀번호</Label>
            <Input
              id="delete-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
            {state.error && (
              <p role="alert" className="text-sm text-destructive">
                {state.error}
              </p>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">취소</AlertDialogCancel>
            <Button type="submit" variant="destructive" disabled={pending}>
              {pending ? "삭제 중..." : "삭제"}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  )
}
