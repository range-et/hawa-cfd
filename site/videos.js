fetch('videos.json?v=20261108-v04').then(response => {
  if (!response.ok) throw new Error('Videos unavailable');
  return response.json();
}).then(videos => {
  const target = document.getElementById('videos');
  const published = videos.filter(video => /^[A-Za-z0-9_-]{11}$/.test(video.id || ''));
  if (!published.length) {
    const message = document.createElement('p');
    message.textContent = 'The YouTube videos will appear here after publication.';
    target.replaceChildren(message);
    return;
  }
  target.replaceChildren(...published.map(video => {
    const article = document.createElement('article');
    const player = document.createElement('iframe');
    player.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.id)}`;
    player.title = video.title;
    player.loading = 'lazy';
    player.allowFullscreen = true;
    player.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    player.referrerPolicy = 'strict-origin-when-cross-origin';
    const title = document.createElement('h3');
    title.textContent = video.title;
    const caption = document.createElement('p');
    caption.textContent = video.description;
    const link = document.createElement('a');
    link.href = `https://youtu.be/${encodeURIComponent(video.id)}`;
    link.className = 'video-link';
    link.textContent = 'Watch on YouTube ↗';
    article.append(player, title, caption, link);
    return article;
  }));
}).catch(() => {
  const target = document.getElementById('videos');
  const message = document.createElement('p');
  message.textContent = 'The video list is unavailable. Please try again later.';
  target.replaceChildren(message);
});
