const TAG_WHITELIST = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li',
  'blockquote', 'code', 'pre',
  'a', 'img',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'div', 'span',
]

const ATTR_WHITELIST = {
  'a': ['href', 'title', 'target'],
  'img': ['src', 'alt', 'title', 'width', 'height'],
  '*': ['class', 'style'],
}

const PROTOCOL_WHITELIST = ['http:', 'https:', 'mailto:', 'tel:']

export function sanitizeHtml(html) {
  if (!html || typeof html !== 'string') return ''
  
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  
  function cleanNode(node) {
    const children = Array.from(node.childNodes)
    children.forEach(child => {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const tagName = child.tagName.toLowerCase()
        
        if (!TAG_WHITELIST.includes(tagName)) {
          child.replaceWith(...child.childNodes)
          return
        }
        
        const allowedAttrs = ATTR_WHITELIST[tagName] || []
        const globalAttrs = ATTR_WHITELIST['*'] || []
        const allAllowed = [...allowedAttrs, ...globalAttrs]
        
        Array.from(child.attributes).forEach(attr => {
          const attrName = attr.name.toLowerCase()
          
          if (!allAllowed.includes(attrName)) {
            child.removeAttribute(attr.name)
            return
          }
          
          if (attrName === 'href' || attrName === 'src') {
            try {
              const url = new URL(attr.value, window.location.origin)
              if (!PROTOCOL_WHITELIST.includes(url.protocol)) {
                child.removeAttribute(attr.name)
              }
            } catch {
              child.removeAttribute(attr.name)
            }
          }
          
          if (attrName === 'style' && /javascript:/i.test(attr.value)) {
            child.removeAttribute(attr.name)
          }
        })
        
        if (tagName === 'a') {
          child.setAttribute('target', '_blank')
          child.setAttribute('rel', 'noopener noreferrer')
        }
        
        cleanNode(child)
      } else if (child.nodeType === Node.COMMENT_NODE) {
        child.remove()
      }
    })
  }
  
  cleanNode(doc.body)
  return doc.body.innerHTML
}

export function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}
