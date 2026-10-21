// Onda que distorce a plataforma inteira ao trocar o modo, como uma gota na água.
// Técnica: feTurbulence + feDisplacementMap (caminho de GPU no Chrome). A amplitude sobe e
// cai; a frequência do ruído cai com o tempo, então as ondas ficam mais longas e suaves,
// como uma onda que se espalha e perde força. Sem imagem de mapa: nada de costura.

const ID = 'ondulacao'
const DURACAO_MS = 1400
const FREQ_INICIAL = 0.018
const FREQ_FINAL = 0.004

function garantirFiltro(): { ruido: SVGFETurbulenceElement; mapa: SVGFEDisplacementMapElement } {
  let svg = document.getElementById(`${ID}-svg`) as SVGSVGElement | null
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.id = `${ID}-svg`
    svg.setAttribute('width', '0')
    svg.setAttribute('height', '0')
    svg.style.position = 'absolute'
    svg.innerHTML = `
      <filter id="${ID}" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
        <feTurbulence id="${ID}-ruido" type="fractalNoise" baseFrequency="${FREQ_INICIAL}" numOctaves="1" seed="7" result="ruido"/>
        <feDisplacementMap id="${ID}-map" in="SourceGraphic" in2="ruido" scale="0" xChannelSelector="R" yChannelSelector="G"/>
      </filter>`
    document.body.appendChild(svg)
  }
  return {
    ruido: document.getElementById(`${ID}-ruido`) as unknown as SVGFETurbulenceElement,
    mapa: document.getElementById(`${ID}-map`) as unknown as SVGFEDisplacementMapElement,
  }
}

let animacao = 0

/** Dispara a onda no elemento `alvo`. A origem (x, y) só muda a semente do ruído. */
export function ondular(alvo: HTMLElement, x: number, y: number, forca = 34) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const { ruido, mapa } = garantirFiltro()
  ruido.setAttribute('seed', String(Math.round((x + y) % 97)))
  const filtroAnterior = alvo.style.filter
  alvo.classList.add('ondulando') // desliga os blurs enquanto a onda roda
  alvo.style.filter = `url(#${ID})`
  cancelAnimationFrame(animacao)
  const inicio = performance.now()
  let ultimaFreq = -1

  const quadro = (agora: number) => {
    const t = Math.min((agora - inicio) / DURACAO_MS, 1)
    // amplitude: sobe rápido (0→0.25), cai devagar; frequência cai (ondas se alongam)
    const amplitude = forca * (t < 0.25 ? Math.sin((t / 0.25) * (Math.PI / 2)) : Math.pow(1 - (t - 0.25) / 0.75, 1.6))
    const freq = FREQ_INICIAL + (FREQ_FINAL - FREQ_INICIAL) * Math.sqrt(t)
    mapa.setAttribute('scale', amplitude.toFixed(2))
    // o ruído só é regerado quando a frequência muda de forma visível
    if (Math.abs(freq - ultimaFreq) > 0.0006) { ruido.setAttribute('baseFrequency', freq.toFixed(4)); ultimaFreq = freq }
    if (t < 1) animacao = requestAnimationFrame(quadro)
    else { alvo.style.filter = filtroAnterior; alvo.classList.remove('ondulando') }
  }
  animacao = requestAnimationFrame(quadro)
}
