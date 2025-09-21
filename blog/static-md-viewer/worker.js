export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
          'Access-Control-Allow-Headers': '*',
        },
      });
    }

    // Only allow GET requests to markdown files
    if (request.method !== 'GET' || !url.pathname.endsWith('.md')) {
      return new Response('Not Found', { status: 404 });
    }

    try {
      // Get file from R2
      const objectKey = url.pathname.substring(1); // Remove leading slash
      const object = await env.R2_BUCKET.get(objectKey);

      if (!object) {
        return new Response('Not Found', { status: 404 });
      }

      // Return with CORS headers
      return new Response(object.body, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
          'Access-Control-Allow-Headers': '*',
          'Cache-Control': 'public, max-age=3600',
        },
      });
    } catch (error) {
      return new Response('Internal Server Error', { status: 500 });
    }
  },
};