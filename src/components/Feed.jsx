import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

const safeWords = ['fun', 'fact', 'animal', 'share', 'favorite'];

function Feed({ user }) {
  const [feedItems, setFeedItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [error, setError] = useState(null);
  const [dragAnswers, setDragAnswers] = useState([]);

  useEffect(() => {
    const fetchFeed = async () => {
      try {
        const { data, error } = await supabase.from('feed').select('*').eq('age_group', user.ageGroup).limit(20);
        if (error) throw error;
        const socialItems = data.filter(item => item.type === 'social' && safeWords.some(word => item.text?.toLowerCase().includes(word)));
        const educationalItems = data.filter(item => item.type === 'educational' && item.grade <= user.grade);
        const gameItems = data.filter(item => item.type === 'game');
        const total = socialItems.length + educationalItems.length + gameItems.length;
        const socialCount = Math.ceil(total * 0.6);
        const shuffled = [
          ...socialItems.sort(() => Math.random() - 0.5).slice(0, socialCount),
          ...educationalItems.sort(() => Math.random() - 0.5),
          ...gameItems.sort(() => Math.random() - 0.5)
        ];
        setFeedItems(shuffled);
      } catch (err) {
        setError('Failed to load feed. Please try again.');
        console.error('Error fetching feed:', err);
      }
    };
    fetchFeed();
    const channel = supabase
      .channel('feed-updates')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'feed' }, fetchFeed)
      .subscribe();
    return () => supabase.removeChannel(channel);
  }, [user]);

  const handleAnswer = async (item, answer) => {
    if (item.type === 'educational') {
      const isCorrect = answer === item.correct || answer.toLowerCase() === item.word?.toLowerCase();
      if (isCorrect) {
        try {
          await supabase.from('user_progress').insert({
            user_id: user.id,
            item_id: item.id,
            points: 10
          });
          setModal(null);
          setDragAnswers([]);
        } catch (error) {
          setError('Error saving progress. Please try again.');
          console.error('Error saving progress:', error);
        }
      } else {
        setError('Incorrect answer. Try again!');
      }
    }
  };

  const handleDragEnd = (result, item) => {
    if (!result.destination) return;
    const items = [...dragAnswers];
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);
    setDragAnswers(items);
    const isCorrect = items.join(',') === item.correct;
    if (isCorrect) {
      handleAnswer(item, item.correct);
    }
  };

  if (error) {
    return <div className="p-4 text-red-500" aria-live="assertive">{error}</div>;
  }

  return (
    <div className="p-4">
      {feedItems.map(item => (
        <div
          key={item.id}
          className={`p-4 mb-4 rounded-lg shadow-md ${
            item.type === 'social'
              ? 'border-2 border-blue-500'
              : item.type === 'educational'
              ? 'border-2 border-green-500'
              : 'border-2 border-yellow-500'
          }`}
          onClick={() => item.type === 'educational' && setModal(item)}
          role="article"
        >
          {item.type === 'social' && <p>{item.text}</p>}
          {item.type === 'educational' && (
            <div>
              <p className="font-bold">
                {item.subject} ({item.standard}): {item.question}
              </p>
              {item.format === 'multiple-choice' && (
                <div>
                  {item.options.map(option => (
                    <button
                      key={option}
                      className="bg-blue-500 text-white p-2 m-2 rounded hover:bg-blue-600"
                      onClick={() => handleAnswer(item, option)}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              )}
              {item.format === 'hangman' && (
                <input
                  type="text"
                  className="border p-2 mt-2 w-full"
                  placeholder="Enter the word"
                  onChange={e => handleAnswer(item, e.target.value)}
                />
              )}
              {item.format === 'drag-and-drop' && (
                <DragDropContext onDragEnd={result => handleDragEnd(result, item)}>
                  <Droppable droppableId="answers">
                    {(provided) => (
                      <div {...provided.droppableProps} ref={provided.innerRef}>
                        {item.options.map((option, index) => (
                          <Draggable key={option} draggableId={option} index={index}>
                            {(provided) => (
                              <div
                                ref={provided.innerRef}
                                {...provided.draggableProps}
                                {...provided.dragHandleProps}
                                className="bg-gray-200 p-2 m-2 rounded"
                              >
                                {option}
                              </div>
                            )}
                          </Draggable>
                        ))}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                </DragDropContext>
              )}
            </div>
          )}
          {item.type === 'game' && (
            <Link to="/game" className="text-blue-500 underline hover:text-blue-700">
              Play {item.name}
            </Link>
          )}
        </div>
      ))}
      {modal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center" role="dialog">
          <div className="bg-white p-6 rounded-lg">
            <p className="mb-4">Complete to Continue: {modal.question}</p>
            {modal.format === 'multiple-choice' && (
              <div>
                {modal.options.map(option => (
                  <button
                    key={option}
                    className="bg-blue-500 text-white p-2 m-2 rounded hover:bg-blue-600"
                    onClick={() => handleAnswer(modal, option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            )}
            {modal.format === 'hangman' && (
              <input
                type="text"
                className="border p-2 w-full"
                placeholder="Enter the word"
                onChange={e => handleAnswer(modal, e.target.value)}
              />
            )}
            {modal.format === 'drag-and-drop' && (
              <DragDropContext onDragEnd={result => handleDragEnd(result, modal)}>
                <Droppable droppableId="answers">
                  {(provided) => (
                    <div {...provided.droppableProps} ref={provided.innerRef}>
                      {modal.options.map((option, index) => (
                        <Draggable key={option} draggableId={option} index={index}>
                          {(provided) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              className="bg-gray-200 p-2 m-2 rounded"
                            >
                              {option}
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                    </div>
                  )}
                </Droppable>
              </DragDropContext>
            )}
            <button
              className="bg-red-500 text-white p-2 mt-4 rounded hover:bg-red-600"
              onClick={() => setModal(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Feed;