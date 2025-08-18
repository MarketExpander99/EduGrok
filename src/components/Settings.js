import React, { useState, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { supabase } from '../utils/api';

const daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const Settings = () => {
  const { user } = useUser();
  const [offlineMode, setOfflineMode] = useState(false);
  const [schedule, setSchedule] = useState({
    active7Days: false,
    selectedDays: [],
    timeSegments: [{ start: '09:00', end: '12:00' }],
  });

  useEffect(() => {
    const fetchSettings = async () => {
      if (!user) return;
      const { data } = await supabase.from('users').select('offline_mode, schedule').eq('id', user.id);
      if (data[0]) {
        setOfflineMode(data[0].offline_mode);
        setSchedule(data[0].schedule || { active7Days: false, selectedDays: [], timeSegments: [] });
      }
    };
    fetchSettings();
  }, [user]);

  if (!user) return <p>Loading...</p>;

  const toggleOffline = async () => {
    const newMode = !offlineMode;
    setOfflineMode(newMode);
    await supabase.from('users').update({ offline_mode: newMode }).eq('id', user.id);
  };

  const handleScheduleChange = async (updatedSchedule) => {
    setSchedule(updatedSchedule);
    await supabase.from('users').update({ schedule: updatedSchedule }).eq('id', user.id);
  };

  const toggleActive7Days = () => {
    const newActive = !schedule.active7Days;
    handleScheduleChange({
      ...schedule,
      active7Days: newActive,
      selectedDays: newActive ? daysOfWeek.map((_, i) => i + 1) : [],
    });
  };

  const toggleDay = (dayIndex) => {
    const newDays = schedule.selectedDays.includes(dayIndex)
      ? schedule.selectedDays.filter(d => d !== dayIndex)
      : [...schedule.selectedDays, dayIndex];
    handleScheduleChange({ ...schedule, selectedDays: newDays });
  };

  const addTimeSegment = () => {
    handleScheduleChange({
      ...schedule,
      timeSegments: [...schedule.timeSegments, { start: '13:00', end: '15:00' }],
    });
  };

  const updateTimeSegment = (index, field, value) => {
    const newSegments = [...schedule.timeSegments];
    newSegments[index][field] = value;
    handleScheduleChange({ ...schedule, timeSegments: newSegments });
  };

  const removeTimeSegment = (index) => {
    const newSegments = schedule.timeSegments.filter((_, i) => i !== index);
    handleScheduleChange({ ...schedule, timeSegments: newSegments });
  };

  return (
    <div className="settings">
      <h2>Settings</h2>
      <label>
        Offline Mode:
        <input type="checkbox" checked={offlineMode} onChange={toggleOffline} />
      </label>
      <p>Language: English (Placeholder)</p>
      <h3>Lesson Schedule</h3>
      <label>
        Active 7 Days a Week:
        <input type="checkbox" checked={schedule.active7Days} onChange={toggleActive7Days} />
      </label>
      {!schedule.active7Days && (
        <div>
          <h4>Select Days:</h4>
          {daysOfWeek.map((day, index) => (
            <label key={day}>
              <input
                type="checkbox"
                checked={schedule.selectedDays.includes(index + 1)}
                onChange={() => toggleDay(index + 1)}
              />
              {day}
            </label>
          ))}
        </div>
      )}
      <h4>Time Segments:</h4>
      {schedule.timeSegments.map((segment, index) => (
        <div key={index}>
          <input
            type="time"
            value={segment.start}
            onChange={(e) => updateTimeSegment(index, 'start', e.target.value)}
          />
          to
          <input
            type="time"
            value={segment.end}
            onChange={(e) => updateTimeSegment(index, 'end', e.target.value)}
          />
          <button onClick={() => removeTimeSegment(index)}>Remove</button>
        </div>
      ))}
      <button onClick={addTimeSegment}>Add Time Segment</button>
    </div>
  );
};

export default Settings;