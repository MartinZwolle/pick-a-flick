(() => {
  const form = document.getElementById('night-form');
  const loading = document.getElementById('expert-loading');
  const line = document.getElementById('expert-line');
  const button = form.querySelector('button');
  let timer;
  form.addEventListener('submit', event => {
    if (!form.querySelector('[name=viewers]:checked')) {
      event.preventDefault();
      form.querySelector('[name=viewers]')?.focus();
      return;
    }
    if (form.querySelector('[name=mode]:checked')?.value !== 'ai') return;
    const wish = document.getElementById('film-wish');
    if (!wish.value.trim()) { event.preventDefault(); wish.focus(); return; }
    const texts = ['De filmspoel wordt opgewarmd…', 'Onverwachte filmfamilies bij elkaar gezet…',
      'Popcorn voor de filmkenner geregeld…', 'Titels worden langs TMDb gehouden…',
      'Streamingdiensten krijgen een zaklampcontrole…', 'De aftiteling mag nog even wachten…'];
    if (/muppet|kermit/i.test(wish.value)) texts.splice(1, 0, 'Duikuitrusting voor Kermit geregeld…');
    if (/zweden|sweden/i.test(wish.value)) texts.splice(2, 0, 'Muppets in Zweden gelokaliseerd…');
    if (/ruimte|space|sterren/i.test(wish.value)) texts.push('Zuurstof voor de ruimtebioscoop bijgevuld…');
    if (/eng|horror|griezel/i.test(wish.value)) texts.push('Monsters onder de bioscoopstoel gecontroleerd…');
    loading.hidden = false;
    form.setAttribute('aria-busy', 'true');
    button.disabled = true;
    let i = 0;
    timer = setInterval(() => { line.textContent = texts[++i % texts.length]; }, 2800);
  });
  window.addEventListener('pageshow', () => {
    clearInterval(timer); loading.hidden = true; button.disabled = false;
    form.removeAttribute('aria-busy');
  });
})();
