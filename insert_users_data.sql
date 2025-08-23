-- Insert test users into the users table with email
INSERT INTO users (id, email, age, grade) VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'user1@example.com', 7, 2),
  ('550e8400-e29b-41d4-a716-446655440001', 'user2@example.com', 9, 4),
  ('550e8400-e29b-41d4-a716-446655440002', 'user3@example.com', 6, 1)
  ON CONFLICT (id) DO NOTHING;