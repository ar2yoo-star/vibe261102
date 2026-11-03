"use client"

import Link from "next/link"
import { useActionState } from "react"

import type { FormState } from "@/app/actions"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

type PostFormProps = {
  action: (prev: FormState, formData: FormData) => Promise<FormState>
  cancelHref: string
  submitLabel: string
  /** 수정 화면에서는 작성자를 바꿀 수 없으므로 읽기 전용으로 보여준다. */
  defaultValues?: { title: string; author: string; content: string }
}

export function PostForm({ action, cancelHref, submitLabel, defaultValues }: PostFormProps) {
  const [state, formAction, pending] = useActionState(action, { error: null })
  const isEdit = Boolean(defaultValues)
  const values = { ...defaultValues, ...state.values }

  return (
    <form action={formAction} className="grid gap-5">
      <div className="grid gap-2">
        <Label htmlFor="title">제목</Label>
        <Input
          id="title"
          name="title"
          maxLength={100}
          defaultValue={values.title}
          placeholder="제목을 입력하세요"
          required
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="author">작성자</Label>
          <Input
            id="author"
            name="author"
            maxLength={20}
            defaultValue={isEdit ? defaultValues?.author : values.author}
            placeholder="이름"
            readOnly={isEdit}
            disabled={isEdit}
            required={!isEdit}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">비밀번호</Label>
          <Input
            id="password"
            name="password"
            type="password"
            minLength={4}
            placeholder={isEdit ? "작성 시 입력한 비밀번호" : "수정·삭제 시 필요 (4자 이상)"}
            autoComplete={isEdit ? "current-password" : "new-password"}
            required
          />
        </div>
      </div>

      <div className="grid gap-2">
        <Label htmlFor="content">내용</Label>
        <Textarea
          id="content"
          name="content"
          maxLength={5000}
          defaultValue={values.content}
          placeholder="내용을 입력하세요"
          className="min-h-64"
          required
        />
      </div>

      {state.error && (
        <p role="alert" className="text-sm text-destructive">
          {state.error}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Link href={cancelHref} className={buttonVariants({ variant: "outline" })}>
          취소
        </Link>
        <Button type="submit" disabled={pending}>
          {pending ? "저장 중..." : submitLabel}
        </Button>
      </div>
    </form>
  )
}
