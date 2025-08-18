import React, { useRef, useEffect, useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import p5 from 'p5';
import { supabase } from '../utils/api';

const Game = () => {
  const { user } = useUser();
  const sketchRef = useRef();
  const [score, setScore] = useState(0);

  useEffect(() => {
    if (!user) return;

    const sketch = (p) => {
      p.setup = () => {
        p.createCanvas(400, 400);
        p.background(220);
      };
      p.draw = () => {
        p.ellipse(50, 50, 80, 80); // Simple placeholder for Space Invaders or Farm Math
      };
    };
    new p5(sketch, sketchRef.current);

    const updateScore = async () => {
      setScore(100);
      await supabase.from('scores').insert([{ user_id: user.id, score: 100 }]);
      localStorage.setItem('gameScore', '100');
    };
    updateScore();
  }, [user]);

  if (!user) return <p>Loading...</p>;

  return (
    <div className="game">
      <h2>Farm Math Adventure / Space Invaders</h2>
      <div ref={sketchRef}></div>
      <p>Score: {score}</p>
      <button>Start Game</button>
      <button>Play Fullscreen</button>
      <button>Upgrade to Premium</button>
    </div>
  );
};

export default Game;