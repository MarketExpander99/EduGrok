const badWords = ['badword', 'hate', 'violence']; // Expand list

export const safetyFilter = (content) => {
  let filtered = content;
  badWords.forEach(word => {
    filtered = filtered.replace(new RegExp(word, 'gi'), '***');
  });
  return filtered;
};