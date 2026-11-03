import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { neon, type NeonQueryFunction } from "@neondatabase/serverless"

export type Post = {
  id: number
  title: string
  content: string
  author: string
  passwordHash: string
  views: number
  createdAt: string
  updatedAt: string
}

/** 클라이언트로 내려보내도 되는 필드만 담은 게시글 */
export type PublicPost = Omit<Post, "passwordHash">

type PostRow = {
  id: number
  title: string
  content: string
  author: string
  views: number
  created_at: Date | string
  updated_at: Date | string
}

export const PAGE_SIZE = 10

// 빌드 중 페이지 정보를 모을 때도 이 모듈을 불러오므로, 연결은 첫 쿼리 시점에 만든다.
let client: NeonQueryFunction<false, false> | null = null

function db(): NeonQueryFunction<false, false> {
  if (!process.env.DATABASE_URL) {
    throw new Error(
      "DATABASE_URL 환경 변수가 없습니다. 로컬은 .env.local, Vercel은 프로젝트 Environment Variables에 설정해 주세요.",
    )
  }
  client ??= neon(process.env.DATABASE_URL)
  return client
}

export function hashPassword(password: string): string {
  const salt = randomBytes(16).toString("hex")
  const hash = scryptSync(password, salt, 32).toString("hex")
  return `${salt}:${hash}`
}

function verifyPassword(password: string, stored: string): boolean {
  const [salt, hash] = stored.split(":")
  if (!salt || !hash) return false
  const expected = Buffer.from(hash, "hex")
  const actual = scryptSync(password, salt, expected.length)
  return timingSafeEqual(expected, actual)
}

// 프로세스당 한 번만 테이블을 만들고, 비어 있으면 안내 글을 넣는다.
let schemaReady: Promise<void> | null = null

function ensureSchema(): Promise<void> {
  schemaReady ??= (async () => {
    await db()`
      CREATE TABLE IF NOT EXISTS posts (
        id            SERIAL PRIMARY KEY,
        title         TEXT NOT NULL,
        content       TEXT NOT NULL,
        author        TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        views         INTEGER NOT NULL DEFAULT 0,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `
    const [{ count }] = (await db()`SELECT count(*)::int AS count FROM posts`) as { count: number }[]
    if (count > 0) return

    const passwordHash = hashPassword("1234")
    await db().transaction([
      db()`
        INSERT INTO posts (title, content, author, password_hash)
        VALUES (
          'DemoWeb 게시판에 오신 것을 환영합니다',
          ${"Next.js, shadcn/ui, TypeScript로 만든 게시판입니다.\n\n글쓰기 버튼으로 새 글을 작성해 보세요. 글을 수정하거나 삭제할 때는 작성할 때 입력한 비밀번호가 필요합니다."},
          '관리자',
          ${passwordHash}
        )
      `,
      db()`
        INSERT INTO posts (title, content, author, password_hash)
        VALUES (
          '게시판 이용 안내',
          ${"- 제목, 작성자, 내용, 비밀번호는 모두 필수입니다.\n- 목록 상단의 검색창으로 제목·작성자·내용을 검색할 수 있습니다.\n- 이 샘플 글들의 비밀번호는 1234 입니다."},
          '관리자',
          ${passwordHash}
        )
      `,
    ])
  })().catch((error) => {
    schemaReady = null
    throw error
  })
  return schemaReady
}

function toIso(value: Date | string): string {
  return new Date(value).toISOString()
}

function toPublic(row: PostRow): PublicPost {
  return {
    id: row.id,
    title: row.title,
    content: row.content,
    author: row.author,
    views: row.views,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
  }
}

export type PostListResult = {
  posts: PublicPost[]
  total: number
  page: number
  totalPages: number
}

export async function listPosts({
  query = "",
  page = 1,
}: {
  query?: string
  page?: number
}): Promise<PostListResult> {
  await ensureSchema()
  // LIKE 와일드카드(%, _)와 이스케이프 문자를 그대로 검색되도록 처리한다.
  const keyword = query.trim()
  const pattern = `%${keyword.replace(/[\\%_]/g, (c) => `\\${c}`)}%`

  const [{ total }] = (await db()`
    SELECT count(*)::int AS total FROM posts
    WHERE ${keyword} = '' OR title ILIKE ${pattern} OR author ILIKE ${pattern} OR content ILIKE ${pattern}
  `) as { total: number }[]

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const current = Math.min(Math.max(1, page), totalPages)

  const rows = (await db()`
    SELECT id, title, content, author, views, created_at, updated_at FROM posts
    WHERE ${keyword} = '' OR title ILIKE ${pattern} OR author ILIKE ${pattern} OR content ILIKE ${pattern}
    ORDER BY id DESC
    LIMIT ${PAGE_SIZE} OFFSET ${(current - 1) * PAGE_SIZE}
  `) as PostRow[]

  return { posts: rows.map(toPublic), total, page: current, totalPages }
}

export async function getPost(id: number): Promise<PublicPost | null> {
  await ensureSchema()
  const rows = (await db()`
    SELECT id, title, content, author, views, created_at, updated_at FROM posts WHERE id = ${id}
  `) as PostRow[]
  return rows[0] ? toPublic(rows[0]) : null
}

/** 조회수를 1 올리고 갱신된 게시글을 돌려준다. */
export async function viewPost(id: number): Promise<PublicPost | null> {
  await ensureSchema()
  const rows = (await db()`
    UPDATE posts SET views = views + 1 WHERE id = ${id}
    RETURNING id, title, content, author, views, created_at, updated_at
  `) as PostRow[]
  return rows[0] ? toPublic(rows[0]) : null
}

export type PostInput = {
  title: string
  content: string
  author: string
  password: string
}

export async function createPost(input: PostInput): Promise<PublicPost> {
  await ensureSchema()
  const rows = (await db()`
    INSERT INTO posts (title, content, author, password_hash)
    VALUES (${input.title}, ${input.content}, ${input.author}, ${hashPassword(input.password)})
    RETURNING id, title, content, author, views, created_at, updated_at
  `) as PostRow[]
  return toPublic(rows[0])
}

export type MutationResult = "ok" | "not-found" | "wrong-password"

async function checkPassword(id: number, password: string): Promise<MutationResult> {
  const rows = (await db()`SELECT password_hash FROM posts WHERE id = ${id}`) as {
    password_hash: string
  }[]
  if (!rows[0]) return "not-found"
  return verifyPassword(password, rows[0].password_hash) ? "ok" : "wrong-password"
}

export async function updatePost(
  id: number,
  input: Omit<PostInput, "author">,
): Promise<MutationResult> {
  await ensureSchema()
  const check = await checkPassword(id, input.password)
  if (check !== "ok") return check
  const rows = await db()`
    UPDATE posts SET title = ${input.title}, content = ${input.content}, updated_at = now()
    WHERE id = ${id}
    RETURNING id
  `
  return rows.length ? "ok" : "not-found"
}

export async function deletePost(id: number, password: string): Promise<MutationResult> {
  await ensureSchema()
  const check = await checkPassword(id, password)
  if (check !== "ok") return check
  const rows = await db()`DELETE FROM posts WHERE id = ${id} RETURNING id`
  return rows.length ? "ok" : "not-found"
}
