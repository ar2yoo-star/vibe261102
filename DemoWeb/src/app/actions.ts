"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import * as posts from "@/lib/posts"

export type FormState = {
  error: string | null
  /** 실패 시 React가 폼을 초기화해도 입력값이 남도록 제출값을 되돌려준다. */
  values?: { title: string; author?: string; content: string }
}

const LIMITS = { title: 100, author: 20, content: 5000 }

function readField(formData: FormData, name: string): string {
  const value = formData.get(name)
  return typeof value === "string" ? value.trim() : ""
}

function validate(fields: Record<string, string>): string | null {
  if (!fields.title) return "제목을 입력해 주세요."
  if (fields.title.length > LIMITS.title) return `제목은 ${LIMITS.title}자 이하로 입력해 주세요.`
  if ("author" in fields) {
    if (!fields.author) return "작성자를 입력해 주세요."
    if (fields.author.length > LIMITS.author) return `작성자는 ${LIMITS.author}자 이하로 입력해 주세요.`
  }
  if (!fields.content) return "내용을 입력해 주세요."
  if (fields.content.length > LIMITS.content) return `내용은 ${LIMITS.content}자 이하로 입력해 주세요.`
  if (fields.password.length < 4) return "비밀번호는 4자 이상 입력해 주세요."
  return null
}

const RESULT_MESSAGES: Record<Exclude<posts.MutationResult, "ok">, string> = {
  "not-found": "게시글을 찾을 수 없습니다.",
  "wrong-password": "비밀번호가 일치하지 않습니다.",
}

export async function createPostAction(_prev: FormState, formData: FormData): Promise<FormState> {
  const fields = {
    title: readField(formData, "title"),
    author: readField(formData, "author"),
    content: readField(formData, "content"),
    password: readField(formData, "password"),
  }
  const values = { title: fields.title, author: fields.author, content: fields.content }
  const error = validate(fields)
  if (error) return { error, values }

  const post = await posts.createPost(fields)
  revalidatePath("/")
  redirect(`/posts/${post.id}`)
}

export async function updatePostAction(
  id: number,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const fields = {
    title: readField(formData, "title"),
    content: readField(formData, "content"),
    password: readField(formData, "password"),
  }
  const values = { title: fields.title, content: fields.content }
  const error = validate(fields)
  if (error) return { error, values }

  const result = await posts.updatePost(id, fields)
  if (result !== "ok") return { error: RESULT_MESSAGES[result], values }

  revalidatePath("/")
  revalidatePath(`/posts/${id}`)
  redirect(`/posts/${id}`)
}

export async function deletePostAction(
  id: number,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const password = readField(formData, "password")
  if (!password) return { error: "비밀번호를 입력해 주세요." }

  const result = await posts.deletePost(id, password)
  if (result !== "ok") return { error: RESULT_MESSAGES[result] }

  revalidatePath("/")
  redirect("/")
}
