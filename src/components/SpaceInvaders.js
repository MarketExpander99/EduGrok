import { useEffect, useRef, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import p5 from 'p5';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

function SpaceInvaders() {
  const sketchRef = useRef();
  const [score, setScore] = useState(0);
  const [gameOver, setGameOver] = useState(false);

  useEffect(() => {
    const sketch = p => {
      let player, bullets = [], enemies = [];
      p.setup = () => {
        p.createCanvas(400, 400);
        player = { x: 200, y: 360, w: 40, h: 20 };
        for (let i = 0; i < 5; i++) {
          enemies.push({ x: 50 + i * 60, y: 50, w: 40, h: 20 });
        }
      };
      p.draw = () => {
        p.background(0);
        p.fill(255);
        p.rect(player.x, player.y, player.w, player.h);
        enemies.forEach(enemy => p.rect(enemy.x, enemy.y, enemy.w, enemy.h));
        bullets.forEach(bullet => {
          p.rect(bullet.x, bullet.y, 5, 10);
          bullet.y -= 5;
          enemies = enemies.filter(enemy => {
            if (
              bullet.x > enemy.x &&
              bullet.x < enemy.x + enemy.w &&
              bullet.y > enemy.y &&
              bullet.y < enemy.y + enemy.h
            ) {
              setScore(s => s + 10);
              return false;
            }
            return true;
          });
        });
        bullets = bullets.filter(b => b.y > 0);
        if (p.frameCount % 60 === 0) {
          enemies.forEach(e => e.y += 10);
          if (enemies.some(e => e.y > 350)) {
            setGameOver(true);
          }
        }
        if (gameOver) {
          p.noLoop();
          p.textSize(32);
          p.textAlign(p.CENTER);
          p.text('Game Over', 200, 200);
          p.text(`Score: ${score}`, 200, 250);
        }
      };
      p.keyPressed = () => {
        if (p.keyCode === p.LEFT_ARROW) player.x = Math.max(0, player.x - 10);
        if (p.keyCode === p.RIGHT_ARROW) player.x = Math.min(400 - player.w, player.x + 10);
        if (p.key === ' ' && !gameOver) bullets.push({ x: player.x + player.w / 2, y: player.y });
      };
    };
    const p5Instance = new p5(sketch, sketchRef.current);
    return () => p5Instance.remove();
  }, [gameOver, score]);

  useEffect(() => {
    if (gameOver && score > 0) {
      supabase.from('game_scores').insert({
        user_id: window.Clerk?.user?.id,
        game: 'Space Invaders',
        score
      }).then(({ error }) => {
        if (error) console.error('Error saving score:', error);
      });
    }
  }, [gameOver, score]);

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Space Invaders</h2>
      <div ref={sketchRef}></div>
      <p className="mt-4">Score: {score}</p>
      {gameOver && <p className="text-red-500">Game Over! Your score has been saved.</p>}
    </div>
  );
}

export default SpaceInvaders;