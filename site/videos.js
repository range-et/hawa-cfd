fetch('videos.json').then(response => {
  if (!response.ok) throw new Error('Videos unavailable');
  return response.json();
}).then(videos => {
  const target = document.getElementById('videos');
  target.replaceChildren(...videos.map(video => {
    const article = document.createElement('article');
    let player;
    if (video.id) {
      player = document.createElement('iframe');
      player.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.id)}`;
      player.title = video.title;
      player.loading = 'lazy';
      player.allowFullscreen = true;
      player.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      player.referrerPolicy = 'strict-origin-when-cross-origin';
    } else {
      player = document.createElement('video');
      player.controls = true;
      player.preload = 'none';
      player.playsInline = true;
      player.poster = video.poster;
      player.setAttribute('aria-label', video.title);
      const source = document.createElement('source');
      source.src = video.file;
      source.type = 'video/mp4';
      player.append(source);
    }
    const title = document.createElement('h3');
    title.textContent = video.title;
    const caption = document.createElement('p');
    caption.textContent = video.description;
    const link = document.createElement('a');
    link.href = video.id ? `https://youtu.be/${encodeURIComponent(video.id)}` : video.file;
    link.className = 'video-link';
    link.textContent = video.id ? 'Watch on YouTube ↗' : 'Download video ↗';
    article.append(player, title, caption, link);
    return article;
  }));
}).catch(() => {
  const target = document.getElementById('videos');
  const message = document.createElement('p');
  message.textContent = 'The video list is unavailable. Open the GitHub release to download the videos.';
  target.replaceChildren(message);
});
