fetch('videos.json').then(response => { if (!response.ok) throw new Error('Videos unavailable'); return response.json(); }).then(videos => {
  if (!videos.length) return;
  const target = document.getElementById('videos');
  target.replaceChildren(...videos.map(video => {
    const article = document.createElement('article');
    const frame = document.createElement('iframe');
    frame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.id)}`;
    frame.title = video.title; frame.loading = 'lazy'; frame.allowFullscreen = true;
    frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    const title = document.createElement('h3'); title.textContent = video.title;
    const caption = document.createElement('p'); caption.textContent = video.description;
    const link = document.createElement('a'); link.href = `https://youtu.be/${encodeURIComponent(video.id)}`; link.className = 'video-link'; link.textContent = 'Watch on YouTube ↗';
    article.append(frame, title, caption, link); return article;
  }));
}).catch(() => {});
