import { NextResponse } from 'next/server'
import fs from 'fs/promises'
import path from 'path'
import matter from 'gray-matter'

const CONTENT_DIR = path.join(process.cwd(), 'content')
const POSTS_DIR = path.join(CONTENT_DIR, 'posts')

async function collectPosts() {
  const entries = await fs.readdir(POSTS_DIR, { withFileTypes: true })
  const files = entries.filter((entry) => entry.isFile() && /\.mdx?$/.test(entry.name))
  const posts = await Promise.all(
    files.map(async (entry) => {
      const slug = entry.name.replace(/\.mdx?$/, '')
      const fullPath = path.join(POSTS_DIR, entry.name)
      const source = await fs.readFile(fullPath, 'utf-8')
      const { data } = matter(source)
      return {
        slug,
        title: data.title ?? slug,
        date: data.date ?? null,
        description: data.description ?? '',
        tag: data.tag ?? data.tags ?? null
      }
    })
  )
  return posts
}

export async function GET() {
  try {
    const posts = await collectPosts()
    return NextResponse.json({ posts })
  } catch (error) {
    console.error('[api/posts] failed to read posts', error)
    return NextResponse.json({ error: 'Failed to read posts metadata' }, { status: 500 })
  }
}
