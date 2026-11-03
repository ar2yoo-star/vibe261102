import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { promises as fs } from "node:fs"
import path from "node:path"

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

type Store = {
  nextId: number
  posts: Post[]
}

const DATA_DIR = path.join(process.cwd(), "data")
const DATA_FILE = path.join(DATA_DIR, "posts.json")

export const PAGE_SIZE = 10

// 같은 프로세스 안에서 파일 읽기/쓰기가 겹치지 않도록 모든 작업을 순서대로 실행한다.
let queue: Promise<unknown> = Promise.resolve()

function withLock<T>(fn: () => Promise<T>): Promise<T> {
  const run = queue.then(fn, fn)
  queue = run.catch(() => undefined)
  return run
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

function seed(): Store {
  const now = new Date().toISOString()
  const passwordHash = hashPassword("1234")
  return {
    nextId: 3,
    posts: [
      {
        id: 1,
        title: "DemoWeb 게시판에 오신 것을 환영합니다",
        content:
          "Next.js, shadcn/ui, TypeScript로 만든 게시판입니다.\n\n글쓰기 버튼으로 새 글을 작성해 보세요. 글을 수정하거나 삭제할 때는 작성할 때 입력한 비밀번호가 필요합니다.",
        author: "관리자",
        passwordHash,
        views: 0,
        createdAt: now,
        updatedAt: now,
      },
      {
        id: 2,
        title: "게시판 이용 안내",
        content:
          "- 제목, 작성자, 내용, 비밀번호는 모두 필수입니다.\n- 목록 상단의 검색창으로 제목·작성자·내용을 검색할 수 있습니다.\n- 이 샘플 글들의 비밀번호는 1234 입니다.",
        author: "관리자",
        passwordHash,
        views: 0,
        createdAt: now,
        updatedAt: now,
      },
    ],
  }
}

async function readStore(): Promise<Store> {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8")
    return JSON.parse(raw) as Store
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error
    const store = seed()
    await writeStore(store)
    return store
  }
}

async function writeStore(store: Store): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true })
  const tmp = `${DATA_FILE}.tmp`
  await fs.writeFile(tmp, JSON.stringify(store, null, 2), "utf8")
  await fs.rename(tmp, DATA_FILE)
}

function toPublic(post: Post): PublicPost {
  const { id, title, content, author, views, createdAt, updatedAt } = post
  return { id, title, content, author, views, createdAt, updatedAt }
}

export type PostListResult = {
  posts: PublicPost[]
  total: number
  page: number
  totalPages: number
}

export function listPosts({
  query = "",
  page = 1,
}: {
  query?: string
  page?: number
}): Promise<PostListResult> {
  return withLock(async () => {
    const { posts } = await readStore()
    const keyword = query.trim().toLowerCase()
    const filtered = posts
      .filter(
        (post) =>
          !keyword ||
          post.title.toLowerCase().includes(keyword) ||
          post.author.toLowerCase().includes(keyword) ||
          post.content.toLowerCase().includes(keyword)
      )
      .sort((a, b) => b.id - a.id)

    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
    const current = Math.min(Math.max(1, page), totalPages)
    const start = (current - 1) * PAGE_SIZE

    return {
      posts: filtered.slice(start, start + PAGE_SIZE).map(toPublic),
      total: filtered.length,
      page: current,
      totalPages,
    }
  })
}

export function getPost(id: number): Promise<PublicPost | null> {
  return withLock(async () => {
    const { posts } = await readStore()
    const post = posts.find((p) => p.id === id)
    return post ? toPublic(post) : null
  })
}

/** 조회수를 1 올리고 갱신된 게시글을 돌려준다. */
export function viewPost(id: number): Promise<PublicPost | null> {
  return withLock(async () => {
    const store = await readStore()
    const post = store.posts.find((p) => p.id === id)
    if (!post) return null
    post.views += 1
    await writeStore(store)
    return toPublic(post)
  })
}

export type PostInput = {
  title: string
  content: string
  author: string
  password: string
}

export function createPost(input: PostInput): Promise<PublicPost> {
  return withLock(async () => {
    const store = await readStore()
    const now = new Date().toISOString()
    const post: Post = {
      id: store.nextId++,
      title: input.title,
      content: input.content,
      author: input.author,
      passwordHash: hashPassword(input.password),
      views: 0,
      createdAt: now,
      updatedAt: now,
    }
    store.posts.push(post)
    await writeStore(store)
    return toPublic(post)
  })
}

export type MutationResult = "ok" | "not-found" | "wrong-password"

export function updatePost(
  id: number,
  input: Omit<PostInput, "author">,
): Promise<MutationResult> {
  return withLock(async () => {
    const store = await readStore()
    const post = store.posts.find((p) => p.id === id)
    if (!post) return "not-found"
    if (!verifyPassword(input.password, post.passwordHash)) return "wrong-password"
    post.title = input.title
    post.content = input.content
    post.updatedAt = new Date().toISOString()
    await writeStore(store)
    return "ok"
  })
}

export function deletePost(id: number, password: string): Promise<MutationResult> {
  return withLock(async () => {
    const store = await readStore()
    const index = store.posts.findIndex((p) => p.id === id)
    if (index === -1) return "not-found"
    if (!verifyPassword(password, store.posts[index].passwordHash)) return "wrong-password"
    store.posts.splice(index, 1)
    await writeStore(store)
    return "ok"
  })
}
