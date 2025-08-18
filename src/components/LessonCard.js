import React from 'react';

const LessonCard = ({ lesson }) => {
  return (
    <div className="lesson-card">
      <h3>{lesson.title}</h3>
      <p>{lesson.content}</p>
      {/* Add interactive elements like buttons for starting lesson */}
    </div>
  );
};

export default LessonCard;