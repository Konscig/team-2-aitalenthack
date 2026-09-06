const slides = [...document.querySelectorAll('.slide')];
const counter = document.querySelector('#counter');
const progress = document.querySelector('#slide-progress');
const progressMarker = document.querySelector('#progress-marker');
let current = Math.max(0, Math.min(slides.length - 1, Number(location.hash.slice(1)) - 1 || 0));

function show(index, updateHash = true) {
  current = (index + slides.length) % slides.length;
  slides.forEach((slide, i) => slide.classList.toggle('active', i === current));
  counter.textContent = `${current + 1} / ${slides.length}`;
  progress.style.setProperty('--progress', current / (slides.length - 1));
  progressMarker.textContent = current + 1;
  document.title = `${current + 1}/${slides.length} — Выгодный момент для перевода`;
  if (updateHash) history.replaceState(null, '', `#${current + 1}`);
}

document.querySelector('#prev').addEventListener('click', () => show(current - 1));
document.querySelector('#next').addEventListener('click', () => show(current + 1));
document.querySelector('#fullscreen').addEventListener('click', () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
document.addEventListener('keydown', (event) => {
  if (['ArrowRight', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); show(current + 1); }
  if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); show(current - 1); }
  if (event.key === 'Home') show(0);
  if (event.key === 'End') show(slides.length - 1);
  if (event.key.toLowerCase() === 'f') document.querySelector('#fullscreen').click();
});
window.addEventListener('hashchange', () => show(Number(location.hash.slice(1)) - 1, false));

let touchX = 0;
document.addEventListener('touchstart', (event) => { touchX = event.changedTouches[0].clientX; }, { passive: true });
document.addEventListener('touchend', (event) => {
  const delta = event.changedTouches[0].clientX - touchX;
  if (Math.abs(delta) > 60) show(current + (delta < 0 ? 1 : -1));
}, { passive: true });

const frame = document.querySelector('#demo-frame');
const demoTabs = [...document.querySelectorAll('.demo-tab')];
demoTabs.forEach((tab) => tab.addEventListener('click', () => {
  frame.src = tab.dataset.src;
  demoTabs.forEach((item) => item.classList.toggle('active', item === tab));
  document.querySelector('.demo-tabs a').href = tab.dataset.fullSrc;
}));

show(current, false);
