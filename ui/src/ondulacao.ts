// Onda que distorce a plataforma inteira a partir de um ponto, como uma gota na água.
// Técnica: feDisplacementMap com um mapa em anel gerado uma vez num canvas: na crista, cada
// pixel é empurrado para fora (direção radial, perfil senoidal, sem bordas). Por frame só o
// tamanho do anel e a intensidade mudam: o bitmap é reaproveitado e escalado pela GPU.

const ID = 'ondulacao'
const DURACAO_MS = 1500
const TAMANHO = 512 // resolução do mapa
const RAIO_INTERNO = 0.46 // começo da crista (fração do raio)
const RAIO_EXTERNO = 0.92 // fim da crista

function gerarAnel(): string {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = TAMANHO
  const ctx = canvas.getContext('2d')!
  const img = ctx.createImageData(TAMANHO, TAMANHO)
  const d = img.data
  const c = TAMANHO / 2
  for (let y = 0; y < TAMANHO; y++) {
    for (let x = 0; x < TAMANHO; x++) {
      const dx = x - c, dy = y - c
      const r = Math.hypot(dx, dy) / c
      let forca = 0
      if (r > RAIO_INTERNO && r < RAIO_EXTERNO) {
        const u = (r - RAIO_INTERNO) / (RAIO_EXTERNO - RAIO_INTERNO) // 0..1 na crista
        forca = Math.sin(u * Math.PI) // perfil suave: 0 → 1 → 0
      }
      const ang = Math.atan2(dy, dx)
      const i = (y * TAMANHO + x) * 4
      d[i] = 128 + 127 * forca * Math.cos(ang) // R: deslocamento em x (radial)
      d[i + 1] = 128 + 127 * forca * Math.sin(ang) // G: deslocamento em y (radial)
      d[i + 2] = 128
      d[i + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)
  return canvas.toDataURL('image/png')
}

let anelUrl: string | null = null

function garantirFiltro(): { imagem: SVGFEImageElement; mapa: SVGFEDisplacementMapElement } {
  let svg = document.getElementById(`${ID}-svg`) as SVGSVGElement | null
  if (!svg) {
    anelUrl ??= gerarAnel()
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.id = `${ID}-svg`
    svg.setAttribute('width', '0')
    svg.setAttribute('height', '0')
    svg.style.position = 'absolute'
    svg.innerHTML = `
      <filter id="${ID}" x="0" y="0" width="100%" height="100%" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
        <feImage id="${ID}-img" href="${anelUrl}" preserveAspectRatio="none" result="mapa"/>
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
export function ondular(alvo: HTMLElement, x: number, y: number, forca = 38) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const { imagem, mapa } = garantirFiltro()
  const caixa = alvo.getBoundingClientRect()
  const cx = x - caixa.left, cy = y - caixa.top
  // raio final: a crista (até 0.92 do raio) precisa passar pelo canto mais distante
  const alcance = Math.hypot(Math.max(cx, caixa.width - cx), Math.max(cy, caixa.height - cy)) / RAIO_INTERNO
  const filtroAnterior = alvo.style.filter
  alvo.classList.add('ondulando') // desliga os blurs enquanto a onda roda
  alvo.style.filter = `url(#${ID})`
  cancelAnimationFrame(animacao)
  const inicio = performance.now()

  const quadro = (agora: number) => {
    const t = Math.min((agora - inicio) / DURACAO_MS, 1)
    const avanco = 1 - Math.pow(1 - t, 1.8) // a onda sai rápido e vai desacelerando
    const raio = Math.max(alcance * avanco, 2)
    // intensidade: forte perto da origem, perde força ao se espalhar
    const intensidade = forca * Math.min(t * 6, 1) * Math.pow(1 - t, 1.3)
    imagem.setAttribute('x', (cx - raio).toFixed(1))
    imagem.setAttribute('y', (cy - raio).toFixed(1))
    imagem.setAttribute('width', (raio * 2).toFixed(1))
    imagem.setAttribute('height', (raio * 2).toFixed(1))
    mapa.setAttribute('scale', intensidade.toFixed(2))
    if (t < 1) animacao = requestAnimationFrame(quadro)
    else { alvo.style.filter = filtroAnterior; alvo.classList.remove('ondulando') }
  }
  animacao = requestAnimationFrame(quadro)
}
