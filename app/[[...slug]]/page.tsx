import type { ReactNode } from 'react'
import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'

export const generateStaticParams = generateStaticParamsFor('slug')

export async function generateMetadata({ params }: { params: Promise<{ slug?: string[] }> }) {
  const resolved = await params
  const slug = resolved?.slug ?? []
  const { metadata } = await importPage(slug)
  return metadata
}

interface PageParams {
  slug?: string[]
}

interface PageProps {
  params: Promise<PageParams>
}

const DefaultWrapper = ({ children }: { children: ReactNode }) => <>{children}</>

export default async function Page(props: PageProps) {
  const resolved = await props.params
  const slug = resolved?.slug ?? []
  const { default: MDXContent, toc, metadata } = await importPage(slug)
  const components = getMDXComponents({})
  const Wrapper = components.wrapper ?? DefaultWrapper

  return (
    <Wrapper toc={toc} metadata={metadata}>
      <MDXContent params={resolved} />
    </Wrapper>
  )
}
