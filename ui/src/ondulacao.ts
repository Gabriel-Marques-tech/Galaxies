// Onda que distorce a plataforma inteira a partir de um ponto, como uma gota na água.
// Técnica: filtro SVG feDisplacementMap cujo mapa é um anel (gradiente radial) que cresce
// a partir da origem; a intensidade sobe e cai, e o anel vai ficando mais largo e suave.

const ID = 'ondulacao'
const DURACAO_MS = 1300

// Anel: cinza (128) = sem deslocamento; a faixa clara/escura desloca os pixels ao passar.
const ANEL =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <defs><radialGradient id="g">
        <stop offset="0.52" stop-color="rgb(128,128,128)"/>
        <stop offset="0.66" stop-color="rgb(96,160,128)"/>
        <stop offset="0.80" stop-color="rgb(176,96,128)"/>
        <stop offset="0.92" stop-color="rgb(128,128,128)"/>
      </radialGradient></defs>
      <rect width="100" height="100" fill="rgb(128,128,128)"/>
      <circle cx="50" cy="50" r="50" fill="url(#g)"/>
    </svg>`,
  )

function garantirFiltro(): { imagem: SVGFEImageElement; mapa: SVGFEDisplacementMapElement } {
  let svg = document.getElementById(`${ID}-svg`) as SVGSVGElement | null
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.id = `${ID}-svg`
    svg.setAttribute('width', '0')
    svg.setAttribute('height', '0')
    svg.style.position = 'absolute'
    svg.innerHTML = `
      <filter id="${ID}" x="0" y="0" width="100%" height="100%" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
        <feImage id="${ID}-img" href="${ANEL}" preserveAspectRatio="none" result="mapa"/>
        <feDisplacementMap id="${ID}-map" in="SourceGraphic" in2="mapa" scale="0" xChannelSelector="R" yChannelSelector="G"/>
      </filter>`
    document.body.appendChild(svg)
  }
  return {
    imagem: document.getElementById(`${ID}-img`) as unknown as SVGFEImageElement,
    mapa: document.getElementById(`${ID}-map`) as unknown as SVGFEDisplacementMapElement,
  }
}

let animacao = 0

/** Dispara a onda no elemento `alvo`, saindo do ponto (x, y) em px da tela. */
export function ondular(alvo: HTMLElement, x: number, y: number, forca = 40) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const { imagem, mapa } = garantirFiltro()
  const caixa = alvo.getBoundingClientRect()
  const cx = x - caixa.left, cy = y - caixa.top
  const alcance = Math.hypot(Math.max(cx, caixa.width - cx), Math.max(cy, caixa.height - cy)) * 1.25
  const filtroAnterior = alvo.style.filter
  alvo.classList.add('ondulando') // desliga os blurs enquanto a onda roda
  alvo.style.filter = `url(#${ID})`
  alvo.style.willChange = 'filter'
  cancelAnimationFrame(animacao)
  const inicio = performance.now()

  const quadro = (agora: number) => {
    const t = Math.min((agora - inicio) / DURACAO_MS, 1)
    const suave = 1 - Math.pow(1 - t, 2.2) // a onda acelera no começo e desacelera no fim
    const raio = Math.max(alcance * suave, 1)
    // intensidade: sobe rápido, cai devagar; a onda perde força conforme se espalha
    const intensidade = forca * Math.sin(Math.PI * Math.min(t * 1.15, 1)) * (1 - 0.45 * t)
    imagem.setAttribute('x', String(cx - raio))
    imagem.setAttribute('y', String(cy - raio))
    imagem.setAttribute('width', String(raio * 2))
    imagem.setAttribute('height', String(raio * 2))
    mapa.setAttribute('scale', intensidade.toFixed(2))
    if (t < 1) animacao = requestAnimationFrame(quadro)
    else { alvo.style.filter = filtroAnterior; alvo.style.willChange = ''; alvo.classList.remove('ondulando') }
  }
  animacao = requestAnimationFrame(quadro)
}
