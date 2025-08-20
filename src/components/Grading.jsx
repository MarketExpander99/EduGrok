import { useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

function Grading({ user, setUser }) {
  const [quiz] = useState([
    { question: 'What is 1 + 1?', options: ['1', '2', '3'], correct: '2', subject: 'Math', weight: 0.4 },
    { question: "Spell 'Cat'", word: 'Cat', format: 'hangman', subject: 'English', weight: 0.3 },
    { question: 'What is the largest planet?', options: ['Earth', 'Jupiter', 'Mars'], correct: 'Jupiter', subject: 'Science', weight: 0.3 }
  ]);
  const [answers, setAnswers] = useState([]);
  const [grade, setGrade] = useState(null);
  const [feedback, setFeedback] = useState([]);

  const handleAnswer = async (index, answer) => {
    const isCorrect = answer === quiz[index].correct || answer.toLowerCase() === quiz[index].word?.toLowerCase();
    setAnswers([...answers.slice(0, index), answer, ...answers.slice(index + 1)]);
    setFeedback([...feedback.slice(0, index), isCorrect ? 'Correct!' : 'Try again!', ...feedback.slice(index + 1)]);
    if (isCorrect) {
      try {
        await supabase.from('quiz_results').insert({
          user_id: user.id,
          question_id: index,
          answer,
          is_correct: true
        });
      } catch (error) {
        console.error('Error saving quiz result:', error);
      }
    }
  };

  const handleSubmit = async () => {
    const score = answers.reduce((acc, ans, i) => {
      const isCorrect = ans === quiz[i].correct || ans.toLowerCase() === quiz[i].word?.toLowerCase();
      return acc + (isCorrect ? quiz[i].weight : 0);
    }, 0);
    const calculatedGrade = Math.min(Math.floor(user.age * 0.5 + score * 6), 12);
    setGrade(calculatedGrade);
    try {
      await supabase.from('users').update({ grade: calculatedGrade }).eq('id', user.id);
      setUser({ ...user, grade: calculatedGrade });
    } catch (error) {
      console.error('Error updating grade:', error);
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Assessment Quiz</h2>
      {quiz.map((q, i) => (
        <div key={i} className="mb-4">
          <p className="font-bold">{q.question}</p>
          {q.format === 'multiple-choice' ? (
            q.options.map(opt => (
              <button
                key={opt}
                className="bg-blue-500 text-white p-2 m-2 rounded hover:bg-blue-600"
                onClick={() => handleAnswer(i, opt)}
              >
                {opt}
              </button>
            ))
          ) : (
            <input
              type="text"
              className="border p-2 w-full"
              placeholder="Enter the word"
              onChange={e => handleAnswer(i, e.target.value)}
            />
          )}
          {feedback[i] && <p className={feedback[i] === 'Correct!' ? 'text-green-500' : 'text-red-500'}>{feedback[i]}</p>}
        </div>
      ))}
      <button
        className="bg-green-500 text-white p-2 rounded hover:bg-green-600"
        onClick={handleSubmit}
        disabled={answers.length < quiz.length}
      >
        Submit
      </button>
      {grade && <p className="mt-4" aria-live="polite">Assigned Grade: {grade}</p>}
    </div>
  );
}

export default Grading;