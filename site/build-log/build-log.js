(async () => {
  const film = document.getElementById('release-film');
  const response = await fetch('../assets/v05/storyboard.json');
  if (!response.ok) return;
  const data = await response.json();
  const chosen = [0, 1, 6, 9, 12, 14, 17, 19, 21, 22];
  const stamp = value => `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
  data.chapters.forEach((scene, index) => {
    if (chosen.includes(index)) {
      const button = document.createElement('button'); button.type = 'button';
      const time = document.createElement('time'); time.textContent = stamp(scene.start_seconds);
      button.append(time, document.createTextNode(scene.title));
      button.addEventListener('click', () => { film.src = `https://www.youtube-nocookie.com/embed/6oiTFRT7qRg?start=${scene.start_seconds}&autoplay=1`; film.scrollIntoView({block: 'start'}); });
      document.getElementById('chapters').append(button);
    }
    const heading = document.createElement('h3'); heading.textContent = `${stamp(scene.start_seconds)} · ${scene.title}`;
    const copy = document.createElement('p'); copy.textContent = scene.caption;
    document.getElementById('transcript').append(heading, copy);
  });
})().catch(() => {
  document.getElementById('chapters').textContent = 'Use the video controls to browse the walkthrough.';
});
